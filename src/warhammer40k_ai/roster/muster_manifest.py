"""Corpus manifests for mustering telemetry records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .build_capability_schema import json_safe
from .muster_record import (
    MUSTER_RECORD_SCHEMA_ID,
    MUSTER_RECORD_VERSION,
    MusterRecord,
    validate_muster_record,
)


MUSTERING_MANIFEST_SCHEMA_ID = "mustering_manifest_schema:v1"
MUSTERING_MANIFEST_VERSION = "1.0.0"
_RATIO_PRECISION = 6


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _round_float(value: float) -> float:
    return float(round(float(value), _RATIO_PRECISION))


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _required_text(value: object, *, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError(f"{field_name} is required.")
    return text


def _normalize_str_tuple(values: Iterable[Any] | None) -> tuple[str, ...]:
    return tuple(sorted({str(item or "").strip() for item in list(values or []) if str(item or "").strip()}))


def _normalize_record_id_tuple(values: Iterable[Any] | None) -> tuple[str, ...]:
    return tuple(str(item or "").strip() for item in list(values or []) if str(item or "").strip())


@dataclass(frozen=True)
class MusteringManifestSlice:
    rules_bundle_ids: tuple[str, ...] = ()
    capability_schema_ids: tuple[str, ...] = ()
    field_distribution_ids: tuple[str, ...] = ()
    event_policy_ids: tuple[str, ...] = ()
    policy_bundle_ids: tuple[str, ...] = ()
    controller_bundle_ids: tuple[str, ...] = ()
    factions: tuple[str, ...] = ()
    detachment_types: tuple[str, ...] = ()
    faction_tags: tuple[str, ...] = ()
    detachment_tags: tuple[str, ...] = ()
    record_kinds: tuple[str, ...] = ()
    army_blueprint_hashes: tuple[str, ...] = ()
    build_capability_profile_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            object.__setattr__(self, field_name, _normalize_str_tuple(getattr(self, field_name)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_bundle_ids": list(self.rules_bundle_ids),
            "capability_schema_ids": list(self.capability_schema_ids),
            "field_distribution_ids": list(self.field_distribution_ids),
            "event_policy_ids": list(self.event_policy_ids),
            "policy_bundle_ids": list(self.policy_bundle_ids),
            "controller_bundle_ids": list(self.controller_bundle_ids),
            "factions": list(self.factions),
            "detachment_types": list(self.detachment_types),
            "faction_tags": list(self.faction_tags),
            "detachment_tags": list(self.detachment_tags),
            "record_kinds": list(self.record_kinds),
            "army_blueprint_hashes": list(self.army_blueprint_hashes),
            "build_capability_profile_ids": list(self.build_capability_profile_ids),
        }

    def is_empty(self) -> bool:
        return not any(tuple(getattr(self, field_name) for field_name in self.__dataclass_fields__))


@dataclass(frozen=True)
class MusteringManifest:
    corpus_id: str
    source_tag: str
    total_records: int
    record_ids: tuple[str, ...]
    record_kind_counts: dict[str, int]
    rules_bundle_ids: tuple[str, ...]
    capability_schema_ids: tuple[str, ...]
    build_capability_profile_ids: tuple[str, ...]
    field_distribution_ids: tuple[str, ...]
    event_policy_ids: tuple[str, ...]
    policy_bundle_ids: tuple[str, ...]
    controller_bundle_ids: tuple[str, ...]
    army_blueprint_hashes: tuple[str, ...]
    factions: tuple[str, ...]
    detachment_types: tuple[str, ...]
    faction_tags: tuple[str, ...]
    detachment_tags: tuple[str, ...]
    utility_term_summary: dict[str, Any]
    outcome_summary: dict[str, Any]
    search_summary: dict[str, Any]
    provenance_summary: dict[str, Any]
    slice_filters: MusteringManifestSlice
    generated_at_utc: str = field(default_factory=_utc_timestamp)
    mustering_manifest_schema_id: str = MUSTERING_MANIFEST_SCHEMA_ID
    manifest_version: str = MUSTERING_MANIFEST_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mustering_manifest_schema_id",
            _required_text(
                self.mustering_manifest_schema_id,
                field_name="mustering_manifest_schema_id",
            ),
        )
        if self.mustering_manifest_schema_id != MUSTERING_MANIFEST_SCHEMA_ID:
            raise ValueError(
                f"Unsupported mustering_manifest_schema_id: {self.mustering_manifest_schema_id}."
            )
        object.__setattr__(
            self,
            "manifest_version",
            _required_text(self.manifest_version, field_name="manifest_version"),
        )
        if self.manifest_version != MUSTERING_MANIFEST_VERSION:
            raise ValueError(f"Unsupported manifest_version: {self.manifest_version}.")
        object.__setattr__(self, "corpus_id", _required_text(self.corpus_id, field_name="corpus_id"))
        object.__setattr__(self, "source_tag", _required_text(self.source_tag, field_name="source_tag"))
        object.__setattr__(self, "total_records", int(self.total_records))
        if self.total_records < 0:
            raise ValueError("total_records cannot be negative.")
        object.__setattr__(self, "record_ids", _normalize_record_id_tuple(self.record_ids))
        for field_name in (
            "rules_bundle_ids",
            "capability_schema_ids",
            "build_capability_profile_ids",
            "field_distribution_ids",
            "event_policy_ids",
            "policy_bundle_ids",
            "controller_bundle_ids",
            "army_blueprint_hashes",
            "factions",
            "detachment_types",
            "faction_tags",
            "detachment_tags",
        ):
            object.__setattr__(self, field_name, _normalize_str_tuple(getattr(self, field_name)))
        object.__setattr__(
            self,
            "record_kind_counts",
            {str(key): int(value) for key, value in sorted(dict(self.record_kind_counts or {}).items())},
        )
        for field_name in (
            "utility_term_summary",
            "outcome_summary",
            "search_summary",
            "provenance_summary",
        ):
            object.__setattr__(self, field_name, dict(json_safe(dict(getattr(self, field_name) or {}))))
        if isinstance(self.slice_filters, MusteringManifestSlice):
            normalized_slice = self.slice_filters
        elif isinstance(self.slice_filters, Mapping):
            normalized_slice = MusteringManifestSlice(**dict(self.slice_filters))
        else:
            raise TypeError("slice_filters must be a MusteringManifestSlice or mapping.")
        object.__setattr__(self, "slice_filters", normalized_slice)
        object.__setattr__(
            self,
            "generated_at_utc",
            _required_text(self.generated_at_utc, field_name="generated_at_utc"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mustering_manifest_schema_id": self.mustering_manifest_schema_id,
            "manifest_version": self.manifest_version,
            "generated_at_utc": self.generated_at_utc,
            "corpus_id": self.corpus_id,
            "source_tag": self.source_tag,
            "total_records": self.total_records,
            "record_ids": list(self.record_ids),
            "record_kind_counts": dict(self.record_kind_counts),
            "rules_bundle_ids": list(self.rules_bundle_ids),
            "capability_schema_ids": list(self.capability_schema_ids),
            "build_capability_profile_ids": list(self.build_capability_profile_ids),
            "field_distribution_ids": list(self.field_distribution_ids),
            "event_policy_ids": list(self.event_policy_ids),
            "policy_bundle_ids": list(self.policy_bundle_ids),
            "controller_bundle_ids": list(self.controller_bundle_ids),
            "army_blueprint_hashes": list(self.army_blueprint_hashes),
            "factions": list(self.factions),
            "detachment_types": list(self.detachment_types),
            "faction_tags": list(self.faction_tags),
            "detachment_tags": list(self.detachment_tags),
            "utility_term_summary": dict(self.utility_term_summary),
            "outcome_summary": dict(self.outcome_summary),
            "search_summary": dict(self.search_summary),
            "provenance_summary": dict(self.provenance_summary),
            "slice_filters": self.slice_filters.to_dict(),
            "record_schema": {
                "muster_record_schema_id": MUSTER_RECORD_SCHEMA_ID,
                "muster_record_version": MUSTER_RECORD_VERSION,
            },
        }


def build_mustering_manifest_slice(
    *,
    rules_bundle_ids: Iterable[str] | None = None,
    capability_schema_ids: Iterable[str] | None = None,
    field_distribution_ids: Iterable[str] | None = None,
    event_policy_ids: Iterable[str] | None = None,
    policy_bundle_ids: Iterable[str] | None = None,
    controller_bundle_ids: Iterable[str] | None = None,
    factions: Iterable[str] | None = None,
    detachment_types: Iterable[str] | None = None,
    faction_tags: Iterable[str] | None = None,
    detachment_tags: Iterable[str] | None = None,
    record_kinds: Iterable[str] | None = None,
    army_blueprint_hashes: Iterable[str] | None = None,
    build_capability_profile_ids: Iterable[str] | None = None,
) -> MusteringManifestSlice:
    return MusteringManifestSlice(
        rules_bundle_ids=_normalize_str_tuple(rules_bundle_ids),
        capability_schema_ids=_normalize_str_tuple(capability_schema_ids),
        field_distribution_ids=_normalize_str_tuple(field_distribution_ids),
        event_policy_ids=_normalize_str_tuple(event_policy_ids),
        policy_bundle_ids=_normalize_str_tuple(policy_bundle_ids),
        controller_bundle_ids=_normalize_str_tuple(controller_bundle_ids),
        factions=_normalize_str_tuple(factions),
        detachment_types=_normalize_str_tuple(detachment_types),
        faction_tags=_normalize_str_tuple(faction_tags),
        detachment_tags=_normalize_str_tuple(detachment_tags),
        record_kinds=_normalize_str_tuple(record_kinds),
        army_blueprint_hashes=_normalize_str_tuple(army_blueprint_hashes),
        build_capability_profile_ids=_normalize_str_tuple(build_capability_profile_ids),
    )


def _record_matches_slice(record: MusterRecord, slice_filters: MusteringManifestSlice) -> bool:
    if slice_filters.is_empty():
        return True
    checks = (
        (slice_filters.rules_bundle_ids, record.rules_bundle_id),
        (slice_filters.capability_schema_ids, record.capability_schema_id),
        (slice_filters.field_distribution_ids, record.field_distribution_id),
        (slice_filters.event_policy_ids, record.event_policy_id),
        (slice_filters.policy_bundle_ids, record.policy_bundle_id),
        (slice_filters.controller_bundle_ids, record.controller_bundle_id),
        (slice_filters.factions, record.faction),
        (slice_filters.detachment_types, record.detachment_type),
        (slice_filters.record_kinds, record.record_kind),
        (slice_filters.army_blueprint_hashes, record.army_blueprint_hash),
        (slice_filters.build_capability_profile_ids, record.build_capability_profile_id),
    )
    for requested, value in checks:
        if requested and str(value or "") not in set(requested):
            return False
    if slice_filters.faction_tags and set(record.faction_tags).isdisjoint(set(slice_filters.faction_tags)):
        return False
    if slice_filters.detachment_tags and set(record.detachment_tags).isdisjoint(set(slice_filters.detachment_tags)):
        return False
    return True


def filter_muster_records(
    records: Iterable[MusterRecord | Mapping[str, Any]],
    *,
    slice_filters: MusteringManifestSlice | None = None,
    **slice_kwargs: Any,
) -> tuple[list[MusterRecord], MusteringManifestSlice]:
    normalized_slice = slice_filters or build_mustering_manifest_slice(**slice_kwargs)
    normalized_records = [MusterRecord.from_dict(record) for record in list(records or [])]
    if normalized_slice.is_empty():
        return normalized_records, normalized_slice
    return [
        record for record in normalized_records if _record_matches_slice(record, normalized_slice)
    ], normalized_slice


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in list(values or []):
        text = str(value or "").strip()
        if not text:
            continue
        counts[text] = int(counts.get(text, 0) or 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _unique(records: list[MusterRecord], attr: str) -> tuple[str, ...]:
    return _normalize_str_tuple(getattr(record, attr) for record in records)


def _flatten_numeric_terms(value: Any, *, prefix: str = "") -> dict[str, float]:
    if isinstance(value, bool):
        return {}
    if isinstance(value, (int, float)):
        return {prefix: float(value)} if prefix else {}
    if isinstance(value, Mapping):
        flattened: dict[str, float] = {}
        for key, inner in dict(value).items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_numeric_terms(inner, prefix=child_prefix))
        return flattened
    return {}


def _utility_summary(records: list[MusterRecord]) -> dict[str, Any]:
    values: dict[str, list[float]] = {}
    for record in records:
        for key, value in _flatten_numeric_terms(record.utility_terms).items():
            values.setdefault(key, []).append(float(value))
    summary: dict[str, Any] = {}
    for key in sorted(values):
        series = values[key]
        if not series:
            continue
        summary[key] = {
            "count": len(series),
            "min": _round_float(min(series)),
            "max": _round_float(max(series)),
            "mean": _round_float(sum(series) / len(series)),
        }
    return summary


def _outcome_summary(records: list[MusterRecord]) -> dict[str, Any]:
    success = 0
    replay_passed = 0
    gate_passed = 0
    failure_reasons: list[str] = []
    for record in records:
        outcomes = dict(record.replay_gate_outcomes or {})
        if bool(outcomes.get("success", False)):
            success += 1
        replay = dict(outcomes.get("replay_audit", {}) or {})
        gate = dict(outcomes.get("manifest_gate", {}) or {})
        if bool(outcomes.get("replay_passed", replay.get("passed", False))):
            replay_passed += 1
        if bool(outcomes.get("gate_passed", gate.get("passed", False))):
            gate_passed += 1
        failure_reasons.extend(str(item) for item in list(outcomes.get("failure_reasons", []) or []) if str(item))
    total = len(records)
    return {
        "success_count": success,
        "success_ratio": _round_float(success / total) if total else 0.0,
        "replay_passed_count": replay_passed,
        "replay_passed_ratio": _round_float(replay_passed / total) if total else 0.0,
        "gate_passed_count": gate_passed,
        "gate_passed_ratio": _round_float(gate_passed / total) if total else 0.0,
        "failure_reason_counts": _counts(failure_reasons),
    }


def _search_summary(records: list[MusterRecord]) -> dict[str, Any]:
    edit_action_ids: list[str] = []
    edit_action_types: list[str] = []
    total_edits = 0
    for record in records:
        for action in record.search_edit_sequence:
            total_edits += 1
            action_id = str(action.get("action_id", "") or "")
            action_type = str(action.get("action_type", "") or action.get("kind", "") or "")
            if action_id:
                edit_action_ids.append(action_id)
            if action_type:
                edit_action_types.append(action_type)
    return {
        "records_with_search_edits": sum(1 for record in records if record.search_edit_sequence),
        "total_search_edit_count": total_edits,
        "edit_action_id_counts": _counts(edit_action_ids),
        "edit_action_type_counts": _counts(edit_action_types),
    }


def _provenance_summary(records: list[MusterRecord]) -> dict[str, Any]:
    git_commits: list[str] = []
    evaluation_modes: list[str] = []
    report_dirs: list[str] = []
    for record in records:
        provenance = dict(record.provenance or {})
        git_commit = str(provenance.get("git_commit", "") or provenance.get("created_from_commit", "") or "")
        if git_commit:
            git_commits.append(git_commit)
        mode = str(provenance.get("evaluation_mode", "") or "")
        if mode:
            evaluation_modes.append(mode)
        report_dir = str(record.report_paths.get("report_dir", "") or "")
        if report_dir:
            report_dirs.append(report_dir)
    return {
        "git_commits": sorted(set(git_commits)),
        "evaluation_modes": sorted(set(evaluation_modes)),
        "report_dirs": sorted(set(report_dirs)),
    }


def build_mustering_manifest(
    records: Iterable[MusterRecord | Mapping[str, Any]],
    *,
    corpus_id: str,
    source_tag: str,
    slice_filters: MusteringManifestSlice | None = None,
    **slice_kwargs: Any,
) -> MusteringManifest:
    filtered_records, normalized_slice = filter_muster_records(
        records,
        slice_filters=slice_filters,
        **slice_kwargs,
    )
    record_kinds = _counts(record.record_kind for record in filtered_records)
    all_faction_tags: list[str] = []
    all_detachment_tags: list[str] = []
    for record in filtered_records:
        all_faction_tags.extend(record.faction_tags)
        all_detachment_tags.extend(record.detachment_tags)
    return MusteringManifest(
        mustering_manifest_schema_id=MUSTERING_MANIFEST_SCHEMA_ID,
        manifest_version=MUSTERING_MANIFEST_VERSION,
        corpus_id=corpus_id,
        source_tag=source_tag,
        total_records=len(filtered_records),
        record_ids=tuple(record.record_id for record in filtered_records),
        record_kind_counts=record_kinds,
        rules_bundle_ids=_unique(filtered_records, "rules_bundle_id"),
        capability_schema_ids=_unique(filtered_records, "capability_schema_id"),
        build_capability_profile_ids=_unique(filtered_records, "build_capability_profile_id"),
        field_distribution_ids=_unique(filtered_records, "field_distribution_id"),
        event_policy_ids=_unique(filtered_records, "event_policy_id"),
        policy_bundle_ids=_unique(filtered_records, "policy_bundle_id"),
        controller_bundle_ids=_unique(filtered_records, "controller_bundle_id"),
        army_blueprint_hashes=_unique(filtered_records, "army_blueprint_hash"),
        factions=_unique(filtered_records, "faction"),
        detachment_types=_unique(filtered_records, "detachment_type"),
        faction_tags=_normalize_str_tuple(all_faction_tags),
        detachment_tags=_normalize_str_tuple(all_detachment_tags),
        utility_term_summary=_utility_summary(filtered_records),
        outcome_summary=_outcome_summary(filtered_records),
        search_summary=_search_summary(filtered_records),
        provenance_summary=_provenance_summary(filtered_records),
        slice_filters=normalized_slice,
    )


def validate_mustering_manifest(manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    payload = dict(manifest or {})
    if payload.get("mustering_manifest_schema_id") != MUSTERING_MANIFEST_SCHEMA_ID:
        errors.append("mustering_manifest_schema_id must be mustering_manifest_schema:v1")
    if payload.get("manifest_version") != MUSTERING_MANIFEST_VERSION:
        errors.append("manifest_version must be 1.0.0")
    required_keys = {
        "corpus_id",
        "source_tag",
        "total_records",
        "record_ids",
        "record_kind_counts",
        "rules_bundle_ids",
        "capability_schema_ids",
        "build_capability_profile_ids",
        "field_distribution_ids",
        "event_policy_ids",
        "policy_bundle_ids",
        "controller_bundle_ids",
        "army_blueprint_hashes",
        "factions",
        "detachment_types",
        "faction_tags",
        "detachment_tags",
        "utility_term_summary",
        "outcome_summary",
        "search_summary",
        "provenance_summary",
        "slice_filters",
        "record_schema",
    }
    missing = sorted(key for key in required_keys if key not in payload)
    if missing:
        errors.append(f"manifest missing required keys: {', '.join(missing)}")
    total_records = payload.get("total_records")
    if not isinstance(total_records, int) or total_records < 0:
        errors.append("total_records must be a non-negative integer")
    record_ids = payload.get("record_ids", [])
    if not isinstance(record_ids, list):
        errors.append("record_ids must be a JSON array")
    if isinstance(total_records, int) and isinstance(record_ids, list) and len(record_ids) != total_records:
        errors.append("record_ids length must match total_records")
    record_schema = dict(payload.get("record_schema", {}) or {})
    if record_schema.get("muster_record_schema_id") != MUSTER_RECORD_SCHEMA_ID:
        errors.append("record_schema.muster_record_schema_id must be muster_record_schema:v1")
    if record_schema.get("muster_record_version") != MUSTER_RECORD_VERSION:
        errors.append("record_schema.muster_record_version must be 1.0.0")
    slice_filters = payload.get("slice_filters")
    if not isinstance(slice_filters, dict):
        errors.append("slice_filters must be an object")
    return errors


def extract_muster_records(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(item or {}) for item in document]
    if isinstance(document, dict) and isinstance(document.get("records"), list):
        return [dict(item or {}) for item in list(document.get("records", []) or [])]
    if isinstance(document, dict) and "muster_record_schema_id" in document:
        return [dict(document)]
    raise ValueError("Input must be a MusterRecord object, a JSON array, or an object with records[].")


def load_muster_records(path: str | Path) -> list[MusterRecord]:
    input_path = Path(path).expanduser().resolve()
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    records = extract_muster_records(payload)
    errors: list[str] = []
    normalized: list[MusterRecord] = []
    for index, record in enumerate(records):
        record_errors = validate_muster_record(record)
        if record_errors:
            errors.extend(f"record[{index}]: {error}" for error in record_errors)
            continue
        normalized.append(MusterRecord.from_dict(record))
    if errors:
        raise ValueError("; ".join(errors))
    return normalized


def save_mustering_manifest(manifest: Mapping[str, Any], path: str | Path) -> None:
    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(json_safe(dict(manifest)), indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )


__all__ = [
    "MUSTERING_MANIFEST_SCHEMA_ID",
    "MUSTERING_MANIFEST_VERSION",
    "MusteringManifest",
    "MusteringManifestSlice",
    "build_mustering_manifest",
    "build_mustering_manifest_slice",
    "extract_muster_records",
    "filter_muster_records",
    "load_muster_records",
    "save_mustering_manifest",
    "validate_mustering_manifest",
]
