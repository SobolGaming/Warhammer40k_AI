#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
DEFAULT_ANALYSIS = ROOT / "data" / "ranker_weight_sweeps" / "current" / "weight_sweep_analysis.json"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "ranker_weight_sweeps" / "promoted_baselines"


def _safe_id(value: str) -> str:
    text = str(value or "").strip().lower() or "weight_set"
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return cleaned.strip("._") or "weight_set"


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}.")
    return dict(payload)


def _write_json(path: Path, payload: Mapping[str, Any], *, force: bool) -> None:
    if path.exists() and not bool(force):
        raise FileExistsError(f"Refusing to overwrite existing promotion artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _resolve_path(raw: str, *, default: Path, base: Path | None = None) -> Path:
    text = str(raw or "").strip()
    path = default if not text else Path(text).expanduser()
    if not path.is_absolute():
        path = (base or ROOT) / path
    return path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Promote an analyzed ranker weight-sweep candidate into an auditable weight-set artifact.",
    )
    parser.add_argument("--analysis", default=str(DEFAULT_ANALYSIS), help="weight_sweep_analysis.json path.")
    parser.add_argument(
        "--weight-set-id",
        default="",
        help="Candidate weight_set_id to promote. Defaults to the analysis recommendation.",
    )
    parser.add_argument(
        "--promoted-weight-set-id",
        default="",
        help="Optional new id for the emitted weight set. Defaults to the source candidate id.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output JSON path. Defaults to data/ranker_weight_sweeps/promoted_baselines/<promoted-id>.json.",
    )
    parser.add_argument("--allow-review", action="store_true", help="Allow promoting a review candidate.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output artifact.")
    parser.add_argument("--notes", default="", help="Human promotion notes stored in provenance.")
    return parser


def _analysis_rows_by_id(analysis: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for raw in list(analysis.get("all_weight_sets", []) or []):
        item = _as_dict(raw)
        weight_set_id = str(item.get("weight_set_id", "") or "").strip()
        if weight_set_id:
            rows[weight_set_id] = item
    return dict(sorted(rows.items()))


def _selected_candidate(analysis: Mapping[str, Any], requested_weight_set_id: str) -> dict[str, Any]:
    rows = _analysis_rows_by_id(analysis)
    selected_id = str(requested_weight_set_id or "").strip()
    if not selected_id:
        selected_id = str(_as_dict(analysis.get("summary")).get("recommended_weight_set_id", "") or "").strip()
    if not selected_id:
        raise ValueError("No weight set was requested and the analysis has no recommendation.")
    candidate = rows.get(selected_id)
    if candidate is None:
        raise ValueError(f"Candidate weight set {selected_id!r} was not found in the analysis.")
    return dict(candidate)


def _validate_candidate_status(candidate: Mapping[str, Any], *, allow_review: bool) -> None:
    status = str(candidate.get("status", "") or "")
    blockers = list(candidate.get("blockers", []) or [])
    if blockers:
        raise ValueError(f"Cannot promote {candidate.get('weight_set_id')}: blockers remain: {blockers}")
    if status == "promote_candidate":
        return
    if status == "review" and bool(allow_review):
        return
    if status == "review":
        raise ValueError("Candidate is review-only; pass --allow-review after human inspection.")
    raise ValueError(f"Candidate status {status!r} is not promotable.")


def _candidate_matrix_path(candidate: Mapping[str, Any], *, analysis_path: Path) -> Path:
    artifact_paths = _as_dict(candidate.get("artifact_paths"))
    raw_path = str(artifact_paths.get("matrix_report", "") or "").strip()
    if not raw_path:
        raise ValueError("Candidate analysis row is missing artifact_paths.matrix_report.")
    return _resolve_path(raw_path, default=Path(raw_path), base=analysis_path.parent)


def _candidate_weight_set(candidate: Mapping[str, Any], *, analysis_path: Path) -> dict[str, Any]:
    matrix_path = _candidate_matrix_path(candidate, analysis_path=analysis_path)
    matrix_report = _read_json_object(matrix_path)
    weight_set = _as_dict(matrix_report.get("weight_set"))
    if not weight_set:
        raise ValueError(f"Matrix report does not contain a weight_set object: {matrix_path}")
    source_id = str(candidate.get("weight_set_id", "") or "").strip()
    matrix_id = str(weight_set.get("weight_set_id", "") or "").strip()
    if source_id and matrix_id and source_id != matrix_id:
        raise ValueError(f"Analysis candidate id {source_id!r} does not match matrix weight_set_id {matrix_id!r}.")
    if not matrix_id:
        weight_set["weight_set_id"] = source_id
    return dict(weight_set)


def build_promotion_artifact(
    analysis: Mapping[str, Any],
    *,
    analysis_path: Path,
    weight_set_id: str = "",
    promoted_weight_set_id: str = "",
    allow_review: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    candidate = _selected_candidate(analysis, weight_set_id)
    _validate_candidate_status(candidate, allow_review=allow_review)
    source_weight_set = _candidate_weight_set(candidate, analysis_path=analysis_path)
    source_weight_set_id = str(candidate.get("weight_set_id", source_weight_set.get("weight_set_id", "")) or "").strip()
    promoted_id = str(promoted_weight_set_id or source_weight_set_id).strip()
    if not promoted_id:
        raise ValueError("Promoted weight-set id could not be resolved.")
    promoted_weight_set = dict(source_weight_set)
    promoted_weight_set["weight_set_id"] = promoted_id
    promotion = {
        "source_weight_set_id": source_weight_set_id,
        "promoted_weight_set_id": promoted_id,
        "candidate_status": str(candidate.get("status", "") or ""),
        "source_analysis_path": str(analysis_path.resolve()),
        "source_sweep_report": str(analysis.get("source_report", "") or ""),
        "baseline_weight_set_id": str(analysis.get("baseline_weight_set_id", "") or ""),
        "promotion_policy": _as_dict(analysis.get("promotion_policy")),
        "metrics": _as_dict(candidate.get("metrics")),
        "baseline_delta": _as_dict(candidate.get("baseline_delta")),
        "consistency": _as_dict(candidate.get("consistency")),
        "review_flags": list(candidate.get("review_flags", []) or []),
        "resource_usage_anomalies": list(candidate.get("resource_usage_anomalies", []) or []),
        "artifact_paths": _as_dict(candidate.get("artifact_paths")),
        "notes": str(notes or ""),
    }
    return {
        "artifact_kind": "ranker_weight_baseline_promotion",
        "schema_version": 1,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "promotion": promotion,
        "weight_sets": [promoted_weight_set],
    }


def main() -> int:
    args = _build_parser().parse_args()
    analysis_path = _resolve_path(str(args.analysis), default=DEFAULT_ANALYSIS)
    analysis = _read_json_object(analysis_path)
    artifact = build_promotion_artifact(
        analysis,
        analysis_path=analysis_path,
        weight_set_id=str(args.weight_set_id or ""),
        promoted_weight_set_id=str(args.promoted_weight_set_id or ""),
        allow_review=bool(args.allow_review),
        notes=str(args.notes or ""),
    )
    promoted_id = str(_as_dict(artifact.get("promotion")).get("promoted_weight_set_id", "") or "promoted")
    output_path = _resolve_path(
        str(args.output or ""),
        default=DEFAULT_OUTPUT_DIR / f"{_safe_id(promoted_id)}.json",
    )
    _write_json(output_path, artifact, force=bool(args.force))
    promotion = _as_dict(artifact.get("promotion"))
    print(f"Promoted ranker weight artifact: {output_path}")
    print(f"Source candidate: {promotion.get('source_weight_set_id')} -> {promotion.get('promoted_weight_set_id')}")
    print("Engine defaults were not changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
