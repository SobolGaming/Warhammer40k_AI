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

_BLOOD_LEGION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009816005": StratagemToolDescriptor(
        stratagem_id="000009816005",
        name="Blood Begets Skulls",
        timing="charge_phase",
        target="khorne_legiones_daemonica_unit_not_yet_selected_to_charge",
        duration="until_end_of_phase",
        effect="charge_after_advance",
        cp_cost=1,
    ),
    "000009816002": StratagemToolDescriptor(
        stratagem_id="000009816002",
        name="Wrath Undeniable",
        timing="fight_phase_after_enemy_targets_selected",
        target="khorne_legiones_daemonica_unit_targeted",
        duration="until_end_of_phase",
        effect="fight_on_death_after_attacks",
        cp_cost=1,
        effect_params={"attack_type": "melee", "fight_on_death_after_attacks": True, "threshold": 4},
    ),
    "000009816003": StratagemToolDescriptor(
        stratagem_id="000009816003",
        name="Gore-Hungry Onslaught",
        timing="movement_or_charge_phase",
        target="khorne_legiones_daemonica_unit",
        duration="until_end_of_phase",
        effect="move_through_terrain",
        cp_cost=1,
        effect_params={
            "move_types_by_phase": {
                "movement": ["move", "advance", "fall_back"],
                "charge": ["charge"],
            }
        },
    ),
    "000009816006": StratagemToolDescriptor(
        stratagem_id="000009816006",
        name="Fools' Flight",
        timing="opponent_movement_phase_after_enemy_fall_back",
        target="khorne_legiones_daemonica_unit_within_6_of_falling_back_enemy",
        duration="immediate",
        effect="out_of_turn_charge_without_charge_bonus",
        cp_cost=2,
        range_in=6.0,
        effect_params={
            "count_as_charged": False,
            "force_single_target": True,
            "trigger_action": "fall_back",
        },
    ),
    "000009816004": StratagemToolDescriptor(
        stratagem_id="000009816004",
        name="Skulls Beget Blood",
        timing="shooting_phase",
        target="khorne_legiones_daemonica_infantry_or_mounted_not_fell_back_not_engaged",
        duration="immediate",
        effect="mortal_wound_burst",
        cp_cost=1,
        range_in=8.0,
        effect_params={
            "roll_count": 6,
            "success_on": 4,
            "mortal_wounds_per_success": 1,
            "target_must_be_visible": True,
            "target_must_not_be_engaged_with_friendly": True,
        },
    ),
    "000009816007": StratagemToolDescriptor(
        stratagem_id="000009816007",
        name="Sheathed in Brass",
        timing="opponent_shooting_phase_after_targets_selected",
        target="khorne_legiones_daemonica_unit_targeted",
        duration="until_end_of_phase",
        effect="set_save_characteristic",
        cp_cost=1,
        effect_params={
            "save_characteristic": 3,
        },
    ),
}

_BLOOD_LEGION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _BLOOD_LEGION_STRATAGEM_DESCRIPTORS.values()
}

_PLAGUE_LEGION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009820002": StratagemToolDescriptor(
        stratagem_id="000009820002",
        name="Seeping Virulence",
        timing="fight_phase",
        target="legiones_daemonica_nurgle_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="melee_critical_hits_on_5plus",
        cp_cost=1,
        effect_params={
            "critical_hit_threshold": 5,
        },
    ),
    "000009820003": StratagemToolDescriptor(
        stratagem_id="000009820003",
        name="Fever Visions",
        timing="shooting_or_fight_phase",
        target="legiones_daemonica_nurgle_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="hit_bonus_and_post_attack_battleshock",
        cp_cost=1,
        effect_params={
            "hit_roll_modifier": 1,
            "post_attack_battleshock": True,
        },
    ),
    "000009820004": StratagemToolDescriptor(
        stratagem_id="000009820004",
        name="Foetid Resurgence",
        timing="command_phase",
        target="legiones_daemonica_nurgle_unit_on_battlefield",
        duration="immediate",
        effect="return_models_or_heal_monster",
        cp_cost=2,
        effect_params={
            "return_models_max": 1,
            "battleline_return_models_roll": "D3",
            "monster_heal_roll": "D3+1",
        },
    ),
    "000009820005": StratagemToolDescriptor(
        stratagem_id="000009820005",
        name="Rot and Renewal",
        timing="movement_or_charge_phase",
        target="legiones_daemonica_nurgle_unit",
        duration="until_end_of_phase",
        effect="move_through_terrain",
        cp_cost=1,
        effect_params={
            "movement_phase_move_types": ["move", "advance", "fall_back"],
            "charge_phase_move_types": ["charge"],
        },
    ),
    "000009820006": StratagemToolDescriptor(
        stratagem_id="000009820006",
        name="Murkshadows",
        timing="movement_phase",
        target="legiones_daemonica_nurgle_infantry_unit",
        duration="until_end_of_phase",
        effect="normal_move_move_characteristic_bonus",
        cp_cost=1,
        effect_params={
            "move_bonus": 5,
            "applies_to_move_types": ["move"],
        },
    ),
    "000009820007": StratagemToolDescriptor(
        stratagem_id="000009820007",
        name="Plague of Woes",
        timing="opponent_command_phase_before_melancholic_miasma_target_selection",
        target="legiones_daemonica_nurgle_unit",
        duration="until_end_of_phase",
        effect="melancholic_miasma_secondary_battleshock",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "requires_melancholic_miasma": True,
            "secondary_target_count": 1,
            "secondary_target_must_be_other_enemy": True,
        },
    ),
}

_PLAGUE_LEGION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _PLAGUE_LEGION_STRATAGEM_DESCRIPTORS.values()
}

_CHAMPIONS_OF_CONTAGION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010132002": StratagemToolDescriptor(
        stratagem_id="000010132002",
        name="Blessings of Filth",
        timing="shooting_or_fight_phase_on_select",
        target="death_guard_attached_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="critical_hits_on_5plus",
        cp_cost=1,
        effect_params={"critical_hit_threshold": 5},
    ),
    "000010132003": StratagemToolDescriptor(
        stratagem_id="000010132003",
        name="Malignance Magnified",
        timing="shooting_or_fight_phase_on_select",
        target="death_guard_attached_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="reroll_hits_and_wounds_vs_target_below_starting_strength",
        cp_cost=2,
        effect_params={
            "reroll_hit_full": True,
            "reroll_wound_full": True,
            "target_condition": "below_starting_strength",
        },
    ),
    "000010132004": StratagemToolDescriptor(
        stratagem_id="000010132004",
        name="Grotesque Fortitude",
        timing="opponent_shooting_or_fight_phase_after_enemy_targets_selected",
        target="death_guard_attached_unit_targeted_by_enemy_attacks",
        duration="until_end_of_phase",
        effect="defensive_toughness_bonus",
        cp_cost=1,
        effect_params={"toughness_bonus": 2},
    ),
    "000010132005": StratagemToolDescriptor(
        stratagem_id="000010132005",
        name="Rabid Infusion",
        timing="fight_phase_start",
        target="death_guard_unit_with_two_character_models",
        duration="until_end_of_phase",
        effect="grant_fights_first",
        cp_cost=1,
        effect_params={"required_character_models": 2},
    ),
    "000010132006": StratagemToolDescriptor(
        stratagem_id="000010132006",
        name="Mobile Vector",
        timing="your_movement_phase_before_reinforcements_step",
        target="death_guard_character_unit_not_leading_and_eligible_unattached_bodyguard_within_2_horizontal_5_vertical",
        duration="immediate",
        effect="attach_as_leader",
        cp_cost=1,
        effect_params={
            "horizontal_range": 2.0,
            "vertical_range": 5.0,
            "requires_unattached_bodyguard": True,
            "allows_second_leader": False,
        },
    ),
    "000010132007": StratagemToolDescriptor(
        stratagem_id="000010132007",
        name="Death's Heads",
        timing="shooting_phase_on_select_to_shoot",
        target="biologus_putrifier_unit_not_engaged_not_yet_shot_visible_enemy_non_vehicle_within_8",
        duration="until_start_of_your_next_turn",
        effect="apply_all_plagues_without_afflicted",
        cp_cost=1,
        range_in=8.0,
        effect_params={
            "requires_visibility": True,
            "enemy_keywords_excluded": ["VEHICLE"],
            "plagues_applied": ["SKULLSQUIRM", "RATTLEJOINT", "SCABROUS"],
            "sets_afflicted": False,
        },
    ),
}

_CHAMPIONS_OF_CONTAGION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CHAMPIONS_OF_CONTAGION_STRATAGEM_DESCRIPTORS.values()
}

_DEATH_LORDS_CHOSEN_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010144002": StratagemToolDescriptor(
        stratagem_id="000010144002",
        name="Blooming Pestilence",
        timing="any_phase_start",
        target="death_guard_terminator_unit",
        duration="until_end_of_phase",
        effect="contagion_range_bonus",
        cp_cost=1,
        effect_params={"contagion_range_bonus": 3},
    ),
    "000010144003": StratagemToolDescriptor(
        stratagem_id="000010144003",
        name="Grim Reapers",
        timing="fight_phase_on_select_to_fight",
        target="death_guard_terminator_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="melee_hit_rerolls_against_non_monster_vehicle",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "reroll_hit_full": True,
            "enemy_keywords_excluded": ["MONSTER", "VEHICLE"],
        },
    ),
    "000010144004": StratagemToolDescriptor(
        stratagem_id="000010144004",
        name="Undying Spite",
        timing="fight_phase_after_enemy_targets_selected",
        target="death_guard_terminator_unit_targeted_by_enemy_attacks",
        duration="until_end_of_phase",
        effect="fight_on_death_on_4_plus",
        cp_cost=1,
        effect_params={"fight_on_death_threshold": 4},
    ),
    "000010144005": StratagemToolDescriptor(
        stratagem_id="000010144005",
        name="Signal Pox",
        timing="command_phase",
        target="lord_of_virulence_model_and_objective_within_30",
        duration="until_start_of_your_next_turn",
        effect="objective_marker_afflicts_enemy_units",
        cp_cost=1,
        range_in=30.0,
        effect_params={
            "requires_visibility": True,
            "objective_afflicts_enemy_units": True,
        },
    ),
    "000010144006": StratagemToolDescriptor(
        stratagem_id="000010144006",
        name="Mortarion's Teachings",
        timing="shooting_phase_on_select_to_shoot",
        target="death_guard_terminator_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="grant_ranged_assault_and_heavy",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "keywords": ["ASSAULT", "HEAVY"],
        },
    ),
    "000010144007": StratagemToolDescriptor(
        stratagem_id="000010144007",
        name="Sickening Impact",
        timing="charge_phase_after_charge_move",
        target="death_guard_terminator_unit_that_ended_charge_move",
        duration="immediate",
        effect="charge_end_mortal_wounds",
        cp_cost=1,
        effect_params={
            "enemy_target": "enemy_unit_within_engagement_range",
            "roll_count": "models_within_engagement_range_of_selected_enemy",
            "success_on": 2,
            "mortal_wounds_per_success": 1,
            "max_mortal_wounds": 6,
        },
    ),
}

_DEATH_LORDS_CHOSEN_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DEATH_LORDS_CHOSEN_STRATAGEM_DESCRIPTORS.values()
}

_FLYBLOWN_HOST_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009730002": StratagemToolDescriptor(
        stratagem_id="000009730002",
        name="Nauseating Paroxysms",
        timing="fight_phase_start",
        target="death_guard_infantry_unit_within_engagement_range_and_enemy_unit_within_engagement_range",
        duration="immediate",
        effect="force_battleshock_test_at_minus_1",
        cp_cost=1,
        effect_params={"battle_shock_modifier": -1},
    ),
    "000009730003": StratagemToolDescriptor(
        stratagem_id="000009730003",
        name="Vermin Cloud",
        timing="fight_phase_on_select_to_fight",
        target="death_guard_infantry_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="pile_in_and_consolidate_up_to_6",
        cp_cost=1,
        effect_params={"pile_in_distance": 6, "consolidate_distance": 6},
    ),
    "000009730004": StratagemToolDescriptor(
        stratagem_id="000009730004",
        name="Eye of the Swarm",
        timing="shooting_phase_on_select_to_shoot",
        target="death_guard_infantry_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="grant_ranged_pistol_except_blast",
        cp_cost=1,
        effect_params={"attack_type": "ranged", "keywords": ["PISTOL"], "exclude_keywords_any": ["BLAST"]},
    ),
    "000009730005": StratagemToolDescriptor(
        stratagem_id="000009730005",
        name="Droning Horror",
        timing="shooting_phase_on_select_to_shoot",
        target="death_guard_infantry_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_hit_reroll_ones_or_full_within_half_range",
        cp_cost=1,
        effect_params={"attack_type": "ranged", "reroll_hit_ones": True, "reroll_hit_full_if_within_half_range": True},
    ),
    "000009730006": StratagemToolDescriptor(
        stratagem_id="000009730006",
        name="Enervating Onslaught",
        timing="charge_phase_after_charge_move",
        target="death_guard_infantry_unit_that_ended_charge_move",
        duration="immediate",
        effect="charge_end_mortal_wounds_against_non_monster_vehicle",
        cp_cost=1,
        effect_params={
            "enemy_target": "enemy_unit_within_engagement_range_excluding_monster_vehicle",
            "roll_count": "models_within_engagement_range_of_selected_enemy",
            "success_on": 5,
            "non_cultist_non_poxwalker_modifier": 1,
            "mortal_wounds_per_success": 1,
            "max_mortal_wounds": 6,
        },
    ),
    "000009730007": StratagemToolDescriptor(
        stratagem_id="000009730007",
        name="Myphitic Invigoration",
        timing="opponent_shooting_phase_after_targets_selected",
        target="death_guard_infantry_unit_within_6_of_friendly_myphitic_blight_hauler_targeted_by_enemy_attacks",
        duration="until_end_of_phase",
        effect="defensive_wound_penalty_when_strength_exceeds_toughness",
        cp_cost=1,
        range_in=6.0,
        effect_params={"attack_type": "ranged", "wound_roll_modifier": -1, "requires_strength_gt_toughness": True},
    ),
}

_FLYBLOWN_HOST_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _FLYBLOWN_HOST_STRATAGEM_DESCRIPTORS.values()
}

_MORTARIONS_HAMMER_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010128002": StratagemToolDescriptor(
        stratagem_id="000010128002",
        name="Blighted Land",
        timing="end_of_your_movement_phase",
        target="death_guard_vehicle_unit_and_visible_terrain_feature_within_24",
        duration="until_start_of_your_next_turn",
        effect="terrain_feature_afflicts_enemy_units_within_3",
        cp_cost=2,
        range_in=24.0,
        effect_params={
            "required_keywords_any": ["VEHICLE"],
            "requires_visibility": True,
            "terrain_affliction_range": 3.0,
        },
    ),
    "000010128003": StratagemToolDescriptor(
        stratagem_id="000010128003",
        name="Relentless Grind",
        timing="movement_or_charge_phase",
        target="death_guard_vehicle_unit_not_yet_selected_to_move_or_charge",
        duration="until_end_of_phase",
        effect="move_through_terrain",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["VEHICLE"],
            "movement_phase_move_types": ["move", "advance"],
            "charge_phase_move_types": ["charge"],
        },
    ),
    "000010128004": StratagemToolDescriptor(
        stratagem_id="000010128004",
        name="Drawn to Despair",
        timing="shooting_phase_on_select_to_shoot",
        target="death_guard_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_full_hit_rerolls_vs_visible_non_aircraft_in_opponent_deployment_zone",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "reroll_hit_full": True,
            "requires_visibility": True,
            "target_condition": "opponent_deployment_zone",
            "enemy_keywords_excluded": ["AIRCRAFT"],
        },
    ),
    "000010128005": StratagemToolDescriptor(
        stratagem_id="000010128005",
        name="Font of Filth",
        timing="shooting_phase_on_select_to_shoot",
        target="death_guard_vehicle_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="grant_ranged_assault",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["VEHICLE"],
            "attack_type": "ranged",
            "keywords": ["ASSAULT"],
        },
    ),
    "000010128006": StratagemToolDescriptor(
        stratagem_id="000010128006",
        name="Eyestinger Storm",
        timing="opponent_command_phase_start",
        target="death_guard_vehicle_unit_and_visible_objective_marker",
        duration="immediate",
        effect="afflicted_enemies_within_objective_take_battleshock_and_ignore_other_tests",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["VEHICLE"],
            "requires_visibility": True,
            "requires_afflicted_targets": True,
            "suppress_other_battle_shock_tests_phase": "COMMAND_PHASE",
        },
    ),
    "000010128007": StratagemToolDescriptor(
        stratagem_id="000010128007",
        name="Stinking Mire",
        timing="opponent_charge_phase_start",
        target="death_guard_vehicle_unit",
        duration="until_end_of_phase",
        effect="enemy_charge_roll_penalty_non_cumulative",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["VEHICLE"],
            "charge_roll_modifier": -2,
            "non_cumulative_with_other_negative_charge_modifiers": True,
        },
    ),
}

_MORTARIONS_HAMMER_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _MORTARIONS_HAMMER_STRATAGEM_DESCRIPTORS.values()
}

_SHAMBLEROT_VECTORIUM_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010140002": StratagemToolDescriptor(
        stratagem_id="000010140002",
        name="Grip of the Walking Pox",
        timing="fight_phase_after_enemy_targets_selected",
        target="poxwalkers_unit_targeted_by_enemy_attacks",
        duration="after_attacking_unit_fights",
        effect="retaliatory_mortal_wounds_per_destroyed_model",
        cp_cost=1,
        effect_params={
            "success_on": 6,
            "roll_count": "models_destroyed_by_attacking_unit_attacks",
            "mortal_wounds_per_success": 1,
            "count_kills_for_curse_if_unit_survives": True,
        },
    ),
    "000010140003": StratagemToolDescriptor(
        stratagem_id="000010140003",
        name="Smeared With Filth",
        timing="fight_phase_on_just_destroyed_poxwalkers",
        target="destroyed_poxwalkers_unit_and_enemy_that_targeted_it_this_phase",
        duration="until_end_of_battle",
        effect="enemy_unit_becomes_afflicted",
        cp_cost=1,
        effect_params={
            "applies_full_afflicted_state": True,
            "target_destroyed_unit_allowed": True,
        },
    ),
    "000010140004": StratagemToolDescriptor(
        stratagem_id="000010140004",
        name="Gnawing Hunger",
        timing="command_phase",
        target="poxwalkers_unit",
        duration="until_end_of_turn",
        effect="move_bonus_and_melee_attacks_strength_bonus",
        cp_cost=1,
        effect_params={
            "move_bonus": 1,
            "attack_type": "melee",
            "attacks_bonus": 1,
            "strength_bonus": 1,
        },
    ),
    "000010140005": StratagemToolDescriptor(
        stratagem_id="000010140005",
        name="Hidden Amongst the Dead",
        timing="movement_phase_reinforcements_step",
        target="poxwalkers_unit_in_strategic_reserves_not_attached",
        duration="until_end_of_phase",
        effect="temporary_deep_strike",
        cp_cost=1,
        effect_params={
            "grant_deep_strike": True,
            "requires_in_strategic_reserves": True,
            "requires_not_attached": True,
        },
    ),
    "000010140006": StratagemToolDescriptor(
        stratagem_id="000010140006",
        name="Shock and Horror",
        timing="charge_phase_after_charge_move",
        target="death_guard_unit_that_ended_charge_move",
        duration="immediate",
        effect="force_battleshock_test_at_minus_1_for_all_enemies_in_engagement_range",
        cp_cost=1,
        effect_params={
            "enemy_target": "all_enemy_units_within_engagement_range",
            "battle_shock_modifier": -1,
        },
    ),
    "000010140007": StratagemToolDescriptor(
        stratagem_id="000010140007",
        name="Shambling Wall",
        timing="opponent_shooting_phase_after_targets_selected",
        target="death_guard_unit_targeted_by_enemy_attacks_and_nearby_visible_poxwalkers_support",
        duration="until_end_of_phase",
        effect="redirect_allocated_attacks_to_support_poxwalkers_model_deaths",
        cp_cost=1,
        range_in=3.0,
        effect_params={
            "support_target": "friendly_poxwalkers_unit_within_3",
            "requires_visibility": True,
            "redirect_uses_damage_characteristic": True,
            "redirect_requires_support_visible_to_attacking_model": True,
        },
    ),
}

_SHAMBLEROT_VECTORIUM_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SHAMBLEROT_VECTORIUM_STRATAGEM_DESCRIPTORS.values()
}

_TALLYBAND_SUMMONERS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010136002": StratagemToolDescriptor(
        stratagem_id="000010136002",
        name="Persistent Pests",
        timing="any_phase_on_just_destroyed_nurglings",
        target="destroyed_friendly_nurglings_unit",
        duration="immediate",
        effect="replace_destroyed_unit_in_strategic_reserves_at_starting_strength",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["PLAGUE LEGIONS", "NURGLINGS"],
            "target_destroyed_unit_allowed": True,
            "reserve_status": "strategic_reserves",
        },
    ),
    "000010136003": StratagemToolDescriptor(
        stratagem_id="000010136003",
        name="Clutching Corruption",
        timing="fight_phase_on_select_to_fight",
        target="death_guard_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="melee_full_hit_rerolls_vs_enemies_engaged_with_friendly_plague_legions",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "reroll_hit_full": True,
            "target_condition": "engaged_with_friendly_plague_legions",
        },
    ),
    "000010136004": StratagemToolDescriptor(
        stratagem_id="000010136004",
        name="All Is Rot",
        timing="shooting_phase_on_select_to_shoot",
        target="engaged_friendly_plague_legions_unit",
        duration="until_end_of_phase",
        effect="ignore_own_engagement_for_ranged_targeting_with_post_shoot_self_mortals_per_damage_in_engagement",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["PLAGUE LEGIONS"],
            "ignore_own_engagement_for_targeting": True,
            "self_mortal_wounds_roll": "D6",
            "self_mortal_wounds_on": 5,
            "self_mortal_trigger": "per_wound_lost_by_enemy_while_in_engagement_range",
        },
    ),
    "000010136005": StratagemToolDescriptor(
        stratagem_id="000010136005",
        name="Fleshy Avalanche",
        timing="movement_or_charge_phase",
        target="plague_legions_monster_unit_not_yet_selected_to_move_or_charge",
        duration="until_end_of_phase",
        effect="move_horizontally_through_terrain",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["PLAGUE LEGIONS", "MONSTER"],
            "movement_phase_move_types": ["move", "advance"],
            "charge_phase_move_types": ["charge"],
        },
    ),
    "000010136006": StratagemToolDescriptor(
        stratagem_id="000010136006",
        name="Avatars of Decay",
        timing="shooting_phase",
        target="friendly_plague_legions_unit",
        duration="until_end_of_phase",
        effect="afflict_enemies_within_6_of_target_unit",
        cp_cost=1,
        range_in=6.0,
        effect_params={
            "required_keywords_any": ["PLAGUE LEGIONS"],
            "affliction_range": 6.0,
            "applies_full_afflicted_state": True,
        },
    ),
    "000010136007": StratagemToolDescriptor(
        stratagem_id="000010136007",
        name="Mireslick",
        timing="opponent_movement_phase_on_enemy_selected_to_fall_back",
        target="plague_legions_unit_within_engagement_range_of_enemy_falling_back",
        duration="until_end_of_phase",
        effect="enemy_fall_back_requires_leadership_test_or_remain_stationary",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["PLAGUE LEGIONS"],
            "enemy_keywords_excluded": ["MONSTER", "VEHICLE"],
            "leadership_test_on_fall_back": True,
            "failed_test_result": "remain_stationary",
        },
    ),
}

_TALLYBAND_SUMMONERS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _TALLYBAND_SUMMONERS_STRATAGEM_DESCRIPTORS.values()
}

_SHADOW_LEGION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009979007": StratagemToolDescriptor(
        stratagem_id="000009979007",
        name="Binding Shadow",
        timing="end_of_opponent_fight_phase",
        target="up_to_one_shadow_legion_heretic_astartes_and_up_to_one_shadow_legion_legiones_daemonica_not_engaged",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "max_units": 2,
            "max_per_group": 1,
            "groups": ["heretic_astartes", "legiones_daemonica"],
            "requires_not_engaged": True,
        },
    ),
    "000009979004": StratagemToolDescriptor(
        stratagem_id="000009979004",
        name="Death Denied",
        timing="command_phase",
        target="shadow_legion_unit",
        duration="immediate",
        effect="heal_and_tzeentch_return_model",
        cp_cost=1,
        effect_params={"heal_wounds_max": 3, "tzeentch_return_destroyed_model_max": 1, "exclude_character": True},
    ),
    "000009979005": StratagemToolDescriptor(
        stratagem_id="000009979005",
        name="Encroaching Darkness",
        timing="shooting_phase",
        target="up_to_one_shadow_legion_heretic_astartes_and_up_to_one_shadow_legion_legiones_daemonica",
        duration="until_end_of_phase",
        effect="ranged_weapons_gain_ignores_cover",
        cp_cost=1,
        effect_params={
            "max_units": 2,
            "max_per_group": 1,
            "groups": ["heretic_astartes", "legiones_daemonica"],
            "requires_arrived_from_reserves_this_turn": True,
        },
    ),
    "000009979006": StratagemToolDescriptor(
        stratagem_id="000009979006",
        name="Shade Path",
        timing="opponent_charge_phase_after_charge_declared",
        target="shadow_legion_unit_selected_as_charge_target",
        duration="until_end_of_phase",
        effect="enemy_charge_roll_modifier_and_nurgle_battleshock",
        cp_cost=2,
        effect_params={"charge_roll_modifier": -2, "nurgle_forces_battleshock_test": True},
    ),
    "000009979002": StratagemToolDescriptor(
        stratagem_id="000009979002",
        name="Spiteful Demise",
        timing="any_phase_on_unit_destroyed",
        target="just_destroyed_shadow_legion_unit",
        duration="immediate",
        effect="engagement_mortal_wound_burst",
        cp_cost=1,
        effect_params={
            "roll_count": "per_enemy_unit_within_engagement_range_of_last_model",
            "threshold_d3": 4,
            "threshold_flat_3": 6,
            "slaanesh_roll_bonus": 2,
        },
    ),
    "000009979003": StratagemToolDescriptor(
        stratagem_id="000009979003",
        name="Channelled Wrath",
        timing="fight_phase",
        target="shadow_legion_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="melee_weapons_gain_lance_and_khorne_ap_bonus",
        cp_cost=1,
        effect_params={"keyword": "LANCE", "khorne_ap_bonus": 1},
    ),
}

_SHADOW_LEGION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SHADOW_LEGION_STRATAGEM_DESCRIPTORS.values()
}

_LEGION_OF_EXCESS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009807003": StratagemToolDescriptor(
        stratagem_id="000009807003",
        name="Archagonists",
        timing="fight_phase",
        target="one_legiones_daemonica_slaanesh_monster_or_up_to_two_non_monster_units_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="melee_wound_bonus",
        cp_cost=2,
        effect_params={
            "melee_wound_roll_modifier": 1,
            "max_non_monster_units": 2,
            "max_monster_units": 1,
        },
    ),
    "000009807004": StratagemToolDescriptor(
        stratagem_id="000009807004",
        name="Sensory Excruciation",
        timing="command_phase",
        target="legiones_daemonica_slaanesh_monster_unit_on_battlefield",
        duration="immediate",
        effect="shadow_of_chaos_battle_shock_sweep",
        cp_cost=1,
        effect_params={
            "targets": "all_units_within_players_shadow_of_chaos",
            "battle_shock_test_modifier_if_below_half_strength": -1,
            "includes_friendly_and_enemy": True,
        },
    ),
    "000009807002": StratagemToolDescriptor(
        stratagem_id="000009807002",
        name="Thieves of Pain",
        timing="any_phase_after_attack_or_mortal_wound_allocated",
        target="legiones_daemonica_slaanesh_unit_excluding_monster_vehicle",
        duration="until_end_of_phase",
        effect="redirect_wound_loss_to_friendly_mortal_wounds",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "requires_visible_secondary_target": True,
            "secondary_target": "other_friendly_legiones_daemonica_slaanesh_unit",
            "redirect_rule": "each_wound_loss_on_target_becomes_1_mortal_wound_on_secondary_target",
            "secondary_target_must_remain_on_battlefield": True,
        },
    ),
    "000009807005": StratagemToolDescriptor(
        stratagem_id="000009807005",
        name="Phantasmal Longing",
        timing="movement_or_charge_phase",
        target="legiones_daemonica_slaanesh_unit",
        duration="until_end_of_phase",
        effect="move_through_terrain",
        cp_cost=1,
        effect_params={
            "move_types_by_phase": {
                "movement": ["move", "advance", "fall_back"],
                "charge": ["charge"],
            }
        },
    ),
    "000009807006": StratagemToolDescriptor(
        stratagem_id="000009807006",
        name="Cavalcade of Blades",
        timing="charge_phase_after_friendly_charge_move",
        target="legiones_daemonica_slaanesh_unit_just_ended_charge_move",
        duration="immediate",
        effect="engagement_mortal_wound_burst",
        cp_cost=1,
        effect_params={
            "roll_count": "per_model_within_engagement_or_six_if_monster",
            "success_on": 4,
            "mortal_wounds_per_success": 1,
        },
    ),
    "000009807007": StratagemToolDescriptor(
        stratagem_id="000009807007",
        name="Overwhelming Excess",
        timing="opponent_shooting_or_fight_phase_after_targets_selected",
        target="legiones_daemonica_slaanesh_unit_targeted_by_attacking_unit",
        duration="until_end_of_phase",
        effect="defensive_hit_penalty",
        cp_cost=1,
        effect_params={"hit_roll_modifier": -1, "attack_type": "any"},
    ),
}

_LEGION_OF_EXCESS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _LEGION_OF_EXCESS_STRATAGEM_DESCRIPTORS.values()
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

_GREEN_TIDE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008882003": StratagemToolDescriptor(
        stratagem_id="000008882003",
        name="BULLDOZER BRUTALITY",
        timing="fight_phase",
        target="orks_boyz_unit_eligible_to_fight_and_engaged",
        duration="until_end_of_phase",
        effect="fight_within_3_activation",
        cp_cost=1,
        effect_params={
            "eligibility_range": 3,
            "requires_target_unit_in_engagement_range": True,
        },
    ),
    "000008882004": StratagemToolDescriptor(
        stratagem_id="000008882004",
        name="BRAGGIN' RIGHTS",
        timing="command_phase",
        target="two_orks_boyz_units_within_6_of_each_other",
        duration="until_start_of_next_command_phase_while_within_6",
        effect="effective_model_count_floor",
        cp_cost=1,
        range_in=6.0,
        effect_params={
            "effective_model_floor": 10,
            "effective_model_count_scopes": ("detachment", "enhancement", "stratagem"),
            "condition": "while_within_6_of_each_other",
            "expires_mode": "next_command_phase",
            "expires_scope": "owner_command_phase",
        },
    ),
    "000008882002": StratagemToolDescriptor(
        stratagem_id="000008882002",
        name="COMPETITIVE STREAK",
        timing="fight_phase",
        target="orks_boyz_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="conditional_melee_wound_reroll",
        cp_cost=1,
        effect_params={
            "default_reroll_mode": "ones",
            "enhanced_reroll_mode_if_effective_10_models": "full",
            "effective_model_count_scope": "stratagem",
            "attack_type": "melee",
        },
    ),
    "000008882005": StratagemToolDescriptor(
        stratagem_id="000008882005",
        name="COME ON LADZ!",
        timing="command_phase",
        target="orks_boyz_unit",
        duration="immediate",
        effect="return_destroyed_models",
        cp_cost=1,
        effect_params={
            "return_roll": "D3+2",
            "required_keyword": "BOYZ",
            "exclude_character": True,
        },
    ),
    "000008882006": StratagemToolDescriptor(
        stratagem_id="000008882006",
        name="TIDE OF MUSCLE",
        timing="charge_phase",
        target="orks_boyz_unit_not_yet_declared_charge",
        duration="until_end_of_phase",
        effect="charge_roll_bonus_and_conditional_reroll",
        cp_cost=1,
        effect_params={
            "charge_roll_bonus": 1,
            "grant_charge_reroll_if_effective_10_models": True,
            "effective_model_count_scope": "stratagem",
        },
    ),
    "000008882007": StratagemToolDescriptor(
        stratagem_id="000008882007",
        name="GO GET 'EM!",
        timing="opponent_shooting_phase_after_targets_selected",
        target="orks_boyz_unit_targeted_by_attacker",
        duration="after_attacker_shoots_once",
        effect="reactive_normal_move",
        cp_cost=1,
        effect_params={
            "distance_roll": "D6",
            "must_end_as_close_as_possible_to_closest_enemy_unit": True,
            "allow_move_within_engagement_range": True,
            "grant_distance_reroll_if_effective_10_models": True,
            "effective_model_count_scope": "stratagem",
        },
    ),
}

_GREEN_TIDE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GREEN_TIDE_STRATAGEM_DESCRIPTORS.values()
}

_ORKS_TEMP_BUFF_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009992003": StratagemToolDescriptor(
        stratagem_id="000009992003",
        name="GET STUCK IN, LADZ!",
        timing="command_phase",
        target="orks_non_gretchin_unit",
        duration="until_start_of_next_command_phase",
        effect="unit_scoped_waaagh_active_override",
        cp_cost=2,
        effect_params={
            "scope": "single_unit",
            "expires_scope": "owner_command_phase",
            "does_not_consume_army_waaagh": True,
        },
    ),
    "000008886002": StratagemToolDescriptor(
        stratagem_id="000008886002",
        name="ARMED TO DATEEF",
        timing="shooting_or_fight_phase_on_select",
        target="orks_nobz_or_meganobz_unit_not_yet_selected",
        duration="until_end_of_phase",
        effect="hit_reroll_ones_or_full_if_waaagh",
        cp_cost=1,
        effect_params={"attack_type": "any", "reroll_mode": "ones", "reroll_mode_if_waaagh": "full"},
    ),
    "000008886003": StratagemToolDescriptor(
        stratagem_id="000008886003",
        name="TOO ARROGANT TO DIE",
        timing="opponent_shooting_or_fight_phase_after_targets_selected",
        target="orks_nobz_or_meganobz_unit_selected_by_attacker",
        duration="until_end_of_phase",
        effect="shoot_or_fight_on_death_after_attacker_finishes_attacks",
        cp_cost=1,
        effect_params={
            "attack_type": "any",
            "base_threshold": 5,
            "waaagh_roll_bonus": 2,
        },
    ),
    "000008886004": StratagemToolDescriptor(
        stratagem_id="000008886004",
        name="ALWAYS LOOKIN’ FER A FIGHT",
        timing="fight_phase_on_unit_destroyed",
        target="orks_nobz_or_meganobz_unit_that_destroyed_enemy",
        duration="until_end_of_phase",
        effect="consolidate_distance_override",
        cp_cost=1,
        effect_params={
            "distance_roll": "D3+3",
            "distance_if_waaagh": 6,
        },
    ),
    "000008886005": StratagemToolDescriptor(
        stratagem_id="000008886005",
        name="CRUSHING IMPACT",
        timing="charge_phase_after_charge_move_end",
        target="orks_nobz_or_meganobz_unit_just_completed_charge",
        duration="immediate",
        effect="charge_end_capped_mortal_wound_burst",
        cp_cost=1,
        effect_params={
            "enemy_selection": "one_enemy_within_engagement_range",
            "dice_per_model_mode": "models_within_engagement_range_of_selected_enemy",
            "success_on": 5,
            "success_on_if_waaagh": 4,
            "mortal_wounds_per_success": 1,
            "max_mortal_wounds": 6,
        },
    ),
    "000008886006": StratagemToolDescriptor(
        stratagem_id="000008886006",
        name="CUT’EM DOWN",
        timing="opponent_movement_phase_after_enemy_selected_to_fall_back",
        target="orks_nobz_or_meganobz_unit_within_engagement_range_of_enemy",
        duration="until_end_of_phase",
        effect="force_enemy_desperate_escape_on_fall_back",
        cp_cost=1,
        effect_params={
            "exclude_monster_vehicle": False,
            "desperate_escape_penalty_if_waaagh": 1,
        },
    ),
    "000008869002": StratagemToolDescriptor(
        stratagem_id="000008869002",
        name="DRAG IT DOWN",
        timing="fight_phase_on_select_to_fight",
        target="orks_beast_snagga_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="melee_sustained_hits_and_prey_critical_hits_5plus",
        cp_cost=1,
        effect_params={"sustained_hits": 1, "prey_critical_hit_threshold": 5},
    ),
    "000008869004": StratagemToolDescriptor(
        stratagem_id="000008869004",
        name="DAT ONE'S EVEN BIGGA!",
        timing="charge_phase",
        target="orks_beast_snagga_unit",
        duration="until_end_of_phase",
        effect="charge_after_advance_or_fall_back_with_prey_gated_charge_reroll",
        cp_cost=1,
        effect_params={
            "charge_after_advance": True,
            "charge_after_fall_back": True,
            "charge_reroll_requires_prey_target": True,
        },
    ),
    "000008869003": StratagemToolDescriptor(
        stratagem_id="000008869003",
        name="UNSTOPPABLE MOMENTUM",
        timing="charge_phase_after_charge_move_end",
        target="orks_beast_snagga_mounted_unit_just_completed_charge",
        duration="immediate",
        effect="charge_end_capped_mortal_wound_burst",
        cp_cost=1,
        effect_params={
            "enemy_selection": "one_enemy_within_engagement_range",
            "dice_per_model_mode": "all_models_in_unit",
            "success_on": 4,
            "prey_bonus_dice": 3,
            "mortal_wounds_per_success": 1,
            "max_mortal_wounds": 6,
        },
    ),
    "000008869007": StratagemToolDescriptor(
        stratagem_id="000008869007",
        name="INSTINCTIVE HUNTERS",
        timing="end_of_opponent_fight_phase",
        target="orks_beast_snagga_unit_not_in_engagement_range",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={"requires_not_in_engagement_range": True, "reserve_status": "strategic_reserves"},
    ),
    "000010713002": StratagemToolDescriptor(
        stratagem_id="000010713002",
        name="BASH AND GRAB",
        timing="fight_phase_on_select_to_fight",
        target="orks_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="melee_wound_reroll_vs_loot_objective",
        cp_cost=1,
        effect_params={"reroll_mode": "full", "target_condition": "loot_objective_range"},
    ),
    "000010713003": StratagemToolDescriptor(
        stratagem_id="000010713003",
        name="GRAB AND BASH",
        timing="command_phase",
        target="orks_non_gretchin_unit_within_loot_objective",
        duration="until_start_of_next_command_phase",
        effect="unit_scoped_waaagh_active_override",
        cp_cost=1,
        effect_params={
            "scope": "single_unit",
            "requires_loot_objective_range": True,
            "expires_scope": "owner_command_phase",
            "does_not_consume_army_waaagh": True,
        },
    ),
    "000010713004": StratagemToolDescriptor(
        stratagem_id="000010713004",
        name="BOARDIN' RUSH",
        timing="movement_phase_on_select_to_move",
        target="orks_unit_not_yet_moved",
        duration="until_end_of_phase",
        effect="advance_no_roll_fixed_distance",
        cp_cost=1,
        effect_params={"fixed_advance_distance": 6},
    ),
    "000010713005": StratagemToolDescriptor(
        stratagem_id="000010713005",
        name="DECK FRAGGERS",
        timing="shooting_phase_on_select_to_shoot",
        target="orks_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_blast_vs_infantry",
        cp_cost=1,
        effect_params={"keyword": "BLAST", "target_keywords_any": ["INFANTRY"]},
    ),
    "000010713006": StratagemToolDescriptor(
        stratagem_id="000010713006",
        name="ROLLING LOOT-HEAP",
        timing="shooting_phase_on_select_to_shoot",
        target="flash_gitz_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_anti_vehicle_4plus",
        cp_cost=1,
        effect_params={"keyword": "ANTI-VEHICLE 4+"},
    ),
    "000008873005": StratagemToolDescriptor(
        stratagem_id="000008873005",
        name="BLITZA FIRE",
        timing="shooting_phase_on_select_to_shoot",
        target="speed_freeks_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_lethal_hits_and_critical_hits_5plus_within_9",
        cp_cost=1,
        range_in=9.0,
        effect_params={"keyword": "LETHAL HITS", "critical_hit_threshold": 5, "critical_hit_target_range": 9.0},
    ),
    "000008873004": StratagemToolDescriptor(
        stratagem_id="000008873004",
        name="DAKKASTORM",
        timing="shooting_phase_on_select_to_shoot",
        target="speed_freeks_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_sustained_hits_within_9_upgrade",
        cp_cost=1,
        range_in=9.0,
        effect_params={"sustained_hits": 1, "sustained_hits_within_range": 2, "range_in": 9.0},
    ),
    "000008873006": StratagemToolDescriptor(
        stratagem_id="000008873006",
        name="FULL THROTTLE!",
        timing="charge_phase_after_charge_move_end",
        target="speed_freeks_unit_just_completed_charge",
        duration="until_end_of_turn",
        effect="melee_wound_bonus",
        cp_cost=1,
        effect_params={"melee_wound_roll_modifier": 1},
    ),
    "000008873003": StratagemToolDescriptor(
        stratagem_id="000008873003",
        name="SQUIG FLINGIN'",
        timing="movement_phase_after_friendly_unit_ends_normal_advance_or_fall_back_move",
        target="speed_freeks_or_trukk_unit_just_completed_normal_advance_or_fall_back_move",
        duration="immediate",
        effect="forced_enemy_battleshock_after_move_end",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "range_inches": 9,
            "battle_shock_test_modifier": -1,
            "trigger_unit_actions": ["normal_move", "advance", "fall_back"],
        },
    ),
    "000009992005": StratagemToolDescriptor(
        stratagem_id="000009992005",
        name="LONG, UNCONTROLLED BURSTS",
        timing="shooting_phase_on_select_to_shoot",
        target="orks_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_ignores_cover",
        cp_cost=1,
        effect_params={"keyword": "IGNORES COVER"},
    ),
    "000009992007": StratagemToolDescriptor(
        stratagem_id="000009992007",
        name="CALL DAT DAKKA?",
        timing="opponent_shooting_phase_after_enemy_shoots_with_models_destroyed",
        target="orks_unit_that_lost_models_to_attacker",
        duration="immediate",
        effect="reactive_shooting_at_attacker",
        cp_cost=1,
        effect_params={
            "force_target_attacker": True,
            "requires_destroyed_models": True,
            "target_restriction": "attacking_enemy_unit_only",
        },
    ),
    "000008878003": StratagemToolDescriptor(
        stratagem_id="000008878003",
        name="SUPERFUELLED BOILER",
        timing="movement_phase_after_select_to_advance",
        target="orks_walker_unit_selected_to_advance",
        duration="until_end_of_turn",
        effect="reroll_advance_and_ranged_assault",
        cp_cost=1,
        effect_params={
            "reroll_advance": True,
            "grant_keyword": "ASSAULT",
            "attack_type": "ranged",
        },
    ),
    "000009992002": StratagemToolDescriptor(
        stratagem_id="000009992002",
        name="ORKS IS STILL ORKS",
        timing="fight_phase_on_select_to_fight",
        target="orks_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="melee_wound_reroll_ones_or_full_on_objective_targets",
        cp_cost=1,
        effect_params={"base_reroll_mode": "ones", "objective_target_reroll_mode": "full"},
    ),
    "000009992006": StratagemToolDescriptor(
        stratagem_id="000009992006",
        name="SPESHUL SHELLS",
        timing="shooting_phase_on_select_to_shoot",
        target="orks_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_ap_bonus_vs_closest_eligible_within_18",
        cp_cost=1,
        range_in=18.0,
        effect_params={"ap_bonus": 1, "closest_eligible_only": True, "max_target_range": 18.0},
    ),
    "000009796002": StratagemToolDescriptor(
        stratagem_id="000009796002",
        name="DAT'S OURS",
        timing="command_phase",
        target="orks_unit_within_engagement_range",
        duration="until_start_of_next_command_phase",
        effect="objective_control_bonus",
        cp_cost=1,
        effect_params={"objective_control_bonus": 1},
    ),
    "000009796004": StratagemToolDescriptor(
        stratagem_id="000009796004",
        name="TAKTIKAL RETREAT",
        timing="movement_phase_after_fall_back",
        target="orks_unit_after_fall_back",
        duration="until_end_of_turn",
        effect="shoot_and_charge_after_fall_back",
        cp_cost=1,
        effect_params={
            "shoot_after_fall_back": True,
            "charge_after_fall_back": True,
        },
    ),
    "000009992004": StratagemToolDescriptor(
        stratagem_id="000009992004",
        name="HUGE SHOW-OFFS",
        timing="command_phase",
        target="orks_walker_unit_excluding_killa_kans",
        duration="until_start_of_next_command_phase",
        effect="characteristic_and_hit_roll_bonus",
        cp_cost=1,
        effect_params={
            "movement_bonus": 1,
            "leadership_bonus": 1,
            "objective_control_bonus": 1,
            "hit_roll_bonus": 1,
        },
    ),
    "000009796003": StratagemToolDescriptor(
        stratagem_id="000009796003",
        name="FIGHT PROPPA",
        timing="fight_phase_on_select_to_fight",
        target="orks_infantry_or_mounted_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="bounded_choice_melee_keyword",
        cp_cost=1,
        effect_params={
            "choices": [
                {"choice_key": "sustained_hits_1", "keyword": "SUSTAINED HITS 1"},
                {"choice_key": "lethal_hits", "keyword": "LETHAL HITS"},
            ],
        },
    ),
    "000008878005": StratagemToolDescriptor(
        stratagem_id="000008878005",
        name="DAKKA! DAKKA! DAKKA!",
        timing="shooting_phase_on_select_to_shoot",
        target="orks_walker_or_grots_vehicle_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="bounded_choice_ranged_hit_reroll_with_optional_hazardous",
        cp_cost=1,
        effect_params={
            "choices": [
                {"choice_key": "normal", "hit_reroll_mode": "ones", "grant_hazardous": False},
                {"choice_key": "push_it", "hit_reroll_mode": "full", "grant_hazardous": True},
            ],
        },
    ),
    "000008878004": StratagemToolDescriptor(
        stratagem_id="000008878004",
        name="BIGGER SHELLS FOR BIGGER GITZ",
        timing="shooting_phase_on_select_to_shoot",
        target="mek_or_orks_walker_or_grots_vehicle_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="bounded_choice_ranged_wound_damage_vs_monster_vehicle",
        cp_cost=1,
        effect_params={
            "target_keywords_any": ["MONSTER", "VEHICLE"],
            "choices": [
                {"choice_key": "normal", "wound_bonus": 1, "damage_bonus": 0, "grant_hazardous": False},
                {"choice_key": "push_it", "wound_bonus": 1, "damage_bonus": 1, "grant_hazardous": True},
            ],
        },
    ),
    "000008878002": StratagemToolDescriptor(
        stratagem_id="000008878002",
        name="KLANKIN' KLAWS",
        timing="fight_phase_on_select_to_fight",
        target="orks_walker_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="bounded_choice_melee_strength_damage_with_optional_hazardous",
        cp_cost=1,
        effect_params={
            "choices": [
                {"choice_key": "normal", "strength_bonus": 2, "damage_bonus": 0, "grant_hazardous": False},
                {"choice_key": "push_it", "strength_bonus": 2, "damage_bonus": 1, "grant_hazardous": True},
            ],
        },
    ),
    "000008869006": StratagemToolDescriptor(
        stratagem_id="000008869006",
        name="STALKIN' TAKTIKS",
        timing="opponent_shooting_phase_after_targets_selected",
        target="beast_snagga_infantry_or_mounted_unit_targeted",
        duration="until_end_of_phase",
        effect="defensive_cover_and_conditional_stealth",
        cp_cost=1,
        effect_params={
            "cover_attack_type": "ranged",
            "conditional_stealth_if_unit_has_keyword": "INFANTRY",
        },
    ),
    "000008873002": StratagemToolDescriptor(
        stratagem_id="000008873002",
        name="SPEEDIEST FREEKS",
        timing="opponent_shooting_or_fight_phase_after_targets_selected",
        target="speed_freeks_or_trukk_unit_targeted",
        duration="until_end_of_phase",
        effect="defensive_conditional_invulnerable_save",
        cp_cost=1,
        effect_params={
            "base_invulnerable_save": 5,
            "vehicle_unmodified_toughness_max_for_improved_invulnerable": 8,
            "improved_invulnerable_save": 4,
        },
    ),
    "000008878007": StratagemToolDescriptor(
        stratagem_id="000008878007",
        name="EXTRA GUBBINZ",
        timing="opponent_shooting_phase_after_targets_selected",
        target="orks_walker_or_grots_vehicle_unit_targeted_excluding_titanic",
        duration="until_end_of_phase",
        effect="defensive_damage_reduction",
        cp_cost=1,
        effect_params={"damage_reduction": 1},
    ),
    "000008869005": StratagemToolDescriptor(
        stratagem_id="000008869005",
        name="WHERE D'YA FINK YOU'RE GOING?",
        timing="opponent_movement_phase_after_enemy_fall_back",
        target="beast_snagga_infantry_or_mounted_unit_engaged_with_trigger_unit_at_phase_start_and_not_engaged_now",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        effect_params={
            "distance": 6,
            "trigger_enemy_actions": ["fall_back"],
            "requires_start_phase_engagement_with_trigger_unit": True,
            "requires_not_in_engagement_range": True,
        },
    ),
    "000010713007": StratagemToolDescriptor(
        stratagem_id="000010713007",
        name="KRUMP AND RUN",
        timing="opponent_movement_phase_after_enemy_fall_back",
        target="orks_unit_engaged_with_trigger_unit_at_phase_start_and_not_engaged_now",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        effect_params={
            "distance": 6,
            "trigger_enemy_actions": ["fall_back"],
            "requires_start_phase_engagement_with_trigger_unit": True,
            "requires_not_in_engagement_range": True,
        },
    ),
    "000009796006": StratagemToolDescriptor(
        stratagem_id="000009796006",
        name="ON TO DA NEXT",
        timing="opponent_movement_phase_after_enemy_fall_back",
        target="orks_unit_engaged_with_trigger_unit_at_phase_start",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        effect_params={
            "distance": 6,
            "trigger_enemy_actions": ["fall_back"],
            "requires_start_phase_engagement_with_trigger_unit": True,
        },
    ),
    "000008878006": StratagemToolDescriptor(
        stratagem_id="000008878006",
        name="CONNIVING RUNTS",
        timing="opponent_movement_phase_after_enemy_unit_ends_normal_advance_or_fall_back_move",
        target="gretchin_unit_within_9_of_enemy_that_ended_move_and_not_engaged",
        duration="immediate",
        effect="reactive_normal_move_with_pre_move_single_roll_mortal_wound_rider",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "distance": 6,
            "trigger_enemy_actions": ["normal_move", "advance", "fall_back"],
            "range_inches": 9,
            "requires_not_in_engagement_range": True,
            "pre_move_rider_effect": "single_roll_mortal_wounds",
            "pre_move_target": "trigger_enemy_unit",
            "pre_move_trigger_roll": "D6",
            "pre_move_success_on": 4,
            "pre_move_mortal_wounds": "D3+1",
        },
    ),
    "000009796007": StratagemToolDescriptor(
        stratagem_id="000009796007",
        name="DED SNEAKY",
        timing="end_of_opponent_fight_phase",
        target="orks_kommandos_or_stormboyz_unit_not_in_engagement_range",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={"requires_not_in_engagement_range": True, "reserve_status": "strategic_reserves"},
    ),
    "000009796005": StratagemToolDescriptor(
        stratagem_id="000009796005",
        name="KRUNCHIN' DESCENT",
        timing="charge_phase_after_charge_move_end",
        target="orks_stormboyz_unit_just_completed_charge",
        duration="immediate",
        effect="charge_end_capped_mortal_wound_burst",
        cp_cost=1,
        effect_params={
            "enemy_selection": "one_enemy_within_engagement_range",
            "dice_per_model_mode": "models_within_engagement_range_of_selected_enemy",
            "success_on": 4,
            "mortal_wounds_per_success": 1,
            "max_mortal_wounds": 6,
        },
    ),
    "000008873007": StratagemToolDescriptor(
        stratagem_id="000008873007",
        name="MORE GITZ OVER 'ERE!",
        timing="opponent_movement_phase_after_enemy_unit_ends_normal_advance_or_fall_back_move",
        target="speed_freeks_unit_within_9_of_enemy_that_ended_move_and_not_engaged",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "distance": 6,
            "trigger_enemy_actions": ["normal_move", "advance", "fall_back"],
            "range_inches": 9,
            "requires_not_in_engagement_range": True,
        },
    ),
}

_ORKS_TEMP_BUFF_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ORKS_TEMP_BUFF_STRATAGEM_DESCRIPTORS.values()
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

_HOST_OF_ASCENSION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009068002": StratagemToolDescriptor(
        stratagem_id="000009068002",
        name="Coordinated Trap",
        timing="start_of_shooting_or_fight_phase",
        target="two_genestealer_cults_units_not_yet_selected_to_shoot_or_fight_and_one_enemy_unit",
        duration="until_end_of_phase",
        effect="target_lock_and_wound_bonus",
        cp_cost=2,
        effect_params={
            "target_lock": True,
            "wound_roll_bonus": 1,
            "fight_phase_enemy_must_be_within_engagement_range_of_both_units": True,
        },
    ),
    "000009068003": StratagemToolDescriptor(
        stratagem_id="000009068003",
        name="Primed and Readied",
        timing="shooting_or_fight_phase",
        target="genestealer_cults_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="critical_hits_on_5plus",
        cp_cost=2,
        effect_params={"critical_hit_threshold": 5},
    ),
    "000009068004": StratagemToolDescriptor(
        stratagem_id="000009068004",
        name="Tunnel Crawlers",
        timing="movement_phase_reinforcements_step",
        target="genestealer_cults_unit_arriving_with_deep_strike",
        duration="this_turn_and_phase",
        effect="deep_strike_min_distance_override_with_no_charge",
        cp_cost=1,
        effect_params={"min_distance": 6, "distance_type": "horizontal", "cannot_charge_this_turn": True},
    ),
    "000009068005": StratagemToolDescriptor(
        stratagem_id="000009068005",
        name="Lying in Wait",
        timing="opponent_movement_phase_reinforcements_step",
        target="genestealer_cults_battleline_unit_in_cult_ambush",
        duration="until_end_of_phase_or_until_set_up",
        effect="cult_ambush_marker_setup_override",
        cp_cost=1,
        effect_params={
            "setup_max_distance": 6,
            "setup_distance_type": "wholly_within",
            "enemy_distance_mode": "engagement_range",
        },
    ),
    "000009068006": StratagemToolDescriptor(
        stratagem_id="000009068006",
        name="Return to the Shadows",
        timing="end_of_opponent_fight_phase",
        target="genestealer_cults_infantry_unit_not_within_engagement_range",
        duration="immediate",
        effect="place_unit_into_strategic_reserves",
        cp_cost=1,
        effect_params={"reserve_status": "strategic_reserves"},
    ),
    "000009068007": StratagemToolDescriptor(
        stratagem_id="000009068007",
        name="A Deadly Snare",
        timing="opponent_charge_phase_after_enemy_charge_declared",
        target="genestealer_cults_infantry_unit_selected_as_charge_target",
        duration="immediate",
        effect="roll_d6_tiered_mortal_wounds_on_charging_enemy",
        cp_cost=1,
        effect_params={
            "mortal_wounds_table": {
                "2-4": "D3",
                "5+": 3,
            }
        },
    ),
}

_HOST_OF_ASCENSION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _HOST_OF_ASCENSION_STRATAGEM_DESCRIPTORS.values()
}

_BROOD_BROTHER_AUXILIA_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009085004": StratagemToolDescriptor(
        stratagem_id="000009085004",
        name="SUPPRESS AND OVERWHELM",
        timing="shooting_phase_after_friendly_astra_militarum_unit_shoots",
        target="friendly_astra_militarum_unit_that_has_shot_and_enemy_hit_by_it",
        duration="until_end_of_turn",
        effect="mark_enemy_unit_no_overwatch_and_gsc_charge_reroll_against_it",
        cp_cost=1,
        effect_params={
            "requires_hit_enemy_target": True,
            "blocks_fire_overwatch_for_marked_enemy": True,
            "gsc_charge_reroll_against_marked_enemy": True,
        },
    ),
}

_BROOD_BROTHER_AUXILIA_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _BROOD_BROTHER_AUXILIA_STRATAGEM_DESCRIPTORS.values()
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

_GRIZZLED_COMPANY_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010638007": StratagemToolDescriptor(
        stratagem_id="000010638007",
        name="Additional Armour",
        timing="opponent_shooting_phase_after_targets_selected",
        target="astra_militarum_unit_targeted",
        duration="until_attacking_unit_finishes_attacks",
        effect="ap_worsen",
        cp_cost=1,
        effect_params={"ap_worsen": 1},
    ),
    "000010638006": StratagemToolDescriptor(
        stratagem_id="000010638006",
        name="Mordian Minute",
        timing="shooting_phase_on_select_to_shoot",
        target="ordered_astra_militarum_infantry_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_strength_bonus",
        cp_cost=1,
        effect_params={"strength_bonus": 1, "order_key": "FIRST_RANK_FIRE"},
    ),
    "000010638005": StratagemToolDescriptor(
        stratagem_id="000010638005",
        name="Purging Fire",
        timing="shooting_phase_on_select_to_shoot",
        target="ordered_astra_militarum_unit_within_objective_range_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_lethal_hits",
        cp_cost=1,
    ),
    "000010638004": StratagemToolDescriptor(
        stratagem_id="000010638004",
        name="Veteran Sharpshooters",
        timing="shooting_phase_on_select_to_shoot",
        target="astra_militarum_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ignore_cover",
        cp_cost=1,
    ),
    "000010638002": StratagemToolDescriptor(
        stratagem_id="000010638002",
        name="Snap To It",
        timing="start_of_any_phase",
        target="astra_militarum_officer_unit",
        duration="immediate",
        effect="issue_order_as_if_command_phase",
        cp_cost=1,
        effect_params={"orders": 1},
    ),
    "000010638003": StratagemToolDescriptor(
        stratagem_id="000010638003",
        name="No Retreat!",
        timing="command_phase",
        target="astra_militarum_unit_with_duty_and_honour_order",
        duration="until_opponent_controls_start_or_end_of_phase",
        effect="sticky_objective",
        cp_cost=1,
    ),
}

_GRIZZLED_COMPANY_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GRIZZLED_COMPANY_STRATAGEM_DESCRIPTORS.values()
}

_RAD_ZONE_CORPS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008386002": StratagemToolDescriptor(
        stratagem_id="000008386002",
        name="Baleful Halo",
        timing="fight_phase_after_enemy_targets_selected",
        target="adeptus_mechanicus_non_vehicle_unit_targeted_by_attacker",
        duration="until_end_of_turn",
        effect="defensive_wound_penalty",
        cp_cost=2,
        effect_params={
            "wound_roll_modifier": -1,
            "optional_support_if_primary_battleline": True,
            "support_target": "friendly_skitarii_unit_non_battleline_within_6",
            "support_selection_optional": True,
        },
    ),
    "000008386003": StratagemToolDescriptor(
        stratagem_id="000008386003",
        name="Extinction Order",
        timing="command_phase",
        target="tech_priest_model_and_objective_within_24",
        duration="immediate",
        effect="objective_range_enemy_mortal_wounds_and_battleshock_test",
        cp_cost=1,
        range_in=24.0,
        effect_params={
            "roll": "D6",
            "threshold": 4,
            "mortal_wounds": 1,
            "battle_shock_test": True,
        },
    ),
    "000008386004": StratagemToolDescriptor(
        stratagem_id="000008386004",
        name="Aggressor Imperative",
        timing="movement_phase_on_select_to_move",
        target="skitarii_unit_not_yet_moved",
        duration="until_end_of_phase",
        effect="advance_no_roll_plus_6",
        cp_cost=1,
        effect_params={
            "advance_distance": 6,
            "optional_support_if_primary_battleline": True,
            "support_target": "friendly_skitarii_unit_non_battleline_within_6_not_yet_moved",
            "support_selection_optional": True,
        },
    ),
    "000008386005": StratagemToolDescriptor(
        stratagem_id="000008386005",
        name="Pre-Calibrated Purge Solution",
        timing="shooting_phase_on_select_to_shoot",
        target="adeptus_mechanicus_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_hit_reroll_vs_opponent_deployment_zone",
        cp_cost=1,
        effect_params={
            "optional_support_if_primary_battleline": True,
            "support_target": "friendly_skitarii_unit_non_battleline_within_6",
            "support_selection_optional": True,
        },
    ),
    "000008386006": StratagemToolDescriptor(
        stratagem_id="000008386006",
        name="Lethal Dosage",
        timing="shooting_phase_on_select_to_shoot",
        target="adeptus_mechanicus_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_lethal_hits",
        cp_cost=1,
        effect_params={
            "optional_support_if_primary_battleline": True,
            "support_target": "friendly_skitarii_unit_non_battleline_within_6",
            "support_selection_optional": True,
        },
    ),
    "000008386007": StratagemToolDescriptor(
        stratagem_id="000008386007",
        name="Bulwark Imperative",
        timing="opponent_shooting_phase_after_targets_selected",
        target="skitarii_unit_targeted_by_attacker",
        duration="until_end_of_phase",
        effect="invulnerable_save",
        cp_cost=2,
        effect_params={
            "invulnerable_save": 4,
            "optional_support_if_primary_battleline": True,
            "support_target": "friendly_skitarii_unit_non_battleline_within_6",
            "support_selection_optional": True,
        },
    ),
}

_RAD_ZONE_CORPS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RAD_ZONE_CORPS_STRATAGEM_DESCRIPTORS.values()
}

_HALLOWED_MARTYRS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008469004": StratagemToolDescriptor(
        stratagem_id="000008469004",
        name="Righteous Vengeance",
        timing="fight_phase_on_select_to_fight",
        target="adepta_sororitas_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="melee_hit_reroll_and_conditional_wound_reroll",
        cp_cost=1,
        effect_params={"reroll_hit_full": True, "reroll_wound_full_vs_target_below_half_strength": True},
    ),
    "000008469003": StratagemToolDescriptor(
        stratagem_id="000008469003",
        name="Suffering and Sacrifice",
        timing="fight_phase_start",
        target="adepta_sororitas_infantry_or_walker_unit",
        duration="until_end_of_phase",
        effect="engaged_enemy_target_lock",
        cp_cost=1,
    ),
    "000008469006": StratagemToolDescriptor(
        stratagem_id="000008469006",
        name="Spirit of the Martyr",
        timing="opponent_fight_phase_after_targets_selected",
        target="adepta_sororitas_unit_targeted_not_yet_fought",
        duration="until_end_of_phase",
        effect="fight_on_death_after_attacks",
        cp_cost=2,
        effect_params={"roll_required": False},
    ),
    "000008469007": StratagemToolDescriptor(
        stratagem_id="000008469007",
        name="Praise the Fallen",
        timing="opponent_shooting_phase_after_enemy_shoots",
        target="adepta_sororitas_unit_that_lost_models_to_attacker",
        duration="immediate",
        effect="reactive_shooting",
        cp_cost=1,
        effect_params={"target_restriction": "enemy_attacker_only"},
    ),
    "000008469005": StratagemToolDescriptor(
        stratagem_id="000008469005",
        name="Sanctified Immolation",
        timing="any_phase_before_destroyed_model_removed",
        target="destroyed_adepta_sororitas_vehicle_model_with_deadly_demise",
        duration="immediate",
        effect="auto_trigger_deadly_demise",
        cp_cost=1,
    ),
    "000008469002": StratagemToolDescriptor(
        stratagem_id="000008469002",
        name="Divine Intervention",
        timing="any_phase_on_friendly_character_destroyed",
        target="destroyed_adepta_sororitas_character_unit_excluding_saint_celestine",
        duration="end_of_current_phase",
        effect="return_destroyed_model_with_d3_plus_discarded_wounds",
        cp_cost=1,
        effect_params={"miracle_dice_discard_min": 1, "miracle_dice_discard_max": 3, "once_per_unit_per_battle": True},
    ),
}

_HALLOWED_MARTYRS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _HALLOWED_MARTYRS_STRATAGEM_DESCRIPTORS.values()
}

_ARMY_OF_FAITH_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009038007": StratagemToolDescriptor(
        stratagem_id="000009038007",
        name="Angelic Descent",
        timing="end_of_opponent_fight_phase",
        target="adepta_sororitas_jump_pack_unit_not_engaged",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
    ),
}

_ARMY_OF_FAITH_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ARMY_OF_FAITH_STRATAGEM_DESCRIPTORS.values()
}

_BRINGERS_OF_FLAME_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009034007": StratagemToolDescriptor(
        stratagem_id="000009034007",
        name="Blazing Ire",
        timing="opponent_shooting_phase_after_enemy_shoots",
        target="adepta_sororitas_transport_targeted_by_enemy_attacker_with_embarked_units",
        duration="immediate",
        effect="reactive_disembark_then_reactive_shooting",
        cp_cost=2,
        effect_params={
            "max_disembark_units": 1,
            "target_restriction": "enemy_attacker_only",
        },
    ),
    "000009034004": StratagemToolDescriptor(
        stratagem_id="000009034004",
        name="Carry Forth the Faithful",
        timing="movement_phase_before_transport_advances",
        target="adepta_sororitas_transport_not_yet_selected_to_move",
        duration="until_end_of_turn",
        effect="transport_advance_reroll_and_disembark_after_advance_no_charge",
        cp_cost=1,
        effect_params={
            "allow_disembark_after_advance": True,
            "disembark_counts_as_normal_move": True,
            "disembarking_units_cannot_charge": True,
            "reroll_advance_for_transport": True,
        },
    ),
}

_BRINGERS_OF_FLAME_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _BRINGERS_OF_FLAME_STRATAGEM_DESCRIPTORS.values()
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

_AUGURIUM_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010365006": StratagemToolDescriptor(
        stratagem_id="000010365006",
        name="Redirected Strike",
        timing="end_of_your_command_phase",
        target="grey_knights_psyker_unit_not_engaged_with_deep_strike",
        duration="immediate",
        effect="enter_strategic_reserves_if_deep_strike",
        cp_cost=1,
        effect_params={"requires_deep_strike": True},
    ),
    "000010365007": StratagemToolDescriptor(
        stratagem_id="000010365007",
        name="Mirage of Echoes",
        timing="opponent_movement_phase_reinforcements_step_after_enemy_setup",
        target="grey_knights_psyker_unit_within_12_not_engaged_with_deep_strike",
        duration="immediate",
        effect="enter_strategic_reserves_if_deep_strike",
        cp_cost=1,
        range_in=12.0,
        effect_params={"requires_deep_strike": True, "requires_enemy_setup_context": True},
    ),
}

_AUGURIUM_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AUGURIUM_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_BROTHERHOOD_STRIKE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010349003": StratagemToolDescriptor(
        stratagem_id="000010349003",
        name="Combat Manifestation",
        timing="movement_phase_reinforcements_step",
        target="grey_knights_unit_arriving_from_deep_strike",
        duration="this_turn_and_phase",
        effect="deep_strike_min_distance_override_with_no_charge",
        cp_cost=1,
        effect_params={"min_distance": 6, "distance_type": "horizontal", "cannot_charge_this_turn": True},
    ),
}

_BROTHERHOOD_STRIKE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _BROTHERHOOD_STRIKE_STRATAGEM_DESCRIPTORS.values()
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

_CHAOS_CULT_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008982002": StratagemToolDescriptor(
        stratagem_id="000008982002",
        name="Chosen for Glory",
        timing="shooting_or_fight_phase_on_select_to_shoot_or_fight",
        target="damned_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="desperate_pact_hit_reroll_with_conditional_wound_reroll",
        cp_cost=1,
        effect_params={"reroll_hit": True, "reroll_wound_if_leadership_passed": True},
    ),
    "000008982003": StratagemToolDescriptor(
        stratagem_id="000008982003",
        name="Selfless Demise",
        timing="opponent_fight_phase_after_enemy_targets_selected",
        target="damned_unit_targeted_by_enemy_melee_attacks",
        duration="until_attacker_finishes_attacks",
        effect="post_attack_mortal_retaliation_on_destroyed_models",
        cp_cost=1,
        effect_params={"threshold": 6, "mortal_wounds": 1, "attack_type": "melee"},
    ),
    "000008982004": StratagemToolDescriptor(
        stratagem_id="000008982004",
        name="Infernal Sacrifice",
        timing="fight_phase_on_select_to_fight",
        target="damned_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="desperate_pact_with_extra_self_mortals_and_melee_attacks_strength_bonus",
        cp_cost=1,
        effect_params={
            "extra_self_mortal_wounds": "D3",
            "melee_attacks_bonus": 1,
            "melee_strength_bonus_if_leadership_passed": 1,
        },
    ),
    "000008982005": StratagemToolDescriptor(
        stratagem_id="000008982005",
        name="Crazed Focus",
        timing="shooting_phase_on_select_to_shoot",
        target="damned_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="desperate_pact_ranged_ap_bonus_with_conditional_strength_bonus",
        cp_cost=1,
        effect_params={"ranged_ap_bonus": 1, "ranged_strength_bonus_if_leadership_passed": 1},
    ),
    "000008982006": StratagemToolDescriptor(
        stratagem_id="000008982006",
        name="Reckless Haste",
        timing="charge_phase",
        target="damned_unit_not_yet_selected_to_charge",
        duration="until_end_of_phase",
        effect="charge_after_advance",
        cp_cost=1,
    ),
    "000008982007": StratagemToolDescriptor(
        stratagem_id="000008982007",
        name="Mortal Thralls",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="heretic_astartes_unit_targeted_with_visible_damned_support_within_3",
        duration="until_end_of_phase",
        effect="redirect_pre_wound_roll_hits_to_support_unit_as_mortal_wounds",
        cp_cost=1,
        range_in=3.0,
    ),
}

_CHAOS_CULT_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CHAOS_CULT_STRATAGEM_DESCRIPTORS.values()
}

_CREATIONS_OF_BILE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009774003": StratagemToolDescriptor(
        stratagem_id="000009774003",
        name="Masters Are Watching",
        timing="either_fight_phase_after_enemy_targets_selected",
        target="heretic_astartes_infantry_unit_targeted_by_enemy_melee_attacks",
        duration="until_end_of_phase",
        effect="fight_on_death_after_attacks",
        cp_cost=1,
        effect_params={
            "roll_required": True,
            "roll_threshold": 4,
            "damned_roll_modifier": -1,
            "attack_type": "melee",
        },
    ),
    "000009774004": StratagemToolDescriptor(
        stratagem_id="000009774004",
        name="Specimens for the Spider",
        timing="either_fight_phase_on_select_to_fight",
        target="heretic_astartes_infantry_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="melee_wound_reroll_vs_character_with_post_fight_battleshock",
        cp_cost=2,
        range_in=6.0,
        effect_params={
            "attack_type": "melee",
            "reroll_wound_full_vs_character": True,
            "post_fight_battleshock_range": 6.0,
            "warlord_destroyed_tests_all": True,
        },
    ),
    "000009774005": StratagemToolDescriptor(
        stratagem_id="000009774005",
        name="Delayed Mutations",
        timing="command_phase",
        target="creations_of_bile_heretic_astartes_infantry_unit_excluding_damned",
        duration="until_start_of_next_command_phase",
        effect="self_mortal_wounds_then_gain_experimental_augmentation",
        cp_cost=2,
        effect_params={
            "self_mortal_wounds": "D3",
            "augmentation_source": "experimental_augmentations",
            "grants_additional_augmentation": True,
        },
    ),
    "000009774006": StratagemToolDescriptor(
        stratagem_id="000009774006",
        name="Diabolic Regeneration",
        timing="command_phase",
        target="creations_of_bile_heretic_astartes_infantry_unit_with_destroyed_non_character_models",
        duration="immediate",
        effect="return_models",
        cp_cost=1,
        effect_params={
            "return_models_max": 1,
            "battleline_return_models_roll": "D3",
            "exclude_character": True,
        },
    ),
    "000009774007": StratagemToolDescriptor(
        stratagem_id="000009774007",
        name="Autostimulants",
        timing="charge_phase",
        target="heretic_astartes_infantry_unit_not_yet_selected_to_charge",
        duration="until_end_of_phase",
        effect="charge_after_advance",
        cp_cost=1,
    ),
}

_CREATIONS_OF_BILE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CREATIONS_OF_BILE_STRATAGEM_DESCRIPTORS.values()
}

_DECEPTORS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008965002": StratagemToolDescriptor(
        stratagem_id="000008965002",
        name="Detonator",
        timing="any_phase_on_enemy_deadly_demise_destroyed",
        target="heretic_astartes_character_unit_within_18_of_destroyed_model",
        duration="immediate",
        effect="auto_trigger_enemy_deadly_demise",
        cp_cost=1,
        range_in=18.0,
        effect_params={"exclude_keywords": ["TITANIC"]},
    ),
    "000008965003": StratagemToolDescriptor(
        stratagem_id="000008965003",
        name="From All Sides",
        timing="charge_phase_start",
        target="heretic_astartes_unit",
        duration="until_end_of_phase",
        effect="charge_roll_bonus_per_other_friendly_charge",
        cp_cost=1,
        effect_params={"max_bonus": 3, "other_friendly_keyword": "HERETIC ASTARTES"},
    ),
    "000008965004": StratagemToolDescriptor(
        stratagem_id="000008965004",
        name="Pick Them Off",
        timing="shooting_phase_on_select_to_shoot",
        target="heretic_astartes_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_hit_reroll_vs_below_starting_and_wound_reroll_vs_below_half",
        cp_cost=1,
    ),
    "000008965005": StratagemToolDescriptor(
        stratagem_id="000008965005",
        name="Coils of Deception",
        timing="movement_phase_after_fall_back",
        target="heretic_astartes_unit_that_fell_back",
        duration="until_end_of_turn",
        effect="shoot_after_fall_back",
        cp_cost=1,
    ),
    "000008965006": StratagemToolDescriptor(
        stratagem_id="000008965006",
        name="Relentless Pursuit",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="heretic_astartes_infantry_or_mounted_unit_within_9_not_engaged",
        duration="immediate",
        effect="reactive_normal_move_up_to_6",
        cp_cost=1,
        range_in=9.0,
        effect_params={"max_distance": 6},
    ),
    "000008965007": StratagemToolDescriptor(
        stratagem_id="000008965007",
        name="Scrambled Coordinates",
        timing="opponent_movement_phase_reinforcements_step_start",
        target="heretic_astartes_unit",
        duration="until_end_of_phase",
        effect="enemy_reserves_arrival_min_distance_from_unit",
        cp_cost=1,
        effect_params={"min_distance": 12, "distance_type": "horizontal"},
    ),
}

_DECEPTORS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DECEPTORS_STRATAGEM_DESCRIPTORS.values()
}

_DREAD_TALONS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008973002": StratagemToolDescriptor(
        stratagem_id="000008973002",
        name="Depthless Cruelty",
        timing="fight_phase_on_select_to_fight",
        target="heretic_astartes_infantry_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="conditional_melee_ap_bonus_vs_battleshocked_or_below_half",
        cp_cost=1,
        effect_params={"ap_bonus": 1},
    ),
    "000008973003": StratagemToolDescriptor(
        stratagem_id="000008973003",
        name="Bloody Example",
        timing="fight_phase_after_destroying_character",
        target="heretic_astartes_unit_that_destroyed_enemy_character",
        duration="immediate",
        effect="battle_shock_all_visible_enemies_within_range_after_destroying_character",
        cp_cost=1,
        range_in=12.0,
    ),
    "000008973004": StratagemToolDescriptor(
        stratagem_id="000008973004",
        name="Pitiless Hunters",
        timing="shooting_phase_on_select_to_shoot",
        target="heretic_astartes_infantry_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_hit_and_wound_reroll_vs_battleshocked_or_below_half",
        cp_cost=1,
    ),
    "000008973005": StratagemToolDescriptor(
        stratagem_id="000008973005",
        name="Relentless Terror",
        timing="movement_phase_after_fall_back",
        target="heretic_astartes_infantry_unit_that_fell_back",
        duration="until_end_of_turn",
        effect="charge_after_fall_back",
        cp_cost=1,
    ),
    "000008973006": StratagemToolDescriptor(
        stratagem_id="000008973006",
        name="Screaming Descent",
        timing="movement_phase_reinforcements_step_start",
        target="heretic_astartes_jump_pack_unit_in_reserves",
        duration="until_end_of_phase",
        effect="deep_strike_min_distance_override_with_no_charge_and_post_arrival_battleshock",
        cp_cost=1,
        effect_params={"min_distance": 6, "distance_type": "horizontal", "no_charge": True, "battle_round_min": 2},
    ),
    "000008973007": StratagemToolDescriptor(
        stratagem_id="000008973007",
        name="Merciless Pursuit",
        timing="opponent_movement_phase_end",
        target="heretic_astartes_infantry_unit_not_engaged_with_enemy_fell_back_within_6",
        duration="immediate",
        effect="out_of_turn_charge_without_charge_bonus",
        cp_cost=1,
        range_in=6.0,
    ),
}

_DREAD_TALONS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DREAD_TALONS_STRATAGEM_DESCRIPTORS.values()
}

_FELLHAMMER_SIEGE_HOST_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008977002": StratagemToolDescriptor(
        stratagem_id="000008977002",
        name="Persistent Assailants",
        timing="fight_phase_after_enemy_targets_selected",
        target="heretic_astartes_unit_targeted_not_yet_fought",
        duration="until_end_of_phase",
        effect="melee_hit_reroll_with_conditional_wound_reroll_when_below_half",
        cp_cost=1,
    ),
    "000008977003": StratagemToolDescriptor(
        stratagem_id="000008977003",
        name="Brutal Attrition",
        timing="opponent_fight_phase_after_enemy_targets_selected",
        target="heretic_astartes_infantry_unit_targeted_by_enemy_melee_attacks_excluding_damned",
        duration="until_end_of_phase",
        effect="post_attack_allocated_melee_mortal_retaliation",
        cp_cost=1,
        effect_params={"threshold": 4, "mortal_wounds": 1, "max_rolls_per_attacker_unit": 6},
    ),
    "000008977004": StratagemToolDescriptor(
        stratagem_id="000008977004",
        name="Pitiless Cannonade",
        timing="shooting_phase_on_select_to_shoot",
        target="heretic_astartes_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_critical_hits_on_5plus_vs_below_half",
        cp_cost=1,
        effect_params={"critical_hit_threshold": 5},
    ),
    "000008977005": StratagemToolDescriptor(
        stratagem_id="000008977005",
        name="Point-Blank Destruction",
        timing="shooting_phase_on_select_to_shoot",
        target="heretic_astartes_unit_engaged_not_yet_shot",
        duration="until_end_of_phase",
        effect="grant_non_blast_ranged_weapons_pistol",
        cp_cost=1,
    ),
    "000008977006": StratagemToolDescriptor(
        stratagem_id="000008977006",
        name="Steadfast Determination",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="heretic_astartes_unit_targeted_excluding_damned",
        duration="until_end_of_phase",
        effect="feel_no_pain",
        cp_cost=1,
        effect_params={"value": 5},
    ),
    "000008977007": StratagemToolDescriptor(
        stratagem_id="000008977007",
        name="Siegecraft",
        timing="opponent_charge_phase_start",
        target="heretic_astartes_unit",
        duration="until_end_of_phase",
        effect="charge_roll_penalty",
        cp_cost=1,
        effect_params={"charge_roll_modifier": -2, "non_cumulative_negative": True},
    ),
}

_FELLHAMMER_SIEGE_HOST_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _FELLHAMMER_SIEGE_HOST_STRATAGEM_DESCRIPTORS.values()
}

_HURONS_MARAUDERS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010689002": StratagemToolDescriptor(
        stratagem_id="000010689002",
        name="Hardened Killers",
        timing="your_command_phase",
        target="damned_unit",
        duration="until_start_of_your_next_command_phase",
        effect="choose_hardened_killers_benefit",
        cp_cost=1,
        effect_params={
            "choices": ["BALLISTIC_SKILL", "RAPID_FIRE", "SAVE"],
        },
    ),
    "000010689003": StratagemToolDescriptor(
        stratagem_id="000010689003",
        name="At the Tyrant's Command",
        timing="your_movement_phase",
        target="heretic_astartes_unit_excluding_monster_vehicle",
        duration="until_end_of_turn",
        effect="shoot_and_charge_after_advance_or_fall_back",
        cp_cost=1,
        effect_params={
            "allow_after_advance": True,
            "allow_after_fall_back": False,
            "attack_type": "ranged_and_charge",
        },
    ),
    "000010689004": StratagemToolDescriptor(
        stratagem_id="000010689004",
        name="Seize the Prize",
        timing="movement_phase_after_selected_to_advance",
        target="same_heretic_astartes_unit_excluding_monster_vehicle",
        duration="until_end_of_phase",
        effect="advance_no_roll_fixed_distance",
        cp_cost=1,
        effect_params={
            "fixed_advance_distance": 6,
        },
    ),
    "000010689005": StratagemToolDescriptor(
        stratagem_id="000010689005",
        name="Reavers' Flurry",
        timing="fight_phase_on_select_to_fight",
        target="heretic_astartes_unit_that_charged_and_not_yet_fought",
        duration="until_end_of_phase",
        effect="melee_attacks_bonus",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "melee_attacks_bonus": 1,
        },
    ),
    "000010689006": StratagemToolDescriptor(
        stratagem_id="000010689006",
        name="To the Favoured the Spoils",
        timing="opponent_shooting_phase_after_shooting_resolved_and_lost_wounds",
        target="heretic_astartes_unit_that_lost_wounds",
        duration="immediate",
        effect="reactive_surge_move_towards_closest_non_aircraft_enemy",
        cp_cost=1,
        effect_params={
            "distance_roll": "D6",
            "allow_engagement_range": True,
        },
    ),
    "000010689007": StratagemToolDescriptor(
        stratagem_id="000010689007",
        name="Encircling Surge",
        timing="end_of_opponent_fight_phase",
        target="heretic_astartes_unit_excluding_monster_vehicle_within_6_of_edge_not_engaged",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        range_in=6.0,
        effect_params={
            "requires_not_engaged": True,
            "distance_to_battlefield_edge": 6.0,
        },
    ),
}

_HURONS_MARAUDERS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _HURONS_MARAUDERS_STRATAGEM_DESCRIPTORS.values()
}

_VETERANS_OF_THE_LONG_WAR_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008961002": StratagemToolDescriptor(
        stratagem_id="000008961002",
        name="Endless Ire",
        timing="any_phase_after_focus_of_hatred_destroyed",
        target="heretic_astartes_character_unit_excluding_damned",
        duration="until_start_of_your_next_command_phase",
        effect="replace_focus_of_hatred_target",
        cp_cost=2,
        range_in=12.0,
        effect_params={
            "requires_visibility": True,
            "target_selection": "enemy_unit_within_12",
        },
    ),
    "000008961003": StratagemToolDescriptor(
        stratagem_id="000008961003",
        name="Contemptuous Disregard",
        timing="opponent_shooting_or_fight_phase_after_enemy_targets_selected",
        target="heretic_astartes_unit_targeted_by_enemy_attacks_excluding_damned",
        duration="until_attacking_unit_finishes_attacks",
        effect="defensive_ap_worsen",
        cp_cost=1,
        effect_params={"ap_worsen": 1},
    ),
    "000008961004": StratagemToolDescriptor(
        stratagem_id="000008961004",
        name="Bringers of Despair",
        timing="fight_phase_start",
        target="heretic_astartes_unit_within_engagement_range_of_focus_of_hatred_excluding_damned",
        duration="until_end_of_phase",
        effect="grant_fights_first",
        cp_cost=2,
    ),
    "000008961005": StratagemToolDescriptor(
        stratagem_id="000008961005",
        name="Black Crusade",
        timing="your_movement_phase",
        target="heretic_astartes_infantry_or_mounted_unit_excluding_damned",
        duration="until_end_of_turn",
        effect="shoot_after_advance_or_fall_back_and_conditional_bolt_devastating_wounds",
        cp_cost=1,
        effect_params={
            "shoot_after_advance": True,
            "shoot_after_fall_back": True,
            "weapon_names": ["bolt pistol", "boltgun", "combi-bolter"],
            "devastating_wounds_cap": 6,
        },
    ),
    "000008961006": StratagemToolDescriptor(
        stratagem_id="000008961006",
        name="Let the Galaxy Burn",
        timing="your_shooting_phase",
        target="heretic_astartes_unit_not_yet_shot_excluding_tzeentch",
        duration="until_end_of_phase",
        effect="ranged_ignores_cover_and_torrent_attacks_set_6",
        cp_cost=1,
        effect_params={"ignores_cover": True, "torrent_attacks": 6},
    ),
    "000008961007": StratagemToolDescriptor(
        stratagem_id="000008961007",
        name="Millennia of Experience",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="heretic_astartes_infantry_or_mounted_unit_within_9_not_engaged_excluding_damned",
        duration="immediate",
        effect="reactive_normal_move_up_to_6",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "distance": 6,
            "trigger_enemy_actions": ["normal_move", "advance", "fall_back"],
            "requires_not_in_engagement_range": True,
        },
    ),
}

_VETERANS_OF_THE_LONG_WAR_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _VETERANS_OF_THE_LONG_WAR_STRATAGEM_DESCRIPTORS.values()
}

_RENEGADE_RAIDERS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008969002": StratagemToolDescriptor(
        stratagem_id="000008969002",
        name="Unfailingly Obdurate",
        timing="opponent_shooting_or_fight_phase_after_targets_selected",
        target="heretic_astartes_unit_targeted_excluding_damned",
        duration="until_attacking_unit_finishes_attacks",
        effect="defensive_ap_worsen",
        cp_cost=1,
        effect_params={
            "ap_worsen": 1,
            "excluded_keywords_any": ["DAMNED"],
        },
    ),
    "000008969003": StratagemToolDescriptor(
        stratagem_id="000008969003",
        name="Scour and Seize",
        timing="fight_phase_before_selected_to_fight",
        target="heretic_astartes_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="conditional_precision_if_target_within_objective_range",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "granted_weapon_keywords": ["PRECISION"],
            "requires_target_within_objective_range": True,
        },
    ),
    "000008969004": StratagemToolDescriptor(
        stratagem_id="000008969004",
        name="Opportunistic Raiders",
        timing="end_of_fight_phase",
        target="heretic_astartes_unit_eligible_to_fight_this_phase",
        duration="immediate",
        effect="end_of_fight_reactive_move_or_fall_back",
        cp_cost=1,
        effect_params={
            "requires_eligible_to_fight_this_phase": True,
            "normal_move_distance": 6,
            "mounted_normal_move_distance": 12,
            "fall_back_if_engaged": True,
            "forbid_embark_if_disembarked_this_turn": True,
        },
    ),
    "000008969005": StratagemToolDescriptor(
        stratagem_id="000008969005",
        name="Warpcharged Engines",
        timing="your_movement_phase_before_selected_to_move",
        target="heretic_astartes_transport_or_mounted_unit_not_yet_selected_to_move",
        duration="until_end_of_phase",
        effect="advance_no_roll_fixed_distance",
        cp_cost=1,
        effect_params={
            "fixed_advance_distance": 6,
            "required_keywords_any": ["TRANSPORT", "MOUNTED"],
        },
    ),
    "000008969006": StratagemToolDescriptor(
        stratagem_id="000008969006",
        name="Ruinous Raid",
        timing="your_shooting_or_fight_phase_before_selected_to_shoot_or_fight",
        target="heretic_astartes_unit_that_disembarked_this_turn_and_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="conditional_hit_and_wound_reroll_if_target_within_objective_range",
        cp_cost=1,
        effect_params={
            "reroll_hit_full": True,
            "reroll_wound_full": True,
            "requires_disembarked_from_transport_this_turn": True,
            "requires_target_within_objective_range": True,
        },
    ),
    "000008969007": StratagemToolDescriptor(
        stratagem_id="000008969007",
        name="Reavers' Haste",
        timing="your_charge_phase",
        target="heretic_astartes_infantry_or_mounted_unit_not_yet_attempted_charge",
        duration="until_end_of_phase",
        effect="charge_after_advance_and_conditional_charge_bonus_vs_objective_target",
        cp_cost=1,
        effect_params={
            "allow_charge_after_advance": True,
            "charge_bonus_if_target_within_objective_range": 1,
        },
    ),
}

_RENEGADE_RAIDERS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RENEGADE_RAIDERS_STRATAGEM_DESCRIPTORS.values()
}

_RENEGADE_WARBAND_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010695002": StratagemToolDescriptor(
        stratagem_id="000010695002",
        name="Never Outgunned",
        timing="shooting_or_fight_phase_after_selected_to_shoot_or_fight",
        target="heretic_astartes_unit_just_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="choose_temporary_weapon_keyword_bonus",
        cp_cost=1,
        effect_params={
            "choices": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
            "shooting_attack_type": "ranged",
            "fight_attack_type": "melee",
        },
    ),
    "000010695003": StratagemToolDescriptor(
        stratagem_id="000010695003",
        name="Vengeful Destruction",
        timing="shooting_or_fight_phase_after_selected_to_shoot_or_fight",
        target="heretic_astartes_infantry_excluding_damned_or_mounted_unit_just_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="wound_bonus_vs_vendetta_target",
        cp_cost=1,
        effect_params={
            "wound_bonus": 1,
            "requires_vendetta_target": True,
        },
    ),
    "000010695004": StratagemToolDescriptor(
        stratagem_id="000010695004",
        name="Undying Hatred",
        timing="fight_phase_after_enemy_targets_selected",
        target="heretic_astartes_unit_targeted_by_enemy_attacks",
        duration="until_end_of_phase",
        effect="fight_on_death_roll",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "base_threshold": 4,
        },
    ),
    "000010695005": StratagemToolDescriptor(
        stratagem_id="000010695005",
        name="Renegade Claim",
        timing="your_movement_phase",
        target="heretic_astartes_unit_within_range_of_controlled_objective",
        duration="until_opponent_control_greater_end_of_phase",
        effect="sticky_objective",
        cp_cost=1,
    ),
    "000010695006": StratagemToolDescriptor(
        stratagem_id="000010695006",
        name="Corrupted Munitions",
        timing="shooting_phase_after_selected_to_shoot",
        target="heretic_astartes_unit_just_selected_to_shoot",
        duration="until_end_of_phase",
        effect="ranged_ap_bonus",
        cp_cost=1,
        effect_params={"ap_bonus": 1},
    ),
    "000010695007": StratagemToolDescriptor(
        stratagem_id="000010695007",
        name="Reavers' Reaction",
        timing="opponent_shooting_phase_after_enemy_shooting_resolved_and_hit",
        target="heretic_astartes_unit_hit_by_enemy_shooting_excluding_monster_vehicle",
        duration="immediate",
        effect="reactive_normal_move_d6",
        cp_cost=1,
        effect_params={"distance_roll": "D6"},
    ),
}

_RENEGADE_WARBAND_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RENEGADE_WARBAND_STRATAGEM_DESCRIPTORS.values()
}

_SOULFORGED_WARPACK_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008986002": StratagemToolDescriptor(
        stratagem_id="000008986002",
        name="Desperate Pledge",
        timing="shooting_or_fight_phase",
        target="heretic_astartes_daemon_vehicle_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="contract_invocation_ap_bonus",
        cp_cost=1,
        effect_params={"ap_bonus": 1},
    ),
    "000008986003": StratagemToolDescriptor(
        stratagem_id="000008986003",
        name="Glut of Souls",
        timing="fight_phase",
        target="heretic_astartes_daemon_vehicle_unit_not_yet_selected_to_fight_excluding_titanic",
        duration="until_end_of_phase",
        effect="contract_invocation_heal_on_destroyed_models",
        cp_cost=1,
        effect_params={"heal_roll": "D6", "success_on": 5, "heal_cap": 6},
    ),
    "000008986004": StratagemToolDescriptor(
        stratagem_id="000008986004",
        name="Daemonic Posession",
        timing="command_phase",
        target="heretic_astartes_vehicle_unit_excluding_daemon",
        duration="until_end_of_battle",
        effect="grant_daemon_keyword_until_battle_end",
        cp_cost=1,
        effect_params={"granted_keyword": "DAEMON"},
    ),
    "000008986005": StratagemToolDescriptor(
        stratagem_id="000008986005",
        name="Unstoppable Rampage",
        timing="movement_or_charge_phase_before_selected_to_move_or_charge",
        target="heretic_astartes_vehicle_or_vashtorr_unit_not_yet_selected_to_move_or_charge",
        duration="until_end_of_phase",
        effect="move_through_terrain_horizontally",
        cp_cost=1,
        effect_params={"movement_phases": ["move", "advance", "charge"]},
    ),
    "000008986006": StratagemToolDescriptor(
        stratagem_id="000008986006",
        name="Predatory Pursuit",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="heretic_astartes_vehicle_or_vashtorr_unit_within_9_not_in_engagement_range",
        duration="immediate",
        effect="reactive_normal_move_toward_trigger_unit",
        cp_cost=1,
        range_in=9.0,
        effect_params={"max_distance": 6, "must_end_closer_to_trigger_unit": True},
    ),
    "000008986007": StratagemToolDescriptor(
        stratagem_id="000008986007",
        name="Feeding Frenzy",
        timing="opponent_movement_phase_on_enemy_fall_back_start",
        target="heretic_astartes_daemon_vehicle_or_vashtorr_unit_in_engagement_range_of_falling_back_enemy",
        duration="until_end_of_phase",
        effect="enemy_fall_back_desperate_escape_battleshock_penalty",
        cp_cost=1,
        effect_params={"exclude_monster_vehicle": True, "battleshock_penalty": 1},
    ),
}

_SOULFORGED_WARPACK_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SOULFORGED_WARPACK_STRATAGEM_DESCRIPTORS.values()
}

_PACTBOUND_ZEALOTS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008358002": StratagemToolDescriptor(
        stratagem_id="000008358002",
        name="Eye of the Gods",
        timing="fight_phase_after_destroying_enemy_unit",
        target="heretic_astartes_character_model_in_character_unit_that_destroyed_enemy_unit",
        duration="until_end_of_battle",
        effect="permanent_characteristic_and_melee_weapon_bonus_after_destroying_enemy_unit",
        cp_cost=1,
        effect_params={
            "movement_bonus": 1,
            "toughness_bonus": 1,
            "wounds_bonus": 1,
            "melee_attacks_bonus": 1,
            "melee_strength_bonus": 1,
            "melee_damage_bonus": 1,
            "excluded_keywords_any": ["DAMNED", "DAEMON", "EPIC HERO"],
        },
    ),
    "000008358003": StratagemToolDescriptor(
        stratagem_id="000008358003",
        name="Eternal Hate",
        timing="opponent_fight_phase_after_enemy_targets_selected",
        target="heretic_astartes_unit_targeted_by_enemy_attacks",
        duration="until_end_of_phase",
        effect="fight_on_death_roll",
        cp_cost=1,
        effect_params={
            "base_threshold": 4,
            "khorne_threshold_modifier": -1,
            "attack_type": "melee",
        },
    ),
    "000008358004": StratagemToolDescriptor(
        stratagem_id="000008358004",
        name="Profane Zeal",
        timing="shooting_or_fight_phase_before_selected_to_shoot_or_fight",
        target="heretic_astartes_chaos_undivided_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="wound_reroll_full",
        cp_cost=1,
        effect_params={
            "reroll_wound_full": True,
            "required_keywords_all": ["HERETIC ASTARTES", "CHAOS UNDIVIDED"],
        },
    ),
    "000008358005": StratagemToolDescriptor(
        stratagem_id="000008358005",
        name="Skinshift",
        timing="your_command_phase",
        target="heretic_astartes_unit",
        duration="immediate",
        effect="heal_and_conditional_return_destroyed_model",
        cp_cost=1,
        effect_params={
            "heal_wounds": 3,
            "return_model_count": 1,
            "return_model_full_wounds": True,
            "return_requires_mark": "TZEENTCH",
            "return_requires_below_starting_strength": True,
            "return_excluded_keywords_any": ["CHARACTER"],
        },
    ),
    "000008358006": StratagemToolDescriptor(
        stratagem_id="000008358006",
        name="Torpefying Refrain",
        timing="your_movement_phase",
        target="heretic_astartes_unit",
        duration="until_end_of_turn",
        effect="charge_after_fall_back_and_conditional_shoot_charge_after_advance_or_fall_back",
        cp_cost=1,
        effect_params={
            "charge_after_fall_back": True,
            "conditional_mark": "SLAANESH",
            "conditional_shoot_after_advance": True,
            "conditional_shoot_after_fall_back": True,
            "conditional_charge_after_advance": True,
            "conditional_charge_after_fall_back": True,
        },
    ),
    "000008358007": StratagemToolDescriptor(
        stratagem_id="000008358007",
        name="Festering Miasma",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="heretic_astartes_unit_targeted_by_enemy_attacks",
        duration="until_end_of_phase",
        effect="grant_stealth_and_conditional_ranged_targeting_cap",
        cp_cost=1,
        effect_params={
            "grant_stealth": True,
            "conditional_mark": "NURGLE",
            "conditional_targeting_range": 18,
        },
    ),
}

_PACTBOUND_ZEALOTS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _PACTBOUND_ZEALOTS_STRATAGEM_DESCRIPTORS.values()
}

_NIGHTMARE_HUNT_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010642002": StratagemToolDescriptor(
        stratagem_id="000010642002",
        name="Talons Sunk Deep",
        timing="shooting_or_fight_phase_on_select_to_shoot_or_fight",
        target="heretic_astartes_infantry_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="conditional_ap_bonus_vs_battleshocked_or_below_half",
        cp_cost=1,
        effect_params={"ap_bonus": 1},
    ),
    "000010642003": StratagemToolDescriptor(
        stratagem_id="000010642003",
        name="Prey on the Weak",
        timing="shooting_or_fight_phase_on_select_to_shoot_or_fight",
        target="heretic_astartes_infantry_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="hit_reroll_vs_battleshocked_or_below_half",
        cp_cost=1,
        effect_params={"reroll_hit_full": True},
    ),
    "000010642004": StratagemToolDescriptor(
        stratagem_id="000010642004",
        name="Sadistic Display",
        timing="fight_phase_after_destroying_enemy_unit",
        target="heretic_astartes_unit_that_destroyed_enemy_unit",
        duration="immediate",
        effect="battle_shock_all_visible_non_monster_non_vehicle_enemies_within_range_after_destroying_enemy_unit",
        cp_cost=1,
        range_in=6.0,
    ),
    "000010642005": StratagemToolDescriptor(
        stratagem_id="000010642005",
        name="Malicious Surge",
        timing="your_charge_phase",
        target="heretic_astartes_infantry_unit",
        duration="until_end_of_phase",
        effect="charge_after_advance",
        cp_cost=1,
        effect_params={"required_keywords_all": ["HERETIC ASTARTES", "INFANTRY"]},
    ),
    "000010642006": StratagemToolDescriptor(
        stratagem_id="000010642006",
        name="Relentless Terror",
        timing="movement_phase_after_fall_back",
        target="heretic_astartes_infantry_unit_that_fell_back",
        duration="until_end_of_turn",
        effect="eligible_to_shoot_and_charge_after_fall_back",
        cp_cost=1,
        effect_params={"shoot_after_fall_back": True, "charge_after_fall_back": True},
    ),
    "000010642007": StratagemToolDescriptor(
        stratagem_id="000010642007",
        name="Horrific Incursion",
        timing="movement_phase_after_arriving_from_reserves",
        target="heretic_astartes_unit_set_up_from_reserves_this_turn",
        duration="immediate",
        effect="visible_enemy_battleshock_test_minus_one_after_arriving_from_reserves",
        cp_cost=1,
        range_in=12.0,
        effect_params={
            "battle_shock_test_modifier": -1,
            "requires_arrived_from_reserves_this_turn": True,
            "excluded_keywords_any": ["MONSTER", "VEHICLE"],
        },
    ),
}

_NIGHTMARE_HUNT_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NIGHTMARE_HUNT_STRATAGEM_DESCRIPTORS.values()
}

_SLAANESHS_CHOSEN_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010019002": StratagemToolDescriptor(
        stratagem_id="000010019002",
        name="Devoted Duellists",
        timing="fight_phase_on_select_to_fight",
        target="emperors_children_character_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="grant_sustained_hits_vs_selected_enemy",
        cp_cost=1,
        effect_params={"sustained_hits_value": 1, "attack_type": "melee", "requires_enemy_target": True},
    ),
    "000010019003": StratagemToolDescriptor(
        stratagem_id="000010019003",
        name="Beautiful Death",
        timing="opponent_fight_phase_after_enemy_targets_selected",
        target="emperors_children_character_unit_targeted",
        duration="until_end_of_phase",
        effect="fight_on_death_roll",
        cp_cost=1,
        effect_params={"roll": "D6", "threshold": 4, "favoured_champions_bonus": 1, "deferred_until_attacker_finishes": True},
    ),
    "000010019004": StratagemToolDescriptor(
        stratagem_id="000010019004",
        name="Heightened Jealousy",
        timing="shooting_or_fight_phase_when_favoured_champions_updated_or_enemy_destroyed",
        target="favoured_champions_emperors_children_character_unit",
        duration="until_end_of_phase",
        effect="grant_strength_bonus_to_non_favoured_character_units",
        cp_cost=1,
        effect_params={"strength_bonus": 1},
    ),
    "000010019005": StratagemToolDescriptor(
        stratagem_id="000010019005",
        name="Diabolic Majesty",
        timing="shooting_or_fight_phase_when_favoured_champions_updated",
        target="favoured_champions_emperors_children_character_unit",
        duration="immediate",
        effect="battle_shock_test_aura",
        cp_cost=1,
        range_in=6.0,
        effect_params={"battle_shock_modifier": -1, "once_per_battle_round": True},
    ),
    "000010019006": StratagemToolDescriptor(
        stratagem_id="000010019006",
        name="Refusal to Be Outdone",
        timing="charge_phase",
        target="emperors_children_character_unit",
        duration="until_end_of_phase",
        effect="charge_roll_bonus_vs_selected_enemy_within_engagement",
        cp_cost=1,
        effect_params={"charge_roll_bonus": 2},
    ),
    "000010019007": StratagemToolDescriptor(
        stratagem_id="000010019007",
        name="Vengeful Surge",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="emperors_children_character_unit_targeted",
        duration="immediate_after_attacker_resolves",
        effect="reactive_surge_move_towards_closest_enemy",
        cp_cost=1,
        effect_params={"distance_roll": "D6", "allow_reroll_if_not_favoured_champions": True, "allow_engagement_range": True},
    ),
}

_SLAANESHS_CHOSEN_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SLAANESHS_CHOSEN_STRATAGEM_DESCRIPTORS.values()
}

_COURT_OF_THE_PHOENICIAN_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010655007": StratagemToolDescriptor(
        stratagem_id="000010655007",
        name="Catalytic Stimulus",
        timing="opponent_shooting_phase_after_shooting_resolved_and_lost_wounds",
        target="emperors_children_unit_that_lost_wounds",
        duration="immediate",
        effect="reactive_stimulus_move_towards_closest_non_aircraft_enemy",
        cp_cost=1,
        effect_params={"distance_roll": "D6", "allow_engagement_range": True},
    ),
    "000010655005": StratagemToolDescriptor(
        stratagem_id="000010655005",
        name="Close-Quarters Excruciation",
        timing="shooting_phase_on_select_to_shoot",
        target="emperors_children_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_strength_and_ap_bonus_within_12",
        cp_cost=1,
        range_in=12.0,
        effect_params={"strength_bonus": 1, "ap_bonus": 1},
    ),
    "000010655002": StratagemToolDescriptor(
        stratagem_id="000010655002",
        name="Contemptuous Disregard",
        timing="shooting_or_fight_phase_after_enemy_targets_selected",
        target="emperors_children_unit_targeted",
        duration="until_end_of_phase",
        effect="defensive_wound_penalty_if_strength_gt_toughness",
        cp_cost=1,
        effect_params={"wound_roll_modifier": -1, "condition": "attacker_strength_greater_than_target_toughness"},
    ),
    "000010655006": StratagemToolDescriptor(
        stratagem_id="000010655006",
        name="Euphoric Inspiration",
        timing="charge_phase_on_declare_charge",
        target="emperors_children_daemon_unit",
        duration="until_end_of_phase",
        effect="grant_charge_reroll_aura",
        cp_cost=1,
        range_in=6.0,
        effect_params={"aura_target_keyword": "EMPEROR'S CHILDREN"},
    ),
    "000010655003": StratagemToolDescriptor(
        stratagem_id="000010655003",
        name="Prideful Superiority",
        timing="fight_phase_on_select_to_fight",
        target="emperors_children_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="reroll_hits_and_wounds_vs_character",
        cp_cost=2,
        effect_params={"target_keywords_any": ["CHARACTER"], "reroll_hit_full": True, "reroll_wound_full": True},
    ),
    "000010655004": StratagemToolDescriptor(
        stratagem_id="000010655004",
        name="Sinuous Breach",
        timing="movement_or_charge_phase_on_select",
        target="emperors_children_daemon_unit_not_yet_selected_for_action",
        duration="until_end_of_phase",
        effect="move_through_terrain",
        cp_cost=1,
        effect_params={"move_types": ["move", "advance", "charge"]},
    ),
}

_COURT_OF_THE_PHOENICIAN_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _COURT_OF_THE_PHOENICIAN_STRATAGEM_DESCRIPTORS.values()
}

_CARNIVAL_OF_EXCESS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010011002": StratagemToolDescriptor(
        stratagem_id="000010011002",
        name="Sustained by Agony",
        timing="fight_phase_on_friendly_emperors_children_destroy_enemy_unit",
        target="emperors_children_source_and_legions_of_excess_unit_within_6",
        duration="immediate",
        effect="heal_or_return_models",
        cp_cost=1,
        range_in=6.0,
        effect_params={"heal_amount": 3, "daemonettes_return_roll": "D3+3"},
    ),
    "000010011003": StratagemToolDescriptor(
        stratagem_id="000010011003",
        name="Ecstatic Slaughter",
        timing="fight_phase_on_friendly_legions_of_excess_destroy_enemy_unit",
        target="legions_of_excess_source_and_emperors_children_unit_within_6_not_engaged",
        duration="immediate",
        effect="out_of_turn_charge",
        cp_cost=1,
        range_in=6.0,
        effect_params={"out_of_turn": True},
    ),
    "000010011004": StratagemToolDescriptor(
        stratagem_id="000010011004",
        name="Violent Crescendo",
        timing="fight_phase_on_select_to_fight",
        target="slaanesh_beasts_infantry_mounted_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="pile_in_and_consolidate_override_with_closest_enemy_unit_rule",
        cp_cost=2,
        effect_params={"pile_in_distance": 6, "consolidate_distance": 6, "closest_enemy_unit_rule": True},
    ),
    "000010011005": StratagemToolDescriptor(
        stratagem_id="000010011005",
        name="Sycophantic Surge",
        timing="charge_phase",
        target="legions_of_excess_unit",
        duration="until_end_of_phase",
        effect="charge_after_advance_or_fall_back_with_target_condition",
        cp_cost=1,
        effect_params={"requires_at_least_one_target_engaged_with_friendly_emperors_children": True},
    ),
    "000010011006": StratagemToolDescriptor(
        stratagem_id="000010011006",
        name="Uncanny Reactions",
        timing="opponent_shooting_phase_after_targets_selected",
        target="slaanesh_unit_targeted_by_attacker",
        duration="until_end_of_phase",
        effect="hit_roll_penalty",
        cp_cost=1,
        effect_params={"hit_modifier": -1},
    ),
    "000010011007": StratagemToolDescriptor(
        stratagem_id="000010011007",
        name="Dark Apparitions",
        timing="end_of_opponent_fight_phase",
        target="daemonettes_unit_not_engaged",
        duration="until_next_movement_phase_reinforcements_step",
        effect="enter_strategic_reserves_with_temp_deep_strike",
        cp_cost=2,
        effect_params={
            "deep_strike_min_distance": 6,
            "distance_type": "horizontal",
            "requires_friendly_emperors_children_wholly_within": 9,
        },
    ),
}

_CARNIVAL_OF_EXCESS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CARNIVAL_OF_EXCESS_STRATAGEM_DESCRIPTORS.values()
}

_COTERIE_OF_THE_CONCEITED_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010015005": StratagemToolDescriptor(
        stratagem_id="000010015005",
        name="Martial Perfection",
        timing="fight_phase_on_select_to_fight",
        target="emperors_children_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="hit_reroll",
        cp_cost=1,
        effect_params={"reroll_hit_full": True},
    ),
    "000010015006": StratagemToolDescriptor(
        stratagem_id="000010015006",
        name="Unbound Arrogance",
        timing="any_phase_on_friendly_unit_destroyed",
        target="emperors_children_unit_that_destroyed_an_enemy",
        duration="immediate",
        effect="increase_pledge",
        cp_cost=1,
        effect_params={"pledge_delta": 1, "once_per_battle_round": True},
    ),
    "000010015003": StratagemToolDescriptor(
        stratagem_id="000010015003",
        name="Unshakeable Opponents",
        timing="command_phase",
        target="emperors_children_unit",
        duration="until_end_of_turn",
        effect="ignore_skill_hit_wound_modifiers",
        cp_cost=1,
    ),
    "000010015002": StratagemToolDescriptor(
        stratagem_id="000010015002",
        name="Protection of the Dark Prince",
        timing="any_phase_after_attack_or_mortal_wound_allocated",
        target="emperors_children_unit_with_allocated_model",
        duration="until_end_of_phase",
        effect="feel_no_pain_with_mortal_bonus",
        cp_cost=1,
        effect_params={"fnp": 6, "fnp_vs_mortal": 4},
    ),
    "000010015004": StratagemToolDescriptor(
        stratagem_id="000010015004",
        name="Embrace the Pain",
        timing="fight_phase_start",
        target="emperors_children_infantry_unit",
        duration="until_end_of_phase",
        effect="engaged_enemy_target_lock",
        cp_cost=1,
    ),
    "000010015007": StratagemToolDescriptor(
        stratagem_id="000010015007",
        name="Armour of Abhorrence",
        timing="opponent_shooting_or_fight_phase_after_targets_selected",
        target="emperors_children_unit_targeted",
        duration="until_attacking_unit_finishes_attacks",
        effect="ap_worsen",
        cp_cost=1,
        effect_params={"ap_worsen": 1},
    ),
}

_COTERIE_OF_THE_CONCEITED_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _COTERIE_OF_THE_CONCEITED_STRATAGEM_DESCRIPTORS.values()
}

_MERCURIAL_HOST_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009999002": StratagemToolDescriptor(
        stratagem_id="000009999002",
        name="Violent Excess",
        timing="fight_phase_on_select_to_fight",
        target="emperors_children_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="grant_sustained_hits_melee",
        cp_cost=1,
        effect_params={"sustained_hits_value": 1, "attack_type": "melee"},
    ),
    "000009999003": StratagemToolDescriptor(
        stratagem_id="000009999003",
        name="Combat Stimms",
        timing="fight_phase_after_enemy_targets_selected",
        target="emperors_children_infantry_unit_targeted",
        duration="until_end_of_phase",
        effect="defensive_wound_penalty",
        cp_cost=2,
        effect_params={"wound_roll_modifier": -1},
    ),
    "000009999004": StratagemToolDescriptor(
        stratagem_id="000009999004",
        name="Honour the Prince",
        timing="movement_phase_before_select_to_move",
        target="emperors_children_infantry_unit_not_yet_moved",
        duration="until_end_of_phase",
        effect="advance_no_roll_plus_6",
        cp_cost=1,
        effect_params={"advance_distance": 6},
    ),
    "000009999005": StratagemToolDescriptor(
        stratagem_id="000009999005",
        name="Dark Vigour",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="emperors_children_unit_within_9_excluding_beasts_vehicles",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        range_in=9.0,
        effect_params={"max_distance": 6, "movement_type": "normal"},
    ),
    "000009999006": StratagemToolDescriptor(
        stratagem_id="000009999006",
        name="Capricious Reactions",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="emperors_children_unit_targeted",
        duration="until_end_of_phase",
        effect="defensive_hit_penalty",
        cp_cost=1,
        effect_params={"hit_roll_modifier": -1},
    ),
    "000009999007": StratagemToolDescriptor(
        stratagem_id="000009999007",
        name="Cruel Raiders",
        timing="end_of_opponent_fight_phase",
        target="emperors_children_unit_wholly_within_9_of_battlefield_edge_and_not_within_3h_enemy",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        range_in=9.0,
        effect_params={"horizontal_enemy_exclusion_range": 3},
    ),
}

_MERCURIAL_HOST_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _MERCURIAL_HOST_STRATAGEM_DESCRIPTORS.values()
}

_RAPID_EVISCERATION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010007003": StratagemToolDescriptor(
        stratagem_id="000010007003",
        name="Advance and Claim",
        timing="command_phase_start",
        target="emperors_children_transport_with_embarked_tormentors_on_controlled_objective",
        duration="until_opponent_control_greater_end_of_phase",
        effect="sticky_objective",
        cp_cost=1,
        effect_params={"requires_embarked_keyword": "TORMENTORS"},
    ),
    "000010007005": StratagemToolDescriptor(
        stratagem_id="000010007005",
        name="Ceaseless Onslaught",
        timing="charge_phase",
        target="emperors_children_unit_disembarked_this_turn_from_friendly_transport_that_made_normal_move",
        duration="until_end_of_phase",
        effect="allow_charge_after_disembark",
        cp_cost=1,
    ),
    "000010007004": StratagemToolDescriptor(
        stratagem_id="000010007004",
        name="Dynamic Breakthrough",
        timing="movement_phase",
        target="emperors_children_vehicle_unit_not_yet_moved",
        duration="until_end_of_phase",
        effect="move_through_enemy_except_monster_vehicle",
        cp_cost=1,
        effect_params={"move_types": ["move", "advance", "fall_back"], "auto_pass_desperate_escape": True},
    ),
    "000010007002": StratagemToolDescriptor(
        stratagem_id="000010007002",
        name="Onto the Next",
        timing="end_of_fight_phase",
        target="emperors_children_unit_that_destroyed_enemy_this_phase_and_transport_within_6",
        duration="immediate",
        effect="embark_transport_if_within_6",
        cp_cost=1,
        range_in=6.0,
    ),
    "000010007007": StratagemToolDescriptor(
        stratagem_id="000010007007",
        name="Outflanking Strike",
        timing="end_of_opponent_fight_phase",
        target="one_or_two_emperors_children_transport_units_wholly_within_9_of_battlefield_edge",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        range_in=9.0,
        effect_params={"max_units": 2, "two_targets_require_dedicated_transport": True},
    ),
    "000010007006": StratagemToolDescriptor(
        stratagem_id="000010007006",
        name="Reactive Disembarkation",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="emperors_children_transport_unit_targeted_by_enemy_with_embarked_units",
        duration="immediate",
        effect="reactive_disembark_one_unit",
        cp_cost=1,
        range_in=6.0,
        effect_params={"max_units": 1},
    ),
}

_RAPID_EVISCERATION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RAPID_EVISCERATION_STRATAGEM_DESCRIPTORS.values()
}

_ARMOURED_WARHOST_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009770007": StratagemToolDescriptor(
        stratagem_id="000009770007",
        name="Anti-Grav Repulsion",
        timing="opponent_charge_phase_after_charge_declared",
        target="aeldari_vehicle_fly_unit_selected_as_charge_target",
        duration="until_end_of_phase",
        effect="enemy_charge_roll_modifier",
        cp_cost=1,
        effect_params={"charge_roll_modifier": -2},
    ),
    "000009770005": StratagemToolDescriptor(
        stratagem_id="000009770005",
        name="Cloudstrike",
        timing="movement_phase_reinforcements_step_start",
        target="aeldari_vehicle_fly_unit_in_strategic_reserves",
        duration="until_end_of_turn",
        effect="temporary_deep_strike_with_6_in_and_no_charge",
        cp_cost=1,
        effect_params={
            "grant_deep_strike": True,
            "deep_strike_min_distance": 6,
            "no_charge_after_6_in_arrival": True,
            "transport_disembark_min_enemy_horizontal_distance": 6,
            "transport_disembark_no_charge": True,
        },
    ),
    "000009770002": StratagemToolDescriptor(
        stratagem_id="000009770002",
        name="Layered Wards",
        timing="any_phase_after_mortal_wound_allocated",
        target="aeldari_vehicle_unit_allocated_mortal_wound",
        duration="until_end_of_phase",
        effect="feel_no_pain_vs_mortals",
        cp_cost=1,
        effect_params={"feel_no_pain_value": 5, "condition": "against mortal wounds"},
    ),
    "000008375002": StratagemToolDescriptor(
        stratagem_id="000008375002",
        name="Angelic Grace",
        timing="any_phase_after_mortal_wound_allocated",
        target="adeptus_astartes_unit_allocated_mortal_wound",
        duration="until_end_of_phase",
        effect="feel_no_pain_vs_mortals",
        cp_cost=1,
        effect_params={"feel_no_pain_value": 5, "condition": "against mortal wounds"},
    ),
    "000009844002": StratagemToolDescriptor(
        stratagem_id="000009844002",
        name="Fuelled by Faith",
        timing="any_phase_after_mortal_wound_allocated",
        target="adeptus_astartes_unit_allocated_mortal_wound",
        duration="until_end_of_phase",
        effect="feel_no_pain_vs_mortals",
        cp_cost=1,
        effect_params={"feel_no_pain_value": 5, "condition": "against mortal wounds"},
    ),
    "000009770006": StratagemToolDescriptor(
        stratagem_id="000009770006",
        name="Soulsight",
        timing="shooting_phase_on_select",
        target="aeldari_vehicle_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="selected_to_shoot_one_hit_one_wound_one_damage_reroll",
        cp_cost=1,
        effect_params={"reroll_hit": True, "reroll_wound": True, "reroll_damage": True},
    ),
    "000009770003": StratagemToolDescriptor(
        stratagem_id="000009770003",
        name="Swift Deployment",
        timing="movement_phase_after_transport_advanced",
        target="aeldari_transport_unit_that_advanced",
        duration="until_end_of_phase",
        effect="allow_disembark_after_advance_no_charge",
        cp_cost=1,
        effect_params={"allow_disembark_after_advance": True, "disembarking_units_cannot_charge": True},
    ),
    "000009770004": StratagemToolDescriptor(
        stratagem_id="000009770004",
        name="Vectored Engines",
        timing="movement_phase_after_fall_back",
        target="aeldari_vehicle_fly_unit_that_fell_back",
        duration="until_end_of_turn",
        effect="shoot_after_fall_back",
        cp_cost=1,
    ),
}

_ARMOURED_WARHOST_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ARMOURED_WARHOST_STRATAGEM_DESCRIPTORS.values()
}

_ASPECT_HOST_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009928005": StratagemToolDescriptor(
        stratagem_id="000009928005",
        name="Doom Inescapable",
        timing="shooting_phase",
        target="avatar_of_khaine_model_not_yet_shot",
        duration="until_end_of_phase",
        effect="wailing_doom_range_and_damage_override",
        cp_cost=1,
        effect_params={"weapon_name": "Wailing Doom", "range": 18, "damage": 8},
    ),
    "000009928007": StratagemToolDescriptor(
        stratagem_id="000009928007",
        name="Khaine's Vengeance",
        timing="opponent_movement_phase_after_selected_to_fall_back",
        target="aspect_warriors_or_avatar_within_engagement_of_falling_back_enemy",
        duration="immediate",
        effect="force_desperate_escape_test",
        cp_cost=1,
        effect_params={"exclude_enemy_keywords": ["MONSTER", "VEHICLE"], "battleshock_roll_modifier": -1},
    ),
    "000009928006": StratagemToolDescriptor(
        stratagem_id="000009928006",
        name="Preternatural Precision",
        timing="shooting_phase",
        target="aspect_warriors_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="select_ranged_weapon_keywords_with_optional_token_spend",
        cp_cost=1,
        effect_params={
            "aspect_shrine_token_optional": True,
            "choices": ["IGNORES COVER", "LETHAL HITS", "SUSTAINED HITS 1"],
            "choice_count_without_token": 1,
            "choice_count_with_token": 2,
        },
    ),
    "000009928004": StratagemToolDescriptor(
        stratagem_id="000009928004",
        name="Skyborne Sanctuary",
        timing="end_of_fight_phase",
        target="asuryani_unit_and_friendly_transport",
        duration="immediate",
        effect="embark_transport_if_within_6_and_not_engaged",
        cp_cost=1,
        range_in=6.0,
    ),
    "000009928003": StratagemToolDescriptor(
        stratagem_id="000009928003",
        name="To Their Final Breath",
        timing="fight_phase_after_enemy_targets_selected",
        target="aspect_warriors_or_avatar_unit_targeted_not_yet_fought",
        duration="until_end_of_phase",
        effect="fight_on_death_after_attacks_with_optional_token_bonus",
        cp_cost=1,
        effect_params={
            "base_threshold": 4,
            "token_spend_bonus": 1,
            "token_spend_optional": True,
            "requires_melee_destroyed_by_attacker": True,
        },
    ),
    "000009928002": StratagemToolDescriptor(
        stratagem_id="000009928002",
        name="Warrior Focus",
        timing="shooting_or_fight_phase_on_select",
        target="aspect_warriors_or_avatar_unit_not_yet_selected",
        duration="until_end_of_phase",
        effect="ignore_attack_characteristic_and_hit_modifiers",
        cp_cost=1,
        effect_params={
            "ignore_modifiers": [
                "ballistic_skill",
                "weapon_skill",
                "strength",
                "armour_penetration",
                "damage",
                "hit_roll",
            ]
        },
    ),
}

_ASPECT_HOST_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ASPECT_HOST_STRATAGEM_DESCRIPTORS.values()
}

_CORSAIR_COTERIE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010705002": StratagemToolDescriptor(
        stratagem_id="000010705002",
        name="Pirates' Due",
        timing="fight_phase_on_select_to_fight",
        target="aeldari_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="wound_reroll_ones_and_conditional_full_reroll",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "reroll_wound_ones": True,
            "full_reroll_if_anhrathe_and_target_within_objective_range": True,
        },
    ),
    "000010705003": StratagemToolDescriptor(
        stratagem_id="000010705003",
        name="Lethal Ruse",
        timing="movement_phase_after_fall_back",
        target="aeldari_unit_that_fell_back",
        duration="until_end_of_turn_and_immediate",
        effect="charge_after_fall_back_and_conditional_mortal_wounds",
        cp_cost=1,
        effect_params={
            "charge_after_fall_back": True,
            "anhrathe_mortal_roll": "6D6",
            "mortal_wound_threshold": 4,
            "mortal_wounds_per_success": 1,
            "enemy_must_be_engaged_at_phase_start": True,
        },
    ),
    "000010705004": StratagemToolDescriptor(
        stratagem_id="000010705004",
        name="Outcast Ambush",
        timing="shooting_phase_before_select_to_shoot",
        target="rangers_or_shroud_runners_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="grant_ranged_ignores_cover_rapid_fire_and_ap_bonus",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "grant_keywords": ["IGNORES COVER", "RAPID FIRE 1"],
            "ap_bonus": 1,
        },
    ),
    "000010705005": StratagemToolDescriptor(
        stratagem_id="000010705005",
        name="Into the Breach",
        timing="shooting_phase_after_shooting_unit_destroys_enemy_unit",
        target="anhrathe_unit_that_destroyed_enemy_unit",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        effect_params={
            "distance_roll": "D6+1",
            "movement_type": "normal",
        },
    ),
    "000010705006": StratagemToolDescriptor(
        stratagem_id="000010705006",
        name="Cloak and Shadow",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="aeldari_infantry_unit_targeted_within_controlled_objective_range",
        duration="until_end_of_phase",
        effect="grant_stealth_and_ranged_targeting_distance_cap",
        cp_cost=1,
        effect_params={
            "stealth": True,
            "attack_type": "ranged",
            "max_targeting_distance": 18,
        },
    ),
    "000010705007": StratagemToolDescriptor(
        stratagem_id="000010705007",
        name="Vengeful Sorrow",
        timing="opponent_shooting_phase_after_enemy_shoots",
        target="aeldari_infantry_unit_that_lost_models_not_battleshocked_not_engaged",
        duration="immediate",
        effect="reactive_surge_move_toward_closest_enemy",
        cp_cost=1,
        effect_params={
            "distance_roll": "D6+1",
            "allow_engagement_range": True,
            "closest_enemy_exclude_keywords": ["AIRCRAFT"],
        },
    ),
}

_CORSAIR_COTERIE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CORSAIR_COTERIE_STRATAGEM_DESCRIPTORS.values()
}

_SEER_COUNCIL_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009924002": StratagemToolDescriptor(
        stratagem_id="000009924002",
        name="Presentiment of Dread",
        timing="command_phase",
        target="asuryani_psyker_model_then_visible_enemy_unit_within_18",
        duration="immediate",
        effect="force_battleshock_test_with_modifier",
        cp_cost=1,
        range_in=18.0,
        effect_params={
            "battle_shock_roll_modifier": -1,
            "visibility_required": True,
        },
    ),
    "000009924003": StratagemToolDescriptor(
        stratagem_id="000009924003",
        name="Forewarned",
        timing="fight_phase_after_enemy_targets_selected",
        target="asuryani_infantry_non_wraith_construct_selected_as_enemy_fight_target_within_9_of_friendly_asuryani_psyker",
        duration="until_end_of_phase",
        effect="defensive_hit_and_wound_penalty",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "attack_type": "any",
            "hit_roll_modifier": -1,
            "wound_roll_modifier": -1,
        },
    ),
    "000009924004": StratagemToolDescriptor(
        stratagem_id="000009924004",
        name="Unshrouded Truth",
        timing="your_movement_phase",
        target="asuryani_infantry_non_wraith_construct_not_selected_to_move_not_set_up_this_phase_within_9_of_friendly_asuryani_psyker",
        duration="immediate_and_until_end_of_phase",
        effect="redeploy_unit_more_than_9_horizontal_from_enemy_models_and_mark_not_eligible_to_move",
        cp_cost=1,
        effect_params={
            "setup_min_distance": 9,
            "setup_distance_type": "horizontal",
            "move_ineligible_until_end_of_phase": True,
        },
    ),
    "000009924005": StratagemToolDescriptor(
        stratagem_id="000009924005",
        name="Fate Inescapable",
        timing="your_shooting_phase",
        target="asuryani_infantry_non_wraith_construct_not_selected_to_shoot_within_9_of_friendly_asuryani_psyker",
        duration="until_end_of_phase",
        effect="ranged_ignores_cover_and_critical_wound_ap_bonus",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "attack_type": "ranged",
            "grant_keywords": ["IGNORES COVER"],
            "critical_wound_ap_bonus": 1,
        },
    ),
    "000009924006": StratagemToolDescriptor(
        stratagem_id="000009924006",
        name="Isha's Fury",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="asuryani_psyker_within_9_of_enemy_unit_that_ended_normal_advance_or_fall_back_move",
        duration="immediate",
        effect="roll_6d6_each_3plus_deals_1_mortal_wound_to_moved_enemy_unit",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "roll": "6D6",
            "threshold": 3,
            "mortal_wounds_per_success": 1,
            "trigger_actions": ["normal_move", "advance", "fall_back"],
        },
    ),
    "000009924007": StratagemToolDescriptor(
        stratagem_id="000009924007",
        name="Psychic Shield",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="asuryani_infantry_non_wraith_construct_selected_as_enemy_ranged_target_within_9_of_friendly_asuryani_psyker",
        duration="until_end_of_phase",
        effect="ranged_targeting_range_restriction",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "attack_type": "ranged",
            "targeting_range": 18,
        },
    ),
}

_SEER_COUNCIL_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SEER_COUNCIL_STRATAGEM_DESCRIPTORS.values()
}

_SPIRIT_CONCLAVE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009908002": StratagemToolDescriptor(
        stratagem_id="000009908002",
        name="Seer's Eye",
        timing="your_shooting_or_fight_phase",
        target="aeldari_psyker_model_and_wraith_construct_unit_within_12_and_visible_enemy_unit",
        duration="until_end_of_phase",
        effect="ignore_ap_and_damage_modifiers_against_selected_enemy",
        cp_cost=1,
        effect_params={
            "distance_inches": 12.0,
            "affected_characteristics": ["armour_penetration", "damage"],
        },
    ),
    "000009908003": StratagemToolDescriptor(
        stratagem_id="000009908003",
        name="Wraithbone Armour",
        timing="opponent_shooting_or_fight_phase_after_enemy_targets_selected",
        target="non_titanic_wraith_construct_unit_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="defensive_damage_reduction",
        cp_cost=1,
        effect_params={"damage_reduction": 1},
    ),
    "000009908004": StratagemToolDescriptor(
        stratagem_id="000009908004",
        name="Blades from Beyond",
        timing="your_fight_phase",
        target="wraithblades_wraithlord_or_wraithknight_unit_not_selected_to_fight",
        duration="until_end_of_phase",
        effect="grant_devastating_wounds_to_melee_weapons",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "grant_keywords": ["DEVASTATING WOUNDS"],
        },
    ),
    "000009908005": StratagemToolDescriptor(
        stratagem_id="000009908005",
        name="Soul Bridge",
        timing="your_command_phase",
        target="wraithblades_wraithguard_or_wraithlord_unit_and_asuryani_psyker_model",
        duration="until_start_of_your_next_command_phase",
        effect="count_as_within_12_of_selected_psyker_for_psychic_guidance_and_spirit_guides",
        cp_cost=1,
        effect_params={
            "distance_inches": 12.0,
            "applies_to_abilities": ["Psychic Guidance", "Spirit Guides"],
        },
    ),
    "000009908006": StratagemToolDescriptor(
        stratagem_id="000009908006",
        name="Spirit Token",
        timing="start_of_your_movement_phase",
        target="wraithblades_or_wraithguard_unit_within_range_of_controlled_objective",
        duration="until_opponent_controls_objective",
        effect="sticky_objective",
        cp_cost=1,
        effect_params={"objective_selection_required": True},
    ),
    "000009908007": StratagemToolDescriptor(
        stratagem_id="000009908007",
        name="Crushing Strides",
        timing="your_charge_phase_after_friendly_charge_move_end",
        target="wraithblades_wraithlord_or_wraithknight_unit_that_ended_charge_move_and_enemy_unit_in_engagement_range",
        duration="immediate",
        effect="roll_dice_by_unit_type_each_3plus_deals_1_mortal_wound_to_selected_enemy",
        cp_cost=1,
        effect_params={
            "wraithblades_roll": "models_in_unit_d6",
            "wraithlord_roll": "4D6",
            "wraithknight_roll": "6D6",
            "threshold": 3,
            "mortal_wounds_per_success": 1,
        },
    ),
}

_SPIRIT_CONCLAVE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPIRIT_CONCLAVE_STRATAGEM_DESCRIPTORS.values()
}

_WINDRIDER_HOST_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009904004": StratagemToolDescriptor(
        stratagem_id="000009904004",
        name="Wind of Blades",
        timing="your_movement_phase",
        target="asuryani_mounted_or_vyper_unit_not_selected_to_move",
        duration="until_end_of_turn",
        effect="shoot_and_charge_after_advance_or_fall_back",
        cp_cost=1,
        effect_params={
            "advance_and_shoot": True,
            "advance_and_charge": True,
            "fall_back_and_shoot": True,
            "fall_back_and_charge": True,
        },
    ),
    "000009904005": StratagemToolDescriptor(
        stratagem_id="000009904005",
        name="Daring Riders",
        timing="start_of_your_movement_phase_reinforcements_step",
        target="asuryani_mounted_or_vyper_unit_in_reserves_that_can_arrive_this_turn",
        duration="this_turn_and_phase",
        effect="deep_strike_min_distance_override_with_conditional_no_charge",
        cp_cost=1,
        effect_params={
            "min_distance": 6,
            "distance_type": "horizontal",
            "conditional_no_charge_if_within": 9,
        },
    ),
    "000009904006": StratagemToolDescriptor(
        stratagem_id="000009904006",
        name="Focused Firepower",
        timing="your_shooting_phase",
        target="asuryani_mounted_or_vyper_unit_not_selected_to_shoot",
        duration="until_end_of_phase",
        effect="ranged_ap_bonus",
        cp_cost=1,
        effect_params={"ap_bonus": 1},
    ),
    "000009904007": StratagemToolDescriptor(
        stratagem_id="000009904007",
        name="Spiralling Evasion",
        timing="opponent_shooting_phase_after_enemy_target_selection",
        target="asuryani_mounted_or_vyper_unit_selected_as_target",
        duration="until_end_of_phase",
        effect="invulnerable_save",
        cp_cost=1,
        effect_params={"invulnerable_save": 4},
    ),
    "000009904002": StratagemToolDescriptor(
        stratagem_id="000009904002",
        name="Death from on High",
        timing="your_shooting_or_fight_phase",
        target="asuryani_mounted_or_vyper_unit_set_up_from_reserves_this_turn_not_yet_selected",
        duration="until_end_of_phase",
        effect="wound_reroll",
        cp_cost=1,
        effect_params={
            "reroll_wound_full": True,
            "requires_arrived_from_reserves_this_turn": True,
        },
    ),
    "000009904003": StratagemToolDescriptor(
        stratagem_id="000009904003",
        name="Overflight",
        timing="end_of_your_shooting_or_fight_phase",
        target="asuryani_mounted_unit_that_destroyed_enemy_this_phase",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        effect_params={
            "max_distance": 7,
            "movement_type": "normal",
        },
    ),
}

_WINDRIDER_HOST_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _WINDRIDER_HOST_STRATAGEM_DESCRIPTORS.values()
}

_SERPENTS_BROOD_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010650002": StratagemToolDescriptor(
        stratagem_id="000010650002",
        name="Fangs of the Brood",
        timing="start_of_fight_phase",
        target="troupe_unit",
        duration="until_end_of_phase",
        effect="dance_of_death_select_three_abilities",
        cp_cost=1,
        effect_params={
            "abilities": ["HERO", "VILLAIN", "TRICKSTER"],
            "selection_count": 3,
        },
    ),
    "000010650003": StratagemToolDescriptor(
        stratagem_id="000010650003",
        name="Venomous Wrath",
        timing="shooting_phase_on_select_to_shoot",
        target="harlequins_vehicle_unit_not_yet_shot",
        duration="until_end_of_turn",
        effect="post_shoot_reactive_normal_move_no_charge",
        cp_cost=1,
        effect_params={
            "reactive_move_distance_inches": 6.0,
            "requires_not_within_engagement_range_after_shooting": True,
            "cannot_charge_until_end_of_turn": True,
        },
    ),
    "000010650004": StratagemToolDescriptor(
        stratagem_id="000010650004",
        name="Striking Stride",
        timing="charge_phase",
        target="harlequins_unit",
        duration="until_end_of_phase",
        effect="charge_after_advance",
        cp_cost=1,
    ),
    "000010650005": StratagemToolDescriptor(
        stratagem_id="000010650005",
        name="Weavers' Coils",
        timing="end_of_your_fight_phase",
        target="harlequins_mounted_unit_eligible_to_fight_this_phase",
        duration="immediate",
        effect="reactive_normal_or_fall_back_move",
        cp_cost=1,
        effect_params={
            "normal_move_if_not_engaged": True,
            "fall_back_distance_if_engaged_inches": 6.0,
        },
    ),
    "000010650006": StratagemToolDescriptor(
        stratagem_id="000010650006",
        name="Weaving Stride",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="harlequins_infantry_unit_within_9_of_enemy_move_end",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "normal_move_distance_inches": 6.0,
            "trigger_actions": ["normal_move", "advance", "fall_back"],
        },
    ),
    "000010650007": StratagemToolDescriptor(
        stratagem_id="000010650007",
        name="Skyward Lunge",
        timing="end_of_opponent_fight_phase",
        target="harlequins_vehicle_or_mounted_unit_not_within_engagement_range",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
    ),
}

_SERPENTS_BROOD_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SERPENTS_BROOD_STRATAGEM_DESCRIPTORS.values()
}

_GUARDIAN_BATTLEHOST_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009912002": StratagemToolDescriptor(
        stratagem_id="000009912002",
        name="Warding Salvoes",
        timing="your_shooting_phase_or_fight_phase",
        target="dire_avengers_or_guardians_unit_not_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="conditional_wound_reroll_vs_targets_within_objective_range",
        cp_cost=1,
        effect_params={"attack_type": "any", "reroll_wound_full": True, "target_within_objective_range_required": True},
    ),
    "000009912003": StratagemToolDescriptor(
        stratagem_id="000009912003",
        name="Shield Nodes",
        timing="opponent_shooting_or_fight_phase_after_enemy_targets_selected",
        target="dire_avengers_or_guardians_unit_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="conditional_defensive_minus_one_to_wound_if_within_objective_range",
        cp_cost=1,
        effect_params={"attack_type": "any", "wound_roll_modifier": -1, "target_within_objective_range_required": True},
    ),
    "000009912004": StratagemToolDescriptor(
        stratagem_id="000009912004",
        name="Vaul's Vengeance",
        timing="opponent_shooting_or_fight_phase_after_enemy_destroys_guardian_unit",
        target="war_walkers_unit",
        duration="immediate",
        effect="reactive_shooting_at_attacker_once_per_battle_round",
        cp_cost=1,
        effect_params={"force_target_attacker": True, "out_of_phase": True, "once_per_battle_round": True},
    ),
    "000009912005": StratagemToolDescriptor(
        stratagem_id="000009912005",
        name="Time to Strike",
        timing="your_movement_phase",
        target="storm_guardians_unit_not_selected_to_move",
        duration="movement_phase_and_turn",
        effect="fixed_advance_six_and_advance_shoot_charge",
        cp_cost=1,
        effect_params={"fixed_advance_distance": 6, "advance_and_shoot": True, "advance_and_charge": True},
    ),
    "000009912006": StratagemToolDescriptor(
        stratagem_id="000009912006",
        name="Blades of Asuryan",
        timing="your_shooting_phase",
        target="dire_avengers_or_guardians_unit_not_selected_to_shoot",
        duration="until_end_of_phase",
        effect="grant_pistol_to_ranged_weapons_until_end_of_phase",
        cp_cost=1,
        effect_params={"weapon_keyword": "PISTOL", "attack_type": "ranged"},
    ),
    "000009912007": StratagemToolDescriptor(
        stratagem_id="000009912007",
        name="Cost of Victory",
        timing="end_of_opponent_fight_phase",
        target="guardians_unit_not_in_engagement_range",
        duration="immediate",
        effect="enter_strategic_reserves_and_return_destroyed_guardians_models",
        cp_cost=1,
        effect_params={"return_destroyed_model_keyword": "GUARDIANS"},
    ),
}

_GUARDIAN_BATTLEHOST_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GUARDIAN_BATTLEHOST_STRATAGEM_DESCRIPTORS.values()
}

_DEVOTED_OF_YNNEAD_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009920002": StratagemToolDescriptor(
        stratagem_id="000009920002",
        name="Pall of Dread",
        timing="any_phase_on_unit_destroyed",
        target="just_destroyed_ynnari_unit_that_was_within_range_of_previously_controlled_objective",
        duration="until_opponent_controls_objective",
        effect="sticky_objective",
        cp_cost=1,
        effect_params={"objective_selection_required": True, "can_target_destroyed_unit": True},
    ),
    "000009920003": StratagemToolDescriptor(
        stratagem_id="000009920003",
        name="Macabre Resilience",
        timing="shooting_or_fight_phase_after_enemy_select_targets",
        target="ynnari_infantry_or_mounted_non_wraith_construct_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="minus_one_to_wound_against_targeted_unit",
        cp_cost=1,
        effect_params={"attack_type": "any", "wound_modifier": -1},
    ),
    "000009920004": StratagemToolDescriptor(
        stratagem_id="000009920004",
        name="Emissaries of Ynnead",
        timing="fight_phase_after_select_targets",
        target="attacking_ynnari_infantry_unit_that_selected_targets",
        duration="until_end_of_phase",
        effect="reroll_melee_hit_ones_or_full_if_below_starting_strength",
        cp_cost=1,
        effect_params={"attack_type": "melee", "reroll_hit_values": [1], "reroll_hit_full_if_attacker_below_starting_strength": True},
    ),
    "000009920005": StratagemToolDescriptor(
        stratagem_id="000009920005",
        name="Parting the Veil",
        timing="fight_phase_after_enemy_select_targets",
        target="ynnari_unit_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="fight_on_death_after_attacks",
        cp_cost=2,
        effect_params={"attack_type": "melee", "fight_on_death_after_attacks": True, "automatic": True},
    ),
    "000009920006": StratagemToolDescriptor(
        stratagem_id="000009920006",
        name="Soulsight",
        timing="shooting_phase_on_select_to_shoot",
        target="ynnari_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="grant_ranged_lethal_hits_and_ignores_cover",
        cp_cost=1,
        effect_params={"attack_type": "ranged", "grant_keywords": ["LETHAL HITS", "IGNORES COVER"]},
    ),
    "000009920007": StratagemToolDescriptor(
        stratagem_id="000009920007",
        name="Death Answers Death",
        timing="end_of_opponent_shooting_phase",
        target="ynnari_unit_not_wraith_construct_that_lost_models_this_phase",
        duration="immediate",
        effect="shoot_as_if_shooting_phase",
        cp_cost=1,
        effect_params={"out_of_phase": True, "allow_target_selection": "normal_shooting_rules"},
    ),
}

_DEVOTED_OF_YNNEAD_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DEVOTED_OF_YNNEAD_STRATAGEM_DESCRIPTORS.values()
}

_GHOSTS_OF_THE_WEBWAY_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009916002": StratagemToolDescriptor(
        stratagem_id="000009916002",
        name="Staged Death",
        timing="any_phase_on_friendly_character_model_destroyed_before_removal",
        target="just_destroyed_harlequins_character_model_once_per_battle_per_model",
        duration="end_of_phase",
        effect="return_destroyed_model_at_half_wounds_as_close_as_possible_not_in_engagement",
        cp_cost=1,
        effect_params={
            "return_timing": "end_of_phase",
            "wounds_fraction": 0.5,
            "round_up": True,
            "once_per_battle_per_model": True,
            "not_within_engagement_range": True,
        },
    ),
    "000009916003": StratagemToolDescriptor(
        stratagem_id="000009916003",
        name="Heroes' Fall",
        timing="fight_phase_after_enemy_targets_selected",
        target="harlequins_unit_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="fight_on_death_after_attacks",
        cp_cost=1,
        effect_params={"attack_type": "melee", "fight_on_death_after_attacks": True, "threshold": 4},
    ),
    "000009916004": StratagemToolDescriptor(
        stratagem_id="000009916004",
        name="Mocking Flight",
        timing="movement_phase_after_fall_back",
        target="harlequins_unit_that_fell_back",
        duration="until_end_of_turn",
        effect="eligible_to_shoot_and_charge_after_fall_back",
        cp_cost=1,
    ),
    "000009916005": StratagemToolDescriptor(
        stratagem_id="000009916005",
        name="Tricksters' Retort",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="troupe_unit_within_9_of_enemy_moved_unit",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        effect_params={"movement_type": "normal", "max_distance_inches": 6.0},
    ),
    "000009916006": StratagemToolDescriptor(
        stratagem_id="000009916006",
        name="Bloody Dance",
        timing="end_of_opponent_charge_phase",
        target="harlequins_infantry_or_mounted_unit_within_6_of_enemy_it_can_charge",
        duration="immediate",
        effect="out_of_turn_charge_without_charge_bonus",
        cp_cost=1,
        effect_params={"out_of_turn": True, "count_as_charged": False, "range_inches": 6.0},
    ),
    "000009916007": StratagemToolDescriptor(
        stratagem_id="000009916007",
        name="Exit the Stage",
        timing="end_of_opponent_fight_phase",
        target="harlequins_unit_not_within_engagement_range",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
    ),
}

_GHOSTS_OF_THE_WEBWAY_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GHOSTS_OF_THE_WEBWAY_STRATAGEM_DESCRIPTORS.values()
}

_ELDRITCH_RAIDERS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010700002": StratagemToolDescriptor(
        stratagem_id="000010700002",
        name="Raiders' Spoils",
        timing="command_phase",
        target="anhrathe_unit_within_engagement_range",
        duration="until_start_of_next_command_phase",
        effect="objective_control_bonus",
        cp_cost=1,
        effect_params={"objective_control_bonus": 1},
    ),
    "000010700003": StratagemToolDescriptor(
        stratagem_id="000010700003",
        name="Ruthless Killers",
        timing="shooting_or_fight_phase",
        target="corsair_voidscarred_unit_not_selected_this_phase",
        duration="until_end_of_phase",
        effect="damage_characteristic_bonus",
        cp_cost=1,
        effect_params={"damage_bonus": 1, "attack_type": "any"},
    ),
    "000010700004": StratagemToolDescriptor(
        stratagem_id="000010700004",
        name="Yriel's Example",
        timing="fight_phase_after_enemy_targets_selected",
        target="aeldari_infantry_non_wraith_construct_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="feel_no_pain",
        cp_cost=1,
        effect_params={"feel_no_pain_value": 5, "attack_type": "any"},
    ),
    "000010700005": StratagemToolDescriptor(
        stratagem_id="000010700005",
        name="No Prey Too Big",
        timing="your_shooting_phase",
        target="anhrathe_or_rangers_or_shroud_runners_not_selected_to_shoot",
        duration="until_end_of_phase",
        effect="conditional_wound_roll_bonus",
        cp_cost=1,
        effect_params={
            "wound_bonus": 1,
            "condition": "attacker_strength_less_than_target_highest_toughness",
            "attack_type": "ranged",
        },
    ),
    "000010700006": StratagemToolDescriptor(
        stratagem_id="000010700006",
        name="Impeding Fire",
        timing="start_of_opponent_charge_phase",
        target="rangers_shroud_runners_or_starfangs_unit_then_visible_non_titanic_enemy_within_36",
        duration="until_end_of_phase",
        effect="enemy_charge_roll_modifier_non_cumulative_negative",
        cp_cost=1,
        effect_params={"charge_roll_modifier": -2, "range_inches": 36, "exclude_keywords_any": ["TITANIC"]},
    ),
    "000010700007": StratagemToolDescriptor(
        stratagem_id="000010700007",
        name="Withdraw and Reinforce",
        timing="end_of_opponent_fight_phase",
        target="anhrathe_unit_not_within_engagement_range",
        duration="immediate",
        effect="enter_strategic_reserves_and_return_destroyed_models",
        cp_cost=1,
        effect_params={"return_destroyed_models_if_below_starting_strength": True, "skip_character": True},
    ),
}

_ELDRITCH_RAIDERS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ELDRITCH_RAIDERS_STRATAGEM_DESCRIPTORS.values()
}

_REAPERS_WAGER_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009782006": StratagemToolDescriptor(
        stratagem_id="000009782006",
        name="SCINTILLATING TEMPO",
        timing="movement_or_charge_phase_after_friendly_unit_selected_to_move_set_up_or_charge",
        target="drukhari_or_harlequins_unit_selected_to_move_set_up_or_charge",
        duration="until_end_of_turn",
        effect="prevent_overwatch_against_target_unit",
        cp_cost=1,
        effect_params={
            "prevents_stratagem": "FIRE OVERWATCH",
            "triggers": ["normal_move", "advance", "fall_back", "set_up", "declare_charge"],
        },
    ),
}

_REAPERS_WAGER_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _REAPERS_WAGER_STRATAGEM_DESCRIPTORS.values()
}

_SKYSPLINTER_ASSAULT_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010577006": StratagemToolDescriptor(
        stratagem_id="000010577006",
        name="Swooping Mockery",
        timing="opponent_movement_phase_after_enemy_unit_ends_normal_advance_or_fall_back_move",
        target="drukhari_transport_within_9_of_enemy_that_ended_move",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        effect_params={
            "distance": 6,
            "trigger_enemy_actions": ["normal_move", "advance", "fall_back"],
            "range_inches": 9,
        },
    ),
    "000010577002": StratagemToolDescriptor(
        stratagem_id="000010577002",
        name="Vicious Blades",
        timing="fight_phase_after_friendly_transport_selects_targets",
        target="drukhari_transport_selected_to_fight",
        duration="after_transport_fights",
        effect="post_fight_embarked_model_mortal_wounds",
        cp_cost=1,
        effect_params={
            "roll_per_embarked_model": True,
            "success_threshold": 5,
            "wracks_roll_bonus": 1,
            "max_mortal_wounds": 6,
        },
    ),
    "000010577004": StratagemToolDescriptor(
        stratagem_id="000010577004",
        name="Pounce on the Prey",
        timing="movement_phase_after_infantry_disembarks_from_transport_that_made_normal_move",
        target="drukhari_infantry_unit_that_disembarked_from_friendly_transport_that_made_normal_move",
        duration="until_end_of_turn",
        effect="disembarked_unit_can_declare_charge",
        cp_cost=1,
        effect_params={
            "remove_disembarked_charge_restriction": True,
        },
    ),
    "000010577005": StratagemToolDescriptor(
        stratagem_id="000010577005",
        name="Skyborne Annihilation",
        timing="shooting_phase",
        target="drukhari_unit_that_disembarked_from_transport_this_turn_not_selected_to_shoot",
        duration="until_end_of_phase",
        effect="grant_ranged_sustained_hits",
        cp_cost=1,
        effect_params={
            "sustained_hits_value": 1,
            "optional_target_keywords_any": ["KABALITE WARRIORS", "HAND OF THE ARCHON"],
            "optional_sustained_hits_value": 2,
        },
    ),
    "000010577003": StratagemToolDescriptor(
        stratagem_id="000010577003",
        name="Wraithlike Retreat",
        timing="end_of_fight_phase",
        target="drukhari_infantry_unit_that_fought_this_phase",
        duration="immediate",
        effect="reactive_normal_or_fall_back_move_with_transport_embark_requirement_for_non_wyches",
        cp_cost=1,
        effect_params={
            "normal_move_distance_when_not_engaged": 6,
            "fallback_when_engaged": True,
            "non_wyches_require_embark_after_move": True,
            "embark_requirement_horizontal": 3.0,
            "embark_requirement_vertical": 5.0,
        },
    ),
}

_SKYSPLINTER_ASSAULT_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SKYSPLINTER_ASSAULT_STRATAGEM_DESCRIPTORS.values()
}

_EXPERIMENTAL_PROTOTYPE_CADRE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009984002": StratagemToolDescriptor(
        stratagem_id="000009984002",
        name="Automated Repair Drones",
        timing="command_phase",
        target="tau_empire_battlesuit_unit_with_wounded_battlesuit_model",
        duration="immediate",
        effect="heal_battlesuit_model",
        cp_cost=1,
        effect_params={
            "model_keyword": "BATTLESUIT",
            "heal_roll": "D3+1",
        },
    ),
    "000009984003": StratagemToolDescriptor(
        stratagem_id="000009984003",
        name="Reactive Impact Dampeners",
        timing="shooting_or_fight_phase_after_enemy_targets_selected",
        target="tau_empire_battlesuit_unit_targeted",
        duration="until_end_of_phase",
        effect="defensive_wound_penalty_if_strength_gt_toughness",
        cp_cost=1,
        effect_params={
            "wound_roll_modifier": -1,
            "condition": "attacker_strength_greater_than_target_toughness",
        },
    ),
    "000009984007": StratagemToolDescriptor(
        stratagem_id="000009984007",
        name="Neuroweb System Jammer",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="tau_empire_crisis_unit_selected_as_target",
        duration="until_end_of_phase",
        effect="ranged_targeting_distance_cap",
        cp_cost=1,
        effect_params={
            "max_targeting_distance": 18,
            "attack_type": "ranged",
        },
    ),
    "000009984004": StratagemToolDescriptor(
        stratagem_id="000009984004",
        name="Experimental Weaponry",
        timing="shooting_phase_on_select_to_shoot",
        target="tau_empire_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="reroll_attack_count_rolls",
        cp_cost=1,
        effect_params={"attack_type": "ranged"},
    ),
    "000009984005": StratagemToolDescriptor(
        stratagem_id="000009984005",
        name="Experimental Ammunition",
        timing="shooting_phase_on_select_to_shoot",
        target="tau_empire_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_strength_or_strength_ap_hazardous_bonus",
        cp_cost=1,
        effect_params={
            "choices": {
                "strength": {"strength_bonus": 1, "ap_bonus": 0, "grant_hazardous": False},
                "hazardous": {"strength_bonus": 1, "ap_bonus": 1, "grant_hazardous": True},
            },
            "restriction": "cannot_target_same_unit_as_threat_assessment_analyser_same_phase",
        },
    ),
    "000009984006": StratagemToolDescriptor(
        stratagem_id="000009984006",
        name="Threat Assessment Analyser",
        timing="shooting_phase_on_select_to_shoot",
        target="tau_empire_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_keyword_choice_with_optional_hazardous",
        cp_cost=1,
        effect_params={
            "choices": {
                "sustained": {"grant_sustained_hits": 1, "grant_lethal_hits": False, "grant_hazardous": False},
                "lethal": {"grant_sustained_hits": 0, "grant_lethal_hits": True, "grant_hazardous": False},
                "all": {"grant_sustained_hits": 1, "grant_lethal_hits": True, "grant_hazardous": True},
            },
            "restriction": "cannot_target_same_unit_as_experimental_ammunition_same_phase",
        },
    ),
}

_EXPERIMENTAL_PROTOTYPE_CADRE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _EXPERIMENTAL_PROTOTYPE_CADRE_STRATAGEM_DESCRIPTORS.values()
}

_MONTKA_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008812004": StratagemToolDescriptor(
        stratagem_id="000008812004",
        name="Focused Fire",
        timing="start_of_your_shooting_phase",
        target="two_tau_empire_units_not_yet_selected_to_shoot_and_one_enemy_unit",
        duration="until_end_of_phase",
        effect="target_lock_and_ranged_ap_bonus",
        cp_cost=1,
        effect_params={
            "friendly_unit_count": 2,
            "enemy_target_count": 1,
            "ap_bonus": 1,
            "restriction": "cannot_use_in_battle_rounds_4_to_5",
        },
    ),
    "000008812005": StratagemToolDescriptor(
        stratagem_id="000008812005",
        name="Combat Debarkation",
        timing="your_shooting_phase_after_select_to_shoot",
        target="tau_empire_infantry_unit_disembarked_from_friendly_transport_this_turn",
        duration="until_end_of_phase",
        effect="closest_eligible_enemy_wound_reroll",
        cp_cost=1,
        effect_params={
            "attack_type": "any",
            "reroll_wound_full": True,
            "closest_target_only": True,
        },
    ),
    "000008812006": StratagemToolDescriptor(
        stratagem_id="000008812006",
        name="Pulse Onslaught",
        timing="your_shooting_phase_after_friendly_unit_shoots",
        target="non_kroot_tau_empire_infantry_unit_that_just_shot_and_hit_enemy_non_monster_non_vehicle_unit",
        duration="until_end_of_opponents_next_turn",
        effect="apply_shaken_mobility_debuff",
        cp_cost=1,
        effect_params={
            "move_penalty": -2,
            "advance_penalty": -2,
            "charge_penalty": -2,
        },
    ),
    "000008812003": StratagemToolDescriptor(
        stratagem_id="000008812003",
        name="Aggressive Mobility",
        timing="movement_phase_before_select_to_move",
        target="tau_empire_unit_not_yet_moved",
        duration="until_end_of_phase",
        effect="advance_no_roll_plus_6",
        cp_cost=1,
        effect_params={"advance_distance": 6},
    ),
    "000008812007": StratagemToolDescriptor(
        stratagem_id="000008812007",
        name="Counterfire Defence Systems",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="tau_empire_unit_targeted_by_enemy_shooter",
        duration="until_end_of_phase",
        effect="defensive_damage_reduction",
        cp_cost=2,
        effect_params={"damage_reduction": 1},
    ),
    "000008812002": StratagemToolDescriptor(
        stratagem_id="000008812002",
        name="Pinpoint Counter-Offensive",
        timing="any_phase_after_friendly_non_kroot_tau_unit_destroyed",
        target="destroyed_non_kroot_tau_empire_unit",
        duration="until_end_of_battle",
        effect="tau_non_kroot_hit_reroll_vs_destroying_enemy",
        cp_cost=1,
        effect_params={
            "trigger_enemy_is_marked_target": True,
            "attacker_required_keywords_any": ["T'AU EMPIRE"],
            "attacker_excluded_keywords_any": ["KROOT"],
            "reroll_hit_full": True,
        },
    ),
}

_MONTKA_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _MONTKA_STRATAGEM_DESCRIPTORS.values()
}

_AUXILIARY_CADRE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009840004": StratagemToolDescriptor(
        stratagem_id="000009840004",
        name="Interlocking Manoeuvres",
        timing="end_of_fight_phase",
        target="tau_empire_unit_eligible_to_fight_this_phase",
        duration="immediate",
        effect="reactive_normal_or_fall_back_move_with_disembark_embark_restriction",
        cp_cost=1,
        effect_params={
            "normal_move_distance_when_not_engaged": 6,
            "fallback_when_engaged": True,
            "disembarked_this_turn_cannot_embark_after_move": True,
        },
    ),
}

_AUXILIARY_CADRE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AUXILIARY_CADRE_STRATAGEM_DESCRIPTORS.values()
}

_KAUYON_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008443003": StratagemToolDescriptor(
        stratagem_id="000008443003",
        name="Point-Blank Ambush",
        timing="shooting_phase_on_select_to_shoot_after_battle_round_2",
        target="tau_empire_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="conditional_ranged_ap_bonus_within_range",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "attack_type": "ranged",
            "ap_bonus": 1,
            "max_range": 9.0,
            "min_battle_round": 3,
        },
    ),
    "000008443007": StratagemToolDescriptor(
        stratagem_id="000008443007",
        name="Wall of Mirrors",
        timing="end_of_opponent_fight_phase",
        target="tau_stealth_or_ghostkeel_or_commander_shadowsun_unit_not_engaged",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
    ),
}

_KAUYON_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _KAUYON_STRATAGEM_DESCRIPTORS.values()
}

_INVASION_FLEET_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008349002": StratagemToolDescriptor(
        stratagem_id="000008349002",
        name="Rapid Regeneration",
        timing="opponent_shooting_or_either_fight_phase_after_enemy_targets_selected",
        target="tyranids_unit_selected_as_target",
        duration="until_end_of_phase",
        effect="conditional_feel_no_pain_by_synapse",
        cp_cost=1,
        effect_params={
            "base_fnp": 6,
            "boosted_fnp": 5,
            "boost_condition": "within_synapse_range",
        },
    ),
    "000008349003": StratagemToolDescriptor(
        stratagem_id="000008349003",
        name="Adrenal Surge",
        timing="fight_phase",
        target="one_tyranids_unit_eligible_to_fight_or_up_to_two_within_synapse",
        duration="until_end_of_phase",
        effect="melee_critical_hits_on_5plus",
        cp_cost=2,
        effect_params={
            "critical_hit_threshold": 5,
            "max_units": 2,
            "two_units_requires_synapse": True,
        },
    ),
    "000008349004": StratagemToolDescriptor(
        stratagem_id="000008349004",
        name="Death Frenzy",
        timing="fight_phase_after_enemy_targets_selected",
        target="tyranids_unit_selected_as_target",
        duration="until_end_of_phase",
        effect="fight_on_death_after_attacks",
        cp_cost=1,
        effect_params={
            "roll_required": True,
            "roll_threshold": 4,
            "attack_type": "melee",
        },
    ),
    "000008349005": StratagemToolDescriptor(
        stratagem_id="000008349005",
        name="Overrun",
        timing="fight_phase_before_consolidate",
        target="tyranids_unit_before_consolidating",
        duration="until_end_of_phase",
        effect="consolidate_plus_3_with_synapse_normal_move_option",
        cp_cost=1,
        effect_params={
            "consolidate_distance": 6,
            "requires_engagement_for_consolidate": True,
            "synapse_normal_move_distance": 6,
            "normal_move_instead_when_not_in_engagement": True,
        },
    ),
    "000008349006": StratagemToolDescriptor(
        stratagem_id="000008349006",
        name="Predatory Imperative",
        timing="command_phase",
        target="one_tyranids_unit_or_up_to_two_within_synapse",
        duration="until_start_of_next_command_phase",
        effect="grant_additional_hyper_adaptation",
        cp_cost=1,
        effect_params={
            "max_units": 2,
            "two_units_requires_synapse": True,
            "cannot_select_first_round_hyper_adaptation": True,
        },
    ),
    "000008349007": StratagemToolDescriptor(
        stratagem_id="000008349007",
        name="Endless Swarm",
        timing="command_phase",
        target="one_endless_multitude_unit_or_up_to_two_within_synapse",
        duration="immediate",
        effect="return_destroyed_models",
        cp_cost=1,
        effect_params={
            "return_roll": "D3+3",
            "max_units": 2,
            "two_units_requires_synapse": True,
            "required_keyword": "ENDLESS MULTITUDE",
        },
    ),
}

_INVASION_FLEET_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _INVASION_FLEET_STRATAGEM_DESCRIPTORS.values()
}

_ASSIMILATION_SWARM_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008413005": StratagemToolDescriptor(
        stratagem_id="000008413005",
        name="Ablative Carapace",
        timing="opponent_shooting_or_either_fight_phase_after_enemy_targets_selected",
        target="harvester_unit_selected_as_target",
        duration="until_end_of_phase",
        effect="conditional_feel_no_pain_by_controlled_objective",
        cp_cost=2,
        effect_params={
            "base_fnp": 5,
            "boosted_fnp": 4,
            "boost_condition": "within_controlled_objective_range",
            "required_keyword": "HARVESTER",
        },
    ),
    "000008413002": StratagemToolDescriptor(
        stratagem_id="000008413002",
        name="Broodguard Impulse",
        timing="any_phase_when_friendly_harvester_just_destroyed",
        target="just_destroyed_harvester_unit",
        duration="until_end_of_battle",
        effect="mark_destroyer_for_tyranids_wound_bonus",
        cp_cost=1,
        effect_params={
            "wound_bonus": 1,
            "required_friendly_keyword": "HARVESTER",
        },
    ),
    "000008413007": StratagemToolDescriptor(
        stratagem_id="000008413007",
        name="Rapacious Hunger",
        timing="your_fight_phase_when_friendly_tyranids_unit_just_destroyed_enemy",
        target="friendly_tyranids_unit_that_just_destroyed_enemy",
        duration="immediate",
        effect="immediate_regenerate_with_harvester_flat_three_heal",
        cp_cost=1,
        effect_params={
            "heal_override_if_harvester": 3,
        },
    ),
    "000008413003": StratagemToolDescriptor(
        stratagem_id="000008413003",
        name="Reclaim Biomass",
        timing="any_phase_before_last_model_removed_when_friendly_tyranids_unit_just_destroyed",
        target="friendly_harvester_within_6_of_destroyed_friendly_tyranids_unit",
        duration="immediate",
        effect="harvester_regenerates_nearby_tyranids_unit",
        cp_cost=1,
        range_in=6.0,
        effect_params={
            "range": 6.0,
            "required_keyword": "HARVESTER",
            "exclude_destroyed_unit": True,
        },
    ),
    "000008413006": StratagemToolDescriptor(
        stratagem_id="000008413006",
        name="Secure Biomass",
        timing="either_fight_phase",
        target="tyranids_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="melee_lethal_hits_with_harvester_critical_hits_on_5plus",
        cp_cost=1,
        effect_params={
            "lethal_hits": True,
            "harvester_critical_hit_threshold": 5,
        },
    ),
    "000008413004": StratagemToolDescriptor(
        stratagem_id="000008413004",
        name="Tyrannoformed",
        timing="command_phase",
        target="harvester_unit_within_controlled_objective_range",
        duration="until_opponent_controls_start_or_end_of_turn",
        effect="sticky_objective",
        cp_cost=1,
        effect_params={
            "required_keyword": "HARVESTER",
        },
    ),
}

_ASSIMILATION_SWARM_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ASSIMILATION_SWARM_STRATAGEM_DESCRIPTORS.values()
}

_VANGUARD_ONSLAUGHT_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008418007": StratagemToolDescriptor(
        stratagem_id="000008418007",
        name="Invisible Hunter",
        timing="end_of_opponent_fight_phase",
        target="up_to_two_vanguard_invader_units_or_one_tyranids_infantry_unit",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "max_units": 2,
            "two_units_require_keyword": "VANGUARD INVADER",
            "single_unit_alternative_keywords": ["TYRANIDS", "INFANTRY"],
        },
    ),
}

_VANGUARD_ONSLAUGHT_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _VANGUARD_ONSLAUGHT_STRATAGEM_DESCRIPTORS.values()
}

_SYNAPTIC_NEXUS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008556007": StratagemToolDescriptor(
        stratagem_id="000008556007",
        name="Override Instincts",
        timing="movement_phase_after_fall_back",
        target="tyranids_unit_within_synapse_that_fell_back",
        duration="until_end_of_turn",
        effect="eligible_to_shoot_and_charge_after_fall_back",
        cp_cost=1,
        effect_params={
            "requires_synapse_range": True,
            "requires_fell_back_this_phase": True,
        },
    ),
}

_SYNAPTIC_NEXUS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SYNAPTIC_NEXUS_STRATAGEM_DESCRIPTORS.values()
}

_CRUSHER_STAMPEDE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008422002": StratagemToolDescriptor(
        stratagem_id="000008422002",
        name="Corrosive Viscera",
        timing="opponent_shooting_or_fight_phase_on_destroyed_model_before_removal",
        target="destroyed_non_fly_tyranids_monster_model_with_deadly_demise",
        duration="immediate",
        effect="auto_trigger_deadly_demise",
        cp_cost=1,
        effect_params={
            "requires_deadly_demise": True,
            "forbid_keywords": ["FLY"],
            "target_kind": "model",
        },
    ),
    "000008422003": StratagemToolDescriptor(
        stratagem_id="000008422003",
        name="Rampaging Monstrosities",
        timing="fight_phase_on_select",
        target="tyranids_monster_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="reroll_hit_rolls",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "reroll_mode": "full",
        },
    ),
    "000008422004": StratagemToolDescriptor(
        stratagem_id="000008422004",
        name="Savage Roar",
        timing="fight_phase_after_enemy_targets_selected",
        target="tyranids_monster_unit_selected_as_enemy_target",
        duration="until_end_of_phase",
        effect="force_battleshock_and_apply_attacker_filtered_melee_penalties",
        cp_cost=1,
        effect_params={
            "battle_shock_test": True,
            "attack_type": "melee",
            "hit_penalty": 1,
            "wound_penalty_on_failed_battleshock": 1,
        },
    ),
    "000008422005": StratagemToolDescriptor(
        stratagem_id="000008422005",
        name="Untrammelled Ferocity",
        timing="movement_phase_on_select_to_move",
        target="tyranids_monster_unit_not_yet_moved",
        duration="until_end_of_phase",
        effect="move_through_models_terrain_with_titanic_block_and_tall_terrain_battleshock_risk",
        cp_cost=1,
        effect_params={
            "move_types": ["move", "advance", "fall_back"],
            "move_through_models": True,
            "block_enemy_keywords": ["TITANIC"],
            "move_through_terrain": True,
            "allow_move_within_engagement_range": True,
            "cannot_end_in_engagement_range": True,
            "tall_terrain_battleshock_roll": "D6",
            "tall_terrain_battleshock_on": 1,
            "tall_terrain_threshold": 4.0,
        },
    ),
    "000008422006": StratagemToolDescriptor(
        stratagem_id="000008422006",
        name="Swarm-guided Salvoes",
        timing="shooting_phase_on_select_to_shoot",
        target="tyranids_monster_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="grant_ranged_ignores_cover_and_ignore_ballistic_skill_and_hit_modifiers",
        cp_cost=1,
        effect_params={
            "grant_ranged_keywords": ["IGNORES COVER"],
            "ignore_skill_modifier_kinds": ["ballistic", "weapon"],
            "allow_hit": True,
        },
    ),
    "000008422007": StratagemToolDescriptor(
        stratagem_id="000008422007",
        name="Massive Impact",
        timing="charge_phase_after_charge_move",
        target="tyranids_monster_model_that_ended_charge_move",
        duration="immediate",
        effect="charge_end_mortal_wounds",
        cp_cost=1,
        effect_params={
            "target_kind": "model",
            "enemy_target": "enemy_unit_within_engagement_range",
            "roll_count": 6,
            "success_on": 4,
            "mortal_wounds_per_success": 1,
        },
    ),
}

_CRUSHER_STAMPEDE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CRUSHER_STAMPEDE_STRATAGEM_DESCRIPTORS.values()
}

_SAGA_OF_THE_BEASTSLAYER_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010270002": StratagemToolDescriptor(
        stratagem_id="000010270002",
        name="Unbridled Ferocity",
        timing="fight_phase_on_select",
        target="space_wolves_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="grant_plus_one_to_wound_on_melee_weapons",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["SPACE WOLVES"],
            "attack_type": "melee",
            "wound_bonus": 1,
        },
    ),
    "000010270003": StratagemToolDescriptor(
        stratagem_id="000010270003",
        name="Shock Cavalry",
        timing="movement_or_charge_phase_on_select",
        target="thunderwolf_cavalry_unit_not_selected_to_move_or_charge_this_phase",
        duration="until_end_of_phase",
        effect="move_through_models_with_titanic_block_and_low_terrain",
        cp_cost=1,
        effect_params={
            "phase_move_types": {
                "movement": ["move", "advance", "fall_back"],
                "charge": ["charge"],
            },
            "move_through_models": True,
            "block_enemy_keywords": ["TITANIC"],
            "low_terrain_threshold": 4.0,
            "movement_phase_allow_move_within_engagement_range": True,
            "movement_phase_cannot_end_in_engagement_range": True,
        },
    ),
    "000010270004": StratagemToolDescriptor(
        stratagem_id="000010270004",
        name="Pinning Fire",
        timing="shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase_source_then_until_start_of_owners_next_shooting_phase_target",
        effect="post_shoot_select_hit_character_monster_vehicle_to_pin",
        cp_cost=1,
        effect_params={
            "target_enemy_keywords_any": ["CHARACTER", "MONSTER", "VEHICLE"],
            "pinned_move_penalty": -2,
            "pinned_charge_penalty": -2,
            "pinned_expires_phase": "SHOOTING_PHASE",
        },
    ),
    "000010270005": StratagemToolDescriptor(
        stratagem_id="000010270005",
        name="Thunderous Pursuit",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="adeptus_astartes_unit_within_9_of_enemy_not_engaged",
        duration="immediate",
        effect="reactive_normal_move_with_space_wolves_or_thunderwolf_fixed_six",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "trigger_actions": ["normal_move", "advance", "fall_back"],
            "distance_roll": "D6",
            "space_wolves_infantry_fixed_distance": 6,
            "thunderwolf_cavalry_fixed_distance": 6,
        },
    ),
    "000010270006": StratagemToolDescriptor(
        stratagem_id="000010270006",
        name="Impetuosity",
        timing="opponent_shooting_phase_after_targets_selected_then_after_enemy_shoots",
        target="wulfen_infantry_or_blood_claws_unit_targeted_by_enemy",
        duration="until_trigger_resolution_or_end_of_phase",
        effect="post_shoot_if_models_destroyed_make_impetuous_move_toward_closest_enemy",
        cp_cost=1,
        effect_params={
            "distance_roll": "D6",
            "required_keywords_any": ["SPACE WOLVES"],
            "eligible_unit_keywords_any": ["WULFEN INFANTRY", "BLOOD CLAWS"],
            "allow_engagement_range": True,
            "closest_enemy_exclude_keywords": ["AIRCRAFT"],
        },
    ),
    "000010270007": StratagemToolDescriptor(
        stratagem_id="000010270007",
        name="Coordinated Strike",
        timing="end_of_opponent_fight_phase",
        target="space_wolves_unit_wholly_within_9_of_battlefield_edge_not_engaged",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["SPACE WOLVES"],
            "battlefield_edge_distance": 9.0,
        },
    ),
}

_SAGA_OF_THE_BEASTSLAYER_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SAGA_OF_THE_BEASTSLAYER_STRATAGEM_DESCRIPTORS.values()
}

_SAGA_OF_THE_BOLD_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010266002": StratagemToolDescriptor(
        stratagem_id="000010266002",
        name="Inspiring Presence",
        timing="fight_phase_on_select_to_fight",
        target="adeptus_astartes_character_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="grant_keywords_to_melee_weapons",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "grant_keywords": ["LETHAL HITS"],
            "required_keywords_all": ["ADEPTUS ASTARTES", "CHARACTER"],
        },
    ),
    "000010266003": StratagemToolDescriptor(
        stratagem_id="000010266003",
        name="Champion's Guidance",
        timing="shooting_or_fight_phase_on_select",
        target="space_wolves_character_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="phase_hit_reroll",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["SPACE WOLVES"],
            "required_keywords_all": ["CHARACTER"],
            "reroll_hit_full": True,
        },
    ),
    "000010266004": StratagemToolDescriptor(
        stratagem_id="000010266004",
        name="Birth of a Saga",
        timing="your_command_phase",
        target="wolf_guard_headtaker_or_wolf_guard_terminator_pack_leader_model",
        duration="until_start_of_your_next_command_phase",
        effect="temporary_model_character_keyword_and_unit_character_status",
        cp_cost=1,
        effect_params={
            "selected_model_keyword": "CHARACTER",
            "selected_unit_counts_as_keyword": "CHARACTER",
        },
    ),
    "000010266005": StratagemToolDescriptor(
        stratagem_id="000010266005",
        name="Alpha Strike",
        timing="your_charge_phase",
        target="adeptus_astartes_character_unit",
        duration="until_end_of_phase",
        effect="charge_after_advance",
        cp_cost=1,
        effect_params={"required_keywords_all": ["ADEPTUS ASTARTES", "CHARACTER"]},
    ),
    "000010266006": StratagemToolDescriptor(
        stratagem_id="000010266006",
        name="Heroic Resolve",
        timing="opponent_shooting_phase_after_targets_selected",
        target="space_wolves_character_unit_targeted_by_enemy_shooter",
        duration="until_end_of_phase",
        effect="defensive_damage_reduction",
        cp_cost=2,
        effect_params={
            "required_keywords_any": ["SPACE WOLVES"],
            "required_keywords_all": ["CHARACTER"],
            "damage_reduction": 1,
        },
    ),
    "000010266007": StratagemToolDescriptor(
        stratagem_id="000010266007",
        name="Countercharge",
        timing="end_of_opponent_charge_phase",
        target="adeptus_astartes_character_unit_within_6_of_enemy_unit_it_can_charge",
        duration="immediate",
        effect="out_of_turn_charge_without_charge_bonus",
        cp_cost=2,
        range_in=6.0,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "CHARACTER"],
            "count_as_charged": False,
        },
    ),
}

_SAGA_OF_THE_BOLD_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SAGA_OF_THE_BOLD_STRATAGEM_DESCRIPTORS.values()
}

_SAGA_OF_THE_HUNTER_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010262002": StratagemToolDescriptor(
        stratagem_id="000010262002",
        name="Hunters' Trail",
        timing="fight_phase_on_select_to_fight",
        target="space_wolves_non_monster_non_vehicle_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="extend_pile_in_and_consolidate_to_six_and_ignore_closest_model_requirement",
        cp_cost=1,
        effect_params={
            "pile_in_distance": 6,
            "consolidate_distance": 6,
            "required_keywords_any": ["SPACE WOLVES"],
            "excluded_keywords_any": ["MONSTER", "VEHICLE"],
        },
    ),
    "000010262003": StratagemToolDescriptor(
        stratagem_id="000010262003",
        name="Territorial Advantage",
        timing="fight_phase_after_destroying_enemy_unit",
        target="adeptus_astartes_unit_within_range_of_controlled_objective",
        duration="until_opponent_controls_objective",
        effect="sticky_objective",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "requires_destroy_enemy_unit": True,
            "requires_controlled_objective_in_range": True,
        },
    ),
    "000010262004": StratagemToolDescriptor(
        stratagem_id="000010262004",
        name="Overwhelming Onslaught",
        timing="fight_phase_after_enemy_targets_selected",
        target="two_adeptus_astartes_units_or_one_space_wolves_beasts_unit_within_engagement_range_of_enemy",
        duration="until_end_of_phase",
        effect="attacking_enemy_hit_penalty",
        cp_cost=1,
        effect_params={
            "hit_roll_modifier": -1,
            "multi_target_mode": "two_adeptus_astartes_or_one_space_wolves_beasts",
        },
    ),
    "000010262005": StratagemToolDescriptor(
        stratagem_id="000010262005",
        name="Chosen Prey",
        timing="your_movement_phase_after_fall_back",
        target="that_space_wolves_unit",
        duration="until_end_of_turn",
        effect="shoot_and_charge_after_fall_back",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["SPACE WOLVES"],
            "shoot_after_fall_back": True,
            "charge_after_fall_back": True,
        },
    ),
    "000010262006": StratagemToolDescriptor(
        stratagem_id="000010262006",
        name="Bounding Advance",
        timing="movement_or_charge_phase_on_select",
        target="space_wolves_infantry_or_beasts_unit_not_yet_selected_to_move_or_charge",
        duration="until_end_of_phase",
        effect="move_through_models_with_titanic_block_and_movement_phase_engagement_pass",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["SPACE WOLVES"],
            "required_keywords_one_of": [["INFANTRY"], ["BEASTS"]],
            "phase_move_types": {
                "movement": ["move", "advance", "fall_back"],
                "charge": ["charge"],
            },
            "move_through_models": True,
            "block_enemy_keywords": ["TITANIC"],
            "movement_phase_allow_move_within_engagement_range": True,
            "movement_phase_cannot_end_in_engagement_range": True,
        },
    ),
    "000010262007": StratagemToolDescriptor(
        stratagem_id="000010262007",
        name="Marked for Destruction",
        timing="shooting_phase_on_select_to_shoot",
        target="two_adeptus_astartes_non_beasts_units_and_one_visible_shared_enemy_unit",
        duration="until_end_of_phase",
        effect="shared_target_lock_and_reroll_wound_ones",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "excluded_keywords_any": ["BEASTS"],
            "required_unit_count": 2,
            "reroll_wound_values": [1],
            "target_lock": True,
        },
    ),
}

_SAGA_OF_THE_HUNTER_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SAGA_OF_THE_HUNTER_STRATAGEM_DESCRIPTORS.values()
}

_SAGA_OF_THE_GREAT_WOLF_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010661003": StratagemToolDescriptor(
        stratagem_id="000010661003",
        name="Grimnar's Command",
        timing="your_command_phase",
        target="adeptus_astartes_unit",
        duration="until_start_of_your_next_command_phase",
        effect="unit_specific_master_of_wolves_hunting_pack_override",
        cp_cost=1,
        effect_params={
            "choices": ["ENCIRCLING_JAWS", "HUNTERS_EYE", "FEROCIOUS_STRIKE"],
            "override_even_if_selected_this_battle": True,
        },
    ),
    "000010661004": StratagemToolDescriptor(
        stratagem_id="000010661004",
        name="Fenrisian Ferocity",
        timing="movement_or_charge_phase_on_select",
        target="adeptus_astartes_mounted_or_walker_unit_not_yet_selected_to_move_or_charge",
        duration="until_end_of_phase",
        effect="move_through_models_and_terrain_with_titanic_block",
        cp_cost=1,
        effect_params={
            "phase_move_types": {
                "movement": ["move", "advance", "fall_back"],
                "charge": ["charge"],
            },
            "move_through_models": True,
            "move_through_terrain": True,
            "block_enemy_keywords": ["TITANIC"],
            "movement_phase_allow_move_within_engagement_range": True,
            "movement_phase_cannot_end_in_engagement_range": True,
        },
    ),
    "000010661005": StratagemToolDescriptor(
        stratagem_id="000010661005",
        name="Unrelenting Hunters",
        timing="movement_phase_on_select_to_move",
        target="adeptus_astartes_unit_not_yet_selected_to_move",
        duration="until_end_of_turn",
        effect="charge_after_fall_back_and_space_wolves_charge_after_advance",
        cp_cost=1,
        effect_params={
            "fall_back_and_charge": True,
            "space_wolves_only_advance_and_charge": True,
        },
    ),
    "000010661006": StratagemToolDescriptor(
        stratagem_id="000010661006",
        name="Eye of the Pack",
        timing="shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="grant_plus_one_to_wound_on_ranged_weapons",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "wound_bonus": 1,
        },
    ),
    "000010661007": StratagemToolDescriptor(
        stratagem_id="000010661007",
        name="Battle Instincts",
        timing="opponent_shooting_phase_after_enemy_unit_shoots",
        target="space_wolves_unit_targeted_by_enemy_shooter",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        effect_params={
            "movement_type": "normal",
            "reactive_move_distance": "D6",
            "required_keywords_any": ["SPACE WOLVES"],
        },
    ),
}

_SAGA_OF_THE_GREAT_WOLF_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SAGA_OF_THE_GREAT_WOLF_STRATAGEM_DESCRIPTORS.values()
}

_FIRST_COMPANY_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008495005": StratagemToolDescriptor(
        stratagem_id="000008495005",
        name="Duty and Honour",
        timing="your_movement_phase",
        target="first_company_veteran_unit_within_range_of_controlled_objective",
        duration="until_opponent_controls_start_or_end_of_turn",
        effect="sticky_objective",
        cp_cost=1,
        effect_params={
            "required_keywords_any": [
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ]
        },
    ),
    "000008495003": StratagemToolDescriptor(
        stratagem_id="000008495003",
        name="Heroes of the Chapter",
        timing="shooting_or_fight_phase_on_select",
        target="first_company_veteran_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="hit_bonus_and_conditional_wound_bonus",
        cp_cost=1,
        effect_params={
            "hit_bonus": 1,
            "wound_bonus": 1,
            "wound_bonus_condition": "below_half_strength",
            "required_keywords_any": [
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ],
        },
    ),
    "000008495007": StratagemToolDescriptor(
        stratagem_id="000008495007",
        name="Legendary Fortitude",
        timing="opponent_charge_phase_after_enemy_charge_move_end",
        target="first_company_veteran_unit_within_engagement_range_of_charging_enemy",
        duration="until_end_of_turn",
        effect="defensive_damage_reduction",
        cp_cost=1,
        effect_params={
            "damage_reduction": 1,
            "attack_type": "melee",
            "required_keywords_any": [
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ],
        },
    ),
    "000008495006": StratagemToolDescriptor(
        stratagem_id="000008495006",
        name="Orbital Teleportarium",
        timing="end_of_opponent_fight_phase",
        target="adeptus_astartes_terminator_unit_not_engaged",
        duration="until_next_reinforcements_step",
        effect="enter_strategic_reserves_with_temp_deep_strike",
        cp_cost=1,
        effect_params={
            "grant_deep_strike": True,
            "required_keywords_any": ["TERMINATOR"],
            "must_arrive_next_movement_phase": True,
        },
    ),
    "000008495004": StratagemToolDescriptor(
        stratagem_id="000008495004",
        name="Terrifying Proficiency",
        timing="your_fight_phase_after_charged_unit_destroys_enemy",
        target="first_company_veteran_unit_that_charged_and_destroyed_enemy",
        duration="until_opponents_next_command_phase",
        effect="delayed_enemy_battleshock_tests_with_conditional_modifier",
        cp_cost=1,
        range_in=6.0,
        effect_params={
            "required_keywords_any": [
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ],
            "requires_charge_this_turn": True,
            "requires_destroy_enemy_this_phase": True,
            "battleshock_range": 6.0,
            "below_half_modifier": -1,
            "suppress_other_battleshock_tests_same_phase": True,
        },
    ),
}

_FIRST_COMPANY_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _FIRST_COMPANY_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_EMPERORS_SHIELD_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010461006": StratagemToolDescriptor(
        stratagem_id="000010461006",
        name="Disciplined Extermination",
        timing="your_shooting_phase",
        target="first_company_veteran_unit_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase",
        effect="ranged_ignores_cover_and_ap_bonus",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "weapon_keywords": ["IGNORES COVER"],
            "ap_bonus": 1,
            "required_keywords_any": [
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ],
        },
    ),
    "000010461007": StratagemToolDescriptor(
        stratagem_id="000010461007",
        name="Dropship Extraction",
        timing="end_of_opponent_fight_phase",
        target="adeptus_astartes_terminator_unit_not_engaged",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["TERMINATOR"],
            "requires_not_engaged": True,
        },
    ),
    "000010461003": StratagemToolDescriptor(
        stratagem_id="000010461003",
        name="Fury of the First",
        timing="shooting_or_fight_phase_on_select",
        target="first_company_veteran_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="hit_bonus_and_conditional_wound_bonus",
        cp_cost=1,
        effect_params={
            "hit_bonus": 1,
            "wound_bonus": 1,
            "wound_bonus_condition": "below_half_strength",
            "required_keywords_any": [
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ],
        },
    ),
    "000010461004": StratagemToolDescriptor(
        stratagem_id="000010461004",
        name="Obdurate Vengeance",
        timing="fight_phase_after_enemy_targets_selected",
        target="first_company_veteran_unit_targeted_by_enemy_melee_attacks",
        duration="until_end_of_fight_phase",
        effect="fight_on_death_after_attacks",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "threshold": 3,
            "required_keywords_any": [
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ],
        },
    ),
    "000010461005": StratagemToolDescriptor(
        stratagem_id="000010461005",
        name="Wrathful Conquerors",
        timing="your_movement_phase",
        target="first_company_veteran_unit_within_range_of_controlled_objective",
        duration="until_opponent_controls_start_or_end_of_turn",
        effect="sticky_objective",
        cp_cost=1,
        effect_params={
            "required_keywords_any": [
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ]
        },
    ),
}

_EMPERORS_SHIELD_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _EMPERORS_SHIELD_STRATAGEM_DESCRIPTORS.values()
}

_HAMMER_OF_AVERNII_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010624004": StratagemToolDescriptor(
        stratagem_id="000010624004",
        name="Dominator Beacon",
        timing="your_movement_phase",
        target="hammer_of_avernii_elite_unit_within_range_of_controlled_objective",
        duration="until_opponent_controls_end_of_phase",
        effect="sticky_objective",
        cp_cost=1,
        effect_params={
            "required_keywords_any": [
                "DREADNOUGHT",
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ]
        },
    ),
    "000010624003": StratagemToolDescriptor(
        stratagem_id="000010624003",
        name="Ruthless Butchery",
        timing="shooting_or_fight_phase_on_select",
        target="hammer_of_avernii_elite_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="hit_bonus_and_conditional_wound_bonus",
        cp_cost=1,
        effect_params={
            "hit_bonus": 1,
            "wound_bonus": 1,
            "wound_bonus_condition": "below_starting_strength",
            "required_keywords_any": [
                "DREADNOUGHT",
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ],
        },
    ),
    "000010624006": StratagemToolDescriptor(
        stratagem_id="000010624006",
        name="Augmetic Fortitude",
        timing="opponent_charge_phase_after_enemy_charge_move_end",
        target="first_company_veteran_unit_within_engagement_range_of_charging_enemy",
        duration="until_end_of_turn",
        effect="defensive_damage_reduction",
        cp_cost=1,
        effect_params={
            "damage_reduction": 1,
            "attack_type": "melee",
            "required_keywords_any": [
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ],
        },
    ),
    "000010624005": StratagemToolDescriptor(
        stratagem_id="000010624005",
        name="Cogitated Ferocity",
        timing="fight_phase_before_selected",
        target="hammer_of_avernii_elite_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="choose_lethal_hits_or_sustained_hits_1_for_weapons",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "choices": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
            "required_keywords_any": [
                "DREADNOUGHT",
                "TERMINATOR",
                "BLADEGUARD VETERAN SQUAD",
                "STERNGUARD VETERAN SQUAD",
                "VANGUARD VETERAN SQUAD",
            ],
        },
    ),
    "000010624007": StratagemToolDescriptor(
        stratagem_id="000010624007",
        name="Dropship Extraction",
        timing="end_of_opponent_fight_phase",
        target="adeptus_astartes_terminator_unit_not_engaged",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["TERMINATOR"],
            "requires_not_engaged": True,
        },
    ),
}

_HAMMER_OF_AVERNII_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _HAMMER_OF_AVERNII_STRATAGEM_DESCRIPTORS.values()
}

_IRONSTORM_SPEARHEAD_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008479006": StratagemToolDescriptor(
        stratagem_id="000008479006",
        name="Ancient Fury",
        timing="your_command_phase",
        target="adeptus_astartes_walker_model",
        duration="until_start_of_your_next_command_phase",
        effect="walker_characteristics_and_hit_bonus_until_next_command_phase",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "WALKER"],
            "movement_bonus": 1,
            "toughness_bonus": 1,
            "leadership_bonus": -1,
            "objective_control_bonus": 1,
            "hit_bonus": 1,
        },
    ),
    "000008479004": StratagemToolDescriptor(
        stratagem_id="000008479004",
        name="Mercy Is Weakness",
        timing="shooting_or_fight_phase_on_select",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="conditional_sustained_hits_and_vehicle_critical_hits_vs_damaged_target",
        cp_cost=2,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "target_condition": "below_starting_strength",
            "sustained_hits": 1,
            "vehicle_critical_hit_threshold": 5,
        },
    ),
    "000008479007": StratagemToolDescriptor(
        stratagem_id="000008479007",
        name="Power of the Machine Spirit",
        timing="opponent_shooting_phase_after_shooting",
        target="adeptus_astartes_vehicle_unit_reduced_to_below_half_strength_by_attacker",
        duration="immediate",
        effect="reactive_shooting_restricted_to_attacker",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "VEHICLE"],
            "requires_target_became_below_half_strength": True,
        },
    ),
    "000008479002": StratagemToolDescriptor(
        stratagem_id="000008479002",
        name="Unbowed Conviction",
        timing="command_phase",
        target="adeptus_astartes_unit_below_starting_strength",
        duration="until_end_of_turn",
        effect="ignore_characteristic_and_roll_modifiers_except_saves",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "requires_below_starting_strength": True,
            "excludes_saving_throws": True,
        },
    ),
    "000008479005": StratagemToolDescriptor(
        stratagem_id="000008479005",
        name="Vengeful Animus",
        timing="any_phase_on_destroyed",
        target="destroyed_adeptus_astartes_vehicle_model_with_deadly_demise",
        duration="immediate",
        effect="auto_trigger_deadly_demise",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "VEHICLE"],
            "requires_deadly_demise": True,
        },
    ),
}

_IRONSTORM_SPEARHEAD_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _IRONSTORM_SPEARHEAD_STRATAGEM_DESCRIPTORS.values()
}

_INNER_CIRCLE_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008775004": StratagemToolDescriptor(
        stratagem_id="000008775004",
        name="Duty Unto Death",
        timing="fight_phase_after_enemy_targets_selected",
        target="deathwing_unit_targeted_by_enemy_attacks",
        duration="until_end_of_phase",
        effect="melee_fight_on_death_after_attacks_with_vowed_objective_bonus",
        cp_cost=1,
        effect_params={
            "base_threshold": 4,
            "threshold_if_within_vowed_objective": 3,
            "required_keywords_any": ["DEATHWING"],
        },
    ),
    "000008775003": StratagemToolDescriptor(
        stratagem_id="000008775003",
        name="Martial Mastery",
        timing="fight_phase_before_selected",
        target="deathwing_infantry_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="melee_wound_reroll_ones_or_full_if_within_vowed_objective",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "base_reroll_mode": "ones",
            "within_vowed_objective_reroll_mode": "full",
            "required_keywords_all": ["DEATHWING", "INFANTRY"],
        },
    ),
    "000008775005": StratagemToolDescriptor(
        stratagem_id="000008775005",
        name="Relic Teleportarium",
        timing="your_movement_phase",
        target="deathwing_unit_arriving_using_deep_strike",
        duration="until_end_of_turn",
        effect="deep_strike_min_distance_override_with_no_charge",
        cp_cost=1,
        effect_params={
            "min_distance": 6,
            "cannot_charge_this_turn": True,
            "required_keywords_any": ["DEATHWING"],
            "requires_deep_strike": True,
            "requires_reserves": True,
        },
    ),
    "000008775007": StratagemToolDescriptor(
        stratagem_id="000008775007",
        name="Unmatched Fortitude",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="deathwing_infantry_unit_targeted_by_enemy_attacks",
        duration="until_end_of_phase",
        effect="defensive_wound_penalty_vs_higher_strength_ranged",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "wound_penalty": 1,
            "requires_strength_gt_toughness": True,
            "required_keywords_all": ["DEATHWING", "INFANTRY"],
        },
    ),
    "000008775006": StratagemToolDescriptor(
        stratagem_id="000008775006",
        name="Wrath of the Lion",
        timing="charge_phase_after_charge_move_end",
        target="deathwing_infantry_unit_just_completed_charge",
        duration="immediate",
        effect="charge_end_capped_mortal_wound_burst",
        cp_cost=1,
        effect_params={
            "enemy_selection": "one_enemy_within_engagement_range",
            "dice_per_model_mode": "all_models_in_unit",
            "success_on": 4,
            "roll_bonus_if_enemy_within_vowed_objective": 1,
            "mortal_wounds_per_success": 1,
            "max_mortal_wounds": 3,
            "required_keywords_all": ["DEATHWING", "INFANTRY"],
        },
    ),
}

_INNER_CIRCLE_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _INNER_CIRCLE_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_LIBRARIUS_CONCLAVE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009791006": StratagemToolDescriptor(
        stratagem_id="000009791006",
        name="Assail",
        timing="your_shooting_phase",
        target="adeptus_astartes_psyker_unit_eligible_to_shoot_with_visible_enemy_within_18",
        duration="immediate",
        effect="psyker_mortal_wound_burst_with_conditional_telekinesis_bonus",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "PSYKER"],
            "range": 18,
            "requires_visibility": True,
            "enemy_excludes_lone_operative": True,
            "dice_count": 6,
            "success_on": 4,
            "roll_bonus_if_discipline_active": {"TELEKINESIS": 1},
            "mortal_wounds_per_success": 1,
        },
    ),
    "000009791004": StratagemToolDescriptor(
        stratagem_id="000009791004",
        name="Fiery Shield",
        timing="fight_phase_after_enemy_targets_selected",
        target="adeptus_astartes_infantry_or_mounted_unit_targeted_and_within_18_of_friendly_psyker",
        duration="until_end_of_phase",
        effect="defensive_hit_penalty_and_conditional_melee_hazardous_on_targeting",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "required_keywords_any": ["INFANTRY", "MOUNTED"],
            "range_to_friendly_psyker": 18,
            "hit_penalty": 1,
            "grant_hazardous_if_discipline_active": {"PYROMANCY": True},
        },
    ),
    "000009791005": StratagemToolDescriptor(
        stratagem_id="000009791005",
        name="Iron Arm",
        timing="fight_phase_before_selected",
        target="adeptus_astartes_infantry_unit_within_18_of_friendly_psyker_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="melee_strength_bonus_and_conditional_biomancy_bonus",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "INFANTRY"],
            "range_to_friendly_psyker": 18,
            "base_strength_bonus": 1,
            "discipline_strength_bonus": {"BIOMANCY": 2},
            "attack_type": "melee",
        },
    ),
    "000009791007": StratagemToolDescriptor(
        stratagem_id="000009791007",
        name="Prescient Precision",
        timing="your_shooting_phase",
        target="adeptus_astartes_psyker_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="ranged_lethal_hits_and_conditional_divination_ignores_cover",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "PSYKER"],
            "attack_type": "ranged",
            "base_keywords": ["LETHAL HITS"],
            "discipline_bonus_keywords": {"DIVINATION": ["IGNORES COVER"]},
        },
    ),
    "000009791002": StratagemToolDescriptor(
        stratagem_id="000009791002",
        name="Sensory Assault",
        timing="either_command_phase",
        target="adeptus_astartes_psyker_unit_with_visible_enemy_within_18",
        duration="until_start_of_your_next_turn",
        effect="pin_enemy_unit_and_conditional_telepathy_battleshock",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "PSYKER"],
            "range": 18,
            "requires_visibility": True,
            "move_penalty": -2,
            "charge_penalty": -2,
            "force_battleshock_if_discipline_active": {"TELEPATHY": {"modifier": -1}},
        },
    ),
}

_LIBRARIUS_CONCLAVE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _LIBRARIUS_CONCLAVE_STRATAGEM_DESCRIPTORS.values()
}

_LIBERATOR_ASSAULT_GROUP_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008375006": StratagemToolDescriptor(
        stratagem_id="000008375006",
        name="Aggressive Onslaught",
        timing="your_movement_phase_after_advance",
        target="adeptus_astartes_unit_that_just_advanced",
        duration="until_end_of_turn",
        effect="choose_shoot_or_charge_after_advance_or_both_with_battleshock",
        cp_cost=1,
        effect_params={
            "choices": ["SHOOT", "CHARGE", "RED_THIRST"],
            "advance_and_shoot_if_choice": {"SHOOT": True, "RED_THIRST": True},
            "advance_and_charge_if_choice": {"CHARGE": True, "RED_THIRST": True},
            "battleshock_if_choice": "RED_THIRST",
            "required_keywords_all": ["ADEPTUS ASTARTES"],
        },
    ),
    "000008375005": StratagemToolDescriptor(
        stratagem_id="000008375005",
        name="Red Rampage",
        timing="fight_phase_before_selected",
        target="adeptus_astartes_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="choose_lance_or_lethal_hits_or_both_with_battleshock_for_melee_weapons",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "choices": ["LANCE", "LETHAL_HITS", "RED_THIRST"],
            "choice_keywords": {
                "LANCE": ["LANCE"],
                "LETHAL_HITS": ["LETHAL HITS"],
                "RED_THIRST": ["LANCE", "LETHAL HITS"],
            },
            "battleshock_if_choice": "RED_THIRST",
            "required_keywords_all": ["ADEPTUS ASTARTES"],
        },
    ),
    "000008375007": StratagemToolDescriptor(
        stratagem_id="000008375007",
        name="Relentless Assault",
        timing="your_movement_phase_after_fall_back",
        target="adeptus_astartes_unit_that_just_fell_back",
        duration="until_end_of_turn",
        effect="choose_shoot_or_charge_after_fall_back_or_both_with_battleshock",
        cp_cost=1,
        effect_params={
            "choices": ["SHOOT", "CHARGE", "RED_THIRST"],
            "fall_back_and_shoot_if_choice": {"SHOOT": True, "RED_THIRST": True},
            "fall_back_and_charge_if_choice": {"CHARGE": True, "RED_THIRST": True},
            "battleshock_if_choice": "RED_THIRST",
            "required_keywords_all": ["ADEPTUS ASTARTES"],
        },
    ),
    "000008375004": StratagemToolDescriptor(
        stratagem_id="000008375004",
        name="Savage Echoes",
        timing="opponent_charge_phase_after_enemy_charge_move_end",
        target="adeptus_astartes_unit_just_charged_by_enemy",
        duration="until_end_of_turn",
        effect="choose_strength_or_attacks_or_both_with_battleshock_for_melee_weapons",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "choices": ["STRENGTH", "ATTACKS", "RED_THIRST"],
            "choice_bonuses": {
                "STRENGTH": {"strength_bonus": 1, "attacks_bonus": 0},
                "ATTACKS": {"strength_bonus": 0, "attacks_bonus": 1},
                "RED_THIRST": {"strength_bonus": 1, "attacks_bonus": 1},
            },
            "battleshock_if_choice": "RED_THIRST",
            "required_keywords_all": ["ADEPTUS ASTARTES"],
        },
    ),
}

_LIBERATOR_ASSAULT_GROUP_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _LIBERATOR_ASSAULT_GROUP_STRATAGEM_DESCRIPTORS.values()
}

_ANVIL_SIEGE_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008475006": StratagemToolDescriptor(
        stratagem_id="000008475006",
        name="Battle Drill Recall",
        timing="your_shooting_phase",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase",
        effect="ranged_sustained_hits_and_conditional_crit_hit_threshold",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "weapon_keywords": ["SUSTAINED HITS 1"],
            "critical_hit_threshold_if_remained_stationary": 5,
        },
    ),
    "000008475007": StratagemToolDescriptor(
        stratagem_id="000008475007",
        name="Hail of Vengeance",
        timing="opponent_shooting_phase_after_enemy_shooting_resolved",
        target="adeptus_astartes_unit_that_lost_models_to_attacker",
        duration="immediate",
        effect="reactive_shooting_against_attacker_after_losing_models",
        cp_cost=2,
        effect_params={
            "force_target_attacker": True,
            "requires_lost_models": True,
        },
    ),
    "000008475005": StratagemToolDescriptor(
        stratagem_id="000008475005",
        name="No Threat Too Great",
        timing="your_shooting_phase",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase",
        effect="ranged_full_wound_rerolls_vs_monsters_vehicles",
        cp_cost=2,
        effect_params={
            "attack_type": "ranged",
            "reroll_wound_full": True,
            "target_keywords_any": ["MONSTER", "VEHICLE"],
        },
    ),
    "000008475004": StratagemToolDescriptor(
        stratagem_id="000008475004",
        name="Not One Backwards Step",
        timing="your_command_phase",
        target="adeptus_astartes_infantry_unit_within_objective_range",
        duration="until_end_of_turn",
        effect="objective_control_multiplier_and_remain_stationary_lock",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["INFANTRY"],
            "objective_control_multiplier": 2,
            "movement_lock_mode": "remain_stationary",
        },
    ),
    "000008475003": StratagemToolDescriptor(
        stratagem_id="000008475003",
        name="Rigid Discipline",
        timing="end_of_fight_phase",
        target="adeptus_astartes_unit_within_engagement_range",
        duration="immediate",
        effect="reactive_fall_back_move",
        cp_cost=1,
        effect_params={"max_distance": 6},
    ),
}

_ANVIL_SIEGE_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ANVIL_SIEGE_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_BASTION_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010677002": StratagemToolDescriptor(
        stratagem_id="000010677002",
        name="Codex Discipline",
        timing="shooting_or_fight_phase_on_select",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="hit_reroll_ones_and_conditional_wound_reroll_ones_vs_auspex_scanned",
        cp_cost=1,
        effect_params={
            "reroll_hit_values": [1],
            "reroll_wound_values": [1],
            "wound_bonus_requires_auspex_scanned": True,
        },
    ),
    "000010677003": StratagemToolDescriptor(
        stratagem_id="000010677003",
        name="Guided Disruption",
        timing="shooting_or_fight_phase_after_battleline_attacks_resolved",
        target="adeptus_astartes_battleline_unit_that_just_attacked",
        duration="until_start_of_your_next_turn",
        effect="auspex_scanned_target_becomes_pinned",
        cp_cost=1,
        effect_params={
            "move_penalty": -2,
            "charge_penalty": -2,
            "exclude_keywords_any": ["MONSTER", "VEHICLE"],
        },
    ),
    "000010677004": StratagemToolDescriptor(
        stratagem_id="000010677004",
        name="Light of Vengeance",
        timing="shooting_or_fight_phase_on_select",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="conditional_lethal_hits_or_sustained_hits_1",
        cp_cost=1,
        effect_params={
            "choices": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
            "target_condition": "auspex_scanned_or_battleline",
        },
    ),
    "000010677005": StratagemToolDescriptor(
        stratagem_id="000010677005",
        name="Shock Bombardment",
        timing="shooting_or_fight_phase_after_battleline_attacks_resolved",
        target="adeptus_astartes_battleline_unit_that_just_attacked",
        duration="until_start_of_your_next_turn",
        effect="auspex_scanned_target_becomes_suppressed",
        cp_cost=1,
        effect_params={
            "hit_modifier": -1,
            "attack_types": ["melee", "ranged"],
        },
    ),
    "000010677007": StratagemToolDescriptor(
        stratagem_id="000010677007",
        name="Heresy Undone",
        timing="shooting_or_charge_phase",
        target="adeptus_astartes_non_battleline_unit",
        duration="until_end_of_phase",
        effect="shoot_and_charge_after_advance_or_fall_back_with_auspex_target_lock",
        cp_cost=1,
        effect_params={
            "advance_and_shoot": True,
            "advance_and_charge": True,
            "fall_back_and_shoot": True,
            "fall_back_and_charge": True,
            "requires_auspex_target_if_used_after_advance_or_fall_back": True,
        },
    ),
}

_BASTION_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _BASTION_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_GLADIUS_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008352005": StratagemToolDescriptor(
        stratagem_id="000008352005",
        name="Adaptive Strategy",
        timing="your_command_phase",
        target="adeptus_astartes_unit",
        duration="until_start_of_your_next_command_phase",
        effect="unit_specific_combat_doctrine_override",
        cp_cost=1,
        effect_params={
            "choices": ["DEVASTATOR", "TACTICAL", "ASSAULT"],
            "override_even_if_already_selected_this_battle": True,
        },
    ),
    "000008352004": StratagemToolDescriptor(
        stratagem_id="000008352004",
        name="Honour the Chapter",
        timing="fight_phase",
        target="adeptus_astartes_unit",
        duration="until_end_of_phase",
        effect="melee_weapons_gain_lance_and_conditional_assault_ap_bonus",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "grant_keywords": ["LANCE"],
            "conditional_ap_bonus_if_doctrine": {"ASSAULT": 1},
        },
    ),
    "000008352003": StratagemToolDescriptor(
        stratagem_id="000008352003",
        name="Only in Death Does Duty End",
        timing="fight_phase_after_enemy_targets_selected",
        target="adeptus_astartes_unit_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="fight_on_death_after_attacks",
        cp_cost=2,
        effect_params={"attack_type": "melee", "fight_on_death_after_attacks": True, "automatic": True},
    ),
    "000008352007": StratagemToolDescriptor(
        stratagem_id="000008352007",
        name="Squad Tactics",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="adeptus_astartes_infantry_or_mounted_unit_not_engaged_within_9_of_enemy_that_ended_normal_advance_or_fall_back_move",
        duration="immediate",
        effect="reactive_normal_move_with_tactical_fixed_six",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "movement_type": "normal",
            "reactive_move_distance": "D6",
            "fixed_distance_if_doctrine": {"TACTICAL": 6},
            "trigger_actions": ["normal_move", "advance", "fall_back"],
        },
    ),
    "000008352006": StratagemToolDescriptor(
        stratagem_id="000008352006",
        name="Storm of Fire",
        timing="shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="ranged_weapons_gain_ignores_cover_and_conditional_devastator_ap_bonus",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "grant_keywords": ["IGNORES COVER"],
            "conditional_ap_bonus_if_doctrine": {"DEVASTATOR": 1},
        },
    ),
}

_GLADIUS_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GLADIUS_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_BLADE_OF_ULTRAMAR_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010634004": StratagemToolDescriptor(
        stratagem_id="000010634004",
        name="Courage and Honour!",
        timing="fight_phase",
        target="adeptus_astartes_unit",
        duration="until_end_of_phase",
        effect="melee_weapons_gain_lance_and_conditional_assault_ap_bonus",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "grant_keywords": ["LANCE"],
            "conditional_ap_bonus_if_doctrine": {"ASSAULT": 1},
        },
    ),
    "000010634006": StratagemToolDescriptor(
        stratagem_id="000010634006",
        name="Exemplary Vigilance",
        timing="shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="ranged_weapons_gain_ignores_cover_and_conditional_devastator_ap_bonus",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "grant_keywords": ["IGNORES COVER"],
            "conditional_ap_bonus_if_doctrine": {"DEVASTATOR": 1},
        },
    ),
    "000010634007": StratagemToolDescriptor(
        stratagem_id="000010634007",
        name="Practical Tactics",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="adeptus_astartes_infantry_or_mounted_unit_not_engaged_within_9_of_enemy_that_ended_normal_advance_or_fall_back_move",
        duration="immediate",
        effect="reactive_normal_move_with_tactical_fixed_six",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "movement_type": "normal",
            "reactive_move_distance": "D6",
            "fixed_distance_if_doctrine": {"TACTICAL": 6},
            "trigger_actions": ["normal_move", "advance", "fall_back"],
        },
    ),
    "000010634003": StratagemToolDescriptor(
        stratagem_id="000010634003",
        name="Tactical Foresight",
        timing="opponent_shooting_or_fight_phase_after_enemy_targets_selected",
        target="adeptus_astartes_unit_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="conditional_minus_one_to_wound_if_attack_strength_gte_toughness",
        cp_cost=1,
        effect_params={
            "attack_type": "any",
            "wound_roll_modifier": -1,
            "requires_attack_strength_gte_target_toughness": True,
        },
    ),
    "000010634005": StratagemToolDescriptor(
        stratagem_id="000010634005",
        name="Ultramarian Adaptivity",
        timing="your_command_phase",
        target="adeptus_astartes_unit",
        duration="until_start_of_your_next_command_phase",
        effect="unit_specific_combat_doctrine_override",
        cp_cost=1,
        effect_params={
            "choices": ["DEVASTATOR", "TACTICAL", "ASSAULT"],
            "override_even_if_already_selected_this_battle": True,
        },
    ),
}

_BLADE_OF_ULTRAMAR_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _BLADE_OF_ULTRAMAR_STRATAGEM_DESCRIPTORS.values()
}

_CHAMPIONS_OF_FENRIS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009852005": StratagemToolDescriptor(
        stratagem_id="000009852005",
        name="Chilling Howl",
        timing="opponent_command_phase",
        target="adeptus_astartes_terminator_unit",
        duration="immediate",
        effect="force_battleshock_test_with_below_half_modifier",
        cp_cost=1,
        range_in=6.0,
        effect_params={
            "required_keywords_all": ["TERMINATOR"],
            "test_radius_in": 6.0,
            "below_half_strength_modifier": -1,
        },
    ),
    "000009852007": StratagemToolDescriptor(
        stratagem_id="000009852007",
        name="Onrushing Storm",
        timing="end_of_opponent_fight_phase",
        target="adeptus_astartes_terminator_unit_not_engaged",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["TERMINATOR"],
            "requires_not_engaged": True,
        },
    ),
    "000009852002": StratagemToolDescriptor(
        stratagem_id="000009852002",
        name="Preytaker's Eye",
        timing="shooting_or_fight_phase_before_selected",
        target="adeptus_astartes_infantry_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="choose_lethal_hits_or_sustained_hits_1_for_weapons",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["INFANTRY"],
            "choices": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
        },
    ),
    "000009852004": StratagemToolDescriptor(
        stratagem_id="000009852004",
        name="Runes of Claiming",
        timing="end_of_your_command_phase",
        target="adeptus_astartes_infantry_or_walker_unit_within_range_of_objective_you_control",
        duration="until_opponent_controls_objective",
        effect="sticky_objective",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["INFANTRY", "WALKER"],
            "requires_controlled_objective": True,
        },
    ),
    "000009852006": StratagemToolDescriptor(
        stratagem_id="000009852006",
        name="Stalking Wolves",
        timing="opponent_shooting_phase_after_targets_selected",
        target="adeptus_astartes_infantry_unit_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="grant_stealth",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["INFANTRY"],
            "granted_keywords": ["STEALTH"],
        },
    ),
}

_CHAMPIONS_OF_FENRIS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CHAMPIONS_OF_FENRIS_STRATAGEM_DESCRIPTORS.values()
}

_COMPANIONS_OF_VEHEMENCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010393002": StratagemToolDescriptor(
        stratagem_id="000010393002",
        name="Devout Push",
        timing="fight_phase_before_selected_to_fight",
        target="adeptus_astartes_infantry_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="extend_pile_in_and_consolidate_to_six",
        cp_cost=1,
        effect_params={"required_keywords_all": ["INFANTRY"], "pile_in_distance_in": 6.0, "consolidate_distance_in": 6.0},
    ),
    "000010393007": StratagemToolDescriptor(
        stratagem_id="000010393007",
        name="Dread Crusaders",
        timing="opponent_charge_phase_after_charge_declared",
        target="adeptus_astartes_infantry_unit_selected_as_charge_target",
        duration="immediate",
        effect="force_battleshock_test_with_modifier",
        cp_cost=1,
        effect_params={"required_keywords_all": ["INFANTRY"], "battle_shock_test_modifier": -1},
    ),
    "000010393004": StratagemToolDescriptor(
        stratagem_id="000010393004",
        name="For the Emperor's Honour!",
        timing="fight_phase_before_selected_to_fight",
        target="adeptus_astartes_infantry_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="grant_precision_to_melee_weapons",
        cp_cost=1,
        effect_params={"required_keywords_all": ["INFANTRY"], "attack_type": "melee", "grant_keywords": ["PRECISION"]},
    ),
    "000010393003": StratagemToolDescriptor(
        stratagem_id="000010393003",
        name="Hearts Hardened to Duty",
        timing="fight_phase_before_consolidate",
        target="adeptus_astartes_infantry_unit_before_consolidating",
        duration="until_end_of_phase",
        effect="consolidate_ignore_closest_enemy_requirement",
        cp_cost=1,
        effect_params={"required_keywords_all": ["INFANTRY"]},
    ),
    "000010393006": StratagemToolDescriptor(
        stratagem_id="000010393006",
        name="Heresy Begets Retribution",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="chaplain_or_judiciar_unit_within_9_not_engaged",
        duration="immediate",
        effect="reactive_retribution_move_toward_closest_enemy",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "required_keywords_any": ["CHAPLAIN", "JUDICIAR"],
            "reactive_move_distance": "D6",
            "allow_engagement_range": True,
            "closest_enemy_unit_exclude_keywords": ["AIRCRAFT"],
            "trigger_actions": ["normal_move", "advance", "fall_back"],
        },
    ),
    "000010393005": StratagemToolDescriptor(
        stratagem_id="000010393005",
        name="Pious Enmity",
        timing="fight_phase_before_selected_to_fight",
        target="chaplain_or_judiciar_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="reroll_melee_hit_ones_and_conditional_wound_ones",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["CHAPLAIN", "JUDICIAR"],
            "attack_type": "melee",
            "reroll_hit_values": [1],
            "reroll_wound_values_vs_keywords": {"MONSTER": [1], "VEHICLE": [1]},
        },
    ),
}

_COMPANIONS_OF_VEHEMENCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _COMPANIONS_OF_VEHEMENCE_STRATAGEM_DESCRIPTORS.values()
}

_VANGUARD_SPEARHEAD_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008491002": StratagemToolDescriptor(
        stratagem_id="000008491002",
        name="A Deadly Prize",
        timing="start_of_command_phase",
        target="adeptus_astartes_infantry_or_mounted_unit_within_range_of_controlled_objective",
        duration="until_opponent_controls_at_start_or_end_of_turn",
        effect="sabotaged_sticky_objective_with_move_end_mortal_wounds",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["INFANTRY", "MOUNTED"],
            "sticky_control": True,
            "trigger_actions": ["normal_move", "advance", "fall_back", "charge"],
            "move_end_trigger_die": "D6",
            "move_end_trigger_threshold": 2,
            "move_end_mortal_wounds": "D3",
        },
    ),
    "000008491006": StratagemToolDescriptor(
        stratagem_id="000008491006",
        name="Calculated Feint",
        timing="opponent_charge_phase_after_charge_declared",
        target="adeptus_astartes_infantry_unit_selected_as_charge_target_not_in_engagement_range",
        duration="immediate",
        effect="reactive_normal_move_with_phobos_or_scout_fixed_six",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["INFANTRY"],
            "reactive_move_distance": "D6",
            "fixed_distance_if_keywords_any": ["PHOBOS", "SCOUT SQUAD"],
            "fixed_distance_in": 6.0,
            "requires_not_engaged": True,
        },
    ),
    "000008491007": StratagemToolDescriptor(
        stratagem_id="000008491007",
        name="Guerrilla Tactics",
        timing="end_of_opponent_fight_phase",
        target="up_to_two_phobos_or_scout_units_or_one_other_adeptus_astartes_infantry_unit_more_than_3_from_enemy",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "max_units": 2,
            "requires_keywords_any_for_multi_select": ["PHOBOS", "SCOUT SQUAD"],
            "required_keywords_any_for_single_non_special_unit": ["INFANTRY"],
            "min_enemy_distance_in": 3.0,
        },
    ),
    "000008491005": StratagemToolDescriptor(
        stratagem_id="000008491005",
        name="Strike from the Shadows",
        timing="your_shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_infantry_unit_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase",
        effect="ranged_ballistic_skill_and_ap_bonus_beyond_12_with_post_shoot_battleshock",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["INFANTRY"],
            "attack_type": "ranged",
            "ballistic_skill_bonus": 1,
            "ap_bonus": 1,
            "min_target_distance_in": 12.0,
            "distance_condition": "strictly_greater_than",
            "post_shoot_battleshock_on_destroyed_model_unit": True,
        },
    ),
    "000008491004": StratagemToolDescriptor(
        stratagem_id="000008491004",
        name="Surgical Strikes",
        timing="fight_phase_before_selected_to_fight",
        target="adeptus_astartes_infantry_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="grant_precision_to_melee_weapons",
        cp_cost=2,
        effect_params={"required_keywords_all": ["INFANTRY"], "attack_type": "melee", "grant_keywords": ["PRECISION"]},
    ),
}

_VANGUARD_SPEARHEAD_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _VANGUARD_SPEARHEAD_STRATAGEM_DESCRIPTORS.values()
}

_SHADOWMARK_TALON_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010467004": StratagemToolDescriptor(
        stratagem_id="000010467004",
        name="Feint and Thrust",
        timing="your_movement_phase",
        target="adeptus_astartes_unit",
        duration="until_end_of_turn",
        effect="shoot_and_charge_after_fall_back_and_conditional_advance",
        cp_cost=1,
        effect_params={
            "required_faction_keywords_all": ["ADEPTUS ASTARTES"],
            "shoot_after_fall_back": True,
            "charge_after_fall_back": True,
            "shoot_after_advance_if_keywords_any": ["PHOBOS", "SCOUT SQUAD"],
            "charge_after_advance_if_keywords_any": ["PHOBOS", "SCOUT SQUAD"],
        },
    ),
    "000010467007": StratagemToolDescriptor(
        stratagem_id="000010467007",
        name="Into Darkness",
        timing="end_of_opponent_fight_phase",
        target="up_to_two_phobos_or_scout_units_or_one_other_adeptus_astartes_infantry_unit_not_in_engagement_range",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "max_units": 2,
            "requires_keywords_any_for_multi_select": ["PHOBOS", "SCOUT SQUAD"],
            "required_keywords_any_for_single_non_special_unit": ["INFANTRY"],
            "requires_not_engaged": True,
        },
    ),
    "000010467003": StratagemToolDescriptor(
        stratagem_id="000010467003",
        name="Lay Low the Tyrants",
        timing="fight_phase_before_selected_to_fight",
        target="adeptus_astartes_infantry_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="grant_precision_to_melee_weapons",
        cp_cost=1,
        effect_params={"required_keywords_all": ["INFANTRY"], "attack_type": "melee", "grant_keywords": ["PRECISION"]},
    ),
    "000010467006": StratagemToolDescriptor(
        stratagem_id="000010467006",
        name="Raptorial Vigilance",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="adeptus_astartes_infantry_or_mounted_unit_within_9_not_engaged",
        duration="immediate",
        effect="reactive_normal_move_with_phobos_or_scout_fixed_six",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "required_keywords_any": ["INFANTRY", "MOUNTED"],
            "reactive_move_distance": "D6",
            "fixed_distance_if_keywords_any": ["PHOBOS", "SCOUT SQUAD"],
            "fixed_distance_in": 6.0,
            "requires_not_engaged": True,
            "trigger_actions": ["normal_move", "advance", "fall_back"],
        },
    ),
    "000010467005": StratagemToolDescriptor(
        stratagem_id="000010467005",
        name="Stunning Fusillade",
        timing="your_shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_infantry_unit_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase",
        effect="ranged_ballistic_skill_and_ap_bonus_beyond_12_with_post_shoot_battleshock",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["INFANTRY"],
            "attack_type": "ranged",
            "ballistic_skill_bonus": 1,
            "ap_bonus": 1,
            "min_target_distance_in": 12.0,
            "distance_condition": "strictly_greater_than",
            "post_shoot_battleshock_on_destroyed_model_unit": True,
        },
    ),
}

_SHADOWMARK_TALON_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SHADOWMARK_TALON_STRATAGEM_DESCRIPTORS.values()
}

_SPEARPOINT_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010630003": StratagemToolDescriptor(
        stratagem_id="000010630003",
        name="Spear Thrust and Sabre Swing",
        timing="fight_phase_before_selected_to_fight",
        target="adeptus_astartes_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="grant_lance_or_lethal_hits_to_melee_weapons",
        cp_cost=1,
        effect_params={
            "required_faction_keywords_all": ["ADEPTUS ASTARTES"],
            "attack_type": "melee",
            "choice_keywords": ["LANCE", "LETHAL HITS"],
            "grant_both_if_keywords_any": ["MOUNTED"],
        },
    ),
    "000010630004": StratagemToolDescriptor(
        stratagem_id="000010630004",
        name="Mobile Lethality",
        timing="your_movement_phase",
        target="adeptus_astartes_unit",
        duration="until_end_of_turn",
        effect="shoot_after_advance_and_fall_back",
        cp_cost=1,
        effect_params={
            "required_faction_keywords_all": ["ADEPTUS ASTARTES"],
            "shoot_after_advance": True,
            "shoot_after_fall_back": True,
        },
    ),
    "000010630006": StratagemToolDescriptor(
        stratagem_id="000010630006",
        name="Evasive Manoeuvres",
        timing="opponent_shooting_phase_after_targets_selected",
        target="adeptus_astartes_mounted_or_fly_vehicle_unit_targeted",
        duration="until_end_of_phase",
        effect="ranged_hit_and_wound_penalty",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["MOUNTED", "FLY VEHICLE"],
            "attack_type": "ranged",
            "hit_penalty": 1,
            "wound_penalty": 1,
        },
    ),
    "000010630007": StratagemToolDescriptor(
        stratagem_id="000010630007",
        name="Withdraw and Regroup",
        timing="end_of_opponent_fight_phase",
        target="adeptus_astartes_mounted_or_fly_vehicle_unit_not_in_engagement_range",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["MOUNTED", "FLY VEHICLE"],
            "requires_not_engaged": True,
        },
    ),
    "000010630005": StratagemToolDescriptor(
        stratagem_id="000010630005",
        name="Hunter's Instincts",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="adeptus_astartes_infantry_or_mounted_unit_within_9_not_engaged",
        duration="immediate",
        effect="reactive_normal_move_up_to_6",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "required_keywords_any": ["INFANTRY", "MOUNTED"],
            "reactive_move_distance_in": 6.0,
            "requires_not_engaged": True,
            "trigger_actions": ["normal_move", "advance", "fall_back"],
        },
    ),
}

_SPEARPOINT_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPEARPOINT_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_FIRESTORM_ASSAULT_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008483003": StratagemToolDescriptor(
        stratagem_id="000008483003",
        name="Crucible of Battle",
        timing="shooting_or_fight_phase_before_selected",
        target="adeptus_astartes_infantry_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="closest_eligible_target_wound_bonus",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "INFANTRY"],
            "wound_bonus": 1,
            "max_distance_in": 6.0,
        },
    ),
    "000008483004": StratagemToolDescriptor(
        stratagem_id="000008483004",
        name="Rapid Embarkation",
        timing="end_of_fight_phase",
        target="adeptus_astartes_transport_and_nearby_eligible_infantry_unit",
        duration="immediate",
        effect="end_of_fight_embark",
        cp_cost=1,
        effect_params={
            "transport_required_keywords_all": ["ADEPTUS ASTARTES", "TRANSPORT"],
            "passenger_required_keywords_all": ["ADEPTUS ASTARTES", "INFANTRY"],
            "range_in": 6.0,
            "requires_empty_transport": True,
            "passenger_requires_not_engaged": True,
            "passenger_requires_not_disembarked_this_turn": True,
        },
    ),
    "000008483005": StratagemToolDescriptor(
        stratagem_id="000008483005",
        name="Immolation Protocols",
        timing="your_shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase",
        effect="grant_devastating_wounds_to_torrent_ranged_weapons",
        cp_cost=2,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "attack_type": "ranged",
            "required_weapon_keywords_any": ["TORRENT"],
            "granted_weapon_keywords": ["DEVASTATING WOUNDS"],
        },
    ),
    "000008483006": StratagemToolDescriptor(
        stratagem_id="000008483006",
        name="Onslaught of Fire",
        timing="your_shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_unit_that_disembarked_this_turn_and_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase",
        effect="closest_eligible_target_ranged_hit_bonus_with_post_shoot_battleshock",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "attack_type": "ranged",
            "requires_disembarked_from_transport_this_turn": True,
            "hit_bonus": 1,
            "max_distance_in": 12.0,
            "post_shoot_battleshock_on_destroyed_model_unit": True,
        },
    ),
    "000008483007": StratagemToolDescriptor(
        stratagem_id="000008483007",
        name="Burning Vengeance",
        timing="opponent_shooting_phase_after_enemy_unit_resolves_attacks",
        target="adeptus_astartes_transport_targeted_by_attacking_enemy_unit",
        duration="immediate",
        effect="reactive_disembark_then_forced_shoot_attacker",
        cp_cost=1,
        effect_params={
            "transport_required_keywords_all": ["ADEPTUS ASTARTES", "TRANSPORT"],
            "max_disembarking_units": 1,
            "requires_transport_with_embarked_units": True,
            "forced_shooting_target": "attacking_unit",
        },
    ),
}

_FIRESTORM_ASSAULT_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _FIRESTORM_ASSAULT_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_FORGEFATHERS_SEEKERS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010369003": StratagemToolDescriptor(
        stratagem_id="000010369003",
        name="Crucible of Battle",
        timing="shooting_or_fight_phase_before_selected",
        target="adeptus_astartes_infantry_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="closest_eligible_target_wound_bonus",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "INFANTRY"],
            "wound_bonus": 1,
            "max_distance_in": 6.0,
        },
    ),
    "000010369004": StratagemToolDescriptor(
        stratagem_id="000010369004",
        name="Wrathful Inferno",
        timing="movement_phase_after_fall_back",
        target="adeptus_astartes_infantry_unit_that_fell_back",
        duration="until_end_of_turn",
        effect="shoot_after_fall_back",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "INFANTRY"],
        },
    ),
    "000010369005": StratagemToolDescriptor(
        stratagem_id="000010369005",
        name="Immolation Protocols",
        timing="your_shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase",
        effect="grant_devastating_wounds_to_torrent_ranged_weapons",
        cp_cost=2,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "attack_type": "ranged",
            "required_weapon_keywords_any": ["TORRENT"],
            "granted_weapon_keywords": ["DEVASTATING WOUNDS"],
        },
    ),
    "000010369006": StratagemToolDescriptor(
        stratagem_id="000010369006",
        name="Burning Vengeance",
        timing="opponent_shooting_phase_after_enemy_unit_resolves_attacks",
        target="adeptus_astartes_transport_targeted_by_attacking_enemy_unit",
        duration="immediate",
        effect="reactive_disembark_then_forced_shoot_attacker",
        cp_cost=1,
        effect_params={
            "transport_required_keywords_all": ["ADEPTUS ASTARTES", "TRANSPORT"],
            "max_disembarking_units": 1,
            "requires_transport_with_embarked_units": True,
            "forced_shooting_target": "attacking_unit",
        },
    ),
    "000010369007": StratagemToolDescriptor(
        stratagem_id="000010369007",
        name="Blazing Earth",
        timing="start_of_opponent_charge_phase",
        target="adeptus_astartes_unit_with_torrent_weapon_then_visible_non_monster_non_vehicle_non_fly_enemy_within_12",
        duration="until_end_of_phase",
        effect="enemy_charge_roll_modifier_non_cumulative_negative",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "required_weapon_keywords_any": ["TORRENT"],
            "charge_roll_modifier": -2,
            "range_inches": 12,
            "exclude_keywords_any": ["MONSTER", "VEHICLE", "FLY"],
        },
    ),
}

_FORGEFATHERS_SEEKERS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _FORGEFATHERS_SEEKERS_STRATAGEM_DESCRIPTORS.values()
}

_GODHAMMER_ASSAULT_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010401002": StratagemToolDescriptor(
        stratagem_id="000010401002",
        name="A Ceaseless Cause",
        timing="end_of_fight_phase",
        target="adeptus_astartes_infantry_unit_eligible_to_fight_this_phase_and_not_engaged",
        duration="immediate",
        effect="end_of_fight_normal_move_up_to_six_no_embark_if_disembarked",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "INFANTRY"],
            "requires_eligible_to_fight_this_phase": True,
            "requires_not_engaged": True,
            "movement_type": "normal",
            "max_distance_in": 6.0,
            "forbid_embark_if_disembarked_this_turn": True,
        },
    ),
    "000010401003": StratagemToolDescriptor(
        stratagem_id="000010401003",
        name="Uncompromising Egress",
        timing="your_movement_phase_before_selected_to_move",
        target="land_raider_with_embarked_adeptus_astartes_unit",
        duration="immediate",
        effect="reactive_disembark_within_six_and_allow_engagement",
        cp_cost=1,
        effect_params={
            "transport_required_keywords_all": ["ADEPTUS ASTARTES", "LAND RAIDER"],
            "passenger_required_keywords_all": ["ADEPTUS ASTARTES"],
            "max_disembarking_units": 1,
            "range_in": 6.0,
            "allow_end_in_engagement_range": True,
        },
    ),
    "000010401004": StratagemToolDescriptor(
        stratagem_id="000010401004",
        name="Gauntlet of the God-Emperor",
        timing="your_movement_phase_before_selected_to_move",
        target="adeptus_astartes_vehicle_unit_not_yet_selected_to_move",
        duration="until_end_of_movement_phase",
        effect="normal_and_advance_move_through_terrain",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "VEHICLE"],
            "movement_types": ["move", "advance"],
            "can_move_horizontally_through_terrain": True,
        },
    ),
    "000010401005": StratagemToolDescriptor(
        stratagem_id="000010401005",
        name="Focused Hatred",
        timing="your_charge_phase_after_charge_roll",
        target="adeptus_astartes_unit_that_disembarked_from_transport_this_turn",
        duration="until_end_of_charge_phase",
        effect="charge_move_through_models_against_declared_targets_only",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "requires_disembarked_from_transport_this_turn": True,
            "movement_type": "charge",
            "can_move_through_models": True,
            "end_in_engagement_only_of_declared_targets": True,
        },
    ),
    "000010401006": StratagemToolDescriptor(
        stratagem_id="000010401006",
        name="Condemnatory Info-screed",
        timing="your_fight_phase_on_select_to_fight",
        target="adeptus_astartes_unit_that_disembarked_from_transport_this_turn_and_not_yet_selected_to_fight",
        duration="until_end_of_fight_phase",
        effect="disembarked_wound_reroll_ones_or_full_if_land_raider",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "requires_disembarked_from_transport_this_turn": True,
            "attack_type": "melee",
            "reroll_wound_values": [1],
            "upgrade_to_full_if_transport_has_keywords_all": ["LAND RAIDER"],
        },
    ),
}

_GODHAMMER_ASSAULT_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GODHAMMER_ASSAULT_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_BLACK_SPEAR_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008523003": StratagemToolDescriptor(
        stratagem_id="000008523003",
        name="Adaptive Tactics",
        timing="your_command_phase",
        target="up_to_two_kill_team_units_or_one_other_adeptus_astartes_unit",
        duration="until_start_of_your_next_command_phase",
        effect="unit_specific_mission_tactic_override",
        cp_cost=1,
        effect_params={
            "max_units": 2,
            "requires_kill_team_for_multi_select": True,
            "choices": ["FUROR_TACTICS", "MALLEUS_TACTICS", "PURGATUS_TACTICS"],
        },
    ),
    "000008523006": StratagemToolDescriptor(
        stratagem_id="000008523006",
        name="Dragonfire Rounds",
        timing="shooting_phase_on_select_to_shoot",
        target="kill_team_unit_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase",
        effect="ranged_assault_and_ignores_cover",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "weapon_keywords": ["ASSAULT", "IGNORES COVER"],
        },
    ),
    "000008523004": StratagemToolDescriptor(
        stratagem_id="000008523004",
        name="Hellfire Rounds",
        timing="shooting_phase_on_select_to_shoot",
        target="kill_team_unit_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase",
        effect="ranged_anti_infantry_2_and_anti_monster_5_except_devastating_wounds",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "weapon_keywords": ["ANTI-INFANTRY 2+", "ANTI-MONSTER 5+"],
            "exclude_weapon_keywords_any": ["DEVASTATING WOUNDS"],
        },
    ),
    "000008523005": StratagemToolDescriptor(
        stratagem_id="000008523005",
        name="Kraken Rounds",
        timing="shooting_phase_on_select_to_shoot",
        target="kill_team_unit_not_yet_selected_to_shoot",
        duration="until_end_of_shooting_phase",
        effect="ranged_ap_and_range_bonus",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "ap_bonus": 1,
            "range_bonus_in": 6.0,
        },
    ),
    "000008523007": StratagemToolDescriptor(
        stratagem_id="000008523007",
        name="Site-to-Site Teleportation",
        timing="end_of_opponent_fight_phase",
        target="up_to_two_kill_team_units_or_one_other_adeptus_astartes_infantry_unit_not_engaged",
        duration="until_next_reinforcements_step",
        effect="enter_strategic_reserves_with_temp_deep_strike",
        cp_cost=1,
        effect_params={
            "max_units": 2,
            "requires_kill_team_for_multi_select": True,
            "required_keywords_any_for_single_non_kill_team": ["INFANTRY"],
            "grant_deep_strike": True,
            "must_arrive_next_movement_phase": True,
        },
    ),
}

_BLACK_SPEAR_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _BLACK_SPEAR_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_COMPANY_OF_HUNTERS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008779005": StratagemToolDescriptor(
        stratagem_id="000008779005",
        name="Death on the Wind",
        timing="your_shooting_phase_after_shooting",
        target="one_ravenwing_unit_that_just_shot_and_one_enemy_unit_hit_by_its_attacks",
        duration="immediate",
        effect="force_battleshock_test_with_conditional_ravenwing_modifier",
        cp_cost=1,
        effect_params={
            "requires_hit_enemy_target": True,
            "test_modifier_if_friendly_ravenwing_within_6": -1,
        },
    ),
    "000008779002": StratagemToolDescriptor(
        stratagem_id="000008779002",
        name="Hunters' Trail",
        timing="either_command_phase",
        target="one_ravenwing_mounted_unit_within_range_of_objective_you_control",
        duration="until_opponent_controls_objective",
        effect="sticky_objective",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["RAVENWING", "MOUNTED"],
            "requires_controlled_objective": True,
        },
    ),
    "000008779007": StratagemToolDescriptor(
        stratagem_id="000008779007",
        name="Rapid Reappraisal",
        timing="end_of_opponent_fight_phase",
        target="one_ravenwing_unit_not_engaged",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["RAVENWING"],
            "requires_not_engaged": True,
        },
    ),
    "000008779004": StratagemToolDescriptor(
        stratagem_id="000008779004",
        name="Talon Strike",
        timing="shooting_or_fight_phase_before_selected",
        target="one_ravenwing_mounted_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="conditional_wound_bonus_vs_character_infantry_or_mounted",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["RAVENWING", "MOUNTED"],
            "wound_bonus": 1,
            "target_required_keywords_all": ["CHARACTER"],
            "target_required_keywords_any": ["INFANTRY", "MOUNTED"],
        },
    ),
}

_COMPANY_OF_HUNTERS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _COMPANY_OF_HUNTERS_STRATAGEM_DESCRIPTORS.values()
}

_LIONS_BLADE_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009734006": StratagemToolDescriptor(
        stratagem_id="000009734006",
        name="Illuminating Fire",
        timing="your_shooting_phase_after_targets_selected",
        target="one_ravenwing_unit_that_selected_targets_and_one_enemy_targeted_within_12",
        duration="until_end_of_phase",
        effect="mark_enemy_for_deathwing_wound_bonus",
        cp_cost=1,
        range_in=12.0,
        effect_params={
            "required_keywords_all": ["RAVENWING"],
            "wound_bonus_keywords_all": ["DEATHWING"],
            "wound_bonus": 1,
            "requires_selected_enemy_target": True,
            "max_target_range": 12.0,
        },
    ),
    "000009734007": StratagemToolDescriptor(
        stratagem_id="000009734007",
        name="Inescapable Wrath",
        timing="end_of_opponent_charge_phase",
        target="one_deathwing_infantry_or_walker_unit_within_6_of_enemy_and_eligible_to_charge",
        duration="immediate",
        effect="out_of_turn_charge",
        cp_cost=2,
        range_in=6.0,
        effect_params={
            "required_keywords_all": ["DEATHWING"],
            "required_keywords_any": ["INFANTRY", "WALKER"],
            "max_enemy_distance": 6.0,
            "count_as_charged": True,
            "force_single_target": True,
        },
    ),
    "000009734005": StratagemToolDescriptor(
        stratagem_id="000009734005",
        name="Knights of Iron",
        timing="movement_or_charge_phase_on_select",
        target="one_ravenwing_unit_not_yet_selected_to_move_or_charge",
        duration="until_end_of_phase",
        effect="move_through_terrain",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["RAVENWING"],
            "move_types_by_phase": {
                "movement": ["move", "advance"],
                "charge": ["charge"],
            },
        },
    ),
    "000009734002": StratagemToolDescriptor(
        stratagem_id="000009734002",
        name="Overpowering Exaction",
        timing="command_phase_or_start_of_fight_phase",
        target="one_adeptus_astartes_unit_within_engagement_range_of_enemy",
        duration="immediate",
        effect="force_battleshock_test_with_conditional_deathwing_or_ravenwing_modifier",
        cp_cost=1,
        effect_params={
            "requires_enemy_within_engagement_range": True,
            "battle_shock_test_modifier_if_source_has_any_keyword": ["DEATHWING", "RAVENWING"],
            "battle_shock_test_modifier": -1,
        },
    ),
    "000009734004": StratagemToolDescriptor(
        stratagem_id="000009734004",
        name="Strength in Unity",
        timing="fight_phase_after_enemy_targets_selected",
        target="one_adeptus_astartes_unit_targeted_by_enemy_attacks",
        duration="until_end_of_phase",
        effect="enemy_melee_hit_and_conditional_wound_penalty",
        cp_cost=1,
        effect_params={
            "hit_penalty_if_enemy_engaging_friendly_keyword": "RAVENWING",
            "wound_penalty_if_enemy_engaging_friendly_keyword": "DEATHWING",
            "wound_penalty_requires_strength_gt_toughness": True,
        },
    ),
}

_LIONS_BLADE_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _LIONS_BLADE_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_ORBITAL_ASSAULT_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010681002": StratagemToolDescriptor(
        stratagem_id="000010681002",
        name="Suppression Strafing",
        timing="command_phase",
        target="one_adeptus_astartes_unit_and_one_visible_enemy_within_18",
        duration="until_start_of_your_next_turn",
        effect="visible_enemy_within_18_forced_battleshock_and_suppressed",
        cp_cost=1,
        range_in=18.0,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "requires_visible_enemy": True,
            "battle_shock_test_modifier": -1,
            "apply_suppressed_on_failed_test": True,
        },
    ),
    "000010681003": StratagemToolDescriptor(
        stratagem_id="000010681003",
        name="Tactical Decapitation",
        timing="shooting_or_fight_phase_before_selected",
        target="one_adeptus_astartes_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="grant_precision_and_character_target_hit_bonus",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "granted_keyword": "PRECISION",
            "hit_bonus_vs_target_keywords_all": ["CHARACTER"],
            "hit_bonus": 1,
        },
    ),
    "000010681004": StratagemToolDescriptor(
        stratagem_id="000010681004",
        name="Shock Onslaught",
        timing="fight_phase_before_selected",
        target="one_adeptus_astartes_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="increase_pile_in_and_consolidate_distance",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "pile_in_distance_in": 6.0,
            "consolidate_distance_in": 6.0,
        },
    ),
    "000010681005": StratagemToolDescriptor(
        stratagem_id="000010681005",
        name="Auto‑Sense Coordination",
        timing="shooting_or_fight_phase_before_selected",
        target="one_adeptus_astartes_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="choose_lethal_hits_or_sustained_hits_1_if_drop_pod_or_within_12",
        cp_cost=1,
        range_in=12.0,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "choice_keywords": ["LETHAL HITS", "SUSTAINED HITS 1"],
            "active_if_disembarked_from_transport_name": "Drop Pod",
            "active_if_target_within_in": 12.0,
        },
    ),
    "000010681006": StratagemToolDescriptor(
        stratagem_id="000010681006",
        name="Blind Screen",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="one_non_titanic_adeptus_astartes_targeted_unit_and_one_friendly_smoke_vehicle_or_drop_pod_within_9",
        duration="until_end_of_phase",
        effect="paired_units_gain_stealth_and_cover",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "target_excluded_keywords_any": ["TITANIC"],
            "paired_support_keywords_any": ["DROP POD", "SMOKE"],
            "grants_stealth": True,
            "grants_benefit_of_cover": True,
        },
    ),
    "000010681007": StratagemToolDescriptor(
        stratagem_id="000010681007",
        name="Onward For The Emperor",
        timing="end_of_opponent_fight_phase",
        target="one_adeptus_astartes_infantry_unit_not_set_up_this_turn_and_one_friendly_transport_within_6",
        duration="immediate",
        effect="end_of_opponent_fight_embark",
        cp_cost=1,
        range_in=6.0,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "INFANTRY"],
            "requires_not_set_up_this_turn": True,
            "requires_transport": True,
        },
    ),
}

_ORBITAL_ASSAULT_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ORBITAL_ASSAULT_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_RECLAMATION_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010685002": StratagemToolDescriptor(
        stratagem_id="000010685002",
        name="Crusading Conquerors",
        timing="end_of_command_phase",
        target="adeptus_astartes_unit",
        duration="until_start_of_next_command_phase",
        effect="objective_control_bonus_until_next_command_phase",
        cp_cost=1,
        effect_params={"objective_control_bonus": 1},
    ),
    "000010685003": StratagemToolDescriptor(
        stratagem_id="000010685003",
        name="Furious Dedication",
        timing="charge_or_fight_phase_on_select",
        target="adeptus_astartes_unit_not_yet_selected",
        duration="until_end_of_turn",
        effect="charge_roll_bonus_and_melee_attacks_bonus",
        cp_cost=1,
        effect_params={"charge_roll_bonus": 2, "melee_attacks_bonus": 1, "once_per_turn": True},
    ),
    "000010685004": StratagemToolDescriptor(
        stratagem_id="000010685004",
        name="Fight to the End",
        timing="fight_phase_after_enemy_targets_selected",
        target="adeptus_astartes_unit_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="fight_on_death_on_4_plus",
        cp_cost=1,
        effect_params={"fight_on_death_threshold": 4},
    ),
    "000010685005": StratagemToolDescriptor(
        stratagem_id="000010685005",
        name="Scions of Guilliman",
        timing="your_movement_phase_after_fall_back",
        target="that_adeptus_astartes_unit",
        duration="until_end_of_turn",
        effect="shoot_and_charge_after_fall_back",
        cp_cost=1,
        effect_params={"shoot_after_fall_back": True, "charge_after_fall_back": True},
    ),
    "000010685006": StratagemToolDescriptor(
        stratagem_id="000010685006",
        name="Ultramarian Destiny",
        timing="movement_phase_on_select",
        target="adeptus_astartes_unit_within_controlled_objective",
        duration="until_control_is_lost",
        effect="sticky_objective_control",
        cp_cost=1,
        effect_params={"requires_controlled_objective_in_range": True},
    ),
    "000010685007": StratagemToolDescriptor(
        stratagem_id="000010685007",
        name="Marching Ever On",
        timing="opponent_movement_phase_after_enemy_fall_back",
        target="adeptus_astartes_unit_engaged_with_enemy_at_phase_start",
        duration="immediate",
        effect="reactive_normal_move_after_enemy_fall_back",
        cp_cost=1,
        effect_params={"distance_roll": "D6+1"},
    ),
}

_RECLAMATION_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RECLAMATION_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_STORMLANCE_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008487003": StratagemToolDescriptor(
        stratagem_id="000008487003",
        name="Blitzing Fusillade",
        timing="your_shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="grant_assault_or_sustained_hits_1_to_ranged_weapons",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "attack_type": "ranged",
            "base_keyword": "ASSAULT",
            "bonus_keyword_if_already_present": "SUSTAINED HITS 1",
        },
    ),
    "000008487004": StratagemToolDescriptor(
        stratagem_id="000008487004",
        name="Full Throttle",
        timing="your_movement_phase",
        target="adeptus_astartes_mounted_or_non_walker_vehicle_unit_not_yet_selected_to_move",
        duration="until_end_of_phase",
        effect="fixed_advance_distance_by_keyword",
        cp_cost=2,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "required_keywords_any": ["MOUNTED", "VEHICLE"],
            "excluded_keywords_any": ["WALKER"],
            "mounted_advance_distance": 9,
            "other_advance_distance": 6,
        },
    ),
    "000008487005": StratagemToolDescriptor(
        stratagem_id="000008487005",
        name="Shock Assault",
        timing="your_charge_phase_on_select_to_charge",
        target="adeptus_astartes_mounted_unit_not_yet_selected_to_charge",
        duration="until_end_of_turn",
        effect="reroll_charge_rolls_and_gain_lance",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES", "MOUNTED"],
            "reroll_charge": True,
            "attack_type": "melee",
            "keywords": ["LANCE"],
        },
    ),
    "000008487006": StratagemToolDescriptor(
        stratagem_id="000008487006",
        name="Ride Hard, Ride Fast",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="adeptus_astartes_mounted_or_fly_vehicle_unit_targeted_by_enemy_attacks",
        duration="until_end_of_phase",
        effect="ranged_hit_and_wound_penalty",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "required_keywords_any": ["MOUNTED", "FLY VEHICLE"],
            "attack_type": "ranged",
            "hit_penalty": 1,
            "wound_penalty": 1,
        },
    ),
    "000008487007": StratagemToolDescriptor(
        stratagem_id="000008487007",
        name="Wind-Swift Evasion",
        timing="opponent_movement_phase_after_enemy_move_ends",
        target="adeptus_astartes_infantry_or_mounted_unit_within_9_of_enemy_and_not_in_engagement_range",
        duration="immediate",
        effect="reactive_normal_move_up_to_6",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "required_keywords_any": ["INFANTRY", "MOUNTED"],
            "requires_not_in_engagement_range": True,
            "max_distance": 6,
        },
    ),
}

_STORMLANCE_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _STORMLANCE_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_ANGELIC_INHERITORS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009836003": StratagemToolDescriptor(
        stratagem_id="000009836003",
        name="Focused Fury",
        timing="fight_phase_on_select_to_fight",
        target="adeptus_astartes_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="melee_lethal_hits_and_conditional_lance",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "base_keywords": ["LETHAL HITS"],
            "character_unit_bonus_keywords": ["LANCE"],
        },
    ),
    "000009836006": StratagemToolDescriptor(
        stratagem_id="000009836006",
        name="In the Shadow of Great Wings",
        timing="opponent_shooting_phase_after_targets_selected",
        target="adeptus_astartes_character_unit_targeted",
        duration="until_end_of_phase",
        effect="ranged_targeting_range_restriction",
        cp_cost=1,
        effect_params={"targeting_range": 18},
    ),
    "000009836004": StratagemToolDescriptor(
        stratagem_id="000009836004",
        name="Instant of Grace",
        timing="your_command_phase",
        target="adeptus_astartes_infantry_unit_with_non_character_model",
        duration="until_start_of_your_next_command_phase",
        effect="temporary_model_character_keyword_and_unit_character_status",
        cp_cost=1,
        effect_params={
            "selected_model_keyword": "CHARACTER",
            "selected_unit_counts_as_keyword": "CHARACTER",
        },
    ),
    "000009836005": StratagemToolDescriptor(
        stratagem_id="000009836005",
        name="Strike Now for Glory",
        timing="shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="ranged_sustained_hits",
        cp_cost=1,
        effect_params={"sustained_hits_value": 1},
    ),
    "000009836007": StratagemToolDescriptor(
        stratagem_id="000009836007",
        name="Unto the Burning Skies",
        timing="end_of_opponent_fight_phase",
        target="adeptus_astartes_jump_pack_unit_or_the_sanguinor_even_if_engaged",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["JUMP PACK"],
            "reserve_status": "strategic_reserves",
            "allow_engaged_if_unit_named": "The Sanguinor",
        },
    ),
}

_ANGELIC_INHERITORS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ANGELIC_INHERITORS_STRATAGEM_DESCRIPTORS.values()
}

_THE_ANGELIC_HOST_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009191004": StratagemToolDescriptor(
        stratagem_id="000009191004",
        name="Angel's Sacrifice",
        timing="fight_phase_start",
        target="adeptus_astartes_jump_pack_unit",
        duration="until_end_of_phase",
        effect="engaged_enemy_target_lock",
        cp_cost=1,
        effect_params={"required_keywords_any": ["JUMP PACK"]},
    ),
    "000009191007": StratagemToolDescriptor(
        stratagem_id="000009191007",
        name="Death from the Skies",
        timing="your_movement_phase_after_advance_or_fall_back",
        target="adeptus_astartes_jump_pack_unit_that_just_advanced_or_fell_back",
        duration="until_end_of_turn",
        effect="shoot_and_charge_after_advance_or_fall_back",
        cp_cost=1,
        effect_params={
            "advance_and_shoot": True,
            "advance_and_charge": True,
            "fall_back_and_shoot": True,
            "fall_back_and_charge": True,
            "required_keywords_any": ["JUMP PACK"],
        },
    ),
    "000009191006": StratagemToolDescriptor(
        stratagem_id="000009191006",
        name="Descent of Angels",
        timing="movement_phase_reinforcements_step",
        target="adeptus_astartes_jump_pack_unit_arriving_using_deep_strike",
        duration="this_phase",
        effect="deep_strike_min_distance_override",
        cp_cost=1,
        effect_params={
            "min_distance": 6,
            "distance_type": "horizontal",
            "required_keywords_any": ["JUMP PACK"],
            "requires_deep_strike": True,
            "requires_reserves": True,
        },
    ),
    "000009191005": StratagemToolDescriptor(
        stratagem_id="000009191005",
        name="Martial Exemplars",
        timing="fight_phase_on_select_to_fight",
        target="adeptus_astartes_jump_pack_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="grant_keywords_to_melee_weapons",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "grant_keywords": ["LETHAL HITS", "PRECISION"],
            "required_keywords_any": ["JUMP PACK"],
        },
    ),
    "000009191002": StratagemToolDescriptor(
        stratagem_id="000009191002",
        name="Unbridled Ardour",
        timing="any_phase_on_destroyed",
        target="destroyed_adeptus_astartes_unit",
        duration="until_end_of_battle",
        effect="battlelong_sanguinary_guard_hit_and_wound_rerolls_vs_marked_destroyer",
        cp_cost=1,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "attacker_unit_name_contains": "Sanguinary Guard",
            "reroll_hit_full": True,
            "reroll_wound_full": True,
        },
    ),
}

_THE_ANGELIC_HOST_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _THE_ANGELIC_HOST_STRATAGEM_DESCRIPTORS.values()
}

_THE_LOST_BRETHREN_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009187004": StratagemToolDescriptor(
        stratagem_id="000009187004",
        name="Final Retribution",
        timing="fight_phase_after_enemy_targets_selected",
        target="death_company_unit_selected_as_target",
        duration="until_end_of_phase",
        effect="fight_on_death_after_attacks",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "fight_on_death_after_attacks": True,
            "threshold": 4,
            "threshold_with_friendly_chaplain_within_12": 3,
            "required_keywords_any": ["DEATH COMPANY"],
        },
    ),
    "000009187005": StratagemToolDescriptor(
        stratagem_id="000009187005",
        name="Furious Onslaught",
        timing="fight_phase_before_pile_in",
        target="death_company_unit",
        duration="until_end_of_phase",
        effect="pile_in_distance_override",
        cp_cost=1,
        effect_params={
            "pile_in_distance_roll": "D3+3",
            "pile_in_distance_if_friendly_chaplain_within_12": 6,
            "pile_in_distance_if_below_starting_strength": 6,
            "required_keywords_any": ["DEATH COMPANY"],
        },
    ),
    "000009187002": StratagemToolDescriptor(
        stratagem_id="000009187002",
        name="Glorious Sacrifice",
        timing="any_phase_on_destroyed",
        target="destroyed_death_company_unit_on_controlled_objective",
        duration="until_opponent_controls_objective",
        effect="sticky_objective",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["DEATH COMPANY"],
            "requires_destroyed": True,
        },
    ),
    "000009187006": StratagemToolDescriptor(
        stratagem_id="000009187006",
        name="Lost to Rage",
        timing="fight_phase_on_select_to_fight",
        target="death_company_unit_below_starting_strength_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="melee_weapon_bonus_and_conditional_hazardous",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "attacks_bonus": 1,
            "strength_bonus": 1,
            "ap_bonus": 1,
            "grant_keywords_unless_friendly_chaplain_within_12": ["HAZARDOUS"],
            "required_keywords_any": ["DEATH COMPANY"],
        },
    ),
    "000009187007": StratagemToolDescriptor(
        stratagem_id="000009187007",
        name="Wrathful Rampage",
        timing="your_movement_phase_after_advance",
        target="death_company_unit_that_just_advanced",
        duration="until_end_of_turn",
        effect="charge_after_advance_and_conditional_shoot_after_advance",
        cp_cost=1,
        effect_params={
            "advance_and_charge": True,
            "advance_and_shoot_if_friendly_chaplain_within_12": True,
            "advance_and_shoot_if_below_starting_strength": True,
            "required_keywords_any": ["DEATH COMPANY"],
        },
    ),
}

_THE_LOST_BRETHREN_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _THE_LOST_BRETHREN_STRATAGEM_DESCRIPTORS.values()
}

_UNFORGIVEN_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008389005": StratagemToolDescriptor(
        stratagem_id="000008389005",
        name="Fire Discipline",
        timing="your_shooting_phase_on_select_to_shoot",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="grant_ranged_assault_heavy_ignores_cover",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "grant_keywords": ["ASSAULT", "HEAVY", "IGNORES COVER"],
        },
    ),
    "000008389006": StratagemToolDescriptor(
        stratagem_id="000008389006",
        name="Grim Retribution",
        timing="opponent_shooting_phase_after_enemy_shoots",
        target="adeptus_astartes_unit_that_lost_models_to_attacker",
        duration="immediate",
        effect="reactive_shooting_against_attacker_after_losing_models",
        cp_cost=1,
        effect_params={"target_restriction": "attacking_enemy_unit_only"},
    ),
    "000008389004": StratagemToolDescriptor(
        stratagem_id="000008389004",
        name="Intractable",
        timing="your_movement_phase_after_fall_back",
        target="adeptus_astartes_unit_that_fell_back",
        duration="until_end_of_turn",
        effect="eligible_to_shoot_and_charge_after_fall_back",
        cp_cost=1,
    ),
    "000008389007": StratagemToolDescriptor(
        stratagem_id="000008389007",
        name="Unbreakable Lines",
        timing="opponent_charge_phase_after_enemy_charge_move_end",
        target="adeptus_astartes_unit_within_engagement_range_of_charger",
        duration="until_end_of_turn",
        effect="defensive_wound_penalty",
        cp_cost=2,
        effect_params={
            "wound_roll_modifier": -1,
            "attack_type": "any",
        },
    ),
    "000008389003": StratagemToolDescriptor(
        stratagem_id="000008389003",
        name="Unforgiven Fury",
        timing="your_shooting_or_either_fight_phase_on_select",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="phase_lethal_hits_and_conditional_crit_hit_threshold",
        cp_cost=1,
        effect_params={
            "conditional_attack_type_by_phase": {
                "shooting": "ranged",
                "fight": "melee",
            },
            "grant_keywords": ["LETHAL HITS"],
            "critical_hit_threshold_if_any_friendly_adeptus_astartes_unit_is_battle_shocked": 5,
        },
    ),
}

_UNFORGIVEN_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _UNFORGIVEN_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_VINDICATION_TASK_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010397002": StratagemToolDescriptor(
        stratagem_id="000010397002",
        name="Refusal to Yield",
        timing="any_phase_on_friendly_ancient_model_destroyed",
        target="just_destroyed_adeptus_astartes_ancient_model_once_per_battle_per_model",
        duration="end_of_phase",
        effect="return_destroyed_model_full_wounds_as_close_as_possible_not_in_engagement",
        cp_cost=1,
        effect_params={
            "return_timing": "end_of_phase",
            "wounds_fraction": 1.0,
            "once_per_battle_per_model": True,
            "not_within_engagement_range": True,
        },
    ),
    "000010397003": StratagemToolDescriptor(
        stratagem_id="000010397003",
        name="Litanies of Purgation",
        timing="fight_phase_on_select_to_fight",
        target="adeptus_astartes_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="conditional_melee_ap_bonus_if_attacker_or_target_within_objective_range",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "ap_bonus": 1,
            "requires_attacker_or_target_within_objective_range": True,
        },
    ),
    "000010397004": StratagemToolDescriptor(
        stratagem_id="000010397004",
        name="Spoor of the Unholy",
        timing="shooting_or_fight_phase_on_select_to_shoot_or_fight",
        target="adeptus_astartes_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="ranged_weapons_gain_ignores_cover_and_ignore_skill_hit_modifiers",
        cp_cost=1,
        effect_params={
            "grant_ranged_keywords": ["IGNORES COVER"],
            "ignore_modifiers": ["ballistic_skill", "weapon_skill", "hit_roll"],
        },
    ),
    "000010397005": StratagemToolDescriptor(
        stratagem_id="000010397005",
        name="Reclaim Our Honour!",
        timing="shooting_or_fight_phase_after_enemy_destroys_friendly_ancient_model",
        target="adeptus_astartes_unit_visible_to_destroying_enemy",
        duration="until_end_of_battle",
        effect="mark_enemy_for_armywide_hit_bonus",
        cp_cost=1,
        effect_params={
            "hit_bonus": 1,
            "applies_against_destroying_enemy_only": True,
            "attacker_required_keywords_all": ["ADEPTUS ASTARTES"],
        },
    ),
    "000010397007": StratagemToolDescriptor(
        stratagem_id="000010397007",
        name="Perfervid Intervention",
        timing="end_of_opponent_charge_phase",
        target="adeptus_astartes_unit_within_6_of_enemy_unit_it_can_charge",
        duration="immediate",
        effect="out_of_turn_charge_without_charge_bonus",
        cp_cost=2,
        range_in=6.0,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "count_as_charged": False,
            "force_single_target": True,
        },
    ),
}

_VINDICATION_TASK_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _VINDICATION_TASK_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_WRATH_OF_THE_ROCK_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010161002": StratagemToolDescriptor(
        stratagem_id="000010161002",
        name="Inescapable Justice",
        timing="any_phase_after_oath_of_moment_target_destroyed",
        target="adeptus_astartes_character_unit_on_battlefield",
        duration="until_start_of_next_command_phase",
        effect="reassign_oath_of_moment_target_from_visible_character",
        cp_cost=2,
        range_in=12.0,
        effect_params={
            "secondary_target": "enemy_unit_visible_to_target",
            "reassigns_oath_of_moment_target": True,
        },
    ),
    "000010161003": StratagemToolDescriptor(
        stratagem_id="000010161003",
        name="Lion's Will",
        timing="command_phase",
        target="adeptus_astartes_unit_within_engagement_range",
        duration="mixed",
        effect="objective_control_until_next_command_phase_and_conditional_hit_bonus_until_end_of_turn",
        cp_cost=1,
        effect_params={
            "objective_control_bonus": 1,
            "hit_bonus": 1,
            "hit_bonus_excluded_keywords_any": ["DEATHWING", "RAVENWING", "VEHICLE"],
        },
    ),
    "000010161005": StratagemToolDescriptor(
        stratagem_id="000010161005",
        name="Tactical Mastery",
        timing="movement_phase",
        target="adeptus_astartes_unit",
        duration="until_end_of_turn",
        effect="shoot_and_charge_after_advance_with_ravenwing_fallback_extension",
        cp_cost=1,
        effect_params={
            "shoot_after_advance": True,
            "charge_after_advance": True,
            "shoot_after_fall_back_required_keyword": "RAVENWING",
            "charge_after_fall_back_required_keyword": "RAVENWING",
        },
    ),
    "000010161006": StratagemToolDescriptor(
        stratagem_id="000010161006",
        name="Relics of the Dark Age",
        timing="shooting_phase",
        target="adeptus_astartes_infantry_or_mounted_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="ranged_weapons_gain_plus_two_strength",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "strength_bonus": 2,
        },
    ),
    "000010161007": StratagemToolDescriptor(
        stratagem_id="000010161007",
        name="Leonine Aggression",
        timing="end_of_opponent_charge_phase",
        target="adeptus_astartes_unit_within_3_or_deathwing_within_6_of_enemy_unit_it_can_charge",
        duration="immediate",
        effect="out_of_turn_charge",
        cp_cost=1,
        range_in=6.0,
        effect_params={
            "required_keywords_all": ["ADEPTUS ASTARTES"],
            "extended_range_keyword": "DEATHWING",
        },
    ),
}

_WRATH_OF_THE_ROCK_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _WRATH_OF_THE_ROCK_STRATAGEM_DESCRIPTORS.values()
}

_WRATHFUL_PROCESSION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009844004": StratagemToolDescriptor(
        stratagem_id="000009844004",
        name="Castigate the Demagogues",
        timing="fight_phase_before_selected_to_fight",
        target="adeptus_astartes_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="grant_precision_to_melee_weapons",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "grant_keywords": ["PRECISION"],
        },
    ),
    "000009844005": StratagemToolDescriptor(
        stratagem_id="000009844005",
        name="Brute Fervour",
        timing="fight_phase_before_selected_to_fight",
        target="adeptus_astartes_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="ignore_skill_hit_wound_modifiers",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "reroll_hit_values": [1],
            "ignore_modifiers": ["weapon_skill", "hit_roll", "wound_roll"],
        },
    ),
    "000009844006": StratagemToolDescriptor(
        stratagem_id="000009844006",
        name="Relentless Momentum",
        timing="fight_phase_before_selected_to_fight",
        target="adeptus_astartes_unit_not_yet_selected_to_fight_in_engagement_range",
        duration="until_end_of_phase",
        effect="fight_eligibility_within_3",
        cp_cost=1,
        effect_params={
            "range_in": 3.0,
            "requires_unit_engagement_range": True,
        },
    ),
    "000009844007": StratagemToolDescriptor(
        stratagem_id="000009844007",
        name="Voice of Devotion",
        timing="your_command_phase",
        target="adeptus_astartes_infantry_or_mounted_unit",
        duration="until_end_of_battle_round",
        effect="unit_specific_zealous_litany_override",
        cp_cost=1,
        effect_params={
            "choices": [
                "CHORUS_OF_RELENTLESS_HATE",
                "RITE_OF_PERFERVID_WRATH",
                "CHANT_OF_DEATHLESS_DEVOTION",
            ],
        },
    ),
}

_WRATHFUL_PROCESSION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _WRATHFUL_PROCESSION_STRATAGEM_DESCRIPTORS.values()
}

_CHANGEHOST_OF_DECEIT_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010198002": StratagemToolDescriptor(
        stratagem_id="000010198002",
        name="Sulphurous Veil",
        timing="opponent_shooting_or_fight_phase_after_targets_selected",
        target="thousand_sons_or_scintillating_legions_unit_targeted_by_attacker",
        duration="until_end_of_phase",
        effect="hit_roll_penalty",
        cp_cost=1,
        effect_params={"hit_modifier": -1},
    ),
    "000010198003": StratagemToolDescriptor(
        stratagem_id="000010198003",
        name="Deceptive Glamour",
        timing="fight_phase_start",
        target="thousand_sons_unit",
        duration="until_end_of_phase",
        effect="engaged_enemy_target_lock_with_scintillating_legions_priority",
        cp_cost=2,
        effect_params={"preferred_friendly_target_keyword": "SCINTILLATING LEGIONS"},
    ),
    "000010198004": StratagemToolDescriptor(
        stratagem_id="000010198004",
        name="Ethereal Phantasm",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="scintillating_legions_unit_within_9_of_enemy_not_in_engagement_range",
        duration="immediate",
        effect="reactive_normal_move_with_thousand_sons_fixed_six",
        cp_cost=1,
        effect_params={
            "distance_roll": "D6",
            "fixed_distance_if_wholly_within_6_of_friendly_thousand_sons": 6,
            "enemy_trigger_distance": 9,
        },
    ),
    "000010198005": StratagemToolDescriptor(
        stratagem_id="000010198005",
        name="Fractal Disjunction",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="non_monster_scintillating_legions_unit_selected_as_target",
        duration="until_end_of_phase",
        effect="ranged_targeting_distance_cap",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "max_targeting_distance": 18,
        },
    ),
    "000010198006": StratagemToolDescriptor(
        stratagem_id="000010198006",
        name="Chronosorcerous Bleed",
        timing="opponent_charge_phase_after_charge_declared",
        target="thousand_sons_psyker_or_scintillating_legions_charge_target",
        duration="until_end_of_phase",
        effect="enemy_charge_roll_modifier_non_cumulative_negative",
        cp_cost=1,
        effect_params={"charge_roll_modifier": -2},
    ),
    "000010198007": StratagemToolDescriptor(
        stratagem_id="000010198007",
        name="Glimmershift Portal",
        timing="end_of_opponent_fight_phase",
        target="up_to_two_scintillating_legions_units_or_one_scintillating_legions_monster_more_than_6_horizontal_from_enemy",
        duration="immediate",
        effect="enter_strategic_reserves",
        cp_cost=1,
        effect_params={
            "max_units": 2,
            "monster_selection_limit": 1,
            "non_monster_selection_limit": 2,
            "min_enemy_horizontal_distance": 6.0,
            "required_keyword": "SCINTILLATING LEGIONS",
        },
    ),
}

_CHANGEHOST_OF_DECEIT_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CHANGEHOST_OF_DECEIT_STRATAGEM_DESCRIPTORS.values()
}

_GRAND_COVEN_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010194002": StratagemToolDescriptor(
        stratagem_id="000010194002",
        name="Psychic Dominion",
        timing="opponent_shooting_or_fight_phase_after_targets_selected",
        target="thousand_sons_unit_targeted_by_enemy_unit",
        duration="until_end_of_phase",
        effect="feel_no_pain_vs_psychic_and_attacker_psychic_hazardous",
        cp_cost=1,
        effect_params={
            "fnp": 4,
            "fnp_condition": "against psychic attacks",
            "grant_hazardous_to_attacker_psychic_weapons": True,
        },
    ),
    "000010194003": StratagemToolDescriptor(
        stratagem_id="000010194003",
        name="Destined by Fate",
        timing="any_phase_after_failed_save",
        target="thousand_sons_psyker_model_with_failed_save",
        duration="selected_attack_only",
        effect="set_damage_characteristic_to_zero",
        cp_cost=1,
    ),
    "000010194004": StratagemToolDescriptor(
        stratagem_id="000010194004",
        name="Egotistical Power",
        timing="your_command_phase",
        target="thousand_sons_psyker_unit",
        duration="until_your_next_command_phase",
        effect="unit_specific_kindred_sorcery_override",
        cp_cost=1,
        effect_params={
            "choices": [
                "IMBUED_MANIFESTATION",
                "PSYCHIC_MAELSTROM",
                "WRATH_OF_THE_IMMATERIUM",
            ],
        },
    ),
    "000010194005": StratagemToolDescriptor(
        stratagem_id="000010194005",
        name="Desecration of Worlds",
        timing="your_command_phase",
        target="thousand_sons_psyker_unit_within_controlled_objective_range",
        duration="until_opponent_control_greater_end_of_phase",
        effect="sticky_objective",
        cp_cost=1,
    ),
    "000010194006": StratagemToolDescriptor(
        stratagem_id="000010194006",
        name="Arcane Focus",
        timing="shooting_phase_after_channeled_ritual_test",
        target="thousand_sons_model_that_channeled_the_warp",
        duration="immediate",
        effect="reroll_all_channeled_ritual_test_dice",
        cp_cost=1,
        effect_params={"reroll_scope": "all_ritual_test_dice"},
    ),
    "000010194007": StratagemToolDescriptor(
        stratagem_id="000010194007",
        name="Devastating Sorcery",
        timing="shooting_phase_on_select_to_shoot",
        target="thousand_sons_psyker_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="psychic_range_bonus_and_full_hit_wound_rerolls",
        cp_cost=2,
        effect_params={
            "range_bonus": 9,
            "reroll_hit": "full",
            "reroll_wound": "full",
            "psychic_only": True,
        },
    ),
}

_GRAND_COVEN_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GRAND_COVEN_STRATAGEM_DESCRIPTORS.values()
}

_WARPFORGED_CABAL_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010210003": StratagemToolDescriptor(
        stratagem_id="000010210003",
        name="Mutate Landscape",
        timing="command_phase",
        target="thousand_sons_psyker_unit_within_controlled_objective_range",
        duration="until_opponent_control_greater_end_of_phase",
        effect="sticky_objective_with_move_end_mortal_wound_trap",
        cp_cost=1,
        effect_params={
            "trigger_actions": ["normal_move", "advance", "fall_back", "charge"],
            "trigger_roll": "D6",
            "success_on": 4,
            "mortal_wounds_roll": "D3",
        },
    ),
    "000010210004": StratagemToolDescriptor(
        stratagem_id="000010210004",
        name="Cyberspirit Machinations",
        timing="movement_phase_after_fall_back",
        target="thousand_sons_vehicle_unit_that_fell_back_within_6_of_friendly_psyker",
        duration="until_end_of_turn",
        effect="eligible_to_shoot_and_charge_after_fall_back",
        cp_cost=1,
    ),
    "000010210005": StratagemToolDescriptor(
        stratagem_id="000010210005",
        name="Malevolent Animus",
        timing="command_phase",
        target="thousand_sons_vehicle_unit_within_6_of_friendly_psyker",
        duration="until_your_next_command_phase",
        effect="ignore_characteristic_roll_and_test_modifiers_except_saves",
        cp_cost=1,
    ),
    "000010210006": StratagemToolDescriptor(
        stratagem_id="000010210006",
        name="Ensorcelled Infusion",
        timing="shooting_phase_on_select_to_shoot",
        target="thousand_sons_vehicle_unit_not_yet_shot_within_6_of_friendly_psyker",
        duration="until_end_of_phase",
        effect="ranged_psychic_and_wound_bonus",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "grant_keyword": "PSYCHIC",
            "wound_bonus": 1,
        },
    ),
    "000010210007": StratagemToolDescriptor(
        stratagem_id="000010210007",
        name="Warpflame Gargoyles",
        timing="opponent_charge_phase_after_charge_move_end",
        target="thousand_sons_vehicle_unit_within_engagement_range_of_enemy_that_just_charged",
        duration="immediate",
        effect="charge_end_mortal_wound_burst_and_battleshock",
        cp_cost=1,
        effect_params={
            "dice_count": 6,
            "success_on": 5,
            "mortal_wounds_per_success": 1,
            "force_battle_shock_test": True,
        },
    ),
}

_WARPFORGED_CABAL_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _WARPFORGED_CABAL_STRATAGEM_DESCRIPTORS.values()
}

_HEXWARP_THRALLBAND_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009742002": StratagemToolDescriptor(
        stratagem_id="000009742002",
        name="Warding Hex",
        timing="command_phase",
        target="thousand_sons_psyker_unit_within_controlled_objective_range_wholly_within_flow_of_magic",
        duration="until_opponent_control_greater_end_of_phase",
        effect="sticky_objective",
        cp_cost=1,
    ),
    "000009742003": StratagemToolDescriptor(
        stratagem_id="000009742003",
        name="Wrath of the Doomed",
        timing="fight_phase_after_enemy_targets_selected",
        target="thousand_sons_unit_targeted_by_attacking_enemy_unit",
        duration="until_end_of_phase",
        effect="fight_on_death_after_attacks",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "threshold": 4,
            "flow_of_magic_threshold": 3,
        },
    ),
    "000009742004": StratagemToolDescriptor(
        stratagem_id="000009742004",
        name="Strands of Time",
        timing="movement_phase_after_fall_back",
        target="thousand_sons_psyker_unit_that_fell_back",
        duration="until_end_of_turn",
        effect="shoot_or_charge_after_fall_back",
        cp_cost=1,
        effect_params={
            "choices": ["SHOOT", "CHARGE"],
            "flow_of_magic_choice": "BOTH",
        },
    ),
    "000009742005": StratagemToolDescriptor(
        stratagem_id="000009742005",
        name="Through the Veil",
        timing="movement_phase_reinforcements_step",
        target="rubric_marines_or_scarab_occult_terminators_unit_in_strategic_reserves",
        duration="until_end_of_phase",
        effect="temporary_deep_strike_with_hexwarp_flow_setup",
        cp_cost=1,
        effect_params={
            "rubric_marines_grant_temp_deep_strike": True,
            "scarab_occult_min_distance": 6,
            "scarab_occult_distance_type": "horizontal",
            "scarab_occult_requires_wholly_within_flow_of_magic": True,
        },
    ),
    "000009742006": StratagemToolDescriptor(
        stratagem_id="000009742006",
        name="Scouring Warpflame",
        timing="shooting_phase",
        target="thousand_sons_psyker_unit_wholly_within_flow_of_magic_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_ignores_cover_and_post_shoot_no_cover",
        cp_cost=1,
    ),
    "000009742007": StratagemToolDescriptor(
        stratagem_id="000009742007",
        name="Kaleidoscopic Tempest",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="thousand_sons_psyker_unit_targeted_by_attacking_enemy_unit",
        duration="until_end_of_phase",
        effect="stealth_and_conditional_cover",
        cp_cost=1,
        effect_params={
            "grant_stealth": True,
            "grant_cover_while_wholly_within_flow_of_magic": True,
        },
    ),
}

_HEXWARP_THRALLBAND_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _HEXWARP_THRALLBAND_STRATAGEM_DESCRIPTORS.values()
}

_WARPMELD_PACT_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010202002": StratagemToolDescriptor(
        stratagem_id="000010202002",
        name="Gift of Change",
        timing="any_phase_on_friendly_character_model_destroyed",
        target="just_destroyed_non_monster_thousand_sons_character_model_once_per_battle_round",
        duration="end_of_phase",
        effect="spawn_chaos_spawn_unit_at_end_of_phase",
        cp_cost=1,
        effect_params={
            "spawn_unit_name": "Chaos Spawn",
            "spawn_unit_datasheet_id": "000001023",
            "spawn_unit_faction_id": "TS",
            "spawn_model_count": 1,
            "setup_as_close_as_possible": True,
            "not_within_engagement_range": True,
            "once_per_battle_round": True,
        },
    ),
    "000010202004": StratagemToolDescriptor(
        stratagem_id="000010202004",
        name="Deranged Ferocity",
        timing="fight_phase_on_select_to_fight",
        target="tzeentch_mutant_unit_just_selected_to_fight",
        duration="until_end_of_phase",
        effect="fight_within_3_and_extend_pile_in_and_consolidate_to_six",
        cp_cost=1,
        effect_params={
            "eligibility_range": 3,
            "requires_target_unit_in_engagement_range": True,
            "pile_in_distance": 6,
            "consolidate_distance": 6,
        },
    ),
    "000010202005": StratagemToolDescriptor(
        stratagem_id="000010202005",
        name="Blessed Transmutations",
        timing="command_phase",
        target="tzaangors_unit_below_starting_strength_within_12_of_friendly_psyker",
        duration="immediate",
        effect="return_destroyed_models",
        cp_cost=1,
        effect_params={
            "return_roll": "D3+1",
            "required_keyword": "TZAANGORS",
            "exclude_character": True,
            "requires_friendly_psyker_within": 12,
        },
    ),
    "000010202006": StratagemToolDescriptor(
        stratagem_id="000010202006",
        name="Touched by Tzeentch",
        timing="movement_phase_start",
        target="tzeentch_mutant_unit",
        duration="until_end_of_turn",
        effect="shoot_and_charge_after_advance",
        cp_cost=1,
        effect_params={"advance_and_shoot": True, "advance_and_charge": True},
    ),
    "000010202007": StratagemToolDescriptor(
        stratagem_id="000010202007",
        name="Twisted Mirage",
        timing="movement_phase_reinforcements_step",
        target="tzeentch_mutant_unit_arriving_from_strategic_reserves",
        duration="this_turn_and_phase",
        effect="deep_strike_min_distance_override_with_no_charge",
        cp_cost=1,
        effect_params={
            "min_distance": 6,
            "monster_min_distance": 9,
            "distance_type": "horizontal",
            "grant_temp_deep_strike": True,
            "cannot_charge_this_turn": True,
            "required_reserve_status": "strategic_reserves",
        },
    ),
}

_WARPMELD_PACT_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _WARPMELD_PACT_STRATAGEM_DESCRIPTORS.values()
}

_RUBRICAE_PHALANX_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010206002": StratagemToolDescriptor(
        stratagem_id="000010206002",
        name="Ardent Automata",
        timing="movement_phase_after_fall_back",
        target="rubricae_unit_that_fell_back",
        duration="until_end_of_turn",
        effect="eligible_to_shoot_and_charge_after_fall_back",
        cp_cost=1,
    ),
    "000010206003": StratagemToolDescriptor(
        stratagem_id="000010206003",
        name="Inexorable Advance",
        timing="movement_phase",
        target="rubricae_unit_not_yet_moved",
        duration="until_end_of_turn",
        effect="ignore_move_and_advance_modifiers_and_gain_ranged_assault",
        cp_cost=1,
        effect_params={
            "ignore_modifiers": ["move_characteristic", "advance_roll"],
            "grant_ranged_assault": True,
        },
    ),
    "000010206004": StratagemToolDescriptor(
        stratagem_id="000010206004",
        name="Infernal Fusillade",
        timing="shooting_phase",
        target="thousand_sons_psyker_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="inferno_weapons_gain_psychic_and_set_strength",
        cp_cost=2,
        effect_params={
            "weapon_names": [
                "inferno bolt pistol",
                "inferno boltgun",
                "inferno combi-bolter",
                "inferno combi-weapon",
            ],
            "set_strength": 5,
            "grant_keyword": "PSYCHIC",
            "attack_type": "ranged",
        },
    ),
    "000010206005": StratagemToolDescriptor(
        stratagem_id="000010206005",
        name="Revenge of the Rubricae",
        timing="opponent_shooting_phase_after_enemy_shoots_with_psyker_model_destroyed",
        target="rubricae_unit_within_6_of_destroyed_model",
        duration="immediate",
        effect="reactive_shooting_at_attacker",
        cp_cost=1,
        effect_params={
            "max_distance_inches": 6.0,
            "force_target_attacker": True,
            "trigger_requires_destroyed_model_keyword": "PSYKER",
        },
    ),
    "000010206006": StratagemToolDescriptor(
        stratagem_id="000010206006",
        name="Implacable Guardians",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="rubric_marines_psyker_unit_selected_by_attacker",
        duration="until_end_of_phase",
        effect="reduce_damage_allocated_except_psyker_models",
        cp_cost=2,
        effect_params={
            "damage_reduction": 1,
            "exclude_allocated_model_keyword": "PSYKER",
            "attack_type": "any",
        },
    ),
    "000010206007": StratagemToolDescriptor(
        stratagem_id="000010206007",
        name="Unwavering Phalanx",
        timing="opponent_charge_phase_after_enemy_charge_move_end",
        target="rubric_marines_unit_within_engagement_range_of_charger",
        duration="until_end_of_turn",
        effect="defensive_wound_penalty",
        cp_cost=1,
        effect_params={
            "wound_roll_modifier": -1,
            "attack_type": "any",
        },
    ),
}

_RUBRICAE_PHALANX_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RUBRICAE_PHALANX_STRATAGEM_DESCRIPTORS.values()
}

_NEEDGAARD_OATHBAND_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010436005": StratagemToolDescriptor(
        stratagem_id="000010436005",
        name="Ancestral Sentence",
        timing="shooting_phase_start",
        target="leagues_of_votann_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="grant_ranged_sustained_hits",
        cp_cost=1,
        effect_params={
            "sustained_hits_value": 1,
            "optional_yield_points_cost": 3,
            "optional_sustained_hits_value": 2,
        },
    ),
    "000010436006": StratagemToolDescriptor(
        stratagem_id="000010436006",
        name="Huntr's Mark",
        timing="shooting_phase_start",
        target="leagues_of_votann_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="reroll_hit_and_wound_ones",
        cp_cost=1,
        effect_params={"attack_type": "ranged"},
    ),
    "000010436003": StratagemToolDescriptor(
        stratagem_id="000010436003",
        name="Honour of the Hold",
        timing="fight_phase_start",
        target="leagues_of_votann_unit_not_yet_fought_with_selected_enemy_in_engagement_range",
        duration="until_end_of_phase",
        effect="melee_ap_bonus_against_selected_enemy",
        cp_cost=1,
        effect_params={
            "ap_bonus": 1,
            "optional_yield_points_cost": 3,
            "optional_ap_bonus": 2,
        },
    ),
    "000010436004": StratagemToolDescriptor(
        stratagem_id="000010436004",
        name="Ordered Retreat",
        timing="movement_phase_after_fall_back",
        target="leagues_of_votann_unit_that_fell_back",
        duration="until_end_of_turn",
        effect="eligible_to_shoot_and_charge_after_fall_back",
        cp_cost=1,
    ),
    "000010436007": StratagemToolDescriptor(
        stratagem_id="000010436007",
        name="Reactive Reprisal",
        timing="opponent_shooting_phase_after_enemy_shoots_with_fortify_takeover",
        target="leagues_of_votann_unit_targeted_by_enemy_shooter",
        duration="immediate",
        effect="reactive_shooting_at_attacker",
        cp_cost=2,
        effect_params={"target_restriction": "attacking_enemy_unit_only"},
    ),
    "000010436002": StratagemToolDescriptor(
        stratagem_id="000010436002",
        name="Void Hardened",
        timing="opponent_shooting_or_either_fight_phase_after_targets_selected_with_fortify_takeover",
        target="leagues_of_votann_unit_targeted_by_enemy_attacker",
        duration="until_attacker_finishes_attacks",
        effect="worsen_incoming_ap",
        cp_cost=1,
        effect_params={"ap_worsen": 1, "duration_scope": "attacking_enemy_unit"},
    ),
}

_NEEDGAARD_OATHBAND_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NEEDGAARD_OATHBAND_STRATAGEM_DESCRIPTORS.values()
}

_VALOURSTRIKE_LANCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010494002": StratagemToolDescriptor(
        stratagem_id="000010494002",
        name="Run Them Through!",
        timing="fight_phase_on_select_to_fight",
        target="imperial_knights_unit_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="melee_weapons_gain_lance",
        cp_cost=1,
        effect_params={"keyword": "LANCE"},
    ),
    "000010494003": StratagemToolDescriptor(
        stratagem_id="000010494003",
        name="Thunderstomp",
        timing="fight_phase_on_select_to_fight",
        target="imperial_knights_model_not_yet_selected_to_fight",
        duration="until_end_of_phase",
        effect="feet_weapon_attacks_set_and_ap_bonus",
        cp_cost=1,
        effect_params={
            "weapon_names": ["armoured feet", "titanic feet"],
            "armoured_feet_attacks": 8,
            "titanic_feet_attacks": 12,
            "ap_bonus": 1,
        },
    ),
    "000010494004": StratagemToolDescriptor(
        stratagem_id="000010494004",
        name="Full Tilt",
        timing="movement_phase_before_select_to_move",
        target="imperial_knights_unit_not_yet_selected_to_move",
        duration="until_end_of_phase",
        effect="movement_and_advance_bonus",
        cp_cost=2,
        effect_params={"move_bonus": 2, "advance_roll_bonus": 2},
    ),
    "000010494005": StratagemToolDescriptor(
        stratagem_id="000010494005",
        name="Vow of Retribution",
        timing="shooting_phase_on_select_to_shoot",
        target="imperial_knights_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_lethal_hits",
        cp_cost=1,
    ),
    "000010494007": StratagemToolDescriptor(
        stratagem_id="000010494007",
        name="Rotate Ion Shields",
        timing="opponent_shooting_phase_after_targets_selected",
        target="imperial_knights_unit_targeted",
        duration="until_end_of_phase",
        effect="invulnerable_save",
        cp_cost=1,
        effect_params={"invulnerable_save": 4},
    ),
    "000010494006": StratagemToolDescriptor(
        stratagem_id="000010494006",
        name="Tactical Foil",
        timing="opponent_movement_phase_on_enemy_move_end",
        target="imperial_knights_unit_within_9_of_moved_enemy_unit",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "distance_roll": "D6",
            "trigger_actions": ["move", "advance", "fall_back"],
        },
    ),
}

_VALOURSTRIKE_LANCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _VALOURSTRIKE_LANCE_STRATAGEM_DESCRIPTORS.values()
}

_SPEARHEAD_AT_ARMS_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010507006": StratagemToolDescriptor(
        stratagem_id="000010507006",
        name="Let Duty Be Your Shield",
        timing="opponent_shooting_phase_after_targets_selected",
        target="armiger_unit_selected_as_target",
        duration="until_attacker_finishes_attacks",
        effect="worsen_incoming_ap",
        cp_cost=1,
        effect_params={"ap_worsen": 1, "duration_scope": "attacking_enemy_unit"},
    ),
    "000010507003": StratagemToolDescriptor(
        stratagem_id="000010507003",
        name="Exemplar's Wisdom",
        timing="shooting_phase_after_titanic_model_shoots",
        target="imperial_knights_titanic_model_and_one_or_more_bondsman_armigers_then_one_hit_enemy",
        duration="until_end_of_phase",
        effect="selected_bondsman_armigers_gain_ap_against_selected_hit_enemy",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "ap_bonus": 1,
            "requires_bondsman": True,
            "requires_hit_enemy_selection": True,
        },
    ),
}

_SPEARHEAD_AT_ARMS_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPEARHEAD_AT_ARMS_STRATAGEM_DESCRIPTORS.values()
}

_IMPERIALIS_FLEET_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009139003": StratagemToolDescriptor(
        stratagem_id="000009139003",
        name="Masters of the Void",
        timing="movement_phase_reinforcements_step",
        target="voidfarers_character_unit",
        duration="until_end_of_phase",
        effect="strategic_reserves_enemy_deployment_zone_override",
        cp_cost=1,
        effect_params={
            "applies_to_keyword": "AGENTS OF THE IMPERIUM",
            "applies_to_arrival_type": "strategic_reserves",
            "allow_enemy_deployment_zone": True,
        },
    ),
}

_IMPERIALIS_FLEET_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _IMPERIALIS_FLEET_STRATAGEM_DESCRIPTORS.values()
}

_VEILED_BLADE_ELIMINATION_FORCE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009758002": StratagemToolDescriptor(
        stratagem_id="000009758002",
        name="Prime Target",
        timing="shooting_or_fight_phase_on_select",
        target="agents_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="wound_reroll_ones_vs_character_with_officio_warlord_full_reroll",
        cp_cost=1,
        effect_params={
            "reroll_wound_ones_vs_keyword": "CHARACTER",
            "officio_assassinorum_full_reroll_vs_enemy_warlord": True,
        },
    ),
    "000009758003": StratagemToolDescriptor(
        stratagem_id="000009758003",
        name="Hyperstimms",
        timing="opponent_shooting_or_fight_phase_after_targets_selected",
        target="agents_character_unit_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="toughness_bonus_and_conditional_feel_no_pain",
        cp_cost=2,
        effect_params={"toughness_bonus": 1, "eversor_assassin_feel_no_pain": 4},
    ),
    "000009758004": StratagemToolDescriptor(
        stratagem_id="000009758004",
        name="Will-Sapping Salvo",
        timing="shooting_phase_on_select_to_shoot",
        target="agents_infantry_unit_not_yet_shot",
        duration="until_end_of_phase",
        effect="ranged_sustained_hits_and_culexus_damage_override",
        cp_cost=1,
        effect_params={"sustained_hits_value": 1, "culexus_ranged_damage_override": 3},
    ),
    "000009758005": StratagemToolDescriptor(
        stratagem_id="000009758005",
        name="Orbital Oversight",
        timing="opponent_shooting_phase_after_targets_selected",
        target="agents_infantry_unit_selected_as_attack_target",
        duration="until_end_of_phase",
        effect="ranged_targeting_range_restriction",
        cp_cost=1,
        effect_params={"targeting_range": 18, "lone_operative_targeting_range": 6},
    ),
    "000009758006": StratagemToolDescriptor(
        stratagem_id="000009758006",
        name="Blind Grenades",
        timing="opponent_charge_phase_after_charge_declared",
        target="agents_grenades_or_vindicare_unit_selected_as_charge_target_not_in_engagement",
        duration="until_end_of_phase",
        effect="enemy_charge_roll_penalty",
        cp_cost=1,
        effect_params={
            "charge_roll_modifier": -1,
            "vindicare_charge_roll_modifier": -2,
            "applies_to_declared_charge_only": True,
        },
    ),
    "000009758007": StratagemToolDescriptor(
        stratagem_id="000009758007",
        name="Ensnaring Trap",
        timing="end_of_opponent_charge_phase",
        target="agents_infantry_within_6_of_enemy_unit_it_can_charge",
        duration="immediate_and_until_end_of_turn",
        effect="out_of_turn_charge_without_charge_bonus",
        cp_cost=1,
        range_in=6.0,
        effect_params={
            "count_as_charged": False,
            "callidus_melee_wound_bonus": 1,
            "callidus_bonus_duration": "until_end_of_turn",
        },
    ),
}

_VEILED_BLADE_ELIMINATION_FORCE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _VEILED_BLADE_ELIMINATION_FORCE_STRATAGEM_DESCRIPTORS.values()
}

_ANNIHILATION_LEGION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008405006": StratagemToolDescriptor(
        stratagem_id="000008405006",
        name="Blood-Fuelled Cruelty",
        timing="opponent_movement_phase_after_enemy_fall_back",
        target="necrons_destroyer_cult_or_flayed_ones_unit_that_started_phase_engaged_with_enemy",
        duration="immediate",
        effect="reactive_normal_move_toward_trigger_unit_with_pre_move_mortal_wounds",
        cp_cost=1,
        effect_params={
            "must_end_as_close_as_possible_to_trigger_unit": True,
            "pre_move_roll": "D6",
            "mortal_wounds_on_2_to_5": "D3",
            "mortal_wounds_on_6": 3,
        },
    ),
    "000008405007": StratagemToolDescriptor(
        stratagem_id="000008405007",
        name="Insanity's Ire",
        timing="opponent_shooting_phase_after_enemy_shooting_resolved",
        target="necrons_destroyer_cult_or_flayed_ones_unit_that_lost_models_to_attacker",
        duration="immediate",
        effect="reactive_normal_move_toward_trigger_unit",
        cp_cost=1,
        effect_params={
            "must_end_as_close_as_possible_to_trigger_unit": True,
        },
    ),
    "000008405004": StratagemToolDescriptor(
        stratagem_id="000008405004",
        name="Murderous Reanimation",
        timing="fight_phase_after_friendly_attacks_resolved",
        target="necrons_destroyer_cult_or_flayed_ones_unit_that_destroyed_enemy_or_made_enemy_below_half_strength",
        duration="immediate",
        effect="conditional_trigger_reanimation_protocols",
        cp_cost=1,
        effect_params={
            "reanimation_roll": "D3",
            "trigger_conditions": ["destroyed_enemy_unit", "caused_enemy_below_half_strength"],
        },
    ),
    "000008405005": StratagemToolDescriptor(
        stratagem_id="000008405005",
        name="Pitiless Hunters",
        timing="fight_phase_on_select_to_fight",
        target="necrons_destroyer_cult_or_flayed_ones_unit_not_yet_fought",
        duration="until_end_of_phase",
        effect="extend_pile_in_and_consolidate_to_six",
        cp_cost=1,
        effect_params={"pile_in_distance": 6, "consolidate_distance": 6},
    ),
    "000008405003": StratagemToolDescriptor(
        stratagem_id="000008405003",
        name="The Spoor of Frailty",
        timing="shooting_or_fight_phase_on_select",
        target="necrons_destroyer_cult_or_flayed_ones_unit_not_yet_selected",
        duration="until_end_of_phase",
        effect="hit_bonus_vs_targets_below_starting_strength_and_wound_bonus_vs_targets_below_half_strength",
        cp_cost=1,
        effect_params={
            "hit_bonus": 1,
            "hit_target_condition": "below_starting_strength",
            "wound_bonus": 1,
            "wound_target_condition": "below_half_strength",
        },
    ),
}

_ANNIHILATION_LEGION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ANNIHILATION_LEGION_STRATAGEM_DESCRIPTORS.values()
}

_AWAKENED_DYNASTY_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008371006": StratagemToolDescriptor(
        stratagem_id="000008371006",
        name="PROTOCOL OF THE CONQUERING TYRANT",
        timing="your_shooting_phase",
        target="necrons_unit_not_selected_to_shoot",
        duration="until_end_of_phase",
        effect="ranged_hit_reroll_ones_or_full_within_half_range",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "reroll_hit_values": [1],
            "reroll_hit_full_if_within_half_range": True,
            "requires_within_half_range": True,
            "full_reroll_if_led_by_character": True,
        },
    ),
    "000008371002": StratagemToolDescriptor(
        stratagem_id="000008371002",
        name="PROTOCOL OF THE ETERNAL REVENANT",
        timing="any_phase_on_friendly_character_model_destroyed_before_removal",
        target="just_destroyed_necrons_infantry_character_model_once_per_battle_per_model",
        duration="end_of_phase",
        effect="return_destroyed_model_at_half_wounds_as_close_as_possible_not_in_engagement",
        cp_cost=1,
        effect_params={
            "return_timing": "end_of_phase",
            "wounds_fraction": 0.5,
            "round_up": True,
            "once_per_battle_per_model": True,
            "not_within_engagement_range": True,
        },
    ),
    "000008371004": StratagemToolDescriptor(
        stratagem_id="000008371004",
        name="PROTOCOL OF THE HUNGRY VOID",
        timing="fight_phase",
        target="necrons_unit_not_selected_to_fight",
        duration="until_end_of_phase",
        effect="melee_strength_bonus_and_conditional_ap_bonus",
        cp_cost=1,
        effect_params={
            "attack_type": "melee",
            "melee_strength_bonus": 1,
            "conditional_melee_ap_bonus": 1,
            "condition": "character_leading",
        },
    ),
    "000008371005": StratagemToolDescriptor(
        stratagem_id="000008371005",
        name="PROTOCOL OF THE SUDDEN STORM",
        timing="your_movement_phase",
        target="necrons_unit",
        duration="until_end_of_turn",
        effect="grant_assault_and_conditional_advance_reroll",
        cp_cost=1,
        effect_params={
            "attack_type": "ranged",
            "grant_keywords": ["ASSAULT"],
            "conditional_reroll_advance": True,
            "condition": "character_leading",
        },
    ),
    "000008371003": StratagemToolDescriptor(
        stratagem_id="000008371003",
        name="PROTOCOL OF THE UNDYING LEGIONS",
        timing="opponent_shooting_or_fight_phase_after_enemy_attacks_resolved",
        target="necrons_unit_that_lost_models_to_attacker_with_reanimation_protocols",
        duration="immediate",
        effect="trigger_reanimation_protocols_with_conditional_bonus",
        cp_cost=1,
        effect_params={
            "reanimation_roll": "D3",
            "conditional_bonus_wounds": 1,
            "condition": "character_leading",
            "requires_reanimation_protocols": True,
        },
    ),
    "000008371007": StratagemToolDescriptor(
        stratagem_id="000008371007",
        name="PROTOCOL OF THE VENGEFUL STARS",
        timing="opponent_shooting_phase_after_enemy_unit_destroys_friendly_unit",
        target="necrons_character_unit_within_6_of_destroyed_friendly_unit",
        duration="immediate",
        effect="reactive_shooting_restricted_to_attacker",
        cp_cost=2,
        effect_params={
            "out_of_phase": True,
            "force_target_attacker_only": True,
            "requires_eligible_shooting_target": True,
            "range_inches": 6.0,
        },
    ),
}

_AWAKENED_DYNASTY_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AWAKENED_DYNASTY_STRATAGEM_DESCRIPTORS.values()
}

_CURSED_LEGION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010669003": StratagemToolDescriptor(
        stratagem_id="000010669003",
        name="Image of Death",
        timing="opponent_shooting_or_fight_phase_after_enemy_targets_selected",
        target="friendly_destroyer_cult_unit_selected_as_target",
        duration="until_end_of_phase",
        effect="defensive_hit_penalty",
        cp_cost=1,
        effect_params={"hit_roll_modifier": -1},
    ),
    "000010669005": StratagemToolDescriptor(
        stratagem_id="000010669005",
        name="Driven to Butchery",
        timing="your_shooting_or_charge_phase",
        target="friendly_destroyer_cult_unit",
        duration="until_end_of_turn",
        effect="shoot_and_charge_after_advance",
        cp_cost=1,
        effect_params={"advance_and_shoot": True, "advance_and_charge": True},
    ),
    "000010669002": StratagemToolDescriptor(
        stratagem_id="000010669002",
        name="Methodical Murder",
        timing="your_shooting_or_fight_phase_on_select",
        target="friendly_necrons_non_monster_non_vehicle_unit_not_yet_selected",
        duration="until_end_of_phase",
        effect="grant_sustained_hits_all_weapons",
        cp_cost=1,
        effect_params={"granted_keyword": "SUSTAINED HITS", "keyword_value": 1},
    ),
    "000010669004": StratagemToolDescriptor(
        stratagem_id="000010669004",
        name="Mortis Protocols",
        timing="your_shooting_or_fight_phase_after_first_friendly_destroyer_cult_unit_destroys_enemy",
        target="friendly_necrons_non_monster_non_vehicle_unit_within_9_with_reanimation_protocols",
        duration="immediate",
        effect="trigger_reanimation_protocols",
        cp_cost=1,
        range_in=9.0,
        effect_params={
            "reanimation_roll": "D3",
            "requires_reanimation_protocols": True,
            "trigger_condition": "first_friendly_destroyer_cult_unit_destroyed_enemy_this_turn",
        },
    ),
    "000010669006": StratagemToolDescriptor(
        stratagem_id="000010669006",
        name="Spreading Madness",
        timing="your_charge_phase",
        target="friendly_necrons_non_monster_non_vehicle_unit_not_yet_selected_to_charge",
        duration="until_end_of_phase",
        effect="conditional_charge_roll_bonus_if_charge_target_engaged",
        cp_cost=1,
        effect_params={
            "charge_roll_modifier": 2,
            "condition": "charge_target_within_engagement_range_of_friendly_unit",
        },
    ),
    "000010669007": StratagemToolDescriptor(
        stratagem_id="000010669007",
        name="Unnatural Aggression",
        timing="end_of_opponent_charge_phase",
        target="friendly_necrons_non_monster_non_vehicle_unit_within_6_of_enemy_it_can_charge",
        duration="immediate",
        effect="out_of_turn_charge_without_charge_bonus",
        cp_cost=2,
        range_in=6.0,
        effect_params={"count_as_charged": False},
    ),
}

_CURSED_LEGION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CURSED_LEGION_STRATAGEM_DESCRIPTORS.values()
}

_CRYPTEK_CONCLAVE_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000010665004": StratagemToolDescriptor(
        stratagem_id="000010665004",
        name="ANIMUS CURSE",
        timing="opponent_shooting_or_fight_phase_after_enemy_attacks_resolved",
        target="just_destroyed_friendly_cryptek_model",
        duration="until_end_of_battle",
        effect="mark_enemy_for_necrons_hit_rerolls",
        cp_cost=1,
        effect_params={"reroll_hit_full": True, "attacker_keyword": "NECRONS"},
    ),
    "000010665003": StratagemToolDescriptor(
        stratagem_id="000010665003",
        name="MICROSCARAB SWARM",
        timing="opponent_shooting_or_fight_phase_after_enemy_targets_selected",
        target="friendly_cryptek_infantry_unit_selected_as_target",
        duration="until_end_of_phase",
        effect="conditional_unit_invulnerable_save_by_keyword",
        cp_cost=1,
        effect_params={
            "keyword_invulnerable_save_map": {
                "NECRON WARRIORS": 5,
                "IMMORTALS": 4,
            }
        },
    ),
    "000010665002": StratagemToolDescriptor(
        stratagem_id="000010665002",
        name="MOLECULAR TARGETING",
        timing="your_shooting_or_fight_phase_on_select",
        target="necrons_unit_not_yet_selected_to_shoot_or_fight",
        duration="until_end_of_phase",
        effect="ignore_skill_hit_and_conditional_wound_modifiers",
        cp_cost=1,
        effect_params={
            "ignore_skill_modifiers": True,
            "ignore_hit_modifiers": True,
            "ignore_wound_modifiers_if_cryptek": True,
        },
    ),
    "000010665007": StratagemToolDescriptor(
        stratagem_id="000010665007",
        name="POTENTIALITY SYPHON",
        timing="opponent_command_phase",
        target="necrons_unit_within_objective_range_with_reanimation_protocols",
        duration="immediate",
        effect="trigger_reanimation_protocols_with_conditional_bonus",
        cp_cost=1,
        effect_params={
            "reanimation_roll": "D3",
            "conditional_bonus_wounds": 1,
            "condition": "cryptek_unit",
            "requires_objective_range": True,
            "requires_reanimation_protocols": True,
        },
    ),
    "000010665005": StratagemToolDescriptor(
        stratagem_id="000010665005",
        name="SYNERGISTIC EMPOWERMENT",
        timing="start_of_your_shooting_phase",
        target="friendly_cryptek_unit_and_friendly_necrons_non_monster_non_vehicle_model_within_12",
        duration="until_end_of_phase",
        effect="temporary_model_cryptek_keyword",
        cp_cost=1,
        range_in=12.0,
        effect_params={
            "granted_keyword": "CRYPTEK",
            "excluded_keywords_any": ["MONSTER", "VEHICLE"],
        },
    ),
    "000010665006": StratagemToolDescriptor(
        stratagem_id="000010665006",
        name="UNTAPPED POWER",
        timing="your_shooting_phase",
        target="friendly_cryptek_unit_not_yet_selected_to_shoot",
        duration="until_end_of_phase",
        effect="additional_technosorcerous_augmentation_choice",
        cp_cost=1,
        effect_params={"additional_choices": 1},
    ),
}

_CRYPTEK_CONCLAVE_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CRYPTEK_CONCLAVE_STRATAGEM_DESCRIPTORS.values()
}

_CANOPTEK_COURT_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008547006": StratagemToolDescriptor(
        stratagem_id="000008547006",
        name="COUNTERTEMPORAL SHIFT",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="friendly_canoptek_unit_selected_as_ranged_target",
        duration="until_end_of_phase",
        effect="ranged_targeting_range_restriction",
        cp_cost=1,
        effect_params={"targeting_range": 18},
    ),
    "000008547002": StratagemToolDescriptor(
        stratagem_id="000008547002",
        name="CURSE OF THE CRYPTEK",
        timing="opponent_shooting_or_fight_phase_after_enemy_attacks_resolved",
        target="just_destroyed_friendly_cryptek_model",
        duration="until_end_of_battle",
        effect="mark_enemy_for_canoptek_hit_and_wound_bonus",
        cp_cost=1,
        effect_params={"hit_bonus": 1, "wound_bonus": 1, "attacker_keyword": "CANOPTEK"},
    ),
    "000008547003": StratagemToolDescriptor(
        stratagem_id="000008547003",
        name="CYNOSURE OF ERADICATION",
        timing="start_of_your_shooting_or_fight_phase",
        target="friendly_cryptek_or_canoptek_unit_wholly_within_power_matrix",
        duration="until_end_of_phase",
        effect="grant_devastating_wounds_to_cryptek_or_canoptek_models",
        cp_cost=2,
        effect_params={"granted_keyword": "DEVASTATING WOUNDS"},
    ),
    "000008547005": StratagemToolDescriptor(
        stratagem_id="000008547005",
        name="REACTIVE SUBROUTINES",
        timing="opponent_movement_phase_after_enemy_move_end",
        target="friendly_canoptek_unit_within_9_of_enemy",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        range_in=9.0,
        effect_params={"max_distance": 6},
    ),
    "000008547004": StratagemToolDescriptor(
        stratagem_id="000008547004",
        name="SOLAR PULSE",
        timing="start_of_your_shooting_phase",
        target="friendly_cryptek_model_and_objective_within_18",
        duration="until_end_of_phase",
        effect="grant_ignores_cover_vs_units_within_selected_objective",
        cp_cost=1,
        range_in=18.0,
        effect_params={"granted_keyword": "IGNORES COVER"},
    ),
    "000008547007": StratagemToolDescriptor(
        stratagem_id="000008547007",
        name="SUBOPTIMAL FACADE",
        timing="opponent_charge_phase_after_charge_declared",
        target="friendly_canoptek_unit_selected_as_charge_target_wholly_within_power_matrix",
        duration="immediate",
        effect="trigger_reanimation_protocols",
        cp_cost=1,
        effect_params={"reanimation_roll": "D3", "requires_power_matrix": True},
    ),
}

_CANOPTEK_COURT_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CANOPTEK_COURT_STRATAGEM_DESCRIPTORS.values()
}

_HYPERCRYPT_LEGION_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000008555002": StratagemToolDescriptor(
        stratagem_id="000008555002",
        name="Hyperphasic Recall",
        timing="opponent_shooting_or_fight_phase_after_enemy_attacks_resolved",
        target="necrons_infantry_unit_that_lost_models_and_friendly_monolith",
        duration="immediate",
        effect="remove_and_set_up_within_monolith_range",
        cp_cost=2,
        range_in=6.0,
        effect_params={
            "required_keywords_any": ["INFANTRY"],
            "anchor_required_keywords_any": ["MONOLITH"],
            "setup_wholly_within_anchor": True,
            "requires_destroyed_models_from_attacker": True,
            "require_not_engagement": True,
        },
    ),
    "000008555003": StratagemToolDescriptor(
        stratagem_id="000008555003",
        name="Quantum Deflection",
        timing="opponent_shooting_or_fight_phase_after_enemy_targets_selected",
        target="necrons_vehicle_unit_targeted_by_enemy_attacks",
        duration="until_end_of_phase",
        effect="grant_invulnerable_save",
        cp_cost=1,
        effect_params={
            "required_keywords_any": ["VEHICLE"],
            "invulnerable_save": 4,
        },
    ),
    "000008555004": StratagemToolDescriptor(
        stratagem_id="000008555004",
        name="Reanimation Crypts",
        timing="command_phase",
        target="necrons_warlord",
        duration="immediate",
        effect="trigger_reanimation_protocols_for_all_reserve_units",
        cp_cost=1,
        effect_params={
            "reserve_status": "reserves",
            "reanimation_roll": "D3",
            "target_scope": "all_friendly_necrons_units_in_reserves",
        },
    ),
    "000008555005": StratagemToolDescriptor(
        stratagem_id="000008555005",
        name="Cosmic Precision",
        timing="movement_phase_reinforcements_step",
        target="necrons_non_monster_unit_arriving_via_deep_strike_or_hyperphasing",
        duration="this_turn_no_charge",
        effect="deep_strike_min_distance_override_with_no_charge",
        cp_cost=1,
        effect_params={
            "deep_strike_min_distance": 6,
            "distance_type": "horizontal",
            "no_charge_this_turn": True,
            "allow_hyperphasing_arrivals": True,
        },
    ),
    "000008555006": StratagemToolDescriptor(
        stratagem_id="000008555006",
        name="Dimensional Corridor",
        timing="charge_phase",
        target="necrons_unit_set_up_via_eternity_gate_this_turn",
        duration="until_end_of_phase",
        effect="allow_charge_after_eternity_gate",
        cp_cost=2,
        effect_params={
            "requires_setup_source": "eternity_gate",
            "requires_anchor_keywords_any": ["MONOLITH"],
            "requires_anchor_started_turn_on_battlefield": True,
        },
    ),
    "000008555007": StratagemToolDescriptor(
        stratagem_id="000008555007",
        name="Entropic Damping",
        timing="opponent_shooting_phase_after_enemy_targets_selected",
        target="friendly_titanic_model_targeted_by_enemy_within_18",
        duration="until_end_of_phase",
        effect="attacker_ranged_weapons_become_hazardous_against_target",
        cp_cost=1,
        range_in=18.0,
        effect_params={
            "required_keywords_any": ["TITANIC"],
            "grant_ranged_hazardous": True,
        },
    ),
}

_HYPERCRYPT_LEGION_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _HYPERCRYPT_LEGION_STRATAGEM_DESCRIPTORS.values()
}

_STARSHATTER_ARSENAL_STRATAGEM_DESCRIPTORS: dict[str, StratagemToolDescriptor] = {
    "000009750002": StratagemToolDescriptor(
        stratagem_id="000009750002",
        name="MERCILESS RECLAMATION",
        timing="shooting_or_fight_phase_on_select",
        target="necrons_non_monster_non_titanic_unit_not_yet_selected",
        duration="until_end_of_phase",
        effect="wound_bonus_vs_targets_within_objective_range",
        cp_cost=2,
        effect_params={
            "wound_bonus": 1,
            "requires_objective_range_target": True,
            "excluded_keywords": ("MONSTER", "TITANIC"),
        },
    ),
    "000009750006": StratagemToolDescriptor(
        stratagem_id="000009750006",
        name="ENDLESS SERVITUDE",
        timing="end_of_fight_phase",
        target="necrons_non_monster_non_titanic_unit_within_controlled_objective",
        duration="immediate",
        effect="trigger_reanimation_protocols",
        cp_cost=1,
        effect_params={
            "reanimation_roll": "D3",
            "requires_reanimation_protocols": True,
            "excluded_keywords": ("MONSTER", "TITANIC"),
        },
    ),
    "000009750007": StratagemToolDescriptor(
        stratagem_id="000009750007",
        name="REACTIVE REPOSITION",
        timing="opponent_shooting_phase_after_enemy_shooting_resolved",
        target="necrons_non_monster_non_titanic_unit_targeted_by_attacker",
        duration="immediate",
        effect="reactive_normal_move",
        cp_cost=1,
        effect_params={
            "move_roll": "D6",
            "excluded_keywords": ("MONSTER", "TITANIC"),
            "requires_not_in_engagement_range": True,
        },
    ),
}

_STARSHATTER_ARSENAL_STRATAGEM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _STARSHATTER_ARSENAL_STRATAGEM_DESCRIPTORS.values()
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
        desc = _BLOOD_LEGION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _PLAGUE_LEGION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CHAMPIONS_OF_CONTAGION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _DEATH_LORDS_CHOSEN_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _FLYBLOWN_HOST_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _MORTARIONS_HAMMER_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SHAMBLEROT_VECTORIUM_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _TALLYBAND_SUMMONERS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SHADOW_LEGION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _LEGION_OF_EXCESS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _GORETRACK_ONSLAUGHT_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _GREEN_TIDE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _ORKS_TEMP_BUFF_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _POSSESSED_SLAUGHTERBAND_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _HOST_OF_ASCENSION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _BROOD_BROTHER_AUXILIA_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _VESSELS_OF_WRATH_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CULT_OF_BLOOD_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _GRIZZLED_COMPANY_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _RAD_ZONE_CORPS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _HALLOWED_MARTYRS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _ARMY_OF_FAITH_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _BRINGERS_OF_FLAME_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _WARPBANE_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _AUGURIUM_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _BROTHERHOOD_STRIKE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CABAL_OF_CHAOS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CHAOS_CULT_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CREATIONS_OF_BILE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _DECEPTORS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _DREAD_TALONS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _FELLHAMMER_SIEGE_HOST_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _HURONS_MARAUDERS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _VETERANS_OF_THE_LONG_WAR_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _RENEGADE_RAIDERS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _RENEGADE_WARBAND_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SOULFORGED_WARPACK_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _PACTBOUND_ZEALOTS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _NIGHTMARE_HUNT_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SLAANESHS_CHOSEN_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _COURT_OF_THE_PHOENICIAN_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CARNIVAL_OF_EXCESS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _COTERIE_OF_THE_CONCEITED_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _MERCURIAL_HOST_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _RAPID_EVISCERATION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _ARMOURED_WARHOST_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _ASPECT_HOST_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CORSAIR_COTERIE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SEER_COUNCIL_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SPIRIT_CONCLAVE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _WINDRIDER_HOST_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _GUARDIAN_BATTLEHOST_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _DEVOTED_OF_YNNEAD_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _GHOSTS_OF_THE_WEBWAY_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SERPENTS_BROOD_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _ELDRITCH_RAIDERS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _REAPERS_WAGER_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SKYSPLINTER_ASSAULT_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _EXPERIMENTAL_PROTOTYPE_CADRE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _MONTKA_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _AUXILIARY_CADRE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _KAUYON_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _INVASION_FLEET_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _ASSIMILATION_SWARM_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _VANGUARD_ONSLAUGHT_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SYNAPTIC_NEXUS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CRUSHER_STAMPEDE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _FIRST_COMPANY_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _EMPERORS_SHIELD_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _HAMMER_OF_AVERNII_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _IRONSTORM_SPEARHEAD_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _LIBERATOR_ASSAULT_GROUP_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _INNER_CIRCLE_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _LIBRARIUS_CONCLAVE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _ANVIL_SIEGE_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _BASTION_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _GLADIUS_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _BLADE_OF_ULTRAMAR_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CHAMPIONS_OF_FENRIS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _COMPANIONS_OF_VEHEMENCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _VANGUARD_SPEARHEAD_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SHADOWMARK_TALON_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SPEARPOINT_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _FIRESTORM_ASSAULT_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _FORGEFATHERS_SEEKERS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _GODHAMMER_ASSAULT_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _BLACK_SPEAR_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _COMPANY_OF_HUNTERS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _LIONS_BLADE_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _ORBITAL_ASSAULT_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _RECLAMATION_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _STORMLANCE_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _ANGELIC_INHERITORS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _THE_ANGELIC_HOST_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _THE_LOST_BRETHREN_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _UNFORGIVEN_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SAGA_OF_THE_BEASTSLAYER_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SAGA_OF_THE_BOLD_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SAGA_OF_THE_HUNTER_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SAGA_OF_THE_GREAT_WOLF_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _VINDICATION_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _WRATH_OF_THE_ROCK_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _WRATHFUL_PROCESSION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CHANGEHOST_OF_DECEIT_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _GRAND_COVEN_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _WARPFORGED_CABAL_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _HEXWARP_THRALLBAND_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _RUBRICAE_PHALANX_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _NEEDGAARD_OATHBAND_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _VALOURSTRIKE_LANCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _SPEARHEAD_AT_ARMS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _IMPERIALIS_FLEET_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _VEILED_BLADE_ELIMINATION_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _ANNIHILATION_LEGION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _AWAKENED_DYNASTY_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CURSED_LEGION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CRYPTEK_CONCLAVE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CANOPTEK_COURT_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _HYPERCRYPT_LEGION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _STARSHATTER_ARSENAL_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
    key = _normalize_name(name)
    if not key:
        return None
    return (
        _INFERNAL_LANCE_STRATAGEM_BY_NAME.get(key)
        or _DAEMONIC_INCURSION_STRATAGEM_BY_NAME.get(key)
        or _SCINTILLATING_LEGION_STRATAGEM_BY_NAME.get(key)
        or _BLOOD_LEGION_STRATAGEM_BY_NAME.get(key)
        or _PLAGUE_LEGION_STRATAGEM_BY_NAME.get(key)
        or _CHAMPIONS_OF_CONTAGION_STRATAGEM_BY_NAME.get(key)
        or _DEATH_LORDS_CHOSEN_STRATAGEM_BY_NAME.get(key)
        or _FLYBLOWN_HOST_STRATAGEM_BY_NAME.get(key)
        or _MORTARIONS_HAMMER_STRATAGEM_BY_NAME.get(key)
        or _SHAMBLEROT_VECTORIUM_STRATAGEM_BY_NAME.get(key)
        or _TALLYBAND_SUMMONERS_STRATAGEM_BY_NAME.get(key)
        or _SHADOW_LEGION_STRATAGEM_BY_NAME.get(key)
        or _LEGION_OF_EXCESS_STRATAGEM_BY_NAME.get(key)
        or _GORETRACK_ONSLAUGHT_STRATAGEM_BY_NAME.get(key)
        or _GREEN_TIDE_STRATAGEM_BY_NAME.get(key)
        or _ORKS_TEMP_BUFF_STRATAGEM_BY_NAME.get(key)
        or _POSSESSED_SLAUGHTERBAND_STRATAGEM_BY_NAME.get(key)
        or _HOST_OF_ASCENSION_STRATAGEM_BY_NAME.get(key)
        or _BROOD_BROTHER_AUXILIA_STRATAGEM_BY_NAME.get(key)
        or _VESSELS_OF_WRATH_STRATAGEM_BY_NAME.get(key)
        or _CULT_OF_BLOOD_STRATAGEM_BY_NAME.get(key)
        or _GRIZZLED_COMPANY_STRATAGEM_BY_NAME.get(key)
        or _RAD_ZONE_CORPS_STRATAGEM_BY_NAME.get(key)
        or _HALLOWED_MARTYRS_STRATAGEM_BY_NAME.get(key)
        or _ARMY_OF_FAITH_STRATAGEM_BY_NAME.get(key)
        or _BRINGERS_OF_FLAME_STRATAGEM_BY_NAME.get(key)
        or _WARPBANE_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _AUGURIUM_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _BROTHERHOOD_STRIKE_STRATAGEM_BY_NAME.get(key)
        or _CABAL_OF_CHAOS_STRATAGEM_BY_NAME.get(key)
        or _CHAOS_CULT_STRATAGEM_BY_NAME.get(key)
        or _CREATIONS_OF_BILE_STRATAGEM_BY_NAME.get(key)
        or _DECEPTORS_STRATAGEM_BY_NAME.get(key)
        or _DREAD_TALONS_STRATAGEM_BY_NAME.get(key)
        or _FELLHAMMER_SIEGE_HOST_STRATAGEM_BY_NAME.get(key)
        or _HURONS_MARAUDERS_STRATAGEM_BY_NAME.get(key)
        or _VETERANS_OF_THE_LONG_WAR_STRATAGEM_BY_NAME.get(key)
        or _RENEGADE_RAIDERS_STRATAGEM_BY_NAME.get(key)
        or _RENEGADE_WARBAND_STRATAGEM_BY_NAME.get(key)
        or _SOULFORGED_WARPACK_STRATAGEM_BY_NAME.get(key)
        or _PACTBOUND_ZEALOTS_STRATAGEM_BY_NAME.get(key)
        or _NIGHTMARE_HUNT_STRATAGEM_BY_NAME.get(key)
        or _SLAANESHS_CHOSEN_STRATAGEM_BY_NAME.get(key)
        or _COURT_OF_THE_PHOENICIAN_STRATAGEM_BY_NAME.get(key)
        or _CARNIVAL_OF_EXCESS_STRATAGEM_BY_NAME.get(key)
        or _COTERIE_OF_THE_CONCEITED_STRATAGEM_BY_NAME.get(key)
        or _MERCURIAL_HOST_STRATAGEM_BY_NAME.get(key)
        or _RAPID_EVISCERATION_STRATAGEM_BY_NAME.get(key)
        or _ARMOURED_WARHOST_STRATAGEM_BY_NAME.get(key)
        or _ASPECT_HOST_STRATAGEM_BY_NAME.get(key)
        or _CORSAIR_COTERIE_STRATAGEM_BY_NAME.get(key)
        or _SEER_COUNCIL_STRATAGEM_BY_NAME.get(key)
        or _SPIRIT_CONCLAVE_STRATAGEM_BY_NAME.get(key)
        or _WINDRIDER_HOST_STRATAGEM_BY_NAME.get(key)
        or _GUARDIAN_BATTLEHOST_STRATAGEM_BY_NAME.get(key)
        or _DEVOTED_OF_YNNEAD_STRATAGEM_BY_NAME.get(key)
        or _GHOSTS_OF_THE_WEBWAY_STRATAGEM_BY_NAME.get(key)
        or _SERPENTS_BROOD_STRATAGEM_BY_NAME.get(key)
        or _ELDRITCH_RAIDERS_STRATAGEM_BY_NAME.get(key)
        or _REAPERS_WAGER_STRATAGEM_BY_NAME.get(key)
        or _SKYSPLINTER_ASSAULT_STRATAGEM_BY_NAME.get(key)
        or _EXPERIMENTAL_PROTOTYPE_CADRE_STRATAGEM_BY_NAME.get(key)
        or _MONTKA_STRATAGEM_BY_NAME.get(key)
        or _AUXILIARY_CADRE_STRATAGEM_BY_NAME.get(key)
        or _KAUYON_STRATAGEM_BY_NAME.get(key)
        or _INVASION_FLEET_STRATAGEM_BY_NAME.get(key)
        or _ASSIMILATION_SWARM_STRATAGEM_BY_NAME.get(key)
        or _VANGUARD_ONSLAUGHT_STRATAGEM_BY_NAME.get(key)
        or _SYNAPTIC_NEXUS_STRATAGEM_BY_NAME.get(key)
        or _CRUSHER_STAMPEDE_STRATAGEM_BY_NAME.get(key)
        or _FIRST_COMPANY_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _EMPERORS_SHIELD_STRATAGEM_BY_NAME.get(key)
        or _HAMMER_OF_AVERNII_STRATAGEM_BY_NAME.get(key)
        or _IRONSTORM_SPEARHEAD_STRATAGEM_BY_NAME.get(key)
        or _LIBERATOR_ASSAULT_GROUP_STRATAGEM_BY_NAME.get(key)
        or _INNER_CIRCLE_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _LIBRARIUS_CONCLAVE_STRATAGEM_BY_NAME.get(key)
        or _ANVIL_SIEGE_FORCE_STRATAGEM_BY_NAME.get(key)
        or _BASTION_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _GLADIUS_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _BLADE_OF_ULTRAMAR_STRATAGEM_BY_NAME.get(key)
        or _CHAMPIONS_OF_FENRIS_STRATAGEM_BY_NAME.get(key)
        or _COMPANIONS_OF_VEHEMENCE_STRATAGEM_BY_NAME.get(key)
        or _VANGUARD_SPEARHEAD_STRATAGEM_BY_NAME.get(key)
        or _SHADOWMARK_TALON_STRATAGEM_BY_NAME.get(key)
        or _SPEARPOINT_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _FIRESTORM_ASSAULT_FORCE_STRATAGEM_BY_NAME.get(key)
        or _FORGEFATHERS_SEEKERS_STRATAGEM_BY_NAME.get(key)
        or _GODHAMMER_ASSAULT_FORCE_STRATAGEM_BY_NAME.get(key)
        or _BLACK_SPEAR_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _COMPANY_OF_HUNTERS_STRATAGEM_BY_NAME.get(key)
        or _LIONS_BLADE_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _ORBITAL_ASSAULT_FORCE_STRATAGEM_BY_NAME.get(key)
        or _RECLAMATION_FORCE_STRATAGEM_BY_NAME.get(key)
        or _STORMLANCE_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _ANGELIC_INHERITORS_STRATAGEM_BY_NAME.get(key)
        or _THE_ANGELIC_HOST_STRATAGEM_BY_NAME.get(key)
        or _THE_LOST_BRETHREN_STRATAGEM_BY_NAME.get(key)
        or _UNFORGIVEN_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _SAGA_OF_THE_BEASTSLAYER_STRATAGEM_BY_NAME.get(key)
        or _SAGA_OF_THE_BOLD_STRATAGEM_BY_NAME.get(key)
        or _SAGA_OF_THE_HUNTER_STRATAGEM_BY_NAME.get(key)
        or _SAGA_OF_THE_GREAT_WOLF_STRATAGEM_BY_NAME.get(key)
        or _VINDICATION_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _WRATH_OF_THE_ROCK_STRATAGEM_BY_NAME.get(key)
        or _WRATHFUL_PROCESSION_STRATAGEM_BY_NAME.get(key)
        or _CHANGEHOST_OF_DECEIT_STRATAGEM_BY_NAME.get(key)
        or _GRAND_COVEN_STRATAGEM_BY_NAME.get(key)
        or _WARPFORGED_CABAL_STRATAGEM_BY_NAME.get(key)
        or _HEXWARP_THRALLBAND_STRATAGEM_BY_NAME.get(key)
        or _WARPMELD_PACT_STRATAGEM_BY_NAME.get(key)
        or _RUBRICAE_PHALANX_STRATAGEM_BY_NAME.get(key)
        or _NEEDGAARD_OATHBAND_STRATAGEM_BY_NAME.get(key)
        or _VALOURSTRIKE_LANCE_STRATAGEM_BY_NAME.get(key)
        or _SPEARHEAD_AT_ARMS_STRATAGEM_BY_NAME.get(key)
        or _IMPERIALIS_FLEET_STRATAGEM_BY_NAME.get(key)
        or _VEILED_BLADE_ELIMINATION_FORCE_STRATAGEM_BY_NAME.get(key)
        or _ANNIHILATION_LEGION_STRATAGEM_BY_NAME.get(key)
        or _AWAKENED_DYNASTY_STRATAGEM_BY_NAME.get(key)
        or _CURSED_LEGION_STRATAGEM_BY_NAME.get(key)
        or _CRYPTEK_CONCLAVE_STRATAGEM_BY_NAME.get(key)
        or _CANOPTEK_COURT_STRATAGEM_BY_NAME.get(key)
        or _HYPERCRYPT_LEGION_STRATAGEM_BY_NAME.get(key)
        or _STARSHATTER_ARSENAL_STRATAGEM_BY_NAME.get(key)
    )
