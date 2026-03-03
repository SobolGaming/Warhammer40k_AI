#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy
import json
from pathlib import Path
import time
from typing import Any

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.deployment_headless import DeterministicDeploymentDecisionMaker
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.engine.reward_profile import (
    annotate_decision_records_with_rewards,
    list_reward_profile_ids,
)
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player, PlayerControl


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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic headless self-play and export DecisionRecords."
    )
    parser.add_argument("--player1-army", default="army_lists/chaos_test.txt")
    parser.add_argument("--player2-army", default="army_lists/aeldari_test.txt")
    parser.add_argument("--games", type=int, default=1)
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
    return parser.parse_args()


def _drain_pending_decisions(game: Game, *, max_attempts: int = 4000) -> None:
    queue = getattr(game, "decision_queue", None)
    event_system = getattr(game, "event_system", None)
    if queue is None or event_system is None:
        return

    attempts = 0
    while True:
        request = queue.peek()
        if request is None:
            return
        if attempts >= int(max_attempts):
            raise RuntimeError(
                f"Unable to resolve pending decision after {max_attempts} attempts: "
                f"{getattr(request, 'decision_type', '')}"
            )
        decision_id_before = str(getattr(request, "decision_id", "") or "")
        event_system.publish("decision_requested", request=request, game=game)
        request_after = queue.peek()
        if request_after is None:
            return
        decision_id_after = str(getattr(request_after, "decision_id", "") or "")
        if decision_id_after == decision_id_before:
            raise RuntimeError(
                "Headless policy could not resolve decision "
                f"{decision_id_after} ({getattr(request_after, 'decision_type', '')})."
            )
        attempts += 1


def _run_single_game(
    *,
    player1_army_file: str,
    player2_army_file: str,
    max_phase_steps: int,
    game_seed: int | None = None,
) -> dict[str, Any]:
    player1 = Player("Player 1", control=PlayerControl.REMOTE)
    player2 = Player("Player 2", control=PlayerControl.REMOTE)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player1, player2])
    if game_seed is not None:
        random_source = getattr(game, "random_source", None)
        seed_fn = getattr(random_source, "seed", None)
        if callable(seed_fn):
            seed_fn(int(game_seed))
    HeadlessPolicyDecisionController(game=game, auto_attach=True)

    deployment_decision_makers = {
        player1.id: DeterministicDeploymentDecisionMaker(game),
        player2.id: DeterministicDeploymentDecisionMaker(game),
    }

    while game.is_in_setup_phase():
        setup_kwargs: dict[str, Any] = {
            "player1_army_file": player1_army_file,
            "player2_army_file": player2_army_file,
        }
        phase_name = str(getattr(game.get_current_setup_phase(), "name", "") or "")
        if phase_name == "DEPLOY_ARMIES":
            setup_kwargs["decision_makers"] = deployment_decision_makers
        game.execute_current_setup_phase(**setup_kwargs)
        _drain_pending_decisions(game)
        game.advance_setup_phase()
        _drain_pending_decisions(game)

    phase_steps = 0
    while not game.is_game_over():
        if phase_steps >= int(max_phase_steps):
            raise RuntimeError(f"Headless game hit max phase steps ({max_phase_steps}) before game over.")
        _drain_pending_decisions(game)
        game.next_phase()
        _drain_pending_decisions(game)
        phase_steps += 1

    winner = game.get_winner()
    records = copy.deepcopy(list(getattr(game.decision_record_store, "records", []) or []))
    return {
        "records": records,
        "phase_steps": int(phase_steps),
        "winner_player_id": str(getattr(winner, "id", "") or ""),
    }


def _run_single_game_job(
    game_index: int,
    *,
    player1_army_file: str,
    player2_army_file: str,
    max_phase_steps: int,
    seed_base: int | None = None,
) -> dict[str, Any]:
    game_seed = None
    if seed_base is not None:
        game_seed = int(seed_base) + int(game_index)
    started_at = time.perf_counter()
    result = _run_single_game(
        player1_army_file=player1_army_file,
        player2_army_file=player2_army_file,
        max_phase_steps=max_phase_steps,
        game_seed=game_seed,
    )
    serialized_result = {
        "records": _json_safe(list(result.get("records", []) or [])),
        "phase_steps": int(result.get("phase_steps", 0) or 0),
        "winner_player_id": str(result.get("winner_player_id", "") or ""),
    }
    elapsed_s = float(time.perf_counter() - started_at)
    return {
        "game_index": int(game_index),
        "elapsed_seconds": elapsed_s,
        "result": serialized_result,
    }


def main() -> int:
    args = _parse_args()
    games = max(1, int(args.games or 1))
    workers = max(1, int(args.workers or 1))
    max_phase_steps = max(1, int(args.max_phase_steps or 1))

    all_records: list[dict[str, Any]] = []
    total_phase_steps = 0
    winners: Counter[str] = Counter()
    decision_type_counts: Counter[str] = Counter()
    per_game_outputs: list[dict[str, Any]] = []

    seed_base = int(args.seed_base) if args.seed_base is not None else None

    if workers == 1 or games == 1:
        for game_index in range(games):
            payload = _run_single_game_job(
                game_index,
                player1_army_file=str(args.player1_army),
                player2_army_file=str(args.player2_army),
                max_phase_steps=max_phase_steps,
                seed_base=seed_base,
            )
            per_game_outputs.append(payload)
            result = dict(payload.get("result", {}) or {})
            records = list(result.get("records", []) or [])
            print(
                f"Completed game {game_index + 1}/{games} in "
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
                )
                for game_index in range(games)
            ]
            for future in as_completed(futures):
                payload = dict(future.result() or {})
                per_game_outputs.append(payload)
                game_index = int(payload.get("game_index", 0) or 0)
                result = dict(payload.get("result", {}) or {})
                records = list(result.get("records", []) or [])
                print(
                    f"Completed game {game_index + 1}/{games} in "
                    f"{float(payload.get('elapsed_seconds', 0.0) or 0.0):.2f}s "
                    f"(phase_steps={int(result.get('phase_steps', 0) or 0)}, records={len(records)})"
                )

    per_game_outputs.sort(key=lambda item: int(item.get("game_index", 0) or 0))
    for payload in per_game_outputs:
        result = dict(payload.get("result", {}) or {})
        records = list(result.get("records", []) or [])
        all_records.extend(records)
        total_phase_steps += int(result.get("phase_steps", 0) or 0)
        winner_player_id = str(result.get("winner_player_id", "") or "")
        if winner_player_id:
            winners[winner_player_id] += 1
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
    if winners:
        print(f"Winners by player id: {dict(winners)}")
    print(f"Top decision types: {dict(decision_type_counts.most_common(10))}")
    print(f"Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
