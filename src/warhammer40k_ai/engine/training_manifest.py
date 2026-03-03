from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


MANIFEST_VERSION = "1.1.0"
PRE_ML_BASELINE_GATE_PROFILE_ID = "pre_ml_baseline_v1"
_RATIO_PRECISION = 6

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


@dataclass(frozen=True)
class TrainingDataGateProfile:
    gate_profile_id: str
    minimum_tier3_pretraining_records: int
    required_semantic_candidate_metadata_ratio: float
    required_relabel_status_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_profile_id": str(self.gate_profile_id or ""),
            "minimum_tier3_pretraining_records": int(self.minimum_tier3_pretraining_records),
            "required_semantic_candidate_metadata_ratio": float(self.required_semantic_candidate_metadata_ratio),
            "required_relabel_status_ratio": float(self.required_relabel_status_ratio),
        }


PRE_ML_BASELINE_GATE_PROFILE = TrainingDataGateProfile(
    gate_profile_id=PRE_ML_BASELINE_GATE_PROFILE_ID,
    minimum_tier3_pretraining_records=10000,
    required_semantic_candidate_metadata_ratio=1.0,
    required_relabel_status_ratio=1.0,
)


def _round_ratio(value: float) -> float:
    return float(round(float(value), _RATIO_PRECISION))


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return _round_ratio(float(numerator) / float(denominator))


def _resolve_gate_profile(profile_id: str) -> TrainingDataGateProfile:
    normalized = str(profile_id or PRE_ML_BASELINE_GATE_PROFILE_ID)
    if normalized == PRE_ML_BASELINE_GATE_PROFILE_ID:
        return PRE_ML_BASELINE_GATE_PROFILE
    raise ValueError(f"Unknown training-data gate profile id: {normalized}")


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
    semantic_ratio = _ratio(with_semantics, total)
    relabel_ratio = _ratio(relabeled, total)
    return {
        "records_with_semantic_candidate_metadata": int(with_semantics),
        "semantic_candidate_metadata_ratio": semantic_ratio,
        "records_with_relabel_status": int(relabeled),
        "relabel_status_ratio": relabel_ratio,
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
    gate_profile_id: str = PRE_ML_BASELINE_GATE_PROFILE_ID,
) -> TrainingDataManifest:
    record_list = [dict(record or {}) for record in list(records or [])]
    total_records = int(len(record_list))
    decision_type_counts = _decision_type_counts(record_list)
    coverage = _coverage(record_list)
    gate_profile = _resolve_gate_profile(gate_profile_id)
    semantic_ratio = float(coverage.get("semantic_candidate_metadata_ratio", 0.0) or 0.0)
    relabel_ratio = float(coverage.get("relabel_status_ratio", 0.0) or 0.0)
    profile_min_records = int(gate_profile.minimum_tier3_pretraining_records)
    profile_semantic_ratio = float(gate_profile.required_semantic_candidate_metadata_ratio)
    profile_relabel_ratio = float(gate_profile.required_relabel_status_ratio)
    meets_profile_minimum = bool(total_records >= profile_min_records)
    meets_profile_semantic = bool(semantic_ratio >= profile_semantic_ratio)
    meets_profile_relabel = bool(relabel_ratio >= profile_relabel_ratio)
    gate_requirements = {
        "minimum_tier3_pretraining_records": int(min_tier3_records),
        "meets_minimum_tier3_pretraining_records": bool(total_records >= int(min_tier3_records)),
        "semantic_candidate_metadata_required": True,
        "semantic_candidate_metadata_complete": bool(
            coverage.get("records_with_semantic_candidate_metadata", 0) == total_records
        ),
        "gate_profile_id": str(gate_profile.gate_profile_id),
        "gate_profile_minimum_tier3_pretraining_records": profile_min_records,
        "required_semantic_candidate_metadata_ratio": profile_semantic_ratio,
        "required_relabel_status_ratio": profile_relabel_ratio,
        "meets_gate_profile_minimum_tier3_pretraining_records": meets_profile_minimum,
        "meets_required_semantic_candidate_metadata_ratio": meets_profile_semantic,
        "meets_required_relabel_status_ratio": meets_profile_relabel,
        "meets_gate_profile": bool(
            meets_profile_minimum and meets_profile_semantic and meets_profile_relabel
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
    relabel_count = int(coverage.get("records_with_relabel_status", 0) or 0)
    if semantic_count > total_records:
        errors.append("coverage.records_with_semantic_candidate_metadata cannot exceed total_records")
    if relabel_count > total_records:
        errors.append("coverage.records_with_relabel_status cannot exceed total_records")

    semantic_ratio = float(coverage.get("semantic_candidate_metadata_ratio", 0.0) or 0.0)
    relabel_ratio = float(coverage.get("relabel_status_ratio", 0.0) or 0.0)
    if semantic_ratio < 0.0 or semantic_ratio > 1.0:
        errors.append("coverage.semantic_candidate_metadata_ratio must be in [0, 1]")
    if relabel_ratio < 0.0 or relabel_ratio > 1.0:
        errors.append("coverage.relabel_status_ratio must be in [0, 1]")
    if semantic_ratio != _ratio(semantic_count, total_records):
        errors.append(
            "coverage.semantic_candidate_metadata_ratio must match records_with_semantic_candidate_metadata"
        )
    if relabel_ratio != _ratio(relabel_count, total_records):
        errors.append("coverage.relabel_status_ratio must match records_with_relabel_status")

    gate_requirements = dict(payload.get("gate_requirements", {}) or {})
    min_records = int(gate_requirements.get("minimum_tier3_pretraining_records", 0) or 0)
    if min_records < 0:
        errors.append("gate_requirements.minimum_tier3_pretraining_records must be >= 0")
    if bool(gate_requirements.get("meets_minimum_tier3_pretraining_records", False)) != bool(
        total_records >= min_records
    ):
        errors.append(
            "gate_requirements.meets_minimum_tier3_pretraining_records must match total_records threshold evaluation"
        )

    if bool(gate_requirements.get("semantic_candidate_metadata_complete", False)) != bool(
        semantic_count == total_records
    ):
        errors.append(
            "gate_requirements.semantic_candidate_metadata_complete must match semantic coverage completeness"
        )

    gate_profile_id = str(gate_requirements.get("gate_profile_id", "") or "")
    if not gate_profile_id:
        errors.append("gate_requirements.gate_profile_id is required")
        return errors
    if gate_profile_id != PRE_ML_BASELINE_GATE_PROFILE_ID:
        errors.append(
            f"gate_requirements.gate_profile_id must be {PRE_ML_BASELINE_GATE_PROFILE_ID}"
        )
        return errors
    gate_profile = PRE_ML_BASELINE_GATE_PROFILE
    profile_min_records = int(gate_requirements.get("gate_profile_minimum_tier3_pretraining_records", 0) or 0)
    required_semantic_ratio = float(gate_requirements.get("required_semantic_candidate_metadata_ratio", 0.0) or 0.0)
    required_relabel_ratio = float(gate_requirements.get("required_relabel_status_ratio", 0.0) or 0.0)
    if profile_min_records != int(gate_profile.minimum_tier3_pretraining_records):
        errors.append(
            "gate_requirements.gate_profile_minimum_tier3_pretraining_records must match canonical gate profile"
        )
    if required_semantic_ratio != float(gate_profile.required_semantic_candidate_metadata_ratio):
        errors.append(
            "gate_requirements.required_semantic_candidate_metadata_ratio must match canonical gate profile"
        )
    if required_relabel_ratio != float(gate_profile.required_relabel_status_ratio):
        errors.append("gate_requirements.required_relabel_status_ratio must match canonical gate profile")
    if required_semantic_ratio < 0.0 or required_semantic_ratio > 1.0:
        errors.append("gate_requirements.required_semantic_candidate_metadata_ratio must be in [0, 1]")
    if required_relabel_ratio < 0.0 or required_relabel_ratio > 1.0:
        errors.append("gate_requirements.required_relabel_status_ratio must be in [0, 1]")

    meets_profile_minimum = bool(gate_requirements.get("meets_gate_profile_minimum_tier3_pretraining_records", False))
    meets_profile_semantic = bool(gate_requirements.get("meets_required_semantic_candidate_metadata_ratio", False))
    meets_profile_relabel = bool(gate_requirements.get("meets_required_relabel_status_ratio", False))
    if meets_profile_minimum != bool(total_records >= profile_min_records):
        errors.append(
            "gate_requirements.meets_gate_profile_minimum_tier3_pretraining_records must match profile minimum evaluation"
        )
    if meets_profile_semantic != bool(semantic_ratio >= required_semantic_ratio):
        errors.append(
            "gate_requirements.meets_required_semantic_candidate_metadata_ratio must match profile semantic ratio evaluation"
        )
    if meets_profile_relabel != bool(relabel_ratio >= required_relabel_ratio):
        errors.append(
            "gate_requirements.meets_required_relabel_status_ratio must match profile relabel ratio evaluation"
        )
    if bool(gate_requirements.get("meets_gate_profile", False)) != bool(
        meets_profile_minimum and meets_profile_semantic and meets_profile_relabel
    ):
        errors.append("gate_requirements.meets_gate_profile must match gate-profile check conjunction")
    return errors


def validate_gate_profile_compliance(manifest: dict[str, Any]) -> list[str]:
    payload = dict(manifest or {})
    gate_requirements = dict(payload.get("gate_requirements", {}) or {})
    failures: list[str] = []
    gate_profile_id = str(gate_requirements.get("gate_profile_id", "") or "")
    if gate_profile_id != PRE_ML_BASELINE_GATE_PROFILE_ID:
        failures.append(
            f"Gate profile id mismatch: expected {PRE_ML_BASELINE_GATE_PROFILE_ID}, found {gate_profile_id or 'missing'}"
        )
        return failures

    if not bool(gate_requirements.get("meets_gate_profile_minimum_tier3_pretraining_records", False)):
        failures.append("Gate profile minimum Tier3 record threshold not met")
    if not bool(gate_requirements.get("meets_required_semantic_candidate_metadata_ratio", False)):
        failures.append("Gate profile semantic metadata coverage threshold not met")
    if not bool(gate_requirements.get("meets_required_relabel_status_ratio", False)):
        failures.append("Gate profile relabel coverage threshold not met")
    if not bool(gate_requirements.get("meets_gate_profile", False)):
        failures.append("Gate profile aggregate check did not pass")
    return failures
