#!/usr/bin/env python3
from __future__ import annotations

import argparse

from warhammer40k_ai.ml.evaluation_pipeline import (
    HEADLESS_FIXED_EVALUATION_MODE,
    TRAINING_GRADE_EVALUATION_MODE,
    run_tournament_roster_evaluation,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run tournament-roster evaluation with bundle resolution, replay audit, gates, and roster context."
    )
    parser.add_argument("--policy-bundle", required=True, help="Policy bundle id or JSON manifest path.")
    parser.add_argument("--models-root", default="models", help="Models root used for bundle/artifact lookup.")
    parser.add_argument("--player1-army", required=True, help="Runtime army file for the candidate roster.")
    parser.add_argument("--player2-army", required=True, help="Runtime army file for the reference opponent.")
    parser.add_argument("--army-blueprint", required=True, help="ArmyBlueprint JSON for deterministic roster context.")
    parser.add_argument("--event-policy", required=True, help="EventPolicyDescriptor JSON path.")
    parser.add_argument("--field-distribution", required=True, help="TournamentFieldDistribution JSON path.")
    parser.add_argument("--rules-data-dir", required=True, help="Snapshot-scoped Wahapedia data directory.")
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed-base", type=int, default=None)
    parser.add_argument("--max-phase-steps", type=int, default=80)
    parser.add_argument("--reward-profile", default="dense_vp_delta_v1")
    parser.add_argument(
        "--evaluation-mode",
        choices=(HEADLESS_FIXED_EVALUATION_MODE, TRAINING_GRADE_EVALUATION_MODE),
        default=HEADLESS_FIXED_EVALUATION_MODE,
    )
    parser.add_argument("--report-dir", default="", help="Optional output report directory.")
    parser.add_argument("--source-tag", default="self_play")
    return parser.parse_args()


def main(argv: list[str] | None = None) -> int:
    del argv
    args = _parse_args()
    result = run_tournament_roster_evaluation(
        policy_bundle_source=str(args.policy_bundle),
        player1_army=str(args.player1_army),
        player2_army=str(args.player2_army),
        army_blueprint=str(args.army_blueprint),
        event_policy=str(args.event_policy),
        field_distribution=str(args.field_distribution),
        rules_data_dir=str(args.rules_data_dir),
        report_dir=(str(args.report_dir) if str(args.report_dir or "").strip() else None),
        models_root=(str(args.models_root) if str(args.models_root or "").strip() else None),
        games=int(args.games),
        workers=int(args.workers),
        seed_base=(int(args.seed_base) if args.seed_base is not None else None),
        max_phase_steps=int(args.max_phase_steps),
        reward_profile=str(args.reward_profile),
        evaluation_mode=str(args.evaluation_mode),
        source_tag=str(args.source_tag),
    )
    print(f"Report directory: {result['report_dir']}")
    print(f"Summary: {result['summary_path']}")
    return 0 if bool(result["success"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
