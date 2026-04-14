"""Schema metadata for deterministic roster capability profiles."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): json_safe(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [json_safe(inner) for inner in value]
    if isinstance(value, set):
        items = [json_safe(inner) for inner in value]
        return sorted(items, key=lambda item: str(item))
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class CapabilityFeatureDefinition:
    name: str
    kind: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": str(self.name or ""),
            "kind": str(self.kind or ""),
            "description": str(self.description or ""),
        }


@dataclass(frozen=True)
class BuildCapabilitySchema:
    capability_schema_id: str
    aggregate_count_names: tuple[str, ...]
    pressure_metric_names: tuple[str, ...]
    feature_definitions: tuple[CapabilityFeatureDefinition, ...]

    @property
    def feature_names(self) -> tuple[str, ...]:
        return tuple(feature.name for feature in self.feature_definitions)

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_schema_id": str(self.capability_schema_id or ""),
            "aggregate_count_names": list(self.aggregate_count_names),
            "pressure_metric_names": list(self.pressure_metric_names),
            "feature_definitions": [feature.to_dict() for feature in self.feature_definitions],
        }


DEFAULT_BUILD_CAPABILITY_SCHEMA = BuildCapabilitySchema(
    capability_schema_id="capability_schema:build_capability_v1",
    aggregate_count_names=(
        "unit_count",
        "detachment_count",
        "enhancement_count",
        "attachment_binding_count",
        "leader_binding_count",
        "support_binding_count",
        "battleline_unit_count",
        "character_unit_count",
        "vehicle_or_monster_unit_count",
        "towering_unit_count",
        "titanic_unit_count",
        "deep_strike_unit_count",
        "infiltrator_unit_count",
        "scout_unit_count",
        "attachment_capable_unit_count",
    ),
    pressure_metric_names=(
        "melee_pressure",
        "ranged_pressure",
        "short_range_pressure",
        "long_range_firepower",
        "indirect_firepower",
        "anti_tank_pressure",
        "action_capacity_total",
        "melee_share",
    ),
    feature_definitions=(
        CapabilityFeatureDefinition(
            name="terrain_occlusion_reliance",
            kind="score",
            description=(
                "How strongly the roster benefits from safe staging and obscuring lanes "
                "to deliver short-range or melee threats."
            ),
        ),
        CapabilityFeatureDefinition(
            name="elevated_fire_affinity",
            kind="score",
            description=(
                "How naturally the roster converts long-range, indirect, or towering "
                "shooting presence into table control."
            ),
        ),
        CapabilityFeatureDefinition(
            name="deployment_reveal_pressure",
            kind="score",
            description=(
                "How much the roster can pressure deployment and reserve declarations via "
                "forward deploy, scouting, or reserve-entry threats."
            ),
        ),
        CapabilityFeatureDefinition(
            name="charge_delivery_reliance",
            kind="score",
            description=(
                "How much the roster's payoff depends on delivering melee threats through "
                "charges, pregame moves, or reserve positioning."
            ),
        ),
        CapabilityFeatureDefinition(
            name="objective_spread_tolerance",
            kind="score",
            description=(
                "How well the roster can spread across multiple objectives without "
                "collapsing its scoring plan."
            ),
        ),
        CapabilityFeatureDefinition(
            name="attachment_dependency_risk",
            kind="score",
            description=(
                "How much the roster depends on leader/support pairings or bound "
                "enhancement packages to function at intended efficiency."
            ),
        ),
        CapabilityFeatureDefinition(
            name="controller_complexity_index",
            kind="score",
            description=(
                "A generic control burden estimate derived from unit count, detachments, "
                "pregame options, and attachment/enhancement state."
            ),
        ),
        CapabilityFeatureDefinition(
            name="mission_action_flex_capacity",
            kind="score",
            description=(
                "How much spare mission-action bandwidth the roster has through cheap, "
                "mobile, or self-sufficient pieces."
            ),
        ),
        CapabilityFeatureDefinition(
            name="detachment_diversity_index",
            kind="score",
            description=(
                "How much the roster spreads its authored identity across multiple "
                "detachments instead of a single detachment plan."
            ),
        ),
        CapabilityFeatureDefinition(
            name="towering_exposure_index",
            kind="score",
            description=(
                "How exposed the roster is to visibility and footprint constraints from "
                "towering or otherwise giant anchors."
            ),
        ),
    ),
)


__all__ = [
    "BuildCapabilitySchema",
    "CapabilityFeatureDefinition",
    "DEFAULT_BUILD_CAPABILITY_SCHEMA",
    "canonical_json",
    "json_safe",
]
