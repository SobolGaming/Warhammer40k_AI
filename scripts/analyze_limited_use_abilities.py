#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from warhammer40k_ai.ml.limited_use_ability_diagnostics import (
    DEFAULT_LIMIT_SCOPES,
    load_self_play_report,
    summarize_limited_use_report,
    summarize_paired_limited_use_reports,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze once-per-battle and other limited-use ability decisions from replay reports."
    )
    parser.add_argument("--report", default="", help="Single report directory or self_play_report.json path.")
    parser.add_argument("--baseline-report", default="", help="Baseline report directory or self_play_report.json path.")
    parser.add_argument("--candidate-report", default="", help="Candidate report directory or self_play_report.json path.")
    parser.add_argument("--output", required=True, help="Output JSON diagnostics path.")
    parser.add_argument("--primary-score-label", default="", help="Scoreboard label used as the margin numerator.")
    parser.add_argument("--opponent-score-label", default="", help="Scoreboard label used as the margin denominator.")
    parser.add_argument("--baseline-name", default="baseline")
    parser.add_argument("--candidate-name", default="candidate")
    parser.add_argument(
        "--limit-scope",
        action="append",
        default=[],
        help=(
            "Limited-use scope to include. Defaults to once-per-battle scopes. "
            "Known values include battle, battle_per_model, battle_per_unit, battle_round, turn, phase."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    scopes = tuple(str(scope or "").strip() for scope in list(args.limit_scope or []) if str(scope or "").strip())
    if not scopes:
        scopes = DEFAULT_LIMIT_SCOPES

    report_path = str(args.report or "").strip()
    baseline_path = str(args.baseline_report or "").strip()
    candidate_path = str(args.candidate_report or "").strip()
    if report_path and (baseline_path or candidate_path):
        raise ValueError("Use either --report or --baseline-report/--candidate-report, not both.")
    if report_path:
        summary = summarize_limited_use_report(
            load_self_play_report(report_path),
            primary_score_label=str(args.primary_score_label or ""),
            opponent_score_label=str(args.opponent_score_label or ""),
            limit_scopes=scopes,
        )
    else:
        if not baseline_path or not candidate_path:
            raise ValueError("Provide --report, or provide both --baseline-report and --candidate-report.")
        summary = summarize_paired_limited_use_reports(
            baseline_report=load_self_play_report(baseline_path),
            candidate_report=load_self_play_report(candidate_path),
            primary_score_label=str(args.primary_score_label or ""),
            opponent_score_label=str(args.opponent_score_label or ""),
            baseline_name=str(args.baseline_name or "baseline"),
            candidate_name=str(args.candidate_name or "candidate"),
            limit_scopes=scopes,
        )

    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    print(f"Summary: {output}")
    if "decision_count" in summary:
        print(f"Limited-use decisions: {summary['decision_count']}")
    else:
        print(f"Baseline limited-use decisions: {summary['baseline']['decision_count']}")
        print(f"Candidate limited-use decisions: {summary['candidate']['decision_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
