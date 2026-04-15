"""Telemetry records for roster mustering, search, and tournament evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any, Mapping

from .army_build import ArmyBlueprint
from .build_capability_schema import canonical_json, json_safe


MUSTER_RECORD_SCHEMA_ID = "muster_record_schema:v1"
MUSTER_RECORD_VERSION = "1.0.0"
_VALID_RECORD_KINDS = {"evaluation", "search_candidate", "search_report"}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _required_text(value: object, *, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError(f"{field_name} is required.")
    return text


def _stable_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping.")
    return dict(json_safe(dict(value)))


def _stable_mapping_tuple(values: object, *, field_name: str) -> tuple[dict[str, Any], ...]:
    items: list[dict[str, Any]] = []
    for value in tuple(values or ()):
        if not isinstance(value, Mapping):
            raise TypeError(f"{field_name} entries must be mappings.")
        items.append(dict(json_safe(dict(value))))
    return tuple(items)


def _sorted_unique_texts(values: object) -> tuple[str, ...]:
    return tuple(sorted({str(item or "").strip() for item in tuple(values or ()) if str(item or "").strip()}))


def _hash_record(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:16]
    return f"muster_record:{digest}"


def _primary_detachment_type(blueprint_payload: Mapping[str, Any]) -> str | None:
    detachments = list(blueprint_payload.get("detachments", []) or [])
    if not detachments:
        return None
    first = detachments[0]
    if not isinstance(first, Mapping):
        return None
    return _optional_text(first.get("detachment_type"))


@dataclass(frozen=True)
class MusterRecord:
    record_kind: str
    army_blueprint_hash: str
    rules_bundle_id: str
    capability_schema_id: str
    build_capability_profile_id: str
    field_distribution_id: str
    event_policy_id: str
    policy_bundle_id: str
    controller_bundle_id: str | None = None
    descriptor_bundle_id: str | None = None
    faction: str | None = None
    detachment_type: str | None = None
    faction_tags: tuple[str, ...] = ()
    detachment_tags: tuple[str, ...] = ()
    utility_terms: dict[str, Any] = field(default_factory=dict)
    replay_gate_outcomes: dict[str, Any] = field(default_factory=dict)
    search_edit_sequence: tuple[dict[str, Any], ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    descriptor_provenance: dict[str, Any] = field(default_factory=dict)
    report_paths: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_tag: str = "mustering"
    generated_at_utc: str = field(default_factory=_utc_timestamp)
    muster_record_schema_id: str = MUSTER_RECORD_SCHEMA_ID
    muster_record_version: str = MUSTER_RECORD_VERSION
    record_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "muster_record_schema_id",
            _required_text(self.muster_record_schema_id, field_name="muster_record_schema_id"),
        )
        if self.muster_record_schema_id != MUSTER_RECORD_SCHEMA_ID:
            raise ValueError(
                f"Unsupported muster_record_schema_id: {self.muster_record_schema_id}."
            )
        object.__setattr__(
            self,
            "muster_record_version",
            _required_text(self.muster_record_version, field_name="muster_record_version"),
        )
        if self.muster_record_version != MUSTER_RECORD_VERSION:
            raise ValueError(
                f"Unsupported muster_record_version: {self.muster_record_version}."
            )
        record_kind = _required_text(self.record_kind, field_name="record_kind")
        if record_kind not in _VALID_RECORD_KINDS:
            allowed = ", ".join(sorted(_VALID_RECORD_KINDS))
            raise ValueError(f"record_kind must be one of: {allowed}.")
        object.__setattr__(self, "record_kind", record_kind)

        for field_name in (
            "army_blueprint_hash",
            "rules_bundle_id",
            "capability_schema_id",
            "build_capability_profile_id",
            "field_distribution_id",
            "event_policy_id",
            "policy_bundle_id",
        ):
            object.__setattr__(self, field_name, _required_text(getattr(self, field_name), field_name=field_name))

        controller_bundle_id = _optional_text(self.controller_bundle_id) or self.policy_bundle_id
        object.__setattr__(self, "controller_bundle_id", controller_bundle_id)
        object.__setattr__(self, "descriptor_bundle_id", _optional_text(self.descriptor_bundle_id))
        object.__setattr__(self, "faction", _optional_text(self.faction))
        object.__setattr__(self, "detachment_type", _optional_text(self.detachment_type))
        object.__setattr__(self, "faction_tags", _sorted_unique_texts(self.faction_tags))
        object.__setattr__(self, "detachment_tags", _sorted_unique_texts(self.detachment_tags))
        object.__setattr__(
            self,
            "utility_terms",
            _stable_mapping(self.utility_terms, field_name="utility_terms"),
        )
        object.__setattr__(
            self,
            "replay_gate_outcomes",
            _stable_mapping(self.replay_gate_outcomes, field_name="replay_gate_outcomes"),
        )
        object.__setattr__(
            self,
            "search_edit_sequence",
            _stable_mapping_tuple(self.search_edit_sequence, field_name="search_edit_sequence"),
        )
        object.__setattr__(
            self,
            "provenance",
            _stable_mapping(self.provenance, field_name="provenance"),
        )
        object.__setattr__(
            self,
            "descriptor_provenance",
            _stable_mapping(self.descriptor_provenance, field_name="descriptor_provenance"),
        )
        object.__setattr__(
            self,
            "report_paths",
            _stable_mapping(self.report_paths, field_name="report_paths"),
        )
        object.__setattr__(
            self,
            "metadata",
            _stable_mapping(self.metadata, field_name="metadata"),
        )
        object.__setattr__(self, "source_tag", _required_text(self.source_tag, field_name="source_tag"))
        object.__setattr__(
            self,
            "generated_at_utc",
            _required_text(self.generated_at_utc, field_name="generated_at_utc"),
        )
        record_id = _optional_text(self.record_id)
        if record_id is None:
            record_id = _hash_record(self._hash_payload())
        object.__setattr__(self, "record_id", record_id)

    def _hash_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload["generated_at_utc"] = ""
        payload["record_id"] = ""
        return payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "muster_record_schema_id": self.muster_record_schema_id,
            "muster_record_version": self.muster_record_version,
            "record_id": self.record_id,
            "record_kind": self.record_kind,
            "generated_at_utc": self.generated_at_utc,
            "source_tag": self.source_tag,
            "army_blueprint_hash": self.army_blueprint_hash,
            "rules_bundle_id": self.rules_bundle_id,
            "descriptor_bundle_id": self.descriptor_bundle_id,
            "capability_schema_id": self.capability_schema_id,
            "build_capability_profile_id": self.build_capability_profile_id,
            "field_distribution_id": self.field_distribution_id,
            "event_policy_id": self.event_policy_id,
            "policy_bundle_id": self.policy_bundle_id,
            "controller_bundle_id": self.controller_bundle_id,
            "faction": self.faction,
            "detachment_type": self.detachment_type,
            "faction_tags": list(self.faction_tags),
            "detachment_tags": list(self.detachment_tags),
            "utility_terms": dict(self.utility_terms),
            "replay_gate_outcomes": dict(self.replay_gate_outcomes),
            "search_edit_sequence": [dict(item) for item in self.search_edit_sequence],
            "provenance": dict(self.provenance),
            "descriptor_provenance": dict(self.descriptor_provenance),
            "report_paths": dict(self.report_paths),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: "MusterRecord | Mapping[str, Any]") -> "MusterRecord":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("MusterRecord data must be a mapping or MusterRecord.")
        return cls(
            muster_record_schema_id=data.get("muster_record_schema_id", MUSTER_RECORD_SCHEMA_ID),
            muster_record_version=data.get("muster_record_version", MUSTER_RECORD_VERSION),
            record_id=str(data.get("record_id", "") or ""),
            record_kind=data.get("record_kind", ""),
            generated_at_utc=data.get("generated_at_utc", _utc_timestamp()),
            source_tag=data.get("source_tag", "mustering"),
            army_blueprint_hash=data.get("army_blueprint_hash", ""),
            rules_bundle_id=data.get("rules_bundle_id", ""),
            descriptor_bundle_id=data.get("descriptor_bundle_id"),
            capability_schema_id=data.get("capability_schema_id", ""),
            build_capability_profile_id=data.get("build_capability_profile_id", ""),
            field_distribution_id=data.get("field_distribution_id", ""),
            event_policy_id=data.get("event_policy_id", ""),
            policy_bundle_id=data.get("policy_bundle_id", ""),
            controller_bundle_id=data.get("controller_bundle_id"),
            faction=data.get("faction"),
            detachment_type=data.get("detachment_type"),
            faction_tags=tuple(data.get("faction_tags", ()) or ()),
            detachment_tags=tuple(data.get("detachment_tags", ()) or ()),
            utility_terms=dict(data.get("utility_terms", {}) or {}),
            replay_gate_outcomes=dict(data.get("replay_gate_outcomes", {}) or {}),
            search_edit_sequence=tuple(data.get("search_edit_sequence", ()) or ()),
            provenance=dict(data.get("provenance", {}) or {}),
            descriptor_provenance=dict(data.get("descriptor_provenance", {}) or {}),
            report_paths=dict(data.get("report_paths", {}) or {}),
            metadata=dict(data.get("metadata", {}) or {}),
        )


def validate_muster_record(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        MusterRecord.from_dict(record)
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
    return errors


def muster_record_from_evaluation_summary(
    summary: Mapping[str, Any],
    *,
    roster_context: Mapping[str, Any] | None = None,
    source_tag: str = "tournament_roster_evaluation",
    provenance: Mapping[str, Any] | None = None,
) -> MusterRecord:
    summary_payload = dict(summary or {})
    roster_eval = dict(summary_payload.get("roster_evaluation", {}) or {})
    policy_bundle_lineage = dict(summary_payload.get("policy_bundle_lineage", {}) or {})
    descriptor_scope = dict(policy_bundle_lineage.get("descriptor_bundle_scope", {}) or {})
    descriptor_bundle_ids = list(descriptor_scope.get("ids", []) or [])
    context_payload = dict(roster_context or {})
    blueprint_payload = dict(context_payload.get("army_blueprint", {}) or {})
    capability_payload = dict(context_payload.get("build_capability_profile", {}) or {})
    matchup_payload = dict(context_payload.get("matchup_context", {}) or {})
    report_dir = str(summary_payload.get("report_dir", "") or "")
    report_paths = {
        "report_dir": report_dir,
        "summary": str(report_dir and f"{report_dir}/summary.json" or ""),
        "roster_context": str(roster_eval.get("roster_context_path", "") or ""),
    }
    descriptor_provenance = {
        "capability_schema_id": (
            capability_payload.get("capability_schema_id")
            or roster_eval.get("capability_schema_id")
            or ""
        ),
        "matchup_context_id": (
            matchup_payload.get("matchup_context_id")
            or roster_eval.get("matchup_context_id")
            or ""
        ),
        "field_distribution_id": (
            matchup_payload.get("field_distribution_id")
            or roster_eval.get("field_distribution_id")
            or ""
        ),
        "event_policy_id": (
            matchup_payload.get("event_policy_id")
            or roster_eval.get("event_policy_id")
            or ""
        ),
        "rules_bundle_id": (
            matchup_payload.get("rules_bundle_id")
            or roster_eval.get("rules_bundle_id")
            or ""
        ),
        "policy_bundle_id": summary_payload.get("policy_bundle_id", ""),
        "policy_bundle_lineage": policy_bundle_lineage,
    }
    return MusterRecord(
        record_kind="evaluation",
        source_tag=source_tag,
        army_blueprint_hash=str(
            roster_eval.get("army_blueprint_hash")
            or capability_payload.get("army_blueprint_hash")
            or matchup_payload.get("army_blueprint_hash")
            or ""
        ),
        rules_bundle_id=str(
            roster_eval.get("rules_bundle_id")
            or matchup_payload.get("rules_bundle_id")
            or ""
        ),
        descriptor_bundle_id=(
            summary_payload.get("descriptor_bundle_id")
            or (descriptor_bundle_ids[0] if descriptor_bundle_ids else None)
        ),
        capability_schema_id=str(
            roster_eval.get("capability_schema_id")
            or capability_payload.get("capability_schema_id")
            or ""
        ),
        build_capability_profile_id=str(
            roster_eval.get("build_capability_profile_id")
            or capability_payload.get("build_capability_profile_id")
            or ""
        ),
        field_distribution_id=str(
            roster_eval.get("field_distribution_id")
            or matchup_payload.get("field_distribution_id")
            or ""
        ),
        event_policy_id=str(
            roster_eval.get("event_policy_id")
            or matchup_payload.get("event_policy_id")
            or ""
        ),
        policy_bundle_id=str(summary_payload.get("policy_bundle_id", "") or ""),
        controller_bundle_id=str(summary_payload.get("policy_bundle_id", "") or ""),
        faction=blueprint_payload.get("faction"),
        detachment_type=(
            matchup_payload.get("primary_detachment_type")
            or _primary_detachment_type(blueprint_payload)
        ),
        faction_tags=tuple([blueprint_payload.get("faction")] if blueprint_payload.get("faction") else ()),
        detachment_tags=tuple(
            [matchup_payload.get("primary_detachment_type") or _primary_detachment_type(blueprint_payload)]
        ),
        utility_terms=dict(summary_payload.get("utility_decomposition", {}) or {}),
        replay_gate_outcomes={
            "success": bool(summary_payload.get("success", False)),
            "self_play": dict(summary_payload.get("self_play", {}) or {}),
            "replay_audit": dict(summary_payload.get("replay_audit", {}) or {}),
            "manifest_gate": dict(summary_payload.get("manifest_gate", {}) or {}),
            "failure_reasons": list(summary_payload.get("failure_reasons", []) or []),
        },
        provenance={
            **dict(provenance or {}),
            "evaluation_run_id": str(summary_payload.get("evaluation_run_id", "") or ""),
            "evaluation_mode": str(summary_payload.get("evaluation_mode", "") or ""),
            "policy_bundle_source": str(summary_payload.get("policy_bundle_source", "") or ""),
        },
        descriptor_provenance=descriptor_provenance,
        report_paths=report_paths,
        metadata={
            "candidate_roster_label": str(summary_payload.get("candidate_roster_label", "") or ""),
            "opponent_roster_label": str(summary_payload.get("opponent_roster_label", "") or ""),
        },
    )


def muster_records_from_search_report(
    search_report: Mapping[str, Any],
    *,
    rules_bundle_id: str,
    capability_schema_id: str,
    field_distribution_id: str,
    event_policy_id: str,
    policy_bundle_id: str,
    source_tag: str = "roster_search",
    descriptor_bundle_id: str | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> tuple[MusterRecord, ...]:
    payload = dict(search_report or {})
    records: list[MusterRecord] = []
    for candidate in list(payload.get("top_candidates", []) or []):
        candidate_payload = dict(candidate or {})
        blueprint = ArmyBlueprint.from_dict(candidate_payload.get("army_blueprint", {}))
        evaluation_summary = dict(candidate_payload.get("evaluation_summary", {}) or {})
        records.append(
            MusterRecord(
                record_kind="search_candidate",
                source_tag=source_tag,
                army_blueprint_hash=str(candidate_payload.get("army_blueprint_hash", "") or ""),
                rules_bundle_id=rules_bundle_id,
                descriptor_bundle_id=descriptor_bundle_id,
                capability_schema_id=str(
                    evaluation_summary.get("capability_schema_id")
                    or capability_schema_id
                ),
                build_capability_profile_id=str(
                    evaluation_summary.get("build_capability_profile_id")
                    or "build_capability_profile:unrecorded"
                ),
                field_distribution_id=field_distribution_id,
                event_policy_id=event_policy_id,
                policy_bundle_id=policy_bundle_id,
                controller_bundle_id=policy_bundle_id,
                faction=blueprint.faction,
                detachment_type=blueprint.primary_detachment_type,
                faction_tags=(blueprint.faction,),
                detachment_tags=tuple([blueprint.primary_detachment_type] if blueprint.primary_detachment_type else ()),
                utility_terms=dict(candidate_payload.get("utility_decomposition", {}) or {}),
                replay_gate_outcomes={
                    "validation_summary": dict(candidate_payload.get("validation_summary", {}) or {}),
                },
                search_edit_sequence=tuple(candidate_payload.get("edit_trace", ()) or ()),
                provenance={
                    **dict(provenance or {}),
                    "strategy": str(payload.get("strategy", "") or ""),
                    "random_seed": payload.get("random_seed"),
                    "candidate_id": str(candidate_payload.get("candidate_id", "") or ""),
                },
                descriptor_provenance={
                    "capability_schema_id": str(
                        evaluation_summary.get("capability_schema_id")
                        or capability_schema_id
                    ),
                    "build_capability_profile_id": str(
                        evaluation_summary.get("build_capability_profile_id")
                        or "build_capability_profile:unrecorded"
                    ),
                },
                metadata={
                    "score": float(candidate_payload.get("score", 0.0) or 0.0),
                },
            )
        )
    return tuple(records)


__all__ = [
    "MUSTER_RECORD_SCHEMA_ID",
    "MUSTER_RECORD_VERSION",
    "MusterRecord",
    "muster_record_from_evaluation_summary",
    "muster_records_from_search_report",
    "validate_muster_record",
]
