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
from warhammer40k_ai.engine.session_store import load_session_replay_reader

OVERLAY_BG = (16, 18, 24, 216)
OVERLAY_TEXT = (236, 236, 236)
OVERLAY_MUTED = (176, 182, 193)
OVERLAY_ACCENT = (122, 190, 255)


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
    reader = load_session_replay_reader(session_id, base_dir=args.replay_dir)
    resolved = Path(args.replay_dir).expanduser().resolve() / session_id / "replay.sqlite3"
    return reader, str(resolved)


def _clamp_decision_idx(raw_idx: int, total_decisions: int) -> int:
    idx = int(raw_idx)
    if idx < 0:
        return 0
    if idx > int(total_decisions):
        return int(total_decisions)
    return idx


def _load_game_for_index(reader: ReplayStoreReader, decision_idx: int):
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
        step = reader.get_step(decision_idx)
        request_payload = reader.get_request_payload(decision_idx)
        record = reader.get_decision_record(decision_idx)
        prompt = str(request_payload.get("prompt", "") or "").strip()
        chosen_label = _chosen_option_label(request_payload, str(step.chosen_option_id))
        lines.append((f"{step.phase} | turn {step.turn_id} | {step.decision_type}", OVERLAY_TEXT))
        lines.append((f"actor {step.actor_player_id} ({step.controller_kind})", OVERLAY_MUTED))
        if prompt:
            for wrapped in _wrap_text(f"prompt: {prompt}", width=68):
                lines.append((wrapped, OVERLAY_TEXT))
        if chosen_label:
            lines.append((f"chosen option: {chosen_label}", OVERLAY_TEXT))
        lines.append((f"chosen action: {step.chosen_action_id}", OVERLAY_MUTED))
        lines.append((f"events: {len(reader.get_events_for_decision(decision_idx))}", OVERLAY_MUTED))
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


def _draw_overlay(screen: pygame.Surface, lines: list[tuple[str, tuple[int, int, int]]]) -> None:
    font = pygame.font.SysFont("Arial", 16)
    line_height = font.get_linesize()
    width = min(720, max(420, int(screen.get_width() * 0.42)))
    height = min(screen.get_height() - 24, 20 + (len(lines) * line_height))
    panel = pygame.Surface((width, height), pygame.SRCALPHA)
    panel.fill(OVERLAY_BG)
    y = 10
    for text, color in lines:
        rendered = font.render(text, True, color)
        panel.blit(rendered, (12, y))
        y += line_height
    screen.blit(panel, (12, 12))


def main() -> int:
    args = _parse_args()
    reader, source_label = _load_reader(args)
    metadata = reader.metadata()
    total_decisions = reader.decision_count()
    decision_idx = _clamp_decision_idx(args.decision_idx, total_decisions)

    screen = create_pygame_screen(title=_window_title(metadata, source_label, decision_idx, total_decisions))
    game = _load_game_for_index(reader, decision_idx)
    player1, player2 = _resolve_players(game)
    ui_interface = HumanUIInterface(screen.get_width(), screen.get_height())
    game_view = GameView(screen, None, game, getattr(game, "map", None), player1, player2, ui_interface)
    overlay_lines = _overlay_lines(reader, metadata, source_label, decision_idx, total_decisions)

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
                    overlay_lines = _overlay_lines(reader, metadata, source_label, decision_idx, total_decisions)
                    pygame.display.set_caption(_window_title(metadata, source_label, decision_idx, total_decisions))
                    continue
            if game_view.handle_pygame_event(event):
                continue

        game_view.draw()
        _draw_overlay(screen, overlay_lines)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
