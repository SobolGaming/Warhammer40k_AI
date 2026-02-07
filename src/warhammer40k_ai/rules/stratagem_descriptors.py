from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import re


@dataclass(frozen=True)
class StratagemToolDescriptor:
    stratagem_id: str
    name: str
    timing: str
    target: str
    duration: str
    effect: str
    cp_cost: int = 0
    range_in: Optional[float] = None
    once_per_battle_round: bool = False
    effect_params: dict[str, Any] = field(default_factory=dict)


def _normalize_name(name: str) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


_INFERNAL_LANCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010305002": StratagemToolDescriptor(
        stratagem_id="000010305002",
        name="Profane Symbiosis",
        timing="end_of_phase",
        target="chaos_knights_unit_not_empowered",
        duration="immediate",
        effect="malefic_surge",
        cp_cost=1,
        once_per_battle_round=True,
        effect_params={"restriction": "same_unit_once_per_battle_round"},
    ),
    "000010305004": StratagemToolDescriptor(
        stratagem_id="000010305004",
        name="Corrupting Taint",
        timing="command_phase_after_malefic_surge",
        target="chaos_knights_character_unit",
        duration="until_opponent_control_greater_end_of_phase",
        effect="sticky_objective",
        cp_cost=1,
    ),
    "000010305005": StratagemToolDescriptor(
        stratagem_id="000010305005",
        name="Unleash Balefire",
        timing="shooting_phase_on_select_to_shoot",
        target="chaos_knights_unit_not_yet_shot",
        duration="after_shooting_once",
        effect="battleshock_then_aflame",
        cp_cost=1,
        effect_params={
            "aflame_move_penalty": -2,
            "aflame_advance_penalty": 0,
            "aflame_charge_penalty": -2,
        },
    ),
    "000010305006": StratagemToolDescriptor(
        stratagem_id="000010305006",
        name="Warp Vision",
        timing="shooting_phase_on_select_to_shoot",
        target="chaos_knights_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ignore_cover",
        cp_cost=1,
    ),
}

_INFERNAL_LANCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _INFERNAL_LANCE_STRATAGEM_DESCRIPTORS.values()
}

_DAEMONIC_INCURSION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008437002": StratagemToolDescriptor(
        stratagem_id="000008437002",
        name="Corrupt Realspace",
        timing="command_phase_start_any",
        target="legiones_daemonica_unit_on_controlled_objective",
        duration="until_opponent_controls_start_or_end_of_turn",
        effect="corrupt_realspace_sticky_objective",
        cp_cost=1,
        effect_params={"shadow_of_chaos_radius": 6},
    ),
    "000008437007": StratagemToolDescriptor(
        stratagem_id="000008437007",
        name="Daemonic Invulnerability",
        timing="opponent_shooting_phase_after_targets_selected",
        target="legiones_daemonica_unit_targeted",
        duration="until_end_of_phase",
        effect="reroll_invulnerable_saves_of_1",
        cp_cost=1,
    ),
    "000008437005": StratagemToolDescriptor(
        stratagem_id="000008437005",
        name="Denizens of the Warp",
        timing="movement_phase_reinforcements_step",
        target="legiones_daemonica_unit_arriving_from_deep_strike",
        duration="this_phase",
        effect="deep_strike_min_distance_override",
        cp_cost=1,
        effect_params={"min_distance": 6, "distance_type": "horizontal"},
    ),
    "000008437004": StratagemToolDescriptor(
        stratagem_id="000008437004",
        name="Draught of Terror",
        timing="shooting_or_fight_phase_on_select",
        target="legiones_daemonica_unit_not_yet_acted",
        duration="until_end_of_phase",
        effect="ap_bonus_and_wound_reroll_vs_battleshocked",
        cp_cost=1,
        effect_params={"ap_bonus": 1, "reroll_wound_vs_battleshocked": True},
    ),
    "000008437006": StratagemToolDescriptor(
        stratagem_id="000008437006",
        name="The Realm of Chaos",
        timing="end_of_opponent_turn",
        target="up_to_two_legiones_daemonica_units",
        duration="until_next_reinforcements_step",
        effect="enter_strategic_reserves_with_temp_deep_strike",
        cp_cost=1,
        effect_params={"max_units": 2, "outside_shadow_max_units": 1, "grant_deep_strike": True},
    ),
    "000008437003": StratagemToolDescriptor(
        stratagem_id="000008437003",
        name="Warp Surge",
        timing="charge_phase",
        target="legiones_daemonica_unit_in_shadow",
        duration="until_end_of_phase",
        effect="charge_after_advance",
        cp_cost=1,
    ),
}

_DAEMONIC_INCURSION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DAEMONIC_INCURSION_STRATAGEM_DESCRIPTORS.values()
}

_SCINTILLATING_LEGION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009811007": StratagemToolDescriptor(
        stratagem_id="000009811007",
        name="Delirium Unmade",
        timing="end_of_opponent_fight_phase",
        target="tzeentch_legiones_daemonica_unit",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={"max_units": 2, "requires_flux_for_two": True, "allow_engaged_with_flux": True},
    ),
    "000009811005": StratagemToolDescriptor(
        stratagem_id="000009811005",
        name="Fateborne Nightmares",
        timing="movement_or_charge_phase",
        target="tzeentch_legiones_daemonica_unit",
        duration="until_end_of_phase",
        effect="move_through_terrain",
        cp_cost=1,
    ),
    "000009811006": StratagemToolDescriptor(
        stratagem_id="000009811006",
        name="Ficklefire",
        timing="shooting_phase",
        target="tzeentch_legiones_daemonica_unit_engaged",
        duration="until_end_of_phase",
        effect="ignore_engagement_for_ranged_attacks",
        cp_cost=1,
        effect_params={"mortal_on_destroy_roll": 5},
    ),
    "000009811004": StratagemToolDescriptor(
        stratagem_id="000009811004",
        name="Flickering Reality",
        timing="fight_phase_after_targets_selected",
        target="tzeentch_legiones_daemonica_unit_targeted",
        duration="until_end_of_phase",
        effect="hit_roll_value_ends_attack",
        cp_cost=1,
        effect_params={"reroll_with_flux": True},
    ),
    "000009811002": StratagemToolDescriptor(
        stratagem_id="000009811002",
        name="Impossible Eclipse",
        timing="any_phase",
        target="tzeentch_legiones_daemonica_monster_unit",
        duration="until_end_of_phase",
        effect="shadow_of_chaos_zone_override",
        cp_cost=1,
        effect_params={"zones": ["nml", "enemy"], "flux_for_both": True},
    ),
    "000009811003": StratagemToolDescriptor(
        stratagem_id="000009811003",
        name="Pyrogenesis",
        timing="shooting_or_fight_phase_on_select",
        target="tzeentch_legiones_daemonica_unit_not_yet_acted",
        duration="until_end_of_phase",
        effect="strength_ap_bonus",
        cp_cost=1,
        effect_params={"strength_bonus": 2, "flux_strength_bonus": 3, "flux_ap_bonus": 1},
    ),
}

_SCINTILLATING_LEGION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SCINTILLATING_LEGION_STRATAGEM_DESCRIPTORS.values()
}

_GORETRACK_ONSLAUGHT_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010087007": StratagemToolDescriptor(
        stratagem_id="000010087007",
        name="Fury Unleashed",
        timing="opponent_shooting_phase_after_shooting",
        target="world_eaters_rhino_hit",
        duration="immediate",
        effect="disembark_and_blood_surge",
        cp_cost=1,
        effect_params={"requires_khorne_berzerkers": True, "movement_type": "blood_surge"},
    ),
    "000010087002": StratagemToolDescriptor(
        stratagem_id="000010087002",
        name="Endless Pursuit of Violence",
        timing="end_of_fight_phase",
        target="world_eaters_infantry_and_transport",
        duration="immediate",
        effect="embark_transport_if_within_6",
        cp_cost=1,
        range_in=6.0,
    ),
    "000010087003": StratagemToolDescriptor(
        stratagem_id="000010087003",
        name="Smash Through",
        timing="movement_phase",
        target="world_eaters_vehicle_not_moved",
        duration="until_end_of_phase",
        effect="move_through_terrain",
        cp_cost=1,
        effect_params={"move_types": ["move", "advance"]},
    ),
    "000010087004": StratagemToolDescriptor(
        stratagem_id="000010087004",
        name="Aggressive Disembarkation",
        timing="movement_phase",
        target="world_eaters_rhino_not_moved",
        duration="immediate",
        effect="disembark_within_6_and_engage",
        cp_cost=1,
        range_in=6.0,
        effect_params={"allow_engagement": True},
    ),
    "000010087005": StratagemToolDescriptor(
        stratagem_id="000010087005",
        name="Full-Throttle Assault",
        timing="movement_phase",
        target="world_eaters_rhino_not_moved",
        duration="until_end_of_phase",
        effect="disembark_charge_after_normal_move",
        cp_cost=1,
    ),
    "000010087006": StratagemToolDescriptor(
        stratagem_id="000010087006",
        name="Unrelenting Advance",
        timing="opponent_shooting_phase_after_shooting",
        target="world_eaters_vehicle_hit",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        effect_params={"max_distance": 6},
    ),
}

_GORETRACK_ONSLAUGHT_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GORETRACK_ONSLAUGHT_STRATAGEM_DESCRIPTORS.values()
}


def get_stratagem_tool_descriptor(*, stratagem_id: str = "", name: str = "") -> Optional[StratagemToolDescriptor]:
    if stratagem_id:
        desc = _INFERNAL_LANCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _DAEMONIC_INCURSION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SCINTILLATING_LEGION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _GORETRACK_ONSLAUGHT_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
    key = _normalize_name(name)
    if not key:
        return None
    return (
        _INFERNAL_LANCE_STRATAGEM_BY_NAME.get(key)
        or _DAEMONIC_INCURSION_STRATAGEM_BY_NAME.get(key)
        or _SCINTILLATING_LEGION_STRATAGEM_BY_NAME.get(key)
        or _GORETRACK_ONSLAUGHT_STRATAGEM_BY_NAME.get(key)
    )
