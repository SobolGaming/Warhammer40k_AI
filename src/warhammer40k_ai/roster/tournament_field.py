"""Tournament field-distribution schema for roster evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import gcd
import hashlib
from typing import Any, Mapping

from .army_build import ArmyBlueprint
from .build_capability_schema import canonical_json, json_safe

FIELD_DISTRIBUTION_SCHEMA_ID = "field_distribution_schema:tournament_field_v1"


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _required_text(value: object, *, field_name: str) -> str:
    text = _optional_text(value)
    if text is not None:
        return text
    raise ValueError(f"{field_name} is required.")


def _optional_positive_int(value: object, *, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    number = int(value)
    if number <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return number


def _positive_float(value: object, *, field_name: str) -> float:
    number = float(value)
    if number <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return number


def _stable_dict(value: object, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping.")
    return dict(json_safe(dict(value)))


def _sorted_unique_texts(values: object) -> tuple[str, ...]:
    normalized = {
        _required_text(value, field_name="archetype_tag")
        for value in tuple(values or ())
    }
    return tuple(sorted(normalized))


def _normalized_ratios(weights: tuple[tuple[str, float], ...]) -> tuple[tuple[str, int, int], ...]:
    if not weights:
        return ()
    scale = 1_000_000
    integers: list[tuple[str, int]] = []
    for key, weight in weights:
        scaled = max(1, int(round(weight * scale)))
        integers.append((key, scaled))
    divisor = 0
    for _key, scaled in integers:
        divisor = scaled if divisor == 0 else gcd(divisor, scaled)
    reduced = [(key, scaled // max(divisor, 1)) for key, scaled in integers]
    total = sum(value for _key, value in reduced)
    return tuple((key, value, total) for key, value in reduced)


def _hash_field_distribution(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:16]
    return f"field_distribution:{digest}"


@dataclass(frozen=True)
class WeightedChoice:
    choice_id: str
    weight: float
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "choice_id", _required_text(self.choice_id, field_name="choice_id"))
        object.__setattr__(self, "weight", _positive_float(self.weight, field_name="weight"))
        object.__setattr__(self, "label", _optional_text(self.label))
        object.__setattr__(
            self,
            "metadata",
            _stable_dict(self.metadata, field_name=f"{self.choice_id}.metadata"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "choice_id": self.choice_id,
            "weight": self.weight,
            "label": self.label,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: "WeightedChoice | Mapping[str, Any]") -> "WeightedChoice":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("WeightedChoice data must be a mapping or WeightedChoice.")
        return cls(
            choice_id=data.get("choice_id", ""),
            weight=data.get("weight", 0),
            label=data.get("label"),
            metadata=data.get("metadata"),
        )


@dataclass(frozen=True)
class OpponentSlice:
    slice_id: str
    weight: float
    label: str | None = None
    faction: str | None = None
    detachment_type: str | None = None
    archetype_tags: tuple[str, ...] = ()
    army_blueprint: ArmyBlueprint | None = None
    build_capability_profile_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "slice_id", _required_text(self.slice_id, field_name="slice_id"))
        object.__setattr__(self, "weight", _positive_float(self.weight, field_name="weight"))
        object.__setattr__(self, "label", _optional_text(self.label))
        object.__setattr__(self, "faction", _optional_text(self.faction))
        object.__setattr__(self, "detachment_type", _optional_text(self.detachment_type))
        object.__setattr__(self, "archetype_tags", _sorted_unique_texts(self.archetype_tags))
        blueprint = self.army_blueprint
        if blueprint is not None:
            blueprint = ArmyBlueprint.from_dict(blueprint)
        object.__setattr__(self, "army_blueprint", blueprint)
        object.__setattr__(
            self,
            "build_capability_profile_id",
            _optional_text(self.build_capability_profile_id),
        )
        object.__setattr__(
            self,
            "metadata",
            _stable_dict(self.metadata, field_name=f"{self.slice_id}.metadata"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "slice_id": self.slice_id,
            "weight": self.weight,
            "label": self.label,
            "faction": self.faction,
            "detachment_type": self.detachment_type,
            "archetype_tags": list(self.archetype_tags),
            "army_blueprint": (
                None if self.army_blueprint is None else self.army_blueprint.to_dict()
            ),
            "build_capability_profile_id": self.build_capability_profile_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: "OpponentSlice | Mapping[str, Any]") -> "OpponentSlice":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("OpponentSlice data must be a mapping or OpponentSlice.")
        return cls(
            slice_id=data.get("slice_id", ""),
            weight=data.get("weight", 0),
            label=data.get("label"),
            faction=data.get("faction"),
            detachment_type=data.get("detachment_type"),
            archetype_tags=tuple(data.get("archetype_tags", ()) or ()),
            army_blueprint=data.get("army_blueprint"),
            build_capability_profile_id=data.get("build_capability_profile_id"),
            metadata=data.get("metadata"),
        )


def normalize_weighted_choices(items: tuple[WeightedChoice, ...]) -> tuple[dict[str, object], ...]:
    ratios = _normalized_ratios(tuple((item.choice_id, item.weight) for item in items))
    ratio_lookup = {
        choice_id: {
            "normalized_weight_numerator": numerator,
            "normalized_weight_denominator": denominator,
            "weight": numerator / denominator,
        }
        for choice_id, numerator, denominator in ratios
    }
    normalized: list[dict[str, object]] = []
    for item in items:
        entry = item.to_dict()
        entry.update(ratio_lookup[item.choice_id])
        normalized.append(entry)
    return tuple(normalized)


def normalize_opponent_slices(items: tuple[OpponentSlice, ...]) -> tuple[dict[str, object], ...]:
    ratios = _normalized_ratios(tuple((item.slice_id, item.weight) for item in items))
    ratio_lookup = {
        slice_id: {
            "normalized_weight_numerator": numerator,
            "normalized_weight_denominator": denominator,
            "weight": numerator / denominator,
        }
        for slice_id, numerator, denominator in ratios
    }
    normalized: list[dict[str, object]] = []
    for item in items:
        entry = item.to_dict()
        entry["army_blueprint_hash"] = (
            None if item.army_blueprint is None else item.army_blueprint.army_blueprint_hash
        )
        entry.update(ratio_lookup[item.slice_id])
        normalized.append(entry)
    return tuple(normalized)


@dataclass(frozen=True)
class TournamentFieldDistribution:
    rules_bundle_id: str
    event_policy_id: str
    terrain_layout_pack_id: str
    opponent_slices: tuple[OpponentSlice, ...]
    mission_distribution: tuple[WeightedChoice, ...]
    deployment_distribution: tuple[WeightedChoice, ...]
    terrain_distribution: tuple[WeightedChoice, ...]
    field_distribution_schema_id: str = FIELD_DISTRIBUTION_SCHEMA_ID
    field_distribution_id: str = ""
    round_count: int | None = None
    event_format_name: str | None = None
    pairing_metadata: dict[str, Any] = field(default_factory=dict)
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "field_distribution_schema_id",
            _required_text(
                self.field_distribution_schema_id,
                field_name="field_distribution_schema_id",
            ),
        )
        object.__setattr__(
            self,
            "rules_bundle_id",
            _required_text(self.rules_bundle_id, field_name="rules_bundle_id"),
        )
        object.__setattr__(
            self,
            "event_policy_id",
            _required_text(self.event_policy_id, field_name="event_policy_id"),
        )
        object.__setattr__(
            self,
            "terrain_layout_pack_id",
            _required_text(
                self.terrain_layout_pack_id,
                field_name="terrain_layout_pack_id",
            ),
        )
        opponent_slices = tuple(
            sorted(
                (OpponentSlice.from_dict(value) for value in tuple(self.opponent_slices or ())),
                key=lambda item: item.slice_id,
            )
        )
        mission_distribution = tuple(
            sorted(
                (WeightedChoice.from_dict(value) for value in tuple(self.mission_distribution or ())),
                key=lambda item: item.choice_id,
            )
        )
        deployment_distribution = tuple(
            sorted(
                (
                    WeightedChoice.from_dict(value)
                    for value in tuple(self.deployment_distribution or ())
                ),
                key=lambda item: item.choice_id,
            )
        )
        terrain_distribution = tuple(
            sorted(
                (WeightedChoice.from_dict(value) for value in tuple(self.terrain_distribution or ())),
                key=lambda item: item.choice_id,
            )
        )
        if not opponent_slices:
            raise ValueError("opponent_slices must contain at least one weighted slice.")
        if not mission_distribution:
            raise ValueError("mission_distribution must contain at least one weighted choice.")
        if not deployment_distribution:
            raise ValueError("deployment_distribution must contain at least one weighted choice.")
        if not terrain_distribution:
            raise ValueError("terrain_distribution must contain at least one weighted choice.")
        object.__setattr__(self, "opponent_slices", opponent_slices)
        object.__setattr__(self, "mission_distribution", mission_distribution)
        object.__setattr__(self, "deployment_distribution", deployment_distribution)
        object.__setattr__(self, "terrain_distribution", terrain_distribution)
        object.__setattr__(
            self,
            "round_count",
            _optional_positive_int(self.round_count, field_name="round_count"),
        )
        object.__setattr__(self, "event_format_name", _optional_text(self.event_format_name))
        object.__setattr__(
            self,
            "pairing_metadata",
            _stable_dict(self.pairing_metadata, field_name="pairing_metadata"),
        )
        object.__setattr__(self, "notes", _optional_text(self.notes))
        object.__setattr__(self, "metadata", _stable_dict(self.metadata, field_name="metadata"))
        field_distribution_id = _optional_text(self.field_distribution_id)
        if field_distribution_id is None:
            field_distribution_id = _hash_field_distribution(self._hash_payload())
        object.__setattr__(self, "field_distribution_id", field_distribution_id)

    def _hash_payload(self) -> dict[str, object]:
        return {
            "field_distribution_schema_id": self.field_distribution_schema_id,
            "field_distribution_id": "",
            "rules_bundle_id": self.rules_bundle_id,
            "event_policy_id": self.event_policy_id,
            "terrain_layout_pack_id": self.terrain_layout_pack_id,
            "opponent_slices": [dict(item) for item in self.normalized_opponent_slices],
            "mission_distribution": [dict(item) for item in self.normalized_mission_distribution],
            "deployment_distribution": [
                dict(item) for item in self.normalized_deployment_distribution
            ],
            "terrain_distribution": [dict(item) for item in self.normalized_terrain_distribution],
            "round_count": self.round_count,
            "event_format_name": self.event_format_name,
            "pairing_metadata": dict(self.pairing_metadata),
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "field_distribution_schema_id": self.field_distribution_schema_id,
            "field_distribution_id": self.field_distribution_id,
            "rules_bundle_id": self.rules_bundle_id,
            "event_policy_id": self.event_policy_id,
            "terrain_layout_pack_id": self.terrain_layout_pack_id,
            "opponent_slices": [slice_.to_dict() for slice_ in self.opponent_slices],
            "mission_distribution": [item.to_dict() for item in self.mission_distribution],
            "deployment_distribution": [item.to_dict() for item in self.deployment_distribution],
            "terrain_distribution": [item.to_dict() for item in self.terrain_distribution],
            "round_count": self.round_count,
            "event_format_name": self.event_format_name,
            "pairing_metadata": dict(self.pairing_metadata),
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    @property
    def normalized_opponent_slices(self) -> tuple[dict[str, object], ...]:
        return normalize_opponent_slices(self.opponent_slices)

    @property
    def normalized_mission_distribution(self) -> tuple[dict[str, object], ...]:
        return normalize_weighted_choices(self.mission_distribution)

    @property
    def normalized_deployment_distribution(self) -> tuple[dict[str, object], ...]:
        return normalize_weighted_choices(self.deployment_distribution)

    @property
    def normalized_terrain_distribution(self) -> tuple[dict[str, object], ...]:
        return normalize_weighted_choices(self.terrain_distribution)

    @classmethod
    def from_dict(
        cls,
        data: "TournamentFieldDistribution | Mapping[str, Any]",
    ) -> "TournamentFieldDistribution":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError(
                "TournamentFieldDistribution data must be a mapping or "
                "TournamentFieldDistribution."
            )
        return cls(
            field_distribution_schema_id=data.get(
                "field_distribution_schema_id",
                FIELD_DISTRIBUTION_SCHEMA_ID,
            ),
            field_distribution_id=data.get("field_distribution_id", ""),
            rules_bundle_id=data.get("rules_bundle_id", ""),
            event_policy_id=data.get("event_policy_id", ""),
            terrain_layout_pack_id=data.get("terrain_layout_pack_id", ""),
            opponent_slices=tuple(data.get("opponent_slices", ()) or ()),
            mission_distribution=tuple(data.get("mission_distribution", ()) or ()),
            deployment_distribution=tuple(data.get("deployment_distribution", ()) or ()),
            terrain_distribution=tuple(data.get("terrain_distribution", ()) or ()),
            round_count=data.get("round_count"),
            event_format_name=data.get("event_format_name"),
            pairing_metadata=data.get("pairing_metadata"),
            notes=data.get("notes"),
            metadata=data.get("metadata"),
        )


__all__ = [
    "FIELD_DISTRIBUTION_SCHEMA_ID",
    "OpponentSlice",
    "TournamentFieldDistribution",
    "WeightedChoice",
    "normalize_opponent_slices",
    "normalize_weighted_choices",
]
