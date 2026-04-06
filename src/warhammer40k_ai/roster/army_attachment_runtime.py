"""Runtime attachment planning and validation helpers for Army."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .army_attachments import AttachmentBinding

if TYPE_CHECKING:
    from .army import Army


def _army_validation_error():
    from .army import ArmyValidationError

    return ArmyValidationError


def _normalized_text(value: object) -> str:
    return str(value or "").strip()


def _normalized_name(value: object) -> str:
    return " ".join(_normalized_text(value).lower().split())


@dataclass(frozen=True)
class AttachmentSlots:
    leader_slots: int
    support_slots: int = 1
    support_requires_bodyguard: bool = True


def attachment_slots_for_bodyguard(bodyguard: object) -> AttachmentSlots:
    leader_slots = 1
    slot_fn = getattr(bodyguard, "leader_attachment_slot_limit", None)
    if callable(slot_fn):
        try:
            leader_slots = max(0, int(slot_fn() or 0))
        except (TypeError, ValueError):
            leader_slots = 0
    support_slots = 1
    support_slot_fn = getattr(bodyguard, "support_attachment_slot_limit", None)
    if callable(support_slot_fn):
        try:
            support_slots = max(0, int(support_slot_fn() or 0))
        except (TypeError, ValueError):
            support_slots = 0
    support_requires_bodyguard = True
    support_requires_fn = getattr(bodyguard, "support_attachment_requires_bodyguard", None)
    if callable(support_requires_fn):
        support_requires_bodyguard = bool(support_requires_fn())
    return AttachmentSlots(
        leader_slots=leader_slots,
        support_slots=support_slots,
        support_requires_bodyguard=support_requires_bodyguard,
    )


def _unit_build_entry_id(unit: object) -> str:
    getter = getattr(unit, "get_build_entry_id", None)
    if callable(getter):
        return _normalized_text(getter())
    return _normalized_text(getattr(unit, "build_entry_id", None))


def _set_unit_build_entry_id(unit: object, entry_id: object) -> None:
    setter = getattr(unit, "set_build_entry_id", None)
    if callable(setter):
        setter(entry_id)
        return
    setattr(unit, "build_entry_id", _normalized_text(entry_id) or None)


def assign_build_entry_ids_to_units(army: "Army") -> dict[str, object]:
    build_entries = list(getattr(army, "build_unit_entries", []) or [])
    units = list(getattr(army, "units", []) or [])
    assigned_ids = {
        entry_id
        for entry_id in (_unit_build_entry_id(unit) for unit in units)
        if entry_id
    }
    entry_ids_by_name: dict[str, list[str]] = {}
    for entry in build_entries:
        entry_id = _normalized_text(getattr(entry, "entry_id", None))
        if not entry_id:
            continue
        name_key = _normalized_name(getattr(entry, "name", None))
        entry_ids_by_name.setdefault(name_key, []).append(entry_id)

    for unit in units:
        if _unit_build_entry_id(unit):
            continue
        name_key = _normalized_name(getattr(unit, "name", None))
        for entry_id in list(entry_ids_by_name.get(name_key, []) or []):
            if entry_id in assigned_ids:
                continue
            _set_unit_build_entry_id(unit, entry_id)
            assigned_ids.add(entry_id)
            break

    runtime_units: dict[str, object] = {}
    for unit in units:
        entry_id = _unit_build_entry_id(unit)
        if entry_id:
            runtime_units[entry_id] = unit
    return runtime_units


def apply_authored_attachment_bindings(army: "Army") -> dict[str, int]:
    bindings = [AttachmentBinding.from_dict(value) for value in list(getattr(army, "attachment_bindings", []) or [])]
    if not bindings:
        return {"leader_bindings_applied": 0, "support_bindings_applied": 0}

    units_by_entry_id = assign_build_entry_ids_to_units(army)
    ArmyValidationError = _army_validation_error()
    leader_applied = 0
    support_applied = 0

    for binding in bindings:
        bodyguard = units_by_entry_id.get(binding.bodyguard_entry_id)
        if bodyguard is None:
            raise ArmyValidationError(
                f"Attachment binding '{binding.binding_id}' could not resolve bodyguard entry "
                f"'{binding.bodyguard_entry_id}' to a runtime unit."
            )

        if binding.leader_entry_id:
            leader = units_by_entry_id.get(binding.leader_entry_id)
            if leader is None:
                raise ArmyValidationError(
                    f"Attachment binding '{binding.binding_id}' could not resolve leader entry "
                    f"'{binding.leader_entry_id}' to a runtime unit."
                )
            current_bodyguard = getattr(leader, "attached_to", None)
            if current_bodyguard is None:
                attach_fn = getattr(leader, "attach_to_unit", None)
                if not callable(attach_fn):
                    raise ArmyValidationError(
                        f"Attachment binding '{binding.binding_id}' references leader '{getattr(leader, 'name', 'Unknown')}' "
                        "but the unit cannot attach at runtime."
                    )
                try:
                    attach_fn(bodyguard)
                except ValueError as exc:
                    raise ArmyValidationError(str(exc)) from exc
                current_bodyguard = getattr(leader, "attached_to", None)
            elif current_bodyguard is not bodyguard:
                raise ArmyValidationError(
                    f"Attachment binding '{binding.binding_id}' conflicts with leader "
                    f"'{getattr(leader, 'name', 'Unknown')}' already being attached to "
                    f"'{getattr(current_bodyguard, 'name', 'Unknown')}'."
                )
            if current_bodyguard is bodyguard:
                marker_fn = getattr(leader, "_mark_leader_attachment_binding", None)
                if callable(marker_fn):
                    marker_fn(bodyguard, binding_id=binding.binding_id, source="build")
                leader_applied += 1

        if binding.support_entry_id:
            support = units_by_entry_id.get(binding.support_entry_id)
            if support is None:
                raise ArmyValidationError(
                    f"Attachment binding '{binding.binding_id}' could not resolve support entry "
                    f"'{binding.support_entry_id}' to a runtime unit."
                )
            current_bodyguard = getattr(support, "support_joined_to", None)
            if current_bodyguard is None:
                attach_fn = getattr(support, "attach_support_artillery_to", None)
                if not callable(attach_fn):
                    raise ArmyValidationError(
                        f"Attachment binding '{binding.binding_id}' references support unit "
                        f"'{getattr(support, 'name', 'Unknown')}' but the unit cannot join a bodyguard at runtime."
                    )
                try:
                    attach_fn(bodyguard)
                except ValueError as exc:
                    raise ArmyValidationError(str(exc)) from exc
                current_bodyguard = getattr(support, "support_joined_to", None)
            elif current_bodyguard is not bodyguard:
                raise ArmyValidationError(
                    f"Attachment binding '{binding.binding_id}' conflicts with support unit "
                    f"'{getattr(support, 'name', 'Unknown')}' already being joined to "
                    f"'{getattr(current_bodyguard, 'name', 'Unknown')}'."
                )
            if current_bodyguard is bodyguard:
                marker_fn = getattr(support, "_mark_support_attachment_binding", None)
                if callable(marker_fn):
                    marker_fn(bodyguard, binding_id=binding.binding_id, source="build")
                support_applied += 1

    return {
        "leader_bindings_applied": leader_applied,
        "support_bindings_applied": support_applied,
    }


def validate_leader_attachments(army: "Army") -> None:
    ArmyValidationError = _army_validation_error()
    units = list(getattr(army, "units", []) or [])
    unit_leader_map: dict[object, list[object]] = {}
    leader_units = [unit for unit in units if bool(getattr(unit, "is_leader", False))]

    for leader in leader_units:
        attached_to = getattr(leader, "attached_to", None)
        if attached_to is None:
            continue
        if attached_to not in units:
            raise ArmyValidationError(f"Leader '{leader.name}' is attached to an invalid unit.")
        can_attach = getattr(leader, "can_attach_to", None)
        if callable(can_attach) and not can_attach(attached_to):
            raise ArmyValidationError(f"Leader '{leader.name}' cannot be attached to '{attached_to.name}'.")
        unit_leader_map.setdefault(attached_to, []).append(leader)

    for bodyguard, leaders in unit_leader_map.items():
        slots = attachment_slots_for_bodyguard(bodyguard)
        if len(leaders) > slots.leader_slots:
            raise ArmyValidationError(
                f"Unit '{bodyguard.name}' has {len(leaders)} Leaders attached (max {slots.leader_slots})."
            )


def validate_support_attachments(army: "Army") -> None:
    ArmyValidationError = _army_validation_error()
    bodyguard_map: dict[object, list[object]] = {}
    units_to_remove: list[object] = []
    units = list(getattr(army, "units", []) or [])
    for unit in units:
        if unit is None:
            continue
        has_joined_support = getattr(unit, "has_joined_support_ability", None)
        if not callable(has_joined_support) or not bool(has_joined_support()):
            continue
        requires_attachment = False
        requires_attach_fn = getattr(unit, "joined_support_requires_attachment", None)
        if callable(requires_attach_fn):
            requires_attachment = bool(requires_attach_fn())
        joined_to = getattr(unit, "support_joined_to", None)
        if joined_to is None:
            if requires_attachment:
                eligible_bodyguards: list[object] = []
                can_join_fn = getattr(unit, "can_join_support_artillery", None)
                if callable(can_join_fn):
                    for candidate in units:
                        if candidate is None or candidate is unit:
                            continue
                        if can_join_fn(candidate):
                            eligible_bodyguards.append(candidate)
                if eligible_bodyguards:
                    names = ", ".join(
                        sorted(
                            {
                                str(getattr(candidate, "name", "Unknown") or "Unknown")
                                for candidate in eligible_bodyguards
                            }
                        )
                    )
                    suffix = f" Eligible units: {names}." if names else "."
                    raise ArmyValidationError(
                        f"Joined support unit '{unit.name}' must join an eligible unit during Declare Battle Formations "
                        "or be supplied by an authored attachment binding."
                        f"{suffix}"
                    )
                units_to_remove.append(unit)
            continue
        if joined_to not in units:
            raise ArmyValidationError(f"Joined support unit '{unit.name}' is joined to an invalid unit.")
        can_join_fn = getattr(unit, "can_join_support_artillery", None)
        if callable(can_join_fn) and not can_join_fn(joined_to):
            raise ArmyValidationError(
                f"Joined support unit '{unit.name}' cannot join '{joined_to.name}'."
            )
        bodyguard_map.setdefault(joined_to, []).append(unit)

    for bodyguard, supports in bodyguard_map.items():
        slots = attachment_slots_for_bodyguard(bodyguard)
        if len(supports) > slots.support_slots:
            names = ", ".join(str(getattr(support, "name", "Unknown") or "Unknown") for support in supports if support)
            raise ArmyValidationError(
                f"Unit '{bodyguard.name}' has multiple joined support units ({names})."
            )

    for unit in units_to_remove:
        if unit not in list(getattr(army, "units", []) or []):
            continue
        army.units.remove(unit)
        special_rules = getattr(unit, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["destroyed_before_battle"] = True
        special_rules["destroyed_before_battle_reason"] = "Mandatory joined-support attachment was impossible."
        unit.special_rules = special_rules


__all__ = [
    "AttachmentSlots",
    "apply_authored_attachment_bindings",
    "assign_build_entry_ids_to_units",
    "attachment_slots_for_bodyguard",
    "validate_leader_attachments",
    "validate_support_attachments",
]
