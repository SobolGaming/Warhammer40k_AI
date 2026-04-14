#!/usr/bin/env python3
from __future__ import annotations

import argparse

from warhammer40k_ai.engine.ruleset import RulesetBundle
from warhammer40k_ai.ml.evaluation_pipeline import (
    HEADLESS_FIXED_EVALUATION_MODE,
    TRAINING_GRADE_EVALUATION_MODE,
    run_policy_bundle_evaluation,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run unified evaluation for a policy bundle and emit an auditable report directory."
    )
    parser.add_argument("--policy-bundle", required=True, help="Policy bundle id or JSON manifest path.")
    parser.add_argument("--models-root", default="models", help="Models root used for bundle/artifact lookup.")
    parser.add_argument("--player1-army", default="army_lists/chaos_test.txt")
    parser.add_argument("--player2-army", default="army_lists/aeldari_test.txt")
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
    parser.add_argument("--core-rules-id", default="")
    parser.add_argument("--rules-commentary-id", default="")
    parser.add_argument("--mission-pack-id", default="")
    parser.add_argument("--terrain-pack-id", default="")
    parser.add_argument("--dataslate-id", default="")
    parser.add_argument("--points-id", default="")
    parser.add_argument("--faction-pack-id", default="")
    parser.add_argument("--detachment-pack-id", default="")
    return parser.parse_args()


def _target_rules_bundle(args: argparse.Namespace) -> RulesetBundle | None:
    values = {
        "core_rules_id": str(args.core_rules_id or ""),
        "rules_commentary_id": str(args.rules_commentary_id or ""),
        "mission_pack_id": str(args.mission_pack_id or ""),
        "terrain_pack_id": str(args.terrain_pack_id or ""),
        "dataslate_id": str(args.dataslate_id or ""),
        "points_id": str(args.points_id or ""),
        "faction_pack_id": str(args.faction_pack_id or ""),
        "detachment_pack_id": str(args.detachment_pack_id or ""),
    }
    if not any(values.values()):
        return None
    return RulesetBundle.from_values(**values)


def main(argv: list[str] | None = None) -> int:
    del argv
    args = _parse_args()
    result = run_policy_bundle_evaluation(
        policy_bundle_source=str(args.policy_bundle),
        player1_army=str(args.player1_army),
        player2_army=str(args.player2_army),
        report_dir=(str(args.report_dir) if str(args.report_dir or "").strip() else None),
        models_root=(str(args.models_root) if str(args.models_root or "").strip() else None),
        games=int(args.games),
        workers=int(args.workers),
        seed_base=(int(args.seed_base) if args.seed_base is not None else None),
        max_phase_steps=int(args.max_phase_steps),
        reward_profile=str(args.reward_profile),
        evaluation_mode=str(args.evaluation_mode),
        source_tag=str(args.source_tag),
        target_rules_bundle=_target_rules_bundle(args),
    )
    print(f"Report directory: {result['report_dir']}")
    print(f"Summary: {result['summary_path']}")
    return 0 if bool(result["success"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
