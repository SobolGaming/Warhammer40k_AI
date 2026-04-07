from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .army import Army
from .army_attachments import AttachmentBinding
from .army_build import DetachmentSelection, EnhancementAssignment, RosterEntry, ValidatedMuster
from .army_runtime import apply_validated_muster_to_army
from .army_validation import validate_army_muster_request
from ..waha_helper import WahaHelper


@dataclass
class UnitSelection:
    """Legacy unit-pick request shape kept as a PR-002 migration adapter."""

    name: str
    count: int = 1
    wargear: list[str] = field(default_factory=list)
    enhancements: list[str] = field(default_factory=list)
    is_warlord: bool = False
    detachment_selection_id: str | None = None
    entry_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "wargear": list(self.wargear),
            "enhancements": list(self.enhancements),
            "is_warlord": self.is_warlord,
            "detachment_selection_id": self.detachment_selection_id,
            "entry_id": self.entry_id,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(
        cls,
        data: "UnitSelection | Mapping[str, Any]",
    ) -> "UnitSelection":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("UnitSelection data must be a mapping or UnitSelection.")
        return cls(
            name=str(data.get("name", "") or ""),
            count=int(data.get("count", 1) or 1),
            wargear=list(data.get("wargear", []) or []),
            enhancements=list(
                data.get(
                    "enhancements",
                    data.get("enhancement_names", []),
                )
                or []
            ),
            is_warlord=bool(data.get("is_warlord", False)),
            detachment_selection_id=data.get("detachment_selection_id"),
            entry_id=data.get("entry_id"),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class ArmyMusterRequest:
    """Serializable build-side army mustering request."""

    faction: str
    points_limit: int = 2000
    battle_size: str | None = None
    detachments: list[DetachmentSelection] = field(default_factory=list)
    detachment_points_budget: int | None = None
    units: list[UnitSelection | RosterEntry] = field(default_factory=list)
    enhancement_assignments: list[EnhancementAssignment] = field(default_factory=list)
    attachment_bindings: list[AttachmentBinding] = field(default_factory=list)
    force_disposition: str | None = None
    allowed_force_dispositions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.faction = str(self.faction or "").strip()
        self.points_limit = int(self.points_limit or 2000)
        self.battle_size = str(self.battle_size or "").strip() or None
        self.detachments = [
            DetachmentSelection.from_dict(value) for value in list(self.detachments or [])
        ]
        self.detachment_points_budget = (
            None
            if self.detachment_points_budget in (None, "")
            else int(self.detachment_points_budget)
        )
        normalized_units: list[UnitSelection | RosterEntry] = []
        for value in list(self.units or []):
            if isinstance(value, (UnitSelection, RosterEntry)):
                normalized_units.append(value)
                continue
            if isinstance(value, Mapping) and "entry_id" in value:
                normalized_units.append(RosterEntry.from_dict(value))
                continue
            normalized_units.append(UnitSelection.from_dict(value))
        self.units = normalized_units
        self.enhancement_assignments = [
            EnhancementAssignment.from_dict(value)
            for value in list(self.enhancement_assignments or [])
        ]
        self.attachment_bindings = [
            AttachmentBinding.from_dict(value)
            for value in list(self.attachment_bindings or [])
        ]
        self.force_disposition = str(self.force_disposition or "").strip() or None
        self.allowed_force_dispositions = [
            str(value or "").strip()
            for value in list(self.allowed_force_dispositions or [])
            if str(value or "").strip()
        ]
        self.metadata = dict(self.metadata or {})

    @property
    def primary_detachment_type(self) -> str | None:
        if not self.detachments:
            return None
        return self.detachments[0].detachment_type

    def to_dict(self) -> dict[str, Any]:
        units_payload: list[dict[str, Any]] = []
        for unit in list(self.units or []):
            if isinstance(unit, RosterEntry):
                units_payload.append(unit.to_dict())
            else:
                units_payload.append(UnitSelection.from_dict(unit).to_dict())
        return {
            "faction": self.faction,
            "points_limit": self.points_limit,
            "battle_size": self.battle_size,
            "detachments": [value.to_dict() for value in list(self.detachments or [])],
            "detachment_points_budget": self.detachment_points_budget,
            "units": units_payload,
            "enhancement_assignments": [
                value.to_dict() for value in list(self.enhancement_assignments or [])
            ],
            "attachment_bindings": [
                value.to_dict() for value in list(self.attachment_bindings or [])
            ],
            "force_disposition": self.force_disposition,
            "allowed_force_dispositions": list(self.allowed_force_dispositions),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(
        cls,
        data: "ArmyMusterRequest | Mapping[str, Any]",
    ) -> "ArmyMusterRequest":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("ArmyMusterRequest data must be a mapping or ArmyMusterRequest.")
        return cls(
            faction=str(data.get("faction", "") or ""),
            points_limit=data.get("points_limit", 2000),
            battle_size=data.get("battle_size"),
            detachments=list(data.get("detachments", []) or []),
            detachment_points_budget=data.get("detachment_points_budget"),
            units=list(data.get("units", data.get("unit_entries", [])) or []),
            enhancement_assignments=list(data.get("enhancement_assignments", []) or []),
            attachment_bindings=list(data.get("attachment_bindings", []) or []),
            force_disposition=data.get("force_disposition"),
            allowed_force_dispositions=list(data.get("allowed_force_dispositions", []) or []),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    def to_blueprint(self):
        return validate_army_muster_request(self).blueprint


class ArmyMusterer:
    """Build runtime armies from validated muster requests."""

    def __init__(self, waha_helper: WahaHelper) -> None:
        self._waha = waha_helper

    def validate_request(self, request: ArmyMusterRequest | Mapping[str, Any]) -> ValidatedMuster:
        return validate_army_muster_request(request)

    def muster_army(self, request: ArmyMusterRequest | Mapping[str, Any]) -> Army:
        validated_muster = self.validate_request(request)
        army = Army(
            faction=validated_muster.blueprint.faction,
            points_limit=validated_muster.blueprint.points_limit,
        )
        army.faction_id = validated_muster.faction_id
        apply_validated_muster_to_army(army, validated_muster)
        if validated_muster.blueprint.unit_entries:
            raise NotImplementedError(
                "Validated mustering can now represent unit entries, but runtime unit "
                "materialization is not implemented yet."
            )
        return army
