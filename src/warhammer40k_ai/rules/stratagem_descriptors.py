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
        desc = _SHADOW_LEGION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _LEGION_OF_EXCESS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _GORETRACK_ONSLAUGHT_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _POSSESSED_SLAUGHTERBAND_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _HOST_OF_ASCENSION_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
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
        desc = _WARPBANE_TASK_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _CABAL_OF_CHAOS_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
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
        desc = _EXPERIMENTAL_PROTOTYPE_CADRE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _MONTKA_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
        if desc is not None:
            return desc
        desc = _INVASION_FLEET_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
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
        desc = _VEILED_BLADE_ELIMINATION_FORCE_STRATAGEM_DESCRIPTORS.get(str(stratagem_id))
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
        or _SHADOW_LEGION_STRATAGEM_BY_NAME.get(key)
        or _LEGION_OF_EXCESS_STRATAGEM_BY_NAME.get(key)
        or _GORETRACK_ONSLAUGHT_STRATAGEM_BY_NAME.get(key)
        or _POSSESSED_SLAUGHTERBAND_STRATAGEM_BY_NAME.get(key)
        or _HOST_OF_ASCENSION_STRATAGEM_BY_NAME.get(key)
        or _VESSELS_OF_WRATH_STRATAGEM_BY_NAME.get(key)
        or _CULT_OF_BLOOD_STRATAGEM_BY_NAME.get(key)
        or _GRIZZLED_COMPANY_STRATAGEM_BY_NAME.get(key)
        or _RAD_ZONE_CORPS_STRATAGEM_BY_NAME.get(key)
        or _HALLOWED_MARTYRS_STRATAGEM_BY_NAME.get(key)
        or _WARPBANE_TASK_FORCE_STRATAGEM_BY_NAME.get(key)
        or _CABAL_OF_CHAOS_STRATAGEM_BY_NAME.get(key)
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
        or _EXPERIMENTAL_PROTOTYPE_CADRE_STRATAGEM_BY_NAME.get(key)
        or _MONTKA_STRATAGEM_BY_NAME.get(key)
        or _INVASION_FLEET_STRATAGEM_BY_NAME.get(key)
        or _RUBRICAE_PHALANX_STRATAGEM_BY_NAME.get(key)
        or _NEEDGAARD_OATHBAND_STRATAGEM_BY_NAME.get(key)
        or _VALOURSTRIKE_LANCE_STRATAGEM_BY_NAME.get(key)
        or _VEILED_BLADE_ELIMINATION_FORCE_STRATAGEM_BY_NAME.get(key)
    )
