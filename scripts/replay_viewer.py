#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from warhammer40k_ai.UI.game_ui import GameView
from warhammer40k_ai.UI.human_interface import HumanUIInterface
from warhammer40k_ai.UI.window import create_pygame_screen
from warhammer40k_ai.engine.replay_store import ReplayStoreReader
from warhammer40k_ai.engine.session_store import load_session_replay_reader, resolve_session_replay_path
from warhammer40k_ai.utility.event_bus import clear_recent_logs, get_recent_actions, get_recent_dice

OVERLAY_BG = (16, 18, 24, 216)
OVERLAY_TEXT = (236, 236, 236)
OVERLAY_MUTED = (176, 182, 193)
OVERLAY_ACCENT = (122, 190, 255)
OVERLAY_BORDER = (88, 103, 129, 255)
OVERLAY_HEADER_BG = (27, 35, 49, 244)
OVERLAY_SHADOW = (0, 0, 0, 112)
OVERLAY_MARGIN = 16
OVERLAY_GRAB_MARGIN = 48


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load a replay store and step through the game decision-by-decision in the Pygame UI."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--replay-path", default="", help="Path to a replay.sqlite3 file.")
    source.add_argument("--session-id", default="", help="Session id containing replay.sqlite3.")
    parser.add_argument(
        "--replay-dir",
        default="games/data",
        help="Base directory for session replay lookup when --session-id is used (default: games/data).",
    )
    parser.add_argument(
        "--decision-idx",
        type=int,
        default=0,
        help="Initial decision index to load. 0 is the initial keyframe before the first decision.",
    )
    return parser.parse_args()


def _load_reader(args: argparse.Namespace) -> tuple[ReplayStoreReader, str]:
    replay_path = str(args.replay_path or "").strip()
    if replay_path:
        path = Path(replay_path).expanduser().resolve()
        return ReplayStoreReader(path), str(path)
    session_id = str(args.session_id or "").strip()
    if not session_id:
        raise ValueError("Either --replay-path or --session-id is required.")
    replay_base_dir = Path(args.replay_dir).expanduser().resolve()
    reader = load_session_replay_reader(session_id, base_dir=replay_base_dir)
    resolved = resolve_session_replay_path(session_id, base_dir=replay_base_dir)
    return reader, str(resolved)


def _clamp_decision_idx(raw_idx: int, total_decisions: int) -> int:
    idx = int(raw_idx)
    if idx < 0:
        return 0
    if idx > int(total_decisions):
        return int(total_decisions)
    return idx


def _load_game_for_index(reader: ReplayStoreReader, decision_idx: int):
    clear_recent_logs()
    game = reader.reconstruct_game_at_decision(decision_idx, strict=True)
    game.is_authoritative = False
    return game


def _resolve_players(game) -> tuple[object, object]:
    players = list(getattr(game, "players", []) or [])
    if len(players) < 2:
        raise RuntimeError("Replay viewer requires a replay with two players.")
    return players[0], players[1]


def _window_title(metadata: dict[str, object], source_label: str, decision_idx: int, total_decisions: int) -> str:
    label = str(metadata.get("label", "") or "").strip()
    session_id = str(metadata.get("session_id", "") or "").strip()
    descriptor = label or session_id or Path(source_label).name
    return f"Warhammer 40,000 Replay Viewer - {descriptor} [{decision_idx}/{total_decisions}]"


def _replay_label_armies(metadata: dict[str, object], source_label: str) -> tuple[str, str]:
    label = str(metadata.get("label", "") or "").strip()
    descriptor = label or Path(source_label).stem
    if "_vs_" not in descriptor:
        return "", ""
    player1_label, player2_label = descriptor.split("_vs_", 1)
    return player1_label.strip(), player2_label.strip()


def _player_army_label(player: object) -> str:
    get_army = getattr(player, "get_army", None)
    army = get_army() if callable(get_army) else getattr(player, "army", None)
    if army is None:
        return ""
    for attr_name in ("name", "label", "faction"):
        value = str(getattr(army, attr_name, "") or "").strip()
        if value:
            return value
    return ""


def _actor_player_label(
    game: object,
    actor_player_id: str,
    metadata: dict[str, object],
    source_label: str,
) -> str:
    actor_id = str(actor_player_id or "").strip()
    if not actor_id:
        return "unknown player"
    replay_army_labels = _replay_label_armies(metadata, source_label)
    for index, player in enumerate(list(getattr(game, "players", []) or [])):
        player_id = str(getattr(player, "id", "") or "").strip()
        if player_id != actor_id:
            continue
        slot_label = f"Player {index + 1}"
        player_name = str(getattr(player, "name", "") or "").strip()
        label = player_name if player_name else slot_label
        if label.lower() == slot_label.lower():
            label = slot_label
        else:
            label = f"{slot_label}: {label}"
        army_label = replay_army_labels[index] if index < len(replay_army_labels) else ""
        army_label = str(army_label or _player_army_label(player)).strip()
        if army_label:
            label = f"{label} - {army_label}"
        return label
    return f"unknown player {actor_id[:8]}"


def _step_jump(event: pygame.event.Event, total_decisions: int, current_idx: int) -> int | None:
    if event.key == pygame.K_HOME:
        return 0
    if event.key == pygame.K_END:
        return int(total_decisions)
    if event.key == pygame.K_PAGEUP:
        return max(0, int(current_idx) - 25)
    if event.key == pygame.K_PAGEDOWN:
        return min(int(total_decisions), int(current_idx) + 25)
    stride = 10 if bool(event.mod & pygame.KMOD_SHIFT) else 1
    if event.key == pygame.K_LEFT:
        return max(0, int(current_idx) - stride)
    if event.key == pygame.K_RIGHT:
        return min(int(total_decisions), int(current_idx) + stride)
    return None


def _chosen_option_label(request_payload: dict[str, object], chosen_option_id: str) -> str:
    option_id = str(chosen_option_id or "")
    for entry in list(request_payload.get("options", []) or []):
        payload = dict(entry or {})
        if str(payload.get("option_id", "") or "") == option_id:
            label = str(payload.get("label", "") or "").strip()
            if label:
                return label
    return ""


def _selected_option_entry(
    request_payload: dict[str, object],
    *,
    chosen_option_id: str,
    chosen_action_id: str,
) -> dict[str, object]:
    option_id = str(chosen_option_id or "")
    action_id = str(chosen_action_id or "")
    for entry in list(request_payload.get("options", []) or []):
        option = dict(entry or {})
        if option_id and str(option.get("option_id", "") or "") == option_id:
            return option
    if not action_id:
        return {}
    for entry in list(request_payload.get("options", []) or []):
        option = dict(entry or {})
        payload = dict(option.get("payload", {}) or {})
        if str(payload.get("action_id", "") or "") == action_id:
            return option
    return {}


def _selected_action_payload(
    request_payload: dict[str, object],
    record: dict[str, object],
    *,
    chosen_option_id: str,
    chosen_action_id: str,
) -> dict[str, object]:
    option = _selected_option_entry(
        request_payload,
        chosen_option_id=chosen_option_id,
        chosen_action_id=chosen_action_id,
    )
    payload = dict(option.get("payload", {}) or {})
    target_action_id = str(chosen_action_id or "")
    if not target_action_id:
        return payload
    for entry in list(record.get("candidates", []) or []):
        candidate = dict(entry or {})
        if str(candidate.get("action_id", "") or "") != target_action_id:
            continue
        params = dict(candidate.get("params", {}) or {})
        metadata = dict(candidate.get("metadata", {}) or {})
        resolved_payload = dict(metadata.get("resolved_result_payload", {}) or {})
        if params:
            merged = dict(payload)
            merged.update(params)
            if resolved_payload:
                merged.update(resolved_payload)
            return merged
        if resolved_payload:
            merged = dict(payload)
            merged.update(resolved_payload)
            return merged
    return payload


def _selected_move_unit_lines(
    request_payload: dict[str, object],
    record: dict[str, object],
    step: object,
) -> list[str]:
    if str(getattr(step, "decision_type", "") or "") != "MOVE_UNIT":
        return []
    context = dict(request_payload.get("context", {}) or {})
    payload = _selected_action_payload(
        request_payload,
        record,
        chosen_option_id=str(getattr(step, "chosen_option_id", "") or ""),
        chosen_action_id=str(getattr(step, "chosen_action_id", "") or ""),
    )
    placement_kind = str(payload.get("placement_kind", "") or context.get("placement_kind", "") or "").strip().lower()
    movement_type = str(payload.get("movement_type", "") or context.get("movement_type", "") or "").strip().lower()
    positions = [
        dict(entry or {})
        for entry in list(
            payload.get("model_positions", [])
            or context.get("deployment_model_positions", [])
            or context.get("model_positions", [])
            or []
        )
        if isinstance(entry, dict)
    ]
    if not positions:
        return []
    if placement_kind == "deployment" or movement_type == "deploy":
        summary = "chosen placement"
    else:
        movement_label = movement_type.replace("_", " ").strip()
        if not movement_label or movement_label == "move":
            summary = "chosen move"
        else:
            summary = f"chosen {movement_label} move"
    model_word = "model" if len(positions) == 1 else "models"
    lines = [f"{summary}: {len(positions)} {model_word}"]
    for idx, entry in enumerate(positions, start=1):
        pos = list(entry.get("position", []) or [])
        if len(pos) < 2:
            continue
        try:
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) >= 3 else 0.0
            facing = float(entry.get("facing", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        lines.append(f"{idx}. ({x:.1f}, {y:.1f}, {z:.1f}, {facing:.1f})")
    return lines


def _wrap_text(text: str, *, width: int) -> list[str]:
    words = str(text or "").split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= int(width):
            current = candidate
            continue
        lines.append(current)
        current = word
    lines.append(current)
    return lines


def _overlay_lines(
    reader: ReplayStoreReader,
    metadata: dict[str, object],
    source_label: str,
    decision_idx: int,
    total_decisions: int,
    game,
) -> list[tuple[str, tuple[int, int, int]]]:
    lines: list[tuple[str, tuple[int, int, int]]] = []
    label = str(metadata.get("label", "") or "").strip()
    session_id = str(metadata.get("session_id", "") or "").strip()
    title = label or session_id or Path(source_label).name
    lines.append((title, OVERLAY_ACCENT))
    lines.append((f"Decision {decision_idx}/{total_decisions}", OVERLAY_TEXT))
    if decision_idx == 0:
        lines.append(("Initial state before the first recorded decision.", OVERLAY_TEXT))
    else:
        lines.append(("Showing settled state after the selected decision.", OVERLAY_MUTED))
        step = reader.get_step(decision_idx)
        request_payload = reader.get_request_payload(decision_idx)
        record = reader.get_decision_record(decision_idx)
        prompt = str(request_payload.get("prompt", "") or "").strip()
        chosen_label = _chosen_option_label(request_payload, str(step.chosen_option_id))
        chosen_move_lines = _selected_move_unit_lines(request_payload, record, step)
        if not bool(getattr(game, "setup_complete", True)):
            setup_phase = str(getattr(getattr(game, "setup_phase", None), "name", "") or "SETUP")
            lines.append((f"setup phase: {setup_phase}", OVERLAY_TEXT))
            lines.append((f"decision type: {step.decision_type}", OVERLAY_TEXT))
        else:
            lines.append((f"phase: {step.phase} | turn {step.turn_id}", OVERLAY_TEXT))
            lines.append((f"decision type: {step.decision_type}", OVERLAY_TEXT))
        actor_label = _actor_player_label(game, str(step.actor_player_id), metadata, source_label)
        actor_id = str(step.actor_player_id or "").strip()
        lines.append((f"actor: {actor_label}", OVERLAY_TEXT))
        if actor_id:
            lines.append((f"controller: {step.controller_kind} | id {actor_id[:8]}", OVERLAY_MUTED))
        else:
            lines.append((f"controller: {step.controller_kind}", OVERLAY_MUTED))
        if prompt:
            for wrapped in _wrap_text(f"prompt: {prompt}", width=68):
                lines.append((wrapped, OVERLAY_TEXT))
        if chosen_move_lines:
            for entry in chosen_move_lines:
                lines.append((entry, OVERLAY_TEXT))
        elif chosen_label:
            lines.append((f"chosen option: {chosen_label}", OVERLAY_TEXT))
        lines.append((f"chosen action: {step.chosen_action_id}", OVERLAY_MUTED))
        lines.append((f"recorded events: {len(reader.get_events_for_decision(decision_idx))}", OVERLAY_MUTED))
        if step.time_budget_ms is not None:
            lines.append((f"time: {step.wall_clock_ms}ms / budget {step.time_budget_ms}ms", OVERLAY_MUTED))
        else:
            lines.append((f"time: {step.wall_clock_ms}ms", OVERLAY_MUTED))
        outcome = dict(record.get("outcome", {}) or {})
        immediate = dict(outcome.get("immediate_deltas", {}) or {})
        errors = list(immediate.get("errors", []) or [])
        if errors:
            lines.append((f"errors: {'; '.join(str(err) for err in errors)}", OVERLAY_MUTED))
    lines.append(("", OVERLAY_TEXT))
    lines.append(("Controls", OVERLAY_ACCENT))
    lines.append(("Left/Right: step 1 decision", OVERLAY_MUTED))
    lines.append(("Shift+Left/Right: step 10 decisions", OVERLAY_MUTED))
    lines.append(("PageUp/PageDown: step 25 decisions", OVERLAY_MUTED))
    lines.append(("Home/End: first/last decision", OVERLAY_MUTED))
    lines.append(("Esc: quit", OVERLAY_MUTED))
    return lines


def _coerce_roll_values(payload: dict[str, object]) -> list[int]:
    values: list[int] = []
    for entry in list(payload.get("dice", []) or []):
        if isinstance(entry, bool):
            continue
        if isinstance(entry, int):
            values.append(entry)
            continue
        if isinstance(entry, float) and entry.is_integer():
            values.append(int(entry))
            continue
        if isinstance(entry, str) and entry.strip().lstrip("-").isdigit():
            values.append(int(entry.strip()))
    if values:
        return values
    value = payload.get("value")
    if isinstance(value, bool):
        return values
    if isinstance(value, int):
        return [value]
    if isinstance(value, float) and value.is_integer():
        return [int(value)]
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return [int(value.strip())]
    return values


def _format_roll_line(payload: dict[str, object]) -> str:
    dice_values = _coerce_roll_values(payload)
    if not dice_values:
        return ""
    reason = str(payload.get("reason", "") or "").strip()
    if reason.startswith("get_roll(") and reason.endswith(")"):
        die_label = reason[len("get_roll(") : -1].strip()
        if die_label.startswith("1D"):
            die_label = die_label[1:]
        reason = f"Generic {die_label} roll" if die_label else "Generic roll"
    if not reason:
        roll_type = str(payload.get("roll_type", "") or "").strip().replace("_", " ")
        reason = f"{roll_type.title()} roll" if roll_type else "Replay roll"
    dice_text = ", ".join(str(value) for value in dice_values)
    total = payload.get("value")
    if len(dice_values) > 1 and isinstance(total, int):
        return f"{reason}: {dice_text} = {int(total)}"
    return f"{reason}: {dice_text}"


def _selected_decision_event_end(reader: ReplayStoreReader, decision_idx: int) -> int | None:
    if int(decision_idx) <= 0:
        return None
    step = reader.get_step(decision_idx)
    decision_id = str(getattr(step, "decision_id", "") or "")
    fallback_end = getattr(step, "event_end_id", None)
    if not decision_id:
        return int(fallback_end) if fallback_end is not None else None
    for event in reader.get_events_for_decision(decision_idx):
        if str(event.get("type", "") or "") != "decision_resolved":
            continue
        payload = dict(event.get("payload", {}) or {})
        if str(payload.get("decision_id", "") or "") == decision_id:
            return int(event.get("event_id", 0) or 0)
    return int(fallback_end) if fallback_end is not None else None


def _replay_dice_log_overrides(
    reader: ReplayStoreReader,
    decision_idx: int,
    player_to_key: dict[str, str],
) -> dict[str, list[str]]:
    event_end_id = _selected_decision_event_end(reader, decision_idx)
    if event_end_id is None:
        return {key: [] for key in player_to_key.values()}
    get_events_until = getattr(reader, "get_events_until_event_id", None)
    if callable(get_events_until):
        events = list(get_events_until(event_end_id))
    else:
        events = [
            event
            for event in reader.get_events_for_decision(decision_idx)
            if int(event.get("event_id", 0) or 0) <= int(event_end_id)
        ]
    lines_by_key = {key: [] for key in player_to_key.values()}
    for event in events:
        if str(event.get("type", "") or "") != "roll_made":
            continue
        payload = dict(event.get("payload", {}) or {})
        player_key = player_to_key.get(str(payload.get("player_id", "") or ""))
        if not player_key:
            continue
        line = _format_roll_line(payload)
        if not line:
            continue
        merged = list(lines_by_key.get(player_key, []))
        if line not in merged:
            merged.append(line)
        lines_by_key[player_key] = merged[-50:]
    return lines_by_key


def _build_hud_log_overrides(reader: ReplayStoreReader, decision_idx: int, game) -> dict[str, list[str]]:
    player1, player2 = _resolve_players(game)
    player_to_key = {
        str(getattr(player1, "id", "") or ""): "p1_dice",
        str(getattr(player2, "id", "") or ""): "p2_dice",
    }
    dice_overrides = (
        _replay_dice_log_overrides(reader, decision_idx, player_to_key)
        if int(decision_idx) > 0
        else {"p1_dice": list(get_recent_dice(player1, limit=50)), "p2_dice": list(get_recent_dice(player2, limit=50))}
    )
    overrides = {
        "p1_actions": list(get_recent_actions(player1, limit=50)),
        "p1_dice": list(dice_overrides.get("p1_dice", [])),
        "p2_actions": list(get_recent_actions(player2, limit=50)),
        "p2_dice": list(dice_overrides.get("p2_dice", [])),
    }
    return overrides


def _overlay_fonts():
    font_module = getattr(pygame, "font", None)
    if font_module is None:
        return None, None
    get_init = getattr(font_module, "get_init", None)
    init = getattr(font_module, "init", None)
    if callable(get_init) and callable(init) and not bool(get_init()):
        init()
    try:
        return font_module.SysFont("Arial", 18, bold=True), font_module.SysFont("Arial", 16)
    except (AttributeError, pygame.error):
        return font_module.Font(None, 18), font_module.Font(None, 16)


def _font_linesize(font: object, default: int) -> int:
    get_linesize = getattr(font, "get_linesize", None)
    if not callable(get_linesize):
        return int(default)
    try:
        value = get_linesize()
    except (AttributeError, TypeError, ValueError, pygame.error):
        return int(default)
    if isinstance(value, bool):
        return int(default)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float) and value > 0:
        return int(value)
    return int(default)


def _overlay_layout(
    screen: pygame.Surface,
    lines: list[tuple[str, tuple[int, int, int]]],
    position: tuple[int, int] | None = None,
) -> dict[str, int]:
    title_font, body_font = _overlay_fonts()
    if title_font is None or body_font is None:
        line_height = 19
        header_height = 38
    else:
        line_height = _font_linesize(body_font, 19)
        header_height = _font_linesize(title_font, 22) + 16
    width = min(560, max(420, int(screen.get_width() * 0.34)))
    height = min(screen.get_height() - (OVERLAY_MARGIN * 2), header_height + 18 + (len(lines) * line_height))
    if position is None:
        x = max(OVERLAY_MARGIN, screen.get_width() - width - 24)
        y = 24
        min_x = OVERLAY_MARGIN
        max_x = max(OVERLAY_MARGIN, screen.get_width() - width - OVERLAY_MARGIN)
        min_y = OVERLAY_MARGIN
        max_y = max(OVERLAY_MARGIN, screen.get_height() - height - OVERLAY_MARGIN)
    else:
        x = int(position[0])
        y = int(position[1])
        min_x = min(OVERLAY_MARGIN, OVERLAY_GRAB_MARGIN - width)
        max_x = max(OVERLAY_MARGIN, screen.get_width() - OVERLAY_GRAB_MARGIN)
        min_y = min(OVERLAY_MARGIN, OVERLAY_GRAB_MARGIN - height)
        max_y = max(OVERLAY_MARGIN, screen.get_height() - OVERLAY_GRAB_MARGIN)
    return {
        "x": min(max(min_x, x), max_x),
        "y": min(max(min_y, y), max_y),
        "width": int(width),
        "height": int(height),
        "header_height": int(header_height),
        "line_height": int(line_height),
    }


def _point_in_layout(layout: dict[str, int], point: tuple[int, int]) -> bool:
    px, py = point
    return (
        layout["x"] <= int(px) <= (layout["x"] + layout["width"])
        and layout["y"] <= int(py) <= (layout["y"] + layout["height"])
    )


def _point_in_overlay_header(layout: dict[str, int], point: tuple[int, int]) -> bool:
    px, py = point
    return (
        layout["x"] <= int(px) <= (layout["x"] + layout["width"])
        and layout["y"] <= int(py) <= (layout["y"] + layout["header_height"])
    )


def _point_in_overlay_drag_region(layout: dict[str, int], point: tuple[int, int]) -> bool:
    return _point_in_layout(layout, point)


def _draw_overlay(
    screen: pygame.Surface,
    lines: list[tuple[str, tuple[int, int, int]]],
    position: tuple[int, int] | None = None,
) -> dict[str, int]:
    layout = _overlay_layout(screen, lines, position=position)
    title_font, body_font = _overlay_fonts()
    x = layout["x"]
    y = layout["y"]
    width = layout["width"]
    height = layout["height"]
    header_height = layout["header_height"]
    line_height = layout["line_height"]

    shadow = pygame.Surface((width + 8, height + 8), pygame.SRCALPHA)
    shadow.fill(OVERLAY_SHADOW)
    screen.blit(shadow, (x + 6, y + 6))

    panel = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(panel, OVERLAY_BG, panel.get_rect(), border_radius=12)
    pygame.draw.rect(panel, OVERLAY_BORDER, panel.get_rect(), width=2, border_radius=12)
    pygame.draw.rect(
        panel,
        OVERLAY_HEADER_BG,
        pygame.Rect(0, 0, width, header_height),
        border_top_left_radius=12,
        border_top_right_radius=12,
    )
    if title_font is not None:
        title = title_font.render("Replay Controls", True, OVERLAY_TEXT)
        panel.blit(title, (16, max(0, (header_height - title.get_height()) // 2)))

    y_cursor = header_height + 10
    if body_font is not None:
        for text, color in lines:
            if (y_cursor + line_height) > (height - 10):
                break
            rendered = body_font.render(text, True, color)
            panel.blit(rendered, (16, y_cursor))
            y_cursor += line_height
    screen.blit(panel, (x, y))
    return layout


def main() -> int:
    args = _parse_args()
    reader, source_label = _load_reader(args)
    metadata = reader.metadata()
    total_decisions = reader.decision_count()
    decision_idx = _clamp_decision_idx(args.decision_idx, total_decisions)

    screen = create_pygame_screen(title=_window_title(metadata, source_label, decision_idx, total_decisions))
    game = _load_game_for_index(reader, decision_idx)
    player1, player2 = _resolve_players(game)
    hud_log_overrides = _build_hud_log_overrides(reader, decision_idx, game)
    ui_interface = HumanUIInterface(screen.get_width(), screen.get_height())
    game_view = GameView(screen, None, game, getattr(game, "map", None), player1, player2, ui_interface)
    game_view.hud_log_overrides = hud_log_overrides
    overlay_lines = _overlay_lines(reader, metadata, source_label, decision_idx, total_decisions, game)
    overlay_state = {
        "lines": overlay_lines,
        "position": None,
        "layout": _overlay_layout(screen, overlay_lines, position=None),
        "dragging": False,
        "drag_offset": (0, 0),
    }
    overlay_state["position"] = (overlay_state["layout"]["x"], overlay_state["layout"]["y"])

    def _render_overlay(surface: pygame.Surface) -> None:
        layout = _draw_overlay(surface, overlay_state["lines"], position=overlay_state["position"])
        if isinstance(layout, dict):
            overlay_state["layout"] = layout
            overlay_state["position"] = (layout["x"], layout["y"])

    game_view.post_draw_callback = _render_overlay

    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue
            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                ui_interface.screen_width = event.w
                ui_interface.screen_height = event.h
                game_view.screen = screen
                game_view.resize_layout(event.w, event.h)
                layout = _overlay_layout(screen, overlay_state["lines"], position=overlay_state["position"])
                overlay_state["layout"] = layout
                overlay_state["position"] = (layout["x"], layout["y"])
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and int(getattr(event, "button", 0) or 0) == 1:
                layout = overlay_state["layout"]
                pos = tuple(getattr(event, "pos", (0, 0)) or (0, 0))
                if _point_in_overlay_drag_region(layout, pos):
                    overlay_state["dragging"] = True
                    overlay_state["drag_offset"] = (int(pos[0]) - layout["x"], int(pos[1]) - layout["y"])
                    continue
                if _point_in_layout(layout, pos):
                    continue
            if event.type == pygame.MOUSEBUTTONUP and int(getattr(event, "button", 0) or 0) == 1:
                if bool(overlay_state["dragging"]):
                    overlay_state["dragging"] = False
                    continue
            if event.type == pygame.MOUSEMOTION and bool(overlay_state["dragging"]):
                pos = tuple(getattr(event, "pos", (0, 0)) or (0, 0))
                drag_offset = tuple(overlay_state.get("drag_offset", (0, 0)) or (0, 0))
                overlay_state["position"] = (
                    int(pos[0]) - int(drag_offset[0]),
                    int(pos[1]) - int(drag_offset[1]),
                )
                layout = _overlay_layout(screen, overlay_state["lines"], position=overlay_state["position"])
                overlay_state["layout"] = layout
                overlay_state["position"] = (layout["x"], layout["y"])
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    continue
                next_idx = _step_jump(event, total_decisions, decision_idx)
                if next_idx is not None and next_idx != decision_idx:
                    decision_idx = next_idx
                    game = _load_game_for_index(reader, decision_idx)
                    player1, player2 = _resolve_players(game)
                    game_view.set_game(game, getattr(game, "map", None), player1, player2)
                    game_view.hud_log_overrides = _build_hud_log_overrides(reader, decision_idx, game)
                    overlay_lines = _overlay_lines(reader, metadata, source_label, decision_idx, total_decisions, game)
                    overlay_state["lines"] = overlay_lines
                    layout = _overlay_layout(screen, overlay_state["lines"], position=overlay_state["position"])
                    overlay_state["layout"] = layout
                    overlay_state["position"] = (layout["x"], layout["y"])
                    pygame.display.set_caption(_window_title(metadata, source_label, decision_idx, total_decisions))
                    continue
            if game_view.handle_pygame_event(event):
                continue

        game_view.draw()
        clock.tick(60)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
