from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


MANIFEST_VERSION = "1.0.0"

_SEMANTIC_METADATA_KEYS = (
    "projected_score_delta_next_window",
    "projected_score_delta_round",
    "projected_deny_delta_next_window",
    "projected_control_delta",
    "projected_action_enablement_delta",
    "projected_exposure_delta",
    "projected_trade_ev",
    "cover_delta",
    "los_delta",
    "resource_delta",
    "rules_provenance_refs",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _descriptor_bundle_fingerprint(descriptor_ids: dict[str, Any]) -> str:
    payload = {
        "mission_descriptor_id": str(descriptor_ids.get("mission_descriptor_id", "") or ""),
        "objective_descriptor_ids": sorted(
            str(item) for item in list(descriptor_ids.get("objective_descriptor_ids", []) or []) if str(item)
        ),
        "terrain_descriptor_ids": sorted(
            str(item) for item in list(descriptor_ids.get("terrain_descriptor_ids", []) or []) if str(item)
        ),
        "deployment_descriptor_id": str(descriptor_ids.get("deployment_descriptor_id", "") or ""),
        "tool_descriptor_ids": sorted(
            str(item) for item in list(descriptor_ids.get("tool_descriptor_ids", []) or []) if str(item)
        ),
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"descriptor_bundle:{digest[:16]}"


def _decision_type_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in list(records or []):
        decision_type = str(record.get("decision_type", "") or "UNKNOWN")
        counts[decision_type] = int(counts.get(decision_type, 0) or 0) + 1
    return {key: counts[key] for key in sorted(counts.keys())}


def _rules_bundle_ids(records: list[dict[str, Any]]) -> list[str]:
    ids = {str(record.get("rules_bundle_id", "") or "") for record in list(records or []) if str(record.get("rules_bundle_id", "") or "")}
    return sorted(ids)


def _descriptor_bundle_ids(records: list[dict[str, Any]]) -> list[str]:
    ids: set[str] = set()
    for record in list(records or []):
        descriptor_ids = dict(record.get("descriptor_ids", {}) or {})
        if not descriptor_ids:
            continue
        ids.add(_descriptor_bundle_fingerprint(descriptor_ids))
    return sorted(ids)


def _candidates_have_semantic_metadata(record: dict[str, Any]) -> bool:
    for candidate in list(record.get("candidates", []) or []):
        metadata = dict(candidate.get("metadata", {}) or {})
        for key in _SEMANTIC_METADATA_KEYS:
            if key not in metadata:
                return False
    return True


def _coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = int(len(records or []))
    with_semantics = 0
    relabeled = 0
    for record in list(records or []):
        if _candidates_have_semantic_metadata(record):
            with_semantics += 1
        if str(record.get("relabel_status", "") or ""):
            relabeled += 1
    ratio = float(with_semantics) / float(total) if total > 0 else 0.0
    return {
        "records_with_semantic_candidate_metadata": int(with_semantics),
        "semantic_candidate_metadata_ratio": float(round(ratio, 6)),
        "records_with_relabel_status": int(relabeled),
    }


@dataclass(frozen=True)
class TrainingDataManifest:
    manifest_version: str
    generated_at_utc: str
    source_tag: str
    total_records: int
    rules_bundle_ids: tuple[str, ...]
    descriptor_bundle_ids: tuple[str, ...]
    decision_type_counts: dict[str, int]
    coverage: dict[str, Any]
    gate_requirements: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": str(self.manifest_version or ""),
            "generated_at_utc": str(self.generated_at_utc or ""),
            "source_tag": str(self.source_tag or ""),
            "total_records": int(self.total_records),
            "rules_bundle_ids": list(self.rules_bundle_ids),
            "descriptor_bundle_ids": list(self.descriptor_bundle_ids),
            "decision_type_counts": {str(k): int(v) for k, v in sorted(self.decision_type_counts.items())},
            "coverage": dict(self.coverage or {}),
            "gate_requirements": dict(self.gate_requirements or {}),
        }


def build_training_manifest(
    records: list[dict[str, Any]],
    *,
    source_tag: str,
    min_tier3_records: int = 10000,
) -> TrainingDataManifest:
    record_list = [dict(record or {}) for record in list(records or [])]
    total_records = int(len(record_list))
    decision_type_counts = _decision_type_counts(record_list)
    coverage = _coverage(record_list)
    gate_requirements = {
        "minimum_tier3_pretraining_records": int(min_tier3_records),
        "meets_minimum_tier3_pretraining_records": bool(total_records >= int(min_tier3_records)),
        "semantic_candidate_metadata_required": True,
        "semantic_candidate_metadata_complete": bool(
            coverage.get("records_with_semantic_candidate_metadata", 0) == total_records
        ),
    }
    return TrainingDataManifest(
        manifest_version=MANIFEST_VERSION,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        source_tag=str(source_tag or ""),
        total_records=total_records,
        rules_bundle_ids=tuple(_rules_bundle_ids(record_list)),
        descriptor_bundle_ids=tuple(_descriptor_bundle_ids(record_list)),
        decision_type_counts=decision_type_counts,
        coverage=coverage,
        gate_requirements=gate_requirements,
    )


def validate_training_manifest(manifest: dict[str, Any]) -> list[str]:
    payload = dict(manifest or {})
    errors: list[str] = []
    required_fields = (
        "manifest_version",
        "generated_at_utc",
        "source_tag",
        "total_records",
        "rules_bundle_ids",
        "descriptor_bundle_ids",
        "decision_type_counts",
        "coverage",
        "gate_requirements",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        errors.append(f"Missing manifest fields: {', '.join(missing)}")

    total_records = int(payload.get("total_records", 0) or 0)
    if total_records < 0:
        errors.append("total_records must be >= 0")

    decision_counts = dict(payload.get("decision_type_counts", {}) or {})
    counted = sum(int(value or 0) for value in decision_counts.values())
    if counted != total_records:
        errors.append(
            f"total_records mismatch: total_records={total_records} but decision_type_counts sum={counted}"
        )

    rules_bundle_ids = payload.get("rules_bundle_ids")
    if not isinstance(rules_bundle_ids, list):
        errors.append("rules_bundle_ids must be a list")
    descriptor_bundle_ids = payload.get("descriptor_bundle_ids")
    if not isinstance(descriptor_bundle_ids, list):
        errors.append("descriptor_bundle_ids must be a list")

    coverage = dict(payload.get("coverage", {}) or {})
    semantic_count = int(coverage.get("records_with_semantic_candidate_metadata", 0) or 0)
    if semantic_count > total_records:
        errors.append("coverage.records_with_semantic_candidate_metadata cannot exceed total_records")

    gate_requirements = dict(payload.get("gate_requirements", {}) or {})
    min_records = int(gate_requirements.get("minimum_tier3_pretraining_records", 0) or 0)
    if min_records < 0:
        errors.append("gate_requirements.minimum_tier3_pretraining_records must be >= 0")
    return errors
