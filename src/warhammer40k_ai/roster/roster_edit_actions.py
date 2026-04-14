"""Deterministic roster-edit action DSL for offline mustering search."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
from typing import Any

from .army_attachments import AttachmentBinding
from .army_build import ArmyBlueprint, DetachmentSelection, EnhancementAssignment, RosterEntry
from .build_capability_schema import canonical_json, json_safe


def _clone_blueprint(blueprint: ArmyBlueprint | Mapping[str, Any]) -> ArmyBlueprint:
    return ArmyBlueprint.from_dict(ArmyBlueprint.from_dict(blueprint).to_dict())


def _required_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if text:
        return text
    raise ValueError(f"{field_name} is required.")


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _string_tuple(values: object) -> tuple[str, ...]:
    ordered: list[str] = []
    for value in list(values or []):
        text = str(value or "").strip()
        if text:
            ordered.append(text)
    return tuple(ordered)


def _stable_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(json_safe(dict(value or {})))


def _stable_wargear_by_model(value: object) -> dict[str, list[dict[str, Any]]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("wargear_by_model must be a mapping.")
    normalized: dict[str, list[dict[str, Any]]] = {}
    for raw_model_name, raw_assignments in sorted(value.items(), key=lambda item: str(item[0])):
        model_name = str(raw_model_name or "").strip()
        if not model_name:
            continue
        if not isinstance(raw_assignments, Sequence) or isinstance(raw_assignments, (str, bytes)):
            raise ValueError(f"wargear_by_model[{model_name!r}] must be a sequence of assignments.")
        assignments: list[dict[str, Any]] = []
        for raw_assignment in raw_assignments:
            if not isinstance(raw_assignment, Mapping):
                raise ValueError(f"wargear_by_model[{model_name!r}] items must be mappings.")
            gear_name = _required_text(raw_assignment.get("name"), field_name=f"{model_name}.name")
            quantity = int(raw_assignment.get("quantity", 1) or 1)
            if quantity <= 0:
                raise ValueError(f"{model_name}.quantity must be positive.")
            assignments.append({"name": gear_name, "quantity": quantity})
        normalized[model_name] = assignments
    return normalized


def _sync_entry_enhancement_names(blueprint: ArmyBlueprint) -> None:
    names_by_entry: dict[str, list[str]] = {}
    for assignment in list(blueprint.enhancement_assignments or []):
        names_by_entry.setdefault(str(assignment.target_entry_id or ""), []).append(
            str(assignment.enhancement_name or "")
        )
    for entry in list(blueprint.unit_entries or []):
        names = [
            name
            for name in names_by_entry.get(str(entry.entry_id or ""), [])
            if str(name or "").strip()
        ]
        entry.enhancement_names = list(names)


def _action_id(kind: str, payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json({"kind": kind, "payload": dict(payload or {})}).encode("utf-8")).hexdigest()[:16]
    return f"roster_edit:{kind}:{digest}"


@dataclass(frozen=True)
class AddDetachmentAction:
    detachment: DetachmentSelection

    def __post_init__(self) -> None:
        object.__setattr__(self, "detachment", DetachmentSelection.from_dict(self.detachment))

    @property
    def kind(self) -> str:
        return "add_detachment"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "detachment": self.detachment.to_dict()}


@dataclass(frozen=True)
class RemoveDetachmentAction:
    selection_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "selection_id", _required_text(self.selection_id, field_name="selection_id"))

    @property
    def kind(self) -> str:
        return "remove_detachment"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "selection_id": self.selection_id}


@dataclass(frozen=True)
class SwapDetachmentAction:
    selection_id: str
    detachment_type: str
    detachment_points_cost: int = 0
    label: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "selection_id", _required_text(self.selection_id, field_name="selection_id"))
        object.__setattr__(self, "detachment_type", _required_text(self.detachment_type, field_name="detachment_type"))
        object.__setattr__(self, "detachment_points_cost", int(self.detachment_points_cost or 0))
        object.__setattr__(self, "label", _optional_text(self.label))
        object.__setattr__(self, "metadata", _stable_mapping(self.metadata))

    @property
    def kind(self) -> str:
        return "swap_detachment"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "selection_id": self.selection_id,
            "detachment_type": self.detachment_type,
            "detachment_points_cost": self.detachment_points_cost,
            "label": self.label,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class AddUnitEntryAction:
    entry: RosterEntry

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry", RosterEntry.from_dict(self.entry))

    @property
    def kind(self) -> str:
        return "add_unit_entry"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "entry": self.entry.to_dict()}


@dataclass(frozen=True)
class RemoveUnitEntryAction:
    entry_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", _required_text(self.entry_id, field_name="entry_id"))

    @property
    def kind(self) -> str:
        return "remove_unit_entry"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "entry_id": self.entry_id}


@dataclass(frozen=True)
class ChangeWargearChoiceAction:
    entry_id: str
    wargear: tuple[str, ...] = ()
    wargear_by_model: dict[str, list[dict[str, Any]]] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", _required_text(self.entry_id, field_name="entry_id"))
        object.__setattr__(self, "wargear", _string_tuple(self.wargear))
        normalized = None if self.wargear_by_model is None else _stable_wargear_by_model(self.wargear_by_model)
        object.__setattr__(self, "wargear_by_model", normalized)

    @property
    def kind(self) -> str:
        return "change_wargear_choice"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "entry_id": self.entry_id,
            "wargear": list(self.wargear),
            "wargear_by_model": None if self.wargear_by_model is None else dict(self.wargear_by_model),
        }


@dataclass(frozen=True)
class AssignEnhancementAction:
    assignment: EnhancementAssignment

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignment", EnhancementAssignment.from_dict(self.assignment))

    @property
    def kind(self) -> str:
        return "assign_enhancement"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "assignment": self.assignment.to_dict()}


@dataclass(frozen=True)
class RemoveEnhancementAction:
    assignment_id: str | None = None
    target_entry_id: str | None = None
    enhancement_name: str | None = None

    def __post_init__(self) -> None:
        assignment_id = _optional_text(self.assignment_id)
        target_entry_id = _optional_text(self.target_entry_id)
        enhancement_name = _optional_text(self.enhancement_name)
        if not assignment_id and not target_entry_id and not enhancement_name:
            raise ValueError("RemoveEnhancementAction requires assignment_id, target_entry_id, or enhancement_name.")
        object.__setattr__(self, "assignment_id", assignment_id)
        object.__setattr__(self, "target_entry_id", target_entry_id)
        object.__setattr__(self, "enhancement_name", enhancement_name)

    @property
    def kind(self) -> str:
        return "remove_enhancement"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "assignment_id": self.assignment_id,
            "target_entry_id": self.target_entry_id,
            "enhancement_name": self.enhancement_name,
        }


@dataclass(frozen=True)
class BindAttachmentAction:
    binding: AttachmentBinding

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding", AttachmentBinding.from_dict(self.binding))

    @property
    def kind(self) -> str:
        return "bind_attachment"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "binding": self.binding.to_dict()}


@dataclass(frozen=True)
class UnbindAttachmentAction:
    binding_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", _required_text(self.binding_id, field_name="binding_id"))

    @property
    def kind(self) -> str:
        return "unbind_attachment"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "binding_id": self.binding_id}


@dataclass(frozen=True)
class RebalanceDetachmentPointSpendAction:
    selection_costs: dict[str, int]
    detachment_points_budget: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.selection_costs, Mapping) or not self.selection_costs:
            raise ValueError("selection_costs must be a non-empty mapping.")
        normalized_costs = {
            _required_text(key, field_name="selection_costs key"): int(value)
            for key, value in sorted(self.selection_costs.items(), key=lambda item: str(item[0]))
        }
        for selection_id, cost in normalized_costs.items():
            if cost < 0:
                raise ValueError(f"selection_costs[{selection_id!r}] cannot be negative.")
        budget = None if self.detachment_points_budget in (None, "") else int(self.detachment_points_budget)
        if budget is not None and budget < 0:
            raise ValueError("detachment_points_budget cannot be negative.")
        object.__setattr__(self, "selection_costs", normalized_costs)
        object.__setattr__(self, "detachment_points_budget", budget)

    @property
    def kind(self) -> str:
        return "rebalance_detachment_point_spend"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "selection_costs": dict(self.selection_costs),
            "detachment_points_budget": self.detachment_points_budget,
        }


@dataclass(frozen=True)
class MutateForceDispositionAction:
    force_disposition: str | None
    allowed_force_dispositions: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "force_disposition", _optional_text(self.force_disposition))
        normalized_allowed = None
        if self.allowed_force_dispositions is not None:
            normalized_allowed = _string_tuple(self.allowed_force_dispositions)
        object.__setattr__(self, "allowed_force_dispositions", normalized_allowed)

    @property
    def kind(self) -> str:
        return "mutate_force_disposition"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "force_disposition": self.force_disposition,
            "allowed_force_dispositions": None if self.allowed_force_dispositions is None else list(self.allowed_force_dispositions),
        }


@dataclass(frozen=True)
class SelectWarlordAction:
    entry_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", _required_text(self.entry_id, field_name="entry_id"))

    @property
    def kind(self) -> str:
        return "select_warlord"

    @property
    def action_id(self) -> str:
        return _action_id(self.kind, self.to_dict())

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "entry_id": self.entry_id}


RosterEditAction = (
    AddDetachmentAction
    | RemoveDetachmentAction
    | SwapDetachmentAction
    | AddUnitEntryAction
    | RemoveUnitEntryAction
    | ChangeWargearChoiceAction
    | AssignEnhancementAction
    | RemoveEnhancementAction
    | BindAttachmentAction
    | UnbindAttachmentAction
    | RebalanceDetachmentPointSpendAction
    | MutateForceDispositionAction
    | SelectWarlordAction
)


def apply_roster_edit_action(
    blueprint: ArmyBlueprint | Mapping[str, Any],
    action: RosterEditAction,
) -> ArmyBlueprint:
    updated = _clone_blueprint(blueprint)
    if isinstance(action, AddDetachmentAction):
        detachments = [
            detachment
            for detachment in list(updated.detachments or [])
            if detachment.selection_id != action.detachment.selection_id
        ]
        detachments.append(DetachmentSelection.from_dict(action.detachment))
        updated.detachments = detachments
        return updated

    if isinstance(action, RemoveDetachmentAction):
        updated.detachments = [
            detachment
            for detachment in list(updated.detachments or [])
            if detachment.selection_id != action.selection_id
        ]
        updated.unit_entries = [
            entry
            for entry in list(updated.unit_entries or [])
            if str(entry.detachment_selection_id or "") != action.selection_id
        ]
        updated.enhancement_assignments = [
            assignment
            for assignment in list(updated.enhancement_assignments or [])
            if str(assignment.detachment_selection_id or "") != action.selection_id
        ]
        updated.attachment_bindings = [
            binding
            for binding in list(updated.attachment_bindings or [])
            if (
                binding.bodyguard_entry_id in {entry.entry_id for entry in updated.unit_entries}
                and (not binding.leader_entry_id or binding.leader_entry_id in {entry.entry_id for entry in updated.unit_entries})
                and (not binding.support_entry_id or binding.support_entry_id in {entry.entry_id for entry in updated.unit_entries})
            )
        ]
        _sync_entry_enhancement_names(updated)
        return updated

    if isinstance(action, SwapDetachmentAction):
        for detachment in list(updated.detachments or []):
            if detachment.selection_id != action.selection_id:
                continue
            detachment.detachment_type = action.detachment_type
            detachment.detachment_points_cost = action.detachment_points_cost
            detachment.label = action.label
            detachment.metadata = dict(action.metadata or {})
            break
        return updated

    if isinstance(action, AddUnitEntryAction):
        entries = [
            entry
            for entry in list(updated.unit_entries or [])
            if entry.entry_id != action.entry.entry_id
        ]
        entries.append(RosterEntry.from_dict(action.entry))
        updated.unit_entries = entries
        return updated

    if isinstance(action, RemoveUnitEntryAction):
        updated.unit_entries = [
            entry
            for entry in list(updated.unit_entries or [])
            if entry.entry_id != action.entry_id
        ]
        updated.enhancement_assignments = [
            assignment
            for assignment in list(updated.enhancement_assignments or [])
            if assignment.target_entry_id != action.entry_id
        ]
        updated.attachment_bindings = [
            binding
            for binding in list(updated.attachment_bindings or [])
            if action.entry_id
            not in {
                str(binding.bodyguard_entry_id or ""),
                str(binding.leader_entry_id or ""),
                str(binding.support_entry_id or ""),
            }
        ]
        _sync_entry_enhancement_names(updated)
        return updated

    if isinstance(action, ChangeWargearChoiceAction):
        for entry in list(updated.unit_entries or []):
            if entry.entry_id != action.entry_id:
                continue
            entry.wargear = list(action.wargear)
            metadata = dict(entry.metadata or {})
            if action.wargear_by_model is None:
                metadata.pop("wargear_by_model", None)
            else:
                metadata["wargear_by_model"] = dict(action.wargear_by_model)
            entry.metadata = metadata
            break
        return updated

    if isinstance(action, AssignEnhancementAction):
        assignments = [
            assignment
            for assignment in list(updated.enhancement_assignments or [])
            if assignment.assignment_id != action.assignment.assignment_id
        ]
        assignments.append(EnhancementAssignment.from_dict(action.assignment))
        updated.enhancement_assignments = assignments
        _sync_entry_enhancement_names(updated)
        return updated

    if isinstance(action, RemoveEnhancementAction):
        def _keep_assignment(assignment: EnhancementAssignment) -> bool:
            if action.assignment_id and assignment.assignment_id == action.assignment_id:
                return False
            if action.target_entry_id and assignment.target_entry_id == action.target_entry_id:
                if not action.enhancement_name or assignment.enhancement_name == action.enhancement_name:
                    return False
            if action.enhancement_name and not action.target_entry_id and assignment.enhancement_name == action.enhancement_name:
                return False
            return True

        updated.enhancement_assignments = [
            assignment
            for assignment in list(updated.enhancement_assignments or [])
            if _keep_assignment(assignment)
        ]
        _sync_entry_enhancement_names(updated)
        return updated

    if isinstance(action, BindAttachmentAction):
        bindings = [
            binding
            for binding in list(updated.attachment_bindings or [])
            if binding.binding_id != action.binding.binding_id
        ]
        bindings.append(AttachmentBinding.from_dict(action.binding))
        updated.attachment_bindings = bindings
        return updated

    if isinstance(action, UnbindAttachmentAction):
        updated.attachment_bindings = [
            binding
            for binding in list(updated.attachment_bindings or [])
            if binding.binding_id != action.binding_id
        ]
        return updated

    if isinstance(action, RebalanceDetachmentPointSpendAction):
        for detachment in list(updated.detachments or []):
            if detachment.selection_id in action.selection_costs:
                detachment.detachment_points_cost = int(action.selection_costs[detachment.selection_id])
        if action.detachment_points_budget is not None:
            updated.detachment_points_budget = int(action.detachment_points_budget)
        return updated

    if isinstance(action, MutateForceDispositionAction):
        updated.force_disposition = action.force_disposition
        if action.allowed_force_dispositions is not None:
            updated.allowed_force_dispositions = list(action.allowed_force_dispositions)
        return updated

    if isinstance(action, SelectWarlordAction):
        for entry in list(updated.unit_entries or []):
            entry.is_warlord = entry.entry_id == action.entry_id
        return updated

    raise TypeError(f"Unsupported roster edit action: {type(action).__name__}")


def apply_roster_edit_trace(
    blueprint: ArmyBlueprint | Mapping[str, Any],
    actions: Sequence[RosterEditAction],
) -> ArmyBlueprint:
    updated = _clone_blueprint(blueprint)
    for action in list(actions or []):
        updated = apply_roster_edit_action(updated, action)
    return updated


__all__ = [
    "AddDetachmentAction",
    "AddUnitEntryAction",
    "AssignEnhancementAction",
    "BindAttachmentAction",
    "ChangeWargearChoiceAction",
    "MutateForceDispositionAction",
    "RebalanceDetachmentPointSpendAction",
    "RemoveDetachmentAction",
    "RemoveEnhancementAction",
    "RemoveUnitEntryAction",
    "RosterEditAction",
    "SelectWarlordAction",
    "SwapDetachmentAction",
    "UnbindAttachmentAction",
    "apply_roster_edit_action",
    "apply_roster_edit_trace",
]
