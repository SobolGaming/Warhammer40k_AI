#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
DEFAULT_INPUT = ROOT / "data" / "ranker_weight_sweeps" / "current" / "weight_sweep_report.json"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _resolve_path(raw: str, *, default: Path) -> Path:
    text = str(raw or "").strip()
    path = default if not text else Path(text).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}.")
    return dict(payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze deterministic ranker weight-sweep outputs and identify promotion candidates.",
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="weight_sweep_report.json path.")
    parser.add_argument("--output", default="", help="Analysis JSON path. Defaults beside --input.")
    parser.add_argument("--baseline-weight-set-id", default="", help="Override baseline id from the sweep report.")
    parser.add_argument("--min-vp-delta", type=float, default=0.0)
    parser.add_argument("--min-win-delta", type=int, default=0)
    parser.add_argument("--max-fallback-rate-delta", type=float, default=0.02)
    parser.add_argument("--max-stale-plan-rate-delta", type=float, default=0.02)
    parser.add_argument("--min-commander-hit-rate-delta", type=float, default=-0.02)
    parser.add_argument("--max-context-mean-byte-delta", type=float, default=1024.0)
    parser.add_argument("--max-context-p90-byte-delta", type=float, default=2048.0)
    parser.add_argument("--max-decision-count-delta-ratio", type=float, default=0.10)
    parser.add_argument("--max-phase-count-delta-ratio", type=float, default=0.10)
    parser.add_argument("--resource-anomaly-delta-ratio", type=float, default=0.25)
    return parser


def _rows_by_id(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {}
    for raw in list(report.get("rows", []) or []):
        if not isinstance(raw, dict):
            continue
        weight_set_id = str(raw.get("weight_set_id", "") or "").strip()
        if weight_set_id:
            rows[weight_set_id] = dict(raw)
    return dict(sorted(rows.items()))


def _context_distribution(row: Mapping[str, Any]) -> dict[str, float]:
    return {
        key: _safe_float(value)
        for key, value in _as_dict(row.get("context_payload_byte_distribution")).items()
        if key in {"count", "min", "p50", "p90", "max", "mean"}
    }


def _delta(value: Any, baseline_value: Any) -> float:
    return round(_safe_float(value) - _safe_float(baseline_value), 6)


def _ratio_delta(value: Any, baseline_value: Any) -> float:
    baseline = max(1.0, abs(_safe_float(baseline_value)))
    return round((_safe_float(value) - _safe_float(baseline_value)) / baseline, 6)


def _resource_anomalies(
    row: Mapping[str, Any],
    baseline: Mapping[str, Any],
    *,
    ratio_threshold: float,
) -> list[dict[str, Any]]:
    usage = _as_dict(row.get("resource_authorization_usage"))
    baseline_usage = _as_dict(baseline.get("resource_authorization_usage"))
    anomalies: list[dict[str, Any]] = []
    for key in sorted(set(usage).union(baseline_usage)):
        current_value = _safe_int(usage.get(key), 0)
        baseline_value = _safe_int(baseline_usage.get(key), 0)
        delta = current_value - baseline_value
        ratio = 0.0 if delta == 0 else float(delta / max(1, abs(baseline_value)))
        if baseline_value == 0 and current_value > 0:
            anomalies.append(
                {
                    "status": str(key),
                    "baseline": baseline_value,
                    "current": current_value,
                    "delta": delta,
                    "delta_ratio": 1.0,
                    "reason": "new_resource_status",
                }
            )
            continue
        if abs(ratio) > float(ratio_threshold):
            anomalies.append(
                {
                    "status": str(key),
                    "baseline": baseline_value,
                    "current": current_value,
                    "delta": delta,
                    "delta_ratio": round(ratio, 6),
                    "reason": "resource_usage_shift",
                }
            )
    return anomalies


def _matrix_path(row: Mapping[str, Any], *, input_path: Path) -> Path | None:
    raw_path = str(row.get("matrix_report_path", "") or "").strip()
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = input_path.parent / path
    return path


def _matrix_pair_vp(row: Mapping[str, Any], *, input_path: Path) -> dict[str, float]:
    path = _matrix_path(row, input_path=input_path)
    if path is None or not path.is_file():
        return {}
    report = _read_json_object(path)
    pairs: dict[str, float] = {}
    for raw in list(report.get("rows", []) or []):
        item = _as_dict(raw)
        pair_id = str(item.get("profile_pair_id", "") or "").strip()
        if not pair_id:
            continue
        vp = _as_dict(item.get("vp"))
        pairs[pair_id] = _safe_float(vp.get("differential_player1_minus_player2"), 0.0)
    return dict(sorted(pairs.items()))


def _consistency_summary(
    row: Mapping[str, Any],
    baseline: Mapping[str, Any],
    *,
    input_path: Path,
) -> dict[str, Any]:
    current_pairs = _matrix_pair_vp(row, input_path=input_path)
    baseline_pairs = _matrix_pair_vp(baseline, input_path=input_path)
    shared_ids = sorted(set(current_pairs).intersection(baseline_pairs))
    deltas = [round(current_pairs[pair_id] - baseline_pairs[pair_id], 6) for pair_id in shared_ids]
    improved = [value for value in deltas if value > 0.0]
    worsened = [value for value in deltas if value < 0.0]
    unchanged = [value for value in deltas if value == 0.0]
    positive_sum = sum(improved)
    dominant_share = 0.0 if positive_sum <= 0.0 else max(improved) / positive_sum
    one_lucky_matchup = bool(
        deltas
        and sum(deltas) > 0.0
        and ((len(improved) == 1 and len(deltas) > 1) or (dominant_share >= 0.75 and bool(worsened)))
    )
    mean_delta = 0.0 if not deltas else round(sum(deltas) / len(deltas), 6)
    return {
        "paired_profile_count": int(len(deltas)),
        "improved_count": int(len(improved)),
        "worsened_count": int(len(worsened)),
        "unchanged_count": int(len(unchanged)),
        "mean_pair_vp_delta": mean_delta,
        "min_pair_vp_delta": round(min(deltas), 6) if deltas else 0.0,
        "max_pair_vp_delta": round(max(deltas), 6) if deltas else 0.0,
        "positive_delta_dominant_share": round(dominant_share, 6),
        "one_lucky_matchup": one_lucky_matchup,
    }


def _metric_deltas(row: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    row_context = _context_distribution(row)
    baseline_context = _context_distribution(baseline)
    return {
        "mean_vp_differential_player1_minus_player2": _delta(
            row.get("mean_vp_differential_player1_minus_player2"),
            baseline.get("mean_vp_differential_player1_minus_player2"),
        ),
        "player1_win_count": _safe_int(row.get("player1_win_count"), 0) - _safe_int(baseline.get("player1_win_count"), 0),
        "player2_win_count": _safe_int(row.get("player2_win_count"), 0) - _safe_int(baseline.get("player2_win_count"), 0),
        "tie_count": _safe_int(row.get("tie_count"), 0) - _safe_int(baseline.get("tie_count"), 0),
        "fallback_rate": _delta(row.get("fallback_rate"), baseline.get("fallback_rate")),
        "commander_assignment_hit_rate": _delta(
            row.get("commander_assignment_hit_rate"),
            baseline.get("commander_assignment_hit_rate"),
        ),
        "stale_plan_rate": _delta(row.get("stale_plan_rate"), baseline.get("stale_plan_rate")),
        "total_decision_count": _safe_int(row.get("total_decision_count"), 0)
        - _safe_int(baseline.get("total_decision_count"), 0),
        "total_phase_count": _safe_int(row.get("total_phase_count"), 0) - _safe_int(baseline.get("total_phase_count"), 0),
        "decision_count_delta_ratio": _ratio_delta(row.get("total_decision_count"), baseline.get("total_decision_count")),
        "phase_count_delta_ratio": _ratio_delta(row.get("total_phase_count"), baseline.get("total_phase_count")),
        "context_mean_bytes": _delta(row_context.get("mean"), baseline_context.get("mean")),
        "context_p90_bytes": _delta(row_context.get("p90"), baseline_context.get("p90")),
        "context_max_bytes": _delta(row_context.get("max"), baseline_context.get("max")),
    }


def _promotion_reasons(
    deltas: Mapping[str, Any],
    consistency: Mapping[str, Any],
    resource_anomalies: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    review_flags: list[str] = []
    if _safe_float(deltas.get("mean_vp_differential_player1_minus_player2")) < float(args.min_vp_delta):
        blockers.append("vp_delta_below_threshold")
    if _safe_int(deltas.get("player1_win_count")) < int(args.min_win_delta):
        blockers.append("win_count_delta_below_threshold")
    if _safe_float(deltas.get("fallback_rate")) > float(args.max_fallback_rate_delta):
        blockers.append("fallback_rate_regression")
    if _safe_float(deltas.get("stale_plan_rate")) > float(args.max_stale_plan_rate_delta):
        blockers.append("stale_plan_rate_regression")
    if _safe_float(deltas.get("commander_assignment_hit_rate")) < float(args.min_commander_hit_rate_delta):
        blockers.append("commander_hit_rate_regression")
    if _safe_float(deltas.get("context_mean_bytes")) > float(args.max_context_mean_byte_delta):
        blockers.append("context_mean_size_regression")
    if _safe_float(deltas.get("context_p90_bytes")) > float(args.max_context_p90_byte_delta):
        blockers.append("context_p90_size_regression")
    if abs(_safe_float(deltas.get("decision_count_delta_ratio"))) > float(args.max_decision_count_delta_ratio):
        blockers.append("decision_count_regression")
    if abs(_safe_float(deltas.get("phase_count_delta_ratio"))) > float(args.max_phase_count_delta_ratio):
        blockers.append("phase_count_regression")
    if bool(consistency.get("one_lucky_matchup", False)):
        blockers.append("improvement_concentrated_in_one_matchup")
    if _safe_int(consistency.get("paired_profile_count"), 0) <= 1:
        review_flags.append("insufficient_pair_coverage")
    if resource_anomalies:
        review_flags.append("resource_usage_anomaly")
    if blockers:
        return "reject", blockers, review_flags
    if review_flags:
        return "review", blockers, review_flags
    return "promote_candidate", blockers, review_flags


def _rank_score(deltas: Mapping[str, Any], consistency: Mapping[str, Any], resource_anomalies: list[dict[str, Any]]) -> float:
    return round(
        (_safe_float(deltas.get("mean_vp_differential_player1_minus_player2")) * 10.0)
        + (_safe_float(deltas.get("player1_win_count")) * 3.0)
        - (_safe_float(deltas.get("fallback_rate")) * 5.0)
        - (_safe_float(deltas.get("stale_plan_rate")) * 5.0)
        + (_safe_float(deltas.get("commander_assignment_hit_rate")) * 3.0)
        - (max(0.0, _safe_float(deltas.get("context_p90_bytes"))) / 1024.0 * 0.25)
        - (abs(_safe_float(deltas.get("decision_count_delta_ratio"))) * 2.0)
        - (abs(_safe_float(deltas.get("phase_count_delta_ratio"))) * 2.0)
        + (_safe_float(consistency.get("improved_count")) - _safe_float(consistency.get("worsened_count")))
        - (len(resource_anomalies) * 0.5),
        6,
    )


def _analyze_row(
    row: Mapping[str, Any],
    baseline: Mapping[str, Any],
    *,
    args: argparse.Namespace,
    input_path: Path,
) -> dict[str, Any]:
    deltas = _metric_deltas(row, baseline)
    consistency = _consistency_summary(row, baseline, input_path=input_path)
    resource_anomalies = _resource_anomalies(
        row,
        baseline,
        ratio_threshold=float(args.resource_anomaly_delta_ratio),
    )
    status, blockers, review_flags = _promotion_reasons(
        deltas,
        consistency,
        resource_anomalies,
        args=args,
    )
    if str(row.get("weight_set_id", "") or "") == str(baseline.get("weight_set_id", "") or ""):
        status = "baseline"
        blockers = []
        review_flags = []
    return {
        "weight_set_id": str(row.get("weight_set_id", "") or ""),
        "description": str(row.get("description", "") or ""),
        "status": status,
        "rank_score": 0.0 if status == "baseline" else _rank_score(deltas, consistency, resource_anomalies),
        "metrics": {
            "mean_vp_differential_player1_minus_player2": _safe_float(
                row.get("mean_vp_differential_player1_minus_player2"),
                0.0,
            ),
            "player1_win_count": _safe_int(row.get("player1_win_count"), 0),
            "player2_win_count": _safe_int(row.get("player2_win_count"), 0),
            "tie_count": _safe_int(row.get("tie_count"), 0),
            "fallback_rate": _safe_float(row.get("fallback_rate"), 0.0),
            "commander_assignment_hit_rate": _safe_float(row.get("commander_assignment_hit_rate"), 0.0),
            "stale_plan_rate": _safe_float(row.get("stale_plan_rate"), 0.0),
            "total_decision_count": _safe_int(row.get("total_decision_count"), 0),
            "total_phase_count": _safe_int(row.get("total_phase_count"), 0),
            "context_payload_byte_distribution": _as_dict(row.get("context_payload_byte_distribution")),
            "resource_authorization_usage": _as_dict(row.get("resource_authorization_usage")),
            "deployment_tempo_usage": _as_dict(row.get("deployment_tempo_usage")),
            "chosen_action_rank_under_current_ranker": _as_dict(row.get("chosen_action_rank_under_current_ranker")),
        },
        "baseline_delta": deltas,
        "consistency": consistency,
        "resource_usage_anomalies": resource_anomalies,
        "blockers": blockers,
        "review_flags": review_flags,
        "artifact_paths": {
            "matrix_report": str(row.get("matrix_report_path", "") or ""),
            "ranker_rows": str(row.get("ranker_rows_path", "") or ""),
            "ranker_coverage": str(row.get("ranker_coverage_path", "") or ""),
        },
    }


def _leader_id(rows: Iterable[Mapping[str, Any]], key: str, *, lower_is_better: bool = False) -> str:
    candidates = [row for row in rows if str(row.get("status", "")) != "baseline"]
    if not candidates:
        return ""
    if lower_is_better:
        selected = min(candidates, key=lambda row: (_safe_float(_as_dict(row.get("metrics")).get(key)), str(row.get("weight_set_id", ""))))
    else:
        selected = max(candidates, key=lambda row: (_safe_float(_as_dict(row.get("metrics")).get(key)), str(row.get("weight_set_id", ""))))
    return str(selected.get("weight_set_id", "") or "")


def _metric_leaders(analyses: list[dict[str, Any]]) -> dict[str, str]:
    return {
        "best_vp_differential": _leader_id(analyses, "mean_vp_differential_player1_minus_player2"),
        "best_player1_win_count": _leader_id(analyses, "player1_win_count"),
        "lowest_fallback_rate": _leader_id(analyses, "fallback_rate", lower_is_better=True),
        "lowest_stale_plan_rate": _leader_id(analyses, "stale_plan_rate", lower_is_better=True),
        "highest_commander_hit_rate": _leader_id(analyses, "commander_assignment_hit_rate"),
    }


def build_analysis_report(
    sweep_report: Mapping[str, Any],
    *,
    args: argparse.Namespace,
    input_path: Path,
) -> dict[str, Any]:
    rows_by_weight_id = _rows_by_id(sweep_report)
    baseline_id = str(args.baseline_weight_set_id or sweep_report.get("baseline_weight_set_id", "") or "baseline")
    baseline = rows_by_weight_id.get(baseline_id)
    if baseline is None:
        raise ValueError(f"Baseline weight set {baseline_id!r} was not found in sweep report.")
    analyses = [
        _analyze_row(row, baseline, args=args, input_path=input_path)
        for _weight_set_id, row in sorted(rows_by_weight_id.items())
    ]
    status_counts = Counter(str(row.get("status", "") or "") for row in analyses)
    ranked = sorted(
        [row for row in analyses if str(row.get("status", "")) != "baseline"],
        key=lambda row: (-_safe_float(row.get("rank_score")), str(row.get("weight_set_id", ""))),
    )
    promotion_candidates = [row for row in ranked if str(row.get("status", "")) == "promote_candidate"]
    review_candidates = [row for row in ranked if str(row.get("status", "")) == "review"]
    recommended = promotion_candidates[0] if promotion_candidates else (review_candidates[0] if review_candidates else {})
    return {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_report": str(input_path.resolve()),
        "baseline_weight_set_id": baseline_id,
        "promotion_policy": {
            "min_vp_delta": float(args.min_vp_delta),
            "min_win_delta": int(args.min_win_delta),
            "max_fallback_rate_delta": float(args.max_fallback_rate_delta),
            "max_stale_plan_rate_delta": float(args.max_stale_plan_rate_delta),
            "min_commander_hit_rate_delta": float(args.min_commander_hit_rate_delta),
            "max_context_mean_byte_delta": float(args.max_context_mean_byte_delta),
            "max_context_p90_byte_delta": float(args.max_context_p90_byte_delta),
            "max_decision_count_delta_ratio": float(args.max_decision_count_delta_ratio),
            "max_phase_count_delta_ratio": float(args.max_phase_count_delta_ratio),
            "resource_anomaly_delta_ratio": float(args.resource_anomaly_delta_ratio),
        },
        "summary": {
            "weight_set_count": int(len(analyses)),
            "status_counts": dict(sorted(status_counts.items())),
            "recommended_weight_set_id": str(recommended.get("weight_set_id", "") or ""),
            "recommended_status": str(recommended.get("status", "") or ""),
        },
        "metric_leaders": _metric_leaders(analyses),
        "promotion_candidates": [str(row.get("weight_set_id", "") or "") for row in promotion_candidates],
        "review_candidates": [str(row.get("weight_set_id", "") or "") for row in review_candidates],
        "ranked_candidates": ranked,
        "all_weight_sets": analyses,
    }


def main() -> int:
    args = _build_parser().parse_args()
    input_path = _resolve_path(str(args.input), default=DEFAULT_INPUT)
    sweep_report = _read_json_object(input_path)
    report = build_analysis_report(sweep_report, args=args, input_path=input_path)
    output_path = _resolve_path(
        str(args.output or ""),
        default=input_path.with_name("weight_sweep_analysis.json"),
    )
    _write_json(output_path, report)
    print(f"Weight sweep analysis: {output_path}")
    print(f"Recommended: {report['summary']['recommended_weight_set_id']} ({report['summary']['recommended_status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
