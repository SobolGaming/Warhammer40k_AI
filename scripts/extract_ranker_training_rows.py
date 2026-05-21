#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import sys
from typing import Any, Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from warhammer40k_ai.ml.record_stream import iter_records_from_json, records_from_document


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract diagnostic ranker candidate rows and coverage from DecisionRecords.",
    )
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        help=(
            "DecisionRecords JSON/JSONL file or directory. Repeat to merge sources. "
            "Directory inputs scan decision-record-like filenames only."
        ),
    )
    parser.add_argument("--output-jsonl", default="data/ranker_training_rows.jsonl")
    parser.add_argument("--coverage-output", default="data/ranker_training_coverage.json")
    parser.add_argument(
        "--ui-smoke-status",
        choices=["pass", "fail", "not_run"],
        default="not_run",
        help="Optional status to include in the coverage report.",
    )
    parser.add_argument(
        "--network-smoke-status",
        choices=["pass", "fail", "not_run"],
        default="not_run",
        help="Optional status to include in the coverage report.",
    )
    parser.add_argument(
        "--snapshot-smoke-status",
        choices=["pass", "fail", "not_run"],
        default="not_run",
        help="Optional status to include in the coverage report.",
    )
    return parser


def _is_directory_record_file(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix not in {".json", ".jsonl"}:
        return False
    name = path.name.lower()
    if name in {
        "accepted_decision_records.json",
        "accepted_decision_records.jsonl",
        "decision_records.json",
        "decision_records.jsonl",
        "headless_self_play_decision_records.json",
        "headless_self_play_decision_records.jsonl",
    }:
        return True
    return path.stem.lower().endswith("_records")


def _iter_input_files(path: Path) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    if not path.is_dir():
        raise FileNotFoundError(f"Input path not found: {path}")
    for candidate in sorted(path.rglob("*"), key=lambda item: str(item)):
        if candidate.is_file() and _is_directory_record_file(candidate):
            yield candidate


def _iter_jsonl_records(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, dict) and isinstance(value.get("records"), list):
                yield from records_from_document(value, source_path=path)
                continue
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_number}.")
            yield value


def _iter_records(inputs: Iterable[str]) -> Iterator[dict[str, Any]]:
    seen_files: set[Path] = set()
    for raw_path in inputs:
        input_path = Path(str(raw_path)).expanduser()
        if not input_path.is_absolute():
            input_path = REPO_ROOT / input_path
        for path in _iter_input_files(input_path.resolve()):
            if path in seen_files:
                continue
            seen_files.add(path)
            if path.suffix.lower() == ".jsonl":
                yield from _iter_jsonl_records(path)
            else:
                yield from iter_records_from_json(path)


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value or []) if isinstance(value, list) else []


def _json_bytes(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))


def _percentile(values: list[int], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(int(value) for value in values)
    if len(ordered) == 1:
        return float(ordered[0])
    index = (len(ordered) - 1) * float(percentile)
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def _distribution(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": 0, "p50": 0.0, "p90": 0.0, "max": 0, "mean": 0.0}
    return {
        "count": int(len(values)),
        "min": int(min(values)),
        "p50": round(_percentile(values, 0.50), 3),
        "p90": round(_percentile(values, 0.90), 3),
        "max": int(max(values)),
        "mean": round(float(statistics.fmean(values)), 3),
    }


def _candidate_count_bucket(count: int) -> str:
    value = int(count)
    if value == 0:
        return "0"
    if value == 1:
        return "1"
    if value <= 4:
        return "2-4"
    if value <= 9:
        return "5-9"
    if value <= 24:
        return "10-24"
    return "25+"


def _player_id(record: dict[str, Any], context: dict[str, Any]) -> str:
    explicit = str(record.get("player_id", "") or context.get("player_id", "") or "")
    if explicit:
        return explicit
    outcome = _safe_dict(record.get("outcome"))
    immediate = _safe_dict(outcome.get("immediate_deltas"))
    return str(immediate.get("actor_player_id", "") or "")


def _unit_id(candidate: dict[str, Any], context: dict[str, Any]) -> str:
    params = _safe_dict(candidate.get("params"))
    metadata = _safe_dict(candidate.get("metadata"))
    for source in (params, metadata, context):
        for key in ("unit_id", "source_unit_id", "actor_unit_id", "selected_unit_id"):
            value = str(source.get(key, "") or "")
            if value:
                return value
    return ""


def _commander_alignment(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    metadata = _safe_dict(candidate.get("metadata"))
    for value in (
        metadata.get("commander_alignment"),
        metadata.get("commander_assignment"),
        context.get("commander_alignment"),
    ):
        if isinstance(value, dict):
            return dict(value)
    return {}


def _outcome_window(record: dict[str, Any]) -> dict[str, Any]:
    outcome = _safe_dict(record.get("outcome"))
    immediate = _safe_dict(outcome.get("immediate_deltas"))
    return {
        "score_delta_next_window": float(
            outcome.get("score_delta_next_window", immediate.get("score_delta", immediate.get("vp_delta", 0.0))) or 0.0
        ),
        "wounds_inflicted_next_phase": float(
            outcome.get("wounds_inflicted_next_phase", immediate.get("wounds_inflicted", 0.0)) or 0.0
        ),
        "target_destroyed_next_phase": bool(
            outcome.get("target_destroyed_next_phase", immediate.get("target_destroyed", False))
        ),
        "objective_control_delta": float(
            outcome.get("objective_control_delta", immediate.get("objective_control_delta", 0.0)) or 0.0
        ),
    }


def _row_for_candidate(
    record: dict[str, Any],
    candidate: dict[str, Any],
    *,
    candidate_index: int,
    legal: bool,
    context: dict[str, Any],
) -> dict[str, Any]:
    chosen_action_id = str(record.get("chosen_action_id", "") or "")
    return {
        "game_id": str(record.get("game_id", "") or ""),
        "seed": int(record.get("global_seed", 0) or 0),
        "decision_seed": int(record.get("decision_seed", 0) or 0),
        "battle_round": int(record.get("turn_id", record.get("battle_round", 0)) or 0),
        "phase": str(record.get("phase", "") or context.get("phase_name", "") or context.get("phase", "") or ""),
        "decision_type": str(record.get("decision_type", "") or ""),
        "decision_id": str(record.get("decision_id", "") or ""),
        "player_id": _player_id(record, context),
        "unit_id": _unit_id(candidate, context),
        "candidate_index": int(candidate_index),
        "candidate_action_id": str(candidate.get("action_id", "") or ""),
        "chosen_action_id": chosen_action_id,
        "legal": bool(legal),
        "chosen": str(candidate.get("action_id", "") or "") == chosen_action_id,
        "candidate_metadata": _safe_dict(candidate.get("metadata")),
        "request_context_keys": sorted(str(key) for key in context.keys()),
        "general_plan_id": str(context.get("general_plan_id", "") or ""),
        "deployment_order_bundle_id": str(context.get("deployment_order_bundle_id", "") or ""),
        "prebattle_order_bundle_id": str(context.get("prebattle_order_bundle_id", "") or ""),
        "deployment_plan_id": str(context.get("deployment_plan_id", "") or ""),
        "battle_round_plan_id": str(context.get("battle_round_plan_id", "") or ""),
        "commander_order_bundle_id": str(context.get("commander_order_bundle_id", "") or ""),
        "commander_alignment": _commander_alignment(candidate, context),
        "outcome_window": _outcome_window(record),
    }


def _candidate_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    context = _safe_dict(record.get("request_context"))
    candidates = [_safe_dict(item) for item in _safe_list(record.get("candidates"))]
    mask = _safe_list(record.get("mask"))
    rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        legal = bool(mask[index]) if index < len(mask) else True
        rows.append(
            _row_for_candidate(
                record,
                candidate,
                candidate_index=index,
                legal=legal,
                context=context,
            )
        )
    return rows


def candidate_rows_from_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        rows.extend(_candidate_rows(_safe_dict(record)))
    return rows


def _has_commander_assignment(row: dict[str, Any], context: dict[str, Any]) -> bool:
    metadata = _safe_dict(row.get("candidate_metadata"))
    if _safe_dict(row.get("commander_alignment")):
        return True
    if metadata.get("commander_assignment") or metadata.get("commander_order") or metadata.get("unit_order"):
        return True
    return bool(context.get("commander_order_bundle_id") or context.get("commander_resource_authorizations"))


def _is_fallback(row: dict[str, Any]) -> bool:
    metadata = _safe_dict(row.get("candidate_metadata"))
    text = " ".join(str(metadata.get(key, "") or "") for key in ("source", "reason", "mode"))
    return bool(metadata.get("fallback_mode", False) or "fallback" in text.lower())


def _resource_status(row: dict[str, Any], context: dict[str, Any]) -> str:
    metadata = _safe_dict(row.get("candidate_metadata"))
    status = str(metadata.get("resource_authorization_status", "") or metadata.get("authorization_status", "") or "")
    if status:
        return status.lower()
    if metadata.get("resource_authorization_rejected") or metadata.get("authorization_rejected"):
        return "rejected"
    if metadata.get("resource_authorization_id") or metadata.get("uses_resource_authorization"):
        return "used"
    if context.get("commander_resource_authorizations"):
        return "available"
    return "none"


def _tempo_status(row: dict[str, Any], context: dict[str, Any]) -> dict[str, bool]:
    metadata = _safe_dict(row.get("candidate_metadata"))
    tempo = _safe_dict(context.get("deployment_tempo_capability"))
    candidate_tempos = _safe_dict(context.get("deployment_candidate_tempo_capabilities"))
    unit_id = str(row.get("unit_id", "") or "")
    if not tempo and unit_id:
        tempo = _safe_dict(candidate_tempos.get(unit_id))
    if not tempo:
        tempo = _safe_dict(metadata.get("deployment_tempo_capability"))
    return {
        "has_scout": bool(tempo.get("has_scout", False)),
        "has_infiltrate": bool(tempo.get("has_infiltrate", False)),
    }


def _is_stale_context(context: dict[str, Any]) -> bool:
    for key in ("deployment_replan_scope", "commander_replan_scope"):
        value = str(context.get(key, "") or "").strip().lower()
        if value and value not in {"none", "clean", "no_replan"}:
            return True
    for key in ("deployment_dirty_flags", "commander_dirty_flags"):
        value = _safe_dict(context.get(key))
        status = str(value.get("status", "") or "").strip().lower()
        if status and status not in {"clean", "none"}:
            return True
        if any(bool(v) for v in value.values() if isinstance(v, bool)):
            return True
    return False


def _build_coverage(records: list[dict[str, Any]], rows: list[dict[str, Any]], smoke_status: dict[str, str]) -> dict[str, Any]:
    decision_counts = Counter(str(record.get("decision_type", "") or "") for record in records)
    candidate_counts = [len(_safe_list(record.get("candidates"))) for record in records]
    candidate_buckets = Counter(_candidate_count_bucket(count) for count in candidate_counts)
    masks: list[bool] = []
    chosen_ranks: list[int] = []
    missing_chosen = 0
    context_bytes = []
    stale_contexts = 0
    contexts_by_decision = {str(record.get("decision_id", "") or ""): _safe_dict(record.get("request_context")) for record in records}

    for record in records:
        candidates = [_safe_dict(item) for item in _safe_list(record.get("candidates"))]
        mask = _safe_list(record.get("mask"))
        masks.extend(bool(mask[index]) if index < len(mask) else True for index, _candidate in enumerate(candidates))
        chosen = str(record.get("chosen_action_id", "") or "")
        if chosen:
            candidate_ids = [str(candidate.get("action_id", "") or "") for candidate in candidates]
            if chosen in candidate_ids:
                chosen_ranks.append(candidate_ids.index(chosen) + 1)
            else:
                missing_chosen += 1
        context = _safe_dict(record.get("request_context"))
        context_bytes.append(_json_bytes(context))
        if _is_stale_context(context):
            stale_contexts += 1

    commander_hit = 0
    commander_fallback = 0
    resource_counts = Counter()
    scout_hits = 0
    infiltrate_hits = 0
    tempo_rows = 0
    for row in rows:
        context = contexts_by_decision.get(str(row.get("decision_id", "") or ""), {})
        if _has_commander_assignment(row, context):
            commander_hit += 1
        if _is_fallback(row):
            commander_fallback += 1
        resource_counts[_resource_status(row, context)] += 1
        tempo = _tempo_status(row, context)
        if tempo["has_scout"] or tempo["has_infiltrate"]:
            tempo_rows += 1
        if tempo["has_scout"]:
            scout_hits += 1
        if tempo["has_infiltrate"]:
            infiltrate_hits += 1

    total_candidates = len(masks)
    legal_candidates = sum(1 for item in masks if item)
    total_rows = max(1, len(rows))
    return {
        "record_count": int(len(records)),
        "candidate_row_count": int(len(rows)),
        "decision_type_counts": dict(sorted(decision_counts.items())),
        "candidate_count_distribution": {
            **_distribution(candidate_counts),
            "buckets": dict(sorted(candidate_buckets.items())),
        },
        "mask_ratio": {
            "total_candidates": int(total_candidates),
            "legal_candidates": int(legal_candidates),
            "masked_candidates": int(total_candidates - legal_candidates),
            "legal_ratio": round(float(legal_candidates / total_candidates), 6) if total_candidates else 0.0,
            "masked_ratio": round(float((total_candidates - legal_candidates) / total_candidates), 6)
            if total_candidates
            else 0.0,
        },
        "chosen_action_rank_under_current_ranker": {
            "observed_count": int(len(chosen_ranks)),
            "missing_count": int(missing_chosen),
            "distribution": _distribution(chosen_ranks),
            "rank_counts": dict(sorted(Counter(chosen_ranks).items())),
        },
        "commander_assignment_hit_fallback_rate": {
            "rows": int(len(rows)),
            "hit_count": int(commander_hit),
            "fallback_count": int(commander_fallback),
            "hit_rate": round(float(commander_hit / total_rows), 6),
            "fallback_rate": round(float(commander_fallback / total_rows), 6),
        },
        "stale_plan_rate": {
            "records": int(len(records)),
            "stale_count": int(stale_contexts),
            "stale_rate": round(float(stale_contexts / max(1, len(records))), 6),
        },
        "resource_authorization_used_rejected": dict(sorted(resource_counts.items())),
        "context_payload_byte_distribution": _distribution(context_bytes),
        "deployment_tempo_usage": {
            "rows": int(len(rows)),
            "tempo_rows": int(tempo_rows),
            "scout_hit_count": int(scout_hits),
            "infiltrate_hit_count": int(infiltrate_hits),
            "scout_hit_rate": round(float(scout_hits / total_rows), 6),
            "infiltrate_hit_rate": round(float(infiltrate_hits / total_rows), 6),
        },
        "smoke_status": dict(smoke_status),
    }


def build_ranker_coverage_report(
    records: Iterable[dict[str, Any]],
    *,
    rows: Iterable[dict[str, Any]] | None = None,
    smoke_status: dict[str, str] | None = None,
) -> dict[str, Any]:
    record_list = [_safe_dict(record) for record in records]
    row_list = list(rows) if rows is not None else candidate_rows_from_records(record_list)
    return _build_coverage(
        record_list,
        [_safe_dict(row) for row in row_list],
        dict(smoke_status or {}),
    )


def main() -> int:
    args = _build_parser().parse_args()
    records = list(_iter_records(args.input))
    rows = candidate_rows_from_records(records)

    output_path = Path(str(args.output_jsonl)).expanduser()
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    coverage_path = Path(str(args.coverage_output)).expanduser()
    if not coverage_path.is_absolute():
        coverage_path = REPO_ROOT / coverage_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
            handle.write("\n")

    coverage = build_ranker_coverage_report(
        records,
        rows=rows,
        smoke_status={
            "ui": str(args.ui_smoke_status),
            "network": str(args.network_smoke_status),
            "snapshot": str(args.snapshot_smoke_status),
        },
    )
    coverage_path.write_text(
        json.dumps(coverage, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )

    print(f"ranker_training_rows=ok records={len(records)} rows={len(rows)}")
    print(f"Rows: {output_path}")
    print(f"Coverage: {coverage_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
