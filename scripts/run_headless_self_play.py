#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import logging
from pathlib import Path
import time
from typing import Any

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.deployment_headless import DeterministicDeploymentDecisionMaker
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

logger = logging.getLogger(__name__)


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


def _resolved_replay_base_dir(path: str | None) -> Path | None:
    path_text = str(path or "").strip()
    if not path_text:
        return None
    return Path(path_text).expanduser().resolve()


def _export_decision_records(records: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    safe_records = _json_safe(list(records or []))
    return list(safe_records or [])


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
    log_phase_transitions: bool = False,
    replay_dir: str | None = None,
    replay_keyframe_interval: int = DEFAULT_KEYFRAME_INTERVAL,
) -> dict[str, Any]:
    player1_label = _army_label_from_path(player1_army_file)
    player2_label = _army_label_from_path(player2_army_file)
    player1 = Player("Player 1", control=PlayerControl.REMOTE)
    player2 = Player("Player 2", control=PlayerControl.REMOTE)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player1, player2])
    game.session_id = str(game_id or "")
    replay_base_dir = _resolved_replay_base_dir(replay_dir)
    replay_path: Path | None = None
    snapshot_path: Path | None = None
    replay_label = f"{player1_label}_vs_{player2_label}"
    if replay_base_dir is not None:
        create_session(
            game,
            base_dir=replay_base_dir,
            session_id=str(game_id or ""),
            label=replay_label,
        )
        replay_path = enable_session_replay_recording(
            game,
            base_dir=replay_base_dir,
            session_id=str(game_id or ""),
            label=replay_label,
            keyframe_interval=max(1, int(replay_keyframe_interval or DEFAULT_KEYFRAME_INTERVAL)),
        )
    if game_seed is not None:
        random_source = getattr(game, "random_source", None)
        seed_fn = getattr(random_source, "seed", None)
        if callable(seed_fn):
            seed_fn(int(game_seed))
    HeadlessPolicyDecisionController(
        game=game,
        auto_attach=True,
        max_reserves_arrival_seconds=float(max_reserves_arrival_seconds),
    )
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
            session_id=str(game_id or ""),
            label=replay_label,
        )
    records = _export_decision_records(list(getattr(game.decision_record_store, "records", []) or []))
    return {
        "game_id": str(game_id or ""),
        "records": records,
        "phase_steps": int(phase_steps),
        "winner_player_id": str(getattr(winner, "id", "") or ""),
        "winner_army_label": str(winner_army_label or ""),
        "winner_score_line": str(winner_score_line or ""),
        "scoreboard": scoreboard,
        "replay_session_id": str(game_id or "") if replay_path is not None else "",
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
    log_level: str = "WARNING",
    log_phase_transitions: bool = False,
    replay_dir: str | None = None,
    replay_keyframe_interval: int = DEFAULT_KEYFRAME_INTERVAL,
) -> dict[str, Any]:
    _setup_logging(str(log_level or "WARNING"))
    game_seed = None
    if seed_base is not None:
        game_seed = int(seed_base) + int(game_index)
    game_id = _game_id_for_index(int(game_index), seed_base=seed_base)
    started_at = time.perf_counter()
    result = _run_single_game(
        game_id=str(game_id),
        player1_army_file=player1_army_file,
        player2_army_file=player2_army_file,
        max_phase_steps=max_phase_steps,
        game_seed=game_seed,
        reserve_policy=str(reserve_policy or "forced_only"),
        max_reserves_arrival_seconds=float(max_reserves_arrival_seconds),
        deployment_ranker_model=str(deployment_ranker_model or ""),
        log_phase_transitions=bool(log_phase_transitions),
        replay_dir=str(replay_dir or ""),
        replay_keyframe_interval=max(1, int(replay_keyframe_interval or DEFAULT_KEYFRAME_INTERVAL)),
    )
    serialized_result = {
        "game_id": str(result.get("game_id", "") or ""),
        "records": _json_safe(list(result.get("records", []) or [])),
        "phase_steps": int(result.get("phase_steps", 0) or 0),
        "winner_player_id": str(result.get("winner_player_id", "") or ""),
        "winner_army_label": str(result.get("winner_army_label", "") or ""),
        "winner_score_line": str(result.get("winner_score_line", "") or ""),
        "scoreboard": _json_safe(dict(result.get("scoreboard", {}) or {})),
        "replay_session_id": str(result.get("replay_session_id", "") or ""),
        "replay_path": str(result.get("replay_path", "") or ""),
        "snapshot_path": str(result.get("snapshot_path", "") or ""),
    }
    elapsed_s = float(time.perf_counter() - started_at)
    return {
        "game_index": int(game_index),
        "elapsed_seconds": elapsed_s,
        "result": serialized_result,
    }


def main() -> int:
    args = _parse_args()
    _setup_logging(str(args.log_level))
    games = max(1, int(args.games or 1))
    workers = max(1, int(args.workers or 1))
    max_phase_steps = max(1, int(args.max_phase_steps or 1))

    all_records: list[dict[str, Any]] = []
    total_phase_steps = 0
    decision_type_counts: Counter[str] = Counter()
    per_game_outputs: list[dict[str, Any]] = []
    game_outcomes: dict[str, dict[str, Any]] = {}

    seed_base = int(args.seed_base) if args.seed_base is not None else None

    if workers == 1 or games == 1:
        for game_index in range(games):
            payload = _run_single_game_job(
                game_index,
                player1_army_file=str(args.player1_army),
                player2_army_file=str(args.player2_army),
                max_phase_steps=max_phase_steps,
                seed_base=seed_base,
                reserve_policy=str(args.reserve_policy),
                max_reserves_arrival_seconds=float(args.max_reserves_arrival_seconds),
                deployment_ranker_model=str(args.deployment_ranker_model),
                log_level=str(args.log_level),
                log_phase_transitions=bool(args.log_phase_transitions),
                replay_dir=str(args.replay_dir),
                replay_keyframe_interval=int(args.replay_keyframe_interval),
            )
            per_game_outputs.append(payload)
            result = dict(payload.get("result", {}) or {})
            records = list(result.get("records", []) or [])
            game_id = str(result.get("game_id", "") or "")
            print(
                f"Completed game {game_index + 1}/{games} ({game_id}) in "
                f"{float(payload.get('elapsed_seconds', 0.0) or 0.0):.2f}s "
                f"(phase_steps={int(result.get('phase_steps', 0) or 0)}, records={len(records)})"
            )
    else:
        max_workers = min(workers, games)
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    _run_single_game_job,
                    game_index,
                    player1_army_file=str(args.player1_army),
                    player2_army_file=str(args.player2_army),
                    max_phase_steps=max_phase_steps,
                    seed_base=seed_base,
                    reserve_policy=str(args.reserve_policy),
                    max_reserves_arrival_seconds=float(args.max_reserves_arrival_seconds),
                    deployment_ranker_model=str(args.deployment_ranker_model),
                    log_level=str(args.log_level),
                    log_phase_transitions=bool(args.log_phase_transitions),
                    replay_dir=str(args.replay_dir),
                    replay_keyframe_interval=int(args.replay_keyframe_interval),
                )
                for game_index in range(games)
            ]
            for future in as_completed(futures):
                payload = dict(future.result() or {})
                per_game_outputs.append(payload)
                game_index = int(payload.get("game_index", 0) or 0)
                result = dict(payload.get("result", {}) or {})
                records = list(result.get("records", []) or [])
                game_id = str(result.get("game_id", "") or "")
                print(
                    f"Completed game {game_index + 1}/{games} ({game_id}) in "
                    f"{float(payload.get('elapsed_seconds', 0.0) or 0.0):.2f}s "
                    f"(phase_steps={int(result.get('phase_steps', 0) or 0)}, records={len(records)})"
                )

    per_game_outputs.sort(key=lambda item: int(item.get("game_index", 0) or 0))
    for payload in per_game_outputs:
        result = dict(payload.get("result", {}) or {})
        records = list(result.get("records", []) or [])
        all_records.extend(records)
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

    exported_records = all_records
    if not bool(args.no_reward_annotation):
        exported_records = annotate_decision_records_with_rewards(
            exported_records,
            profile_id=str(args.reward_profile),
        )
    exported_records = _json_safe(exported_records)

    output_path = Path(str(args.output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(exported_records, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Games: {games}")
    print(f"Workers: {workers}")
    print(f"Phase steps: {total_phase_steps}")
    print(f"Decision records: {len(exported_records)}")
    if not bool(args.no_reward_annotation):
        print(f"Reward profile: {args.reward_profile}")
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
    print(f"Wrote: {output_path}")
    replay_root = _resolved_replay_base_dir(str(args.replay_dir))
    if replay_root is not None:
        print(f"Replay sessions: {replay_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
