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

_POSSESSED_SLAUGHTERBAND_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010083002": StratagemToolDescriptor(
        stratagem_id="000010083002",
        name="Daemonic Resistance",
        timing="opponent_shooting_or_fight_phase_after_targets_selected",
        target="world_eaters_possessed_unit_targeted",
        duration="until_end_of_phase",
        effect="wound_roll_penalty",
        cp_cost=2,
        effect_params={"wound_modifier": -1},
    ),
    "000010083003": StratagemToolDescriptor(
        stratagem_id="000010083003",
        name="Daemonic Strength",
        timing="fight_phase_on_select_to_fight",
        target="world_eaters_possessed_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="conditional_melee_damage_bonus",
        cp_cost=1,
        effect_params={
            "eightbound_bonus_vs_non_monster_vehicle": 1,
            "exalted_eightbound_bonus_vs_monster_vehicle": 1,
        },
    ),
    "000010083004": StratagemToolDescriptor(
        stratagem_id="000010083004",
        name="Immortal Fury",
        timing="opponent_fight_phase_after_targets_selected",
        target="world_eaters_possessed_unit_targeted_not_yet_fought",
        duration="until_end_of_phase",
        effect="fight_on_death_after_attacks",
        cp_cost=2,
        effect_params={"roll_required": False},
    ),
    "000010083005": StratagemToolDescriptor(
        stratagem_id="000010083005",
        name="Rapid Manifestation",
        timing="movement_phase_reinforcements_step",
        target="exalted_eightbound_unit_arriving_from_deep_strike",
        duration="this_turn_and_phase",
        effect="deep_strike_min_distance_override_with_no_charge",
        cp_cost=1,
        effect_params={"min_distance": 6, "distance_type": "horizontal", "cannot_charge_this_turn": True},
    ),
    "000010083006": StratagemToolDescriptor(
        stratagem_id="000010083006",
        name="Warp Stalkers",
        timing="movement_or_charge_phase_on_select",
        target="world_eaters_possessed_unit_not_yet_selected",
        duration="until_end_of_phase",
        effect="move_through_enemy_except_monster_vehicle",
        cp_cost=1,
        effect_params={"auto_pass_desperate_escape": True},
    ),
    "000010083007": StratagemToolDescriptor(
        stratagem_id="000010083007",
        name="Horrifying Violence",
        timing="opponent_command_phase_start",
        target="world_eaters_possessed_unit",
        duration="immediate",
        effect="engagement_range_enemy_battleshock_test_modifier",
        cp_cost=1,
        effect_params={"battle_shock_test_modifier": -1},
    ),
}

_POSSESSED_SLAUGHTERBAND_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _POSSESSED_SLAUGHTERBAND_STRATAGEM_DESCRIPTORS.values()
}

_VESSELS_OF_WRATH_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009848002": StratagemToolDescriptor(
        stratagem_id="000009848002",
        name="Aspire to Infamy",
        timing="fight_phase_on_select_to_fight",
        target="khorne_berzerkers_or_jakhals_within_8_of_world_eaters_character_not_yet_fought",
        duration="until_end_of_phase",
        effect="non_character_melee_strength_ap_bonus",
        cp_cost=1,
        range_in=8.0,
        effect_params={"strength_bonus": 1, "ap_bonus": 1, "non_character_only": True},
    ),
    "000009848003": StratagemToolDescriptor(
        stratagem_id="000009848003",
        name="Overshadowed by None",
        timing="fight_phase_on_select_to_fight",
        target="world_eaters_infantry_mounted_or_daemon_prince_not_yet_fought",
        duration="until_end_of_phase",
        effect="wound_reroll_vs_monster_vehicle",
        cp_cost=1,
        effect_params={"attack_type": "melee", "target_keywords_any": ["MONSTER", "VEHICLE"]},
    ),
    "000009848007": StratagemToolDescriptor(
        stratagem_id="000009848007",
        name="Brazen Contempt",
        timing="opponent_shooting_phase_after_targets_selected",
        target="world_eaters_unit_targeted_by_attacking_unit",
        duration="until_end_of_phase",
        effect="conditional_wound_roll_penalty",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "wound_modifier": -1,
            "requires_strength_gt_toughness_or_vessel_of_wrath": True,
        },
    ),
    "000009848004": StratagemToolDescriptor(
        stratagem_id="000009848004",
        name="Gory Dedication",
        timing="end_of_fight_phase",
        target="world_eaters_unit_that_destroyed_enemy_models_with_melee",
        duration="until_opponent_control_greater_end_of_phase",
        effect="sticky_objective",
        cp_cost=1,
    ),
    "000009848006": StratagemToolDescriptor(
        stratagem_id="000009848006",
        name="Meet Force with Force",
        timing="opponent_shooting_phase_after_shooting",
        target="world_eaters_infantry_mounted_or_daemon_prince_that_lost_wounds",
        duration="immediate",
        effect="blood_surge_move_d6_with_optional_reroll",
        cp_cost=1,
        effect_params={"movement_type": "blood_surge", "distance_roll": "D6", "reroll_if": ["berzerkers", "vessel_of_wrath"]},
    ),
    "000009848005": StratagemToolDescriptor(
        stratagem_id="000009848005",
        name="Punish the Craven",
        timing="opponent_movement_phase_on_enemy_selected_to_fall_back",
        target="world_eaters_infantry_or_daemon_prince_within_engagement_range",
        duration="until_fall_back_resolved",
        effect="enemy_fall_back_desperate_escape",
        cp_cost=1,
        effect_params={
            "enemy_exclude_keywords_any": ["MONSTER", "VEHICLE"],
            "force_desperate_escape": True,
            "vessel_penalty": -1,
        },
    ),
}

_VESSELS_OF_WRATH_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _VESSELS_OF_WRATH_STRATAGEM_DESCRIPTORS.values()
}

_CULT_OF_BLOOD_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010075005": StratagemToolDescriptor(
        stratagem_id="000010075005",
        name="Bloodthirsty Horde",
        timing="fight_phase_on_select_to_fight",
        target="jakhals_or_goremongers_unit_not_yet_fought_in_engagement_range",
        duration="until_end_of_phase",
        effect="fight_eligibility_within_3",
        cp_cost=1,
        effect_params={"range_in": 3.0, "requires_unit_engagement_range": True},
    ),
    "000010075007": StratagemToolDescriptor(
        stratagem_id="000010075007",
        name="Brazen Idol",
        timing="command_phase",
        target="world_eaters_monster_or_titanic_unit",
        duration="until_start_of_next_command_phase",
        effect="source_specific_idol_override",
        cp_cost=2,
        effect_params={"idol_choices": ["INFINITE_RAGE", "BURNING_WRATH", "BLESSED_BLOOD"], "once_per_battle": True},
    ),
    "000010075002": StratagemToolDescriptor(
        stratagem_id="000010075002",
        name="Bloody Vengeance",
        timing="any_phase_on_friendly_unit_destroyed",
        target="destroyed_world_eaters_monster_or_titanic_unit",
        duration="until_end_of_battle",
        effect="jakhals_goremongers_hit_reroll_vs_destroying_enemy",
        cp_cost=1,
        effect_params={"attack_roll": "hit", "applies_to_keywords_any": ["JAKHALS", "GOREMONGERS"]},
    ),
    "000010075006": StratagemToolDescriptor(
        stratagem_id="000010075006",
        name="Fail Not the Blood God",
        timing="fight_phase",
        target="jakhals_or_goremongers_unit",
        duration="until_end_of_phase",
        effect="hit_reroll_ones_or_full_if_monster_titanic_proximity",
        cp_cost=1,
        effect_params={"base_reroll_values": [1], "full_reroll_if_monster_or_titanic_in_range": True},
    ),
    "000010075004": StratagemToolDescriptor(
        stratagem_id="000010075004",
        name="In the Shadow of Brass Idols",
        timing="opponent_shooting_or_fight_phase_after_targets_selected",
        target="jakhals_or_goremongers_unit_targeted",
        duration="until_end_of_phase",
        effect="feel_no_pain_6_or_5_with_monster_titanic_proximity",
        cp_cost=1,
        effect_params={"base_fnp": 6, "boosted_fnp": 5},
    ),
    "000010075003": StratagemToolDescriptor(
        stratagem_id="000010075003",
        name="Drawn to the Slaughter",
        timing="any_phase_on_friendly_unit_destroyed",
        target="destroyed_jakhals_unit",
        duration="immediate",
        effect="clone_unit_to_strategic_reserves",
        cp_cost=2,
        effect_params={"clone_to_starting_strength": True, "once_per_battle": True, "disallow_character_attachment_return": True},
    ),
}

_CULT_OF_BLOOD_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CULT_OF_BLOOD_STRATAGEM_DESCRIPTORS.values()
}

_WARPBANE_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009778002": StratagemToolDescriptor(
        stratagem_id="000009778002",
        name="Sanctified Kill Zone",
        timing="shooting_or_fight_phase_on_select",
        target="grey_knights_unit_not_yet_acted_wholly_within_hallowed_ground",
        duration="until_end_of_phase",
        effect="wound_reroll",
        cp_cost=1,
        effect_params={"reroll_wound_ones": True, "purifier_squad_full_reroll": True},
    ),
    "000009778003": StratagemToolDescriptor(
        stratagem_id="000009778003",
        name="Flames of Sanctity",
        timing="end_of_fight_phase",
        target="purifier_squad_unit_eligible_to_fight",
        duration="immediate",
        effect="enemy_units_within_range_mortal_wounds",
        cp_cost=1,
        range_in=6.0,
        effect_params={"roll": "D6", "threshold": 4, "mortal_wounds": "D3", "castellan_crowe_bonus": 1},
    ),
    "000009778004": StratagemToolDescriptor(
        stratagem_id="000009778004",
        name="Hallowed Beacon",
        timing="movement_phase_reinforcements_step",
        target="grey_knights_infantry_non_terminator_arriving_deep_strike",
        duration="this_phase",
        effect="deep_strike_min_distance_override",
        cp_cost=1,
        effect_params={"min_distance": 6, "distance_type": "horizontal", "requires_hallowed_ground": True},
    ),
    "000009778005": StratagemToolDescriptor(
        stratagem_id="000009778005",
        name="Fires of Covenant",
        timing="opponent_movement_phase_start",
        target="grey_knights_infantry_unit",
        duration="until_end_of_phase",
        effect="enemy_move_or_setup_proximity_mortal_wounds",
        cp_cost=1,
        range_in=6.0,
        effect_params={
            "trigger_events": ["enemy_set_up", "enemy_normal_move_end", "enemy_advance_move_end", "enemy_fall_back_end"],
            "roll": "D6",
            "base_threshold": 4,
            "hallowed_ground_roll_bonus": 2,
            "mortal_wounds": "D3",
        },
    ),
    "000009778006": StratagemToolDescriptor(
        stratagem_id="000009778006",
        name="Aegis Eternal",
        timing="opponent_shooting_phase_after_targets_selected",
        target="grey_knights_infantry_unit_targeted",
        duration="until_end_of_phase",
        effect="invulnerable_save_in_hallowed_ground",
        cp_cost=1,
        effect_params={"invulnerable_save": 4},
    ),
    "000009778007": StratagemToolDescriptor(
        stratagem_id="000009778007",
        name="Repelling Sphere",
        timing="opponent_charge_phase_start",
        target="grey_knights_infantry_unit",
        duration="until_end_of_phase",
        effect="defensive_charge_roll_penalty",
        cp_cost=1,
        effect_params={"base_penalty": 1, "hallowed_ground_penalty": 2},
    ),
}

_WARPBANE_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _WARPBANE_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_CABAL_OF_CHAOS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010152002": StratagemToolDescriptor(
        stratagem_id="000010152002",
        name="Baleful Blessing",
        timing="any_phase_after_mortal_wound_allocated",
        target="heretic_astartes_unit_allocated_mortal_wound",
        duration="until_end_of_phase",
        effect="fnp_vs_mortal_wounds",
        cp_cost=1,
        effect_params={"fnp": 5},
    ),
    "000010152004": StratagemToolDescriptor(
        stratagem_id="000010152004",
        name="Mutation's Curse",
        timing="shooting_phase",
        target="heretic_astartes_psyker_unit",
        duration="immediate",
        effect="visible_enemy_within_range_mortal_wounds",
        cp_cost=1,
        range_in=12.0,
        effect_params={
            "roll_table": {
                "1": 1,
                "2-4": "D3",
                "5-6": "2D3",
            }
        },
    ),
    "000010152003": StratagemToolDescriptor(
        stratagem_id="000010152003",
        name="No Rest in Death",
        timing="movement_phase",
        target="heretic_astartes_unit_within_9_of_psyker_or_daemon_prince_source",
        duration="immediate",
        effect="heal_or_return_models",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "heal_roll": "D3+1",
            "battleline_return_roll": "D3",
            "battleline_excludes_character": True,
            "choice": ["heal", "return_models"],
        },
    ),
    "000010152007": StratagemToolDescriptor(
        stratagem_id="000010152007",
        name="Shroud of Chaos",
        timing="start_of_opponent_shooting_phase",
        target="heretic_astartes_psyker_or_daemon_prince_unit",
        duration="until_end_of_phase",
        effect="grant_stealth_aura",
        cp_cost=1,
        range_in=6.0,
        effect_params={"aura_target_keyword": "HERETIC ASTARTES"},
    ),
    "000010152005": StratagemToolDescriptor(
        stratagem_id="000010152005",
        name="Soulseekers",
        timing="shooting_phase_on_select_to_shoot",
        target="heretic_astartes_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ignore_cover",
        cp_cost=1,
    ),
    "000010152006": StratagemToolDescriptor(
        stratagem_id="000010152006",
        name="Unholy Haste",
        timing="charge_phase",
        target="heretic_astartes_infantry_unit_not_yet_selected_to_charge",
        duration="until_end_of_phase",
        effect="charge_after_advance",
        cp_cost=1,
    ),
}

_CABAL_OF_CHAOS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CABAL_OF_CHAOS_STRATAGEM_DESCRIPTORS.values()
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
        desc = _POSSESSED_SLAUGHTERBAND_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _VESSELS_OF_WRATH_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CULT_OF_BLOOD_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _WARPBANE_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CABAL_OF_CHAOS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
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
        or _POSSESSED_SLAUGHTERBAND_STRATAGEM_BY_NAME.get(key)
        or _VESSELS_OF_WRATH_STRATAGEM_BY_NAME.get(key)
        or _CULT_OF_BLOOD_STRATAGEM_BY_NAME.get(key)
        or _WARPBANE_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _CABAL_OF_CHAOS_STRATAGEM_BY_NAME.get(key)
    )
