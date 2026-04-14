"""Build-side army model for mustering and 11e port work."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Mapping

from .army_attachments import AttachmentBinding


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


def _positive_int(value: object, *, field_name: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return number


def _string_list(values: object) -> list[str]:
    return [str(value or "").strip() for value in list(values or []) if str(value or "").strip()]


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _json_safe(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, set):
        values = [_json_safe(inner) for inner in value]
        return sorted(values, key=lambda item: str(item))
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass
class DetachmentSelection:
    """A single detachment choice inside a build-side army blueprint."""

    selection_id: str
    detachment_type: str
    detachment_points_cost: int = 0
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.selection_id = _required_text(self.selection_id, field_name="selection_id")
        self.detachment_type = _required_text(self.detachment_type, field_name="detachment_type")
        self.detachment_points_cost = _optional_non_negative_int(
            self.detachment_points_cost,
            field_name="detachment_points_cost",
        ) or 0
        self.label = _optional_text(self.label)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection_id": self.selection_id,
            "detachment_type": self.detachment_type,
            "detachment_points_cost": self.detachment_points_cost,
            "label": self.label,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(
        cls,
        data: "DetachmentSelection | Mapping[str, Any]",
    ) -> "DetachmentSelection":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("DetachmentSelection data must be a mapping or DetachmentSelection.")
        return cls(
            selection_id=str(data.get("selection_id", "") or ""),
            detachment_type=str(data.get("detachment_type", "") or ""),
            detachment_points_cost=data.get("detachment_points_cost", 0),
            label=data.get("label"),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class EnhancementAssignment:
    """Explicit enhancement assignment chosen during list building."""

    assignment_id: str
    enhancement_name: str
    target_entry_id: str
    detachment_selection_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.assignment_id = _required_text(self.assignment_id, field_name="assignment_id")
        self.enhancement_name = _required_text(self.enhancement_name, field_name="enhancement_name")
        self.target_entry_id = _required_text(self.target_entry_id, field_name="target_entry_id")
        self.detachment_selection_id = _optional_text(self.detachment_selection_id)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "enhancement_name": self.enhancement_name,
            "target_entry_id": self.target_entry_id,
            "detachment_selection_id": self.detachment_selection_id,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(
        cls,
        data: "EnhancementAssignment | Mapping[str, Any]",
    ) -> "EnhancementAssignment":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("EnhancementAssignment data must be a mapping or EnhancementAssignment.")
        return cls(
            assignment_id=str(data.get("assignment_id", "") or ""),
            enhancement_name=str(data.get("enhancement_name", "") or ""),
            target_entry_id=str(data.get("target_entry_id", "") or ""),
            detachment_selection_id=data.get("detachment_selection_id"),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class RosterEntry:
    """Build-side unit entry before runtime units are materialized."""

    entry_id: str
    name: str
    count: int = 1
    detachment_selection_id: str | None = None
    wargear: list[str] = field(default_factory=list)
    enhancement_names: list[str] = field(default_factory=list)
    is_warlord: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.entry_id = _required_text(self.entry_id, field_name="entry_id")
        self.name = _required_text(self.name, field_name="name")
        self.count = _positive_int(self.count, field_name="count")
        self.detachment_selection_id = _optional_text(self.detachment_selection_id)
        self.wargear = _string_list(self.wargear)
        self.enhancement_names = _string_list(self.enhancement_names)
        self.is_warlord = bool(self.is_warlord)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "name": self.name,
            "count": self.count,
            "detachment_selection_id": self.detachment_selection_id,
            "wargear": list(self.wargear),
            "enhancement_names": list(self.enhancement_names),
            "is_warlord": self.is_warlord,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(
        cls,
        data: "RosterEntry | Mapping[str, Any]",
    ) -> "RosterEntry":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("RosterEntry data must be a mapping or RosterEntry.")
        enhancement_names = data.get("enhancement_names")
        if not enhancement_names:
            enhancement_names = data.get("enhancements", [])
        return cls(
            entry_id=str(data.get("entry_id", "") or ""),
            name=str(data.get("name", "") or ""),
            count=data.get("count", 1),
            detachment_selection_id=data.get("detachment_selection_id"),
            wargear=list(data.get("wargear", []) or []),
            enhancement_names=list(enhancement_names or []),
            is_warlord=bool(data.get("is_warlord", False)),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class ArmyBlueprint:
    """A build-time army specification independent from runtime Army state."""

    faction: str
    points_limit: int = 2000
    battle_size: str | None = None
    detachments: list[DetachmentSelection] = field(default_factory=list)
    detachment_points_budget: int | None = None
    unit_entries: list[RosterEntry] = field(default_factory=list)
    enhancement_assignments: list[EnhancementAssignment] = field(default_factory=list)
    attachment_bindings: list[AttachmentBinding] = field(default_factory=list)
    force_disposition: str | None = None
    allowed_force_dispositions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.faction = _required_text(self.faction, field_name="faction")
        self.points_limit = _positive_int(self.points_limit, field_name="points_limit")
        self.battle_size = _optional_text(self.battle_size)
        self.detachments = [
            DetachmentSelection.from_dict(value) for value in list(self.detachments or [])
        ]
        self.detachment_points_budget = _optional_non_negative_int(
            self.detachment_points_budget,
            field_name="detachment_points_budget",
        )
        self.unit_entries = [RosterEntry.from_dict(value) for value in list(self.unit_entries or [])]
        self.enhancement_assignments = [
            EnhancementAssignment.from_dict(value)
            for value in list(self.enhancement_assignments or [])
        ]
        self.attachment_bindings = [
            AttachmentBinding.from_dict(value) for value in list(self.attachment_bindings or [])
        ]
        self.force_disposition = _optional_text(self.force_disposition)
        self.allowed_force_dispositions = _string_list(self.allowed_force_dispositions)
        self.metadata = dict(self.metadata or {})

    @property
    def primary_detachment_type(self) -> str | None:
        if not self.detachments:
            return None
        return self.detachments[0].detachment_type

    @property
    def army_blueprint_hash(self) -> str:
        digest = hashlib.sha256(_canonical_json(self.to_dict()).encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "faction": self.faction,
            "points_limit": self.points_limit,
            "battle_size": self.battle_size,
            "detachments": [item.to_dict() for item in list(self.detachments or [])],
            "detachment_points_budget": self.detachment_points_budget,
            "unit_entries": [item.to_dict() for item in list(self.unit_entries or [])],
            "enhancement_assignments": [
                item.to_dict() for item in list(self.enhancement_assignments or [])
            ],
            "attachment_bindings": [
                item.to_dict() for item in list(self.attachment_bindings or [])
            ],
            "force_disposition": self.force_disposition,
            "allowed_force_dispositions": list(self.allowed_force_dispositions),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(
        cls,
        data: "ArmyBlueprint | Mapping[str, Any]",
    ) -> "ArmyBlueprint":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("ArmyBlueprint data must be a mapping or ArmyBlueprint.")
        return cls(
            faction=str(data.get("faction", "") or ""),
            points_limit=data.get("points_limit", 2000),
            battle_size=data.get("battle_size"),
            detachments=list(data.get("detachments", []) or []),
            detachment_points_budget=data.get("detachment_points_budget"),
            unit_entries=list(data.get("unit_entries", []) or []),
            enhancement_assignments=list(data.get("enhancement_assignments", []) or []),
            attachment_bindings=list(data.get("attachment_bindings", []) or []),
            force_disposition=data.get("force_disposition"),
            allowed_force_dispositions=list(data.get("allowed_force_dispositions", []) or []),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class ValidatedMuster:
    """Validated build-side muster payload consumed by runtime mustering."""

    blueprint: ArmyBlueprint
    faction_id: str
    detachment_points_spent: int = 0
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.blueprint = ArmyBlueprint.from_dict(self.blueprint)
        self.faction_id = _required_text(self.faction_id, field_name="faction_id")
        self.detachment_points_spent = _optional_non_negative_int(
            self.detachment_points_spent,
            field_name="detachment_points_spent",
        ) or 0
        self.warnings = _string_list(self.warnings)

    @property
    def primary_detachment_type(self) -> str | None:
        return self.blueprint.primary_detachment_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint": self.blueprint.to_dict(),
            "faction_id": self.faction_id,
            "detachment_points_spent": self.detachment_points_spent,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(
        cls,
        data: "ValidatedMuster | Mapping[str, Any]",
    ) -> "ValidatedMuster":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("ValidatedMuster data must be a mapping or ValidatedMuster.")
        return cls(
            blueprint=data.get("blueprint", {}),
            faction_id=str(data.get("faction_id", "") or ""),
            detachment_points_spent=data.get("detachment_points_spent", 0),
            warnings=list(data.get("warnings", []) or []),
        )


__all__ = [
    "ArmyBlueprint",
    "DetachmentSelection",
    "EnhancementAssignment",
    "RosterEntry",
    "ValidatedMuster",
]
