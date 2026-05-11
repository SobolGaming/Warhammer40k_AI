#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from warhammer40k_ai.ml.paired_eval_analysis import (
    load_self_play_report,
    summarize_paired_policy_evaluation,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize same-seed paired policy evaluation results and first replay divergence."
    )
    parser.add_argument("--baseline-report", required=True, help="Baseline report directory or self_play_report.json path.")
    parser.add_argument("--candidate-report", required=True, help="Candidate report directory or self_play_report.json path.")
    parser.add_argument("--output", required=True, help="Output JSON summary path.")
    parser.add_argument("--primary-score-label", default="", help="Scoreboard label used as the margin numerator.")
    parser.add_argument("--opponent-score-label", default="", help="Scoreboard label used as the margin denominator.")
    parser.add_argument("--baseline-name", default="heuristic", help="Display key for baseline action labels.")
    parser.add_argument("--candidate-name", default="candidate", help="Display key for candidate action labels.")
    parser.add_argument(
        "--ignore-decision-type",
        action="append",
        default=[],
        help="Decision type to ignore when finding first divergence. Repeat for multiple values.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = summarize_paired_policy_evaluation(
        baseline_report=load_self_play_report(args.baseline_report),
        candidate_report=load_self_play_report(args.candidate_report),
        primary_score_label=str(args.primary_score_label or ""),
        opponent_score_label=str(args.opponent_score_label or ""),
        baseline_name=str(args.baseline_name or "heuristic"),
        candidate_name=str(args.candidate_name or "candidate"),
        ignored_decision_types=[
            str(value or "").strip()
            for value in list(args.ignore_decision_type or [])
            if str(value or "").strip()
        ],
    )
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Summary: {output}")
    print(f"Common games: {summary['common_games']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
