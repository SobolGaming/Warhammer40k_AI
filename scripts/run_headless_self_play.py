#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.deployment_headless import DeterministicDeploymentDecisionMaker
from warhammer40k_ai.engine.decision_record import merge_decision_records_by_id
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.engine.local_runtime import LocalAuthoritativeRuntime
from warhammer40k_ai.engine.replay_store import DEFAULT_KEYFRAME_INTERVAL
from warhammer40k_ai.engine.reward_profile import (
    annotate_decision_records_with_rewards,
    list_reward_profile_ids,
)
from warhammer40k_ai.engine.session_store import (
    create_session,
    enable_session_replay_recording,
    save_session_snapshot,
)
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.ml.llm_agents import build_llm_router_from_config_file
from warhammer40k_ai.utility.profiling_controller import ProfilingController

logger = logging.getLogger(__name__)


def _safe_profile_label(value: str) -> str:
    raw = str(value or "profile").strip() or "profile"
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in raw)
    return cleaned.strip("._") or "profile"


def _dump_profile_artifacts(
    controller: ProfilingController,
    *,
    label: str,
    metadata: dict[str, object],
) -> dict[str, str]:
    controller.disable()
    try:
        txt_path, prof_path = controller.dump(
            label=_safe_profile_label(label),
            write_binary_prof=True,
            metadata=dict(metadata or {}),
        )
    except RuntimeError:
        return {}
    artifacts = {"profile_text": str(txt_path.resolve())}
    if prof_path is not None:
        artifacts["profile_binary"] = str(prof_path.resolve())
    return artifacts


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, set):
        return [_json_safe(inner) for inner in sorted(value, key=lambda entry: str(entry))]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())
    return str(value)


class _JsonArrayWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle = None
        self._first = True

    def __enter__(self) -> "_JsonArrayWriter":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8")
        self._handle.write("[\n")
        return self

    def write(self, value: Any) -> None:
        if self._handle is None:
            raise RuntimeError("JSON array writer is not open.")
        if not self._first:
            self._handle.write(",\n")
        json.dump(_json_safe(value), self._handle, indent=2, sort_keys=True, ensure_ascii=True)
        self._first = False

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._handle is None:
            return
        self._handle.write("\n]\n")
        self._handle.close()
        self._handle = None


def _write_json_array(path: Path, values: list[Any] | tuple[Any, ...]) -> None:
    with _JsonArrayWriter(path) as writer:
        for value in list(values or []):
            writer.write(value)


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON array at {path}.")
    return [dict(item or {}) for item in list(payload or [])]


def _collect_tool_action_probe_diagnostics(game: object) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in list(getattr(game, "tool_action_probe_diagnostics", []) or []):
        item = _json_safe(dict(entry or {}))
        key = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        if key in seen:
            continue
        seen.add(key)
        diagnostics.append(dict(item))
    for player in list(getattr(game, "players", []) or []):
        manager = getattr(player, "stratagems", None)
        get_diagnostics = getattr(manager, "get_tool_action_probe_diagnostics", None)
        if not callable(get_diagnostics):
            continue
        for entry in list(get_diagnostics() or []):
            item = _json_safe(dict(entry or {}))
            key = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            if key in seen:
                continue
            seen.add(key)
            diagnostics.append(dict(item))
    return diagnostics


def _collect_reserve_arrival_diagnostics(game: object) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in list(getattr(game, "reserve_arrival_diagnostics", []) or []):
        item = _json_safe(dict(entry or {}))
        key = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        if key in seen:
            continue
        seen.add(key)
        diagnostics.append(dict(item))
    return diagnostics


def _tool_action_probe_diagnostic_summary(diagnostics: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for diagnostic in list(diagnostics or []):
        item = dict(diagnostic or {})
        tool_name = str(item.get("tool_name", "") or "<unknown>")
        code = str(item.get("code", "") or "<unknown>")
        severity = str(item.get("severity", "") or "WARNING")
        counts[f"{severity}:{tool_name}:{code}"] += 1
    return dict(counts)


def _setup_logging(log_level: str) -> logging.Logger:
    level_name = str(log_level or "WARNING").strip().upper() or "WARNING"
    level = logging.getLevelNamesMapping().get(level_name, logging.WARNING)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    return logging.getLogger(__name__)


def _game_id_for_index(game_index: int, *, seed_base: int | None = None) -> str:
    if seed_base is not None:
        return f"selfplay:{int(seed_base) + int(game_index)}"
    return f"selfplay:{int(game_index):06d}"


def _army_label_from_path(path: str) -> str:
    path_text = str(path or "").strip()
    if not path_text:
        return "unknown_army"
    parsed = Path(path_text)
    return parsed.stem or parsed.name or path_text


def _army_labels_from_paths(player1_army_file: str, player2_army_file: str) -> tuple[str, str]:
    player1_label = _army_label_from_path(player1_army_file)
    player2_label = _army_label_from_path(player2_army_file)
    if player1_label != player2_label:
        return player1_label, player2_label

    def _with_parent(path: str, label: str, fallback_prefix: str) -> str:
        parent_name = Path(str(path or "")).parent.name
        if parent_name:
            return f"{parent_name}:{label}"
        return f"{fallback_prefix}:{label}"

    player1_disambiguated = _with_parent(player1_army_file, player1_label, "player1")
    player2_disambiguated = _with_parent(player2_army_file, player2_label, "player2")
    if player1_disambiguated == player2_disambiguated:
        return f"player1:{player1_label}", f"player2:{player2_label}"
    return player1_disambiguated, player2_disambiguated


def _resolved_replay_base_dir(path: str | None) -> Path | None:
    path_text = str(path or "").strip()
    if not path_text:
        return None
    return Path(path_text).expanduser().resolve()


def _allocate_replay_session_id(
    game: Game,
    *,
    replay_base_dir: Path,
    preferred_session_id: str,
    label: str,
) -> str:
    preferred_id = str(preferred_session_id or "").strip()
    if not preferred_id:
        raise ValueError("Preferred replay session id is required.")
    suffix = 0
    candidate_session_id = preferred_id
    while True:
        try:
            create_session(
                game,
                base_dir=replay_base_dir,
                session_id=candidate_session_id,
                label=label,
            )
            return candidate_session_id
        except FileExistsError:
            suffix += 1
            candidate_session_id = f"{preferred_id}:run{suffix:03d}"


def _export_decision_records(records: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    safe_records = _json_safe(list(records or []))
    return merge_decision_records_by_id(list(safe_records or []))


def _player_score(player: object) -> int:
    getter = getattr(player, "get_score", None)
    value = getter() if callable(getter) else getattr(player, "score", 0)
    return int(value or 0)


def _winner_summary(
    *,
    winner: object | None,
    player1: object,
    player2: object,
    player1_label: str,
    player2_label: str,
) -> tuple[str, str, dict[str, int]]:
    player1_score = _player_score(player1)
    player2_score = _player_score(player2)
    scoreboard = {
        str(player1_label or "player1"): player1_score,
        str(player2_label or "player2"): player2_score,
    }
    if winner is player1 or str(getattr(winner, "id", "") or "") == str(getattr(player1, "id", "") or ""):
        return player1_label, f"<SCORE: {player1_score} vs {player2_score}>", scoreboard
    if winner is player2 or str(getattr(winner, "id", "") or "") == str(getattr(player2, "id", "") or ""):
        return player2_label, f"<SCORE: {player2_score} vs {player1_score}>", scoreboard
    return "tie", f"<SCORE: {player1_score} vs {player2_score}>", scoreboard


def _current_player_label(game: object) -> str:
    getter = getattr(game, "get_current_player", None)
    player = getter() if callable(getter) else None
    if player is None:
        return "unknown"
    players = list(getattr(game, "players", []) or [])
    player_id = str(getattr(player, "id", "") or "")
    for index, candidate in enumerate(players, start=1):
        candidate_id = str(getattr(candidate, "id", "") or "")
        if candidate is player or (player_id and candidate_id and candidate_id == player_id):
            return str(index)
    return player_id or str(getattr(player, "name", "") or "unknown")


def _current_phase_step_label(game: object) -> str:
    if bool(getattr(game, "reinforcements_step_active", False)):
        return "REINFORCEMENTS"
    queue = getattr(game, "decision_queue", None)
    requests = list(queue.list() or []) if queue is not None and hasattr(queue, "list") else []
    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
    for request in requests:
        ctx = dict(getattr(request, "context", {}) or {})
        request_phase = str(ctx.get("phase_name", "") or "").strip().upper()
        request_step = str(ctx.get("phase_step", "") or "").strip().upper()
        if request_phase != phase_name or not request_step:
            continue
        return request_step
    if phase_name == "FIGHT_PHASE":
        manager = getattr(game, "fight_phase_manager", None)
        stage = str(getattr(getattr(manager, "current_stage", None), "name", "") or "").strip().upper()
        if stage and stage != "COMPLETE":
            return stage
    return "PHASE_START"


def _phase_state_summary(game: object) -> str:
    if bool(getattr(game, "is_in_setup_phase", lambda: False)()):
        getter = getattr(game, "get_current_setup_phase", None)
        setup_phase = getter() if callable(getter) else None
        setup_phase_name = str(getattr(setup_phase, "name", "") or "UNKNOWN")
        return f"pre-deployment setup_phase={setup_phase_name}"
    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "UNKNOWN")
    battle_round = int(getattr(game, "turn", 0) or 0)
    return (
        f"post-deployment player={_current_player_label(game)} "
        f"battle_round={battle_round} phase={phase_name} step={_current_phase_step_label(game)}"
    )


def _log_phase_state_if_changed(
    game: Game,
    *,
    game_id: str,
    enabled: bool,
    last_state: str | None,
) -> str:
    state = _phase_state_summary(game)
    if enabled and state != str(last_state or ""):
        logger.info("(%s %s)", str(game_id or ""), state)
    return state


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic headless self-play and export DecisionRecords."
    )
    parser.add_argument("--player1-army", default="army_lists/chaos_test.txt")
    parser.add_argument("--player2-army", default="army_lists/aeldari_test.txt")
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Root logging level for headless self-play.",
    )
    parser.add_argument(
        "--log-phase-transitions",
        action="store_true",
        help=(
            "Emit INFO logs for setup/battle phase-state transitions using the per-game id. "
            "Format: '(<game_id> <pre/post-deployment state ...>)'."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes for parallel self-play generation (default: 1).",
    )
    parser.add_argument(
        "--seed-base",
        type=int,
        default=None,
        help="Optional deterministic base seed; each game uses seed_base + game_index.",
    )
    parser.add_argument(
        "--reserve-policy",
        default="forced_only",
        choices=("forced_only", "balanced"),
        help=(
            "Reserve declaration policy for deterministic deployment. "
            "'forced_only' keeps optional units on the board for faster/stabler headless play."
        ),
    )
    parser.add_argument(
        "--max-reserves-arrival-seconds",
        type=float,
        default=10.0,
        help="Hard wall-clock cap per reserves-arrival placement decision (default: 10.0).",
    )
    parser.add_argument(
        "--deployment-ranker-model",
        default="",
        help=(
            "Optional path to a deployment ranking model JSON. "
            "When provided, zone/next-unit deployment choices are ranked from candidate metadata."
        ),
    )
    parser.add_argument(
        "--llm-agent-config",
        default="",
        help=(
            "Optional JSON config for LLM-backed hierarchical AI agents. "
            "LLM choices are validated against legal candidates and fall back to deterministic rankers."
        ),
    )
    parser.add_argument(
        "--disable-tool-decisions",
        action="store_true",
        help="Disable optional generic tool-action decisions such as opportunistic stratagem reactions.",
    )
    parser.add_argument("--max-phase-steps", type=int, default=80)
    parser.add_argument(
        "--output",
        default="data/headless_self_play_decision_records.json",
        help="Output JSON path for exported DecisionRecords.",
    )
    parser.add_argument(
        "--reward-profile",
        default="dense_vp_delta_v1",
        choices=list_reward_profile_ids(),
        help="Reward profile applied to exported records.",
    )
    parser.add_argument(
        "--no-reward-annotation",
        action="store_true",
        help="Disable reward annotation and export raw engine DecisionRecords.",
    )
    parser.add_argument(
        "--replay-dir",
        default="",
        help=(
            "Optional base directory for per-game replay sessions. "
            "Each game writes a filesystem-safe session directory under <replay-dir> containing "
            "{manifest.json,snapshot.json,replay.sqlite3}; the manifest preserves the original game id. "
            "Because game ids are stable, reuse a fresh directory or remove conflicting session subdirectories first."
        ),
    )
    parser.add_argument(
        "--replay-keyframe-interval",
        type=int,
        default=DEFAULT_KEYFRAME_INTERVAL,
        help=(
            "Decision interval for sparse replay keyframes when --replay-dir is enabled "
            f"(default: {DEFAULT_KEYFRAME_INTERVAL})."
        ),
    )
    parser.add_argument(
        "--report-output",
        default="",
        help="Optional JSON report path with per-game outcomes, diagnostics, and aggregate self-play metadata.",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable per-game cProfile and section-timer profiling artifacts.",
    )
    parser.add_argument(
        "--profile-dir",
        default="profiles",
        help="Directory for profiling artifacts when --profile is enabled.",
    )
    parser.add_argument(
        "--profile-sort",
        default="tottime",
        help="pstats sort key for readable profiling reports.",
    )
    parser.add_argument(
        "--profile-lines",
        type=int,
        default=120,
        help="Number of pstats rows to include in readable profiling reports.",
    )
    parser.add_argument(
        "--profile-label",
        default="",
        help="Optional label prefix for profiling artifact filenames.",
    )
    return parser.parse_args()


def _drain_pending_decisions(
    game: Game,
    *,
    max_attempts: int = 4000,
    game_id: str = "",
    log_phase_transitions: bool = False,
    last_state: str | None = None,
) -> str | None:
    queue = getattr(game, "decision_queue", None)
    event_system = getattr(game, "event_system", None)
    if queue is None or event_system is None:
        return last_state

    attempts = 0
    while True:
        request = queue.peek()
        if request is None:
            return _log_phase_state_if_changed(
                game,
                game_id=str(game_id or ""),
                enabled=bool(log_phase_transitions),
                last_state=last_state,
            )
        if attempts >= int(max_attempts):
            raise RuntimeError(
                f"Unable to resolve pending decision after {max_attempts} attempts: "
                f"{getattr(request, 'decision_type', '')}"
            )
        decision_id_before = str(getattr(request, "decision_id", "") or "")
        event_system.publish("decision_requested", request=request, game=game)
        last_state = _log_phase_state_if_changed(
            game,
            game_id=str(game_id or ""),
            enabled=bool(log_phase_transitions),
            last_state=last_state,
        )
        request_after = queue.peek()
        if request_after is None:
            return last_state
        decision_id_after = str(getattr(request_after, "decision_id", "") or "")
        if decision_id_after == decision_id_before:
            raise RuntimeError(
                "Headless policy could not resolve decision "
                f"{decision_id_after} ({getattr(request_after, 'decision_type', '')})."
            )
        attempts += 1


def _run_single_game(
    *,
    game_id: str,
    player1_army_file: str,
    player2_army_file: str,
    max_phase_steps: int,
    game_seed: int | None = None,
    reserve_policy: str = "forced_only",
    max_reserves_arrival_seconds: float = 10.0,
    deployment_ranker_model: str | None = None,
    llm_agent_config: str | None = None,
    enable_tool_decisions: bool = True,
    log_phase_transitions: bool = False,
    replay_dir: str | None = None,
    replay_keyframe_interval: int = DEFAULT_KEYFRAME_INTERVAL,
) -> dict[str, Any]:
    stable_game_id = str(game_id or "")
    player1_label, player2_label = _army_labels_from_paths(player1_army_file, player2_army_file)
    player1 = Player("Player 1", control=PlayerControl.REMOTE)
    player2 = Player("Player 2", control=PlayerControl.REMOTE)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player1, player2])
    game.session_id = stable_game_id
    replay_base_dir = _resolved_replay_base_dir(replay_dir)
    replay_path: Path | None = None
    snapshot_path: Path | None = None
    replay_label = f"{player1_label}_vs_{player2_label}"
    replay_session_id = stable_game_id
    if replay_base_dir is not None:
        replay_session_id = _allocate_replay_session_id(
            game,
            replay_base_dir=replay_base_dir,
            preferred_session_id=stable_game_id,
            label=replay_label,
        )
        replay_path = enable_session_replay_recording(
            game,
            base_dir=replay_base_dir,
            session_id=replay_session_id,
            label=replay_label,
            keyframe_interval=max(1, int(replay_keyframe_interval or DEFAULT_KEYFRAME_INTERVAL)),
        )
        game.session_id = stable_game_id
    if game_seed is not None:
        random_source = getattr(game, "random_source", None)
        seed_fn = getattr(random_source, "seed", None)
        if callable(seed_fn):
            seed_fn(int(game_seed))
    ai_router = None
    llm_config_text = str(llm_agent_config or "").strip()
    if llm_config_text:
        ai_router = build_llm_router_from_config_file(llm_config_text)
    controller = HeadlessPolicyDecisionController(
        game=game,
        auto_attach=True,
        max_reserves_arrival_seconds=float(max_reserves_arrival_seconds),
        reserve_policy=str(reserve_policy or "forced_only"),
        ai_router=ai_router,
        enable_tool_decisions=bool(enable_tool_decisions),
    )
    game._headless_disable_generic_tool_decisions = not bool(enable_tool_decisions)
    runtime = LocalAuthoritativeRuntime(
        game,
        player1_army_file=player1_army_file,
        player2_army_file=player2_army_file,
        manual_phases=False,
    )
    session_game = runtime.game_proxy

    deployment_decision_makers = {
        player1.id: DeterministicDeploymentDecisionMaker(
            game,
            reserve_policy=str(reserve_policy or "forced_only"),
            ranker_model_path=str(deployment_ranker_model or ""),
        ),
        player2.id: DeterministicDeploymentDecisionMaker(
            game,
            reserve_policy=str(reserve_policy or "forced_only"),
            ranker_model_path=str(deployment_ranker_model or ""),
        ),
    }

    last_state = _log_phase_state_if_changed(
        game,
        game_id=str(game_id or ""),
        enabled=bool(log_phase_transitions),
        last_state=None,
    )
    while session_game.is_in_setup_phase():
        if runtime.is_driver_managed_setup_phase():
            runtime.run_setup_autosteps()
            last_state = _drain_pending_decisions(
                game,
                game_id=str(game_id or ""),
                log_phase_transitions=bool(log_phase_transitions),
                last_state=last_state,
            )
            last_state = _log_phase_state_if_changed(
                game,
                game_id=str(game_id or ""),
                enabled=bool(log_phase_transitions),
                last_state=last_state,
            )
            continue
        setup_kwargs: dict[str, Any] = {
            "player1_army_file": player1_army_file,
            "player2_army_file": player2_army_file,
        }
        phase_name = str(getattr(session_game.get_current_setup_phase(), "name", "") or "")
        if phase_name == "DEPLOY_ARMIES":
            setup_kwargs["decision_makers"] = deployment_decision_makers
        session_game.execute_current_setup_phase(**setup_kwargs)
        last_state = _drain_pending_decisions(
            game,
            game_id=str(game_id or ""),
            log_phase_transitions=bool(log_phase_transitions),
            last_state=last_state,
        )
        session_game.advance_setup_phase()
        last_state = _drain_pending_decisions(
            game,
            game_id=str(game_id or ""),
            log_phase_transitions=bool(log_phase_transitions),
            last_state=last_state,
        )
        last_state = _log_phase_state_if_changed(
            game,
            game_id=str(game_id or ""),
            enabled=bool(log_phase_transitions),
            last_state=last_state,
        )

    phase_steps = 0
    last_state = _log_phase_state_if_changed(
        game,
        game_id=str(game_id or ""),
        enabled=bool(log_phase_transitions),
        last_state=last_state,
    )
    while not session_game.is_game_over():
        if phase_steps >= int(max_phase_steps):
            raise RuntimeError(f"Headless game hit max phase steps ({max_phase_steps}) before game over.")
        last_state = _drain_pending_decisions(
            game,
            game_id=str(game_id or ""),
            log_phase_transitions=bool(log_phase_transitions),
            last_state=last_state,
        )
        session_game.next_phase()
        last_state = _drain_pending_decisions(
            game,
            game_id=str(game_id or ""),
            log_phase_transitions=bool(log_phase_transitions),
            last_state=last_state,
        )
        phase_steps += 1
        last_state = _log_phase_state_if_changed(
            game,
            game_id=str(game_id or ""),
            enabled=bool(log_phase_transitions),
            last_state=last_state,
        )

    winner = game.get_winner()
    winner_army_label, winner_score_line, scoreboard = _winner_summary(
        winner=winner,
        player1=player1,
        player2=player2,
        player1_label=player1_label,
        player2_label=player2_label,
    )
    if replay_base_dir is not None:
        snapshot_path = save_session_snapshot(
            game,
            base_dir=replay_base_dir,
            session_id=replay_session_id,
            label=replay_label,
        )
        game.session_id = stable_game_id
    records = _export_decision_records(list(getattr(game.decision_record_store, "records", []) or []))
    tool_action_probe_diagnostics = _collect_tool_action_probe_diagnostics(game)
    reserve_arrival_diagnostics = _collect_reserve_arrival_diagnostics(game)
    get_reserves_metrics = getattr(controller, "get_reserves_arrival_search_metrics", None)
    reserves_arrival_search_metrics = list(get_reserves_metrics() or []) if callable(get_reserves_metrics) else []
    deployment_search_metrics = {
        str(player_id): list(getattr(maker, "get_deployment_search_metrics", lambda: [])() or [])
        for player_id, maker in dict(deployment_decision_makers or {}).items()
    }
    collect_llm_traces = getattr(ai_router, "collect_component_traces", None)
    llm_agent_traces = list(collect_llm_traces() or []) if callable(collect_llm_traces) else []
    return {
        "game_id": stable_game_id,
        "records": records,
        "phase_steps": int(phase_steps),
        "winner_player_id": str(getattr(winner, "id", "") or ""),
        "winner_army_label": str(winner_army_label or ""),
        "winner_score_line": str(winner_score_line or ""),
        "scoreboard": scoreboard,
        "tool_action_probe_diagnostics": tool_action_probe_diagnostics,
        "reserve_arrival_diagnostics": reserve_arrival_diagnostics,
        "reserves_arrival_search_metrics": reserves_arrival_search_metrics,
        "deployment_search_metrics": deployment_search_metrics,
        "llm_agent_traces": llm_agent_traces,
        "replay_session_id": replay_session_id if replay_path is not None else "",
        "replay_path": str(replay_path) if replay_path is not None else "",
        "snapshot_path": str(snapshot_path) if snapshot_path is not None else "",
    }


def _run_single_game_job(
    game_index: int,
    *,
    player1_army_file: str,
    player2_army_file: str,
    max_phase_steps: int,
    seed_base: int | None = None,
    reserve_policy: str = "forced_only",
    max_reserves_arrival_seconds: float = 10.0,
    deployment_ranker_model: str | None = None,
    llm_agent_config: str | None = None,
    enable_tool_decisions: bool = True,
    log_level: str = "WARNING",
    log_phase_transitions: bool = False,
    replay_dir: str | None = None,
    replay_keyframe_interval: int = DEFAULT_KEYFRAME_INTERVAL,
    profile: bool = False,
    profile_dir: str = "profiles",
    profile_sort: str = "tottime",
    profile_lines: int = 120,
    profile_label: str = "",
) -> dict[str, Any]:
    _setup_logging(str(log_level or "WARNING"))
    game_seed = None
    if seed_base is not None:
        game_seed = int(seed_base) + int(game_index)
    game_id = _game_id_for_index(int(game_index), seed_base=seed_base)
    profile_controller: ProfilingController | None = None
    profile_artifacts: dict[str, str] = {}
    label_prefix = str(profile_label or "headless_self_play")
    if bool(profile):
        profile_controller = ProfilingController(
            out_dir=str(profile_dir or "profiles"),
            sort_by=str(profile_sort or "tottime"),
            lines=max(1, int(profile_lines or 120)),
        )
        profile_controller.reset()
        profile_controller.enable()
    started_at = time.perf_counter()
    try:
        result = _run_single_game(
            game_id=str(game_id),
            player1_army_file=player1_army_file,
            player2_army_file=player2_army_file,
            max_phase_steps=max_phase_steps,
            game_seed=game_seed,
            reserve_policy=str(reserve_policy or "forced_only"),
            max_reserves_arrival_seconds=float(max_reserves_arrival_seconds),
            deployment_ranker_model=str(deployment_ranker_model or ""),
            llm_agent_config=str(llm_agent_config or ""),
            enable_tool_decisions=bool(enable_tool_decisions),
            log_phase_transitions=bool(log_phase_transitions),
            replay_dir=str(replay_dir or ""),
            replay_keyframe_interval=max(1, int(replay_keyframe_interval or DEFAULT_KEYFRAME_INTERVAL)),
        )
        elapsed_s = float(time.perf_counter() - started_at)
    finally:
        if profile_controller is not None:
            elapsed_for_profile = float(time.perf_counter() - started_at)
            profile_artifacts = _dump_profile_artifacts(
                profile_controller,
                label=f"{label_prefix}_{game_id}_pid{os.getpid()}",
                metadata={
                    "script": "scripts/run_headless_self_play.py",
                    "game_id": str(game_id),
                    "game_index": int(game_index),
                    "workers_profile_scope": "worker_game_job",
                    "elapsed_wall_seconds": round(elapsed_for_profile, 6),
                },
            )
    serialized_result = {
        "game_id": str(result.get("game_id", "") or ""),
        "records": _json_safe(list(result.get("records", []) or [])),
        "phase_steps": int(result.get("phase_steps", 0) or 0),
        "winner_player_id": str(result.get("winner_player_id", "") or ""),
        "winner_army_label": str(result.get("winner_army_label", "") or ""),
        "winner_score_line": str(result.get("winner_score_line", "") or ""),
        "scoreboard": _json_safe(dict(result.get("scoreboard", {}) or {})),
        "tool_action_probe_diagnostics": _json_safe(list(result.get("tool_action_probe_diagnostics", []) or [])),
        "reserve_arrival_diagnostics": _json_safe(list(result.get("reserve_arrival_diagnostics", []) or [])),
        "reserves_arrival_search_metrics": _json_safe(list(result.get("reserves_arrival_search_metrics", []) or [])),
        "deployment_search_metrics": _json_safe(dict(result.get("deployment_search_metrics", {}) or {})),
        "llm_agent_traces": _json_safe(list(result.get("llm_agent_traces", []) or [])),
        "replay_session_id": str(result.get("replay_session_id", "") or ""),
        "replay_path": str(result.get("replay_path", "") or ""),
        "snapshot_path": str(result.get("snapshot_path", "") or ""),
    }
    if profile_artifacts:
        serialized_result["profile_artifacts"] = dict(profile_artifacts)
    return {
        "game_index": int(game_index),
        "elapsed_seconds": elapsed_s,
        "result": serialized_result,
    }


def run_headless_self_play(
    *,
    player1_army: str,
    player2_army: str,
    games: int,
    workers: int,
    max_phase_steps: int,
    log_level: str = "WARNING",
    log_phase_transitions: bool = False,
    seed_base: int | None = None,
    reserve_policy: str = "forced_only",
    max_reserves_arrival_seconds: float = 10.0,
    deployment_ranker_model: str = "",
    llm_agent_config: str = "",
    enable_tool_decisions: bool = True,
    output: str = "data/headless_self_play_decision_records.json",
    reward_profile: str = "dense_vp_delta_v1",
    no_reward_annotation: bool = False,
    replay_dir: str = "",
    replay_keyframe_interval: int = DEFAULT_KEYFRAME_INTERVAL,
    report_output: str = "",
    profile: bool = False,
    profile_dir: str = "profiles",
    profile_sort: str = "tottime",
    profile_lines: int = 120,
    profile_label: str = "",
) -> dict[str, Any]:
    _setup_logging(str(log_level))
    games = max(1, int(games or 1))
    workers = max(1, int(workers or 1))
    max_phase_steps = max(1, int(max_phase_steps or 1))
    output_path = Path(str(output))
    spool_dir = output_path.parent / f".{output_path.name}.parts"
    if spool_dir.exists():
        shutil.rmtree(spool_dir)
    spool_dir.mkdir(parents=True, exist_ok=True)
    exported_record_count = 0
    total_phase_steps = 0
    decision_type_counts: Counter[str] = Counter()
    tool_probe_diagnostic_counts: Counter[str] = Counter()
    reserve_arrival_diagnostic_counts: Counter[str] = Counter()
    llm_agent_trace_counts: Counter[str] = Counter()
    per_game_outputs: list[dict[str, Any]] = []
    game_outcomes: dict[str, dict[str, Any]] = {}

    def _spool_completed_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
        game_index = int(payload.get("game_index", 0) or 0)
        result = dict(payload.get("result", {}) or {})
        records = list(result.pop("records", []) or [])
        part_path = spool_dir / f"game_{game_index:06d}.json"
        _write_json_array(part_path, records)
        payload["result"] = result
        payload["records_part_path"] = str(part_path)
        payload["record_count"] = int(len(records))
        return records

    if workers == 1 or games == 1:
        for game_index in range(games):
            payload = _run_single_game_job(
                game_index,
                player1_army_file=str(player1_army),
                player2_army_file=str(player2_army),
                max_phase_steps=max_phase_steps,
                seed_base=seed_base,
                reserve_policy=str(reserve_policy),
                max_reserves_arrival_seconds=float(max_reserves_arrival_seconds),
                deployment_ranker_model=str(deployment_ranker_model),
                llm_agent_config=str(llm_agent_config),
                enable_tool_decisions=bool(enable_tool_decisions),
                log_level=str(log_level),
                log_phase_transitions=bool(log_phase_transitions),
                replay_dir=str(replay_dir),
                replay_keyframe_interval=int(replay_keyframe_interval),
                profile=bool(profile),
                profile_dir=str(profile_dir),
                profile_sort=str(profile_sort),
                profile_lines=int(profile_lines),
                profile_label=str(profile_label),
            )
            result = dict(payload.get("result", {}) or {})
            records = _spool_completed_payload(payload)
            per_game_outputs.append(payload)
            game_id = str(result.get("game_id", "") or "")
            print(
                f"Completed game {game_index + 1}/{games} ({game_id}) in "
                f"{float(payload.get('elapsed_seconds', 0.0) or 0.0):.2f}s "
                f"(phase_steps={int(result.get('phase_steps', 0) or 0)}, records={len(records)})"
            )
            diagnostic_summary = _tool_action_probe_diagnostic_summary(
                list(result.get("tool_action_probe_diagnostics", []) or [])
            )
            if diagnostic_summary:
                print(f"Tool probe diagnostics for game {game_index + 1}: {diagnostic_summary}")
    else:
        max_workers = min(workers, games)
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    _run_single_game_job,
                    game_index,
                    player1_army_file=str(player1_army),
                    player2_army_file=str(player2_army),
                    max_phase_steps=max_phase_steps,
                    seed_base=seed_base,
                    reserve_policy=str(reserve_policy),
                    max_reserves_arrival_seconds=float(max_reserves_arrival_seconds),
                    deployment_ranker_model=str(deployment_ranker_model),
                    llm_agent_config=str(llm_agent_config),
                    enable_tool_decisions=bool(enable_tool_decisions),
                    log_level=str(log_level),
                    log_phase_transitions=bool(log_phase_transitions),
                    replay_dir=str(replay_dir),
                    replay_keyframe_interval=int(replay_keyframe_interval),
                    profile=bool(profile),
                    profile_dir=str(profile_dir),
                    profile_sort=str(profile_sort),
                    profile_lines=int(profile_lines),
                    profile_label=str(profile_label),
                )
                for game_index in range(games)
            ]
            for future in as_completed(futures):
                payload = dict(future.result() or {})
                game_index = int(payload.get("game_index", 0) or 0)
                result = dict(payload.get("result", {}) or {})
                records = _spool_completed_payload(payload)
                per_game_outputs.append(payload)
                game_id = str(result.get("game_id", "") or "")
                print(
                    f"Completed game {game_index + 1}/{games} ({game_id}) in "
                    f"{float(payload.get('elapsed_seconds', 0.0) or 0.0):.2f}s "
                    f"(phase_steps={int(result.get('phase_steps', 0) or 0)}, records={len(records)})"
                )
                diagnostic_summary = _tool_action_probe_diagnostic_summary(
                    list(result.get("tool_action_probe_diagnostics", []) or [])
                )
                if diagnostic_summary:
                    print(f"Tool probe diagnostics for game {game_index + 1}: {diagnostic_summary}")

    per_game_outputs.sort(key=lambda item: int(item.get("game_index", 0) or 0))
    with _JsonArrayWriter(output_path) as output_writer:
        for payload in per_game_outputs:
            result = dict(payload.get("result", {}) or {})
            part_path = Path(str(payload.get("records_part_path", "") or ""))
            records = _load_json_array(part_path) if part_path.is_file() else []
            total_phase_steps += int(result.get("phase_steps", 0) or 0)
            winner_army_label = str(result.get("winner_army_label", "") or "")
            winner_score_line = str(result.get("winner_score_line", "") or "")
            scoreboard = dict(result.get("scoreboard", {}) or {})
            game_id = str(result.get("game_id", "") or "")
            if game_id:
                game_outcomes[game_id] = {
                    "winner": winner_army_label or "tie",
                    "score": winner_score_line,
                    "scoreboard": scoreboard,
                }
            for record in records:
                decision_type = str(record.get("decision_type", "") or "")
                if decision_type:
                    decision_type_counts[decision_type] += 1
            for diagnostic in list(result.get("tool_action_probe_diagnostics", []) or []):
                item = dict(diagnostic or {})
                tool_name = str(item.get("tool_name", "") or "<unknown>")
                code = str(item.get("code", "") or "<unknown>")
                severity = str(item.get("severity", "") or "WARNING")
                tool_probe_diagnostic_counts[f"{severity}:{tool_name}:{code}"] += 1
            for diagnostic in list(result.get("reserve_arrival_diagnostics", []) or []):
                item = dict(diagnostic or {})
                code = str(item.get("code", "") or "<unknown>")
                severity = str(item.get("severity", "") or "WARNING")
                reserve_arrival_diagnostic_counts[f"{severity}:{code}"] += 1
            for trace in list(result.get("llm_agent_traces", []) or []):
                item = dict(trace or {})
                component = str(item.get("component_name", "") or "<unknown>")
                legal = bool(item.get("legal", False))
                error = str(item.get("error", "") or "")
                status = "legal" if legal else ("error" if error else "illegal")
                llm_agent_trace_counts[f"{component}:{status}"] += 1

            exported_game_records = merge_decision_records_by_id(records)
            if not bool(no_reward_annotation):
                exported_game_records = annotate_decision_records_with_rewards(
                    exported_game_records,
                    profile_id=str(reward_profile),
                )
            exported_game_records = merge_decision_records_by_id(list(_json_safe(exported_game_records) or []))
            for record in exported_game_records:
                output_writer.write(record)
                exported_record_count += 1
    shutil.rmtree(spool_dir)

    print(f"Games: {games}")
    print(f"Workers: {workers}")
    print(f"Phase steps: {total_phase_steps}")
    print(f"Decision records: {exported_record_count}")
    if not bool(no_reward_annotation):
        print(f"Reward profile: {reward_profile}")
    if games == 1 and game_outcomes:
        only_game_id = next(iter(sorted(game_outcomes)))
        outcome = dict(game_outcomes.get(only_game_id, {}) or {})
        winner_army_label = str(outcome.get("winner", "") or "tie")
        winner_score_line = str(outcome.get("score", "") or "<SCORE: 0 vs 0>")
        print(f"Winners: {{{winner_army_label!r}: {winner_score_line}}}")
    elif game_outcomes:
        winner_counts: Counter[str] = Counter(
            str(outcome.get("winner", "") or "tie") for outcome in game_outcomes.values()
        )
        print(f"Winner counts: {dict(winner_counts)}")
        print(f"Game outcomes: {game_outcomes}")
    print(f"Top decision types: {dict(decision_type_counts.most_common(10))}")
    if tool_probe_diagnostic_counts:
        print(f"Tool probe diagnostics: {dict(tool_probe_diagnostic_counts.most_common(20))}")
    if reserve_arrival_diagnostic_counts:
        print(f"Reserve arrival diagnostics: {dict(reserve_arrival_diagnostic_counts.most_common(20))}")
    if llm_agent_trace_counts:
        print(f"LLM agent traces: {dict(llm_agent_trace_counts.most_common(20))}")
    print(f"Wrote: {output_path}")
    replay_root = _resolved_replay_base_dir(str(replay_dir))
    if replay_root is not None:
        print(f"Replay sessions: {replay_root}")
    report_games: list[dict[str, Any]] = []
    profile_artifact_paths: list[dict[str, object]] = []
    for payload in per_game_outputs:
        game_payload = dict(payload or {})
        result = dict(game_payload.get("result", {}) or {})
        sanitized_result = dict(result)
        sanitized_result.pop("records", None)
        profile_artifacts = dict(sanitized_result.get("profile_artifacts", {}) or {})
        if profile_artifacts:
            profile_artifact_paths.append(
                {
                    "game_index": int(game_payload.get("game_index", 0) or 0),
                    "game_id": str(result.get("game_id", "") or ""),
                    **profile_artifacts,
                }
            )
        report_games.append(
            {
                "game_index": int(game_payload.get("game_index", 0) or 0),
                "elapsed_seconds": float(game_payload.get("elapsed_seconds", 0.0) or 0.0),
                "result": sanitized_result,
            }
        )
    report = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "games_requested": int(games),
        "games_completed": int(len(report_games)),
        "games_failed": int(max(0, int(games) - len(report_games))),
        "completion_rate": float(len(report_games) / games) if games > 0 else 0.0,
        "workers": int(workers),
        "seed_base": seed_base,
        "player1_army": str(player1_army),
        "player2_army": str(player2_army),
        "reward_profile": None if bool(no_reward_annotation) else str(reward_profile),
        "phase_steps": int(total_phase_steps),
        "decision_record_count": int(exported_record_count),
        "decision_type_counts": dict(decision_type_counts),
        "tool_probe_diagnostic_counts": dict(tool_probe_diagnostic_counts),
        "reserve_arrival_diagnostic_counts": dict(reserve_arrival_diagnostic_counts),
        "llm_agent_trace_counts": dict(llm_agent_trace_counts),
        "game_outcomes": game_outcomes,
        "records_output_path": str(output_path.resolve()),
        "replay_dir": "" if replay_root is None else str(replay_root),
        "profile_artifacts": profile_artifact_paths,
        "games": report_games,
    }
    report_output_text = str(report_output or "").strip()
    if report_output_text:
        report_path = Path(report_output_text)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True),
            encoding="utf-8",
        )
    return report


def main() -> int:
    args = _parse_args()
    run_headless_self_play(
        player1_army=str(args.player1_army),
        player2_army=str(args.player2_army),
        games=int(args.games),
        workers=int(args.workers),
        max_phase_steps=int(args.max_phase_steps),
        log_level=str(args.log_level),
        log_phase_transitions=bool(args.log_phase_transitions),
        seed_base=(int(args.seed_base) if args.seed_base is not None else None),
        reserve_policy=str(args.reserve_policy),
        max_reserves_arrival_seconds=float(args.max_reserves_arrival_seconds),
        deployment_ranker_model=str(args.deployment_ranker_model),
        llm_agent_config=str(args.llm_agent_config),
        enable_tool_decisions=not bool(args.disable_tool_decisions),
        output=str(args.output),
        reward_profile=str(args.reward_profile),
        no_reward_annotation=bool(args.no_reward_annotation),
        replay_dir=str(args.replay_dir),
        replay_keyframe_interval=int(args.replay_keyframe_interval),
        report_output=str(args.report_output),
        profile=bool(args.profile),
        profile_dir=str(args.profile_dir),
        profile_sort=str(args.profile_sort),
        profile_lines=int(args.profile_lines),
        profile_label=str(args.profile_label),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
