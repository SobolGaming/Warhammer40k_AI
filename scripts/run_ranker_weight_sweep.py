#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Iterable, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

DETERMINISTIC_PYTHON_HASH_SEED = "0"


def _ensure_deterministic_python_hash_seed() -> None:
    if os.environ.get("WH40K_ALLOW_RANDOM_HASH_SEED") == "1":
        return
    if os.environ.get("PYTHONHASHSEED") == DETERMINISTIC_PYTHON_HASH_SEED:
        return
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = DETERMINISTIC_PYTHON_HASH_SEED
    os.execvpe(sys.executable, [sys.executable, *sys.argv], env)


if __name__ == "__main__":
    _ensure_deterministic_python_hash_seed()

import run_general_profile_eval as profile_eval
from extract_ranker_training_rows import build_ranker_coverage_report, candidate_rows_from_records
from warhammer40k_ai.engine.ai_component_rankers import (
    CandidateScoreWeights,
    DeterministicComponentRanker,
    default_ai_component_rankers,
)
from warhammer40k_ai.engine.ai_policy_orchestrator import AIPolicyOrchestrator


ROOT = SCRIPT_DIR.parents[0]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "ranker_weight_sweeps" / "current"
DEFAULT_BASELINE_WEIGHT_SET_ID = "baseline"
DEFAULT_REJECTION_REGISTRY = ROOT / "data" / "ranker_weight_sweeps" / "rejected_weight_sets.json"
FINGERPRINT_IGNORED_WEIGHT_SET_KEYS = frozenset(
    {
        "created_at_utc",
        "description",
        "id",
        "metadata",
        "notes",
        "weight_set_id",
    }
)


def _json_safe(value: Any) -> Any:
    return profile_eval._json_safe(value)


def _write_json(path: Path, payload: Any) -> None:
    profile_eval._write_json(path, payload)


def _safe_id(value: str) -> str:
    text = str(value or "").strip().lower() or "weight_set"
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return cleaned.strip("._") or "weight_set"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic General profile matrices across configurable ranker weight sets.",
    )
    parser.add_argument(
        "--weight-sets",
        default="",
        help=(
            "JSON file containing a list or {'weight_sets': [...]} of weight-set definitions. "
            "A built-in baseline is prepended when the baseline id is absent."
        ),
    )
    parser.add_argument("--baseline-weight-set-id", default=DEFAULT_BASELINE_WEIGHT_SET_ID)
    parser.add_argument("--profiles", default=str(profile_eval.DEFAULT_PROFILES_PATH))
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--player1-profile-id", action="append", default=[])
    parser.add_argument("--player2-profile-id", action="append", default=[])
    parser.add_argument(
        "--pairing-mode",
        choices=("cartesian", "mirror", "zip"),
        default="mirror",
        help="How to pair selected Player 1 and Player 2 profiles for every weight set.",
    )
    parser.add_argument("--player1-army", default="")
    parser.add_argument("--player2-army", default="")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--sweep-report-output",
        default="",
        help="Aggregate sweep report JSON. Defaults to <output-dir>/weight_sweep_report.json.",
    )
    parser.add_argument(
        "--rejection-registry",
        default=str(DEFAULT_REJECTION_REGISTRY),
        help="Rejected weight-set registry. Rejected functional fingerprints are skipped by default.",
    )
    parser.add_argument(
        "--allow-rejected-weight-sets",
        action="store_true",
        help="Include weight sets even when their functional fingerprint is present in the rejection registry.",
    )
    parser.add_argument("--max-phase-steps", type=int, default=50)
    parser.add_argument("--decision-record-max", type=int, default=4096)
    parser.add_argument("--profile", action="store_true", help="Enable cProfile artifacts for each profile game.")
    parser.add_argument("--profile-lines", type=int, default=80)
    parser.add_argument("--replay-dir", default="")
    parser.add_argument("--write-records", action="store_true", help="Write per-profile DecisionRecord JSON files.")
    parser.add_argument("--ui-smoke-status", choices=("pass", "fail", "not_run"), default="not_run")
    parser.add_argument("--network-smoke-status", choices=("pass", "fail", "not_run"), default="not_run")
    parser.add_argument("--snapshot-smoke-status", choices=("pass", "fail", "not_run"), default="not_run")
    return parser


def _default_weight_set() -> dict[str, Any]:
    return {
        "weight_set_id": DEFAULT_BASELINE_WEIGHT_SET_ID,
        "description": "Built-in deterministic component-ranker baseline.",
        "components": {},
    }


def _load_weight_sets(path_text: str, *, baseline_weight_set_id: str) -> list[dict[str, Any]]:
    weight_sets: list[dict[str, Any]] = []
    if str(path_text or "").strip():
        path = Path(str(path_text)).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_weight_sets = payload.get("weight_sets") if isinstance(payload, dict) else payload
        if not isinstance(raw_weight_sets, list):
            raise ValueError("weight set config must be a list or an object with a weight_sets list.")
        weight_sets = [_normalize_weight_set(raw) for raw in raw_weight_sets]

    baseline_id = str(baseline_weight_set_id or DEFAULT_BASELINE_WEIGHT_SET_ID).strip() or DEFAULT_BASELINE_WEIGHT_SET_ID
    if not any(str(item.get("weight_set_id", "") or "") == baseline_id for item in weight_sets):
        baseline = _default_weight_set()
        baseline["weight_set_id"] = baseline_id
        weight_sets.insert(0, baseline)

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw in weight_sets:
        item = _normalize_weight_set(raw)
        weight_set_id = str(item.get("weight_set_id", "") or "").strip()
        if weight_set_id in seen:
            raise ValueError(f"Duplicate weight_set_id: {weight_set_id}")
        seen.add(weight_set_id)
        normalized.append(item)
    return normalized


def _normalize_weight_set(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Each weight set must be a JSON object.")
    item = dict(raw)
    weight_set_id = str(item.get("weight_set_id", item.get("id", "")) or "").strip()
    if not weight_set_id:
        raise ValueError("Each weight set requires weight_set_id or id.")
    item["weight_set_id"] = weight_set_id
    item["components"] = _as_dict(item.get("components"))
    return item


def _fingerprintable_weight_set(weight_set: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _normalize_weight_set(weight_set)
    return {
        str(key): _json_safe(value)
        for key, value in sorted(normalized.items())
        if str(key) not in FINGERPRINT_IGNORED_WEIGHT_SET_KEYS
    }


def weight_set_fingerprint(weight_set: Mapping[str, Any]) -> str:
    payload = json.dumps(
        _fingerprintable_weight_set(weight_set),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_rejection_registry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "rejected_weight_sets": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected rejection registry JSON object at {path}.")
    raw_entries = payload.get("rejected_weight_sets", [])
    if not isinstance(raw_entries, list):
        raise ValueError(f"Expected rejected_weight_sets list in rejection registry: {path}.")
    return {"schema_version": int(payload.get("schema_version", 1) or 1), "rejected_weight_sets": list(raw_entries)}


def _rejected_entries_by_fingerprint(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for raw in list(registry.get("rejected_weight_sets", []) or []):
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status", "reject") or "reject")
        if status != "reject":
            continue
        fingerprint = str(raw.get("candidate_fingerprint", "") or "").strip()
        if fingerprint:
            entries[fingerprint] = dict(raw)
    return dict(sorted(entries.items()))


def _filter_rejected_weight_sets(
    weight_sets: list[dict[str, Any]],
    *,
    baseline_weight_set_id: str,
    registry: Mapping[str, Any],
    allow_rejected: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if bool(allow_rejected):
        return weight_sets, []
    rejected_by_fingerprint = _rejected_entries_by_fingerprint(registry)
    if not rejected_by_fingerprint:
        return weight_sets, []
    baseline_id = str(baseline_weight_set_id or DEFAULT_BASELINE_WEIGHT_SET_ID)
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for weight_set in weight_sets:
        weight_set_id = str(weight_set.get("weight_set_id", "") or "")
        if weight_set_id == baseline_id:
            selected.append(weight_set)
            continue
        fingerprint = weight_set_fingerprint(weight_set)
        rejection = rejected_by_fingerprint.get(fingerprint)
        if rejection is None:
            selected.append(weight_set)
            continue
        skipped.append(
            {
                "weight_set_id": weight_set_id,
                "candidate_fingerprint": fingerprint,
                "matched_rejected_weight_set_id": str(rejection.get("weight_set_id", "") or ""),
                "blockers": list(rejection.get("blockers", []) or []),
                "source_analysis_path": str(rejection.get("source_analysis_path", "") or ""),
            }
        )
    return selected, skipped


def _component_spec(weight_set: Mapping[str, Any], component_name: str) -> dict[str, Any]:
    spec = _as_dict(_as_dict(weight_set.get("components")).get(component_name))
    for key in ("component_weights", "component_weight_overrides"):
        value = _as_dict(_as_dict(weight_set).get(key)).get(component_name)
        if isinstance(value, dict):
            merged = _as_dict(spec.get("weights"))
            merged.update(dict(value))
            spec["weights"] = merged
    value = _as_dict(_as_dict(weight_set).get("component_weight_multipliers")).get(component_name)
    if isinstance(value, dict):
        merged = _as_dict(spec.get("weight_multipliers"))
        merged.update(dict(value))
        spec["weight_multipliers"] = merged
    value = _as_dict(_as_dict(weight_set).get("component_weight_scales")).get(component_name)
    if value is not None:
        spec["weight_scale"] = value
    value = _as_dict(_as_dict(weight_set).get("component_skip_penalties")).get(component_name)
    if value is not None:
        spec["skip_penalty"] = value
    value = _as_dict(_as_dict(weight_set).get("component_fallback_penalties")).get(component_name)
    if value is not None:
        spec["fallback_penalty"] = value
    return spec


def _ranker_for_component(
    component_name: str,
    baseline: DeterministicComponentRanker,
    *,
    weight_set: Mapping[str, Any],
) -> DeterministicComponentRanker:
    baseline_weights = dict(getattr(getattr(baseline, "score_weights", None), "weights", {}) or {})
    baseline_skip = float(getattr(getattr(baseline, "score_weights", None), "skip_penalty", -1.0))
    baseline_fallback = float(getattr(getattr(baseline, "score_weights", None), "fallback_penalty", -0.1))
    spec = _component_spec(weight_set, component_name)
    scale = _safe_float(spec.get("weight_scale", weight_set.get("global_weight_scale", 1.0)), 1.0)
    weights = {str(key): round(float(value) * scale, 8) for key, value in sorted(baseline_weights.items())}
    for key, multiplier in sorted(_as_dict(spec.get("weight_multipliers")).items()):
        text_key = str(key)
        weights[text_key] = round(float(weights.get(text_key, 0.0)) * _safe_float(multiplier, 1.0), 8)
    for key, value in sorted(_as_dict(spec.get("weights")).items()):
        weights[str(key)] = round(_safe_float(value), 8)
    skip_penalty = _safe_float(spec.get("skip_penalty", weight_set.get("skip_penalty", baseline_skip)), baseline_skip)
    fallback_penalty = _safe_float(
        spec.get("fallback_penalty", weight_set.get("fallback_penalty", baseline_fallback)),
        baseline_fallback,
    )
    return DeterministicComponentRanker(
        component_name=str(component_name),
        score_weights=CandidateScoreWeights(
            weights=weights,
            skip_penalty=skip_penalty,
            fallback_penalty=fallback_penalty,
        ),
    )


def build_orchestrator_for_weight_set(weight_set: Mapping[str, Any]) -> AIPolicyOrchestrator:
    baseline_rankers = default_ai_component_rankers()
    components = {
        component_name: _ranker_for_component(component_name, ranker, weight_set=weight_set)
        for component_name, ranker in sorted(baseline_rankers.items())
    }
    return AIPolicyOrchestrator(components=components)


def _extract_rate(coverage: Mapping[str, Any], path: tuple[str, ...]) -> float:
    value: Any = dict(coverage or {})
    for key in path:
        if not isinstance(value, dict):
            return 0.0
        value = value.get(key)
    return _safe_float(value, 0.0)


def _aggregate_result_row(
    *,
    weight_set: Mapping[str, Any],
    matrix_report: Mapping[str, Any],
    coverage: Mapping[str, Any],
    weight_set_dir: Path,
    ranker_rows_path: Path,
    ranker_coverage_path: Path,
) -> dict[str, Any]:
    aggregate = dict(matrix_report.get("aggregate", {}) or {})
    return {
        "weight_set_id": str(weight_set.get("weight_set_id", "") or ""),
        "description": str(weight_set.get("description", "") or ""),
        "profile_pair_count": int(aggregate.get("profile_pair_count", matrix_report.get("profile_pair_count", 0)) or 0),
        "mean_vp_differential_player1_minus_player2": _safe_float(
            aggregate.get("mean_vp_differential_player1_minus_player2"),
            0.0,
        ),
        "winner_counts": dict(aggregate.get("winner_counts", {}) or {}),
        "player1_win_count": int(aggregate.get("player1_win_count", 0) or 0),
        "player2_win_count": int(aggregate.get("player2_win_count", 0) or 0),
        "tie_count": int(aggregate.get("tie_count", 0) or 0),
        "total_phase_count": int(aggregate.get("total_phase_count", 0) or 0),
        "total_decision_count": int(aggregate.get("total_decision_count", 0) or 0),
        "fallback_rate": _extract_rate(coverage, ("commander_assignment_hit_fallback_rate", "fallback_rate")),
        "commander_assignment_hit_rate": _extract_rate(
            coverage,
            ("commander_assignment_hit_fallback_rate", "hit_rate"),
        ),
        "stale_plan_rate": _extract_rate(coverage, ("stale_plan_rate", "stale_rate")),
        "resource_authorization_usage": dict(coverage.get("resource_authorization_used_rejected", {}) or {}),
        "deployment_tempo_usage": dict(coverage.get("deployment_tempo_usage", {}) or {}),
        "chosen_action_rank_under_current_ranker": dict(
            coverage.get("chosen_action_rank_under_current_ranker", {}) or {}
        ),
        "context_payload_byte_distribution": dict(coverage.get("context_payload_byte_distribution", {}) or {}),
        "smoke_status": dict(matrix_report.get("smoke_status", {}) or {}),
        "matrix_report_path": str((weight_set_dir / "matrix_report.json").resolve()),
        "ranker_rows_path": str(ranker_rows_path.resolve()),
        "ranker_coverage_path": str(ranker_coverage_path.resolve()),
    }


def _baseline_delta(row: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    numeric_keys = (
        "mean_vp_differential_player1_minus_player2",
        "player1_win_count",
        "player2_win_count",
        "tie_count",
        "total_phase_count",
        "total_decision_count",
        "fallback_rate",
        "commander_assignment_hit_rate",
        "stale_plan_rate",
    )
    return {
        key: round(_safe_float(row.get(key), 0.0) - _safe_float(baseline.get(key), 0.0), 6)
        for key in numeric_keys
    }


def _resolve_path(raw: str, *, default: Path) -> Path:
    text = str(raw or "").strip()
    path = default if not text else Path(text).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def _selected_profile_pairs(args: argparse.Namespace, document: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    catalog = profile_eval._profile_catalog(document)
    generic_profiles = profile_eval._profiles_by_id(document, args.profile_id)
    player1_profiles = profile_eval._profiles_by_id(document, args.player1_profile_id) or generic_profiles or list(catalog.values())
    player2_profiles = profile_eval._profiles_by_id(document, args.player2_profile_id) or generic_profiles or list(catalog.values())
    return profile_eval._profile_pairings(
        player1_profiles=player1_profiles,
        player2_profiles=player2_profiles,
        pairing_mode=str(args.pairing_mode),
    )


def _run_weight_set(
    *,
    args: argparse.Namespace,
    weight_set: dict[str, Any],
    profiles_path: Path,
    profile_pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    player1_army: str,
    player2_army: str,
    seed: int,
    output_dir: Path,
    smoke_status: dict[str, str],
) -> dict[str, Any]:
    weight_set_id = str(weight_set.get("weight_set_id", "") or "")
    weight_set_dir = output_dir / _safe_id(weight_set_id)
    weight_set_dir.mkdir(parents=True, exist_ok=True)
    orchestrator = build_orchestrator_for_weight_set(weight_set)
    summaries: list[dict[str, Any]] = []
    records_by_pair: dict[str, list[dict[str, Any]]] = {}
    all_records: list[dict[str, Any]] = []
    for run_index, (player1_profile, player2_profile) in enumerate(profile_pairs):
        summary, records = profile_eval._run_profile_game(
            run_index=run_index,
            player1_profile=player1_profile,
            player2_profile=player2_profile,
            player1_army=player1_army,
            player2_army=player2_army,
            seed=seed,
            max_phase_steps=max(1, int(args.max_phase_steps or 50)),
            output_dir=weight_set_dir,
            profile_enabled=bool(args.profile),
            profile_lines=max(1, int(args.profile_lines or 80)),
            replay_dir=str(args.replay_dir or ""),
            ai_orchestrator=orchestrator,
            collect_records=True,
            write_records=bool(args.write_records),
        )
        summaries.append(summary)
        pair_id = str(summary.get("profile_pair_id", "") or "")
        records_by_pair[pair_id] = list(records)
        all_records.extend(records)
        print(
            f"{weight_set_id}: {summary['player1_profile_id']} vs {summary['player2_profile_id']} "
            f"{summary['winner_score_line']} in {summary['elapsed_seconds']:.2f}s"
        )

    rows = candidate_rows_from_records(all_records)
    coverage = build_ranker_coverage_report(all_records, rows=rows, smoke_status=smoke_status)
    ranker_rows_path = weight_set_dir / "ranker_training_rows.jsonl"
    with ranker_rows_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
            handle.write("\n")
    ranker_coverage_path = weight_set_dir / "ranker_training_coverage.json"
    _write_json(ranker_coverage_path, coverage)
    matrix_report = profile_eval._build_profile_matrix_report(
        summaries=summaries,
        records_by_profile_pair_id=records_by_pair,
        profiles_path=profiles_path,
        player1_army=player1_army,
        player2_army=player2_army,
        seed=seed,
        decision_record_max=max(1, int(args.decision_record_max or 4096)),
        pairing_mode=str(args.pairing_mode),
        smoke_status=smoke_status,
        ranker_rows_path=str(ranker_rows_path.resolve()),
        ranker_coverage_path=str(ranker_coverage_path.resolve()),
    )
    matrix_report["weight_set_id"] = weight_set_id
    matrix_report["weight_set"] = _json_safe(weight_set)
    matrix_report_path = weight_set_dir / "matrix_report.json"
    _write_json(matrix_report_path, matrix_report)
    summary_path = weight_set_dir / "summary.json"
    _write_json(
        summary_path,
        {
            "weight_set_id": weight_set_id,
            "matrix_report_path": str(matrix_report_path.resolve()),
            "ranker_rows_path": str(ranker_rows_path.resolve()),
            "ranker_coverage_path": str(ranker_coverage_path.resolve()),
            "summaries": summaries,
        },
    )
    return _aggregate_result_row(
        weight_set=weight_set,
        matrix_report=matrix_report,
        coverage=coverage,
        weight_set_dir=weight_set_dir,
        ranker_rows_path=ranker_rows_path,
        ranker_coverage_path=ranker_coverage_path,
    )


def main() -> int:
    args = _build_parser().parse_args()
    profiles_path = _resolve_path(str(args.profiles), default=profile_eval.DEFAULT_PROFILES_PATH)
    document = profile_eval._load_profile_document(profiles_path)
    profile_pairs = _selected_profile_pairs(args, document)
    if not profile_pairs:
        raise ValueError("No profile pairs selected for weight sweep.")
    player1_army = str(args.player1_army or document.get("default_player1_army", "") or "")
    player2_army = str(args.player2_army or document.get("default_player2_army", "") or "")
    if not player1_army or not player2_army:
        raise ValueError("Both player army paths are required.")
    seed = int(args.seed or document.get("default_seed", 2026052000) or 2026052000)
    output_dir = _resolve_path(str(args.output_dir), default=DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ["WH40K_DECISION_RECORD_MAX"] = str(max(1, int(args.decision_record_max or 4096)))
    smoke_status = {
        "ui": str(args.ui_smoke_status),
        "network": str(args.network_smoke_status),
        "snapshot": str(args.snapshot_smoke_status),
    }
    weight_sets = _load_weight_sets(
        str(args.weight_sets or ""),
        baseline_weight_set_id=str(args.baseline_weight_set_id or DEFAULT_BASELINE_WEIGHT_SET_ID),
    )
    rejection_registry_path = _resolve_path(str(args.rejection_registry or ""), default=DEFAULT_REJECTION_REGISTRY)
    rejection_registry = _load_rejection_registry(rejection_registry_path)
    requested_candidate_count = sum(
        1
        for weight_set in weight_sets
        if str(weight_set.get("weight_set_id", "") or "") != str(args.baseline_weight_set_id or DEFAULT_BASELINE_WEIGHT_SET_ID)
    )
    weight_sets, skipped_rejected_weight_sets = _filter_rejected_weight_sets(
        weight_sets,
        baseline_weight_set_id=str(args.baseline_weight_set_id or DEFAULT_BASELINE_WEIGHT_SET_ID),
        registry=rejection_registry,
        allow_rejected=bool(args.allow_rejected_weight_sets),
    )
    selected_candidate_count = sum(
        1
        for weight_set in weight_sets
        if str(weight_set.get("weight_set_id", "") or "") != str(args.baseline_weight_set_id or DEFAULT_BASELINE_WEIGHT_SET_ID)
    )
    if requested_candidate_count > 0 and selected_candidate_count == 0:
        skipped_ids = ", ".join(str(item.get("weight_set_id", "") or "") for item in skipped_rejected_weight_sets)
        raise ValueError(
            "All non-baseline weight sets are marked rejected. "
            f"Provide fresh candidates or pass --allow-rejected-weight-sets. Skipped: {skipped_ids}"
        )
    if skipped_rejected_weight_sets:
        skipped_ids = ", ".join(str(item.get("weight_set_id", "") or "") for item in skipped_rejected_weight_sets)
        print(f"Skipped rejected weight sets: {skipped_ids}")
    rows: list[dict[str, Any]] = []
    for weight_set in weight_sets:
        rows.append(
            _run_weight_set(
                args=args,
                weight_set=weight_set,
                profiles_path=profiles_path,
                profile_pairs=profile_pairs,
                player1_army=player1_army,
                player2_army=player2_army,
                seed=seed,
                output_dir=output_dir,
                smoke_status=smoke_status,
            )
        )

    baseline_id = str(args.baseline_weight_set_id or DEFAULT_BASELINE_WEIGHT_SET_ID)
    baseline = next((row for row in rows if str(row.get("weight_set_id", "")) == baseline_id), rows[0])
    for row in rows:
        row["baseline_delta"] = _baseline_delta(row, baseline)
    ordered_rows = sorted(
        rows,
        key=lambda row: (
            -_safe_float(dict(row.get("baseline_delta", {}) or {}).get("mean_vp_differential_player1_minus_player2"), 0.0),
            str(row.get("weight_set_id", "")),
        ),
    )
    report = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "profiles_path": str(profiles_path.resolve()),
        "player1_army": player1_army,
        "player2_army": player2_army,
        "seed": int(seed),
        "pairing_mode": str(args.pairing_mode),
        "baseline_weight_set_id": baseline_id,
        "weight_set_count": int(len(rows)),
        "profile_pair_count": int(len(profile_pairs)),
        "smoke_status": dict(smoke_status),
        "rejection_registry_path": str(rejection_registry_path.resolve()),
        "skipped_rejected_weight_sets": skipped_rejected_weight_sets,
        "rows": ordered_rows,
    }
    report_path = _resolve_path(
        str(args.sweep_report_output or ""),
        default=output_dir / "weight_sweep_report.json",
    )
    _write_json(report_path, report)
    print(f"Weight sweep report: {report_path}")
    print(f"Weight sets: {len(rows)}")
    print(f"Best delta: {ordered_rows[0]['weight_set_id']} {ordered_rows[0]['baseline_delta']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
