"""Repair and legality helpers for roster-search candidates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..waha_helper import WahaHelper
from .army import Army, ArmyValidationError
from .army_attachments import AttachmentBinding
from .army_build import ArmyBlueprint, DetachmentSelection, EnhancementAssignment, RosterEntry, ValidatedMuster
from .army_muster import ArmyMusterer
from .build_capability_schema import json_safe
from .event_policy import EventPolicyDescriptor


def _clone_blueprint(blueprint: ArmyBlueprint | Mapping[str, Any]) -> ArmyBlueprint:
    return ArmyBlueprint.from_dict(ArmyBlueprint.from_dict(blueprint).to_dict())


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _force_disposition_is_mutable(event_policy: EventPolicyDescriptor | Mapping[str, Any] | None) -> bool:
    if event_policy is None:
        return True
    descriptor = (
        event_policy
        if isinstance(event_policy, EventPolicyDescriptor)
        else EventPolicyDescriptor.from_dict(dict(event_policy))
    )
    return str(descriptor.force_disposition_lock_mode or "").strip() == "flexible"


@dataclass(frozen=True)
class BlueprintRepairResult:
    blueprint: ArmyBlueprint
    repairs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint": self.blueprint.to_dict(),
            "repairs": list(self.repairs),
        }


@dataclass(frozen=True)
class BlueprintLegalityIssue:
    stage: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "stage": str(self.stage or ""),
            "message": str(self.message or ""),
        }


@dataclass
class BlueprintLegalityResult:
    blueprint: ArmyBlueprint
    repaired_blueprint: ArmyBlueprint
    repairs: tuple[str, ...] = ()
    is_valid: bool = False
    issues: tuple[BlueprintLegalityIssue, ...] = ()
    validated_muster: ValidatedMuster | None = None
    army: Army | None = None
    runtime_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint": self.blueprint.to_dict(),
            "repaired_blueprint": self.repaired_blueprint.to_dict(),
            "repairs": list(self.repairs),
            "is_valid": bool(self.is_valid),
            "issues": [issue.to_dict() for issue in self.issues],
            "validated_muster": None if self.validated_muster is None else self.validated_muster.to_dict(),
            "runtime_summary": dict(json_safe(self.runtime_summary or {})),
        }


def _synchronize_entry_enhancement_names(blueprint: ArmyBlueprint) -> None:
    names_by_entry: dict[str, list[str]] = {}
    for assignment in list(blueprint.enhancement_assignments or []):
        target_entry_id = str(assignment.target_entry_id or "")
        enhancement_name = str(assignment.enhancement_name or "").strip()
        if not target_entry_id or not enhancement_name:
            continue
        names_by_entry.setdefault(target_entry_id, []).append(enhancement_name)
    for entry in list(blueprint.unit_entries or []):
        entry.enhancement_names = list(names_by_entry.get(str(entry.entry_id or ""), []))


def _unique_detachment_ids(blueprint: ArmyBlueprint) -> list[str]:
    repairs: list[str] = []
    seen: set[str] = set()
    for index, detachment in enumerate(list(blueprint.detachments or []), start=1):
        base = str(detachment.selection_id or "").strip() or f"detachment_{index}"
        candidate = base
        suffix = 1
        while candidate in seen:
            suffix += 1
            candidate = f"{base}_{suffix}"
        if candidate != detachment.selection_id:
            detachment.selection_id = candidate
            repairs.append(f"normalized detachment selection_id to {candidate}")
        seen.add(candidate)
    return repairs


def _unique_entry_ids(blueprint: ArmyBlueprint) -> list[str]:
    repairs: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(list(blueprint.unit_entries or []), start=1):
        base = str(entry.entry_id or "").strip() or f"unit_{index}"
        candidate = base
        suffix = 1
        while candidate in seen:
            suffix += 1
            candidate = f"{base}_{suffix}"
        if candidate != entry.entry_id:
            original = str(entry.entry_id or "").strip()
            entry.entry_id = candidate
            repairs.append(f"normalized roster entry id {original or '<missing>'} -> {candidate}")
            for assignment in list(blueprint.enhancement_assignments or []):
                if assignment.target_entry_id == original:
                    assignment.target_entry_id = candidate
            for binding in list(blueprint.attachment_bindings or []):
                if binding.bodyguard_entry_id == original:
                    binding.bodyguard_entry_id = candidate
                if binding.leader_entry_id == original:
                    binding.leader_entry_id = candidate
                if binding.support_entry_id == original:
                    binding.support_entry_id = candidate
        seen.add(candidate)
    return repairs


def _unique_assignment_ids(blueprint: ArmyBlueprint) -> list[str]:
    repairs: list[str] = []
    seen: set[str] = set()
    for index, assignment in enumerate(list(blueprint.enhancement_assignments or []), start=1):
        base = str(assignment.assignment_id or "").strip() or f"enhancement_{index}"
        candidate = base
        suffix = 1
        while candidate in seen:
            suffix += 1
            candidate = f"{base}_{suffix}"
        if candidate != assignment.assignment_id:
            assignment.assignment_id = candidate
            repairs.append(f"normalized enhancement assignment id to {candidate}")
        seen.add(candidate)
    return repairs


def _unique_binding_ids(blueprint: ArmyBlueprint) -> list[str]:
    repairs: list[str] = []
    seen: set[str] = set()
    for index, binding in enumerate(list(blueprint.attachment_bindings or []), start=1):
        base = str(binding.binding_id or "").strip() or f"attachment_{index}"
        candidate = base
        suffix = 1
        while candidate in seen:
            suffix += 1
            candidate = f"{base}_{suffix}"
        if candidate != binding.binding_id:
            binding.binding_id = candidate
            repairs.append(f"normalized attachment binding id to {candidate}")
        seen.add(candidate)
    return repairs


def _repair_detachment_references(blueprint: ArmyBlueprint) -> list[str]:
    repairs: list[str] = []
    detachments = list(blueprint.detachments or [])
    detachment_ids = [str(detachment.selection_id or "") for detachment in detachments if str(detachment.selection_id or "")]
    default_detachment_id = detachment_ids[0] if detachment_ids else None
    valid_detachment_ids = set(detachment_ids)

    for entry in list(blueprint.unit_entries or []):
        detachment_id = _optional_text(entry.detachment_selection_id)
        if detachment_id and detachment_id in valid_detachment_ids:
            continue
        if detachment_id and default_detachment_id:
            entry.detachment_selection_id = default_detachment_id
            repairs.append(f"reassigned unit entry {entry.entry_id} to detachment {default_detachment_id}")
        elif detachment_id and not default_detachment_id:
            entry.detachment_selection_id = None
            repairs.append(f"cleared unknown detachment on unit entry {entry.entry_id}")

    valid_entry_ids = {str(entry.entry_id or "") for entry in list(blueprint.unit_entries or [])}
    repaired_assignments: list[EnhancementAssignment] = []
    seen_assignment_keys: set[tuple[str, str]] = set()
    for assignment in list(blueprint.enhancement_assignments or []):
        if assignment.target_entry_id not in valid_entry_ids:
            repairs.append(
                f"dropped enhancement assignment {assignment.assignment_id} for missing entry {assignment.target_entry_id}"
            )
            continue
        key = (str(assignment.target_entry_id or "").lower(), str(assignment.enhancement_name or "").lower())
        if key in seen_assignment_keys:
            repairs.append(f"dropped duplicate enhancement assignment {assignment.assignment_id}")
            continue
        seen_assignment_keys.add(key)
        target_entry = next(entry for entry in list(blueprint.unit_entries or []) if entry.entry_id == assignment.target_entry_id)
        if assignment.detachment_selection_id and assignment.detachment_selection_id not in valid_detachment_ids:
            assignment.detachment_selection_id = _optional_text(target_entry.detachment_selection_id)
            repairs.append(
                f"reassigned enhancement {assignment.assignment_id} to detachment {assignment.detachment_selection_id or '<none>'}"
            )
        repaired_assignments.append(assignment)
    blueprint.enhancement_assignments = repaired_assignments

    repaired_bindings: list[AttachmentBinding] = []
    seen_bindings: set[tuple[str, str, str]] = set()
    for binding in list(blueprint.attachment_bindings or []):
        bodyguard_entry_id = str(binding.bodyguard_entry_id or "")
        leader_entry_id = str(binding.leader_entry_id or "")
        support_entry_id = str(binding.support_entry_id or "")
        if bodyguard_entry_id not in valid_entry_ids:
            repairs.append(f"dropped attachment binding {binding.binding_id} for missing bodyguard {bodyguard_entry_id}")
            continue
        if leader_entry_id and leader_entry_id not in valid_entry_ids:
            repairs.append(f"dropped attachment binding {binding.binding_id} for missing leader {leader_entry_id}")
            continue
        if support_entry_id and support_entry_id not in valid_entry_ids:
            repairs.append(f"dropped attachment binding {binding.binding_id} for missing support {support_entry_id}")
            continue
        binding_key = (bodyguard_entry_id, leader_entry_id, support_entry_id)
        if binding_key in seen_bindings:
            repairs.append(f"dropped duplicate attachment binding {binding.binding_id}")
            continue
        seen_bindings.add(binding_key)
        repaired_bindings.append(binding)
    blueprint.attachment_bindings = repaired_bindings

    return repairs


def _repair_force_disposition(
    blueprint: ArmyBlueprint,
    *,
    event_policy: EventPolicyDescriptor | Mapping[str, Any] | None,
) -> list[str]:
    repairs: list[str] = []
    allowed: list[str] = []
    seen: set[str] = set()
    for raw_value in list(blueprint.allowed_force_dispositions or []):
        value = str(raw_value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        allowed.append(value)
    if tuple(allowed) != tuple(blueprint.allowed_force_dispositions or []):
        blueprint.allowed_force_dispositions = list(allowed)
        repairs.append("normalized allowed_force_dispositions ordering and uniqueness")

    chosen = _optional_text(blueprint.force_disposition)
    if chosen and chosen in set(allowed):
        return repairs
    if allowed and (chosen is not None or not _force_disposition_is_mutable(event_policy)):
        blueprint.force_disposition = allowed[0]
        repairs.append(f"set force_disposition to {allowed[0]}")
    elif chosen is not None and not allowed:
        blueprint.force_disposition = None
        repairs.append("cleared unsupported force_disposition without allowed choices")
    return repairs


def _repair_warlord_selection(
    blueprint: ArmyBlueprint,
    *,
    waha_helper: WahaHelper | None,
) -> list[str]:
    repairs: list[str] = []
    if waha_helper is None or not blueprint.unit_entries:
        return repairs
    try:
        army = ArmyMusterer(waha_helper).muster_blueprint(blueprint)
    except (ArmyValidationError, RuntimeError, TypeError, ValueError):
        return repairs

    candidates: list[tuple[str, str]] = []
    for unit in list(getattr(army, "units", []) or []):
        build_entry_id = str(getattr(unit, "get_build_entry_id", lambda: getattr(unit, "build_entry_id", ""))() or "").strip()
        if not build_entry_id:
            build_entry_id = str(getattr(unit, "build_entry_id", "") or "").strip()
        if not build_entry_id:
            continue
        if not bool(getattr(unit, "is_character", False)):
            continue
        cannot_be_warlord = bool(isinstance(getattr(unit, "special_rules", None), dict) and getattr(unit, "special_rules", {}).get("cannot_be_warlord"))
        if cannot_be_warlord:
            continue
        candidates.append((build_entry_id, str(getattr(unit, "name", "") or "")))
    candidates.sort(key=lambda item: (item[0], item[1]))

    if not candidates:
        return repairs

    chosen_entry_id = None
    current_warlords = [entry.entry_id for entry in list(blueprint.unit_entries or []) if bool(entry.is_warlord)]
    if len(current_warlords) == 1 and current_warlords[0] in {entry_id for entry_id, _name in candidates}:
        return repairs
    chosen_entry_id = candidates[0][0]
    for entry in list(blueprint.unit_entries or []):
        entry.is_warlord = entry.entry_id == chosen_entry_id
    repairs.append(f"selected repaired warlord {chosen_entry_id}")
    return repairs


def repair_army_blueprint(
    blueprint: ArmyBlueprint | Mapping[str, Any],
    *,
    waha_helper: WahaHelper | None = None,
    event_policy: EventPolicyDescriptor | Mapping[str, Any] | None = None,
) -> BlueprintRepairResult:
    repaired = _clone_blueprint(blueprint)
    repairs: list[str] = []
    repairs.extend(_unique_detachment_ids(repaired))
    repairs.extend(_unique_entry_ids(repaired))
    repairs.extend(_unique_assignment_ids(repaired))
    repairs.extend(_unique_binding_ids(repaired))
    repairs.extend(_repair_detachment_references(repaired))
    repairs.extend(_repair_force_disposition(repaired, event_policy=event_policy))
    repairs.extend(_repair_warlord_selection(repaired, waha_helper=waha_helper))
    _synchronize_entry_enhancement_names(repaired)
    return BlueprintRepairResult(
        blueprint=repaired,
        repairs=tuple(repairs),
    )


def validate_blueprint_runtime_legality(
    blueprint: ArmyBlueprint | Mapping[str, Any],
    *,
    waha_helper: WahaHelper,
    event_policy: EventPolicyDescriptor | Mapping[str, Any] | None = None,
) -> BlueprintLegalityResult:
    normalized_blueprint = ArmyBlueprint.from_dict(blueprint)
    repair_result = repair_army_blueprint(
        normalized_blueprint,
        waha_helper=waha_helper,
        event_policy=event_policy,
    )
    muster = ArmyMusterer(waha_helper)
    try:
        army = muster.validate_runtime_legality(repair_result.blueprint)
    except (ArmyValidationError, RuntimeError, TypeError, ValueError) as exc:
        return BlueprintLegalityResult(
            blueprint=normalized_blueprint,
            repaired_blueprint=repair_result.blueprint,
            repairs=repair_result.repairs,
            is_valid=False,
            issues=(BlueprintLegalityIssue(stage="runtime", message=str(exc)),),
        )

    warlord_entry_id = None
    if getattr(army, "warlord", None) is not None:
        get_entry_id = getattr(army.warlord, "get_build_entry_id", None)
        if callable(get_entry_id):
            warlord_entry_id = str(get_entry_id() or "").strip() or None
        else:
            warlord_entry_id = str(getattr(army.warlord, "build_entry_id", "") or "").strip() or None

    return BlueprintLegalityResult(
        blueprint=normalized_blueprint,
        repaired_blueprint=repair_result.blueprint,
        repairs=repair_result.repairs,
        is_valid=True,
        issues=(),
        validated_muster=getattr(army, "validated_muster", None),
        army=army,
        runtime_summary={
            "army_blueprint_hash": str(getattr(army, "army_blueprint_hash", "") or ""),
            "primary_detachment_type": str(getattr(army, "get_primary_detachment_type", lambda: "")() or ""),
            "detachment_types": list(getattr(army, "get_detachment_types", lambda: [])() or []),
            "unit_count": len(list(getattr(army, "units", []) or [])),
            "total_points": int(getattr(army, "get_total_points", lambda: 0)() or 0),
            "warlord_entry_id": warlord_entry_id,
            "detachment_points_spent": int(getattr(getattr(army, "validated_muster", None), "detachment_points_spent", 0) or 0),
        },
    )


__all__ = [
    "BlueprintLegalityIssue",
    "BlueprintLegalityResult",
    "BlueprintRepairResult",
    "repair_army_blueprint",
    "validate_blueprint_runtime_legality",
]
