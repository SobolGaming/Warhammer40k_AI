"""Runtime helpers for attaching build-side army state to Army."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .army import Army
from .army_attachment_runtime import assign_build_entry_ids_to_units
from .army_build import DetachmentSelection, ValidatedMuster


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _required_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if text:
        return text
    raise ValueError(f"{field_name} is required.")


def _optional_non_negative_int(value: object, *, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    number = int(value)
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    return number


@dataclass
class DetachmentInstance:
    """Runtime counterpart of a validated detachment selection."""

    instance_id: str
    selection_id: str
    faction_id: str
    detachment_type: str
    detachment_points_cost: int = 0
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.instance_id = _required_text(self.instance_id, field_name="instance_id")
        self.selection_id = _required_text(self.selection_id, field_name="selection_id")
        self.faction_id = _required_text(self.faction_id, field_name="faction_id")
        self.detachment_type = _required_text(self.detachment_type, field_name="detachment_type")
        self.detachment_points_cost = _optional_non_negative_int(
            self.detachment_points_cost,
            field_name="detachment_points_cost",
        ) or 0
        self.label = _optional_text(self.label)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "selection_id": self.selection_id,
            "faction_id": self.faction_id,
            "detachment_type": self.detachment_type,
            "detachment_points_cost": self.detachment_points_cost,
            "label": self.label,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(
        cls,
        data: "DetachmentInstance | Mapping[str, Any]",
    ) -> "DetachmentInstance":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("DetachmentInstance data must be a mapping or DetachmentInstance.")
        return cls(
            instance_id=str(data.get("instance_id", "") or ""),
            selection_id=str(data.get("selection_id", "") or ""),
            faction_id=str(data.get("faction_id", "") or ""),
            detachment_type=str(data.get("detachment_type", "") or ""),
            detachment_points_cost=data.get("detachment_points_cost", 0),
            label=data.get("label"),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    @classmethod
    def from_selection(
        cls,
        selection: DetachmentSelection,
        *,
        faction_id: str,
        index: int,
    ) -> "DetachmentInstance":
        selection = DetachmentSelection.from_dict(selection)
        normalized_faction_id = str(
            selection.metadata.get("faction_id", faction_id) or faction_id
        ).strip().upper()
        return cls(
            instance_id=f"detachment_instance_{index}",
            selection_id=selection.selection_id,
            faction_id=normalized_faction_id,
            detachment_type=selection.detachment_type,
            detachment_points_cost=selection.detachment_points_cost,
            label=selection.label,
            metadata=dict(selection.metadata or {}),
        )


def apply_validated_muster_to_army(army: Army, validated_muster: ValidatedMuster) -> Army:
    """Attach build-side muster metadata to an already-created runtime army."""

    blueprint = validated_muster.blueprint
    runtime_detachments = [
        DetachmentInstance.from_selection(
            selection,
            faction_id=validated_muster.faction_id,
            index=index,
        )
        for index, selection in enumerate(list(blueprint.detachments or []), start=1)
    ]
    remaining_detachment_points = None
    if blueprint.detachment_points_budget is not None:
        remaining_detachment_points = int(blueprint.detachment_points_budget) - int(
            validated_muster.detachment_points_spent
        )

    army.army_blueprint = blueprint
    army.army_blueprint_hash = blueprint.army_blueprint_hash
    army.validated_muster = validated_muster
    army.build_detachments = list(blueprint.detachments or [])
    army.detachments = runtime_detachments
    army.build_unit_entries = list(blueprint.unit_entries or [])
    army.build_enhancement_assignments = list(blueprint.enhancement_assignments or [])
    army.build_upgrade_assignments = list(blueprint.upgrade_assignments or [])
    army.build_attachment_bindings = list(blueprint.attachment_bindings or [])
    army.attachment_bindings = list(blueprint.attachment_bindings or [])
    army.detachment_points_budget = blueprint.detachment_points_budget
    army.detachment_points_spent = validated_muster.detachment_points_spent
    army.detachment_points_summary = {
        "budget": blueprint.detachment_points_budget,
        "spent": validated_muster.detachment_points_spent,
        "remaining": remaining_detachment_points,
    }
    army.force_disposition = blueprint.force_disposition
    army.allowed_force_dispositions = list(blueprint.allowed_force_dispositions or [])
    army.build_metadata = {"warnings": list(validated_muster.warnings or [])}
    if getattr(army, "units", None):
        assign_build_entry_ids_to_units(army)
    return army


__all__ = ["DetachmentInstance", "apply_validated_muster_to_army"]
