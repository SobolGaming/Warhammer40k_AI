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
    key = _normalize_name(name)
    if not key:
        return None
    return _GORETRACK_ONSLAUGHT_BY_NAME.get(key) or _DAEMONIC_INCURSION_BY_NAME.get(key) or _PLAGUE_LEGION_BY_NAME.get(key)
