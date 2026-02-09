from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import re


@dataclass(frozen=True)
class EnhancementToolDescriptor:
    enhancement_id: str
    name: str
    timing: str
    target: str
    duration: str
    effect: str
    range_in: Optional[float] = None
    once_per_battle: bool = False
    effect_params: dict[str, Any] = field(default_factory=dict)


def _normalize_name(name: str) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


_GORETRACK_ONSLAUGHT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010086002": EnhancementToolDescriptor(
        enhancement_id="000010086002",
        name="Murderous Onslaught",
        timing="on_disembark",
        target="bearer_unit",
        duration="until_end_of_turn",
        effect="prevent_overwatch",
    ),
    "000010086003": EnhancementToolDescriptor(
        enhancement_id="000010086003",
        name="Aggressive Deployment",
        timing="declare_battle_formations",
        target="dedicated_transport_with_bearer_embarked",
        duration="scout_step",
        effect="grant_scouts",
        effect_params={"scouts_distance": 9.0},
    ),
    "000010086004": EnhancementToolDescriptor(
        enhancement_id="000010086004",
        name="Unleash Hell",
        timing="start_of_shooting_phase",
        target="friendly_vehicle_within_range_or_bearer_transport",
        duration="until_end_of_phase",
        effect="post_shoot_suppression",
        range_in=6.0,
        effect_params={"suppression_excludes_monsters_vehicles": False},
    ),
    "000010086005": EnhancementToolDescriptor(
        enhancement_id="000010086005",
        name="Infernal Infusion",
        timing="start_of_fight_phase",
        target="bearer_unit",
        duration="until_end_of_phase",
        effect="fights_first",
        once_per_battle=True,
    ),
}

_GORETRACK_ONSLAUGHT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GORETRACK_ONSLAUGHT_DESCRIPTORS.values()
}

_DAEMONIC_INCURSION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008438002": EnhancementToolDescriptor(
        enhancement_id="000008438002",
        name="A'rgath, the King of Blades",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_melee_attacks_strength_bonus_shadow",
        effect_params={"base_attacks_bonus": 1, "base_strength_bonus": 1, "shadow_multiplier": 2},
    ),
    "000008438003": EnhancementToolDescriptor(
        enhancement_id="000008438003",
        name="Soulstealer",
        timing="on_melee_model_destroyed",
        target="bearer",
        duration="instant",
        effect="heal_on_kill_test",
        effect_params={"roll": "D6", "shadow_bonus": 1, "threshold": 4, "heal": 1},
    ),
    "000008438004": EnhancementToolDescriptor(
        enhancement_id="000008438004",
        name="The Endless Gift",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_fnp",
        effect_params={"fnp": 5},
    ),
    "000008438005": EnhancementToolDescriptor(
        enhancement_id="000008438005",
        name="The Everstave",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_ranged_strength_range_bonus_shadow",
        effect_params={"base_strength_bonus": 1, "base_range_bonus": 3, "shadow_multiplier": 2},
    ),
}

_DAEMONIC_INCURSION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DAEMONIC_INCURSION_DESCRIPTORS.values()
}

_PLAGUE_LEGION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009819002": EnhancementToolDescriptor(
        enhancement_id="000009819002",
        name="Cankerblight",
        timing="on_enemy_battleshock_failed",
        target="enemy_unit_within_range",
        duration="instant",
        effect="destroy_model_no_terror",
        range_in=6.0,
        effect_params={"exclude_monsters_vehicles": True, "suppresses_daemonic_terror": True},
    ),
    "000009819003": EnhancementToolDescriptor(
        enhancement_id="000009819003",
        name="Maggot Maws",
        timing="shooting_phase",
        target="enemy_unit_within_range",
        duration="instant",
        effect="battleshock_then_mortal_wounds",
        range_in=6.0,
        effect_params={"mortal_wound_roll": "D6>=3 -> D3", "suppresses_daemonic_terror": True},
    ),
}

_PLAGUE_LEGION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _PLAGUE_LEGION_DESCRIPTORS.values()
}

_SCINTILLATING_LEGION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009810002": EnhancementToolDescriptor(
        enhancement_id="000009810002",
        name="Inescapable Eye",
        timing="command_phase_start",
        target="bearer",
        duration="instant",
        effect="gain_flux_token_if_opponent_has_tokens",
        effect_params={"amount": 1, "requires_bearer_on_battlefield": True},
    ),
    "000009810003": EnhancementToolDescriptor(
        enhancement_id="000009810003",
        name="Infernal Puppeteer",
        timing="selected_to_shoot",
        target="friendly_tzeentch_legiones_unit_within_range",
        duration="until_end_of_activation",
        effect="origin_measurement_override",
        range_in=9.0,
        effect_params={"origin_mode": "infernal_puppeteer", "requires_bearer_on_battlefield": True},
    ),
    "000009810004": EnhancementToolDescriptor(
        enhancement_id="000009810004",
        name="Neverblade",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_melee_profile_bonus",
        effect_params={"strength_bonus": 2, "attacks_bonus": 1, "ap_bonus": 1, "hit_bonus": 1},
    ),
    "000009810005": EnhancementToolDescriptor(
        enhancement_id="000009810005",
        name="Improbable Shield (Aura)",
        timing="passive_aura",
        target="friendly_tzeentch_legiones_within_range",
        duration="constant",
        effect="grant_fnp_vs_psychic_mortal",
        range_in=6.0,
        effect_params={"fnp": 4, "condition": "against psychic attacks and mortal wounds"},
    ),
}

_SCINTILLATING_LEGION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SCINTILLATING_LEGION_DESCRIPTORS.values()
}

_GRAND_COVEN_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010193002": EnhancementToolDescriptor(
        enhancement_id="000010193002",
        name="Lord of Forbidden Lore",
        timing="while_manifesting_ritual",
        target="bearer",
        duration="instant",
        effect="ritual_range_bonus",
        effect_params={"ritual_range_bonus": 6},
    ),
    "000010193003": EnhancementToolDescriptor(
        enhancement_id="000010193003",
        name="Incandaeum",
        timing="while_selecting_ritual",
        target="bearer",
        duration="once_per_battle",
        effect="doombolt_repeat_override",
        once_per_battle=True,
        effect_params={"ritual_key": "DOOMBOLT"},
    ),
    "000010193004": EnhancementToolDescriptor(
        enhancement_id="000010193004",
        name="Umbralefic Crystal",
        timing="command_phase_start",
        target="bearer_unit",
        duration="until_reinforcements_step",
        effect="reposition_to_strategic_reserves_then_deep_strike",
        once_per_battle=True,
        effect_params={"min_enemy_distance_horizontal": 9, "requires_not_in_engagement_range": True},
    ),
    "000010193005": EnhancementToolDescriptor(
        enhancement_id="000010193005",
        name="Eldritch Vortex of E'taph",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_psychic_strength_damage_bonus",
        effect_params={"strength_bonus": 1, "damage_bonus": 1},
    ),
}

_GRAND_COVEN_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GRAND_COVEN_DESCRIPTORS.values()
}

_RUBRICAE_PHALANX_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010205002": EnhancementToolDescriptor(
        enhancement_id="000010205002",
        name="Risen Rubricae",
        timing="declare_battle_formations_start",
        target="friendly_rubricae_units",
        duration="during_deployment",
        effect="grant_infiltrators_to_selected_units",
        effect_params={
            "selection_modes": (
                "two_rubricae_battleline_units",
                "one_other_rubricae_unit",
            ),
        },
    ),
    "000010205003": EnhancementToolDescriptor(
        enhancement_id="000010205003",
        name="Arcane Thralls (Aura)",
        timing="passive_aura",
        target="friendly_rubricae_units_within_range",
        duration="constant",
        effect="reroll_battleshock_tests",
        range_in=9.0,
        effect_params={"keyword": "RUBRICAE"},
    ),
    "000010205004": EnhancementToolDescriptor(
        enhancement_id="000010205004",
        name="Lord of the Rubricae",
        timing="passive_while_leading",
        target="rubricae_models_in_bearer_unit",
        duration="constant",
        effect="hit_roll_bonus",
        effect_params={"hit_bonus": 1, "model_keyword": "RUBRICAE"},
    ),
    "000010205005": EnhancementToolDescriptor(
        enhancement_id="000010205005",
        name="The Stave Abominus",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={"sustained_hits_dice": "D3", "devastating_wounds": True},
    ),
}

_RUBRICAE_PHALANX_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RUBRICAE_PHALANX_DESCRIPTORS.values()
}

_WARPBANE_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009777002": EnhancementToolDescriptor(
        enhancement_id="000009777002",
        name="Mandulian Reliquary",
        timing="passive",
        target="bearer",
        duration="while_bearer_unit_not_battle_shocked",
        effect="bearer_objective_control_bonus",
        effect_params={"objective_control_bonus": 3},
    ),
    "000009777003": EnhancementToolDescriptor(
        enhancement_id="000009777003",
        name="Radiant Champion",
        timing="passive",
        target="bearer",
        duration="constant_conditional",
        effect="bearer_melee_precision_and_mortal_on_wound",
        effect_params={
            "precision": True,
            "mortal_wounds_on_successful_wound": 1,
            "mortal_condition": "bearer_wholly_within_hallowed_ground",
        },
    ),
    "000009777004": EnhancementToolDescriptor(
        enhancement_id="000009777004",
        name="Phial of the Abyss",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_stealth",
    ),
    "000009777005": EnhancementToolDescriptor(
        enhancement_id="000009777005",
        name="Paragon of Sanctity",
        timing="start_of_any_phase",
        target="friendly_grey_knights_unit_within_range_visible",
        duration="until_end_of_phase",
        effect="count_as_within_hallowed_ground",
        range_in=18.0,
        once_per_battle=True,
    ),
}

_WARPBANE_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _WARPBANE_TASK_FORCE_DESCRIPTORS.values()
}


def get_enhancement_tool_descriptor(*, enhancement_id: str = "", name: str = "") -> Optional[EnhancementToolDescriptor]:
    if enhancement_id:
        desc = _GORETRACK_ONSLAUGHT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DAEMONIC_INCURSION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _PLAGUE_LEGION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SCINTILLATING_LEGION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GRAND_COVEN_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _RUBRICAE_PHALANX_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _WARPBANE_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
    key = _normalize_name(name)
    if not key:
        return None
    return (
        _GORETRACK_ONSLAUGHT_BY_NAME.get(key)
        or _DAEMONIC_INCURSION_BY_NAME.get(key)
        or _PLAGUE_LEGION_BY_NAME.get(key)
        or _SCINTILLATING_LEGION_BY_NAME.get(key)
        or _GRAND_COVEN_BY_NAME.get(key)
        or _RUBRICAE_PHALANX_BY_NAME.get(key)
        or _WARPBANE_TASK_FORCE_BY_NAME.get(key)
    )
