from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..roster.army_attachments import AttachmentBinding
from ..roster.army_build import (
    ArmyBlueprint,
    DetachmentSelection,
    EnhancementAssignment,
    RosterEntry,
    ValidatedMuster,
)
from ..roster.army_runtime import DetachmentInstance
from ..utility.entity_ids import get_entity_id
from .descriptor_bundle import CompiledDescriptor, descriptor_id, iter_players, json_safe, safe_int


def _detachment_selections(values: object) -> list[DetachmentSelection]:
    selections: list[DetachmentSelection] = []
    for index, value in enumerate(list(values or []), start=1):
        if isinstance(value, DetachmentSelection):
            selections.append(value)
            continue
        if isinstance(value, DetachmentInstance):
            selections.append(
                DetachmentSelection(
                    selection_id=str(value.selection_id or value.instance_id or f"detachment_{index}"),
                    detachment_type=str(value.detachment_type or ""),
                    detachment_points_cost=int(value.detachment_points_cost or 0),
                    label=value.label,
                    metadata=dict(value.metadata or {}),
                )
            )
            continue
        if isinstance(value, Mapping):
            mapping = dict(value)
            if not str(mapping.get("selection_id", "") or "").strip():
                mapping["selection_id"] = str(
                    mapping.get("instance_id", "") or f"detachment_{index}"
                )
            if "detachment_type" not in mapping:
                continue
            selections.append(DetachmentSelection.from_dict(mapping))
            continue
        selection_id = str(getattr(value, "selection_id", "") or getattr(value, "instance_id", "") or f"detachment_{index}")
        detachment_type = str(getattr(value, "detachment_type", "") or "")
        if not detachment_type:
            continue
        selections.append(
            DetachmentSelection(
                selection_id=selection_id,
                detachment_type=detachment_type,
                detachment_points_cost=int(getattr(value, "detachment_points_cost", 0) or 0),
                label=getattr(value, "label", None),
                metadata=dict(getattr(value, "metadata", {}) or {}),
            )
        )
    return selections


def _roster_entries(values: object) -> list[RosterEntry]:
    entries: list[RosterEntry] = []
    for index, value in enumerate(list(values or []), start=1):
        if isinstance(value, RosterEntry):
            entries.append(value)
            continue
        if isinstance(value, Mapping):
            mapping = dict(value)
            if not str(mapping.get("entry_id", "") or "").strip():
                mapping["entry_id"] = f"unit_{index}"
            entries.append(RosterEntry.from_dict(mapping))
            continue
        entry_id = str(getattr(value, "entry_id", "") or f"unit_{index}")
        name = str(getattr(value, "name", "") or "")
        if not name:
            continue
        entries.append(
            RosterEntry(
                entry_id=entry_id,
                name=name,
                count=max(1, int(getattr(value, "count", 1) or 1)),
                detachment_selection_id=getattr(value, "detachment_selection_id", None),
                wargear=list(getattr(value, "wargear", []) or []),
                enhancement_names=list(
                    getattr(value, "enhancement_names", getattr(value, "enhancements", [])) or []
                ),
                is_warlord=bool(getattr(value, "is_warlord", False)),
                metadata=dict(getattr(value, "metadata", {}) or {}),
            )
        )
    return entries


def _runtime_unit_entries(army: object) -> list[RosterEntry]:
    units = list(getattr(army, "units", []) or [])
    units.sort(key=lambda unit: str(get_entity_id(unit) or getattr(unit, "name", "") or ""))
    entries: list[RosterEntry] = []
    warlord = getattr(army, "warlord", None)
    for index, unit in enumerate(units, start=1):
        name = str(getattr(unit, "name", "") or "")
        if not name:
            continue
        enhancement = getattr(unit, "enhancement", None)
        enhancement_names = [str(getattr(enhancement, "name", "") or "")] if enhancement is not None else []
        model_count = len(list(getattr(unit, "models", []) or []))
        entries.append(
            RosterEntry(
                entry_id=str(get_entity_id(unit) or f"runtime_unit_{index}"),
                name=name,
                count=max(1, model_count),
                enhancement_names=enhancement_names,
                is_warlord=unit is warlord,
            )
        )
    return entries


def _enhancement_assignments(values: object) -> list[EnhancementAssignment]:
    assignments: list[EnhancementAssignment] = []
    for index, value in enumerate(list(values or []), start=1):
        if isinstance(value, EnhancementAssignment):
            assignments.append(value)
            continue
        if isinstance(value, Mapping):
            mapping = dict(value)
            if not str(mapping.get("assignment_id", "") or "").strip():
                mapping["assignment_id"] = f"enhancement_{index}"
            assignments.append(EnhancementAssignment.from_dict(mapping))
            continue
        assignment_id = str(getattr(value, "assignment_id", "") or f"enhancement_{index}")
        enhancement_name = str(getattr(value, "enhancement_name", "") or "")
        target_entry_id = str(getattr(value, "target_entry_id", "") or "")
        if not enhancement_name or not target_entry_id:
            continue
        assignments.append(
            EnhancementAssignment(
                assignment_id=assignment_id,
                enhancement_name=enhancement_name,
                target_entry_id=target_entry_id,
                detachment_selection_id=getattr(value, "detachment_selection_id", None),
                metadata=dict(getattr(value, "metadata", {}) or {}),
            )
        )
    return assignments


def _runtime_enhancement_assignments(entries: list[RosterEntry]) -> list[EnhancementAssignment]:
    assignments: list[EnhancementAssignment] = []
    for entry in entries:
        for index, enhancement_name in enumerate(list(entry.enhancement_names or []), start=1):
            assignments.append(
                EnhancementAssignment(
                    assignment_id=f"{entry.entry_id}_enhancement_{index}",
                    enhancement_name=enhancement_name,
                    target_entry_id=entry.entry_id,
                    detachment_selection_id=entry.detachment_selection_id,
                    metadata={"source": "runtime_fallback"},
                )
            )
    return assignments


def _attachment_bindings(values: object) -> list[AttachmentBinding]:
    bindings: list[AttachmentBinding] = []
    for index, value in enumerate(list(values or []), start=1):
        if isinstance(value, AttachmentBinding):
            bindings.append(value)
            continue
        if isinstance(value, Mapping):
            mapping = dict(value)
            if not str(mapping.get("binding_id", "") or "").strip():
                mapping["binding_id"] = f"attachment_{index}"
            bindings.append(AttachmentBinding.from_dict(mapping))
            continue
        binding_id = str(getattr(value, "binding_id", "") or f"attachment_{index}")
        bodyguard_entry_id = str(getattr(value, "bodyguard_entry_id", "") or "")
        leader_entry_id = getattr(value, "leader_entry_id", None)
        support_entry_id = getattr(value, "support_entry_id", None)
        if not bodyguard_entry_id or (leader_entry_id is None and support_entry_id is None):
            continue
        bindings.append(
            AttachmentBinding(
                binding_id=binding_id,
                bodyguard_entry_id=bodyguard_entry_id,
                leader_entry_id=leader_entry_id,
                support_entry_id=support_entry_id,
            )
        )
    return bindings


def _fallback_blueprint(army: object) -> ArmyBlueprint | None:
    faction = str(getattr(army, "faction", "") or "").strip()
    if not faction:
        return None
    detachments = _detachment_selections(getattr(army, "build_detachments", []) or [])
    if not detachments:
        detachments = _detachment_selections(getattr(army, "detachments", []) or [])
    if not detachments:
        get_primary_detachment_type = getattr(army, "get_primary_detachment_type", None)
        detachment_type = (
            str(get_primary_detachment_type() or "").strip()
            if callable(get_primary_detachment_type)
            else ""
        )
        if detachment_type:
            detachments = [
                DetachmentSelection(
                    selection_id="detachment_1",
                    detachment_type=detachment_type,
                    detachment_points_cost=safe_int(getattr(army, "detachment_points_spent", 0), 0),
                )
            ]
    unit_entries = _roster_entries(getattr(army, "build_unit_entries", []) or [])
    if not unit_entries:
        unit_entries = _runtime_unit_entries(army)
    enhancement_assignments = _enhancement_assignments(
        getattr(army, "build_enhancement_assignments", []) or []
    )
    if not enhancement_assignments:
        enhancement_assignments = _runtime_enhancement_assignments(unit_entries)
    attachment_bindings = _attachment_bindings(
        getattr(army, "build_attachment_bindings", []) or getattr(army, "attachment_bindings", []) or []
    )
    return ArmyBlueprint(
        faction=faction,
        points_limit=max(1, safe_int(getattr(army, "points_limit", 2000), 2000)),
        battle_size=getattr(army, "battle_size", None),
        detachments=detachments,
        detachment_points_budget=getattr(army, "detachment_points_budget", None),
        unit_entries=unit_entries,
        enhancement_assignments=enhancement_assignments,
        attachment_bindings=attachment_bindings,
        force_disposition=getattr(army, "force_disposition", None),
        allowed_force_dispositions=list(getattr(army, "allowed_force_dispositions", []) or []),
        metadata=dict(getattr(army, "build_metadata", {}) or {}),
    )


def army_blueprint_for_army(army: object) -> ArmyBlueprint | None:
    if army is None:
        return None
    blueprint = getattr(army, "army_blueprint", None)
    if isinstance(blueprint, ArmyBlueprint):
        return blueprint
    if isinstance(blueprint, Mapping):
        return ArmyBlueprint.from_dict(blueprint)
    return _fallback_blueprint(army)


def validated_muster_for_army(army: object, blueprint: ArmyBlueprint | None) -> ValidatedMuster | None:
    validated = getattr(army, "validated_muster", None)
    if isinstance(validated, ValidatedMuster):
        return validated
    if isinstance(validated, Mapping):
        return ValidatedMuster.from_dict(validated)
    faction_id = str(getattr(army, "faction_id", "") or "").strip()
    if blueprint is None or not faction_id:
        return None
    build_metadata = dict(getattr(army, "build_metadata", {}) or {})
    return ValidatedMuster(
        blueprint=blueprint,
        faction_id=faction_id,
        detachment_points_spent=safe_int(getattr(army, "detachment_points_spent", 0), 0),
        warnings=list(build_metadata.get("warnings", []) or []),
    )


def detachment_points_summary_for_army(
    army: object,
    *,
    blueprint: ArmyBlueprint | None,
    validated_muster: ValidatedMuster | None,
) -> dict[str, Any]:
    summary = getattr(army, "detachment_points_summary", None)
    if isinstance(summary, Mapping):
        spent = summary.get("spent")
        if spent in (None, ""):
            spent = getattr(army, "detachment_points_spent", 0)
        budget = summary.get("budget")
        if budget in ("",):
            budget = None
        elif budget is not None:
            budget = safe_int(budget, 0)
        remaining = summary.get("remaining")
        if remaining in ("",):
            remaining = None
        elif remaining is not None:
            remaining = safe_int(remaining, 0)
        elif budget is not None:
            remaining = int(budget) - safe_int(spent, 0)
        return {
            "budget": budget,
            "spent": safe_int(spent, 0),
            "remaining": remaining,
        }
    budget = getattr(army, "detachment_points_budget", None)
    spent = safe_int(getattr(army, "detachment_points_spent", 0), 0)
    if validated_muster is not None:
        spent = int(validated_muster.detachment_points_spent)
    if budget is None and blueprint is not None:
        budget = blueprint.detachment_points_budget
    remaining = None if budget is None else int(budget) - int(spent)
    return {
        "budget": budget,
        "spent": spent,
        "remaining": remaining,
    }


def army_build_player_payload(player: object) -> dict[str, Any]:
    player_payload: dict[str, Any] = {
        "player_id": str(getattr(player, "id", "") or ""),
        "player_name": str(getattr(player, "name", "") or ""),
    }
    army = getattr(player, "army", None)
    if army is None:
        player_payload["army_present"] = False
        return json_safe(player_payload)

    blueprint = army_blueprint_for_army(army)
    validated_muster = validated_muster_for_army(army, blueprint)
    detachments = list(blueprint.detachments or []) if blueprint is not None else []
    unit_entries = list(blueprint.unit_entries or []) if blueprint is not None else []
    enhancement_assignments = list(blueprint.enhancement_assignments or []) if blueprint is not None else []
    attachment_bindings = list(blueprint.attachment_bindings or []) if blueprint is not None else []
    if blueprint is None:
        fallback = _fallback_blueprint(army)
        if fallback is not None:
            blueprint = fallback
            detachments = list(fallback.detachments or [])
            unit_entries = list(fallback.unit_entries or [])
            enhancement_assignments = list(fallback.enhancement_assignments or [])
            attachment_bindings = list(fallback.attachment_bindings or [])

    get_primary_detachment_type = getattr(army, "get_primary_detachment_type", None)
    primary_detachment_type = str(
        (blueprint.primary_detachment_type if blueprint is not None else "")
        or (get_primary_detachment_type() if callable(get_primary_detachment_type) else "")
        or ""
    )
    army_blueprint_hash = str(
        getattr(army, "army_blueprint_hash", None)
        or (blueprint.army_blueprint_hash if blueprint is not None else "")
        or ""
    )
    build_metadata = dict(getattr(army, "build_metadata", {}) or {})
    if validated_muster is not None:
        build_metadata.setdefault("warnings", list(validated_muster.warnings or []))

    player_payload.update(
        {
            "army_present": True,
            "army_id": str(getattr(army, "id", "") or ""),
            "faction": str(getattr(army, "faction", "") or ""),
            "faction_id": str(getattr(army, "faction_id", "") or ""),
            "points_limit": safe_int(getattr(army, "points_limit", 0), 0),
            "battle_size": str(getattr(blueprint, "battle_size", "") or "") if blueprint is not None else "",
            "army_blueprint_hash": army_blueprint_hash,
            "primary_detachment_type": primary_detachment_type,
            "detachments": [item.to_dict() for item in detachments],
            "unit_entries": [item.to_dict() for item in unit_entries],
            "enhancement_assignments": [item.to_dict() for item in enhancement_assignments],
            "attachment_bindings": [item.to_dict() for item in attachment_bindings],
            "detachment_points_summary": detachment_points_summary_for_army(
                army,
                blueprint=blueprint,
                validated_muster=validated_muster,
            ),
            "force_disposition": str(
                getattr(army, "force_disposition", None)
                or (blueprint.force_disposition if blueprint is not None else "")
                or ""
            ),
            "allowed_force_dispositions": list(
                getattr(army, "allowed_force_dispositions", None)
                or (blueprint.allowed_force_dispositions if blueprint is not None else [])
                or []
            ),
            "build_metadata": build_metadata,
            "blueprint_metadata": dict(getattr(blueprint, "metadata", {}) or {}) if blueprint is not None else {},
        }
    )
    if validated_muster is not None:
        player_payload["validated_muster"] = {
            "faction_id": str(validated_muster.faction_id or ""),
            "detachment_points_spent": int(validated_muster.detachment_points_spent),
            "warnings": list(validated_muster.warnings or []),
        }
    return json_safe(player_payload)


def build_army_build_descriptor_payload(game: object) -> dict[str, Any]:
    players = [army_build_player_payload(player) for player in iter_players(game)]
    return json_safe({"players": players})


def compile_army_build_descriptor(game: object) -> CompiledDescriptor:
    payload = build_army_build_descriptor_payload(game)
    return CompiledDescriptor(
        family="ArmyBuildDescriptor",
        descriptor_id=descriptor_id("army_build_descriptor", payload),
        payload=payload,
    )


__all__ = [
    "army_blueprint_for_army",
    "army_build_player_payload",
    "build_army_build_descriptor_payload",
    "compile_army_build_descriptor",
    "detachment_points_summary_for_army",
    "validated_muster_for_army",
]
