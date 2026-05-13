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


@dataclass(frozen=True)
class BuildCapabilityExtensionGroup:
    extension_group_id: str
    feature_definitions: tuple[CapabilityFeatureDefinition, ...]
    source_provenance: tuple[dict[str, object], ...]
    activation: str = "explicit"

    @property
    def feature_names(self) -> tuple[str, ...]:
        return tuple(feature.name for feature in self.feature_definitions)

    def to_dict(self) -> dict[str, object]:
        return {
            "extension_group_id": str(self.extension_group_id or ""),
            "feature_definitions": [feature.to_dict() for feature in self.feature_definitions],
            "source_provenance": [json_safe(source) for source in self.source_provenance],
            "activation": str(self.activation or ""),
        }


_BUILD_CAPABILITY_V1_FEATURE_DEFINITIONS = (
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
)

_BUILD_CAPABILITY_V2_FEATURE_DEFINITIONS = _BUILD_CAPABILITY_V1_FEATURE_DEFINITIONS + (
    CapabilityFeatureDefinition(
        name="charge_option_flexibility",
        kind="score",
        description=(
            "How much the roster can exploit flexible charge routing and target-binding "
            "choices once delivery has succeeded."
        ),
    ),
    CapabilityFeatureDefinition(
        name="ingress_charge_conversion",
        kind="score",
        description=(
            "How efficiently reserve-entry threat converts into near-term charge pressure "
            "under the active ingress exclusion geometry."
        ),
    ),
    CapabilityFeatureDefinition(
        name="fight_order_resilience",
        kind="score",
        description=(
            "How well the roster preserves value when melee fight-order priority or "
            "interrupt timing changes across the active rules bundle."
        ),
    ),
    CapabilityFeatureDefinition(
        name="overrun_chain_potential",
        kind="score",
        description=(
            "How much the roster can continue extracting melee value after an initial "
            "engagement collapses and a follow-on pile-in becomes available."
        ),
    ),
    CapabilityFeatureDefinition(
        name="consolidate_objective_swing",
        kind="score",
        description=(
            "How strongly end-of-fight consolidates can convert into objective steals, "
            "denial swings, or late activation pressure."
        ),
    ),
    CapabilityFeatureDefinition(
        name="engagement_footprint_pressure",
        kind="score",
        description=(
            "How strongly the roster can exploit enlarged engagement footprints or broad "
            "melee threat bubbles to pin space."
        ),
    ),
    CapabilityFeatureDefinition(
        name="transport_pop_punish_index",
        kind="score",
        description=(
            "How well the roster can capitalize on transport-destruction fight states and "
            "newly exposed passengers."
        ),
    ),
)

_MAY_2026_FACTION_FOCUS_EXTENSION_FEATURE_DEFINITIONS = (
    CapabilityFeatureDefinition(
        name="detection_marker_coverage",
        kind="score",
        description=(
            "How broadly the roster can project value from generic detection-marker "
            "style visibility range changes."
        ),
    ),
    CapabilityFeatureDefinition(
        name="anti_hidden_projection",
        kind="score",
        description=(
            "How well the roster can combine reach, marker support, and ranged pressure "
            "to contest Hidden-style targets."
        ),
    ),
    CapabilityFeatureDefinition(
        name="hidden_persistence_value",
        kind="score",
        description=(
            "How much value the roster can preserve from Hidden-style protection while "
            "still contributing to board state."
        ),
    ),
    CapabilityFeatureDefinition(
        name="keyword_mutation_density",
        kind="score",
        description=(
            "How much the roster's deterministic evaluation depends on runtime keyword "
            "mutation, upgrade payloads, or detachment-authored keyword changes."
        ),
    ),
    CapabilityFeatureDefinition(
        name="cleave_horde_clearance",
        kind="score",
        description=(
            "How naturally melee pressure and model volume convert into horde-clearance "
            "value under a generic Cleave-like attack-dice modifier."
        ),
    ),
    CapabilityFeatureDefinition(
        name="heavy_stationary_fire_quality",
        kind="score",
        description=(
            "How much the roster benefits from remaining unengaged, not being set up this "
            "turn, and limiting model movement before shooting."
        ),
    ),
    CapabilityFeatureDefinition(
        name="mobile_terrain_traversal_value",
        kind="score",
        description=(
            "How much mission and movement value the roster can extract from generic "
            "Mobile-style terrain traversal."
        ),
    ),
    CapabilityFeatureDefinition(
        name="reactive_move_density",
        kind="score",
        description=(
            "How much roster value is exposed to reusable reactive-move decision points."
        ),
    ),
    CapabilityFeatureDefinition(
        name="heroic_intervention_density",
        kind="score",
        description=(
            "How strongly the roster can exploit modal Heroic Intervention or countercharge "
            "decision surfaces."
        ),
    ),
    CapabilityFeatureDefinition(
        name="must_fight_next_leverage",
        kind="score",
        description=(
            "How much the roster can gain from scheduler-visible must-fight-next constraints."
        ),
    ),
    CapabilityFeatureDefinition(
        name="action_after_advance_fallback_flex",
        kind="score",
        description=(
            "How much mission-action value remains available when units advance, fall back, "
            "or otherwise need movement-flex exceptions."
        ),
    ),
    CapabilityFeatureDefinition(
        name="reserve_reposition_flex",
        kind="score",
        description=(
            "How much the roster can exploit reserve-entry, reserve-exit, and reposition "
            "decision surfaces."
        ),
    ),
    CapabilityFeatureDefinition(
        name="upgrade_cardinality_complexity",
        kind="score",
        description=(
            "How much the roster's build-side semantics depend on multi-target, unit/model, "
            "or weapon-profile upgrade assignment shape."
        ),
    ),
    CapabilityFeatureDefinition(
        name="battle_shock_persistence_leverage",
        kind="score",
        description=(
            "How much the roster can exploit persistent tactical-status state instead of "
            "assuming automatic Command phase cleanup."
        ),
    ),
)


BUILD_CAPABILITY_SCHEMA_V1 = BuildCapabilitySchema(
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
    feature_definitions=_BUILD_CAPABILITY_V1_FEATURE_DEFINITIONS,
)

BUILD_CAPABILITY_SCHEMA_V2 = BuildCapabilitySchema(
    capability_schema_id="capability_schema:build_capability_v2",
    aggregate_count_names=BUILD_CAPABILITY_SCHEMA_V1.aggregate_count_names,
    pressure_metric_names=BUILD_CAPABILITY_SCHEMA_V1.pressure_metric_names,
    feature_definitions=_BUILD_CAPABILITY_V2_FEATURE_DEFINITIONS,
)

BUILD_CAPABILITY_EXTENSION_11E_FACTION_FOCUS_MAY2026 = BuildCapabilityExtensionGroup(
    extension_group_id="capability_extension:11e_faction_focus_may2026",
    feature_definitions=_MAY_2026_FACTION_FOCUS_EXTENSION_FEATURE_DEFINITIONS,
    source_provenance=(
        {
            "source_id": "wc_2026_05_faction_focus_previews",
            "label": "May 2026 faction-focus preview mechanics",
            "preview_only": True,
            "mechanics_observed": [
                "detection_markers",
                "hidden_preserving_shooting",
                "cleave",
                "updated_heavy",
                "mobile",
                "reactive_movement",
                "heroic_intervention_modes",
                "must_fight_next",
                "upgrade_cardinality",
                "battle_shock_persistence",
            ],
        },
    ),
    activation="explicit",
)

BUILD_CAPABILITY_EXTENSION_GROUPS = (
    BUILD_CAPABILITY_EXTENSION_11E_FACTION_FOCUS_MAY2026,
)
_BUILD_CAPABILITY_EXTENSION_GROUPS_BY_ID = {
    str(group.extension_group_id or ""): group
    for group in BUILD_CAPABILITY_EXTENSION_GROUPS
}


def resolve_build_capability_extension_group(
    extension_group: BuildCapabilityExtensionGroup | str,
) -> BuildCapabilityExtensionGroup:
    if isinstance(extension_group, BuildCapabilityExtensionGroup):
        return extension_group
    extension_group_id = str(extension_group or "").strip()
    if extension_group_id in _BUILD_CAPABILITY_EXTENSION_GROUPS_BY_ID:
        return _BUILD_CAPABILITY_EXTENSION_GROUPS_BY_ID[extension_group_id]
    raise ValueError(f"Unknown build capability extension group: {extension_group_id!r}.")


def resolve_build_capability_extension_groups(
    extension_groups: tuple[BuildCapabilityExtensionGroup | str, ...]
    | list[BuildCapabilityExtensionGroup | str]
    | None,
) -> tuple[BuildCapabilityExtensionGroup, ...]:
    if not extension_groups:
        return ()
    resolved: list[BuildCapabilityExtensionGroup] = []
    seen: set[str] = set()
    for group in extension_groups:
        resolved_group = resolve_build_capability_extension_group(group)
        group_id = str(resolved_group.extension_group_id or "")
        if not group_id or group_id in seen:
            continue
        seen.add(group_id)
        resolved.append(resolved_group)
    return tuple(sorted(resolved, key=lambda item: item.extension_group_id))

DEFAULT_BUILD_CAPABILITY_SCHEMA = BUILD_CAPABILITY_SCHEMA_V1


__all__ = [
    "BUILD_CAPABILITY_EXTENSION_11E_FACTION_FOCUS_MAY2026",
    "BUILD_CAPABILITY_EXTENSION_GROUPS",
    "BUILD_CAPABILITY_SCHEMA_V1",
    "BUILD_CAPABILITY_SCHEMA_V2",
    "BuildCapabilityExtensionGroup",
    "BuildCapabilitySchema",
    "CapabilityFeatureDefinition",
    "DEFAULT_BUILD_CAPABILITY_SCHEMA",
    "canonical_json",
    "json_safe",
    "resolve_build_capability_extension_group",
    "resolve_build_capability_extension_groups",
]
