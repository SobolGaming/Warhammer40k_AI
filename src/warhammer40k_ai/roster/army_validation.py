"""Validation and normalization helpers for build-side army mustering."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .army import ArmyValidationError, _assert_supported_faction, get_faction_id_from_name
from .army_attachments import AttachmentBinding
from .army_build import (
    ArmyBlueprint,
    DetachmentSelection,
    EnhancementAssignment,
    RosterEntry,
    ValidatedMuster,
)


def _to_mapping(value: object) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    return None


def _normalize_detachments(values: object) -> list[DetachmentSelection]:
    selections: list[DetachmentSelection] = []
    for index, value in enumerate(list(values or []), start=1):
        data = _to_mapping(value)
        if data is not None and not str(data.get("selection_id", "") or "").strip():
            data = dict(data)
            data["selection_id"] = f"detachment_{index}"
        selections.append(DetachmentSelection.from_dict(data or value))
    return selections


def _normalize_roster_entries(values: object) -> list[RosterEntry]:
    entries: list[RosterEntry] = []
    for index, value in enumerate(list(values or []), start=1):
        if isinstance(value, RosterEntry):
            entries.append(value)
            continue
        data = _to_mapping(value)
        if data is None:
            data = {
                "entry_id": str(getattr(value, "entry_id", "") or f"unit_{index}"),
                "name": getattr(value, "name", ""),
                "count": getattr(value, "count", 1),
                "detachment_selection_id": getattr(value, "detachment_selection_id", None),
                "wargear": list(getattr(value, "wargear", []) or []),
                "enhancements": list(getattr(value, "enhancements", []) or []),
                "enhancement_names": list(getattr(value, "enhancement_names", []) or []),
                "is_warlord": bool(getattr(value, "is_warlord", False)),
                "metadata": dict(getattr(value, "metadata", {}) or {}),
            }
        else:
            data = dict(data)
        if not str(data.get("entry_id", "") or "").strip():
            data["entry_id"] = f"unit_{index}"
        entries.append(RosterEntry.from_dict(data))
    return entries


def _normalize_enhancement_assignments(values: object) -> list[EnhancementAssignment]:
    assignments: list[EnhancementAssignment] = []
    for index, value in enumerate(list(values or []), start=1):
        data = _to_mapping(value)
        if data is not None and not str(data.get("assignment_id", "") or "").strip():
            data = dict(data)
            data["assignment_id"] = f"enhancement_{index}"
        assignments.append(EnhancementAssignment.from_dict(data or value))
    return assignments


def _normalize_attachment_bindings(values: object) -> list[AttachmentBinding]:
    bindings: list[AttachmentBinding] = []
    for index, value in enumerate(list(values or []), start=1):
        data = _to_mapping(value)
        if data is not None and not str(data.get("binding_id", "") or "").strip():
            data = dict(data)
            data["binding_id"] = f"attachment_{index}"
        bindings.append(AttachmentBinding.from_dict(data or value))
    return bindings


def build_army_blueprint_from_request(
    request: object,
) -> tuple[ArmyBlueprint, bool]:
    """Normalize raw muster input into a build-side ArmyBlueprint."""

    if isinstance(request, ArmyBlueprint):
        return request, False
    if request is None:
        raise ArmyValidationError("Army mustering request is missing.")

    data = _to_mapping(request)
    get_value = data.get if data is not None else lambda name, default=None: getattr(request, name, default)

    faction = str(get_value("faction", "") or "").strip()
    if not faction:
        raise ArmyValidationError("Army mustering request is missing a faction.")

    raw_detachments = get_value("detachments", [])
    raw_units = get_value("units", get_value("unit_entries", []))
    raw_assignments = get_value("enhancement_assignments", [])
    raw_bindings = get_value("attachment_bindings", [])

    detachments = _normalize_detachments(raw_detachments)
    if not detachments:
        raise ArmyValidationError("Army mustering request must define at least one detachment.")

    entries = _normalize_roster_entries(raw_units)
    assignments = _normalize_enhancement_assignments(raw_assignments)
    seen_assignments = {
        (
            assignment.target_entry_id.lower(),
            assignment.enhancement_name.lower(),
        )
        for assignment in list(assignments or [])
    }
    for entry in list(entries or []):
        for index, enhancement_name in enumerate(list(entry.enhancement_names or []), start=1):
            key = (entry.entry_id.lower(), enhancement_name.lower())
            if key in seen_assignments:
                continue
            seen_assignments.add(key)
            assignments.append(
                EnhancementAssignment(
                    assignment_id=f"{entry.entry_id}_enhancement_{index}",
                    enhancement_name=enhancement_name,
                    target_entry_id=entry.entry_id,
                    detachment_selection_id=entry.detachment_selection_id,
                    metadata={"adapter_source": "legacy_unit_selection"},
                )
            )

    blueprint = ArmyBlueprint(
        faction=faction,
        points_limit=get_value("points_limit", 2000),
        battle_size=get_value("battle_size"),
        detachments=detachments,
        detachment_points_budget=get_value("detachment_points_budget"),
        unit_entries=entries,
        enhancement_assignments=assignments,
        attachment_bindings=_normalize_attachment_bindings(raw_bindings),
        force_disposition=get_value("force_disposition"),
        allowed_force_dispositions=list(get_value("allowed_force_dispositions", []) or []),
        metadata=dict(get_value("metadata", {}) or {}),
    )
    return blueprint, False


def validate_detachment_points_budget(blueprint: ArmyBlueprint) -> int:
    """Return the detachment points spent, raising if the budget is exceeded."""

    spent = sum(
        int(getattr(detachment, "detachment_points_cost", 0) or 0)
        for detachment in list(blueprint.detachments or [])
    )
    budget = blueprint.detachment_points_budget
    if budget is not None and spent > budget:
        raise ArmyValidationError(
            f"Detachment-point budget exceeded: spent {spent}, budget {budget}."
        )
    return spent


def validate_army_blueprint(blueprint: ArmyBlueprint) -> tuple[str, int]:
    """Validate the normalized blueprint and return faction id plus detachment spend."""

    faction_id = get_faction_id_from_name(blueprint.faction)
    _assert_supported_faction(blueprint.faction, faction_id)

    detachment_ids = {
        str(detachment.selection_id or "").strip()
        for detachment in list(blueprint.detachments or [])
        if str(detachment.selection_id or "").strip()
    }
    entry_ids = {
        str(entry.entry_id or "").strip()
        for entry in list(blueprint.unit_entries or [])
        if str(entry.entry_id or "").strip()
    }

    for entry in list(blueprint.unit_entries or []):
        detachment_id = str(entry.detachment_selection_id or "").strip()
        if detachment_id and detachment_id not in detachment_ids:
            raise ArmyValidationError(
                f"Roster entry '{entry.entry_id}' references unknown detachment '{detachment_id}'."
            )

    for assignment in list(blueprint.enhancement_assignments or []):
        if assignment.target_entry_id not in entry_ids:
            raise ArmyValidationError(
                f"Enhancement assignment '{assignment.assignment_id}' references unknown unit entry "
                f"'{assignment.target_entry_id}'."
            )
        detachment_id = str(assignment.detachment_selection_id or "").strip()
        if detachment_id and detachment_id not in detachment_ids:
            raise ArmyValidationError(
                f"Enhancement assignment '{assignment.assignment_id}' references unknown detachment "
                f"'{detachment_id}'."
            )

    for binding in list(blueprint.attachment_bindings or []):
        if binding.bodyguard_entry_id not in entry_ids:
            raise ArmyValidationError(
                f"Attachment binding '{binding.binding_id}' references unknown bodyguard entry "
                f"'{binding.bodyguard_entry_id}'."
            )
        if binding.leader_entry_id and binding.leader_entry_id not in entry_ids:
            raise ArmyValidationError(
                f"Attachment binding '{binding.binding_id}' references unknown leader entry "
                f"'{binding.leader_entry_id}'."
            )
        if binding.support_entry_id and binding.support_entry_id not in entry_ids:
            raise ArmyValidationError(
                f"Attachment binding '{binding.binding_id}' references unknown support entry "
                f"'{binding.support_entry_id}'."
            )

    if (
        blueprint.force_disposition is not None
        and blueprint.allowed_force_dispositions
        and blueprint.force_disposition not in set(blueprint.allowed_force_dispositions)
    ):
        raise ArmyValidationError(
            "Chosen force_disposition must be present in allowed_force_dispositions."
        )

    spent = validate_detachment_points_budget(blueprint)
    return str(faction_id or ""), spent


def validate_army_muster_request(request: object) -> ValidatedMuster:
    """Normalize and validate a muster request into a ValidatedMuster."""

    blueprint, legacy_adapter_used = build_army_blueprint_from_request(request)
    faction_id, spent = validate_army_blueprint(blueprint)
    warnings: list[str] = []
    if legacy_adapter_used:
        warnings.append("legacy_single_detachment_adapter")
    return ValidatedMuster(
        blueprint=blueprint,
        faction_id=faction_id,
        detachment_points_spent=spent,
        legacy_single_detachment_adapter_used=legacy_adapter_used,
        warnings=warnings,
    )
