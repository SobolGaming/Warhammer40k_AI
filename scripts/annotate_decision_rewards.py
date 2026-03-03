#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from warhammer40k_ai.engine.reward_profile import (
    annotate_decision_records_with_rewards,
    list_reward_profile_ids,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Annotate DecisionRecords with profile-based reward targets."
    )
    parser.add_argument("--input", required=True, help="Path to DecisionRecords JSON array.")
    parser.add_argument("--output", required=True, help="Output path for annotated records JSON array.")
    parser.add_argument(
        "--reward-profile",
        default="dense_vp_delta_v1",
        choices=list_reward_profile_ids(),
        help="Reward profile id to apply.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    records = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Input DecisionRecords payload must be a JSON array.")

    annotated = annotate_decision_records_with_rewards(
        records,
        profile_id=str(args.reward_profile),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(annotated, indent=2, sort_keys=True), encoding="utf-8")
    print(
        f"Annotated {len(annotated)} decision records with reward profile "
        f"{str(args.reward_profile)} -> {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
