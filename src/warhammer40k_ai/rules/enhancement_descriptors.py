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

_CULT_OF_BLOOD_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010074002": EnhancementToolDescriptor(
        enhancement_id="000010074002",
        name="Chosen of the Blood God",
        timing="passive_aura",
        target="bearer",
        duration="constant",
        effect="bearer_aura_range_bonus",
        effect_params={"aura_range_bonus": 3},
    ),
    "000010074003": EnhancementToolDescriptor(
        enhancement_id="000010074003",
        name="Butcher Lord",
        timing="declare_battle_formations",
        target="bearer",
        duration="battle_setup",
        effect="attach_to_jakhals_or_goremongers_and_goremongers_infiltrators",
    ),
    "000010074004": EnhancementToolDescriptor(
        enhancement_id="000010074004",
        name="Brazen Form",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_toughness_and_fnp_bonus",
        effect_params={"toughness_bonus": 1, "fnp": 5},
    ),
    "000010074005": EnhancementToolDescriptor(
        enhancement_id="000010074005",
        name="Strategic Slaughter",
        timing="after_deployment",
        target="friendly_jakhals_or_goremongers_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={"max_units": 3, "allow_strategic_reserves": True},
    ),
}

_CULT_OF_BLOOD_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CULT_OF_BLOOD_DESCRIPTORS.values()
}

_GRIZZLED_COMPANY_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010637002": EnhancementToolDescriptor(
        enhancement_id="000010637002",
        name="Abhuman Detail",
        timing="declare_battle_formations",
        target="bearer",
        duration="battle_setup_and_order_targeting",
        effect="add_ogryn_order_targeting_and_attachment_override",
        effect_params={
            "order_target_keyword_add": ("OGRYN",),
            "attachment_override_unit_keywords_any": ("OGRYN",),
            "attachment_override_unit_names_any": ("Ogryn Squad", "Bullgryn Squad"),
        },
    ),
    "000010637003": EnhancementToolDescriptor(
        enhancement_id="000010637003",
        name="Aquilan Eye",
        timing="when_selecting_order",
        target="bearer",
        duration="constant",
        effect="grant_extra_order_option_target_weak_spot",
        effect_params={
            "extra_order_key": "TARGET_WEAK_SPOT",
            "extra_order_attack_type": "ranged",
            "extra_order_ap_bonus": 1,
            "extra_order_range": 12.0,
        },
    ),
    "000010637004": EnhancementToolDescriptor(
        enhancement_id="000010637004",
        name="Spec Ops Veteran",
        timing="when_selecting_order",
        target="bearer",
        duration="constant",
        effect="grant_extra_order_option_move_to_shadows",
        effect_params={
            "extra_order_key": "MOVE_TO_SHADOWS",
            "extra_order_defensive_attack_type": "ranged",
            "extra_order_grants": ("STEALTH",),
        },
    ),
    "000010637005": EnhancementToolDescriptor(
        enhancement_id="000010637005",
        name="Laud Hailer",
        timing="when_issuing_order",
        target="bearer",
        duration="constant",
        effect="increase_order_range",
        effect_params={"order_range": 12.0},
    ),
}

_GRIZZLED_COMPANY_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GRIZZLED_COMPANY_DESCRIPTORS.values()
}

_BRIDGEHEAD_STRIKE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009801002": EnhancementToolDescriptor(
        enhancement_id="000009801002",
        name="Bombast-class Vox-array",
        timing="when_issuing_order",
        target="bearer_unit_with_master_vox",
        duration="constant",
        effect="issue_same_order_to_up_to_three_regiment_units_if_master_vox",
        effect_params={
            "max_order_targets": 3,
            "order_target_keyword": "REGIMENT",
            "requires_master_vox": True,
        },
    ),
    "000009801003": EnhancementToolDescriptor(
        enhancement_id="000009801003",
        name="Priority-drop Beacon",
        timing="movement_phase_while_in_strategic_reserves",
        target="bearer_unit_in_strategic_reserves",
        duration="constant_while_in_strategic_reserves",
        effect="strategic_reserves_setup_round_bonus_for_deep_strike",
        effect_params={
            "strategic_reserves_setup_round_bonus": 1,
            "requires_deep_strike": True,
        },
    ),
    "000009801004": EnhancementToolDescriptor(
        enhancement_id="000009801004",
        name="Shroud Projector",
        timing="overwatch_targeting",
        target="enemy_units_targeting_bearer_unit_with_fire_overwatch",
        duration="constant_while_bearer_alive",
        effect="prevent_fire_overwatch_against_bearer_unit",
        effect_params={"requires_bearer_alive": True},
    ),
    "000009801005": EnhancementToolDescriptor(
        enhancement_id="000009801005",
        name="Advance Augury",
        timing="after_deployment",
        target="friendly_regiment_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "allow_strategic_reserves": True,
            "redeploy_filters": ("REGIMENT",),
        },
    ),
}

_BRIDGEHEAD_STRIKE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _BRIDGEHEAD_STRIKE_DESCRIPTORS.values()
}

_COMBINED_ARMS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008380002": EnhancementToolDescriptor(
        enhancement_id="000008380002",
        name="Death Mask of Ollanius",
        timing="passive_while_battle_shocked",
        target="bearer_unit",
        duration="while_bearer_alive_and_unit_battle_shocked",
        effect="battleshock_objective_control_subtract_instead_of_zero",
        effect_params={"objective_control_penalty": 1},
    ),
    "000008380003": EnhancementToolDescriptor(
        enhancement_id="000008380003",
        name="Drill Commander",
        timing="passive_while_leading",
        target="bearer_led_unit",
        duration="while_bearer_alive_and_unit_remained_stationary_this_turn",
        effect="ranged_critical_hits_on_5plus",
        effect_params={
            "attack_type": "ranged",
            "critical_hit_threshold": 5,
            "requires_remained_stationary": True,
        },
    ),
    "000008380004": EnhancementToolDescriptor(
        enhancement_id="000008380004",
        name="Grand Strategist",
        timing="command_phase",
        target="bearer",
        duration="constant",
        effect="additional_orders",
        effect_params={"additional_orders": 1},
    ),
    "000008380005": EnhancementToolDescriptor(
        enhancement_id="000008380005",
        name="Reactive Command",
        timing="on_enemy_unit_set_up_within_range",
        target="bearer",
        duration="triggered",
        effect="issue_order_without_consuming_order_count",
        range_in=9.0,
        effect_params={
            "trigger_range": 9.0,
            "additional_orders_per_trigger": 1,
            "does_not_count_towards_order_limit": True,
        },
    ),
}

_COMBINED_ARMS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _COMBINED_ARMS_DESCRIPTORS.values()
}

_HAMMER_OF_THE_EMPEROR_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009865002": EnhancementToolDescriptor(
        enhancement_id="000009865002",
        name="Calm Under Fire",
        timing="after_issuing_order",
        target="bearer",
        duration="once_per_turn",
        effect="issue_same_order_once_per_turn_to_additional_squadron_unit",
        effect_params={
            "additional_targets": 1,
            "order_target_keyword": "SQUADRON",
            "once_per_turn": True,
        },
    ),
    "000009865003": EnhancementToolDescriptor(
        enhancement_id="000009865003",
        name="Indomitable Steed",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_feel_no_pain",
        effect_params={"feel_no_pain": 6},
    ),
    "000009865004": EnhancementToolDescriptor(
        enhancement_id="000009865004",
        name="Regimental Banner",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_objective_control_bonus",
        effect_params={"objective_control_bonus": 3},
    ),
    "000009865005": EnhancementToolDescriptor(
        enhancement_id="000009865005",
        name="Veteran Crew",
        timing="on_attack_roll",
        target="bearer_unit_ranged_attacks",
        duration="constant",
        effect="ranged_reroll_hit_ones",
        effect_params={"reroll_hit_values": (1,), "attack_type": "ranged"},
    ),
}

_HAMMER_OF_THE_EMPEROR_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _HAMMER_OF_THE_EMPEROR_DESCRIPTORS.values()
}

_MECHANISED_ASSAULT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009861002": EnhancementToolDescriptor(
        enhancement_id="000009861002",
        name="Bold Leadership",
        timing="end_of_command_phase",
        target="controlled_objective_markers_within_bearer_unit_or_embarked_transport",
        duration="until_opponent_controls_at_start_or_end_of_turn",
        effect="sticky_objective_control",
        effect_params={
            "allow_embarked_transport": True,
            "source_scope": "unit",
            "sticky_source": "unit_sticky_objective",
        },
    ),
    "000009861003": EnhancementToolDescriptor(
        enhancement_id="000009861003",
        name="Sacred Unguents",
        timing="start_of_shooting_phase",
        target="friendly_transport_within_range",
        duration="until_end_of_phase",
        effect="selected_transport_reroll_hit",
        range_in=3.0,
        effect_params={
            "target_keywords_all": ("TRANSPORT",),
            "exclude_target_keywords_any": ("AIRCRAFT", "TITANIC"),
            "reroll_hit": "full",
            "requires_bearer_alive": True,
        },
    ),
    "000009861004": EnhancementToolDescriptor(
        enhancement_id="000009861004",
        name="Smoke Grenades",
        timing="passive_while_wholly_within_range_of_transport",
        target="bearer_unit",
        duration="conditional",
        effect="benefit_of_cover_and_stealth",
        range_in=3.0,
        effect_params={
            "require_friendly_transport": True,
            "require_wholly_within": True,
            "grants_benefit_of_cover": True,
            "grants_stealth": True,
        },
    ),
    "000009861005": EnhancementToolDescriptor(
        enhancement_id="000009861005",
        name="Vanguard Honours",
        timing="on_disembark_after_transport_advance",
        target="bearer_unit",
        duration="that_phase_and_turn",
        effect="allow_disembark_after_advance_counts_as_normal_move_no_charge",
        effect_params={
            "allow_after_advance": True,
            "force_cannot_charge_this_turn": True,
        },
    ),
}

_MECHANISED_ASSAULT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _MECHANISED_ASSAULT_DESCRIPTORS.values()
}

_RECON_ELEMENT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009869002": EnhancementToolDescriptor(
        enhancement_id="000009869002",
        name="Guerrilla Honours",
        timing="after_deployment",
        target="other_friendly_astra_militarum_infantry_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "allow_strategic_reserves": True,
            "redeploy_filters": ("ASTRA MILITARUM", "INFANTRY"),
            "exclude_source_unit": True,
        },
    ),
    "000009869003": EnhancementToolDescriptor(
        enhancement_id="000009869003",
        name="Scare Gas Grenades",
        timing="start_of_any_phase",
        target="enemy_unit_within_range_excluding_monster_vehicle",
        duration="instant",
        effect="enemy_battleshock_test",
        range_in=8.0,
        once_per_battle=True,
        effect_params={
            "exclude_target_keywords_any": ("MONSTER", "VEHICLE"),
            "ability_key": "scare_gas_grenades",
        },
    ),
    "000009869004": EnhancementToolDescriptor(
        enhancement_id="000009869004",
        name="Survival Gear",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="grant_scouts",
        effect_params={
            "scouts_distance": 6.0,
            "applies_to_bearer_only": True,
        },
    ),
    "000009869005": EnhancementToolDescriptor(
        enhancement_id="000009869005",
        name="Tripwires",
        timing="on_enemy_move_end_within_range",
        target="enemy_infantry_or_mounted_unit",
        duration="until_start_of_next_owner_turn_on_success",
        effect="stun_on_roll",
        range_in=9.0,
        effect_params={
            "trigger_actions": ("move", "advance", "charge", "fall_back"),
            "target_keywords_any": ("INFANTRY", "MOUNTED"),
            "roll": "D6",
            "success_on": 4,
            "hit_roll_modifier": -1,
        },
    ),
}

_RECON_ELEMENT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RECON_ELEMENT_DESCRIPTORS.values()
}

_SIEGE_REGIMENT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009857002": EnhancementToolDescriptor(
        enhancement_id="000009857002",
        name="Eager Advance",
        timing="passive_while_leading",
        target="bearer_led_regiment_unit",
        duration="while_bearer_alive",
        effect="grant_scouts",
        effect_params={
            "scouts_distance": 6.0,
            "requires_leading": True,
            "target_keyword": "REGIMENT",
        },
    ),
    "000009857003": EnhancementToolDescriptor(
        enhancement_id="000009857003",
        name="Flash Grenades",
        timing="overwatch_targeting",
        target="enemy_units_targeting_bearer_unit_with_fire_overwatch",
        duration="constant_while_bearer_alive",
        effect="prevent_fire_overwatch_against_bearer_unit",
        effect_params={"requires_bearer_alive": True},
    ),
    "000009857004": EnhancementToolDescriptor(
        enhancement_id="000009857004",
        name="Legacy Sidearm",
        timing="passive_on_attack_characteristic",
        target="bearer_pistols",
        duration="constant",
        effect="add_pistol_attacks",
        effect_params={
            "attacks_bonus": 2,
            "weapon_keyword": "PISTOL",
            "bearer_only": True,
        },
    ),
    "000009857005": EnhancementToolDescriptor(
        enhancement_id="000009857005",
        name="Stalwart's Honours",
        timing="when_issued_order_while_leading",
        target="bearer_led_unit",
        duration="order_duration",
        effect="also_apply_take_cover_order",
        effect_params={
            "requires_leading": True,
            "additional_order_key": "TAKE_COVER",
        },
    ),
}

_SIEGE_REGIMENT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SIEGE_REGIMENT_DESCRIPTORS.values()
}

_POSSESSED_SLAUGHTERBAND_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010082002": EnhancementToolDescriptor(
        enhancement_id="000010082002",
        name="Malicious Vigour",
        timing="on_brazen_fury_move",
        target="bearer_unit",
        duration="constant",
        effect="set_brazen_fury_distance",
        effect_params={"distance": 6},
    ),
    "000010082003": EnhancementToolDescriptor(
        enhancement_id="000010082003",
        name="Killing Clarity",
        timing="on_enemy_unit_destroyed",
        target="bearer_unit",
        duration="instant",
        effect="cp_gain_on_kill_roll",
        effect_params={"cp": 1, "roll": "D6", "success_on": 4},
    ),
    "000010082004": EnhancementToolDescriptor(
        enhancement_id="000010082004",
        name="Frenzied Focus",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="critical_hit_threshold_bonus",
        effect_params={"crit_hit_threshold": 5},
    ),
    "000010082005": EnhancementToolDescriptor(
        enhancement_id="000010082005",
        name="Violent Demise",
        timing="on_bearer_destroyed",
        target="bearer",
        duration="instant",
        effect="deadly_demise_trigger_and_damage_bonus",
        effect_params={"trigger_roll": "D6", "success_on": 2, "damage": "D3+1"},
    ),
}

_POSSESSED_SLAUGHTERBAND_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _POSSESSED_SLAUGHTERBAND_DESCRIPTORS.values()
}

_VESSELS_OF_WRATH_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009847002": EnhancementToolDescriptor(
        enhancement_id="000009847002",
        name="Archslaughterer",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant_conditional",
        effect="bearer_melee_ap_and_vessel_damage_bonus",
        effect_params={"ap_bonus": 1, "vessel_of_wrath_damage_bonus": 1},
    ),
    "000009847003": EnhancementToolDescriptor(
        enhancement_id="000009847003",
        name="Vox-diabolus",
        timing="on_enemy_unit_destroyed_by_melee",
        target="bearer_unit",
        duration="instant",
        effect="cp_gain_on_melee_kill_roll",
        effect_params={"cp": 1, "roll": "D6", "success_on": 4, "vessel_of_wrath_roll_bonus": 1},
    ),
    "000009847004": EnhancementToolDescriptor(
        enhancement_id="000009847004",
        name="Avenger's Crown",
        timing="on_bearer_destroyed_by_melee",
        target="bearer",
        duration="instant",
        effect="melee_fight_on_death_after_attacks",
        effect_params={"roll": "D6", "success_on": 2},
    ),
    "000009847005": EnhancementToolDescriptor(
        enhancement_id="000009847005",
        name="Gateways to Glory",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="move_through_models_and_terrain",
        effect_params={
            "move_types": ("move", "advance", "charge"),
            "horizontal_only": True,
            "cannot_end_engagement_on": ("move", "advance"),
        },
    ),
}

_VESSELS_OF_WRATH_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _VESSELS_OF_WRATH_DESCRIPTORS.values()
}

_ADEPTA_SORORITAS_ARMY_OF_FAITH_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009037002": EnhancementToolDescriptor(
        enhancement_id="000009037002",
        name="Litanies of Faith",
        timing="start_of_command_phase",
        target="bearer",
        duration="instant",
        effect="leadership_test_gain_miracle_die",
    ),
    "000009037003": EnhancementToolDescriptor(
        enhancement_id="000009037003",
        name="Blade of Saint Ellynor",
        timing="passive_and_on_enemy_model_destroyed",
        target="bearer_melee_weapons",
        duration="constant_and_per_fight_activation",
        effect="bearer_melee_stats_precision_and_miracle_die_on_melee_kill",
        effect_params={"strength_bonus": 1, "ap_bonus": 1, "precision": True},
    ),
    "000009037004": EnhancementToolDescriptor(
        enhancement_id="000009037004",
        name="Divine Aspect",
        timing="start_of_movement_phase",
        target="enemy_unit_within_range_of_bearer",
        duration="instant",
        effect="force_battle_shock_and_gain_miracle_die_on_failure",
        range_in=12.0,
    ),
    "000009037005": EnhancementToolDescriptor(
        enhancement_id="000009037005",
        name="Triptych of the Macharian Crusade",
        timing="on_bearer_save_act_of_faith",
        target="bearer",
        duration="instant",
        effect="auto_pass_bearer_save_when_miracle_die_substituted",
    ),
}

_ADEPTA_SORORITAS_ARMY_OF_FAITH_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ADEPTA_SORORITAS_ARMY_OF_FAITH_DESCRIPTORS.values()
}

_ADEPTA_SORORITAS_BRINGERS_OF_FLAME_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009033002": EnhancementToolDescriptor(
        enhancement_id="000009033002",
        name="Righteous Rage",
        timing="on_bearer_selected_to_fight",
        target="bearer",
        duration="until_end_of_phase",
        effect="discard_miracle_dice_for_bearer_melee_attacks_strength_bonus",
        effect_params={"max_discard_miracle_dice": 3, "melee_attacks_strength_bonus_per_discard": 1},
    ),
    "000009033003": EnhancementToolDescriptor(
        enhancement_id="000009033003",
        name="Manual of Saint Griselda",
        timing="start_of_command_phase",
        target="miracle_dice_pool",
        duration="instant",
        effect="discard_up_to_two_miracle_dice_add_sum_capped_die",
        effect_params={"max_discard_miracle_dice": 2, "result_value_max": 6},
    ),
    "000009033004": EnhancementToolDescriptor(
        enhancement_id="000009033004",
        name="Fire and Fury",
        timing="passive_while_leading",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="torrent_attacks_bonus_and_other_ranged_sustained_hits",
        effect_params={"requires_bearer_leading": True, "torrent_attacks_bonus": 1, "other_ranged_sustained_hits": 1},
    ),
    "000009033005": EnhancementToolDescriptor(
        enhancement_id="000009033005",
        name="Iron Surplice of Saint Istalela",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_save_set_and_fnp",
        effect_params={"save_characteristic": 2, "feel_no_pain": 5},
    ),
}

_ADEPTA_SORORITAS_BRINGERS_OF_FLAME_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ADEPTA_SORORITAS_BRINGERS_OF_FLAME_DESCRIPTORS.values()
}

_ADEPTA_SORORITAS_CHAMPIONS_OF_FAITH_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009831002": EnhancementToolDescriptor(
        enhancement_id="000009831002",
        name="Triptych of Judgement",
        timing="passive",
        target="bearer_unit_attacks",
        duration="constant",
        effect="bearer_unit_ignore_hit_and_skill_modifiers",
        effect_params={
            "ignore_hit_roll_modifiers": True,
            "ignore_ballistic_skill_modifiers": True,
            "ignore_weapon_skill_modifiers": True,
        },
    ),
    "000009831003": EnhancementToolDescriptor(
        enhancement_id="000009831003",
        name="Mark of Devotion",
        timing="passive_and_conditional_while_unit_righteous",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_attacks_bonus_with_righteous_upgrade",
        effect_params={
            "melee_attacks_bonus": 1,
            "melee_attacks_bonus_if_righteous": 2,
            "melee_damage_bonus_if_righteous": 1,
        },
    ),
    "000009831004": EnhancementToolDescriptor(
        enhancement_id="000009831004",
        name="Eyes of the Oracle",
        timing="passive_and_on_enemy_character_model_destroyed_by_bearer_unit",
        target="bearer_weapons_and_command_points",
        duration="constant",
        effect="bearer_weapons_precision_and_gain_cp_on_character_model_destroyed_by_bearer_unit",
        effect_params={
            "keywords": ("PRECISION",),
            "cp_gain": 1,
            "target_keywords_any": ("CHARACTER",),
        },
    ),
    "000009831005": EnhancementToolDescriptor(
        enhancement_id="000009831005",
        name="Sanctified Amulet",
        timing="passive_aura",
        target="enemy_reserves_arrival",
        duration="constant",
        effect="enemy_reserves_arrival_min_distance_from_bearer",
        effect_params={
            "min_enemy_distance": 12,
            "horizontal_only": False,
        },
    ),
}

_ADEPTA_SORORITAS_CHAMPIONS_OF_FAITH_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ADEPTA_SORORITAS_CHAMPIONS_OF_FAITH_DESCRIPTORS.values()
}

_ADEPTA_SORORITAS_PENITENT_HOST_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009029002": EnhancementToolDescriptor(
        enhancement_id="000009029002",
        name="Psalm of Righteous Judgement",
        timing="on_enemy_unit_destroyed_by_friendly_penitent_unit",
        target="miracle_dice_pool",
        duration="instant",
        effect="discard_miracle_die_then_gain_fixed_miracle_die_value",
        effect_params={
            "discard_miracle_dice": 1,
            "gained_miracle_die_value": 6,
            "requires_source_unit_keyword": "PENITENT",
        },
    ),
    "000009029003": EnhancementToolDescriptor(
        enhancement_id="000009029003",
        name="Verse of Holy Piety",
        timing="start_of_battle_round_once_per_battle",
        target="bearer_unit",
        duration="battle_round",
        effect="select_additional_vow_of_atonement_for_bearer_unit",
        once_per_battle=True,
        effect_params={
            "optional": True,
            "vow_keys": (
                "path_of_the_penitent",
                "absolution_in_battle",
                "death_before_disgrace",
            ),
        },
    ),
    "000009029004": EnhancementToolDescriptor(
        enhancement_id="000009029004",
        name="Refrain of Enduring Faith",
        timing="passive_while_leading",
        target="bearer_led_unit",
        duration="constant",
        effect="bearer_led_unit_invulnerable_save",
        effect_params={
            "invulnerable_save": 5,
            "requires_bearer_leading": True,
        },
    ),
    "000009029005": EnhancementToolDescriptor(
        enhancement_id="000009029005",
        name="Catechism of Divine Penitence",
        timing="passive_and_declare_battle_formations_attachment_override",
        target="bearer",
        duration="constant",
        effect="grant_bearer_keyword_and_attachment_override",
        effect_params={
            "add_keywords": ("PENITENT",),
            "attachment_override_unit_names_any": ("Repentia Squad",),
        },
    ),
}

_ADEPTA_SORORITAS_PENITENT_HOST_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ADEPTA_SORORITAS_PENITENT_HOST_DESCRIPTORS.values()
}

_AELDARI_GUARDIAN_BATTLEHOST_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009911002": EnhancementToolDescriptor(
        enhancement_id="000009911002",
        name="Craftworld's Champion",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_objective_control_set",
        effect_params={"objective_control": 5},
    ),
    "000009911003": EnhancementToolDescriptor(
        enhancement_id="000009911003",
        name="Ethereal Pathway",
        timing="deploy_armies_step_start",
        target="friendly_guardians_units",
        duration="during_deployment",
        effect="grant_infiltrators_to_selected_units",
        effect_params={"max_units": 2, "keyword": "GUARDIANS", "optional": True},
    ),
    "000009911004": EnhancementToolDescriptor(
        enhancement_id="000009911004",
        name="Protector of the Paths",
        timing="overwatch_targeting",
        target="bearer_unit",
        duration="battle_round",
        effect="overwatch_zero_cp_and_hit_threshold_bonus_while_leading",
        effect_params={
            "base_overwatch_hit_threshold": 5,
            "controlled_objective_hit_threshold": 4,
            "limit": "battle_round",
            "required_bodyguard_keywords": ("DIRE AVENGERS", "GUARDIANS"),
        },
    ),
    "000009911005": EnhancementToolDescriptor(
        enhancement_id="000009911005",
        name="Breath of Vaul",
        timing="passive_while_leading",
        target="bearer_unit",
        duration="constant",
        effect="flamer_attack_count_and_fusion_damage_rerolls",
        effect_params={
            "required_bodyguard_keyword": "STORM GUARDIANS",
            "flamer_weapon_names": ("flamer",),
            "fusion_weapon_names": ("fusion gun",),
        },
    ),
}

_AELDARI_GUARDIAN_BATTLEHOST_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AELDARI_GUARDIAN_BATTLEHOST_DESCRIPTORS.values()
}

_AELDARI_SEER_COUNCIL_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009923002": EnhancementToolDescriptor(
        enhancement_id="000009923002",
        name="Lucid Eye",
        timing="start_of_command_phase",
        target="seer_council_fate_pool_die",
        duration="instant",
        effect="adjust_fate_die_value",
        effect_params={
            "delta_choices": (-1, 1),
            "min_value": 1,
            "max_value": 6,
            "optional": True,
        },
    ),
    "000009923003": EnhancementToolDescriptor(
        enhancement_id="000009923003",
        name="Runes of Warding",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_fnp_conditional",
        effect_params={
            "fnp": 4,
            "conditions": (
                "against mortal wounds",
                "against psychic attacks",
                "against attacks made as the result of a critical wound where the attacking weapon had devastating wounds",
            ),
        },
    ),
    "000009923004": EnhancementToolDescriptor(
        enhancement_id="000009923004",
        name="Stone of Eldritch Fury",
        timing="passive",
        target="bearer_ranged_psychic_weapons",
        duration="constant",
        effect="bearer_psychic_ranged_range_bonus",
        effect_params={"range_bonus": 12},
    ),
    "000009923005": EnhancementToolDescriptor(
        enhancement_id="000009923005",
        name="Torc of Morai-Heg",
        timing="opponent_stratagem_targeting",
        target="enemy_unit_within_range_of_bearer",
        duration="constant",
        effect="targeted_stratagem_cp_increase",
        range_in=12.0,
        effect_params={"cp_increase": 1, "limit": "turn", "max_per_stratagem_use": 1},
    ),
}

_AELDARI_SEER_COUNCIL_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AELDARI_SEER_COUNCIL_DESCRIPTORS.values()
}

_AELDARI_CORSAIR_COTERIE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010704002": EnhancementToolDescriptor(
        enhancement_id="000010704002",
        name="Infamy (Aura)",
        timing="passive_aura",
        target="enemy_units_within_range_of_bearer_unit",
        duration="constant",
        effect="enemy_objective_control_penalty_minimum",
        range_in=3.0,
        effect_params={"objective_control_penalty": 1, "objective_control_minimum": 1},
    ),
    "000010704003": EnhancementToolDescriptor(
        enhancement_id="000010704003",
        name="Webway Pathstone",
        timing="passive_and_end_of_opponent_turn",
        target="bearer_unit",
        duration="constant_and_once_per_battle",
        effect="grant_deep_strike_and_enter_strategic_reserves",
        once_per_battle=True,
        effect_params={
            "grants_deep_strike": True,
            "enter_strategic_reserves_timing": "end_of_opponent_turn",
            "requires_not_engagement_range": True,
        },
    ),
    "000010704004": EnhancementToolDescriptor(
        enhancement_id="000010704004",
        name="Archraider",
        timing="opponent_stratagem_targeting",
        target="enemy_unit_within_range_of_selected_character_model",
        duration="constant",
        effect="targeted_stratagem_cp_increase",
        range_in=12.0,
        effect_params={"cp_increase": 1, "select_character_model_start_of_battle": True},
    ),
    "000010704005": EnhancementToolDescriptor(
        enhancement_id="000010704005",
        name="Voidstone",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_invulnerable_save",
        effect_params={"invulnerable_save": 5},
    ),
}

_AELDARI_CORSAIR_COTERIE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AELDARI_CORSAIR_COTERIE_DESCRIPTORS.values()
}

_AELDARI_ELDRITCH_RAIDERS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010699002": EnhancementToolDescriptor(
        enhancement_id="000010699002",
        name="Pirate Prince",
        timing="on_battle_focus_token_spend",
        target="bearer_unit_while_bearer_is_leading",
        duration="instant",
        effect="battle_focus_token_refund_on_agile_maneuver_spend",
        effect_params={"refund_roll_threshold": 3, "refund_tokens": 1},
    ),
    "000010699003": EnhancementToolDescriptor(
        enhancement_id="000010699003",
        name="Alacritous Assault",
        timing="passive",
        target="bearer_unit_melee_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={"attack_type": "melee", "keywords": ("LANCE",)},
    ),
    "000010699004": EnhancementToolDescriptor(
        enhancement_id="000010699004",
        name="Exotic Munitions",
        timing="passive",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={"attack_type": "ranged", "keywords": ("ANTI-MONSTER 5+", "ANTI-VEHICLE 5+")},
    ),
    "000010699005": EnhancementToolDescriptor(
        enhancement_id="000010699005",
        name="Adrenal Infusions",
        timing="reactive_battle_focus_fade_back",
        target="bearer_unit",
        duration="constant",
        effect="grant_fade_back_without_battle_focus_token",
        effect_params={
            "free_fade_back": True,
            "ignore_phase_fade_back_limit": True,
            "does_not_consume_phase_fade_back_limit": True,
        },
    ),
}

_AELDARI_ELDRITCH_RAIDERS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AELDARI_ELDRITCH_RAIDERS_DESCRIPTORS.values()
}

_AELDARI_WINDRIDER_HOST_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009903002": EnhancementToolDescriptor(
        enhancement_id="000009903002",
        name="Firstdrawn Blade",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_scouts_to_bearer_unit",
        effect_params={"scouts_distance": 9},
    ),
    "000009903003": EnhancementToolDescriptor(
        enhancement_id="000009903003",
        name="Mirage Field",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_target_hit_penalty",
        effect_params={"attack_type": "any", "hit_penalty": 1},
    ),
    "000009903004": EnhancementToolDescriptor(
        enhancement_id="000009903004",
        name="Seersight Strike",
        timing="passive",
        target="bearer_psychic_weapons",
        duration="constant",
        effect="bearer_psychic_weapon_gain_anti",
        effect_params={"anti_monster": 2, "anti_vehicle": 2},
    ),
    "000009903005": EnhancementToolDescriptor(
        enhancement_id="000009903005",
        name="Echoes of Ulthanesh",
        timing="start_of_command_phase",
        target="bearer",
        duration="instant",
        effect="cp_gain_roll_with_deployment_zone_modifiers",
        effect_params={
            "cp_gain": 1,
            "success_on": 5,
            "outside_own_zone_bonus": 1,
            "enemy_zone_additional_bonus": 1,
        },
    ),
}

_AELDARI_WINDRIDER_HOST_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AELDARI_WINDRIDER_HOST_DESCRIPTORS.values()
}

_AELDARI_GHOSTS_OF_THE_WEBWAY_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009915002": EnhancementToolDescriptor(
        enhancement_id="000009915002",
        name="Cegorach's Coil",
        timing="end_of_charge_move",
        target="enemy_unit_within_engagement_range_of_bearer_unit",
        duration="instant",
        effect="charge_end_mortal_wounds_per_model_in_engagement_with_cap",
        effect_params={
            "roll": "D6",
            "roll_threshold": 4,
            "mortal_per_success": 1,
            "max_mortal_wounds": 6,
        },
    ),
    "000009915003": EnhancementToolDescriptor(
        enhancement_id="000009915003",
        name="Mask of Secrets",
        timing="enemy_fall_back_within_engagement_range",
        target="enemy_non_monster_non_vehicle_unit_within_engagement_range_of_bearer_unit",
        duration="instant",
        effect="enemy_fall_back_forced_desperate_escape_with_battleshock_penalty",
        effect_params={
            "exclude_monster_vehicle": True,
            "battle_shock_test_modifier": -1,
        },
    ),
    "000009915004": EnhancementToolDescriptor(
        enhancement_id="000009915004",
        name="Murder's Jest",
        timing="on_attack_hit_roll",
        target="bearer_attacks_vs_enemy_below_half_strength",
        duration="constant_conditional",
        effect="successful_hits_become_critical",
        effect_params={"target_requires_below_half_strength": True},
    ),
    "000009915005": EnhancementToolDescriptor(
        enhancement_id="000009915005",
        name="Mistweave",
        timing="passive_while_leading",
        target="bearer_unit",
        duration="constant",
        effect="grant_infiltrators_while_leading",
    ),
}

_AELDARI_GHOSTS_OF_THE_WEBWAY_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AELDARI_GHOSTS_OF_THE_WEBWAY_DESCRIPTORS.values()
}

_AELDARI_SPIRIT_CONCLAVE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009907002": EnhancementToolDescriptor(
        enhancement_id="000009907002",
        name="Light of Clarity",
        timing="start_of_command_phase",
        target="friendly_wraith_construct_unit_within_range_of_bearer",
        duration="until_start_of_next_command_phase",
        effect="target_wraith_construct_model_objective_control_bonus",
        range_in=12.0,
        effect_params={
            "infantry_objective_control_bonus": 1,
            "monster_objective_control_bonus": 3,
        },
    ),
    "000009907003": EnhancementToolDescriptor(
        enhancement_id="000009907003",
        name="Stave of Kurnous",
        timing="start_of_command_phase",
        target="friendly_non_titanic_wraith_construct_unit_within_range_of_bearer",
        duration="until_start_of_next_command_phase",
        effect="target_wraith_construct_precision_on_critical_wound",
        range_in=12.0,
        effect_params={
            "precision_on_critical_wound": True,
            "exclude_titanic": True,
        },
    ),
    "000009907004": EnhancementToolDescriptor(
        enhancement_id="000009907004",
        name="Rune of Mists",
        timing="start_of_command_phase",
        target="friendly_wraith_construct_unit_within_range_of_bearer",
        duration="until_start_of_next_command_phase",
        effect="target_wraith_construct_ranged_cover_unless_attacker_within_distance",
        range_in=12.0,
        effect_params={
            "minimum_attacker_distance_for_cover": 18,
        },
    ),
    "000009907005": EnhancementToolDescriptor(
        enhancement_id="000009907005",
        name="Higher Duty",
        timing="enemy_move_end_reactive",
        target="bearer_unit",
        duration="constant_once_per_turn",
        effect="reactive_normal_move_when_enemy_move_ends_within_range",
        effect_params={
            "trigger_range": 9,
            "normal_move_distance": 6,
            "trigger_actions": ("move", "advance", "fall_back"),
            "limit": "turn",
        },
    ),
}

_AELDARI_SPIRIT_CONCLAVE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AELDARI_SPIRIT_CONCLAVE_DESCRIPTORS.values()
}

_AELDARI_SERPENTS_BROOD_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010649002": EnhancementToolDescriptor(
        enhancement_id="000010649002",
        name="Key of Ghosts",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_scouts_to_bearer_unit",
        effect_params={"scouts_distance": 6},
    ),
    "000010649003": EnhancementToolDescriptor(
        enhancement_id="000010649003",
        name="Weavers' Wail",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_strength_attacks_bonus",
        effect_params={"strength_bonus": 3, "attacks_bonus": 1},
    ),
    "000010649004": EnhancementToolDescriptor(
        enhancement_id="000010649004",
        name="Fanged Leer",
        timing="on_cruel_amusement_selection",
        target="bearer_shrieker_cannon",
        duration="constant",
        effect="cruel_amusement_select_two_abilities",
        effect_params={"max_selected_abilities": 2},
    ),
    "000010649005": EnhancementToolDescriptor(
        enhancement_id="000010649005",
        name="Shedskin Raiment",
        timing="after_deployment",
        target="friendly_harlequins_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "allow_strategic_reserves": True,
            "filters": ("HARLEQUINS",),
        },
    ),
}

_AELDARI_SERPENTS_BROOD_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AELDARI_SERPENTS_BROOD_DESCRIPTORS.values()
}

_AELDARI_DEVOTED_OF_YNNEAD_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009919002": EnhancementToolDescriptor(
        enhancement_id="000009919002",
        name="Gaze of Ynnead",
        timing="passive",
        target="bearer_weapon_eldritch_storm",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={
            "weapon_name": "eldritch storm",
            "attack_type": "ranged",
            "keywords": ("DEVASTATING WOUNDS",),
        },
    ),
    "000009919003": EnhancementToolDescriptor(
        enhancement_id="000009919003",
        name="Storm of Whispers",
        timing="post_shooting",
        target="enemy_unit_hit_by_bearer",
        duration="instant",
        effect="post_shoot_battleshock_test",
        effect_params={"infantry_only": False},
    ),
    "000009919004": EnhancementToolDescriptor(
        enhancement_id="000009919004",
        name="Borrowed Vigour",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_attacks_bonus",
        effect_params={"attacks_bonus": 2},
    ),
    "000009919005": EnhancementToolDescriptor(
        enhancement_id="000009919005",
        name="Morbid Might",
        timing="on_melee_attack",
        target="bearer_melee_attacks",
        duration="constant",
        effect="bearer_melee_wound_reroll",
        effect_params={"reroll_wound_full": True},
    ),
}

_AELDARI_DEVOTED_OF_YNNEAD_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _AELDARI_DEVOTED_OF_YNNEAD_DESCRIPTORS.values()
}

_EXPERIMENTAL_PROTOTYPE_CADRE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009983002": EnhancementToolDescriptor(
        enhancement_id="000009983002",
        name="Supernova Launcher",
        timing="passive",
        target="bearer_selected_airbursting_fragmentation_projector",
        duration="constant",
        effect="selected_ranged_weapon_strength_ap_damage_bonus",
        effect_params={
            "weapon_name": "airbursting fragmentation projector",
            "strength_bonus": 3,
            "ap_bonus": 1,
            "damage_bonus": 1,
        },
    ),
    "000009983003": EnhancementToolDescriptor(
        enhancement_id="000009983003",
        name="Thermoneutronic Projector",
        timing="passive",
        target="bearer_selected_tau_flamer",
        duration="constant",
        effect="selected_ranged_weapon_strength_ap_damage_bonus",
        effect_params={
            "weapon_name": "t'au flamer",
            "strength_bonus": 2,
            "ap_bonus": 1,
            "damage_bonus": 1,
        },
    ),
    "000009983004": EnhancementToolDescriptor(
        enhancement_id="000009983004",
        name="Plasma Accelerator Rifle",
        timing="passive",
        target="bearer_selected_plasma_rifle",
        duration="constant",
        effect="selected_ranged_weapon_strength_ap_damage_bonus",
        effect_params={
            "weapon_name": "plasma rifle",
            "strength_bonus": 2,
            "attacks_bonus": 1,
            "ap_bonus": 1,
            "damage_bonus": 1,
        },
    ),
    "000009983005": EnhancementToolDescriptor(
        enhancement_id="000009983005",
        name="Fusion Blades",
        timing="passive",
        target="bearer_selected_fusion_blaster",
        duration="constant",
        effect="selected_ranged_weapon_strength_ap_damage_bonus",
        effect_params={
            "weapon_name": "fusion blaster",
            "attacks_bonus": 1,
            "strength_bonus": 3,
            "melta_bonus": 4,
        },
    ),
}

_EXPERIMENTAL_PROTOTYPE_CADRE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _EXPERIMENTAL_PROTOTYPE_CADRE_DESCRIPTORS.values()
}

_TAU_AUXILIARY_CADRE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009839003": EnhancementToolDescriptor(
        enhancement_id="000009839003",
        name="Admired Leader",
        timing="command_phase_start",
        target="one_friendly_kroot_or_vespid_stingwings_unit_within_range",
        duration="until_your_next_command_phase",
        effect="select_friendly_auxiliary_unit_for_leadership_and_objective_control_bonus",
        effect_params={
            "selection_range": 12.0,
            "target_keywords_any": ("KROOT", "VESPID STINGWINGS"),
            "leadership_bonus": 1,
            "objective_control_bonus": 1,
            "requires_not_battle_shocked_for_objective_control": True,
        },
    ),
    "000009839004": EnhancementToolDescriptor(
        enhancement_id="000009839004",
        name="Fanatical Convert",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_for_the_greater_good_to_bearer_unit",
        effect_params={"requires_bearer_alive": True},
    ),
    "000009839002": EnhancementToolDescriptor(
        enhancement_id="000009839002",
        name="Student of Kauyon",
        timing="declare_battle_formations",
        target="up_to_three_friendly_kroot_carnivores_or_kroot_farstalkers_units",
        duration="until_end_of_battle",
        effect="grant_deep_strike_to_selected_units",
        effect_params={
            "max_units": 3,
            "target_unit_name_patterns": ("kroot carnivore", "kroot farstalker"),
            "optional": True,
        },
    ),
    "000009839005": EnhancementToolDescriptor(
        enhancement_id="000009839005",
        name="Transponder Lock Module",
        timing="movement_phase_reinforcements_step",
        target="bearer_unit_in_reserves",
        duration="turn_one_reinforcements_step",
        effect="first_turn_deep_strike_arrival_with_auxiliary_spotter_requirement",
        effect_params={
            "strategic_reserves_setup_round_bonus": 1,
            "requires_deep_strike": True,
            "turn_one_spotter_range": 12.0,
            "turn_one_spotter_keywords_any": ("KROOT", "VESPID STINGWINGS"),
        },
    ),
}

_TAU_AUXILIARY_CADRE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _TAU_AUXILIARY_CADRE_DESCRIPTORS.values()
}

_TAU_KROOT_HUNTING_PACK_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008821002": EnhancementToolDescriptor(
        enhancement_id="000008821002",
        name="Borthrod Gland",
        timing="passive_while_bearer_is_leading",
        target="bearer_unit_melee_attacks",
        duration="constant",
        effect="leading_bearer_unit_melee_critical_hits_on_5plus",
        effect_params={
            "attack_type": "melee",
            "crit_hit_threshold": 5,
            "requires_bearer_alive": True,
            "requires_bearer_leading": True,
        },
    ),
    "000008821003": EnhancementToolDescriptor(
        enhancement_id="000008821003",
        name="Kroothawk Flock",
        timing="passive",
        target="bearer_unit_ranged_weapons_and_enemy_reinforcements_near_bearer",
        duration="constant",
        effect="bearer_unit_ranged_weapons_gain_ignores_cover_and_enemy_reserves_arrival_min_horizontal_distance_from_bearer",
        effect_params={
            "attack_type": "ranged",
            "keywords": ("IGNORES COVER",),
            "enemy_reserves_min_distance": 12.0,
            "horizontal_only": True,
            "requires_bearer_alive": True,
        },
    ),
    "000008821004": EnhancementToolDescriptor(
        enhancement_id="000008821004",
        name="Nomadic Hunter",
        timing="passive_while_bearer_is_leading",
        target="bearer_unit",
        duration="constant",
        effect="leading_bearer_unit_movement_bonus_and_ranged_assault",
        effect_params={
            "movement_bonus": 3,
            "attack_type": "ranged",
            "keywords": ("ASSAULT",),
            "requires_bearer_alive": True,
            "requires_bearer_leading": True,
        },
    ),
    "000008821005": EnhancementToolDescriptor(
        enhancement_id="000008821005",
        name="Root-carved Weapons",
        timing="passive",
        target="bearer_weapons",
        duration="constant",
        effect="bearer_weapons_gain_precision_and_devastating_wounds",
        effect_params={"attack_type": "any", "keywords": ("PRECISION", "DEVASTATING WOUNDS")},
    ),
}

_TAU_KROOT_HUNTING_PACK_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _TAU_KROOT_HUNTING_PACK_DESCRIPTORS.values()
}

_MONTKA_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008811002": EnhancementToolDescriptor(
        enhancement_id="000008811002",
        name="Coordinated Exploitation",
        timing="on_becoming_observer_while_bearer_is_leading",
        target="guided_units_targeting_spotted_unit",
        duration="until_end_of_phase",
        effect="grant_ranged_sustained_hits_vs_spotted",
        effect_params={"sustained_hits_value": 1},
    ),
    "000008811003": EnhancementToolDescriptor(
        enhancement_id="000008811003",
        name="Exemplar of the Mont'ka",
        timing="passive_while_bearer_is_leading",
        target="bearer_unit",
        duration="battle_round_4",
        effect="extend_killing_blow_to_round_four",
    ),
    "000008811004": EnhancementToolDescriptor(
        enhancement_id="000008811004",
        name="Strategic Conqueror",
        timing="start_of_first_battle_round_before_first_turn",
        target="friendly_tau_empire_models_within_selected_objective_while_bearer_on_battlefield",
        duration="constant",
        effect="add_objective_control_near_selected_objective",
        effect_params={"objective_control_bonus": 1},
    ),
    "000008811005": EnhancementToolDescriptor(
        enhancement_id="000008811005",
        name="Strike Swiftly",
        timing="start_of_battle_before_scout_moves",
        target="up_to_two_friendly_tau_empire_units_within_range_without_scouts",
        duration="until_end_of_battle",
        effect="grant_scouts_to_selected_units",
        effect_params={
            "max_units": 2,
            "selection_range": 6,
            "scouts_distance": 6,
            "requires_no_existing_scouts": True,
            "optional": True,
        },
    ),
}

_MONTKA_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _MONTKA_DESCRIPTORS.values()
}

_RETALIATION_CADRE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008815002": EnhancementToolDescriptor(
        enhancement_id="000008815002",
        name="Internal Grenade Racks",
        timing="end_of_normal_move",
        target="enemy_unit_moved_over_by_bearer",
        duration="instant",
        effect="bearer_gains_grenades_and_move_over_mortal_wounds",
        effect_params={
            "add_keywords": ["GRENADES"],
            "dice": 6,
            "threshold": 4,
            "mortal_per_success": 1,
            "move_types": ["move"],
            "requires_bearer_alive": True,
            "optional": True,
        },
    ),
    "000008815003": EnhancementToolDescriptor(
        enhancement_id="000008815003",
        name="Prototype Weapon System",
        timing="selected_to_shoot",
        target="bearer_ranged_weapons",
        duration="until_attacks_resolved",
        effect="choose_bearer_ranged_weapon_keyword_mode",
        effect_params={
            "ability_key": "prototype_weapon_system",
            "keyword_options": ["LETHAL HITS", "SUSTAINED HITS 1"],
            "requires_bearer_alive": True,
        },
    ),
    "000008815004": EnhancementToolDescriptor(
        enhancement_id="000008815004",
        name="Puretide Engram Neurochip",
        timing="targeted_by_stratagem",
        target="bearer_unit",
        duration="instant",
        effect="targeted_stratagem_cp_refund",
        effect_params={
            "roll_min": 4,
            "cp_gain": 1,
            "requires_bearer_alive": True,
        },
    ),
    "000008815005": EnhancementToolDescriptor(
        enhancement_id="000008815005",
        name="Starflare Ignition System",
        timing="end_of_opponent_turn",
        target="bearer_unit",
        duration="instant",
        effect="end_of_opponent_turn_enter_strategic_reserves_if_not_engaged",
        effect_params={
            "requires_not_engagement_range": True,
            "requires_bearer_alive": True,
            "once_per_battle": False,
            "ability_key": "starflare_ignition_system",
            "trigger_phase": "OPPONENT_TURN_END",
        },
    ),
}

_RETALIATION_CADRE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RETALIATION_CADRE_DESCRIPTORS.values()
}

_RAD_ZONE_CORPS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008385002": EnhancementToolDescriptor(
        enhancement_id="000008385002",
        name="Radial Suffusion",
        timing="command_phase_start_battle_round_2_to_5",
        target="enemy_units_within_enemy_deployment_zone_or_within_extra_range",
        duration="instant",
        effect="extend_rad_bombardment_fallout_targeting",
        effect_params={
            "extra_range_from_enemy_deployment_zone": 6,
            "requires_bearer_on_battlefield": True,
        },
    ),
    "000008385003": EnhancementToolDescriptor(
        enhancement_id="000008385003",
        name="Malphonic Susurrus",
        timing="passive_while_leading",
        target="bearer_unit",
        duration="constant",
        effect="grant_stealth_while_leading",
    ),
    "000008385004": EnhancementToolDescriptor(
        enhancement_id="000008385004",
        name="Peerless Eradicator",
        timing="passive_while_leading",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="grant_ranged_sustained_hits_while_leading",
        effect_params={"sustained_hits_value": 1},
    ),
    "000008385005": EnhancementToolDescriptor(
        enhancement_id="000008385005",
        name="Autoclavic Denunciation",
        timing="passive",
        target="bearer_ranged_weapons",
        duration="constant",
        effect="grant_bearer_ranged_anti_keywords",
        effect_params={"anti_infantry": 2, "anti_monster": 4},
    ),
}

_RAD_ZONE_CORPS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RAD_ZONE_CORPS_DESCRIPTORS.values()
}

_SKITARII_HUNTER_COHORT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008560002": EnhancementToolDescriptor(
        enhancement_id="000008560002",
        name="Cantic Thrallnet",
        timing="start_of_battle_round_optional",
        target="one_friendly_skitarii_unit_within_range_of_bearer",
        duration="until_start_of_next_battle_round",
        effect="select_friendly_skitarii_unit_within_range_of_bearer_and_treat_both_doctrina_imperatives_as_active",
        range_in=12.0,
        effect_params={
            "range": 12.0,
            "required_target_keywords": ("SKITARII",),
            "optional": True,
        },
    ),
    "000008560003": EnhancementToolDescriptor(
        enhancement_id="000008560003",
        name="Clandestine Infiltrator",
        timing="passive",
        target="bearer_and_bearer_led_unit",
        duration="constant",
        effect="grant_infiltrators_and_scouts_to_bearer_and_bearer_led_unit",
        effect_params={
            "scouts_distance": 6,
        },
    ),
    "000008560004": EnhancementToolDescriptor(
        enhancement_id="000008560004",
        name="Veiled Hunter",
        timing="post_deployment",
        target="friendly_skitarii_infantry_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "can_place_in_reserves": True,
            "redeploy_filters": ("SKITARII", "INFANTRY"),
        },
    ),
    "000008560005": EnhancementToolDescriptor(
        enhancement_id="000008560005",
        name="Battle-sphere Uplink",
        timing="your_shooting_phase_after_bearer_unit_shoots",
        target="bearer_unit",
        duration="instant_optional_with_no_charge_until_end_of_turn",
        effect="post_shoot_reactive_normal_move_no_charge",
        effect_params={
            "move_range": 6,
            "requires_not_engagement_range": True,
            "requires_bearer_alive": True,
        },
    ),
}

_SKITARII_HUNTER_COHORT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SKITARII_HUNTER_COHORT_DESCRIPTORS.values()
}

_COHORT_CYBERNETICA_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008572002": EnhancementToolDescriptor(
        enhancement_id="000008572002",
        name="Necromechanic",
        timing="when_friendly_legio_or_adeptus_mechanicus_vehicle_within_range_fails_save",
        target="friendly_legio_cybernetica_or_adeptus_mechanicus_vehicle_model_within_range",
        duration="once_per_battle_round",
        effect="set_failed_save_attack_damage_to_zero",
        range_in=12.0,
        effect_params={
            "range": 12.0,
            "usage": "battle_round",
            "required_target_keywords_any": ("LEGIO CYBERNETICA", "VEHICLE"),
            "required_target_faction_keyword_for_vehicle": "ADEPTUS MECHANICUS",
        },
    ),
    "000008572003": EnhancementToolDescriptor(
        enhancement_id="000008572003",
        name="Lord of Machines",
        timing="start_of_opponent_shooting_phase",
        target="enemy_vehicle_unit_within_range_visible",
        duration="until_end_of_phase",
        effect="leadership_test_then_hit_penalty_or_ineligible_to_shoot",
        range_in=12.0,
        effect_params={
            "range": 12.0,
            "required_target_keywords": ("VEHICLE",),
            "resolution_mode": "leadership_test",
            "optional": True,
            "limit_one_per_army": False,
        },
    ),
    "000008572004": EnhancementToolDescriptor(
        enhancement_id="000008572004",
        name="Emotionless Clarity",
        timing="when_friendly_legio_or_adeptus_mechanicus_vehicle_within_range_is_destroyed",
        target="friendly_legio_cybernetica_or_adeptus_mechanicus_vehicle_model_within_range_with_deadly_demise",
        duration="once_per_turn",
        effect="auto_trigger_deadly_demise",
        range_in=12.0,
        effect_params={
            "range": 12.0,
            "usage": "turn",
            "required_target_keywords_any": ("LEGIO CYBERNETICA", "VEHICLE"),
            "required_target_faction_keyword_for_vehicle": "ADEPTUS MECHANICUS",
        },
    ),
    "000008572005": EnhancementToolDescriptor(
        enhancement_id="000008572005",
        name="Arch-negator",
        timing="passive",
        target="bearer_ranged_weapons",
        duration="constant",
        effect="grant_bearer_ranged_anti_keywords",
        effect_params={"anti_vehicle": 4},
    ),
}

_COHORT_CYBERNETICA_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _COHORT_CYBERNETICA_DESCRIPTORS.values()
}

_DATA_PSALM_CONCLAVE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008564002": EnhancementToolDescriptor(
        enhancement_id="000008564002",
        name="Mechanicus Locum",
        timing="start_of_any_phase_once_per_battle",
        target="friendly_cult_mechanicus_battleshocked_unit_within_range",
        duration="instant",
        effect="clear_battleshock_for_friendly_unit_in_range",
        range_in=12.0,
        effect_params={
            "range": 12.0,
            "keyword_phrase": "CULT MECHANICUS",
            "once_per_battle_key": "mechanicus_locum",
        },
    ),
    "000008564003": EnhancementToolDescriptor(
        enhancement_id="000008564003",
        name="Mantle of the Gnosticarch",
        timing="when_attack_is_allocated_to_bearer",
        target="bearer",
        duration="constant",
        effect="set_allocated_damage_to_value",
        effect_params={"set_damage_to": 1},
    ),
    "000008564004": EnhancementToolDescriptor(
        enhancement_id="000008564004",
        name="Data-blessed Autosermon",
        timing="start_of_command_phase_once_per_battle",
        target="bearer_unit",
        duration="until_next_command_phase",
        effect="activate_other_data_psalm_benediction_for_bearer_unit",
        effect_params={
            "once_per_battle_key": "data_blessed_autosermon",
        },
    ),
    "000008564005": EnhancementToolDescriptor(
        enhancement_id="000008564005",
        name="Temporcopia",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_fights_first_to_bearer_unit",
    ),
}

_DATA_PSALM_CONCLAVE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DATA_PSALM_CONCLAVE_DESCRIPTORS.values()
}

_ADEPTUS_CUSTODES_AURIC_CHAMPIONS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008930002": EnhancementToolDescriptor(
        enhancement_id="000008930002",
        name="Blade Imperator",
        timing="on_charge_end_and_once_per_battle_on_charge_end",
        target="enemy_unit_in_engagement_range_of_bearer_and_enemy_units_within_range_of_bearer",
        duration="instant",
        effect="charge_end_single_roll_mortal_wounds_plus_once_per_battle_battleshock_aura",
        effect_params={
            "roll_threshold": 4,
            "mortal_wounds_die": "D3",
            "charge_target_requires_engagement_with_bearer": True,
            "battleshock_range": 6,
            "charge_mortal_once_per_battle_key": "blade_imperator_charge_mortal",
            "battleshock_once_per_battle_key": "blade_imperator_battleshock",
        },
    ),
    "000008930003": EnhancementToolDescriptor(
        enhancement_id="000008930003",
        name="Inspirational Exemplar",
        timing="passive_and_start_of_any_phase_once_per_battle",
        target="bearer_and_friendly_adeptus_custodes_battleshocked_unit_within_range",
        duration="constant_and_instant",
        effect="set_bearer_leadership_and_clear_battleshock_for_friendly_unit_in_range",
        range_in=12.0,
        effect_params={
            "bearer_leadership": 5,
            "range": 12.0,
            "keyword_phrase": "ADEPTUS CUSTODES",
            "once_per_battle_key": "inspirational_exemplar",
        },
    ),
    "000008930004": EnhancementToolDescriptor(
        enhancement_id="000008930004",
        name="Martial Philosopher",
        timing="passive_and_on_enemy_move_ended_within_range_once_per_battle",
        target="bearer_unit",
        duration="constant_and_instant",
        effect="shoot_and_charge_after_fall_back_plus_once_per_battle_reactive_move",
        range_in=9.0,
        effect_params={
            "shoot_after_fall_back": True,
            "charge_after_fall_back": True,
            "trigger_range": 9,
            "max_distance": 6,
            "trigger_actions": ("move", "advance", "fall_back"),
            "requires_not_engaged": True,
            "once_per_battle": True,
            "once_per_battle_key": "martial_philosopher",
        },
    ),
    "000008930005": EnhancementToolDescriptor(
        enhancement_id="000008930005",
        name="Veiled Blade",
        timing="passive_and_start_of_any_command_phase_once_per_battle",
        target="bearer",
        duration="constant_and_until_end_of_turn",
        effect="bearer_melee_attacks_bonus_and_once_per_battle_objective_control_multiplier",
        effect_params={
            "melee_attacks_bonus": 2,
            "objective_control_multiplier": 3,
            "once_per_battle_key": "veiled_blade",
        },
    ),
}

_ADEPTUS_CUSTODES_AURIC_CHAMPIONS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ADEPTUS_CUSTODES_AURIC_CHAMPIONS_DESCRIPTORS.values()
}

_ADEPTUS_CUSTODES_NULL_MAIDEN_VIGIL_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008926002": EnhancementToolDescriptor(
        enhancement_id="000008926002",
        name="Enhanced Voidsheen Cloak",
        timing="when_attack_is_allocated_to_bearer",
        target="bearer",
        duration="constant",
        effect="reduce_allocated_damage_or_set_to_one_vs_psyker_or_battleshocked_attacker",
        effect_params={
            "damage_reduction": 1,
            "set_damage_to": 1,
            "conditional_attacker_keywords_any": ("PSYKER",),
            "conditional_attacker_battle_shocked": True,
        },
    ),
    "000008926003": EnhancementToolDescriptor(
        enhancement_id="000008926003",
        name="Huntress' Eye",
        timing="start_of_command_phase",
        target="enemy_unit_within_range_of_bearer",
        duration="instant",
        effect="select_enemy_unit_within_range_to_take_battleshock_test",
        range_in=12.0,
        effect_params={
            "range": 12.0,
        },
    ),
    "000008926004": EnhancementToolDescriptor(
        enhancement_id="000008926004",
        name="Oblivion Knight",
        timing="passive_while_bearer_is_leading",
        target="bearer_led_unit_attacks",
        duration="constant_while_bearer_is_leading",
        effect="add_hit_bonus_for_bearer_led_unit_and_wound_bonus_vs_psyker",
        effect_params={
            "requires_bearer_leading": True,
            "hit_roll_bonus": 1,
            "wound_roll_bonus_vs_psyker": 1,
        },
    ),
    "000008926005": EnhancementToolDescriptor(
        enhancement_id="000008926005",
        name="Raptor Blade",
        timing="passive_with_conditional_scaling",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_asd_bonus_with_conditional_extra_vs_battleshocked_psyker_in_engagement",
        effect_params={
            "base_melee_attacks_bonus": 1,
            "base_melee_strength_bonus": 1,
            "base_melee_damage_bonus": 1,
            "conditional_extra_bonus": 1,
            "conditional_enemy_keyword": "PSYKER",
            "conditional_enemy_battle_shocked": True,
        },
    ),
}

_ADEPTUS_CUSTODES_NULL_MAIDEN_VIGIL_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ADEPTUS_CUSTODES_NULL_MAIDEN_VIGIL_DESCRIPTORS.values()
}

_ADEPTUS_CUSTODES_SHIELD_HOST_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008395002": EnhancementToolDescriptor(
        enhancement_id="000008395002",
        name="Auric Mantle",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="add_wounds_to_bearer",
        effect_params={"wounds_bonus": 2},
    ),
    "000008395003": EnhancementToolDescriptor(
        enhancement_id="000008395003",
        name="Castellan's Mark",
        timing="after_deployment_before_first_turn",
        target="up_to_two_friendly_adeptus_custodes_units_excluding_anathema_psykana",
        duration="instant",
        effect="redeploy_units",
        effect_params={
            "max_units": 2,
            "can_place_in_reserves": True,
            "redeploy_filters": ("ADEPTUS CUSTODES",),
            "redeploy_excluded_keywords": ("ANATHEMA PSYKANA",),
        },
    ),
    "000008395004": EnhancementToolDescriptor(
        enhancement_id="000008395004",
        name="From the Hall of Armouries",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="add_strength_and_damage_to_bearer_melee_weapons",
        effect_params={
            "melee_strength_bonus": 1,
            "melee_damage_bonus": 1,
        },
    ),
    "000008395005": EnhancementToolDescriptor(
        enhancement_id="000008395005",
        name="Panoptispex",
        timing="while_bearer_is_leading",
        target="bearer_led_unit_ranged_weapons",
        duration="constant_while_bearer_is_leading",
        effect="grant_ignores_cover_to_bearer_led_unit_ranged_weapons",
        effect_params={
            "requires_bearer_leading": True,
            "keywords": ("IGNORES COVER",),
        },
    ),
}

_ADEPTUS_CUSTODES_SHIELD_HOST_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ADEPTUS_CUSTODES_SHIELD_HOST_DESCRIPTORS.values()
}

_ADEPTUS_CUSTODES_SOLAR_SPEARHEAD_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009753004": EnhancementToolDescriptor(
        enhancement_id="000009753004",
        name="Honoured Fallen (Aura)",
        timing="passive_aura",
        target="friendly_adeptus_custodes_infantry_or_mounted_units_within_range_of_bearer",
        duration="constant",
        effect="reroll_hit_rolls_of_one_for_friendly_units_in_aura",
        range_in=6.0,
        effect_params={
            "range": 6.0,
            "reroll_values": (1,),
            "required_target_faction_keyword": "ADEPTUS CUSTODES",
            "required_target_keywords_any": ("INFANTRY", "MOUNTED"),
        },
    ),
    "000009753005": EnhancementToolDescriptor(
        enhancement_id="000009753005",
        name="Veteran of the Kataphraktoi",
        timing="start_of_command_phase",
        target="friendly_adeptus_custodes_vehicle_or_mounted_unit_within_range_of_bearer",
        duration="until_next_command_phase",
        effect="select_friendly_unit_to_shoot_after_fall_back",
        range_in=6.0,
        effect_params={
            "range": 6.0,
            "optional": True,
            "required_target_faction_keyword": "ADEPTUS CUSTODES",
            "required_target_keywords_any": ("VEHICLE", "MOUNTED"),
            "shoot_after_fall_back": True,
        },
    ),
}

_ADEPTUS_CUSTODES_SOLAR_SPEARHEAD_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ADEPTUS_CUSTODES_SOLAR_SPEARHEAD_DESCRIPTORS.values()
}

_ADEPTUS_CUSTODES_TALONS_OF_THE_EMPEROR_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008921002": EnhancementToolDescriptor(
        enhancement_id="000008921002",
        name="Aegis Projector",
        timing="on_first_failed_save_each_turn",
        target="bearer_unit",
        duration="once_per_turn",
        effect="set_failed_save_damage_to_zero",
        effect_params={
            "usage_scope": "turn",
            "first_failed_save_only": True,
            "set_damage_to": 0,
        },
    ),
    "000008921003": EnhancementToolDescriptor(
        enhancement_id="000008921003",
        name="Champion of the Imperium",
        timing="passive",
        target="bearer_null_aegis_or_deadly_unity_ability",
        duration="constant",
        effect="increase_bearer_talons_aura_range",
        range_in=9.0,
        effect_params={
            "aura_range": 9.0,
            "applies_to_abilities": ("Null Aegis", "Deadly Unity"),
        },
    ),
    "000008921004": EnhancementToolDescriptor(
        enhancement_id="000008921004",
        name="Gift of Terran Artifice",
        timing="passive",
        target="bearer_melee_attacks",
        duration="constant",
        effect="add_wound_roll_bonus_to_bearer_melee_attacks",
        effect_params={"melee_wound_bonus": 1},
    ),
    "000008921005": EnhancementToolDescriptor(
        enhancement_id="000008921005",
        name="Radiant Mantle",
        timing="when_bearer_unit_is_targeted_by_attack",
        target="attacks_targeting_bearer_unit_within_range",
        duration="constant",
        effect="subtract_hit_roll_when_attacker_within_range",
        range_in=12.0,
        effect_params={
            "range": 12.0,
            "target_hit_roll_penalty": 1,
        },
    ),
}

_ADEPTUS_CUSTODES_TALONS_OF_THE_EMPEROR_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ADEPTUS_CUSTODES_TALONS_OF_THE_EMPEROR_DESCRIPTORS.values()
}

_EXPLORATOR_MANIPLE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008568002": EnhancementToolDescriptor(
        enhancement_id="000008568002",
        name="Magos",
        timing="end_of_command_phase",
        target="bearer_on_acquisition_objective",
        duration="instant",
        effect="roll_for_command_point_gain_if_bearer_within_acquisition_objective",
        effect_params={
            "roll": "D6",
            "roll_min": 4,
            "cp_gain": 1,
        },
    ),
    "000008568003": EnhancementToolDescriptor(
        enhancement_id="000008568003",
        name="Genetor",
        timing="passive",
        target="bearer_led_unit_within_acquisition_objective",
        duration="constant",
        effect="grant_invulnerable_save_to_bearer_led_unit_within_acquisition_objective",
        effect_params={
            "requires_bearer_leading": True,
            "requires_unit_within_acquisition_objective": True,
            "invulnerable_save": 4,
        },
    ),
    "000008568004": EnhancementToolDescriptor(
        enhancement_id="000008568004",
        name="Logis",
        timing="passive",
        target="bearer_led_unit_attacks_vs_target_within_acquisition_objective",
        duration="constant",
        effect="add_hit_roll_bonus_for_bearer_led_unit_vs_target_within_acquisition_objective",
        effect_params={
            "requires_bearer_leading": True,
            "requires_target_within_acquisition_objective": True,
            "hit_roll_bonus": 1,
        },
    ),
    "000008568005": EnhancementToolDescriptor(
        enhancement_id="000008568005",
        name="Artisan",
        timing="after_hit_wound_or_save_roll_once_per_phase",
        target="bearer_led_unit_within_acquisition_objective",
        duration="instant_once_per_phase",
        effect="set_one_hit_wound_or_save_roll_to_unmodified_six",
        effect_params={
            "requires_bearer_leading": True,
            "requires_unit_within_acquisition_objective": True,
            "usage_limit": "phase",
            "allowed_roll_types": ("hit", "wound", "save"),
        },
    ),
}

_EXPLORATOR_MANIPLE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _EXPLORATOR_MANIPLE_DESCRIPTORS.values()
}

_HALOSCREED_BATTLE_CLADE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009745002": EnhancementToolDescriptor(
        enhancement_id="000009745002",
        name="Transoracular Dyad Wafers",
        timing="passive",
        target="bearer_attached_kastelan_robots_unit",
        duration="constant",
        effect="grant_halo_override_to_bearer_attached_kastelan_unit_and_exclude_from_noospheric_selection",
        effect_params={
            "requires_bearer_attached_to_kastelan_robots": True,
        },
    ),
    "000009745003": EnhancementToolDescriptor(
        enhancement_id="000009745003",
        name="Cognitive Reinforcement",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="treat_conqueror_and_protector_imperatives_as_active_for_bearer_unit",
    ),
    "000009745004": EnhancementToolDescriptor(
        enhancement_id="000009745004",
        name="Sanctified Ordnance",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="add_ranged_range_and_hazardous_reroll_for_bearer_unit",
        effect_params={
            "range_bonus": 6,
            "hazardous_reroll": True,
        },
    ),
    "000009745005": EnhancementToolDescriptor(
        enhancement_id="000009745005",
        name="Inloaded Lethality",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="add_melee_attacks_and_damage_to_bearer_melee_weapons",
        effect_params={
            "melee_attacks_bonus": 3,
            "melee_damage_bonus": 1,
        },
    ),
}

_HALOSCREED_BATTLE_CLADE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _HALOSCREED_BATTLE_CLADE_DESCRIPTORS.values()
}

_ERADICATION_COHORT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010747002": EnhancementToolDescriptor(
        enhancement_id="000010747002",
        name="Belicosa-Class Capacitor Vanes",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="treat_conqueror_and_protector_imperatives_as_active_for_bearer_unit",
    ),
    "000010747003": EnhancementToolDescriptor(
        enhancement_id="000010747003",
        name="Martial Signatum Amplificator",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_skitarii_keyword_to_bearer_unit",
        effect_params={"added_keyword": "SKITARII"},
    ),
    "000010747004": EnhancementToolDescriptor(
        enhancement_id="000010747004",
        name="Omnicogitator",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="add_ranged_range_and_strength_to_bearer_unit",
        effect_params={
            "range_bonus": 6,
            "strength_bonus": 1,
        },
    ),
    "000010747005": EnhancementToolDescriptor(
        enhancement_id="000010747005",
        name="Omnissiah's Fury",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="add_melee_attacks_ap_and_damage_to_bearer_melee_weapons",
        effect_params={
            "melee_attacks_bonus": 2,
            "melee_ap_bonus": 1,
            "melee_damage_bonus": 1,
        },
    ),
}

_ERADICATION_COHORT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ERADICATION_COHORT_DESCRIPTORS.values()
}

_INVASION_FLEET_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008348002": EnhancementToolDescriptor(
        enhancement_id="000008348002",
        name="Alien Cunning",
        timing="after_deployment",
        target="friendly_tyranids_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={"max_units": 3, "allow_strategic_reserves": True},
    ),
    "000008348003": EnhancementToolDescriptor(
        enhancement_id="000008348003",
        name="Perfectly Adapted",
        timing="when_making_roll_for_bearer",
        target="bearer",
        duration="once_per_turn",
        effect="bearer_single_reroll_one_of_hit_wound_damage_advance_charge_or_save",
        effect_params={
            "once_per_turn": True,
            "shared_pool": True,
            "roll_types": ("hit", "wound", "damage", "advance", "charge", "save"),
        },
    ),
    "000008348004": EnhancementToolDescriptor(
        enhancement_id="000008348004",
        name="Synaptic Linchpin",
        timing="passive_aura",
        target="friendly_tyranids_units_within_range_of_bearer",
        duration="constant",
        effect="count_as_within_synapse_range",
        range_in=9.0,
        effect_params={"keyword": "TYRANIDS"},
    ),
}

_INVASION_FLEET_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _INVASION_FLEET_DESCRIPTORS.values()
}

_CABAL_OF_CHAOS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010151002": EnhancementToolDescriptor(
        enhancement_id="000010151002",
        name="Touched by the Warp",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="grant_keyword",
        effect_params={"keyword": "PSYKER"},
    ),
    "000010151003": EnhancementToolDescriptor(
        enhancement_id="000010151003",
        name="Eyes of Z'desh",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_scouts",
        effect_params={"scouts_distance": 6},
    ),
    "000010151004": EnhancementToolDescriptor(
        enhancement_id="000010151004",
        name="Mind Blade",
        timing="passive",
        target="bearer_unit_melee_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={"lance": True},
    ),
    "000010151005": EnhancementToolDescriptor(
        enhancement_id="000010151005",
        name="Infernal Avatar",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_strength_ap_bonus",
        effect_params={"strength_bonus": 2, "ap_bonus": 1},
    ),
}

_CABAL_OF_CHAOS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CABAL_OF_CHAOS_DESCRIPTORS.values()
}

_CHAOS_CULT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008981002": EnhancementToolDescriptor(
        enhancement_id="000008981002",
        name="Amulet of Tainted Vigour",
        timing="command_phase_start",
        target="bearer_led_unit",
        duration="instant_optional",
        effect="return_destroyed_damned_models_to_bearer_unit",
        effect_params={
            "requires_bearer_leading": True,
            "return_roll": "D3",
            "required_model_keyword": "DAMNED",
            "exclude_character": True,
            "optional": True,
        },
    ),
    "000008981003": EnhancementToolDescriptor(
        enhancement_id="000008981003",
        name="Cultist's Brand",
        timing="passive",
        target="bearer_unit",
        duration="constant_conditional",
        effect="reroll_advance_and_charge_rolls_for_bearer_unit",
        effect_params={
            "reroll_advance": True,
            "reroll_charge": True,
            "requires_all_other_models_keyword": "DAMNED",
            "exclude_model_names": ("Dark Disciple", "Dark Disciples"),
        },
    ),
    "000008981004": EnhancementToolDescriptor(
        enhancement_id="000008981004",
        name="Incendiary Goad",
        timing="passive",
        target="damned_models_in_bearer_unit_melee_weapons",
        duration="constant_conditional",
        effect="conditional_melee_strength_and_attacks_bonus_for_damned_models_in_bearer_unit",
        effect_params={
            "required_model_keyword": "DAMNED",
            "requires_unit_below_starting_strength": True,
            "melee_strength_bonus": 1,
            "requires_unit_below_half_strength_for_attacks_bonus": True,
            "melee_attacks_bonus": 1,
        },
    ),
    "000008981005": EnhancementToolDescriptor(
        enhancement_id="000008981005",
        name="Warped Foresight",
        timing="passive",
        target="bearer_unit",
        duration="constant_conditional",
        effect="grant_scouts_while_bearer_leads_scouts_unit",
        effect_params={
            "requires_bearer_leading": True,
            "required_led_unit_scouts_distance": 6,
            "scouts_distance": 6,
        },
    ),
}

_CHAOS_CULT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CHAOS_CULT_DESCRIPTORS.values()
}

_CREATIONS_OF_BILE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009773002": EnhancementToolDescriptor(
        enhancement_id="000009773002",
        name="Surgical Precision",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_weapons_gain_precision",
        effect_params={"keywords": ("PRECISION",)},
    ),
    "000009773003": EnhancementToolDescriptor(
        enhancement_id="000009773003",
        name="Living Carapace",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_wounds_and_fnp_bonus",
        effect_params={
            "bearer_wounds_bonus": 1,
            "fnp": 5,
        },
    ),
    "000009773004": EnhancementToolDescriptor(
        enhancement_id="000009773004",
        name="Helm of All-seeing",
        timing="passive_aura",
        target="enemy_reserves_arrival",
        duration="constant",
        effect="enemy_reserves_arrival_min_distance_from_bearer",
        effect_params={
            "min_enemy_distance": 12,
            "horizontal_only": False,
        },
    ),
    "000009773005": EnhancementToolDescriptor(
        enhancement_id="000009773005",
        name="Prime Test Subject",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_damage_bonus_and_reroll_hits",
        effect_params={
            "bearer_melee_damage_bonus": 1,
            "reroll_hit": True,
        },
    ),
}

_CREATIONS_OF_BILE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CREATIONS_OF_BILE_DESCRIPTORS.values()
}

_DECEPTORS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008964002": EnhancementToolDescriptor(
        enhancement_id="000008964002",
        name="Cursed Fang",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_ap_bonus_and_precision",
        effect_params={"melee_ap_bonus": 1, "precision": True},
    ),
    "000008964003": EnhancementToolDescriptor(
        enhancement_id="000008964003",
        name="Falsehood",
        timing="declare_battle_formations_and_reinforcements_step",
        target="bearer_and_friendly_legionaries_or_chosen_model",
        duration="battle_setup_and_once_during_battle",
        effect="optional_reserves_setup_and_reinforcements_model_swap_attach",
        effect_params={
            "optional": True,
            "declare_choice": ("DEPLOY", "RESERVES"),
            "target_unit_names": ("Legionaries", "Chosen"),
            "requires_target_unit_models_remaining_at_least": 2,
        },
    ),
    "000008964004": EnhancementToolDescriptor(
        enhancement_id="000008964004",
        name="Shroud of Obfuscation",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_gains_stealth_and_lone_operative",
        effect_params={"grants_stealth": True, "grants_lone_operative": True},
    ),
    "000008964005": EnhancementToolDescriptor(
        enhancement_id="000008964005",
        name="Soul Link",
        timing="start_of_command_phase",
        target="bearer_and_other_friendly_heretic_astartes_infantry_character_model",
        duration="until_start_of_next_owner_command_phase",
        effect="select_model_gain_psyker_and_replace_bearer_datasheet_abilities",
        effect_params={"optional": True, "granted_keyword": "PSYKER", "exclude_epic_hero": True},
    ),
}

_DECEPTORS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DECEPTORS_DESCRIPTORS.values()
}

_HURONS_MARAUDERS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010688002": EnhancementToolDescriptor(
        enhancement_id="000010688002",
        name="Voice of the Tyrant",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_has_both_tyrannical_motivation_abilities",
        effect_params={
            "grant_hurons_elite": True,
            "grant_mobile_marauders": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010688003": EnhancementToolDescriptor(
        enhancement_id="000010688003",
        name="Raid Leader",
        timing="on_disembark_after_transport_normal_move",
        target="bearer_unit",
        duration="that_turn",
        effect="allow_charge_after_disembark_from_transport_normal_move",
        effect_params={
            "allow_charge_after_normal_move": True,
            "requires_disembarked_from_moved_transport": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010688004": EnhancementToolDescriptor(
        enhancement_id="000010688004",
        name="Dread Reputation",
        timing="on_unit_set_up",
        target="enemy_units_within_range_of_bearer_unit",
        duration="instant",
        effect="on_set_up_enemy_units_within_range_take_battleshock_test",
        effect_params={
            "range_in": 6.0,
            "deep_strike_range_in": 12.0,
            "requires_bearer_alive": True,
        },
    ),
    "000010688005": EnhancementToolDescriptor(
        enhancement_id="000010688005",
        name="Eager for Bloodshed",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_gains_infiltrators",
        effect_params={
            "grants_infiltrators": True,
            "requires_bearer_alive": True,
        },
    ),
}

_HURONS_MARAUDERS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _HURONS_MARAUDERS_DESCRIPTORS.values()
}

_RENEGADE_RAIDERS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008968002": EnhancementToolDescriptor(
        enhancement_id="000008968002",
        name="Despot's Claim",
        timing="start_of_command_phase",
        target="army",
        duration="instant",
        effect="command_phase_cp_roll_with_enemy_deployment_zone_bonus",
        effect_params={
            "roll": "D6",
            "success_on": 5,
            "cp_gain": 1,
            "enemy_deployment_zone_bonus_if_wholly_within_distance": 1,
            "enemy_deployment_zone_distance_in": 12.0,
            "requires_bearer_on_battlefield": True,
        },
    ),
    "000008968003": EnhancementToolDescriptor(
        enhancement_id="000008968003",
        name="Dread Reaver",
        timing="on_bearer_melee_attack",
        target="bearer_melee_attacks",
        duration="constant_conditional",
        effect="bearer_melee_hit_wound_reroll_within_enemy_deployment_zone_distance",
        effect_params={
            "distance_in": 12.0,
            "reroll_hit": True,
            "reroll_wound": True,
            "requires_bearer_alive": True,
            "requires_bearer_on_battlefield": True,
        },
    ),
    "000008968004": EnhancementToolDescriptor(
        enhancement_id="000008968004",
        name="Mark of the Hound",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_gains_scouts",
        effect_params={
            "scout_distance": 6,
            "requires_bearer_alive": True,
        },
    ),
    "000008968005": EnhancementToolDescriptor(
        enhancement_id="000008968005",
        name="Tyrant's Lash",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="reroll_advance_and_shoot_after_fall_back_for_bearer_unit",
        effect_params={
            "reroll_advance": True,
            "allow_shoot_after_fall_back": True,
            "requires_bearer_alive": True,
            "requires_bearer_on_battlefield": True,
        },
    ),
}

_RENEGADE_RAIDERS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RENEGADE_RAIDERS_DESCRIPTORS.values()
}

_RENEGADE_WARBAND_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010694002": EnhancementToolDescriptor(
        enhancement_id="000010694002",
        name="Weaponised Hatred",
        timing="after_vendetta_target_destroyed_once_per_battle_round",
        target="visible_enemy_unit_or_skip",
        duration="instant",
        effect="optional_select_new_vendetta_target",
        effect_params={
            "optional": True,
            "requires_vendetta_target_destroyed": True,
            "requires_bearer_on_battlefield": True,
            "requires_visibility": True,
            "excludes_destroyed_vendetta_target": True,
            "excludes_current_vendetta_target": True,
        },
    ),
    "000010694003": EnhancementToolDescriptor(
        enhancement_id="000010694003",
        name="Eyes of the Hunter",
        timing="passive",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={
            "keywords": ("IGNORES COVER",),
            "attack_type": "ranged",
        },
    ),
    "000010694004": EnhancementToolDescriptor(
        enhancement_id="000010694004",
        name="Fratricidal Trophies",
        timing="passive",
        target="bearer_unit_attacks",
        duration="constant_conditional",
        effect="reroll_hit_when_default_to_doctrine",
        effect_params={
            "reroll_hit": True,
            "requires_default_to_doctrine": True,
        },
    ),
    "000010694005": EnhancementToolDescriptor(
        enhancement_id="000010694005",
        name="Empyric Symbiote",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="advance_and_charge_roll_bonus",
        effect_params={
            "advance_roll_bonus": 1,
            "charge_roll_bonus": 1,
        },
    ),
}

_RENEGADE_WARBAND_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _RENEGADE_WARBAND_DESCRIPTORS.values()
}

_DREAD_TALONS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008972002": EnhancementToolDescriptor(
        enhancement_id="000008972002",
        name="Eater of Dread",
        timing="start_of_command_phase",
        target="army",
        duration="instant",
        effect="command_phase_cp_roll_per_battle_shocked_enemy_unit",
        effect_params={
            "roll": "D6",
            "success_on": 5,
            "cp_gain": 1,
            "enemy_battleshocked_roll_bonus": 1,
            "requires_bearer_on_battlefield": True,
        },
    ),
    "000008972003": EnhancementToolDescriptor(
        enhancement_id="000008972003",
        name="Night's Shroud",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_gains_stealth",
        effect_params={"requires_bearer_alive": True},
    ),
    "000008972004": EnhancementToolDescriptor(
        enhancement_id="000008972004",
        name="Warp-fuelled Thrusters",
        timing="end_of_opponent_turn",
        target="bearer_unit",
        duration="instant",
        effect="end_of_opponent_turn_enter_strategic_reserves_if_not_engaged",
        effect_params={
            "requires_not_engagement_range": True,
            "requires_bearer_alive": True,
            "once_per_battle": False,
            "ability_key": "warp_fuelled_thrusters",
        },
    ),
    "000008972005": EnhancementToolDescriptor(
        enhancement_id="000008972005",
        name="Willbreaker",
        timing="post_fight_after_bearer_attacks",
        target="hit_enemy_unit",
        duration="instant",
        effect="post_fight_bearer_select_hit_enemy_battleshock_test",
        effect_params={
            "applies_after_fight": True,
            "requires_bearer_hit_target": True,
        },
    ),
}

_DREAD_TALONS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DREAD_TALONS_DESCRIPTORS.values()
}

_FELLHAMMER_SIEGE_HOST_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008976002": EnhancementToolDescriptor(
        enhancement_id="000008976002",
        name="Bastion Plate",
        timing="on_failed_save_for_bearer_unit",
        target="bearer_unit",
        duration="constant_once_per_battle_round",
        effect="failed_save_damage_set_zero_for_bearer_unit",
        effect_params={
            "usage_scope": "battle_round",
            "set_damage_to": 0,
            "optional": True,
        },
    ),
    "000008976003": EnhancementToolDescriptor(
        enhancement_id="000008976003",
        name="Iron Artifice",
        timing="passive",
        target="bearer_weapons",
        duration="constant",
        effect="grant_bearer_weapon_anti_vehicle_and_fortification",
        effect_params={
            "anti_vehicle": 4,
            "anti_fortification": 4,
        },
    ),
    "000008976004": EnhancementToolDescriptor(
        enhancement_id="000008976004",
        name="Ironbound Enmity",
        timing="passive",
        target="bearer_attacks",
        duration="constant_conditional",
        effect="bearer_wound_roll_bonus_while_within_objective_range",
        effect_params={
            "wound_roll_bonus": 1,
            "requires_within_objective_range": True,
        },
    ),
    "000008976005": EnhancementToolDescriptor(
        enhancement_id="000008976005",
        name="Warp Tracer",
        timing="post_shoot_after_bearer_attacks",
        target="hit_enemy_unit",
        duration="until_end_of_phase",
        effect="post_shoot_select_hit_enemy_loses_cover",
        effect_params={
            "attack_type": "ranged",
            "requires_bearer_hit_target": True,
            "expires_timing": "phase_end",
        },
    ),
}

_FELLHAMMER_SIEGE_HOST_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _FELLHAMMER_SIEGE_HOST_DESCRIPTORS.values()
}

_NIGHTMARE_HUNT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010641002": EnhancementToolDescriptor(
        enhancement_id="000010641002",
        name="Greyveil Hex",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_gains_stealth_and_objective_controlled_ranged_targeting_cap",
        effect_params={
            "grants_stealth": True,
            "ranged_targeting_max_distance": 18,
            "requires_bearer_alive": True,
            "requires_bearer_unit_within_controlled_objective_range": True,
        },
    ),
    "000010641003": EnhancementToolDescriptor(
        enhancement_id="000010641003",
        name="Warp-fuelled Thrusters",
        timing="end_of_opponent_fight_phase",
        target="bearer_unit",
        duration="instant",
        effect="end_of_opponent_fight_phase_enter_strategic_reserves_if_not_engaged",
        effect_params={
            "requires_not_engagement_range": True,
            "requires_bearer_alive": True,
            "once_per_battle": False,
            "ability_key": "warp_fuelled_thrusters",
            "trigger_phase": "OPPONENT_FIGHT_PHASE_END",
        },
    ),
    "000010641004": EnhancementToolDescriptor(
        enhancement_id="000010641004",
        name="Terrorglut Parasite",
        timing="start_of_fight_phase",
        target="enemy_units_in_engagement_range_of_bearer",
        duration="instant",
        effect="start_of_fight_phase_bearer_engagement_range_enemy_battleshock_minus_one",
        effect_params={
            "battle_shock_test_modifier": -1,
            "requires_bearer_alive": True,
        },
    ),
    "000010641005": EnhancementToolDescriptor(
        enhancement_id="000010641005",
        name="Sorrowscent Vulture",
        timing="passive_and_declare_battle_formations_attachment_override",
        target="bearer_unit_and_bearer",
        duration="constant_and_declare_battle_formations",
        effect="grant_scouts_to_bearer_unit_and_allow_attach_to_warp_talons",
        effect_params={
            "scouts_distance": 6,
            "requires_bearer_alive": True,
            "attachment_override_unit_names_any": ("Warp Talons",),
            "attachment_override_unit_datasheet_ids_any": ("000000959",),
        },
    ),
}

_NIGHTMARE_HUNT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NIGHTMARE_HUNT_DESCRIPTORS.values()
}

_PACTBOUND_ZEALOTS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008357002": EnhancementToolDescriptor(
        enhancement_id="000008357002",
        name="Eye of Tzeentch",
        timing="after_dark_pact_leadership_test",
        target="bearer",
        duration="instant",
        effect="gain_cp_on_dark_pact_passed_modified_roll_threshold",
        effect_params={
            "modified_roll_threshold": 8,
            "cp_gain": 1,
            "requires_dark_pact_passed": True,
            "requires_bearer_alive": True,
            "requires_bearer_on_battlefield": True,
        },
    ),
    "000008357003": EnhancementToolDescriptor(
        enhancement_id="000008357003",
        name="Intoxicating Elixir",
        timing="passive_and_after_bearer_shoots_or_fights",
        target="bearer_and_one_enemy_unit_hit_by_bearer",
        duration="constant_and_instant",
        effect="bearer_gains_fnp_and_post_attack_select_hit_enemy_battleshock_test_on_passed_dark_pact",
        effect_params={
            "fnp": 5,
            "applies_after_fight": True,
            "requires_bearer_hit_target": True,
            "requires_dark_pact_passed": True,
        },
    ),
    "000008357004": EnhancementToolDescriptor(
        enhancement_id="000008357004",
        name="Orbs of Unlife",
        timing="end_of_fight_phase",
        target="enemy_units_within_range_of_bearer",
        duration="instant",
        effect="roll_for_each_enemy_within_range_mortal_wounds_with_dark_pact_threshold_bonus",
        range_in=3.0,
        effect_params={
            "roll": "D6",
            "base_threshold": 4,
            "threshold_if_dark_pact_passed": 3,
            "mortal_wounds": "D3",
            "requires_dark_pact_passed_for_threshold_bonus": True,
        },
    ),
    "000008357005": EnhancementToolDescriptor(
        enhancement_id="000008357005",
        name="Talisman of Burning Blood",
        timing="passive_and_after_dark_pact_leadership_test",
        target="bearer_melee_weapons",
        duration="constant_and_until_end_of_current_phase",
        effect="bearer_melee_attacks_strength_bonus_replaced_by_dark_pact_roll",
        effect_params={
            "base_attacks_bonus": 1,
            "base_strength_bonus": 1,
            "dark_pact_roll": "D3",
            "requires_dark_pact_passed": True,
        },
    ),
}

_PACTBOUND_ZEALOTS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _PACTBOUND_ZEALOTS_DESCRIPTORS.values()
}

_SOULFORGED_WARPACK_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008985002": EnhancementToolDescriptor(
        enhancement_id="000008985002",
        name="Forge's Blessing",
        timing="start_of_command_phase",
        target="friendly_heretic_astartes_vehicle_unit_within_range_of_bearer",
        duration="until_start_of_next_owner_command_phase",
        effect="select_vehicle_unit_gain_fnp",
        range_in=12.0,
        effect_params={
            "fnp": 6,
            "required_target_keyword": "VEHICLE",
            "required_target_faction_keyword": "HERETIC ASTARTES",
        },
    ),
    "000008985003": EnhancementToolDescriptor(
        enhancement_id="000008985003",
        name="Invigorated Mechatendrils",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_move_bonus",
        effect_params={"move_bonus": 4},
    ),
    "000008985004": EnhancementToolDescriptor(
        enhancement_id="000008985004",
        name="Tempting Addendum",
        timing="on_contract_invoked_within_range_of_bearer",
        target="friendly_heretic_astartes_daemon_vehicle_unit",
        duration="until_end_of_phase",
        effect="contract_failure_mortal_wound_bonus_and_attack_hit_reroll",
        range_in=3.0,
        effect_params={
            "required_target_keywords_all": ("HERETIC ASTARTES", "DAEMON", "VEHICLE"),
            "dark_pact_failure_mortal_wound_bonus": 1,
            "reroll_hit": True,
        },
    ),
    "000008985005": EnhancementToolDescriptor(
        enhancement_id="000008985005",
        name="Soul Harvester",
        timing="any_phase_on_enemy_unit_destroyed_within_range_of_bearer",
        target="army",
        duration="constant_while_bearer_on_battlefield",
        effect="gain_cp_on_destroyed_enemy_unit_within_range",
        range_in=12.0,
        effect_params={
            "success_on": 5,
            "cp_gain": 1,
            "requires_bearer_on_battlefield": True,
        },
    ),
}

_SOULFORGED_WARPACK_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SOULFORGED_WARPACK_DESCRIPTORS.values()
}

_VETERANS_OF_THE_LONG_WAR_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008960002": EnhancementToolDescriptor(
        enhancement_id="000008960002",
        name="Eager for Vengeance",
        timing="passive",
        target="bearer_unit",
        duration="constant_conditional",
        effect="fallback_shoot_charge_and_focus_bonuses_after_fall_back",
        effect_params={
            "allow_shoot_after_fall_back": True,
            "allow_charge_after_fall_back": True,
            "requires_focus_of_hatred_target": True,
            "requires_unit_fell_back_this_turn_for_hit_bonus": True,
            "focus_hit_roll_bonus": 1,
            "focus_charge_roll_bonus": 1,
        },
    ),
    "000008960003": EnhancementToolDescriptor(
        enhancement_id="000008960003",
        name="Eye of Abaddon",
        timing="any_phase_on_focus_of_hatred_destroyed",
        target="army",
        duration="constant_conditional",
        effect="gain_cp_on_focus_of_hatred_destroyed",
        effect_params={
            "requires_bearer_on_battlefield": True,
            "success_on": 4,
            "cp_gain": 1,
        },
    ),
    "000008960004": EnhancementToolDescriptor(
        enhancement_id="000008960004",
        name="Mark of Legend",
        timing="on_bearer_hit_wound_or_save_roll",
        target="bearer",
        duration="constant",
        effect="once_per_turn_reroll_hit_wound_or_save_for_bearer",
        effect_params={
            "once_per_turn": True,
            "allow_hit_reroll": True,
            "allow_wound_reroll": True,
            "allow_save_reroll": True,
        },
    ),
    "000008960005": EnhancementToolDescriptor(
        enhancement_id="000008960005",
        name="Warmaster's Gift",
        timing="on_bearer_wound_roll",
        target="bearer_attacks_vs_focus_of_hatred",
        duration="constant_conditional",
        effect="focus_of_hatred_wound_roll_critical_on_5_plus_for_bearer",
        effect_params={
            "requires_focus_of_hatred_target": True,
            "critical_wound_threshold": 5,
        },
    ),
}

_VETERANS_OF_THE_LONG_WAR_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _VETERANS_OF_THE_LONG_WAR_DESCRIPTORS.values()
}

_COVENITE_COTERIE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010584002": EnhancementToolDescriptor(
        enhancement_id="000010584002",
        name="Master Regenesist",
        timing="on_bearer_fleshcraft_use",
        target="bearer_unit",
        duration="instant",
        effect="fleshcraft_optional_return_up_to_d3_plus_3_instead_of_d3_plus_1",
        effect_params={
            "optional": True,
            "base_return_roll": "D3+1",
            "enhanced_return_roll": "D3+3",
        },
    ),
    "000010584003": EnhancementToolDescriptor(
        enhancement_id="000010584003",
        name="Master Nemesine",
        timing="passive",
        target="bearer_weapons",
        duration="constant",
        effect="grant_bearer_weapon_anti_beast_and_monster",
        effect_params={"anti_beast": 2, "anti_monster": 4},
    ),
    "000010584004": EnhancementToolDescriptor(
        enhancement_id="000010584004",
        name="Master Artisan",
        timing="passive",
        target="bearer_and_bearer_unit_models",
        duration="constant",
        effect="bearer_wounds_and_bearer_unit_toughness_bonus",
        effect_params={"bearer_wounds_bonus": 1, "bearer_unit_toughness_bonus": 1},
    ),
    "000010584005": EnhancementToolDescriptor(
        enhancement_id="000010584005",
        name="Master Repugnomancer (Aura)",
        timing="passive_aura_and_on_friendly_battleshock_fail_or_destroyed",
        target="friendly_drukhari_units_within_9_of_bearer",
        duration="constant",
        effect="fear_incarnate_range_bonus_and_pain_token_on_friendly_battleshock_fail_or_destroyed",
        effect_params={
            "fear_incarnate_range_bonus": 3,
            "trigger_range": 9,
            "success_on": 4,
            "pain_tokens_gained": 1,
        },
    ),
}

_COVENITE_COTERIE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _COVENITE_COTERIE_DESCRIPTORS.values()
}

_REALSPACE_RAIDERS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010574002": EnhancementToolDescriptor(
        enhancement_id="000010574002",
        name="Dark Vitality",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_always_empowered_no_pain_token_cost",
        effect_params={
            "always_empowered": True,
            "pain_token_cost": 0,
        },
    ),
    "000010574003": EnhancementToolDescriptor(
        enhancement_id="000010574003",
        name="Labyrinthine Cunning",
        timing="start_of_friendly_command_phase",
        target="bearer",
        duration="instant_optional",
        effect="command_phase_choice_spend_pain_token_for_cp_or_roll_for_cp",
        effect_params={
            "pain_token_cost": 1,
            "cp_gain": 1,
            "roll": "D6",
            "success_on": 4,
            "optional": True,
        },
    ),
    "000010574004": EnhancementToolDescriptor(
        enhancement_id="000010574004",
        name="Eye of Spite",
        timing="passive_and_fight_unit_selected",
        target="bearer_melee_weapons",
        duration="constant_and_until_end_of_phase",
        effect="improve_bearer_melee_attacks_and_ap_by_1_and_optional_plus_2_instead_with_pain_token",
        effect_params={
            "base_attacks_bonus": 1,
            "base_ap_bonus": 1,
            "empowered_attacks_bonus": 2,
            "empowered_ap_bonus": 2,
            "pain_token_cost": 1,
            "optional": True,
        },
    ),
    "000010574005": EnhancementToolDescriptor(
        enhancement_id="000010574005",
        name="Crucible of Malediction",
        timing="friendly_shooting_phase_once_per_battle",
        target="enemy_units_within_12_of_bearer",
        duration="instant",
        effect="enemy_units_within_12_take_battleshock_optional_pain_token_modifier_and_psyker_fail_mortal_wounds",
        once_per_battle=True,
        effect_params={
            "range": 12.0,
            "pain_token_cost": 1,
            "battle_shock_test_modifier_if_spent": -1,
            "psyker_fail_mortal_wounds": 3,
            "optional": True,
        },
    ),
}

_REALSPACE_RAIDERS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _REALSPACE_RAIDERS_DESCRIPTORS.values()
}

_REAPERS_WAGER_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009781002": EnhancementToolDescriptor(
        enhancement_id="000009781002",
        name="Archraider",
        timing="declare_battle_formations",
        target="dedicated_transport_with_bearer_embarked",
        duration="scout_step",
        effect="grant_scouts_if_bearer_starts_embarked",
        effect_params={"scouts_distance": 9.0},
    ),
    "000009781003": EnhancementToolDescriptor(
        enhancement_id="000009781003",
        name="Webway Walker",
        timing="passive_and_on_unit_set_up_via_deep_strike",
        target="bearer_unit",
        duration="constant_and_until_end_of_turn_on_trigger",
        effect="grant_deep_strike_and_charge_reroll_if_losing_wager_on_deep_strike_setup",
        effect_params={
            "grants_deep_strike": True,
            "requires_losing_wager_at_setup": True,
            "charge_reroll_duration": "until_end_of_turn",
        },
    ),
    "000009781004": EnhancementToolDescriptor(
        enhancement_id="000009781004",
        name="Reaper's Cowl",
        timing="passive",
        target="bearer_unit_models",
        duration="constant",
        effect="grant_stealth_and_infiltrators_to_bearer_unit_models",
        effect_params={
            "grants_stealth": True,
            "grants_infiltrators": True,
        },
    ),
    "000009781005": EnhancementToolDescriptor(
        enhancement_id="000009781005",
        name="Conductor of Torment",
        timing="friendly_command_phase",
        target="army_wager_state",
        duration="instant_optional",
        effect="optional_switch_wager_winner_with_pain_token_exchange",
        effect_params={
            "gain_pain_tokens_if_drukhari_losing": 1,
            "switch_to_drukhari_when_losing": True,
            "spend_pain_token_cost_if_drukhari_winning": 1,
            "switch_to_harlequins_when_winning": True,
            "optional": True,
        },
    ),
}

_REAPERS_WAGER_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _REAPERS_WAGER_DESCRIPTORS.values()
}

_KABALITE_CARTEL_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010588002": EnhancementToolDescriptor(
        enhancement_id="000010588002",
        name="Leechbite Plate",
        timing="start_of_either_command_phase",
        target="bearer",
        duration="constant_and_optional_instant",
        effect="set_bearer_save_to_3_plus_and_optional_full_heal_spend_pain_token",
        effect_params={
            "save_characteristic": 3,
            "pain_token_cost": 1,
            "heal_lost_wounds": "all",
            "requires_wounded_bearer": True,
        },
    ),
    "000010588003": EnhancementToolDescriptor(
        enhancement_id="000010588003",
        name="Webway Awl",
        timing="passive_and_stratagem_targeting",
        target="bearer_unit",
        duration="constant",
        effect="grant_deep_strike_and_rapid_ingress_zero_cp",
        effect_params={
            "grants_deep_strike": True,
            "stratagem_name": "RAPID INGRESS",
            "cp_reduction": "to_zero",
        },
    ),
    "000010588004": EnhancementToolDescriptor(
        enhancement_id="000010588004",
        name="Informant Network",
        timing="declare_battle_formations_start",
        target="up_to_three_friendly_kabalite_warriors_or_hand_of_the_archon_units",
        duration="battle",
        effect="select_up_to_three_units_gain_infiltrators",
        effect_params={
            "max_units": 3,
            "eligible_unit_name_patterns": ("KABALITE WARRIORS", "HAND OF THE ARCHON"),
        },
    ),
    "000010588005": EnhancementToolDescriptor(
        enhancement_id="000010588005",
        name="Towering Arrogance",
        timing="passive_while_bearer_leading",
        target="models_in_bearer_unit",
        duration="while_bearer_is_leading",
        effect="leadership_and_objective_control_improve_by_1",
        effect_params={
            "leadership_improvement": 1,
            "objective_control_bonus": 1,
        },
    ),
}

_KABALITE_CARTEL_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _KABALITE_CARTEL_DESCRIPTORS.values()
}

_SPECTACLE_OF_SPITE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010580002": EnhancementToolDescriptor(
        enhancement_id="000010580002",
        name="Pharmacophex",
        timing="command_phase_start_after_combat_drugs_selection",
        target="bearer_unit",
        duration="until_next_command_phase",
        effect="extra_combat_drug_roll_for_bearer_unit",
        effect_params={"roll": "D6", "ignore_if_drug_already_active_army_wide": True},
    ),
    "000010580003": EnhancementToolDescriptor(
        enhancement_id="000010580003",
        name="Chronoshard",
        timing="start_of_fight_phase",
        target="bearer_unit",
        duration="until_end_of_phase",
        effect="fights_first",
        once_per_battle=True,
    ),
    "000010580004": EnhancementToolDescriptor(
        enhancement_id="000010580004",
        name="Periapt of Torments",
        timing="passive",
        target="enemy_units_targeting_bearer_unit",
        duration="constant",
        effect="prevent_overwatch_against_bearer_unit",
    ),
    "000010580005": EnhancementToolDescriptor(
        enhancement_id="000010580005",
        name="Morghenna's Curse",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_ap_damage_bonus",
        effect_params={"ap_bonus": 1, "damage_bonus": 1},
    ),
}

_SPECTACLE_OF_SPITE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPECTACLE_OF_SPITE_DESCRIPTORS.values()
}

_SKYSPLINTER_ASSAULT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010576002": EnhancementToolDescriptor(
        enhancement_id="000010576002",
        name="Phantasmal Smoke",
        timing="passive_while_bearer_unit_wholly_within_friendly_transport_range",
        target="bearer_unit",
        duration="while_condition_met",
        effect="grant_stealth_and_benefit_of_cover_while_wholly_within_range_of_friendly_transport",
        effect_params={
            "range": 6.0,
            "requires_friendly_transport": True,
            "requires_wholly_within": True,
            "grants_stealth": True,
            "grants_benefit_of_cover_vs_ranged": True,
        },
    ),
    "000010576003": EnhancementToolDescriptor(
        enhancement_id="000010576003",
        name="Sadistic Fulcrum",
        timing="on_bearer_unit_empower_in_shooting_phase",
        target="friendly_drukhari_transport_within_6_of_bearer_unit",
        duration="until_end_of_phase",
        effect="optional_select_transport_reroll_hit_when_bearer_unit_empowered",
        effect_params={
            "trigger_phase": "shooting",
            "range": 6.0,
            "requires_friendly_transport": True,
            "optional_selection_with_none": True,
            "grants_hit_reroll": True,
        },
    ),
    "000010576004": EnhancementToolDescriptor(
        enhancement_id="000010576004",
        name="Spiteful Raider",
        timing="on_enemy_unit_destroyed_in_fight_phase_by_bearer_unit",
        target="destroyed_enemy_unit_that_was_within_objective_when_bearer_unit_selected_to_fight",
        duration="instant",
        effect="gain_additional_pain_token_if_destroyed_unit_was_within_objective_when_selected_to_fight",
        effect_params={
            "pain_tokens_gained": 1,
            "requires_fight_phase": True,
            "requires_destroyed_unit_within_objective_when_selected_to_fight": True,
        },
    ),
    "000010576005": EnhancementToolDescriptor(
        enhancement_id="000010576005",
        name="Nightmare Shroud",
        timing="on_bearer_unit_disembark",
        target="enemy_units_targeting_bearer_unit",
        duration="until_end_of_turn",
        effect="prevent_overwatch_against_bearer_unit_after_disembark",
        effect_params={
            "trigger": "disembark",
            "prevents_stratagem": "FIRE OVERWATCH",
        },
    ),
}

_SKYSPLINTER_ASSAULT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SKYSPLINTER_ASSAULT_DESCRIPTORS.values()
}

_COURT_OF_THE_PHOENICIAN_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010654002": EnhancementToolDescriptor(
        enhancement_id="000010654002",
        name="Tears of the Phoenix",
        timing="passive",
        target="bearer_unit_melee_attacks",
        duration="constant",
        effect="ignore_melee_ws_hit_wound_modifiers",
        effect_params={
            "ignore_weapon_skill_modifiers": True,
            "ignore_hit_roll_modifiers": True,
            "ignore_wound_roll_modifiers": True,
        },
    ),
    "000010654003": EnhancementToolDescriptor(
        enhancement_id="000010654003",
        name="Exalted Patron",
        timing="declare_battle_formations",
        target="bearer",
        duration="battle_setup_and_constant",
        effect="bearer_move_bonus_and_attach_to_flawless_blades",
        effect_params={"move_bonus": 1},
    ),
    "000010654004": EnhancementToolDescriptor(
        enhancement_id="000010654004",
        name="Soulstain Made Manifest",
        timing="start_of_fight_phase",
        target="enemy_unit_within_engagement_range_of_bearer",
        duration="instant",
        effect="optional_battleshock_test_with_modifier",
        effect_params={"test_modifier": -1, "optional": True},
    ),
    "000010654005": EnhancementToolDescriptor(
        enhancement_id="000010654005",
        name="Spiritsliver",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_strength_attacks_bonus",
        effect_params={"strength_bonus": 1, "attacks_bonus": 1},
    ),
}

_COURT_OF_THE_PHOENICIAN_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _COURT_OF_THE_PHOENICIAN_DESCRIPTORS.values()
}

_SLAANESHS_CHOSEN_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010018002": EnhancementToolDescriptor(
        enhancement_id="000010018002",
        name="Eager to Prove",
        timing="passive_and_while_favoured_champions",
        target="bearer_unit",
        duration="constant_conditional",
        effect="charge_reroll_and_favoured_move_bonus",
        effect_params={"charge_reroll": True, "favoured_move_bonus": 2},
    ),
    "000010018003": EnhancementToolDescriptor(
        enhancement_id="000010018003",
        name="Repulsed by Weakness",
        timing="enemy_fall_back_within_engagement_range",
        target="enemy_unit",
        duration="instant",
        effect="force_desperate_escape_and_favoured_test_penalty",
        effect_params={
            "exclude_monsters_vehicles": True,
            "favoured_desperate_escape_penalty": 1,
        },
    ),
    "000010018004": EnhancementToolDescriptor(
        enhancement_id="000010018004",
        name="Proud and Vainglorious",
        timing="passive_and_while_favoured_champions",
        target="bearer_unit",
        duration="constant_conditional",
        effect="leadership_battleshock_rerolls_and_favoured_oc_bonus",
        effect_params={
            "reroll_tests": ("battle_shock", "leadership"),
            "favoured_objective_control_bonus": 1,
        },
    ),
    "000010018005": EnhancementToolDescriptor(
        enhancement_id="000010018005",
        name="Slayer of Champions",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant_conditional",
        effect="bearer_melee_precision_and_character_target_strength_ap_bonus",
        effect_params={
            "precision": True,
            "character_target_strength_bonus": 1,
            "character_target_ap_bonus": 1,
        },
    ),
}

_SLAANESHS_CHOSEN_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SLAANESHS_CHOSEN_DESCRIPTORS.values()
}

_COTERIE_OF_CONCEITED_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010014002": EnhancementToolDescriptor(
        enhancement_id="000010014002",
        name="Pledge of Eternal Servitude",
        timing="on_bearer_destroyed_first_time",
        target="bearer",
        duration="end_of_phase",
        effect="return_on_death_on_leadership_test",
        effect_params={
            "leadership_test": True,
            "return_wounds": "D6",
            "first_time_only": True,
            "set_up_not_in_engagement_range": True,
        },
    ),
    "000010014003": EnhancementToolDescriptor(
        enhancement_id="000010014003",
        name="Pledge of Dark Glory",
        timing="passive_while_leading",
        target="bearer_unit",
        duration="constant",
        effect="leadership_and_objective_control_bonus",
        effect_params={"leadership_bonus": 1, "objective_control_bonus": 1},
    ),
    "000010014004": EnhancementToolDescriptor(
        enhancement_id="000010014004",
        name="Pledge of Mortal Pain",
        timing="start_of_shooting_phase",
        target="enemy_unit_within_range_visible",
        duration="instant",
        effect="leadership_test_then_mortal_wounds",
        range_in=12.0,
        effect_params={"test_modifier_if_battle_shocked": -2, "mortal_wounds_on_fail": 3},
    ),
    "000010014005": EnhancementToolDescriptor(
        enhancement_id="000010014005",
        name="Pledge of Unholy Fortune",
        timing="after_roll_once_per_turn",
        target="bearer_unit",
        duration="instant",
        effect="set_roll_to_unmodified_six",
        effect_params={
            "roll_types": ("hit", "wound", "save"),
            "usage_limit": "turn",
            "requires_bearer_not_battle_shocked": True,
        },
    ),
}

_COTERIE_OF_CONCEITED_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _COTERIE_OF_CONCEITED_DESCRIPTORS.values()
}

_CARNIVAL_OF_EXCESS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010010002": EnhancementToolDescriptor(
        enhancement_id="000010010002",
        name="Empyric Suffusion",
        timing="when_targeting_friendly_unit_with_heroic_intervention",
        target="friendly_slaanesh_unit_within_range_of_bearer",
        duration="instant",
        effect="heroic_intervention_cp_set_zero",
        range_in=6.0,
        effect_params={"usage_limit": "battle_round"},
    ),
    "000010010003": EnhancementToolDescriptor(
        enhancement_id="000010010003",
        name="Dark Blessings",
        timing="after_enemy_selects_targets",
        target="bearer",
        duration="until_end_of_phase",
        effect="set_temporary_invulnerable_save",
        once_per_battle=True,
        effect_params={"invulnerable_save": 3},
    ),
    "000010010004": EnhancementToolDescriptor(
        enhancement_id="000010010004",
        name="Possessed Blade",
        timing="start_of_battle_and_when_selected_to_fight",
        target="bearer_selected_melee_weapon",
        duration="constant_and_until_end_of_fight_activation",
        effect="selected_weapon_attacks_bonus_and_fight_activation_damage_devastating_hazardous",
        effect_params={"attacks_bonus": 1, "fight_activation_damage_bonus": 1},
    ),
    "000010010005": EnhancementToolDescriptor(
        enhancement_id="000010010005",
        name="Warp Walker",
        timing="passive_on_move_and_advance",
        target="bearer_unit",
        duration="constant",
        effect="advance_no_roll_and_move_through_enemy_models",
        effect_params={
            "advance_distance_bonus": 6,
            "move_types": ("move", "advance", "fall_back"),
            "can_move_within_engagement_range": True,
            "cannot_end_in_engagement_range": True,
            "auto_pass_desperate_escape": True,
        },
    ),
}

_CARNIVAL_OF_EXCESS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CARNIVAL_OF_EXCESS_DESCRIPTORS.values()
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

_SHADOW_LEGION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009980002": EnhancementToolDescriptor(
        enhancement_id="000009980002",
        name="Leaping Shadows",
        timing="declare_battle_formations",
        target="bearer_unit",
        duration="scout_step",
        effect="grant_scouts",
        effect_params={"scouts_distance": 9},
    ),
    "000009980003": EnhancementToolDescriptor(
        enhancement_id="000009980003",
        name="Mantle of Gloom (Aura)",
        timing="passive_aura",
        target="enemy_unit_within_engagement_range_of_bearer_unit",
        duration="constant",
        effect="enemy_objective_control_penalty",
        effect_params={"objective_control_penalty": 1},
    ),
    "000009980004": EnhancementToolDescriptor(
        enhancement_id="000009980004",
        name="Fade to Darkness",
        timing="end_of_fight_phase",
        target="bearer_unit",
        duration="instant_optional",
        effect="enter_strategic_reserves_if_destroyed_enemy_and_not_engaged",
        effect_params={"requires_destroyed_enemy_this_phase": True, "requires_not_in_engagement_range": True},
    ),
    "000009980005": EnhancementToolDescriptor(
        enhancement_id="000009980005",
        name="Malice Made Manifest",
        timing="start_of_fight_phase",
        target="enemy_unit_within_engagement_range_of_bearer_unit",
        duration="instant",
        effect="select_enemy_then_roll_mortal_wounds",
        effect_params={
            "roll": "D6",
            "threshold_mid_min": 2,
            "threshold_mid_max": 5,
            "mortal_mid": "D3",
            "threshold_high": 6,
            "mortal_high": 3,
        },
    ),
}

_SHADOW_LEGION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SHADOW_LEGION_DESCRIPTORS.values()
}

_BLOOD_LEGION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009815002": EnhancementToolDescriptor(
        enhancement_id="000009815002",
        name="Slaughterthirst (Aura)",
        timing="passive_aura",
        target="friendly_khorne_legiones_daemonica_units_within_range_excluding_monsters",
        duration="constant",
        effect="grant_weapon_keywords",
        range_in=6.0,
        effect_params={
            "attack_type": "melee",
            "keywords": ("LANCE",),
            "required_keywords_all": ("LEGIONES DAEMONICA", "KHORNE"),
            "excluded_keywords_any": ("MONSTER",),
        },
    ),
    "000009815003": EnhancementToolDescriptor(
        enhancement_id="000009815003",
        name="Fury's Cage",
        timing="when_selected_to_fight",
        target="bearer",
        duration="until_end_of_phase",
        effect="optional_self_mortal_then_full_hit_wound_rerolls",
        effect_params={
            "self_mortal_wounds_roll": "D3+1",
            "attack_type": "melee",
            "reroll_hit": "full",
            "reroll_wound": "full",
            "optional": True,
        },
    ),
    "000009815004": EnhancementToolDescriptor(
        enhancement_id="000009815004",
        name="Brazenmaw",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="charge_roll_bonus",
        effect_params={"charge_roll_bonus": 2},
    ),
    "000009815005": EnhancementToolDescriptor(
        enhancement_id="000009815005",
        name="Gateway Unto Damnation",
        timing="on_bearer_destroyed_and_on_enemy_unit_destroyed_by_bearer",
        target="bearer",
        duration="battle",
        effect="deadly_demise_trigger_and_damage_override_after_kill",
        effect_params={
            "trigger_roll": "D6",
            "success_on": 2,
            "base_damage_after_kill": "D3+3",
            "requires_destroyed_enemy_units_this_battle": 1,
        },
    ),
}

_BLOOD_LEGION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _BLOOD_LEGION_DESCRIPTORS.values()
}

_SPACE_MARINES_FIRST_COMPANY_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008494002": EnhancementToolDescriptor(
        enhancement_id="000008494002",
        name="The Imperium's Sword",
        timing="passive_and_start_of_any_phase_optional",
        target="bearer_and_bearer_unit_other_models",
        duration="constant_and_until_end_of_phase_once_per_battle",
        effect="bearer_melee_attacks_bonus_and_once_per_battle_unit_other_models_melee_attacks_bonus",
        once_per_battle=True,
        effect_params={
            "bearer_melee_attacks_bonus": 1,
            "unit_other_models_melee_attacks_bonus": 1,
            "once_per_battle_key": "the_imperiums_sword",
        },
    ),
    "000008494003": EnhancementToolDescriptor(
        enhancement_id="000008494003",
        name="Fear Made Manifest (Aura)",
        timing="on_enemy_battleshock_fail_within_aura",
        target="enemy_non_monster_non_vehicle_unit_within_range_of_bearer",
        duration="instant_and_once_per_battle_upgrade",
        effect="destroy_models_on_battleshock_fail_with_once_per_battle_d3_upgrade",
        range_in=6.0,
        once_per_battle=True,
        effect_params={
            "range": 6.0,
            "exclude_keywords_any": ("MONSTER", "VEHICLE"),
            "base_models_destroyed": 1,
            "once_per_battle_models_destroyed_roll": "D3",
            "once_per_battle_key": "fear_made_manifest",
        },
    ),
    "000008494004": EnhancementToolDescriptor(
        enhancement_id="000008494004",
        name="Rites of War",
        timing="passive_and_start_of_any_phase_optional",
        target="bearer_and_bearer_unit_other_models",
        duration="constant_and_until_end_of_phase_once_per_battle",
        effect="bearer_objective_control_bonus_and_once_per_battle_unit_other_models_objective_control_bonus",
        once_per_battle=True,
        effect_params={
            "bearer_objective_control_bonus": 1,
            "unit_other_models_objective_control_bonus": 1,
            "once_per_battle_key": "rites_of_war",
        },
    ),
    "000008494005": EnhancementToolDescriptor(
        enhancement_id="000008494005",
        name="Iron Resolve",
        timing="passive_and_when_targeted_optional",
        target="bearer_and_bearer_unit",
        duration="constant_and_until_end_of_phase_once_per_battle",
        effect="bearer_fnp_and_once_per_battle_targeted_unit_fnp",
        once_per_battle=True,
        effect_params={
            "bearer_fnp": 5,
            "trigger": "unit_targeted_by_attacks",
            "unit_fnp_on_trigger": 5,
            "once_per_battle_key": "iron_resolve",
        },
    ),
}

_SPACE_MARINES_FIRST_COMPANY_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_FIRST_COMPANY_TASK_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_ANGELIC_INHERITORS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009835002": EnhancementToolDescriptor(
        enhancement_id="000009835002",
        name="Prescient Flash",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_scouts_to_bearer_unit",
        effect_params={"scouts_distance": 6},
    ),
    "000009835003": EnhancementToolDescriptor(
        enhancement_id="000009835003",
        name="Troubling Visions",
        timing="command_phase_optional",
        target="bearer_unit",
        duration="until_start_of_next_command_phase",
        effect="once_per_battle_activate_all_angelic_legacy_for_bearer_unit",
        once_per_battle=True,
        effect_params={"once_per_battle_key": "troubling_visions"},
    ),
    "000009835004": EnhancementToolDescriptor(
        enhancement_id="000009835004",
        name="Blazing Icon",
        timing="passive",
        target="enemy_units_targeting_bearer_unit_with_fire_overwatch",
        duration="constant",
        effect="prevent_fire_overwatch_against_bearer_unit",
        effect_params={"stratagem_name": "Fire Overwatch"},
    ),
    "000009835005": EnhancementToolDescriptor(
        enhancement_id="000009835005",
        name="Ordained Sacrifice",
        timing="on_bearer_destroyed",
        target="bearer",
        duration="resolve_at_end_of_phase_first_time",
        effect="return_bearer_on_2plus_with_fixed_wounds",
        once_per_battle=True,
        effect_params={
            "roll_min": 2,
            "wounds_on_return": 3,
            "return_on_death_key": "ordained_sacrifice",
        },
    ),
}

_SPACE_MARINES_ANGELIC_INHERITORS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_ANGELIC_INHERITORS_DESCRIPTORS.values()
}

_SPACE_MARINES_THE_ANGELIC_HOST_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009190002": EnhancementToolDescriptor(
        enhancement_id="000009190002",
        name="Artisan of War",
        timing="passive",
        target="bearer_weapons_and_bearer",
        duration="constant",
        effect="improve_bearer_weapon_ap_and_set_bearer_save",
        effect_params={
            "bearer_weapon_ap_bonus": 1,
            "save_characteristic": 2,
        },
    ),
    "000009190003": EnhancementToolDescriptor(
        enhancement_id="000009190003",
        name="Visage of Death",
        timing="opponent_command_phase_battleshock_step",
        target="enemy_non_monster_non_vehicle_units_within_engagement_range_of_bearer",
        duration="instant_each_opponent_command_phase",
        effect="force_battleshock_for_enemy_units_within_bearer_engagement_range",
        effect_params={
            "exclude_keywords_any": ("MONSTER", "VEHICLE"),
        },
    ),
    "000009190004": EnhancementToolDescriptor(
        enhancement_id="000009190004",
        name="Archangel's Shard",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="grant_bearer_melee_anti_chaos_and_lance",
        effect_params={
            "anti_keyword": "CHAOS",
            "anti_value": 5,
            "keywords": ("LANCE",),
        },
    ),
    "000009190005": EnhancementToolDescriptor(
        enhancement_id="000009190005",
        name="Gleaming Pinions",
        timing="on_enemy_move_ended_within_range",
        target="bearer_unit",
        duration="instant_once_per_turn",
        effect="once_per_turn_reactive_normal_move_if_not_engaged",
        effect_params={
            "trigger_range": 9,
            "max_reactive_move_distance": 6,
            "trigger_actions": ("move", "advance", "fall_back"),
            "requires_not_engaged": True,
            "once_per_turn": True,
        },
    ),
}

_SPACE_MARINES_THE_ANGELIC_HOST_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_THE_ANGELIC_HOST_DESCRIPTORS.values()
}

_SPACE_MARINES_THE_LOST_BRETHREN_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009186002": EnhancementToolDescriptor(
        enhancement_id="000009186002",
        name="Sanguinius' Grace",
        timing="fight_phase_end",
        target="bearer",
        duration="instant_once_per_battle_optional",
        effect="fight_one_additional_time_if_bearer_engaged_with_three_plus_enemy_models",
        once_per_battle=True,
        effect_params={
            "min_enemy_models_in_engagement_range": 3,
            "once_per_battle_key": "sanguinius_grace",
        },
    ),
    "000009186003": EnhancementToolDescriptor(
        enhancement_id="000009186003",
        name="Blood Shard",
        timing="on_bearer_destroyed",
        target="bearer",
        duration="resolve_at_end_of_phase_first_time",
        effect="return_bearer_on_2plus_with_fixed_wounds",
        once_per_battle=True,
        effect_params={
            "roll_min": 2,
            "wounds_on_return": 3,
            "return_on_death_key": "blood_shard",
        },
    ),
    "000009186004": EnhancementToolDescriptor(
        enhancement_id="000009186004",
        name="To Slay the Warmaster",
        timing="start_of_fight_phase",
        target="enemy_character_unit_within_engagement_range_of_bearer",
        duration="instant_once_per_battle_optional",
        effect="select_character_unit_roll_six_d6_mortal_wounds_on_4plus_to_character_models",
        once_per_battle=True,
        effect_params={
            "dice_count": 6,
            "success_on": 4,
            "once_per_battle_key": "to_slay_the_warmaster",
        },
    ),
    "000009186005": EnhancementToolDescriptor(
        enhancement_id="000009186005",
        name="Vengeful Onslaught",
        timing="on_bearer_destroyed",
        target="friendly_death_company_models",
        duration="until_end_of_owners_next_turn",
        effect="hit_roll_bonus_for_friendly_death_company_models",
        effect_params={
            "hit_bonus": 1,
        },
    ),
}

_SPACE_MARINES_THE_LOST_BRETHREN_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_THE_LOST_BRETHREN_DESCRIPTORS.values()
}

_SPACE_MARINES_UNFORGIVEN_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008771002": EnhancementToolDescriptor(
        enhancement_id="000008771002",
        name="Shroud of Heroes",
        timing="on_bearer_destroyed",
        target="bearer",
        duration="resolve_at_end_of_phase_first_time",
        effect="return_bearer_on_2plus_with_fixed_wounds_or_full_if_battleshocked",
        once_per_battle=True,
        effect_params={
            "roll_min": 2,
            "wounds_on_return": 3,
            "wounds_on_return_if_battle_shocked": "full",
            "return_on_death_key": "shroud_of_heroes",
        },
    ),
    "000008771003": EnhancementToolDescriptor(
        enhancement_id="000008771003",
        name="Stubborn Tenacity",
        timing="passive_while_leading",
        target="bearer_unit_models",
        duration="constant_conditional",
        effect="add_hit_and_conditional_wound_bonus_while_below_starting_strength",
        effect_params={
            "hit_bonus": 1,
            "wound_bonus_if_battle_shocked": 1,
            "requires_below_starting_strength": True,
            "requires_bearer_leading": True,
        },
    ),
    "000008771004": EnhancementToolDescriptor(
        enhancement_id="000008771004",
        name="Weapons of the First Legion",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant_battleshock_scaled",
        effect="improve_bearer_melee_attacks_strength_damage_with_battleshock_scaling",
        effect_params={
            "base_bonus": 1,
            "battle_shocked_bonus": 2,
        },
    ),
    "000008771005": EnhancementToolDescriptor(
        enhancement_id="000008771005",
        name="Pennant of Remembrance",
        timing="passive_while_leading",
        target="bearer_unit_models",
        duration="constant_battleshock_scaled",
        effect="grant_unit_fnp_with_battleshock_scaling",
        effect_params={
            "feel_no_pain": 6,
            "feel_no_pain_if_battle_shocked": 4,
            "requires_bearer_leading": True,
        },
    ),
}

_SPACE_MARINES_UNFORGIVEN_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_UNFORGIVEN_TASK_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_ANVIL_SIEGE_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008474002": EnhancementToolDescriptor(
        enhancement_id="000008474002",
        name="Indomitable Fury",
        timing="on_bearer_destroyed",
        target="bearer",
        duration="resolve_at_end_of_phase_first_time",
        effect="return_bearer_on_2plus_with_full_wounds",
        once_per_battle=True,
        effect_params={
            "roll_min": 2,
            "wounds_on_return": "full",
            "return_on_death_key": "indomitable_fury",
        },
    ),
    "000008474003": EnhancementToolDescriptor(
        enhancement_id="000008474003",
        name="Fleet Commander",
        timing="start_of_shooting_phase_and_next_start_of_shooting_phase",
        target="battlefield_points_and_units_crossed_by_line",
        duration="two_step_once_per_battle",
        effect="pick_two_markers_then_roll_mortal_wounds_for_units_line_passes_over",
        once_per_battle=True,
        effect_params={
            "marker_range": 12.0,
            "roll_min": 3,
            "mortal_wounds_roll": "D3",
            "once_per_battle_key": "fleet_commander",
        },
    ),
    "000008474004": EnhancementToolDescriptor(
        enhancement_id="000008474004",
        name="Stoic Defender",
        timing="passive_while_leading",
        target="bearer_unit_models",
        duration="constant_conditional",
        effect="grant_fnp_on_controlled_objective_and_battleshock_oc_halving",
        effect_params={
            "feel_no_pain": 6,
            "requires_within_controlled_objective": True,
            "battle_shock_objective_control_divisor": 2,
        },
    ),
    "000008474005": EnhancementToolDescriptor(
        enhancement_id="000008474005",
        name="Architect of War",
        timing="passive_while_leading",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={
            "attack_type": "ranged",
            "keywords": ("IGNORES COVER",),
        },
    ),
}

_SPACE_MARINES_ANVIL_SIEGE_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_ANVIL_SIEGE_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_FIRESTORM_ASSAULT_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008482002": EnhancementToolDescriptor(
        enhancement_id="000008482002",
        name="Champion of Humanity",
        timing="passive_while_leading",
        target="bearer_unit_models",
        duration="constant",
        effect="ignore_characteristic_and_roll_modifiers_except_save_while_leading",
        effect_params={
            "requires_bearer_leading": True,
            "exclude_save_modifiers": True,
        },
    ),
    "000008482003": EnhancementToolDescriptor(
        enhancement_id="000008482003",
        name="War-tempered Artifice",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_strength_bonus",
        effect_params={
            "strength_bonus": 3,
        },
    ),
    "000008482004": EnhancementToolDescriptor(
        enhancement_id="000008482004",
        name="Forged in Battle",
        timing="passive_while_leading",
        target="bearer_unit_models",
        duration="constant",
        effect="leading_unit_unmodified_six_once_per_turn",
        effect_params={
            "requires_bearer_leading": True,
            "usage": "turn",
            "allowed_roll_types": ("hit", "save"),
        },
    ),
    "000008482005": EnhancementToolDescriptor(
        enhancement_id="000008482005",
        name="Adamantine Mantle",
        timing="on_attack_allocated_to_bearer",
        target="bearer",
        duration="constant",
        effect="bearer_allocated_damage_reduction_with_melta_torrent_set_one",
        effect_params={
            "damage_reduction": 1,
            "set_damage_to": 1,
            "if_weapon_keywords_any": ("MELTA", "TORRENT"),
        },
    ),
}

_SPACE_MARINES_FIRESTORM_ASSAULT_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_FIRESTORM_ASSAULT_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_FORGEFATHERS_SEEKERS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010368002": EnhancementToolDescriptor(
        enhancement_id="000010368002",
        name="Immolator",
        timing="passive",
        target="bearer_unit_torrent_weapons",
        duration="constant",
        effect="bearer_unit_torrent_attacks_bonus",
        effect_params={
            "attacks_bonus": 1,
            "requires_bearer_alive": True,
        },
    ),
    "000010368003": EnhancementToolDescriptor(
        enhancement_id="000010368003",
        name="War-tempered Artifice",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_strength_bonus",
        effect_params={
            "strength_bonus": 3,
        },
    ),
    "000010368004": EnhancementToolDescriptor(
        enhancement_id="000010368004",
        name="Forged in Battle",
        timing="passive_while_leading",
        target="bearer_unit_models",
        duration="constant",
        effect="leading_unit_unmodified_six_once_per_turn",
        effect_params={
            "requires_bearer_leading": True,
            "usage": "turn",
            "allowed_roll_types": ("hit", "save"),
        },
    ),
    "000010368005": EnhancementToolDescriptor(
        enhancement_id="000010368005",
        name="Adamantine Mantle",
        timing="on_attack_allocated_to_bearer",
        target="bearer",
        duration="constant",
        effect="bearer_allocated_damage_reduction_with_melta_torrent_set_one",
        effect_params={
            "damage_reduction": 1,
            "set_damage_to": 1,
            "if_weapon_keywords_any": ("MELTA", "TORRENT"),
        },
    ),
}

_SPACE_MARINES_FORGEFATHERS_SEEKERS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_FORGEFATHERS_SEEKERS_DESCRIPTORS.values()
}

_SPACE_MARINES_GLADIUS_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008353002": EnhancementToolDescriptor(
        enhancement_id="000008353002",
        name="Artificer Armour",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_save_and_fnp",
        effect_params={
            "save_characteristic": 2,
            "feel_no_pain": 5,
        },
    ),
    "000008353003": EnhancementToolDescriptor(
        enhancement_id="000008353003",
        name="The Honour Vehement",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant_conditional",
        effect="bearer_melee_attacks_strength_bonus_with_assault_doctrine_scaling",
        effect_params={
            "base_bonus": 1,
            "assault_doctrine_bonus": 2,
        },
    ),
    "000008353004": EnhancementToolDescriptor(
        enhancement_id="000008353004",
        name="Adept of the Codex",
        timing="start_of_command_phase_optional",
        target="bearer_unit",
        duration="until_next_command_phase",
        effect="unit_tactical_doctrine_override",
        effect_params={
            "doctrine": "TACTICAL",
            "optional": True,
        },
    ),
    "000008353005": EnhancementToolDescriptor(
        enhancement_id="000008353005",
        name="Fire Discipline",
        timing="passive_while_leading_and_doctrine_conditional",
        target="bearer_unit_ranged_weapons_and_advance_rolls",
        duration="constant_conditional",
        effect="grant_sustained_hits_and_devastator_advance_reroll",
        effect_params={
            "sustained_hits": 1,
            "requires_leading": True,
            "advance_reroll_requires_doctrine": "DEVASTATOR",
        },
    ),
}

_SPACE_MARINES_GLADIUS_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_GLADIUS_TASK_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_GODHAMMER_ASSAULT_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010400002": EnhancementToolDescriptor(
        enhancement_id="000010400002",
        name="Paragon of Fury",
        timing="passive_and_on_disembark",
        target="bearer_melee_weapons",
        duration="constant_conditional",
        effect="bearer_melee_strength_bonus_and_disembark_damage_bonus",
        effect_params={
            "strength_bonus": 2,
            "disembarked_from_transport_damage_bonus": 1,
        },
    ),
    "000010400003": EnhancementToolDescriptor(
        enhancement_id="000010400003",
        name="Battle-psalm Precentor",
        timing="on_shock_and_awe_battleshock",
        target="enemy_unit_selected_for_shock_and_awe",
        duration="instant",
        effect="shock_and_awe_battleshock_test_modifier",
        effect_params={
            "battleshock_test_modifier": -1,
        },
    ),
    "000010400004": EnhancementToolDescriptor(
        enhancement_id="000010400004",
        name="Augury Servo-host",
        timing="start_of_shooting_phase",
        target="enemy_unit_within_range_visible_to_bearer",
        duration="until_end_of_phase",
        effect="target_enemy_no_cover_until_end_of_phase",
        range_in=12.0,
        effect_params={
            "range": 12,
        },
    ),
    "000010400005": EnhancementToolDescriptor(
        enhancement_id="000010400005",
        name="Herald of Sacred Slaughter",
        timing="declare_battle_formations",
        target="dedicated_transport_with_bearer_embarked",
        duration="scout_step",
        effect="grant_scouts",
        effect_params={
            "scouts_distance": 9,
        },
    ),
}

_SPACE_MARINES_GODHAMMER_ASSAULT_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_GODHAMMER_ASSAULT_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_HAMMER_OF_AVERNII_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010623002": EnhancementToolDescriptor(
        enhancement_id="000010623002",
        name="Spiritus Ferrum",
        timing="passive_and_start_of_any_phase_optional",
        target="bearer_and_bearer_unit_other_models",
        duration="constant_and_until_end_of_phase_once_per_battle",
        effect="bearer_melee_attacks_bonus_and_once_per_battle_unit_other_models_melee_attacks_bonus",
        once_per_battle=True,
        effect_params={
            "bearer_melee_attacks_bonus": 1,
            "unit_other_models_melee_attacks_bonus": 1,
            "once_per_battle_key": "spiritus_ferrum",
        },
    ),
    "000010623003": EnhancementToolDescriptor(
        enhancement_id="000010623003",
        name="Medusan Roar (Aura)",
        timing="on_enemy_battleshock_fail_within_aura",
        target="enemy_non_monster_non_vehicle_unit_within_range_of_bearer",
        duration="instant_and_once_per_battle_upgrade",
        effect="destroy_models_on_battleshock_fail_with_once_per_battle_d3_upgrade",
        range_in=6.0,
        once_per_battle=True,
        effect_params={
            "range": 6.0,
            "exclude_keywords_any": ("MONSTER", "VEHICLE"),
            "base_models_destroyed": 1,
            "once_per_battle_models_destroyed_roll": "D3",
            "once_per_battle_key": "medusan_roar",
        },
    ),
    "000010623004": EnhancementToolDescriptor(
        enhancement_id="000010623004",
        name="Iron Laurel",
        timing="passive_and_start_of_any_phase_optional",
        target="bearer_and_bearer_unit_other_models",
        duration="constant_and_until_end_of_phase_once_per_battle",
        effect="bearer_objective_control_bonus_and_once_per_battle_unit_other_models_objective_control_bonus",
        once_per_battle=True,
        effect_params={
            "bearer_objective_control_bonus": 1,
            "unit_other_models_objective_control_bonus": 1,
            "once_per_battle_key": "iron_laurel",
        },
    ),
    "000010623005": EnhancementToolDescriptor(
        enhancement_id="000010623005",
        name="Steel Font",
        timing="command_phase_while_leading",
        target="bearer_led_unit",
        duration="instant",
        effect="return_one_destroyed_bodyguard_model",
        effect_params={
            "requires_bearer_leading": True,
            "command_phase_bodyguard_return_amount": 1,
            "ability_key": "steel_font",
        },
    ),
}

_SPACE_MARINES_HAMMER_OF_AVERNII_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_HAMMER_OF_AVERNII_DESCRIPTORS.values()
}

_SPACE_MARINES_INNER_CIRCLE_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008774002": EnhancementToolDescriptor(
        enhancement_id="000008774002",
        name="Champion of the Deathwing",
        timing="passive_and_conditional_on_vowed_objective",
        target="bearer_melee_weapons",
        duration="constant_conditional",
        effect="bearer_melee_lethal_hits_and_critical_hits_on_5plus_within_vowed_objective",
        effect_params={
            "critical_hit_threshold_within_vowed_objective": 5,
        },
    ),
    "000008774003": EnhancementToolDescriptor(
        enhancement_id="000008774003",
        name="Eye of the Unseen",
        timing="when_bearer_unit_targeted_by_stratagem",
        target="bearer_unit",
        duration="instant",
        effect="targeted_stratagem_cp_refund_with_vowed_objective_bonus",
        effect_params={
            "roll_min": 5,
            "cp_gain": 1,
            "roll_bonus_if_bearer_within_vowed_objective": 1,
        },
    ),
    "000008774004": EnhancementToolDescriptor(
        enhancement_id="000008774004",
        name="Singular Will",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_pile_in_and_consolidate_distance_bonus",
        effect_params={
            "pile_in_distance_bonus": 3,
            "consolidate_distance_bonus": 3,
        },
    ),
    "000008774005": EnhancementToolDescriptor(
        enhancement_id="000008774005",
        name="Deathwing Assault",
        timing="passive_while_in_reserves",
        target="bearer_unit_with_deep_strike",
        duration="while_in_reserves",
        effect="strategic_reserves_setup_round_bonus_for_deep_strike",
        effect_params={
            "strategic_reserves_setup_round_bonus": 1,
            "requires_deep_strike": True,
        },
    ),
}

_SPACE_MARINES_INNER_CIRCLE_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_INNER_CIRCLE_TASK_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_WRATH_OF_THE_ROCK_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010155002": EnhancementToolDescriptor(
        enhancement_id="000010155002",
        name="Tempered in Battle (Aura)",
        timing="passive_aura",
        target="friendly_adeptus_astartes_units_within_aura",
        duration="constant_while_bearer_alive",
        effect="aura_reroll_battleshock_and_leadership_tests",
        range_in=6.0,
        effect_params={
            "range": 6,
            "reroll_tests": ("battle_shock", "leadership"),
        },
    ),
    "000010155003": EnhancementToolDescriptor(
        enhancement_id="000010155003",
        name="Ancient Weapons",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant_while_bearer_alive",
        effect="bearer_melee_strength_ap_damage_bonus",
        effect_params={
            "bearer_melee_strength_bonus": 2,
            "bearer_melee_ap_bonus": 1,
            "bearer_melee_damage_bonus": 1,
        },
    ),
    "000010155004": EnhancementToolDescriptor(
        enhancement_id="000010155004",
        name="Deathwing Assault",
        timing="passive_while_in_reserves",
        target="bearer_unit_with_deep_strike",
        duration="while_in_reserves",
        effect="strategic_reserves_setup_round_bonus_for_deep_strike",
        effect_params={
            "strategic_reserves_setup_round_bonus": 1,
            "requires_deep_strike": True,
        },
    ),
    "000010155005": EnhancementToolDescriptor(
        enhancement_id="000010155005",
        name="Lord of the Ravenwing",
        timing="passive",
        target="bearer_unit",
        duration="constant_while_bearer_alive",
        effect="bearer_unit_reroll_advance_and_charge",
        effect_params={
            "reroll_advance": True,
            "reroll_charge": True,
        },
    ),
}

_SPACE_MARINES_WRATH_OF_THE_ROCK_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_WRATH_OF_THE_ROCK_DESCRIPTORS.values()
}

_SPACE_MARINES_WRATHFUL_PROCESSION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009843002": EnhancementToolDescriptor(
        enhancement_id="000009843002",
        name="Pyrebrand",
        timing="passive",
        target="bearer_unit",
        duration="constant_while_bearer_alive",
        effect="bearer_unit_gains_stealth",
    ),
    "000009843003": EnhancementToolDescriptor(
        enhancement_id="000009843003",
        name="Sacred Rage",
        timing="start_of_fight_phase_once_per_battle",
        target="bearer_unit",
        duration="until_end_of_phase",
        effect="bearer_unit_gains_fights_first_once_per_battle",
        once_per_battle=True,
    ),
    "000009843004": EnhancementToolDescriptor(
        enhancement_id="000009843004",
        name="Taramond's Censer",
        timing="start_of_fight_phase",
        target="enemy_units_within_engagement_range_of_bearer_unit",
        duration="instant",
        effect="engagement_range_enemy_units_take_battleshock_with_modifier",
        effect_params={
            "battle_shock_test_modifier": -1,
        },
    ),
    "000009843005": EnhancementToolDescriptor(
        enhancement_id="000009843005",
        name="Benediction of Fury",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant_while_bearer_alive",
        effect="bearer_melee_gains_devastating_wounds",
        effect_params={
            "keywords": ("DEVASTATING WOUNDS",),
        },
    ),
}

_SPACE_MARINES_WRATHFUL_PROCESSION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_WRATHFUL_PROCESSION_DESCRIPTORS.values()
}

_SPACE_MARINES_IRONSTORM_SPEARHEAD_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008478002": EnhancementToolDescriptor(
        enhancement_id="000008478002",
        name="Target Augury Web",
        timing="command_phase",
        target="friendly_adeptus_astartes_vehicle_model_within_range_of_bearer",
        duration="until_start_of_next_command_phase",
        effect="target_vehicle_weapons_gain_lethal_hits_until_next_command_phase",
        effect_params={
            "range": 6,
            "required_target_keywords": ("VEHICLE",),
        },
    ),
    "000008478003": EnhancementToolDescriptor(
        enhancement_id="000008478003",
        name="The Flesh is Weak",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_fnp",
        effect_params={
            "feel_no_pain": 4,
        },
    ),
    "000008478004": EnhancementToolDescriptor(
        enhancement_id="000008478004",
        name="Adept of the Omnissiah",
        timing="on_failed_save_for_friendly_vehicle_model_within_range_of_bearer",
        target="friendly_adeptus_astartes_vehicle_model_within_range_of_bearer",
        duration="instant_once_per_battle_round",
        effect="first_failed_save_damage_set_zero_for_target_vehicle_model",
        effect_params={
            "range": 6,
            "usage": "battle_round",
        },
    ),
    "000008478005": EnhancementToolDescriptor(
        enhancement_id="000008478005",
        name="Master of Machine War",
        timing="command_phase",
        target="friendly_adeptus_astartes_vehicle_model_within_range_of_bearer",
        duration="until_start_of_next_command_phase",
        effect="target_vehicle_can_shoot_after_advance_or_fall_back_until_next_command_phase",
        effect_params={
            "range": 6,
            "required_target_keywords": ("VEHICLE",),
        },
    ),
}

_SPACE_MARINES_IRONSTORM_SPEARHEAD_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_IRONSTORM_SPEARHEAD_DESCRIPTORS.values()
}

_SPACE_MARINES_LIBERATOR_ASSAULT_GROUP_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008376002": EnhancementToolDescriptor(
        enhancement_id="000008376002",
        name="Speed of the Primarch",
        timing="start_of_fight_phase_once_per_battle",
        target="bearers_unit",
        duration="until_end_of_phase",
        effect="bearer_unit_gains_fights_first_once_per_battle",
        effect_params={
            "once_per_battle_key": "speed_of_the_primarch",
        },
    ),
    "000008376003": EnhancementToolDescriptor(
        enhancement_id="000008376003",
        name="Rage-fuelled Warrior",
        timing="start_of_fight_phase_once_per_battle",
        target="bearer",
        duration="until_end_of_phase",
        effect="bearer_melee_gains_sustained_hits_once_per_battle",
        effect_params={
            "sustained_hits": 3,
            "once_per_battle_key": "rage_fuelled_warrior",
        },
    ),
    "000008376004": EnhancementToolDescriptor(
        enhancement_id="000008376004",
        name="Icon of the Angel",
        timing="enemy_fall_back_trigger",
        target="enemy_non_monster_non_vehicle_within_engagement_of_bearers_unit",
        duration="while_bearer_alive",
        effect="enemy_fall_back_forces_desperate_escape_with_battleshock_penalty",
        effect_params={
            "exclude_target_keywords": ("MONSTER", "VEHICLE"),
            "battleshock_penalty": 1,
        },
    ),
    "000008376005": EnhancementToolDescriptor(
        enhancement_id="000008376005",
        name="Gift of Foresight",
        timing="after_bearer_hit_wound_or_save_roll_once_per_battle_round",
        target="bearer",
        duration="instant_once_per_battle_round",
        effect="set_bearer_hit_wound_or_save_roll_to_unmodified_six",
        effect_params={
            "usage": "battle_round",
        },
    ),
}

_SPACE_MARINES_LIBERATOR_ASSAULT_GROUP_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_LIBERATOR_ASSAULT_GROUP_DESCRIPTORS.values()
}

_SPACE_MARINES_LIBRARIUS_CONCLAVE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009785002": EnhancementToolDescriptor(
        enhancement_id="000009785002",
        name="Prescience",
        timing="enemy_move_end_reactive",
        target="bearer_unit",
        duration="constant_once_per_turn",
        effect="reactive_normal_move_up_to_d6_or_six_if_divination_active",
        range_in=9.0,
        effect_params={
            "trigger_actions": ("move", "advance", "fall_back"),
            "trigger_range": 9,
            "distance_roll": "D6",
            "divination_max_distance": 6,
            "limit": "turn",
        },
    ),
    "000009785003": EnhancementToolDescriptor(
        enhancement_id="000009785003",
        name="Celerity",
        timing="passive",
        target="bearer_unit",
        duration="constant_conditional",
        effect="charge_after_advance_and_biomancy_charge_after_fall_back",
        effect_params={
            "charge_after_advance": True,
            "charge_after_fall_back_when_discipline_active": "BIOMANCY",
        },
    ),
    "000009785004": EnhancementToolDescriptor(
        enhancement_id="000009785004",
        name="Obfuscation",
        timing="passive",
        target="bearer_unit",
        duration="constant_conditional",
        effect="prevent_fire_overwatch_and_telepathy_ranged_targeting_cap",
        effect_params={
            "stratagem_name": "Fire Overwatch",
            "telepathy_ranged_targeting_cap": 18,
        },
    ),
    "000009785005": EnhancementToolDescriptor(
        enhancement_id="000009785005",
        name="Fusillade",
        timing="passive",
        target="bearer_unit_ranged_weapons",
        duration="constant_conditional",
        effect="grant_anti_keywords_and_conditional_pyromancy_sustained_hits_and_telekinesis_range_bonus",
        effect_params={
            "anti_monster": 5,
            "anti_vehicle": 5,
            "pyromancy_sustained_hits": 1,
            "telekinesis_range_bonus": 6,
        },
    ),
}

_SPACE_MARINES_LIBRARIUS_CONCLAVE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_LIBRARIUS_CONCLAVE_DESCRIPTORS.values()
}

_SPACE_MARINES_LIONS_BLADE_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009733002": EnhancementToolDescriptor(
        enhancement_id="000009733002",
        name="Calibanite Armaments",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_damage_bonus",
        effect_params={"melee_damage_bonus": 1},
    ),
    "000009733003": EnhancementToolDescriptor(
        enhancement_id="000009733003",
        name="Lord of the Hunt",
        timing="passive",
        target="bearer_unit",
        duration="constant_while_bearer_alive",
        effect="eligible_to_shoot_and_charge_after_fall_back_and_reroll_desperate_escape_tests",
        effect_params={
            "shoot_after_fall_back": True,
            "charge_after_fall_back": True,
            "reroll_desperate_escape_tests": True,
        },
    ),
    "000009733004": EnhancementToolDescriptor(
        enhancement_id="000009733004",
        name="Stalwart Champion",
        timing="passive",
        target="bearer_unit",
        duration="constant_while_not_battle_shocked",
        effect="while_not_battleshocked_bearer_unit_objective_control_bonus",
        effect_params={
            "objective_control_bonus": 1,
            "requires_not_battle_shocked": True,
        },
    ),
    "000009733005": EnhancementToolDescriptor(
        enhancement_id="000009733005",
        name="Fulgus Magna",
        timing="end_of_opponent_turn_once_per_battle",
        target="bearer_unit",
        duration="instant_once_per_battle",
        effect="once_per_battle_end_of_opponent_turn_enter_strategic_reserves",
        effect_params={
            "once_per_battle_key": "fulgus_magna",
            "requires_not_engagement_range": True,
            "destination": "strategic_reserves",
        },
    ),
}

_SPACE_MARINES_LIONS_BLADE_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_LIONS_BLADE_TASK_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_ORBITAL_ASSAULT_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010680002": EnhancementToolDescriptor(
        enhancement_id="000010680002",
        name="Laurels of Thunder",
        timing="passive",
        target="bearer_unit",
        duration="conditional_on_setup_turn_while_bearer_alive",
        effect="charge_reroll_on_setup_turn",
        effect_params={
            "charge_reroll_on_setup_turn": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010680003": EnhancementToolDescriptor(
        enhancement_id="000010680003",
        name="Veteran of the Vanguard",
        timing="passive",
        target="bearer_unit",
        duration="constant_while_bearer_alive",
        effect="bearer_unit_gain_scouts",
        effect_params={
            "scouts_distance": 6,
            "requires_bearer_alive": True,
        },
    ),
    "000010680004": EnhancementToolDescriptor(
        enhancement_id="000010680004",
        name="Orbital Uplink Reliquary",
        timing="post_deployment",
        target="friendly_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "can_place_in_reserves": True,
            "redeploy_filters": ("ADEPTUS ASTARTES",),
        },
    ),
    "000010680005": EnhancementToolDescriptor(
        enhancement_id="000010680005",
        name="Dedicated Gunship",
        timing="end_of_opponent_fight_phase_once_per_battle",
        target="bearer_unit",
        duration="instant_once_per_battle",
        effect="once_per_battle_end_of_opponent_fight_phase_enter_strategic_reserves",
        effect_params={
            "once_per_battle_key": "dedicated_gunship",
            "requires_not_engagement_range": True,
            "destination": "strategic_reserves",
        },
    ),
}

_SPACE_MARINES_ORBITAL_ASSAULT_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_ORBITAL_ASSAULT_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_CERAMITE_SENTINELS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010759002": EnhancementToolDescriptor(
        enhancement_id="000010759002",
        name="Honour Indefatigable",
        timing="end_of_phase_when_bearer_destroyed_first_time",
        target="bearer",
        duration="once_per_battle",
        effect="return_bearer_on_2plus_with_fixed_wounds",
        effect_params={
            "roll_min": 2,
            "wounds_on_return": "full",
            "return_on_death_key": "honour_indefatigable",
        },
    ),
    "000010759003": EnhancementToolDescriptor(
        enhancement_id="000010759003",
        name="Castellum Omnivox",
        timing="after_bearer_unit_falls_back",
        target="bearer_unit",
        duration="until_end_of_turn",
        effect="choose_action_or_shoot_and_charge_after_fall_back",
        effect_params={
            "choices": ("ACTION", "SHOOT_AND_CHARGE"),
        },
    ),
    "000010759004": EnhancementToolDescriptor(
        enhancement_id="000010759004",
        name="Spy-skull Data Link",
        timing="passive",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="grant_ignores_cover_to_bearer_led_unit_ranged_weapons",
        effect_params={
            "attack_type": "ranged",
            "keywords": ("IGNORES COVER",),
        },
    ),
    "000010759005": EnhancementToolDescriptor(
        enhancement_id="000010759005",
        name="Defensive Mastery",
        timing="post_deployment",
        target="friendly_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "can_place_in_reserves": True,
            "redeploy_filters": ("ADEPTUS ASTARTES",),
            "strategic_reserves_ignore_current_unit_count_limit": True,
        },
    ),
}

_SPACE_MARINES_CERAMITE_SENTINELS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_CERAMITE_SENTINELS_DESCRIPTORS.values()
}

_SPACE_MARINES_RECLAMATION_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010684002": EnhancementToolDescriptor(
        enhancement_id="000010684002",
        name="Seals of Reconquest",
        timing="passive",
        target="bearer_unit",
        duration="constant_while_bearer_alive",
        effect="bearer_unit_invulnerable_save",
        effect_params={
            "invulnerable_save": 5,
            "requires_bearer_alive": True,
        },
    ),
    "000010684003": EnhancementToolDescriptor(
        enhancement_id="000010684003",
        name="Avenging Avatar (Aura)",
        timing="opponent_command_phase_battleshock_step",
        target="enemy_units_within_range",
        duration="repeatable",
        effect="opponent_command_phase_below_starting_strength_battleshock_aura",
        range_in=9.0,
        effect_params={
            "range": 9,
            "requires_target_below_starting_strength": True,
        },
    ),
    "000010684004": EnhancementToolDescriptor(
        enhancement_id="000010684004",
        name="Scroll of Proclamation",
        timing="charge_declaration",
        target="bearer_unit",
        duration="conditional",
        effect="charge_reroll_if_charge_target_within_objective_range",
        effect_params={
            "charge_reroll_if_target_on_objective": True,
        },
    ),
    "000010684005": EnhancementToolDescriptor(
        enhancement_id="000010684005",
        name="Liberatum",
        timing="passive",
        target="bearer_attacks",
        duration="conditional",
        effect="bearer_hit_and_wound_rerolls_if_target_within_objective_range",
        effect_params={
            "reroll_hit": True,
            "reroll_wound": True,
            "requires_target_within_objective_range": True,
        },
    ),
}

_SPACE_MARINES_RECLAMATION_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_RECLAMATION_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_BASTION_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010676002": EnhancementToolDescriptor(
        enhancement_id="000010676002",
        name="Eye of the Primarch",
        timing="passive",
        target="bearer_and_battleline_models_in_bearer_unit_ranged_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={
            "attack_type": "ranged",
            "keywords": ("PRECISION",),
            "includes_bearer": True,
            "includes_battleline_models": True,
        },
    ),
    "000010676003": EnhancementToolDescriptor(
        enhancement_id="000010676003",
        name="Hero of the Chapter",
        timing="passive_while_leading",
        target="bearer",
        duration="constant_conditional",
        effect="bearer_gains_keyword_while_leading",
        effect_params={"keyword": "BATTLELINE"},
    ),
    "000010676004": EnhancementToolDescriptor(
        enhancement_id="000010676004",
        name="Blades of Valour",
        timing="passive",
        target="bearer_and_battleline_models_in_bearer_unit_melee_weapons",
        duration="constant",
        effect="melee_ap_bonus_for_bearer_and_battleline_models_in_bearer_unit",
        effect_params={
            "ap_bonus": 1,
            "includes_bearer": True,
            "includes_battleline_models": True,
        },
    ),
    "000010676005": EnhancementToolDescriptor(
        enhancement_id="000010676005",
        name="Bombast Omnivox",
        timing="when_bearer_unit_targeted_by_stratagem",
        target="bearer_unit",
        duration="instant_repeatable",
        effect="targeted_stratagem_cp_refund_with_conditional_bonus",
        effect_params={
            "roll_min": 4,
            "cp_gain": 1,
            "roll_bonus": 1,
            "roll_bonus_if_target_has_keyword": "BATTLELINE",
        },
    ),
}

_SPACE_MARINES_BASTION_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_BASTION_TASK_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_BLADE_OF_ULTRAMAR_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010633002": EnhancementToolDescriptor(
        enhancement_id="000010633002",
        name="Armour of Antoninus",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_save_and_fnp",
        effect_params={
            "save_characteristic": 2,
            "feel_no_pain": 5,
        },
    ),
    "000010633003": EnhancementToolDescriptor(
        enhancement_id="000010633003",
        name="Oath of Macragge",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant_conditional",
        effect="bearer_melee_attacks_strength_bonus_with_assault_doctrine_scaling",
        effect_params={
            "base_bonus": 1,
            "assault_doctrine_bonus": 2,
        },
    ),
    "000010633004": EnhancementToolDescriptor(
        enhancement_id="000010633004",
        name="Student of the Codex",
        timing="start_of_command_phase_optional",
        target="bearer_unit",
        duration="until_next_command_phase",
        effect="unit_tactical_doctrine_override",
        effect_params={
            "doctrine": "TACTICAL",
            "optional": True,
        },
    ),
    "000010633005": EnhancementToolDescriptor(
        enhancement_id="000010633005",
        name="Veteran of Behemoth",
        timing="passive_while_leading_and_doctrine_conditional",
        target="bearer_unit_ranged_weapons_and_advance_rolls",
        duration="constant_conditional",
        effect="grant_sustained_hits_and_devastator_advance_reroll",
        effect_params={
            "sustained_hits": 1,
            "requires_leading": True,
            "advance_reroll_requires_doctrine": "DEVASTATOR",
        },
    ),
}

_SPACE_MARINES_BLADE_OF_ULTRAMAR_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_BLADE_OF_ULTRAMAR_DESCRIPTORS.values()
}

_SPACE_MARINES_CHAMPIONS_OF_FENRIS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009851002": EnhancementToolDescriptor(
        enhancement_id="000009851002",
        name="Wolves' Wisdom",
        timing="passive",
        target="bearer_unit_great_wolf_watches_trigger",
        duration="constant",
        effect="increase_great_wolf_watches_charge_trigger_range",
        effect_params={
            "base_range": 3,
            "enhanced_range": 6,
        },
    ),
    "000009851003": EnhancementToolDescriptor(
        enhancement_id="000009851003",
        name="Foes' Fate",
        timing="enemy_fall_back_from_engagement_with_bearer_unit",
        target="enemy_units_within_engagement_of_bearer_unit_excluding_monsters_vehicles",
        duration="constant",
        effect="enemy_fall_back_forced_desperate_escape_with_battleshock_penalty",
        effect_params={
            "exclude_monsters_vehicles": True,
            "battleshock_penalty": 1,
        },
    ),
    "000009851004": EnhancementToolDescriptor(
        enhancement_id="000009851004",
        name="Fangrune Pendant",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="eligible_to_shoot_and_charge_after_fall_back",
        effect_params={},
    ),
    "000009851005": EnhancementToolDescriptor(
        enhancement_id="000009851005",
        name="Longstrider",
        timing="passive",
        target="bearer_unit_charge_rolls",
        duration="constant",
        effect="reroll_charge_rolls_for_bearer_unit",
        effect_params={},
    ),
}

_SPACE_MARINES_CHAMPIONS_OF_FENRIS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_CHAMPIONS_OF_FENRIS_DESCRIPTORS.values()
}

_SPACE_MARINES_SAGA_OF_THE_BEASTSLAYER_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010269002": EnhancementToolDescriptor(
        enhancement_id="000010269002",
        name="Wolf-touched",
        timing="passive_and_declare_battle_formations_attachment_override",
        target="bearer_and_bearer_attachment_eligibility",
        duration="constant",
        effect="bearer_move_bonus_and_attach_to_wulfen_infantry",
        effect_params={
            "bearer_move_bonus": 2,
            "attach_override_target_keywords_all": ("WULFEN", "INFANTRY"),
        },
    ),
    "000010269003": EnhancementToolDescriptor(
        enhancement_id="000010269003",
        name="Hunter's Guile",
        timing="post_deployment",
        target="friendly_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "can_place_in_reserves": True,
            "redeploy_filter_any_groups": (
                ("THUNDERWOLF CAVALRY",),
                ("WULFEN",),
                ("BLOOD CLAWS",),
            ),
        },
    ),
    "000010269004": EnhancementToolDescriptor(
        enhancement_id="000010269004",
        name="Elder's Guidance",
        timing="start_of_fight_phase_optional_once_per_battle_if_bearer_is_leading_blood_claws",
        target="bearer_led_blood_claws_unit",
        duration="until_end_of_phase_once_per_battle",
        effect="once_per_battle_start_of_fight_phase_melee_ap_bonus_for_bearer_led_blood_claws_unit",
        once_per_battle=True,
        effect_params={
            "once_per_battle_key": "elders_guidance",
            "melee_ap_bonus": 1,
            "requires_bearer_leading_blood_claws": True,
        },
    ),
    "000010269005": EnhancementToolDescriptor(
        enhancement_id="000010269005",
        name="Helm of the Beastslayer",
        timing="when_targeted_by_character_monster_vehicle_attacks",
        target="attacks_targeting_bearer_unit",
        duration="constant",
        effect="ap_worsen_against_character_monster_vehicle_attacks_targeting_bearer_unit",
        effect_params={
            "ap_worsen": 1,
            "attacker_keywords_any": ("CHARACTER", "MONSTER", "VEHICLE"),
        },
    ),
}

_SPACE_MARINES_SAGA_OF_THE_BEASTSLAYER_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_SAGA_OF_THE_BEASTSLAYER_DESCRIPTORS.values()
}

_SPACE_MARINES_SAGA_OF_THE_BOLD_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010265002": EnhancementToolDescriptor(
        enhancement_id="000010265002",
        name="Braggart's Steel",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_strength_bonus_and_conditional_damage_bonus_on_boast",
        effect_params={
            "strength_bonus": 2,
            "damage_bonus_if_unit_has_boast": 1,
        },
    ),
    "000010265003": EnhancementToolDescriptor(
        enhancement_id="000010265003",
        name="Skjald",
        timing="on_space_wolves_character_unit_achieves_boast",
        target="army_command_points",
        duration="instant",
        effect="gain_cp_when_space_wolves_character_unit_achieves_boast_if_bearer_on_battlefield",
        effect_params={
            "cp_gain": 1,
        },
    ),
    "000010265004": EnhancementToolDescriptor(
        enhancement_id="000010265004",
        name="Hordeslayer",
        timing="start_of_fight_phase_if_enemy_models_outnumber_friendly_within_6_of_bearer",
        target="bearer_melee_weapons",
        duration="until_end_of_phase",
        effect="start_of_fight_phase_conditional_bearer_melee_attacks_bonus",
        effect_params={
            "range": 6,
            "attacks_bonus": 2,
            "attacks_bonus_with_boast": 3,
        },
    ),
    "000010265005": EnhancementToolDescriptor(
        enhancement_id="000010265005",
        name="Thunderwolf's Fortitude",
        timing="on_first_bearer_destroyed_end_of_phase",
        target="bearer",
        duration="once",
        effect="return_bearer_on_death_on_2_plus",
        effect_params={
            "roll_min": 2,
            "wounds_on_return": 3,
            "return_on_death_key": "thunderwolfs_fortitude",
        },
    ),
}

_SPACE_MARINES_SAGA_OF_THE_BOLD_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_SAGA_OF_THE_BOLD_DESCRIPTORS.values()
}

_SPACE_MARINES_SAGA_OF_THE_HUNTER_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010261002": EnhancementToolDescriptor(
        enhancement_id="000010261002",
        name="Swift Hunter",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_scouts_to_bearer_unit",
        effect_params={
            "scouts_distance": 7,
        },
    ),
    "000010261003": EnhancementToolDescriptor(
        enhancement_id="000010261003",
        name="Fenrisian Grit",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_fnp",
        effect_params={
            "feel_no_pain": 4,
        },
    ),
    "000010261004": EnhancementToolDescriptor(
        enhancement_id="000010261004",
        name="Wolf Master",
        timing="command_phase",
        target="friendly_space_wolves_unit_within_range_of_bearer",
        duration="until_start_of_next_command_phase",
        effect="target_space_wolves_unit_specific_weapons_gain_lethal_hits_until_next_command_phase",
        effect_params={
            "range": 9,
            "required_target_keywords_any": ("SPACE WOLVES",),
            "weapon_names": ("teeth and claws", "tyrnak and fenrir"),
            "granted_keywords": ("LETHAL HITS",),
        },
    ),
    "000010261005": EnhancementToolDescriptor(
        enhancement_id="000010261005",
        name="Feral Rage",
        timing="passive_and_on_charge",
        target="bearer_melee_weapons",
        duration="constant_and_until_end_of_turn_after_charge",
        effect="bearer_melee_attacks_bonus_and_additional_bonus_after_charge",
        effect_params={
            "bearer_melee_attacks_bonus": 1,
            "bearer_melee_attacks_bonus_on_charge": 1,
        },
    ),
}

_SPACE_MARINES_SAGA_OF_THE_HUNTER_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_SAGA_OF_THE_HUNTER_DESCRIPTORS.values()
}

_SPACE_MARINES_SAGA_OF_THE_GREAT_WOLF_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010660002": EnhancementToolDescriptor(
        enhancement_id="000010660002",
        name="Grimnar's Mark",
        timing="once_per_battle_round_battle_round_2_plus_when_targeting_bearer_unit_with_rapid_ingress_or_heroic_intervention",
        target="bearer_unit_and_bearer_attachment_eligibility",
        duration="instant_and_constant_attachment_override",
        effect="zero_cp_target_bearer_unit_with_rapid_ingress_or_heroic_intervention_and_attach_to_wolf_guard_terminators",
        effect_params={
            "stratagem_names": ("RAPID INGRESS", "HEROIC INTERVENTION"),
            "cp_cost": 0,
            "once_per_battle_round_key": "grimnars_mark_free_stratagem",
            "min_battle_round": 2,
            "attach_override_unit_names_any": ("Wolf Guard Terminators",),
        },
    ),
    "000010660003": EnhancementToolDescriptor(
        enhancement_id="000010660003",
        name="Howlmaw",
        timing="start_of_fight_phase_optional",
        target="one_enemy_unit_within_6_of_bearer",
        duration="instant",
        effect="select_enemy_within_6_of_bearer_take_battleshock_with_minus_1_modifier",
        effect_params={
            "range": 6,
            "battleshock_test_modifier": -1,
        },
    ),
    "000010660004": EnhancementToolDescriptor(
        enhancement_id="000010660004",
        name="Chariots of the Storm",
        timing="post_deployment",
        target="friendly_adeptus_astartes_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "can_place_in_reserves": True,
            "redeploy_filters": ("ADEPTUS ASTARTES",),
        },
    ),
    "000010660005": EnhancementToolDescriptor(
        enhancement_id="000010660005",
        name="Skjald's Foretelling",
        timing="while_bearer_is_leading",
        target="bearer_led_unit_melee_weapons",
        duration="constant_while_bearer_is_leading",
        effect="grant_lance_to_weapons_of_models_in_bearer_led_unit",
        effect_params={
            "keywords": ("LANCE",),
            "requires_bearer_leading": True,
        },
    ),
}

_SPACE_MARINES_SAGA_OF_THE_GREAT_WOLF_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_SAGA_OF_THE_GREAT_WOLF_DESCRIPTORS.values()
}

_SPACE_MARINES_STORMLANCE_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008486002": EnhancementToolDescriptor(
        enhancement_id="000008486002",
        name="Fury of the Storm",
        timing="passive_and_charge_move_end",
        target="bearer_model_melee_weapons",
        duration="constant_with_charge_move_end_bonus_until_end_of_turn",
        effect="bearer_melee_strength_and_ap_bonus_with_charge_upgrade",
        effect_params={
            "base_bearer_melee_strength_bonus": 1,
            "base_bearer_melee_ap_bonus": 1,
            "charged_bearer_melee_strength_bonus": 2,
            "charged_bearer_melee_ap_bonus": 2,
        },
    ),
    "000008486003": EnhancementToolDescriptor(
        enhancement_id="000008486003",
        name="Portents of Wisdom",
        timing="while_bearer_is_leading",
        target="bearer_led_unit",
        duration="constant_while_bearer_is_leading",
        effect="reroll_advance_rolls_for_bearer_led_unit",
        effect_params={"requires_bearer_leading": True},
    ),
    "000008486004": EnhancementToolDescriptor(
        enhancement_id="000008486004",
        name="Feinting Withdrawal",
        timing="while_bearer_is_leading",
        target="bearer_led_unit",
        duration="constant_while_bearer_is_leading",
        effect="allow_bearer_led_unit_to_shoot_after_fall_back",
        effect_params={"requires_bearer_leading": True, "shoot_after_fall_back": True},
    ),
    "000008486005": EnhancementToolDescriptor(
        enhancement_id="000008486005",
        name="Hunter's Instincts",
        timing="movement_phase_while_in_strategic_reserves",
        target="bearer_unit_in_strategic_reserves",
        duration="constant_while_in_strategic_reserves",
        effect="add_setup_round_for_bearer_unit_in_strategic_reserves",
        effect_params={"strategic_reserves_setup_round_bonus": 1},
    ),
}

_SPACE_MARINES_STORMLANCE_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_STORMLANCE_TASK_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_COMPANY_OF_HUNTERS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008778002": EnhancementToolDescriptor(
        enhancement_id="000008778002",
        name="Master-crafted Weapon",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="grant_precision_to_bearer_melee_weapons",
        effect_params={},
    ),
    "000008778003": EnhancementToolDescriptor(
        enhancement_id="000008778003",
        name="Mounted Strategist",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="reroll_advance_and_charge_rolls_for_bearer_unit",
        effect_params={},
    ),
    "000008778004": EnhancementToolDescriptor(
        enhancement_id="000008778004",
        name="Master of Manoeuvre",
        timing="deployment_phase_passive",
        target="bearer_unit_in_strategic_reserves",
        duration="constant_while_in_strategic_reserves",
        effect="ignore_strategic_reserves_points_limit_and_add_setup_round_for_bearer_unit",
        effect_params={
            "ignore_strategic_reserve_points_limit": True,
            "strategic_reserves_setup_round_bonus": 1,
        },
    ),
    "000008778005": EnhancementToolDescriptor(
        enhancement_id="000008778005",
        name="Recon Hunter",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_scouts_to_bearer_unit",
        effect_params={
            "scouts_distance": 9,
        },
    ),
}

_SPACE_MARINES_COMPANY_OF_HUNTERS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_COMPANY_OF_HUNTERS_DESCRIPTORS.values()
}

_SPACE_MARINES_VANGUARD_SPEARHEAD_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008490002": EnhancementToolDescriptor(
        enhancement_id="000008490002",
        name="The Blade Driven Deep",
        timing="while_bearer_is_leading",
        target="bearer_led_unit",
        duration="constant_while_bearer_is_leading",
        effect="grant_infiltrators_to_bearer_led_unit",
        effect_params={"requires_bearer_leading": True},
    ),
    "000008490003": EnhancementToolDescriptor(
        enhancement_id="000008490003",
        name="Ghostweave Cloak",
        timing="passive",
        target="bearer_model",
        duration="constant",
        effect="grant_stealth_and_lone_operative_to_bearer",
        effect_params={},
    ),
    "000008490004": EnhancementToolDescriptor(
        enhancement_id="000008490004",
        name="Execute and Redeploy",
        timing="your_shooting_phase_after_bearer_unit_shoots",
        target="bearer_unit",
        duration="instant_optional_with_no_charge_until_end_of_turn",
        effect="post_shoot_reactive_normal_move_no_charge_once_per_shooting_phase",
        effect_params={
            "move_range": 6,
            "requires_not_engagement_range": True,
            "requires_bearer_alive": True,
            "requires_bearer_phobos": True,
            "once_per_shooting_phase": True,
        },
    ),
    "000008490005": EnhancementToolDescriptor(
        enhancement_id="000008490005",
        name="Shadow War Veteran",
        timing="opponent_stratagem_targeting",
        target="enemy_unit_within_range_of_bearer",
        duration="constant",
        effect="targeted_stratagem_cp_increase",
        range_in=12.0,
        effect_params={"cp_increase": 1, "ability_name": "Lord of Deceit (Aura)"},
    ),
}

_SPACE_MARINES_VANGUARD_SPEARHEAD_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_VANGUARD_SPEARHEAD_DESCRIPTORS.values()
}

_SPACE_MARINES_SHADOWMARK_TALON_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010466002": EnhancementToolDescriptor(
        enhancement_id="000010466002",
        name="Blackwing Shroud",
        timing="while_bearer_is_leading",
        target="bearer_led_unit",
        duration="constant_while_bearer_is_leading",
        effect="grant_infiltrators_to_bearer_led_unit",
        effect_params={"requires_bearer_leading": True},
    ),
    "000010466003": EnhancementToolDescriptor(
        enhancement_id="000010466003",
        name="Coronal Susurrant",
        timing="opponent_stratagem_targeting",
        target="enemy_unit_within_range_of_bearer",
        duration="constant",
        effect="targeted_stratagem_cp_increase",
        range_in=12.0,
        effect_params={"cp_increase": 1},
    ),
    "000010466004": EnhancementToolDescriptor(
        enhancement_id="000010466004",
        name="Umbral Raptor",
        timing="passive",
        target="bearer_model",
        duration="constant",
        effect="grant_stealth_and_lone_operative_to_bearer",
        effect_params={},
    ),
    "000010466005": EnhancementToolDescriptor(
        enhancement_id="000010466005",
        name="Hunter's Instincts",
        timing="movement_phase_while_in_strategic_reserves",
        target="bearer_unit_in_strategic_reserves",
        duration="constant_while_in_strategic_reserves",
        effect="add_setup_round_for_bearer_unit_in_strategic_reserves",
        effect_params={"strategic_reserves_setup_round_bonus": 1},
    ),
}

_SPACE_MARINES_SHADOWMARK_TALON_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_SHADOWMARK_TALON_DESCRIPTORS.values()
}

_SPACE_MARINES_SPEARPOINT_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010629002": EnhancementToolDescriptor(
        enhancement_id="000010629002",
        name="Spearpoint Paragon",
        timing="passive_and_charge_move_end",
        target="bearer_model_melee_weapons",
        duration="constant_with_charge_move_end_bonus_until_end_of_turn",
        effect="bearer_melee_strength_and_ap_bonus_with_charge_upgrade",
        effect_params={
            "base_bearer_melee_strength_bonus": 1,
            "base_bearer_melee_ap_bonus": 1,
            "charged_bearer_melee_strength_bonus": 2,
            "charged_bearer_melee_ap_bonus": 2,
        },
    ),
    "000010629003": EnhancementToolDescriptor(
        enhancement_id="000010629003",
        name="Stormseers' Wisdom",
        timing="while_bearer_is_leading",
        target="bearer_led_unit",
        duration="constant_while_bearer_is_leading",
        effect="reroll_advance_rolls_for_bearer_led_unit",
        effect_params={"requires_bearer_leading": True},
    ),
    "000010629004": EnhancementToolDescriptor(
        enhancement_id="000010629004",
        name="Hunter's Eye",
        timing="passive",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="grant_sustained_hits_and_ignores_cover_to_bearer_unit_ranged_weapons",
        effect_params={"keywords": ("SUSTAINED HITS 1", "IGNORES COVER")},
    ),
    "000010629005": EnhancementToolDescriptor(
        enhancement_id="000010629005",
        name="Chogorian Huntmaster",
        timing="movement_phase_while_in_strategic_reserves",
        target="bearer_unit_in_strategic_reserves",
        duration="constant_while_in_strategic_reserves",
        effect="add_setup_round_for_bearer_unit_in_strategic_reserves",
        effect_params={"strategic_reserves_setup_round_bonus": 1},
    ),
}

_SPACE_MARINES_SPEARPOINT_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_SPEARPOINT_TASK_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_COMPANIONS_OF_VEHEMENCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010392002": EnhancementToolDescriptor(
        enhancement_id="000010392002",
        name="Incendiary Animus",
        timing="passive",
        target="bearer_unit_melee_weapons",
        duration="constant",
        effect="melee_ap_bonus_for_bearer_unit",
        effect_params={
            "ap_bonus": 1,
        },
    ),
    "000010392003": EnhancementToolDescriptor(
        enhancement_id="000010392003",
        name="Oathbound Exemplar",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="advance_bonus_and_action_after_advance_for_bearer_unit",
        effect_params={
            "advance_bonus": 1,
            "allow_action_after_advance": True,
        },
    ),
    "000010392004": EnhancementToolDescriptor(
        enhancement_id="000010392004",
        name="Merciless Denunciation",
        timing="passive",
        target="bearer_unit_melee_attacks",
        duration="constant",
        effect="reroll_hit_rolls_for_bearer_unit_melee_attacks",
        effect_params={},
    ),
    "000010392005": EnhancementToolDescriptor(
        enhancement_id="000010392005",
        name="Zealous Vanguard",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_scouts_to_bearer_unit",
        effect_params={
            "scouts_distance": 6,
        },
    ),
}

_SPACE_MARINES_COMPANIONS_OF_VEHEMENCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_COMPANIONS_OF_VEHEMENCE_DESCRIPTORS.values()
}

_SPACE_MARINES_EMPERORS_SHIELD_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010460002": EnhancementToolDescriptor(
        enhancement_id="000010460002",
        name="Champion of the Feast",
        timing="passive_and_start_of_any_phase_optional",
        target="bearer_and_bearer_unit_other_models",
        duration="constant_and_until_end_of_phase_once_per_battle",
        effect="bearer_melee_attacks_bonus_and_once_per_battle_unit_other_models_melee_attacks_bonus",
        once_per_battle=True,
        effect_params={
            "bearer_melee_attacks_bonus": 1,
            "unit_other_models_melee_attacks_bonus": 1,
            "once_per_battle_key": "champion_of_the_feast",
        },
    ),
    "000010460003": EnhancementToolDescriptor(
        enhancement_id="000010460003",
        name="Disciple of Rhetoricus",
        timing="passive_and_start_of_any_phase_optional",
        target="bearer_and_bearer_unit_other_models",
        duration="constant_and_until_end_of_phase_once_per_battle",
        effect="bearer_objective_control_bonus_and_once_per_battle_unit_other_models_objective_control_bonus",
        once_per_battle=True,
        effect_params={
            "bearer_objective_control_bonus": 1,
            "unit_other_models_objective_control_bonus": 1,
            "once_per_battle_key": "disciple_of_rhetoricus",
        },
    ),
    "000010460004": EnhancementToolDescriptor(
        enhancement_id="000010460004",
        name="Indomitable Champion",
        timing="on_bearer_destroyed",
        target="bearer",
        duration="resolve_at_end_of_phase_first_time",
        effect="return_bearer_on_2plus_with_fixed_wounds",
        once_per_battle=True,
        effect_params={
            "roll_min": 2,
            "wounds_on_return": 3,
            "return_on_death_key": "indomitable_champion",
        },
    ),
    "000010460005": EnhancementToolDescriptor(
        enhancement_id="000010460005",
        name="Malodraxian Standard",
        timing="passive",
        target="attacks_targeting_bearer_unit",
        duration="constant",
        effect="wound_roll_penalty_when_attack_strength_exceeds_bearer_unit_toughness",
        effect_params={
            "wound_roll_penalty": 1,
            "requires_strength_gt_toughness": True,
        },
    ),
}

_SPACE_MARINES_EMPERORS_SHIELD_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_EMPERORS_SHIELD_DESCRIPTORS.values()
}

_SPACE_MARINES_BLACK_SPEAR_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008522002": EnhancementToolDescriptor(
        enhancement_id="000008522002",
        name="Thief of Secrets",
        timing="passive_and_end_of_fight_phase_on_bearer_melee_kill",
        target="bearer_melee_weapons",
        duration="constant_then_battle_long_upgrade",
        effect="bearer_melee_strength_damage_ap_bonus_with_end_of_fight_upgrade",
        effect_params={
            "base_bonus": 1,
            "upgraded_bonus": 2,
        },
    ),
    "000008522003": EnhancementToolDescriptor(
        enhancement_id="000008522003",
        name="Osseus Key",
        timing="start_of_opponent_shooting_phase",
        target="enemy_vehicle_unit_within_range_visible_excluding_titanic",
        duration="until_end_of_phase",
        effect="leadership_test_then_hit_penalty_or_ineligible_to_shoot",
        range_in=12.0,
        effect_params={
            "range": 12.0,
            "required_target_keywords": ("VEHICLE",),
            "excluded_target_keywords": ("TITANIC",),
            "resolution_mode": "leadership_test",
        },
    ),
    "000008522004": EnhancementToolDescriptor(
        enhancement_id="000008522004",
        name="Beacon Angelis",
        timing="passive_and_stratagem_targeting",
        target="bearer_unit",
        duration="constant",
        effect="grant_deep_strike_and_rapid_ingress_zero_cp",
        effect_params={
            "grants_deep_strike": True,
            "stratagem_name": "RAPID INGRESS",
            "cp_reduction": "to_zero",
        },
    ),
    "000008522005": EnhancementToolDescriptor(
        enhancement_id="000008522005",
        name="The Tome of Ectoclades",
        timing="after_selecting_oath_of_moment_target",
        target="enemy_unit",
        duration="until_next_command_phase_once_per_battle",
        effect="optional_second_oath_of_moment_target",
        once_per_battle=True,
        effect_params={
            "once_per_battle_key": "tome_of_ectoclades",
            "target_slot": "secondary",
        },
    ),
}

_SPACE_MARINES_BLACK_SPEAR_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_BLACK_SPEAR_TASK_FORCE_DESCRIPTORS.values()
}

_SPACE_MARINES_VINDICATION_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010396002": EnhancementToolDescriptor(
        enhancement_id="000010396002",
        name="Imperialis of the Eternal Crusade",
        timing="enemy_charge_targeting_bearer_unit",
        target="enemy_unit_declaring_charge_against_bearer_unit",
        duration="instant_per_charge_declaration",
        effect="charge_roll_penalty_against_enemy_unit_targeting_bearer_unit",
        effect_params={
            "charge_roll_penalty": 2,
            "not_cumulative_with_other_negative_modifiers": True,
        },
    ),
    "000010396003": EnhancementToolDescriptor(
        enhancement_id="000010396003",
        name="Consecrating Aura",
        timing="passive",
        target="bearer_unit",
        duration="constant_while_bearer_alive",
        effect="bearer_unit_invulnerable_save",
        effect_params={
            "invulnerable_save": 5,
            "requires_bearer_alive": True,
        },
    ),
    "000010396004": EnhancementToolDescriptor(
        enhancement_id="000010396004",
        name="Orb of the Emperor's Aegis",
        timing="passive",
        target="bearer_unit",
        duration="constant_while_bearer_alive",
        effect="grant_deep_strike_to_bearer_unit",
        effect_params={
            "grants_deep_strike": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010396005": EnhancementToolDescriptor(
        enhancement_id="000010396005",
        name="Warden of Honour",
        timing="while_bearer_is_leading",
        target="vengeful_exhortation_rolls_for_bearer_unit",
        duration="constant_while_bearer_is_leading",
        effect="vengeful_exhortation_roll_bonus",
        effect_params={
            "vengeful_exhortation_roll_bonus": 1,
            "requires_bearer_leading": True,
        },
    ),
}

_SPACE_MARINES_VINDICATION_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _SPACE_MARINES_VINDICATION_TASK_FORCE_DESCRIPTORS.values()
}

_LEGION_OF_EXCESS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009806002": EnhancementToolDescriptor(
        enhancement_id="000009806002",
        name="False Majesty (Aura)",
        timing="passive_aura",
        target="friendly_slaanesh_legiones_daemonica_units_within_range_excluding_monsters",
        duration="constant",
        effect="melee_wound_roll_bonus",
        range_in=6.0,
        effect_params={
            "attack_type": "melee",
            "wound_bonus": 1,
            "required_keywords_all": ("LEGIONES DAEMONICA", "SLAANESH"),
            "excluded_keywords_any": ("MONSTER",),
        },
    ),
    "000009806003": EnhancementToolDescriptor(
        enhancement_id="000009806003",
        name="Dreaming Crown (Aura)",
        timing="passive_aura",
        target="friendly_slaanesh_legiones_daemonica_units_within_range_excluding_monsters",
        duration="constant",
        effect="melee_hit_roll_bonus",
        range_in=6.0,
        effect_params={
            "attack_type": "melee",
            "hit_bonus": 1,
            "required_keywords_all": ("LEGIONES DAEMONICA", "SLAANESH"),
            "excluded_keywords_any": ("MONSTER",),
        },
    ),
    "000009806004": EnhancementToolDescriptor(
        enhancement_id="000009806004",
        name="Avatar of Perfection",
        timing="phase_start_conditional",
        target="bearer",
        duration="until_end_of_phase",
        effect="phase_isolation_grants_rerolls_and_modifier_choice",
        range_in=6.0,
        effect_params={
            "isolation_range": 6.0,
            "requires_no_other_friendly_units_within_range": True,
            "reroll_advance": True,
            "reroll_charge": True,
            "ignore_move_modifiers": True,
            "ignore_advance_modifiers": True,
            "ignore_charge_modifiers": True,
        },
    ),
    "000009806005": EnhancementToolDescriptor(
        enhancement_id="000009806005",
        name="Soul Glutton",
        timing="fight_phase_end",
        target="bearer",
        duration="instant_optional",
        effect="heal_on_bearer_melee_kills",
        effect_params={
            "requires_melee_kills_this_phase": True,
            "heal_roll": "D3",
            "optional": True,
        },
    ),
}

_LEGION_OF_EXCESS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _LEGION_OF_EXCESS_DESCRIPTORS.values()
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
    "000009819004": EnhancementToolDescriptor(
        enhancement_id="000009819004",
        name="Droning Shroud (Aura)",
        timing="passive_aura",
        target="friendly_nurgle_legiones_daemonica_units_within_range",
        duration="constant",
        effect="ranged_targeting_range_cap",
        range_in=6.0,
        effect_params={
            "required_keywords_all": ("LEGIONES DAEMONICA", "NURGLE"),
            "ranged_targeting_max_distance": 18,
        },
    ),
    "000009819005": EnhancementToolDescriptor(
        enhancement_id="000009819005",
        name="Font of Spores (Aura)",
        timing="passive_aura",
        target="friendly_nurgle_legiones_daemonica_units_within_range",
        duration="constant",
        effect="weapon_ap_bonus",
        range_in=6.0,
        effect_params={
            "required_keywords_all": ("LEGIONES DAEMONICA", "NURGLE"),
            "ap_bonus": 1,
            "attack_type": "any",
        },
    ),
}

_PLAGUE_LEGION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _PLAGUE_LEGION_DESCRIPTORS.values()
}

_DEATH_GUARD_CHAMPIONS_OF_CONTAGION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010131002": EnhancementToolDescriptor(
        enhancement_id="000010131002",
        name="Final Ingredient",
        timing="fight_phase_after_unit_fights_and_character_destroyed",
        target="bearer_unit",
        duration="until_end_of_battle",
        effect="select_additional_plague_for_all_afflicted_units",
        once_per_battle=True,
        effect_params={
            "requires_enemy_character_model_destroyed": True,
            "select_from_default_plagues": True,
            "requires_target_is_afflicted": True,
            "once_per_battle_key": "final_ingredient",
        },
    ),
    "000010131003": EnhancementToolDescriptor(
        enhancement_id="000010131003",
        name="Visions of Virulence",
        timing="passive",
        target="enemy_units_enfeebled_by_bearer_pestilent_fallout",
        duration="while_enfeebled_state_active",
        effect="treat_enfeebled_units_as_afflicted",
        effect_params={
            "required_source_name": "Pestilent Fallout",
            "requires_bearer_source_match": True,
        },
    ),
    "000010131004": EnhancementToolDescriptor(
        enhancement_id="000010131004",
        name="Needle of Nurgle",
        timing="command_phase_when_tainted_narthecium_resolves",
        target="bearer_unit_bodyguard_models",
        duration="instant",
        effect="override_bodyguard_return_amount_roll",
        effect_params={
            "command_phase_bodyguard_return_amount_roll": "D3",
            "command_phase_bodyguard_return_max": 3,
            "requires_bearer_leading": True,
            "ability_key": "needle_of_nurgle",
        },
    ),
    "000010131005": EnhancementToolDescriptor(
        enhancement_id="000010131005",
        name="Cornucophagus",
        timing="declare_battle_formations",
        target="bearer_contagion_range_enemy_units",
        duration="until_end_of_battle",
        effect="select_additional_plague_within_bearer_contagion_range",
        effect_params={
            "select_from_default_plagues": True,
            "requires_contagion_range": True,
            "source_name": "Cornucophagus",
        },
    ),
}

_DEATH_GUARD_CHAMPIONS_OF_CONTAGION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DEATH_GUARD_CHAMPIONS_OF_CONTAGION_DESCRIPTORS.values()
}

_DEATH_GUARD_DEATH_LORDS_CHOSEN_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010143002": EnhancementToolDescriptor(
        enhancement_id="000010143002",
        name="Face of Death",
        timing="start_of_fight_phase",
        target="enemy_units_within_engagement_range_of_bearer_unit",
        duration="instant",
        effect="start_of_fight_phase_bearer_engagement_range_enemy_battleshock",
        effect_params={"requires_bearer_alive": True},
    ),
    "000010143003": EnhancementToolDescriptor(
        enhancement_id="000010143003",
        name="Vile Vigour",
        timing="passive",
        target="bearer_unit_while_bearer_is_leading",
        duration="constant_while_bearer_leading",
        effect="leading_bearer_unit_movement_bonus_and_advance_reroll",
        effect_params={
            "movement_bonus": 1,
            "reroll_advance_roll": True,
            "requires_bearer_alive": True,
            "requires_bearer_leading": True,
        },
    ),
    "000010143004": EnhancementToolDescriptor(
        enhancement_id="000010143004",
        name="Warprot Talisman",
        timing="end_of_opponent_turn_once_per_battle",
        target="bearer_unit_not_within_engagement_range",
        duration="instant",
        effect="once_per_battle_end_of_opponent_turn_enter_strategic_reserves",
        once_per_battle=True,
        effect_params={
            "ability_key": "warprot_talisman",
            "trigger_phase": "OPPONENT_TURN_END",
            "destination": "strategic_reserves",
            "requires_bearer_alive": True,
        },
    ),
    "000010143005": EnhancementToolDescriptor(
        enhancement_id="000010143005",
        name="Helm of the Fly King",
        timing="passive",
        target="bearer_unit_while_bearer_is_leading",
        duration="constant_while_bearer_leading",
        effect="leading_bearer_unit_ranged_targeting_cap",
        effect_params={
            "ranged_targeting_max_distance": 18,
            "requires_bearer_alive": True,
            "requires_bearer_leading": True,
        },
    ),
}

_DEATH_GUARD_DEATH_LORDS_CHOSEN_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DEATH_GUARD_DEATH_LORDS_CHOSEN_DESCRIPTORS.values()
}

_DEATH_GUARD_FLYBLOWN_HOST_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009729002": EnhancementToolDescriptor(
        enhancement_id="000009729002",
        name="Droning Chorus",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_ranged_weapons_gain_assault",
        effect_params={
            "assault_ranged": True,
            "requires_bearer_alive": True,
        },
    ),
    "000009729003": EnhancementToolDescriptor(
        enhancement_id="000009729003",
        name="Insectile Murmuration",
        timing="passive",
        target="bearer_unit_attacks_vs_targets_in_friendly_contagion_range",
        duration="constant",
        effect="reroll_wound_ones_vs_units_in_friendly_contagion_range",
        effect_params={
            "reroll_wound_ones": True,
            "requires_target_within_friendly_contagion_range": True,
            "requires_bearer_alive": True,
        },
    ),
    "000009729004": EnhancementToolDescriptor(
        enhancement_id="000009729004",
        name="Rejuvenating Swarm",
        timing="end_of_each_phase",
        target="bearer",
        duration="repeat_each_phase",
        effect="end_of_each_phase_bearer_regain_all_lost_wounds",
        effect_params={
            "regain_all_lost_wounds": True,
            "requires_bearer_alive": True,
        },
    ),
    "000009729005": EnhancementToolDescriptor(
        enhancement_id="000009729005",
        name="Plagueveil",
        timing="passive",
        target="bearer_unit_while_within_controlled_objective_range",
        duration="constant_while_condition_met",
        effect="controlled_objective_bearer_unit_ranged_targeting_cap",
        effect_params={
            "ranged_targeting_max_distance": 18,
            "requires_within_controlled_objective_range": True,
            "requires_bearer_alive": True,
        },
    ),
}

_DEATH_GUARD_FLYBLOWN_HOST_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DEATH_GUARD_FLYBLOWN_HOST_DESCRIPTORS.values()
}

_DEATH_GUARD_MORTARIONS_HAMMER_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010127002": EnhancementToolDescriptor(
        enhancement_id="000010127002",
        name="Eye of Affliction",
        timing="passive",
        target="bearer_unit_ranged_attacks_vs_afflicted_enemy_units",
        duration="constant",
        effect="ranged_attacks_vs_afflicted_targets_gain_ignores_cover",
        effect_params={
            "ignores_cover": True,
            "requires_target_afflicted": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010127003": EnhancementToolDescriptor(
        enhancement_id="000010127003",
        name="Bilemaw Blight",
        timing="start_of_shooting_phase",
        target="bearer_plague_wind_weapon",
        duration="until_end_of_phase",
        effect="start_of_shooting_phase_bearer_plague_wind_range_bonus",
        effect_params={
            "weapon_name": "Plague Wind",
            "range_bonus": 12,
            "requires_bearer_alive": True,
        },
    ),
    "000010127004": EnhancementToolDescriptor(
        enhancement_id="000010127004",
        name="Shriekworm Familiar",
        timing="stratagem_cost_modification",
        target="bearer_unit",
        duration="once_per_battle_round",
        effect="once_per_battle_round_fire_overwatch_zero_cp",
        effect_params={
            "stratagem_names": ["OVERWATCH", "FIRE OVERWATCH"],
            "once_per_battle_round": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010127005": EnhancementToolDescriptor(
        enhancement_id="000010127005",
        name="Tendrilous Emissions",
        timing="passive_aura",
        target="bearer_and_friendly_death_guard_vehicle_units_within_range",
        duration="constant_while_within_aura_range",
        effect="conditional_lone_operative_and_vehicle_reroll_wound_ones_aura",
        range_in=3.0,
        effect_params={
            "vehicle_aura_range": 3.0,
            "grant_lone_operative_to_bearer": True,
            "vehicle_reroll_wound_ones": True,
            "requires_bearer_alive": True,
        },
    ),
}

_DEATH_GUARD_MORTARIONS_HAMMER_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DEATH_GUARD_MORTARIONS_HAMMER_DESCRIPTORS.values()
}

_DEATH_GUARD_TALLYBAND_SUMMONERS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010135002": EnhancementToolDescriptor(
        enhancement_id="000010135002",
        name="Beckoning Blight",
        timing="deep_strike_setup",
        target="friendly_plague_legions_unit_being_set_up",
        duration="instant_at_setup",
        effect="deep_strike_plague_legions_within_bearer_reduced_enemy_distance",
        effect_params={
            "bearer_range": 12.0,
            "min_enemy_distance": 6.0,
            "requires_unit_keyword": "PLAGUE LEGIONS",
            "requires_bearer_alive": True,
        },
    ),
    "000010135003": EnhancementToolDescriptor(
        enhancement_id="000010135003",
        name="Fell Harvester",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_weapons_attacks_bonus",
        effect_params={
            "melee_attacks_bonus": 2,
            "requires_bearer_alive": True,
        },
    ),
    "000010135004": EnhancementToolDescriptor(
        enhancement_id="000010135004",
        name="Entropic Knell",
        timing="opponent_command_phase_battle_shock_step",
        target="enemy_units_within_bearer_range_below_starting_strength",
        duration="instant",
        effect="forced_battleshock_test_with_modifier",
        range_in=6.0,
        effect_params={
            "range": 6.0,
            "battle_shock_test_modifier": -1,
            "requires_target_below_starting_strength": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010135005": EnhancementToolDescriptor(
        enhancement_id="000010135005",
        name="Tome of Bounteous Blessings",
        timing="on_friendly_battleshock_test",
        target="friendly_plague_legions_units_within_bearer_range",
        duration="instant_per_test",
        effect="friendly_battleshock_modifier_with_restore_on_pass",
        range_in=12.0,
        effect_params={
            "range": 12.0,
            "battle_shock_test_modifier": 1,
            "restore_die": "D3",
            "requires_target_keyword": "PLAGUE LEGIONS",
            "requires_bearer_alive": True,
        },
    ),
}

_DEATH_GUARD_TALLYBAND_SUMMONERS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DEATH_GUARD_TALLYBAND_SUMMONERS_DESCRIPTORS.values()
}

_DEATH_GUARD_SHAMBLEROT_VECTORIUM_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010139002": EnhancementToolDescriptor(
        enhancement_id="000010139002",
        name="Witherbone Pipes",
        timing="passive",
        target="models_in_bearer_led_poxwalkers_unit",
        duration="constant_while_bearer_leading",
        effect="leading_poxwalkers_unit_objective_control_bonus_and_leadership_test_modifier",
        effect_params={
            "objective_control_bonus": 1,
            "leadership_test_modifier": 1,
            "requires_bearer_alive": True,
            "requires_bearer_leading": True,
            "requires_led_unit_name": "Poxwalkers",
        },
    ),
    "000010139003": EnhancementToolDescriptor(
        enhancement_id="000010139003",
        name="Lord of the Walking Pox",
        timing="movement_phase_while_in_strategic_reserves",
        target="bearer_led_poxwalkers_unit_in_strategic_reserves",
        duration="constant_while_in_strategic_reserves",
        effect="strategic_reserves_setup_treat_current_round_as_third",
        effect_params={
            "strategic_reserves_setup_treat_as_round": 3,
            "requires_bearer_alive": True,
            "requires_bearer_leading": True,
            "requires_led_unit_name": "Poxwalkers",
        },
    ),
    "000010139004": EnhancementToolDescriptor(
        enhancement_id="000010139004",
        name="Sorrowsyphon",
        timing="passive_and_post_shooting",
        target="bearer_plague_wind_attacks_while_leading_poxwalkers_unit",
        duration="constant_and_instant_post_attack",
        effect="leading_poxwalkers_unit_bearer_plague_wind_damage_bonus_with_bodyguard_loss",
        effect_params={
            "weapon_name": "Plague Wind",
            "plague_wind_damage_bonus": 1,
            "bodyguard_loss_die": "D3",
            "requires_bearer_alive": True,
            "requires_bearer_leading": True,
            "requires_led_unit_name": "Poxwalkers",
        },
    ),
    "000010139005": EnhancementToolDescriptor(
        enhancement_id="000010139005",
        name="Talisman of Burgeoning",
        timing="passive",
        target="poxwalkers_models_in_bearer_led_unit",
        duration="constant_while_bearer_leading",
        effect="leading_unit_poxwalkers_models_toughness_bonus",
        effect_params={
            "toughness_bonus": 1,
            "requires_bearer_alive": True,
            "requires_bearer_leading": True,
            "requires_led_unit_name": "Poxwalkers",
        },
    ),
}

_DEATH_GUARD_SHAMBLEROT_VECTORIUM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _DEATH_GUARD_SHAMBLEROT_VECTORIUM_DESCRIPTORS.values()
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

_GREY_KNIGHTS_BROTHERHOOD_STRIKE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010348002": EnhancementToolDescriptor(
        enhancement_id="000010348002",
        name="Banishing Wave (Psychic)",
        timing="on_unit_set_up_as_reinforcements",
        target="enemy_units_within_range_of_bearer",
        duration="instant",
        effect="deep_strike_setup_enemy_mortal_wound_table",
        range_in=12.0,
        effect_params={
            "range": 12,
            "trigger_roll": "D6",
            "low_roll_min": 2,
            "low_roll_max": 5,
            "low_mortal_wounds": 1,
            "high_roll_threshold": 6,
            "high_mortal_wounds_roll": "D3",
            "requires_bearer_alive": True,
        },
    ),
    "000010348003": EnhancementToolDescriptor(
        enhancement_id="000010348003",
        name="Blinding Aura",
        timing="on_unit_set_up_as_reinforcements",
        target="bearer_unit",
        duration="until_end_of_turn",
        effect="prevent_fire_overwatch_against_bearer_unit_on_deep_strike_setup_turn",
        effect_params={
            "requires_bearer_alive": True,
        },
    ),
    "000010348004": EnhancementToolDescriptor(
        enhancement_id="000010348004",
        name="Purity of Purpose",
        timing="on_unit_set_up_as_reinforcements",
        target="bearer_unit",
        duration="until_end_of_turn",
        effect="grant_charge_reroll_on_deep_strike_setup_turn",
        effect_params={
            "charge_reroll": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010348005": EnhancementToolDescriptor(
        enhancement_id="000010348005",
        name="Tome of Forbidden Ways",
        timing="passive",
        target="gate_of_infinity_army_rule",
        duration="while_bearer_on_battlefield_or_in_strategic_reserves",
        effect="increase_gate_of_infinity_max_units",
        effect_params={
            "additional_max_units": 1,
            "requires_bearer_on_battlefield_or_strategic_reserves": True,
        },
    ),
}

_GREY_KNIGHTS_BROTHERHOOD_STRIKE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GREY_KNIGHTS_BROTHERHOOD_STRIKE_DESCRIPTORS.values()
}

_GREY_KNIGHTS_AUGURIUM_TASK_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010364002": EnhancementToolDescriptor(
        enhancement_id="000010364002",
        name="Grimoire of Conjunctions",
        timing="start_of_fight_phase_once_per_battle",
        target="bearer_unit",
        duration="until_end_of_phase",
        effect="optional_bearer_melee_strength_bonus",
        once_per_battle=True,
        effect_params={
            "bearer_melee_strength_bonus": 4,
            "once_per_battle_key": "grimoire_of_conjunctions",
            "requires_bearer_alive": True,
            "optional": True,
        },
    ),
    "000010364003": EnhancementToolDescriptor(
        enhancement_id="000010364003",
        name="Shield of Prophecy",
        timing="start_of_battle_round_once_per_battle",
        target="bearer_unit",
        duration="until_end_of_battle_round",
        effect="optional_bearer_unit_toughness_bonus",
        once_per_battle=True,
        effect_params={
            "bearer_unit_toughness_bonus": 2,
            "once_per_battle_key": "shield_of_prophecy",
            "requires_bearer_alive": True,
            "optional": True,
        },
    ),
    "000010364004": EnhancementToolDescriptor(
        enhancement_id="000010364004",
        name="A Foot in the Future",
        timing="on_unit_set_up_as_reinforcements",
        target="bearer_unit",
        duration="immediate_then_until_end_of_turn",
        effect="optional_reactive_normal_move_after_reinforcements_setup",
        effect_params={
            "move_roll": "D6",
            "no_charge_this_turn": True,
            "requires_bearer_alive": True,
            "optional": True,
        },
    ),
    "000010364005": EnhancementToolDescriptor(
        enhancement_id="000010364005",
        name="Doomseer's Amulet",
        timing="on_unit_set_up_as_reinforcements",
        target="enemy_unit_within_range_visible",
        duration="instant",
        effect="optional_select_enemy_battleshock_on_reinforcements_setup",
        range_in=12.0,
        effect_params={
            "range": 12,
            "test_penalty": 1,
            "requires_visibility": True,
            "optional": True,
            "requires_bearer_alive": True,
        },
    ),
}

_GREY_KNIGHTS_AUGURIUM_TASK_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GREY_KNIGHTS_AUGURIUM_TASK_FORCE_DESCRIPTORS.values()
}

_GREY_KNIGHTS_BANISHERS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010356002": EnhancementToolDescriptor(
        enhancement_id="000010356002",
        name="Sigil of the Hunt",
        timing="passive",
        target="bearer_unit_ranged_attacks",
        duration="your_shooting_phase",
        effect="reroll_hit_roll_of_1",
        effect_params={
            "attack_type": "ranged",
            "reroll_hit_values": (1,),
            "requires_bearer_alive": True,
        },
    ),
    "000010356003": EnhancementToolDescriptor(
        enhancement_id="000010356003",
        name="The Ephemeral Tome",
        timing="start_of_your_shooting_phase",
        target="bearer_unit",
        duration="immediate_then_until_end_of_turn",
        effect="optional_reactive_normal_move_start_of_shooting_no_charge",
        effect_params={
            "move_roll": "D6",
            "no_charge_this_turn": True,
            "requires_bearer_alive": True,
            "optional": True,
        },
    ),
    "000010356004": EnhancementToolDescriptor(
        enhancement_id="000010356004",
        name="The Sixty-sixth Seal",
        timing="passive",
        target="bearer_unit_ranged_attacks",
        duration="your_shooting_phase",
        effect="ranged_ap_bonus",
        effect_params={
            "attack_type": "ranged",
            "ap_bonus": 1,
            "requires_bearer_alive": True,
        },
    ),
    "000010356005": EnhancementToolDescriptor(
        enhancement_id="000010356005",
        name="Pyresoul (Psychic)",
        timing="start_of_your_shooting_phase",
        target="enemy_unit_within_range_visible",
        duration="instant",
        effect="optional_select_enemy_mortal_wounds",
        range_in=24.0,
        effect_params={
            "range": 24,
            "mortal_wounds_roll": "D3",
            "requires_visibility": True,
            "requires_bearer_alive": True,
            "optional": True,
        },
    ),
}

_GREY_KNIGHTS_BANISHERS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GREY_KNIGHTS_BANISHERS_DESCRIPTORS.values()
}

_GREY_KNIGHTS_HALLOWED_CONCLAVE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010352002": EnhancementToolDescriptor(
        enhancement_id="000010352002",
        name="Eye of the Augurium",
        timing="when_targeted_with_fire_overwatch_or_heroic_intervention",
        target="bearer_unit",
        duration="instant",
        effect="stratagem_cp_cost_set_zero_with_repeat_exception",
        effect_params={
            "stratagems": ("OVERWATCH", "FIRE OVERWATCH", "HEROIC INTERVENTION"),
            "limit": "battle_round",
        },
    ),
    "000010352003": EnhancementToolDescriptor(
        enhancement_id="000010352003",
        name="Inescapable Judgement (Psychic)",
        timing="on_enemy_unit_fall_back_within_bearer_unit_engagement_range",
        target="enemy_unit_that_fell_back_from_bearer_unit",
        duration="instant",
        effect="optional_enemy_fall_back_mortal_wound_table",
        effect_params={
            "low_roll_min": 2,
            "low_roll_max": 5,
            "low_mortal_wounds_roll": "D3",
            "high_roll_threshold": 6,
            "high_mortal_wounds_roll": "D3+3",
            "requires_bearer_alive": True,
            "optional": True,
        },
    ),
    "000010352004": EnhancementToolDescriptor(
        enhancement_id="000010352004",
        name="Sanctic Reaper",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_attacks_bonus",
        effect_params={
            "bearer_melee_attacks_bonus": 3,
            "requires_bearer_alive": True,
        },
    ),
    "000010352005": EnhancementToolDescriptor(
        enhancement_id="000010352005",
        name="Nemesis Rounds",
        timing="when_targeted_with_fire_overwatch",
        target="bearer_unit",
        duration="while_resolving_fire_overwatch",
        effect="fire_overwatch_hit_threshold",
        effect_params={
            "overwatch_hit_threshold": 5,
            "stratagems": ("OVERWATCH", "FIRE OVERWATCH"),
            "requires_bearer_alive": True,
        },
    ),
}

_GREY_KNIGHTS_HALLOWED_CONCLAVE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GREY_KNIGHTS_HALLOWED_CONCLAVE_DESCRIPTORS.values()
}

_GREY_KNIGHTS_SANCTIC_SPEARHEAD_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010360002": EnhancementToolDescriptor(
        enhancement_id="000010360002",
        name="Driven by Duty",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_pile_in_and_consolidate_distance_override",
        effect_params={
            "pile_in_distance_override": 6,
            "consolidate_distance_override": 6,
            "requires_bearer_alive": True,
        },
    ),
    "000010360003": EnhancementToolDescriptor(
        enhancement_id="000010360003",
        name="Quickening Foci",
        timing="on_unit_disembark_from_transport",
        target="bearer_unit",
        duration="until_end_of_turn",
        effect="disembark_this_turn_charge_reroll",
        effect_params={
            "charge_reroll": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010360004": EnhancementToolDescriptor(
        enhancement_id="000010360004",
        name="Sigil of Exigence",
        timing="when_targeted_by_ranged_attack_once_per_battle",
        target="bearer_unit",
        duration="instant",
        effect="optional_redeploy_bearer_unit_more_than_9_horizontal_from_enemy_models",
        once_per_battle=True,
        effect_params={
            "min_enemy_distance_horiz": 9,
            "once_per_battle_key": "sigil_of_exigence",
            "requires_bearer_alive": True,
            "optional": True,
        },
    ),
    "000010360005": EnhancementToolDescriptor(
        enhancement_id="000010360005",
        name="Spiritus Machina",
        timing="when_selected_to_shoot_after_disembark",
        target="bearer_unit",
        duration="until_end_of_phase",
        effect="disembarked_this_turn_shooting_wound_reroll",
        effect_params={
            "reroll_wound": True,
            "requires_bearer_alive": True,
        },
    ),
}

_GREY_KNIGHTS_SANCTIC_SPEARHEAD_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GREY_KNIGHTS_SANCTIC_SPEARHEAD_DESCRIPTORS.values()
}

_CHAOS_KNIGHTS_HOUNDPACK_LANCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010312002": EnhancementToolDescriptor(
        enhancement_id="000010312002",
        name="Preyslayer's Mantle",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="grant_super_heavy_walker",
    ),
    "000010312003": EnhancementToolDescriptor(
        enhancement_id="000010312003",
        name="Final Howl (Aura)",
        timing="passive_aura",
        target="friendly_war_dog_models_within_range",
        duration="constant",
        effect="reroll_wound_roll_of_1",
        range_in=6.0,
        effect_params={"reroll_wound_values": (1,), "requires_keyword": "WAR DOG"},
    ),
    "000010312004": EnhancementToolDescriptor(
        enhancement_id="000010312004",
        name="Loping Predator",
        timing="passive",
        target="bearer_ranged_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={"attack_type": "ranged", "keywords": ("ASSAULT",)},
    ),
    "000010312005": EnhancementToolDescriptor(
        enhancement_id="000010312005",
        name="Panoply of the Cursed Knight",
        timing="passive_defensive",
        target="attacks_targeting_bearer",
        duration="constant",
        effect="worsen_incoming_ap",
        effect_params={"ap_worsen": 1},
    ),
}

_CHAOS_KNIGHTS_HOUNDPACK_LANCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CHAOS_KNIGHTS_HOUNDPACK_LANCE_DESCRIPTORS.values()
}

_CHAOS_KNIGHTS_HELHUNT_LANCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010751002": EnhancementToolDescriptor(
        enhancement_id="000010751002",
        name="Aspect of the Beast",
        timing="start_of_command_phase",
        target="bearer",
        duration="until_start_of_next_command_phase",
        effect="select_bearer_specific_dread_ability",
        effect_params={
            "dread_keys": ("DESPAIR", "DOOM", "DARKNESS", "DISMAY", "DELIRIUM", "DOMINION"),
        },
    ),
    "000010751003": EnhancementToolDescriptor(
        enhancement_id="000010751003",
        name="Hunter's Helm",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="reroll_advance_and_charge",
    ),
    "000010751004": EnhancementToolDescriptor(
        enhancement_id="000010751004",
        name="Octagram of Conjuration",
        timing="passive_aura",
        target="friendly_war_dog_models_within_range",
        duration="constant",
        effect="post_shoot_battleshock_for_friendly_war_dog_models",
        range_in=9.0,
    ),
    "000010751005": EnhancementToolDescriptor(
        enhancement_id="000010751005",
        name="Throne Tyrannicus",
        timing="command_phase",
        target="other_friendly_chaos_knights_character_within_range",
        duration="until_start_of_next_command_phase",
        effect="selected_character_affected_by_bearer_war_dog_auras",
        range_in=9.0,
    ),
}

_CHAOS_KNIGHTS_HELHUNT_LANCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CHAOS_KNIGHTS_HELHUNT_LANCE_DESCRIPTORS.values()
}

_CHAOS_KNIGHTS_TRAITORIS_LANCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008516002": EnhancementToolDescriptor(
        enhancement_id="000008516002",
        name="Nightmare's Master",
        timing="start_of_fight_phase",
        target="enemy_units_within_bearer_engagement_range",
        duration="instant",
        effect="force_battleshock_for_enemy_units_within_bearer_engagement_range",
    ),
    "000008516003": EnhancementToolDescriptor(
        enhancement_id="000008516003",
        name="Tyrant's Shadow",
        timing="end_of_command_phase",
        target="objective_marker_within_range_you_control",
        duration="until_opponent_has_higher_level_of_control",
        effect="objective_marker_sticky_control_and_harbingers_deathly_terror",
        effect_params={"grants_dread_key": "DEATHLY_TERROR"},
    ),
    "000008516004": EnhancementToolDescriptor(
        enhancement_id="000008516004",
        name="Malevolent Heraldry",
        timing="on_random_harbingers_roll",
        target="army_harbingers_roll",
        duration="instant",
        effect="optional_reroll_one_or_both_harbingers_dice",
        effect_params={"reroll_modes": ("keep", "reroll_first", "reroll_second", "reroll_both")},
    ),
    "000008516005": EnhancementToolDescriptor(
        enhancement_id="000008516005",
        name="Veil of Medrengard",
        timing="passive_defensive",
        target="bearer",
        duration="constant",
        effect="bearer_attack_type_specific_invulnerable_save",
        effect_params={"ranged_invulnerable_save": 4, "melee_invulnerable_save": 5},
    ),
}

_CHAOS_KNIGHTS_TRAITORIS_LANCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CHAOS_KNIGHTS_TRAITORIS_LANCE_DESCRIPTORS.values()
}

_CHAOS_KNIGHTS_LORDS_OF_DREAD_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010308002": EnhancementToolDescriptor(
        enhancement_id="000010308002",
        name="Throne Mechanicum of Skulls",
        timing="passive_and_start_of_charge_phase",
        target="bearer_unit",
        duration="constant_and_until_end_of_phase",
        effect="reroll_charge_and_optional_charge_after_advance_once_per_battle",
        once_per_battle=True,
        effect_params={"once_per_battle_key": "throne_mechanicum_of_skulls"},
    ),
    "000010308003": EnhancementToolDescriptor(
        enhancement_id="000010308003",
        name="Blade of Celerity",
        timing="passive_and_start_of_fight_phase",
        target="bearer_unit",
        duration="constant_and_until_end_of_phase",
        effect="grant_assault_and_optional_fights_first_once_per_battle",
        once_per_battle=True,
    ),
    "000010308004": EnhancementToolDescriptor(
        enhancement_id="000010308004",
        name="Warp-borne Stalker",
        timing="passive_and_end_of_opponent_turn",
        target="bearer",
        duration="constant_and_instant",
        effect="grant_deep_strike_and_optional_strategic_reserves_once_per_battle",
        once_per_battle=True,
        effect_params={"once_per_battle_key": "warp_borne_stalker"},
    ),
    "000010308005": EnhancementToolDescriptor(
        enhancement_id="000010308005",
        name="Putrid Carapace",
        timing="passive_and_start_of_command_phase",
        target="bearer",
        duration="constant_and_instant",
        effect="set_save_characteristic_and_optional_regain_wounds_once_per_battle",
        once_per_battle=True,
        effect_params={"save_characteristic": 2, "heal_roll": "D6", "once_per_battle_key": "putrid_carapace"},
    ),
    "000010308006": EnhancementToolDescriptor(
        enhancement_id="000010308006",
        name="Mirror of Fates",
        timing="passive",
        target="bearer_unit_and_enemy_units_within_range",
        duration="constant_and_once_per_battle_round",
        effect="command_reroll_cost_set_zero_once_per_battle_round_and_stratagem_cp_increase_aura",
        range_in=12.0,
        effect_params={"aura_range": 12, "cp_increase": 1, "ability_name": "Lord of Deceit (Aura)"},
    ),
    "000010308007": EnhancementToolDescriptor(
        enhancement_id="000010308007",
        name="Blessing of the Dark Master",
        timing="passive_and_after_saving_throw",
        target="bearer",
        duration="constant_and_instant_once_per_battle",
        effect="grant_stealth_and_optional_set_allocated_attack_damage_to_zero",
        once_per_battle=True,
        effect_params={"damage_zero_usage": "battle"},
    ),
}

_CHAOS_KNIGHTS_LORDS_OF_DREAD_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _CHAOS_KNIGHTS_LORDS_OF_DREAD_DESCRIPTORS.values()
}

_IMPERIAL_KNIGHTS_QUESTOR_FORGEPACT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009761003": EnhancementToolDescriptor(
        enhancement_id="000009761003",
        name="Knight of the Opus Machina",
        timing="ranged_attack",
        target="bearer",
        duration="constant",
        effect="bearer_ranged_attacks_reroll_hit_ones_while_near_friendly_adeptus_mechanicus",
        effect_params={"range_in": 6.0},
    ),
    "000009761004": EnhancementToolDescriptor(
        enhancement_id="000009761004",
        name="Magos Questoris",
        timing="command_phase_and_passive",
        target="bearer_and_friendly_imperial_knights_unit",
        duration="constant_and_instant",
        effect="grant_lone_operative_while_near_friendly_imperial_knights_and_heal_selected_knight",
        effect_params={"range_in": 3.0, "heal_amount": 2},
    ),
    "000009761005": EnhancementToolDescriptor(
        enhancement_id="000009761005",
        name="Vocifer Magnificat (Aura)",
        timing="passive",
        target="enemy_units_and_friendly_adeptus_mechanicus_units_within_aura",
        duration="constant",
        effect="enemy_leadership_penalty_aura_and_friendly_adeptus_mechanicus_leadership_bonus_aura",
        range_in=6.0,
        effect_params={"aura_range": 6.0, "leadership_penalty": 1, "leadership_bonus": 1},
    ),
}

_IMPERIAL_KNIGHTS_QUESTOR_FORGEPACT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _IMPERIAL_KNIGHTS_QUESTOR_FORGEPACT_DESCRIPTORS.values()
}

_IMPERIAL_KNIGHTS_GATE_WARDEN_LANCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010497002": EnhancementToolDescriptor(
        enhancement_id="000010497002",
        name="Acquisitor-at-Arms",
        timing="passive",
        target="friendly_bondsman_models",
        duration="constant",
        effect="bondsman_models_gain_bearer_objective_control_while_bearer_holds_enemy_free_defensive_line",
        effect_params={
            "requires_bearer_on_defensive_line": True,
            "requires_no_enemy_units_on_defensive_line": True,
        },
    ),
    "000010497003": EnhancementToolDescriptor(
        enhancement_id="000010497003",
        name="Purgation's Hand",
        timing="melee_attack",
        target="bearer",
        duration="constant",
        effect="bearer_melee_attacks_reroll_hit_and_wound_ones_on_defensive_line",
        effect_params={"requires_bearer_on_defensive_line": True},
    ),
    "000010497004": EnhancementToolDescriptor(
        enhancement_id="000010497004",
        name="Augury Halo",
        timing="ranged_attack",
        target="bearer",
        duration="constant",
        effect="bearer_ranged_weapons_gain_ignores_cover_on_defensive_line",
        effect_params={"requires_bearer_on_defensive_line": True},
    ),
    "000010497005": EnhancementToolDescriptor(
        enhancement_id="000010497005",
        name="Vengeful Tread",
        timing="when_targeting_bearer_with_tank_shock",
        target="bearer",
        duration="instant_once_per_turn",
        effect="tank_shock_zero_cp_once_per_turn_for_bearer",
        effect_params={
            "stratagem_names": ("TANK SHOCK",),
            "once_per_turn_key": "VENGEFUL_TREAD_TANK_SHOCK",
            "requires_bearer_on_battlefield": True,
        },
    ),
}

_IMPERIAL_KNIGHTS_GATE_WARDEN_LANCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _IMPERIAL_KNIGHTS_GATE_WARDEN_LANCE_DESCRIPTORS.values()
}

_IMPERIAL_KNIGHTS_FREEBLADE_COMPANY_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010755002": EnhancementToolDescriptor(
        enhancement_id="000010755002",
        name="Bringer of Justice",
        timing="melee_attack",
        target="bearer",
        duration="constant",
        effect="bearer_melee_attacks_bonus_and_hit_bonus",
        effect_params={"attacks_bonus": 2, "hit_bonus": 1},
    ),
    "000010755003": EnhancementToolDescriptor(
        enhancement_id="000010755003",
        name="Hunter's Eye",
        timing="ranged_attack",
        target="bearer_ranged_weapons",
        duration="constant",
        effect="bearer_ranged_weapons_gain_keywords",
        effect_params={"keywords": ("IGNORES COVER",)},
    ),
    "000010755004": EnhancementToolDescriptor(
        enhancement_id="000010755004",
        name="Mysterious Guardian",
        timing="passive_and_end_of_opponent_turn",
        target="bearer",
        duration="constant_and_once_per_battle",
        effect="bearer_deep_strike_and_end_of_opponent_turn_strategic_reserves",
        once_per_battle=True,
        effect_params={"once_per_battle_key": "mysterious_guardian"},
    ),
    "000010755005": EnhancementToolDescriptor(
        enhancement_id="000010755005",
        name="Sanctuary",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_unit_invulnerable_save",
        effect_params={"invulnerable_save": 5},
    ),
}

_IMPERIAL_KNIGHTS_FREEBLADE_COMPANY_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _IMPERIAL_KNIGHTS_FREEBLADE_COMPANY_DESCRIPTORS.values()
}

_IMPERIAL_KNIGHTS_QUESTORIS_COMPANIONS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010502002": EnhancementToolDescriptor(
        enhancement_id="000010502002",
        name="Herald of Triumph",
        timing="on_charge_move_end",
        target="enemy_units_within_engagement_range_of_bearer",
        duration="instant_until_oath_fulfilled",
        effect="optional_bearer_charge_end_battleshock_aura",
        effect_params={
            "battle_shock_test_modifier": -1,
            "expended_until_oath_fulfilled": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010502003": EnhancementToolDescriptor(
        enhancement_id="000010502003",
        name="Wyrmslayer Divination",
        timing="when_bearer_is_selected_to_shoot",
        target="bearer_ranged_attacks_vs_fly",
        duration="until_end_of_phase_until_oath_fulfilled",
        effect="optional_bearer_ranged_attacks_reroll_hits_vs_fly",
        effect_params={
            "target_keywords_any": ("FLY",),
            "expended_until_oath_fulfilled": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010502004": EnhancementToolDescriptor(
        enhancement_id="000010502004",
        name="Pennant of Silvered Fury",
        timing="when_bearer_is_selected_to_fight",
        target="bearer_melee_weapons",
        duration="until_end_of_phase_until_oath_fulfilled",
        effect="optional_grant_weapon_keywords",
        effect_params={
            "attack_type": "melee",
            "keywords": ("SUSTAINED HITS 2",),
            "expended_until_oath_fulfilled": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010502005": EnhancementToolDescriptor(
        enhancement_id="000010502005",
        name="Crushing Condemnation",
        timing="after_bearer_fight_if_enemy_destroyed",
        target="enemy_unit_within_12_visible_not_engaged_with_friendly",
        duration="instant_until_oath_fulfilled",
        effect="optional_select_enemy_and_roll_six_d6_for_mortal_wounds",
        range_in=12.0,
        effect_params={
            "roll_count": 6,
            "mortal_wound_threshold": 4,
            "requires_visibility": True,
            "disallow_units_within_engagement_range_of_friendly": True,
            "expended_until_oath_fulfilled": True,
            "requires_bearer_alive": True,
        },
    ),
}

_IMPERIAL_KNIGHTS_QUESTORIS_COMPANIONS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _IMPERIAL_KNIGHTS_QUESTORIS_COMPANIONS_DESCRIPTORS.values()
}

_IMPERIAL_KNIGHTS_SPEARHEAD_AT_ARMS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010506002": EnhancementToolDescriptor(
        enhancement_id="000010506002",
        name="Mentor's Pride",
        timing="passive",
        target="friendly_armiger_under_bearers_bondsman",
        duration="constant",
        effect="bondsman_armigers_reroll_hit_ones_while_two_or_more_are_affected",
        effect_params={
            "required_target_keyword": "ARMIGER",
            "required_min_bondsman_targets": 2,
            "requires_bearer_on_battlefield": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010506003": EnhancementToolDescriptor(
        enhancement_id="000010506003",
        name="Fables of Nightmare",
        timing="passive",
        target="friendly_armiger_under_bearers_bondsman_melee_weapons",
        duration="constant",
        effect="bondsman_armigers_gain_precision_while_two_or_more_are_affected",
        effect_params={
            "required_target_keyword": "ARMIGER",
            "required_min_bondsman_targets": 2,
            "attack_type": "melee",
            "keywords": ("PRECISION",),
            "requires_bearer_on_battlefield": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010506004": EnhancementToolDescriptor(
        enhancement_id="000010506004",
        name="Tales of Heroism",
        timing="passive",
        target="friendly_armiger_under_bearers_bondsman_melee_attacks",
        duration="constant",
        effect="bondsman_armigers_ignore_hit_and_wound_modifiers_while_two_or_more_are_affected",
        effect_params={
            "required_target_keyword": "ARMIGER",
            "required_min_bondsman_targets": 2,
            "attack_type": "melee",
            "ignore_hit_modifiers": True,
            "ignore_wound_modifiers": True,
            "requires_bearer_on_battlefield": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010506005": EnhancementToolDescriptor(
        enhancement_id="000010506005",
        name="Martial Tuition",
        timing="when_targeting_bondsman_armiger_with_counter_offensive",
        target="friendly_armiger_under_bearers_bondsman",
        duration="instant_once_per_turn",
        effect="counter_offensive_zero_cp_once_per_turn_for_bondsman_armiger",
        effect_params={
            "stratagem_names": ("COUNTER-OFFENSIVE",),
            "once_per_turn_key": "MARTIAL_TUITION_COUNTER_OFFENSIVE",
            "required_target_keyword": "ARMIGER",
            "required_min_bondsman_targets": 2,
            "requires_bearer_on_battlefield": True,
        },
    ),
}

_IMPERIAL_KNIGHTS_SPEARHEAD_AT_ARMS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _IMPERIAL_KNIGHTS_SPEARHEAD_AT_ARMS_DESCRIPTORS.values()
}

_VEILED_BLADE_ELIMINATION_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009757002": EnhancementToolDescriptor(
        enhancement_id="000009757002",
        name="Decoy Targets",
        timing="movement_phase",
        target="other_friendly_infantry_model_and_bearer",
        duration="instant",
        effect="destroy_selected_model_and_redeploy_bearer",
        effect_params={
            "max_uses": 2,
            "per_battle_round_limit": 1,
            "selection_excludes_bearer": True,
            "disallow_engagement_range_targets": True,
        },
    ),
    "000009757003": EnhancementToolDescriptor(
        enhancement_id="000009757003",
        name="Esoteric Explosives",
        timing="when_targeted_by_grenades_stratagem",
        target="bearer",
        duration="instant",
        effect="grenade_mortal_wound_threshold_modifier",
        effect_params={
            "grenade_mortal_threshold": 3,
            "default_threshold": 4,
        },
    ),
    "000009757004": EnhancementToolDescriptor(
        enhancement_id="000009757004",
        name="Intraneural Biotech",
        timing="when_targeted_with_heroic_intervention_or_counter_offensive",
        target="bearer",
        duration="instant",
        effect="stratagem_cp_cost_set_zero_with_repeat_exception",
        effect_params={
            "stratagems": ("HEROIC INTERVENTION", "COUNTER-OFFENSIVE"),
            "limit": "battle_round",
        },
    ),
    "000009757005": EnhancementToolDescriptor(
        enhancement_id="000009757005",
        name="Micromelta Rounds",
        timing="passive",
        target="bearer_weapon_exitus_rifle",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={
            "weapon_name": "exitus rifle",
            "anti_monster": 4,
            "anti_vehicle": 4,
        },
    ),
}

_VEILED_BLADE_ELIMINATION_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _VEILED_BLADE_ELIMINATION_FORCE_DESCRIPTORS.values()
}

_GENESTEALER_CULTS_HOST_OF_ASCENSION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009067002": EnhancementToolDescriptor(
        enhancement_id="000009067002",
        name="Prowling Agitant",
        timing="on_enemy_move_ended_within_range",
        target="bearer_unit",
        duration="instant_once_per_turn",
        effect="reactive_normal_move_up_to_d6",
        range_in=9.0,
        effect_params={"max_distance_roll": "D6", "requires_not_engaged": True, "per": "turn"},
    ),
    "000009067003": EnhancementToolDescriptor(
        enhancement_id="000009067003",
        name="A Chink in Their Armour",
        timing="on_bearer_set_up_as_reinforcements",
        target="bearer_unit_ranged_weapons",
        duration="until_end_of_next_owner_fight_phase",
        effect="grant_weapon_keywords",
        effect_params={"keywords": ("LETHAL HITS",), "attack_type": "ranged"},
    ),
    "000009067004": EnhancementToolDescriptor(
        enhancement_id="000009067004",
        name="Our Time Is Nigh",
        timing="on_declare_charge",
        target="bearer_unit",
        duration="until_end_of_phase",
        effect="optional_charge_roll_bonus_once_per_battle",
        once_per_battle=True,
        effect_params={"charge_roll_bonus": 2, "once_per_battle_key": "our_time_is_nigh"},
    ),
    "000009067005": EnhancementToolDescriptor(
        enhancement_id="000009067005",
        name="Assassination Edict",
        timing="on_attack_roll",
        target="bearer_unit_attacks_vs_character",
        duration="constant",
        effect="add_hit_roll_modifier",
        effect_params={"hit_roll_bonus": 1, "target_keywords_any": ("CHARACTER",)},
    ),
}

_GENESTEALER_CULTS_HOST_OF_ASCENSION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GENESTEALER_CULTS_HOST_OF_ASCENSION_DESCRIPTORS.values()
}

_GENESTEALER_CULTS_BIOSANCTIC_BROODSURGE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009075002": EnhancementToolDescriptor(
        enhancement_id="000009075002",
        name="Predatory Instincts",
        timing="while_bearer_alive",
        target="bearer_unit",
        duration="constant_and_once_per_battle_round",
        effect="grant_infiltrators_to_bearer_unit_models_and_heroic_intervention_zero_cp_once_per_battle_round",
        effect_params={
            "requires_bearer_alive": True,
            "stratagem_names": ("HEROIC INTERVENTION",),
            "usage_key": "PREDATORY_INSTINCTS_HEROIC_INTERVENTION",
            "usage_scope": "battle_round",
        },
    ),
    "000009075003": EnhancementToolDescriptor(
        enhancement_id="000009075003",
        name="Biomorph Adaptation",
        timing="while_bearer_alive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_ap_damage_bonus",
        effect_params={"ap_bonus": 1, "damage_bonus": 1, "requires_bearer_alive": True},
    ),
    "000009075004": EnhancementToolDescriptor(
        enhancement_id="000009075004",
        name="Mutagenic Regeneration",
        timing="each_command_phase",
        target="one_model_in_bearer_unit",
        duration="instant",
        effect="command_phase_one_model_in_bearer_unit_regains_lost_wound",
        effect_params={"regain_wounds": 1, "requires_bearer_alive": True},
    ),
    "000009075005": EnhancementToolDescriptor(
        enhancement_id="000009075005",
        name="Alien Majesty",
        timing="while_bearer_alive",
        target="enemy_unit_within_engagement_range_of_bearer_unit",
        duration="constant",
        effect="enemy_objective_control_penalty_minimum",
        effect_params={"objective_control_penalty": 1, "objective_control_minimum": 1, "requires_bearer_alive": True},
    ),
}

_GENESTEALER_CULTS_BIOSANCTIC_BROODSURGE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GENESTEALER_CULTS_BIOSANCTIC_BROODSURGE_DESCRIPTORS.values()
}

_GENESTEALER_CULTS_BROOD_BROTHER_AUXILIA_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009084002": EnhancementToolDescriptor(
        enhancement_id="000009084002",
        name="Martial Espionage",
        timing="when_friendly_astra_militarum_infantry_or_mounted_unit_within_range_of_bearer_is_selected_to_shoot",
        target="friendly_astra_militarum_infantry_or_mounted_unit_within_range_of_bearer",
        duration="until_end_of_phase_once_per_turn",
        effect="optional_selected_to_shoot_ranged_ap_bonus_once_per_turn",
        effect_params={
            "range": 9.0,
            "ap_bonus": 1,
            "once_per_turn": True,
            "requires_bearer_alive": True,
            "required_target_keywords": ("ASTRA MILITARUM",),
            "required_target_any_keywords": ("INFANTRY", "MOUNTED"),
        },
    ),
    "000009084003": EnhancementToolDescriptor(
        enhancement_id="000009084003",
        name="Adaptive Reprisal",
        timing="when_targeting_friendly_genestealer_cults_unit_with_heroic_intervention",
        target="friendly_genestealer_cults_unit_within_range_of_bearer",
        duration="instant_once_per_turn",
        effect="heroic_intervention_zero_cp_once_per_turn_within_bearer_range",
        effect_params={
            "stratagem_names": ("HEROIC INTERVENTION",),
            "once_per_turn_key": "ADAPTIVE_REPRISAL_HEROIC_INTERVENTION",
            "range": 9.0,
            "required_target_keywords": ("GENESTEALER CULTS",),
            "requires_bearer_on_battlefield": True,
        },
    ),
    "000009084004": EnhancementToolDescriptor(
        enhancement_id="000009084004",
        name="The Hero Returned",
        timing="while_bearer_alive",
        target="models_in_bearers_unit",
        duration="constant",
        effect="improve_leadership_and_objective_control_of_bearers_unit",
        effect_params={
            "leadership_improvement": 1,
            "objective_control_bonus": 1,
            "requires_bearer_alive": True,
        },
    ),
    "000009084005": EnhancementToolDescriptor(
        enhancement_id="000009084005",
        name="Firepoint Commander",
        timing="while_targeting_bearers_unit_with_fire_overwatch",
        target="bearers_unit",
        duration="constant_while_bearer_alive",
        effect="fire_overwatch_hits_on_threshold",
        effect_params={
            "fire_overwatch_hit_threshold": 5,
            "requires_bearer_alive": True,
        },
    ),
}

_GENESTEALER_CULTS_BROOD_BROTHER_AUXILIA_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GENESTEALER_CULTS_BROOD_BROTHER_AUXILIA_DESCRIPTORS.values()
}

_GENESTEALER_CULTS_FINAL_DAY_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009827002": EnhancementToolDescriptor(
        enhancement_id="000009827002",
        name="Synaptic Auger",
        timing="when_bearer_regains_wounds_from_psionic_parasitism",
        target="bearer",
        duration="instant",
        effect="double_psionic_parasitism_healing_for_bearer",
        effect_params={"heal_multiplier": 2, "requires_bearer_alive": True},
    ),
    "000009827003": EnhancementToolDescriptor(
        enhancement_id="000009827003",
        name="Enraptured Damnation",
        timing="while_targeting_bearers_unit_with_fire_overwatch",
        target="bearers_unit",
        duration="constant_while_bearer_alive",
        effect="prevent_enemy_fire_overwatch_against_bearers_unit",
        effect_params={"requires_bearer_alive": True},
    ),
    "000009827004": EnhancementToolDescriptor(
        enhancement_id="000009827004",
        name="Vanguard Tyrant",
        timing="while_bearer_alive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_strength_ap_bonus",
        effect_params={"strength_bonus": 1, "ap_bonus": 1, "requires_bearer_alive": True},
    ),
    "000009827005": EnhancementToolDescriptor(
        enhancement_id="000009827005",
        name="Inhuman Integration",
        timing="while_targeting_enemy_within_range_of_friendly_tyranids",
        target="bearers_unit_weapons",
        duration="constant_while_bearer_alive",
        effect="grant_sustained_hits_one_vs_enemies_near_friendly_tyranids",
        effect_params={"range": 6.0, "sustained_hits_value": 1, "requires_bearer_alive": True},
    ),
}

_GENESTEALER_CULTS_FINAL_DAY_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GENESTEALER_CULTS_FINAL_DAY_DESCRIPTORS.values()
}

_GENESTEALER_CULTS_OUTLANDER_CLAW_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009079002": EnhancementToolDescriptor(
        enhancement_id="000009079002",
        name="Serpentine Tactics",
        timing="while_bearer_alive",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="eligible_to_shoot_after_fall_back",
        effect_params={
            "attack_type": "ranged",
            "requires_bearer_alive": True,
        },
    ),
    "000009079003": EnhancementToolDescriptor(
        enhancement_id="000009079003",
        name="Cartographic Data-leech",
        timing="while_bearer_embarked_in_transport_that_shoots_using_firing_deck",
        target="transport_firing_deck_weapons",
        duration="constant",
        effect="improve_firing_deck_ballistic_skill_while_bearer_embarked",
        effect_params={
            "ballistic_skill_improvement": 1,
            "requires_bearer_alive": True,
            "requires_bearer_embarked": True,
        },
    ),
    "000009079004": EnhancementToolDescriptor(
        enhancement_id="000009079004",
        name="Starfall Shells",
        timing="after_bearer_shoots",
        target="enemy_unit_hit_by_bearers_cult_sniper_rifle",
        duration="until_start_of_next_owner_shooting_phase",
        effect="post_shoot_select_hit_enemy_for_hit_penalty",
        effect_params={
            "weapon_name": "cult sniper rifle",
            "hit_roll_penalty": 1,
            "requires_bearer_alive": True,
        },
    ),
    "000009079005": EnhancementToolDescriptor(
        enhancement_id="000009079005",
        name="Assault Commando",
        timing="while_bearer_alive_after_disembarking_from_transport_this_turn",
        target="bearer_unit_ranged_attacks",
        duration="turn",
        effect="reroll_hit_rolls_after_disembarking_from_transport",
        effect_params={
            "attack_type": "ranged",
            "reroll_scope": "full",
            "requires_bearer_alive": True,
        },
    ),
}

_GENESTEALER_CULTS_OUTLANDER_CLAW_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GENESTEALER_CULTS_OUTLANDER_CLAW_DESCRIPTORS.values()
}

_GENESTEALER_CULTS_XENOCREED_CONGREGATION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009071002": EnhancementToolDescriptor(
        enhancement_id="000009071002",
        name="Gene-sire's Reliquant",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="reroll_battleshock_tests",
        effect_params={"requires_bearer_alive": True},
    ),
    "000009071003": EnhancementToolDescriptor(
        enhancement_id="000009071003",
        name="Denunciator of Tyrants",
        timing="on_attack_roll",
        target="bearer_unit_attacks_vs_character",
        duration="constant",
        effect="add_hit_and_wound_roll_modifier",
        effect_params={
            "hit_roll_bonus": 1,
            "wound_roll_bonus": 1,
            "target_keywords_any": ("CHARACTER",),
        },
    ),
    "000009071004": EnhancementToolDescriptor(
        enhancement_id="000009071004",
        name="Deeds That Speak to the Masses",
        timing="start_of_battle",
        target="cult_ambush_army_rule",
        duration="battle_setup",
        effect="additional_starting_resurgence_points",
        effect_params={"additional_resurgence_points": 2},
    ),
    "000009071005": EnhancementToolDescriptor(
        enhancement_id="000009071005",
        name="Incendiary Inspiration",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="charge_after_advance",
        effect_params={
            "charge_after_advance": True,
            "requires_bearer_alive": True,
        },
    ),
}

_GENESTEALER_CULTS_XENOCREED_CONGREGATION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _GENESTEALER_CULTS_XENOCREED_CONGREGATION_DESCRIPTORS.values()
}

_AGENTS_OF_THE_IMPERIUM_ORDO_HERETICUS_PURGATION_FORCE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009130002": EnhancementToolDescriptor(
        enhancement_id="000009130002",
        name="Ignis Judicium",
        timing="passive",
        target="bearer_ranged_weapons",
        duration="constant",
        effect="grant_bearer_ranged_weapon_keywords",
        effect_params={
            "attack_type": "ranged",
            "weapon_keywords": ("DEVASTATING WOUNDS", "MELTA 1", "PRECISION"),
            "melta_bonus": 1,
        },
    ),
    "000009130003": EnhancementToolDescriptor(
        enhancement_id="000009130003",
        name="Liber Heresius",
        timing="after_deployment",
        target="friendly_agents_of_the_imperium_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "allow_strategic_reserves": True,
            "redeploy_filters": ("AGENTS OF THE IMPERIUM",),
        },
    ),
    "000009130005": EnhancementToolDescriptor(
        enhancement_id="000009130005",
        name="Witch Hunter",
        timing="while_bearer_is_leading_and_bearer_unit_targets_psyker_unit",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_reroll_hit_vs_keyword_while_leading",
        effect_params={
            "required_target_keywords": ("PSYKER",),
            "requires_bearer_leading": True,
        },
    ),
}

_AGENTS_OF_THE_IMPERIUM_ORDO_HERETICUS_PURGATION_FORCE_BY_NAME = {
    _normalize_name(desc.name): desc
    for desc in _AGENTS_OF_THE_IMPERIUM_ORDO_HERETICUS_PURGATION_FORCE_DESCRIPTORS.values()
}

_AGENTS_OF_THE_IMPERIUM_ORDO_XENOS_ALIEN_HUNTERS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009126002": EnhancementToolDescriptor(
        enhancement_id="000009126002",
        name="Amulet of Auto-Chastisement",
        timing="start_of_opponent_shooting_phase",
        target="enemy_vehicle_unit_within_range_visible_excluding_titanic",
        duration="until_end_of_phase",
        effect="leadership_test_then_hit_penalty_or_ineligible_to_shoot",
        range_in=12.0,
        effect_params={
            "range": 12.0,
            "required_target_keywords": ("VEHICLE",),
            "excluded_target_keywords": ("TITANIC",),
            "resolution_mode": "leadership_test",
        },
    ),
    "000009126003": EnhancementToolDescriptor(
        enhancement_id="000009126003",
        name="Beacon Angelis",
        timing="passive_and_stratagem_targeting",
        target="bearer_unit",
        duration="constant",
        effect="grant_deep_strike_and_rapid_ingress_zero_cp",
        effect_params={
            "grants_deep_strike": True,
            "stratagem_name": "RAPID INGRESS",
            "cp_reduction": "to_zero",
        },
    ),
    "000009126005": EnhancementToolDescriptor(
        enhancement_id="000009126005",
        name="Universal Anathema",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="grant_bearer_melee_anti_infantry_and_monster",
        effect_params={
            "granted_keywords": ("ANTI-INFANTRY 2+", "ANTI-MONSTER 4+"),
            "anti_specs": (("INFANTRY", 2), ("MONSTER", 4)),
        },
    ),
}

_AGENTS_OF_THE_IMPERIUM_ORDO_XENOS_ALIEN_HUNTERS_BY_NAME = {
    _normalize_name(desc.name): desc
    for desc in _AGENTS_OF_THE_IMPERIUM_ORDO_XENOS_ALIEN_HUNTERS_DESCRIPTORS.values()
}

_AGENTS_OF_THE_IMPERIUM_ORDO_MALLEUS_DAEMON_HUNTERS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009134002": EnhancementToolDescriptor(
        enhancement_id="000009134002",
        name="Daemon Slayer",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_attacks_bonus_and_anti_daemon",
        effect_params={
            "bearer_melee_attacks_bonus": 1,
            "anti_keyword": "DAEMON",
            "anti_value": 3,
        },
    ),
    "000009134003": EnhancementToolDescriptor(
        enhancement_id="000009134003",
        name="Formidable Resolve",
        timing="passive_and_start_of_any_phase_once_per_battle",
        target="bearer_and_friendly_imperium_battleshocked_unit_within_range",
        duration="constant_and_instant",
        effect="improve_bearer_leadership_and_wounds_and_clear_battleshock_for_friendly_unit_in_range",
        range_in=12.0,
        once_per_battle=True,
        effect_params={
            "leadership_improvement": 1,
            "wounds_bonus": 1,
            "range": 12.0,
            "keyword_phrase": "IMPERIUM",
            "once_per_battle_key": "formidable_resolve",
        },
    ),
    "000009134004": EnhancementToolDescriptor(
        enhancement_id="000009134004",
        name="Gift of the Prescient",
        timing="when_targeting_grey_knights_terminator_squad_with_rapid_ingress",
        target="friendly_grey_knights_terminator_squad_unit",
        duration="instant_once_per_battle_for_cp_and_target_setup_until_resolution",
        effect="rapid_ingress_zero_cp_once_per_battle_with_three_inch_setup_for_grey_knights_terminator_squad",
        once_per_battle=True,
        effect_params={
            "stratagem_names": ("RAPID INGRESS",),
            "once_per_battle_key": "GIFT_OF_THE_PRESCIENT_RAPID_INGRESS",
            "required_target_unit_name_patterns": ("GREY KNIGHTS TERMINATOR SQUAD",),
            "requires_bearer_on_battlefield": True,
            "deep_strike_min_distance": 3.0,
            "expires_phase": "MOVEMENT_PHASE",
        },
    ),
    "000009134005": EnhancementToolDescriptor(
        enhancement_id="000009134005",
        name="Grimoire of True Names (Aura)",
        timing="passive_aura",
        target="enemy_units_within_range_of_bearer_and_enemy_daemon_attacks",
        duration="constant",
        effect="enemy_leadership_characteristic_penalty_aura_and_daemon_attack_penalties",
        range_in=9.0,
        effect_params={
            "range": 9.0,
            "leadership_penalty": 1,
            "required_target_keywords": ("DAEMON",),
            "hit_roll_penalty": 1,
            "wound_roll_penalty": 1,
            "bearer_only": True,
        },
    ),
}

_AGENTS_OF_THE_IMPERIUM_ORDO_MALLEUS_DAEMON_HUNTERS_BY_NAME = {
    _normalize_name(desc.name): desc
    for desc in _AGENTS_OF_THE_IMPERIUM_ORDO_MALLEUS_DAEMON_HUNTERS_DESCRIPTORS.values()
}

_AGENTS_OF_THE_IMPERIUM_IMPERIALIS_FLEET_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009138002": EnhancementToolDescriptor(
        enhancement_id="000009138002",
        name="Clandestine Operation",
        timing="declare_battle_formations",
        target="friendly_agents_of_the_imperium_infantry_units",
        duration="battle_setup",
        effect="select_up_to_three_units_gain_infiltrators",
        effect_params={
            "max_units": 3,
            "required_keywords": ("AGENTS OF THE IMPERIUM", "INFANTRY"),
            "excluded_unit_name_patterns": ("GREY KNIGHTS TERMINATOR SQUAD",),
        },
    ),
    "000009138003": EnhancementToolDescriptor(
        enhancement_id="000009138003",
        name="Combat Landers",
        timing="declare_battle_formations",
        target="friendly_voidfarers_units",
        duration="battle_setup",
        effect="grant_deep_strike_to_selected_units",
        effect_params={
            "max_units": 3,
            "required_keywords": ("VOIDFARERS",),
        },
    ),
    "000009138004": EnhancementToolDescriptor(
        enhancement_id="000009138004",
        name="Digital Weapons",
        timing="when_bearer_is_selected_to_fight",
        target="enemy_units_within_engagement_range_of_bearer",
        duration="instant",
        effect="selected_to_fight_precision_mortal_wounds",
        effect_params={
            "dice": 3,
            "threshold": 4,
            "mortal_wounds_per_success": 1,
            "precision_allocation": True,
        },
    ),
    "000009138005": EnhancementToolDescriptor(
        enhancement_id="000009138005",
        name="Fleetmaster",
        timing="when_targeting_bearer_unit_with_named_stratagem",
        target="bearer_unit",
        duration="instant_once_per_battle_round",
        effect="stratagem_cp_cost_set_zero",
        effect_params={
            "stratagem_names": ("VIOLENT ACQUISITION", "MASTERS OF THE VOID", "CLOSE-QUARTERS BARRAGE"),
            "once_per_battle_round_key": "FLEETMASTER_FREE_STRATAGEM",
        },
    ),
}

_AGENTS_OF_THE_IMPERIUM_IMPERIALIS_FLEET_BY_NAME = {
    _normalize_name(desc.name): desc
    for desc in _AGENTS_OF_THE_IMPERIUM_IMPERIALIS_FLEET_DESCRIPTORS.values()
}

_TAU_KAUYON_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008442002": EnhancementToolDescriptor(
        enhancement_id="000008442002",
        name="Exemplar of the Kauyon",
        timing="passive_while_bearer_is_leading",
        target="bearer_unit",
        duration="battle_rounds_2_to_5",
        effect="extend_patient_hunter_to_round_two",
    ),
    "000008442003": EnhancementToolDescriptor(
        enhancement_id="000008442003",
        name="Precision of the Patient Hunter",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_ranged_hit_bonus_and_round_three_wound_bonus",
        effect_params={
            "attack_type": "ranged",
            "hit_bonus": 1,
            "wound_bonus_from_battle_round": 3,
            "wound_bonus": 1,
        },
    ),
    "000008442004": EnhancementToolDescriptor(
        enhancement_id="000008442004",
        name="Solid-image Projection Unit",
        timing="after_deployment",
        target="friendly_tau_empire_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "allow_strategic_reserves": True,
            "redeploy_filters": ("T'AU EMPIRE",),
        },
    ),
    "000008442005": EnhancementToolDescriptor(
        enhancement_id="000008442005",
        name="Through Unity, Devastation",
        timing="on_becoming_observer_while_bearer_is_leading",
        target="guided_units_targeting_spotted_unit",
        duration="until_end_of_phase",
        effect="grant_ranged_lethal_hits_vs_spotted",
        effect_params={"lethal_hits": True},
    ),
}

_TAU_KAUYON_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _TAU_KAUYON_DESCRIPTORS.values()
}

_THOUSAND_SONS_CHANGEHOST_OF_DECEIT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010197002": EnhancementToolDescriptor(
        enhancement_id="000010197002",
        name="Nethershriek Mind-eater",
        timing="start_of_shooting_phase",
        target="enemy_unit_within_range_visible_to_bearer",
        duration="instant",
        effect="visible_enemy_battleshock_test_with_mortal_wounds_on_failure",
        range_in=12.0,
        effect_params={
            "range": 12.0,
            "fail_mortal_wounds": 3,
            "leadership_test_counts_as_battle_shock": True,
        },
    ),
    "000010197003": EnhancementToolDescriptor(
        enhancement_id="000010197003",
        name="Diabolic Savant",
        timing="while_channeling_the_warp",
        target="bearer",
        duration="instant_conditional",
        effect="ritual_test_bonus_while_nearby_scintillating_legions",
        range_in=6.0,
        effect_params={
            "range": 6.0,
            "ritual_test_bonus": 1,
            "requires_channel_the_warp": True,
            "required_friendly_keyword": "SCINTILLATING LEGIONS",
        },
    ),
    "000010197004": EnhancementToolDescriptor(
        enhancement_id="000010197004",
        name="Duplicitous Malediction",
        timing="after_deployment",
        target="friendly_thousand_sons_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "allow_strategic_reserves": True,
            "redeploy_filters": ("THOUSAND SONS",),
        },
    ),
    "000010197005": EnhancementToolDescriptor(
        enhancement_id="000010197005",
        name="Tome of True Names",
        timing="start_of_any_phase",
        target="bearer",
        duration="until_end_of_phase_once_per_battle",
        effect="bearer_invulnerable_save",
        once_per_battle=True,
        effect_params={
            "invulnerable_save": 2,
            "once_per_battle_key": "start_any_phase_invuln:tome_of_true_names",
        },
    ),
}

_THOUSAND_SONS_CHANGEHOST_OF_DECEIT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _THOUSAND_SONS_CHANGEHOST_OF_DECEIT_DESCRIPTORS.values()
}

_THOUSAND_SONS_HEXWARP_THRALLBAND_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009741002": EnhancementToolDescriptor(
        enhancement_id="000009741002",
        name="Arcane Might",
        timing="passive_and_flow_of_magic_conditional",
        target="models_in_bearer_unit_psychic_weapons",
        duration="constant",
        effect="psychic_weapon_strength_bonus_for_bearer_unit",
        effect_params={
            "base_strength_bonus": 1,
            "flow_strength_bonus": 2,
        },
    ),
    "000009741003": EnhancementToolDescriptor(
        enhancement_id="000009741003",
        name="Empowered Manifestation",
        timing="passive_while_bearer_unit_wholly_within_flow",
        target="bearer_psychic_abilities_and_bearer_unit_psychic_hazardous_tests",
        duration="constant_conditional",
        effect="ritual_range_and_hazardous_reroll_while_within_flow",
        effect_params={
            "range_bonus": 6,
            "ritual_range_bonus": 6,
            "hazardous_reroll": True,
            "requires_wholly_within_flow_of_magic": True,
        },
    ),
    "000009741004": EnhancementToolDescriptor(
        enhancement_id="000009741004",
        name="Empyric Onslaught",
        timing="passive_while_bearer_unit_wholly_within_flow",
        target="bearer_ranged_psychic_weapons",
        duration="constant_conditional",
        effect="bearer_ranged_psychic_attacks_bonus",
        effect_params={
            "attacks_bonus": 3,
            "requires_wholly_within_flow_of_magic": True,
        },
    ),
    "000009741005": EnhancementToolDescriptor(
        enhancement_id="000009741005",
        name="Noctilith Mantle",
        timing="passive",
        target="bearer_unit",
        duration="constant_while_on_battlefield",
        effect="treat_bearer_unit_as_wholly_within_flow_and_prevent_ritual_selection",
        effect_params={
            "treat_unit_as_wholly_within_flow_of_magic": True,
            "prevent_ritual_selection": True,
        },
    ),
}

_THOUSAND_SONS_HEXWARP_THRALLBAND_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _THOUSAND_SONS_HEXWARP_THRALLBAND_DESCRIPTORS.values()
}

_THOUSAND_SONS_WARPFORGED_CABAL_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010209002": EnhancementToolDescriptor(
        enhancement_id="000010209002",
        name="Warp Syphon",
        timing="while_channeling_the_warp",
        target="bearer_and_selected_friendly_vehicle_unit_within_range",
        duration="instant_conditional",
        effect="optional_vehicle_self_mortal_for_channel_die_reroll",
        range_in=6.0,
        effect_params={
            "range": 6.0,
            "self_mortal_wounds": 1,
            "reroll_channel_die": True,
            "required_target_keywords": ("THOUSAND SONS", "VEHICLE"),
        },
    ),
    "000010209003": EnhancementToolDescriptor(
        enhancement_id="000010209003",
        name="The Perplexing Cloak",
        timing="passive_while_near_friendly_vehicle",
        target="bearer",
        duration="constant_conditional",
        effect="conditional_lone_operative_while_nearby_vehicle",
        range_in=3.0,
        effect_params={
            "range": 3.0,
            "grants_lone_operative": True,
            "required_target_keywords": ("THOUSAND SONS", "VEHICLE"),
        },
    ),
    "000010209004": EnhancementToolDescriptor(
        enhancement_id="000010209004",
        name="Biomechanical Mutation",
        timing="command_phase_start",
        target="friendly_thousand_sons_vehicle_model_within_range",
        duration="instant",
        effect="repair_vehicle_model",
        range_in=6.0,
        effect_params={
            "range": 6.0,
            "heal_roll": "D3",
            "selection_kind": "model",
            "target_requires_vehicle": True,
            "target_keyword": "THOUSAND SONS",
        },
    ),
    "000010209005": EnhancementToolDescriptor(
        enhancement_id="000010209005",
        name="Warp-cursed Runemaster",
        timing="while_manifesting_ritual_near_friendly_vehicle",
        target="bearer",
        duration="instant_conditional",
        effect="ritual_range_bonus_while_nearby_vehicle",
        range_in=6.0,
        effect_params={
            "range": 6.0,
            "ritual_range_bonus": 6,
            "required_target_keywords": ("THOUSAND SONS", "VEHICLE"),
        },
    ),
}

_THOUSAND_SONS_WARPFORGED_CABAL_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _THOUSAND_SONS_WARPFORGED_CABAL_DESCRIPTORS.values()
}

_THOUSAND_SONS_WARPMELD_PACT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010201002": EnhancementToolDescriptor(
        enhancement_id="000010201002",
        name="Warpmeld Dagger",
        timing="while_attempting_ritual",
        target="bearer",
        duration="instant_optional",
        effect="optional_self_mortal_for_ritual_bonus",
        effect_params={"self_mortal_roll": "D3"},
    ),
    "000010201003": EnhancementToolDescriptor(
        enhancement_id="000010201003",
        name="Diamond of Distortion",
        timing="passive_while_leading_unit",
        target="bearer_led_unit",
        duration="constant_while_leading",
        effect="leading_unit_target_hit_penalty",
        effect_params={
            "target_hit_roll_penalty": 1,
            "requires_bearer_leading": True,
        },
    ),
    "000010201004": EnhancementToolDescriptor(
        enhancement_id="000010201004",
        name="Bray Lord",
        timing="declare_battle_formations",
        target="bearer",
        duration="battle_setup_and_constant",
        effect="scouts_and_attachment_override",
        effect_params={
            "scouts_distance": 6,
            "attachment_override_unit_names_any": ("Tzaangors",),
        },
    ),
    "000010201005": EnhancementToolDescriptor(
        enhancement_id="000010201005",
        name="Flowing Flesh",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_fnp_and_set_wounds",
        effect_params={
            "fnp": 4,
            "wounds_characteristic": 5,
        },
    ),
}

_THOUSAND_SONS_WARPMELD_PACT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _THOUSAND_SONS_WARPMELD_PACT_DESCRIPTORS.values()
}

_NECRONS_ANNIHILATION_LEGION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008543002": EnhancementToolDescriptor(
        enhancement_id="000008543002",
        name="Eternal Madness",
        timing="on_model_destroyed_in_fight_phase",
        target="bearer_unit_models_that_have_not_fought",
        duration="instant",
        effect="melee_fight_on_death_after_attacks",
        effect_params={
            "roll": "D6",
            "success_on": 4,
            "requires_bearer_alive": True,
            "fight_phase_any_destroyed": True,
        },
    ),
    "000008543003": EnhancementToolDescriptor(
        enhancement_id="000008543003",
        name="Ingrained Superiority",
        timing="on_critical_wound",
        target="bearer_unit_attacks",
        duration="constant_while_bearer_alive",
        effect="bearer_unit_critical_wound_ap_bonus",
        effect_params={"critical_wound_ap_bonus": 1, "requires_bearer_alive": True},
    ),
    "000008543005": EnhancementToolDescriptor(
        enhancement_id="000008543005",
        name="Eldritch Nightmare",
        timing="start_of_fight_phase",
        target="enemy_units_within_engagement_range_of_bearer",
        duration="instant",
        effect="start_of_fight_phase_bearer_engagement_range_enemy_battleshock",
        effect_params={"requires_bearer_alive": True},
    ),
}

_NECRONS_ANNIHILATION_LEGION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NECRONS_ANNIHILATION_LEGION_DESCRIPTORS.values()
}

_NECRONS_AWAKENED_DYNASTY_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008372002": EnhancementToolDescriptor(
        enhancement_id="000008372002",
        name="Veil of Darkness",
        timing="end_of_opponent_turn_once_per_battle",
        target="bearer_unit_not_within_engagement_range",
        duration="instant_and_next_movement_phase_return",
        effect="once_per_battle_end_of_opponent_turn_enter_strategic_reserves_then_next_movement_phase_deep_strike_return",
        once_per_battle=True,
        effect_params={
            "once_per_battle_key": "veil_of_darkness",
            "trigger_phase": "OPPONENT_TURN_END",
            "destination": "strategic_reserves",
            "requires_not_engagement_range": True,
            "requires_bearer_alive": True,
            "return_as_deep_strike": True,
            "must_arrive_next_movement_phase": True,
            "return_setup_min_enemy_distance_horiz": 9.0,
        },
    ),
    "000008372003": EnhancementToolDescriptor(
        enhancement_id="000008372003",
        name="Nether-realm Casket",
        timing="passive_while_leading",
        target="bearer_unit",
        duration="constant",
        effect="grant_stealth_while_leading",
        effect_params={"requires_bearer_alive": True},
    ),
    "000008372004": EnhancementToolDescriptor(
        enhancement_id="000008372004",
        name="Phasal Subjugator (Aura)",
        timing="passive_aura",
        target="friendly_necrons_non_character_units_within_range_of_bearer",
        duration="constant",
        effect="aura_friendly_non_character_unit_hit_bonus",
        effect_params={
            "range_inches": 6.0,
            "hit_roll_bonus": 1,
            "requires_bearer_alive": True,
        },
    ),
}

_NECRONS_AWAKENED_DYNASTY_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NECRONS_AWAKENED_DYNASTY_DESCRIPTORS.values()
}

_NECRONS_CANOPTEK_COURT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008546002": EnhancementToolDescriptor(
        enhancement_id="000008546002",
        name="Dimensional Sanctum",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_infiltrators_to_bearer_unit_models",
        effect_params={"requires_bearer_alive": True},
    ),
    "000008546003": EnhancementToolDescriptor(
        enhancement_id="000008546003",
        name="Hyperphasic Fulcrum",
        timing="passive_while_leading_and_wholly_within_power_matrix",
        target="bearer_unit",
        duration="constant_conditional",
        effect="power_matrix_bearer_unit_wound_reroll_ones_while_leading",
        effect_params={"reroll_wound_ones": True, "requires_bearer_alive": True},
    ),
    "000008546005": EnhancementToolDescriptor(
        enhancement_id="000008546005",
        name="Metalodermal Tesla Weave",
        timing="on_enemy_charge_declared",
        target="enemy_unit_that_selected_bearer_unit_as_charge_target",
        duration="instant_once_per_phase",
        effect="charge_target_mortal_wounds_once_per_phase",
        effect_params={
            "requires_bearer_alive": True,
            "trigger_roll": "D6",
            "mid_range": (2, 5),
            "mid_mortal_wounds": "D3",
            "high_threshold": 6,
            "high_mortal_wounds": 3,
        },
    ),
}

_NECRONS_CANOPTEK_COURT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NECRONS_CANOPTEK_COURT_DESCRIPTORS.values()
}

_NECRONS_HYPERCRYPT_LEGION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008554002": EnhancementToolDescriptor(
        enhancement_id="000008554002",
        name="Dimensional Overseer",
        timing="passive",
        target="army",
        duration="constant_while_bearer_on_battlefield_or_in_strategic_reserves",
        effect="hyperphasing_selection_cap_bonus",
        effect_params={
            "selection_cap_bonus": 1,
            "active_reserve_statuses": ["deployed", "strategic_reserves"],
            "requires_bearer_alive": True,
        },
    ),
    "000008554003": EnhancementToolDescriptor(
        enhancement_id="000008554003",
        name="Arisen Tyrant",
        timing="passive",
        target="bearer_unit",
        duration="constant_conditional",
        effect="bearer_unit_hit_reroll_ones_or_full_if_set_up_this_turn",
        effect_params={
            "reroll_hit_ones": True,
            "reroll_hit_full_if_set_up_this_turn": True,
            "requires_bearer_alive": True,
        },
    ),
    "000008554004": EnhancementToolDescriptor(
        enhancement_id="000008554004",
        name="Hyperspatial Transfer Node",
        timing="on_unit_advance",
        target="bearer_unit",
        duration="phase",
        effect="bearer_unit_advance_no_roll_move_bonus",
        effect_params={
            "advance_distance": 6,
            "requires_bearer_alive": True,
        },
    ),
    "000008554005": EnhancementToolDescriptor(
        enhancement_id="000008554005",
        name="Osteoclave Fulcrum",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_deep_strike_to_bearer_unit_models",
        effect_params={"requires_bearer_alive": True},
    ),
}

_NECRONS_HYPERCRYPT_LEGION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NECRONS_HYPERCRYPT_LEGION_DESCRIPTORS.values()
}

_NECRONS_OBEISANCE_PHALANX_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008550002": EnhancementToolDescriptor(
        enhancement_id="000008550002",
        name="Honourable Combatant",
        timing="on_enemy_character_unit_destroyed_by_bearer_unit",
        target="enemy_command_points",
        duration="instant_repeatable",
        effect="opponent_loses_cp_on_enemy_character_unit_destroyed_by_bearer_unit",
        effect_params={
            "cp_loss": 1,
            "target_keywords_any": ["CHARACTER"],
            "requires_bearer_alive": True,
        },
    ),
    "000008550003": EnhancementToolDescriptor(
        enhancement_id="000008550003",
        name="Unflinching Will",
        timing="passive",
        target="bearer_melee_weapons",
        duration="constant",
        effect="bearer_melee_weapons_precision_and_anti_infantry",
        effect_params={
            "granted_keywords": ["PRECISION", "ANTI-INFANTRY 5+"],
            "anti_keyword": "INFANTRY",
            "anti_value": 5,
            "requires_bearer_alive": True,
        },
    ),
    "000008550004": EnhancementToolDescriptor(
        enhancement_id="000008550004",
        name="Warrior Noble",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_target_melee_hit_penalty",
        effect_params={
            "attack_type": "melee",
            "hit_roll_penalty": 1,
            "requires_bearer_alive": True,
        },
    ),
    "000008550005": EnhancementToolDescriptor(
        enhancement_id="000008550005",
        name="Eternal Conqueror",
        timing="passive_conditional",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_hit_reroll_if_target_within_objective_range",
        effect_params={
            "requires_target_within_objective_range": True,
            "reroll_hit_full": True,
            "requires_bearer_alive": True,
        },
    ),
}

_NECRONS_OBEISANCE_PHALANX_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NECRONS_OBEISANCE_PHALANX_DESCRIPTORS.values()
}

_NECRONS_PANTHEON_OF_WOE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010672002": EnhancementToolDescriptor(
        enhancement_id="000010672002",
        name="Singularity Matrix",
        timing="opponent_stratagem_targeting",
        target="enemy_unit_within_range_of_bearer",
        duration="constant",
        effect="targeted_stratagem_cp_increase",
        range_in=12.0,
        effect_params={
            "cp_increase": 1,
            "ability_name": "Lord of Deceit (Aura)",
            "requires_bearer_alive": True,
        },
    ),
    "000010672003": EnhancementToolDescriptor(
        enhancement_id="000010672003",
        name="Quantum Goad",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="charge_after_advance",
        effect_params={
            "charge_after_advance": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010672004": EnhancementToolDescriptor(
        enhancement_id="000010672004",
        name="Animus Damper",
        timing="start_of_opponent_shooting_phase",
        target="visible_enemy_vehicle_unit",
        duration="until_end_of_phase",
        effect="opponent_shooting_phase_select_visible_vehicle_leadership_test_hit_penalty_and_failed_test_wound_penalty",
        range_in=9999.0,
        effect_params={
            "range": 9999,
            "required_target_keywords": ["VEHICLE"],
            "resolution_mode": "leadership_test",
            "apply_wound_penalty_on_failed_leadership_test": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010672005": EnhancementToolDescriptor(
        enhancement_id="000010672005",
        name="Reletavistic Tether",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="deep_strike_and_translocation_six_inch_setup_with_conditional_no_charge",
        effect_params={
            "deep_strike_min_distance": 6,
            "advance_redeploy_min_distance": 6,
            "no_charge_if_within_distance": 9,
            "requires_bearer_alive": True,
        },
    ),
}

_NECRONS_PANTHEON_OF_WOE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NECRONS_PANTHEON_OF_WOE_DESCRIPTORS.values()
}

_NECRONS_CURSED_LEGION_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010668002": EnhancementToolDescriptor(
        enhancement_id="000010668002",
        name="Destroyer Ankh",
        timing="passive",
        target="bearer_and_bearer_unit",
        duration="constant",
        effect="bearer_keyword_and_bearer_unit_move_bonus_with_bearer_melee_attacks_bonus",
        effect_params={
            "granted_keyword": "DESTROYER CULT",
            "movement_bonus": 2,
            "bearer_melee_attacks_bonus": 2,
            "requires_bearer_alive": True,
        },
    ),
    "000010668003": EnhancementToolDescriptor(
        enhancement_id="000010668003",
        name="Murdermind",
        timing="passive_and_declare_battle_formations",
        target="bearer_and_destroyer_cult_bodyguard_unit",
        duration="constant",
        effect="bearer_keyword_move_bonus_and_attach_to_destroyer_cult_unit",
        effect_params={
            "granted_keyword": "DESTROYER CULT",
            "bearer_move_bonus": 3,
            "attachment_override_required_keyword": "DESTROYER CULT",
            "attachment_override_exclude_keywords_any": ["CHARACTER"],
            "requires_bearer_alive": True,
        },
    ),
    "000010668004": EnhancementToolDescriptor(
        enhancement_id="000010668004",
        name="Mark of the Nekrosor",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_hit_roll_bonus",
        effect_params={
            "hit_roll_bonus": 1,
            "requires_bearer_alive": True,
        },
    ),
    "000010668005": EnhancementToolDescriptor(
        enhancement_id="000010668005",
        name="Cursed Circlet",
        timing="after_enemy_unit_finishes_shooting",
        target="bearer_unit",
        duration="instant_repeatable",
        effect="post_enemy_shooting_destroyed_models_surge_move",
        effect_params={
            "range_roll": "D6",
            "allow_engagement_range": True,
            "closest_enemy_exclude_keywords_any": ["AIRCRAFT"],
            "requires_not_battle_shocked": True,
            "requires_bearer_alive": True,
        },
    ),
}

_NECRONS_CURSED_LEGION_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NECRONS_CURSED_LEGION_DESCRIPTORS.values()
}

_NECRONS_CRYPTEK_CONCLAVE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010664002": EnhancementToolDescriptor(
        enhancement_id="000010664002",
        name="Quantum Abacus",
        timing="when_bearer_unit_targeted_by_stratagem",
        target="bearer_unit",
        duration="instant_repeatable",
        effect="targeted_stratagem_cp_refund_with_objective_bonus",
        effect_params={
            "roll_min": 4,
            "cp_gain": 1,
            "roll_bonus": 1,
            "roll_bonus_if_target_within_objective_range": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010664003": EnhancementToolDescriptor(
        enhancement_id="000010664003",
        name="Atomic Disintegrators",
        timing="selected_to_shoot",
        target="bearer_unit",
        duration="while_selecting_technosorcerous_augmentation",
        effect="extend_technosorcerous_augmentation_choices",
        effect_params={
            "extra_choice_keys": ["ANTI_MONSTER_5", "ANTI_VEHICLE_5"],
            "requires_bearer_alive": True,
        },
    ),
    "000010664004": EnhancementToolDescriptor(
        enhancement_id="000010664004",
        name="Gauntlet of Compression",
        timing="passive",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="bearer_unit_ranged_range_bonus",
        effect_params={
            "range_bonus": 6,
            "requires_bearer_alive": True,
        },
    ),
    "000010664005": EnhancementToolDescriptor(
        enhancement_id="000010664005",
        name="Gravitic Bolas",
        timing="after_bearer_has_shot",
        target="enemy_unit_hit_by_bearer_ranged_attacks",
        duration="until_start_of_next_turn",
        effect="post_shoot_select_hit_enemy_unit_to_pin",
        effect_params={
            "move_penalty": -2,
            "charge_penalty": -2,
            "expires_phase": "COMMAND_PHASE",
            "exclude_keywords_any": ["TITANIC"],
            "requires_bearer_alive": True,
        },
    ),
}

_NECRONS_CRYPTEK_CONCLAVE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NECRONS_CRYPTEK_CONCLAVE_DESCRIPTORS.values()
}

_NECRONS_STARSHATTER_ARSENAL_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009749002": EnhancementToolDescriptor(
        enhancement_id="000009749002",
        name="Dread Majesty (Aura)",
        timing="passive_aura",
        target="friendly_necrons_units_within_6",
        duration="constant",
        effect="reroll_hit_and_wound_ones_aura",
        effect_params={
            "range_in": 6.0,
            "reroll_hit_ones": True,
            "reroll_wound_ones": True,
            "excluded_keywords": ("MONSTER", "TITANIC"),
            "requires_bearer_alive": True,
            "requires_bearer_on_battlefield": True,
        },
    ),
    "000009749003": EnhancementToolDescriptor(
        enhancement_id="000009749003",
        name="Miniaturised Nebuloscope",
        timing="passive",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={
            "keywords": ("IGNORES COVER",),
            "attack_type": "ranged",
            "requires_bearer_alive": True,
        },
    ),
    "000009749004": EnhancementToolDescriptor(
        enhancement_id="000009749004",
        name="Demanding Leader",
        timing="command_phase",
        target="friendly_necrons_vehicle_or_mounted_within_6",
        duration="until_start_of_next_owner_command_phase",
        effect="grant_fall_back_and_shoot",
        effect_params={
            "range_in": 6.0,
            "requires_vehicle_or_mounted": True,
            "excluded_keywords": ("TITANIC",),
            "requires_bearer_alive": True,
            "requires_bearer_on_battlefield": True,
            "optional": True,
        },
    ),
    "000009749005": EnhancementToolDescriptor(
        enhancement_id="000009749005",
        name="Chrono-impedance Fields",
        timing="command_phase",
        target="friendly_necrons_vehicle_or_mounted_within_6",
        duration="until_start_of_next_owner_command_phase",
        effect="reduce_allocated_damage",
        effect_params={
            "range_in": 6.0,
            "damage_modifier": -1,
            "requires_vehicle_or_mounted": True,
            "excluded_keywords": ("TITANIC",),
            "requires_bearer_alive": True,
            "requires_bearer_on_battlefield": True,
            "optional": True,
        },
    ),
}

_NECRONS_STARSHATTER_ARSENAL_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _NECRONS_STARSHATTER_ARSENAL_DESCRIPTORS.values()
}

_TYRANIDS_SUBTERRANEAN_ASSAULT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010147002": EnhancementToolDescriptor(
        enhancement_id="000010147002",
        name="Synaptic Strategy",
        timing="while_targeting_rapid_ingress",
        target="bearer_unit",
        duration="once_per_battle",
        effect="rapid_ingress_zero_cp_with_repeat_bypass",
        once_per_battle=True,
        effect_params={
            "stratagem_names": ("RAPID INGRESS",),
            "usage_key": "synaptic_strategy_rapid_ingress",
            "repeat_bypass": True,
        },
    ),
    "000010147003": EnhancementToolDescriptor(
        enhancement_id="000010147003",
        name="Tremor Senses",
        timing="after_deployment",
        target="friendly_tyranids_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "allow_strategic_reserves": True,
            "redeploy_filters": ("TYRANIDS",),
            "strategic_reserves_ignore_current_unit_count_limit": True,
        },
    ),
    "000010147004": EnhancementToolDescriptor(
        enhancement_id="000010147004",
        name="Vanguard Intellect",
        timing="movement_phase_while_in_reserves",
        target="bearer_unit_in_reserves",
        duration="constant_while_in_reserves",
        effect="strategic_reserves_setup_round_bonus_for_deep_strike",
        effect_params={
            "strategic_reserves_setup_round_bonus": 1,
            "requires_deep_strike": True,
        },
    ),
    "000010147005": EnhancementToolDescriptor(
        enhancement_id="000010147005",
        name="Trygon Prime",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_gain_synapse_and_bearer_melee_strength_and_weapon_skill_bonus",
        effect_params={
            "gain_keywords": ("SYNAPSE",),
            "strength_bonus": 1,
            "weapon_skill_bonus": 1,
            "bearer_only": True,
        },
    ),
}

_TYRANIDS_SUBTERRANEAN_ASSAULT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _TYRANIDS_SUBTERRANEAN_ASSAULT_DESCRIPTORS.values()
}

_TYRANIDS_SYNAPTIC_NEXUS_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008421002": EnhancementToolDescriptor(
        enhancement_id="000008421002",
        name="Power of the Hive Mind",
        timing="passive",
        target="bearer_psychic_weapons",
        duration="constant",
        effect="bearer_psychic_strength_and_ap_bonus",
        effect_params={
            "psychic_strength_bonus": 1,
            "psychic_ap_bonus": 1,
            "bearer_only": True,
        },
    ),
    "000008421003": EnhancementToolDescriptor(
        enhancement_id="000008421003",
        name="Psychostatic Disruption",
        timing="passive_and_on_enemy_strategic_reserves_declare_optional",
        target="enemy_units_arriving_from_reserves_within_range_and_enemy_strategic_reserves_arrival",
        duration="constant_and_once_per_battle_instant",
        effect="reserves_denial_aura_and_once_per_battle_strategic_reserves_arrival_cancel",
        range_in=12.0,
        once_per_battle=True,
        effect_params={
            "min_enemy_distance": 12.0,
            "trigger_rounds": (1, 2),
            "roll": "D6",
            "success_on": 4,
            "once_per_battle_key": "psychostatic_disruption",
            "bearer_only": True,
            "optional": True,
        },
    ),
    "000008421004": EnhancementToolDescriptor(
        enhancement_id="000008421004",
        name="Synaptic Control",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_incoming_damage_modifier",
        effect_params={
            "damage_modifier": -1,
            "minimum_damage": 1,
            "bearer_only": True,
        },
    ),
    "000008421005": EnhancementToolDescriptor(
        enhancement_id="000008421005",
        name="The Dirgeheart of Kharis (Aura)",
        timing="passive_aura",
        target="enemy_units_within_range_of_bearer",
        duration="constant",
        effect="enemy_leadership_characteristic_penalty_aura",
        range_in=9.0,
        effect_params={"range": 9.0, "leadership_penalty": 1, "bearer_only": True},
    ),
}

_TYRANIDS_SYNAPTIC_NEXUS_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _TYRANIDS_SYNAPTIC_NEXUS_DESCRIPTORS.values()
}

_TYRANIDS_WARRIOR_BIOFORM_ONSLAUGHT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009737002": EnhancementToolDescriptor(
        enhancement_id="000009737002",
        name="Synaptic Tyrant",
        timing="passive_and_declare_battle_formations_attachment_override",
        target="bearer",
        duration="battle_setup",
        effect="attachment_override",
        effect_params={
            "attachment_override_unit_names_any": (
                "Tyranid Warriors with Ranged Bio-weapons",
                "Tyranid Warriors with Melee Bio-weapons",
            ),
        },
    ),
    "000009737003": EnhancementToolDescriptor(
        enhancement_id="000009737003",
        name="Ocular Adaptation",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="hit_roll_bonus",
        effect_params={"hit_bonus": 1},
    ),
    "000009737004": EnhancementToolDescriptor(
        enhancement_id="000009737004",
        name="Sensory Assimilation",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="target_hit_roll_penalty",
        effect_params={"target_hit_roll_penalty": 1},
    ),
    "000009737005": EnhancementToolDescriptor(
        enhancement_id="000009737005",
        name="Elevated Might",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="charge_after_advance",
        effect_params={"charge_after_advance": True},
    ),
}

_TYRANIDS_WARRIOR_BIOFORM_ONSLAUGHT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _TYRANIDS_WARRIOR_BIOFORM_ONSLAUGHT_DESCRIPTORS.values()
}

_TYRANIDS_UNENDING_SWARM_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008408002": EnhancementToolDescriptor(
        enhancement_id="000008408002",
        name="Relentless Hunger",
        timing="passive",
        target="bearer_unit",
        duration="constant_while_bearer_alive",
        effect="bearer_unit_movement_bonus",
        effect_params={"movement_bonus": 2, "requires_bearer_alive": True},
    ),
    "000008408003": EnhancementToolDescriptor(
        enhancement_id="000008408003",
        name="Naturalised Camouflage",
        timing="start_of_first_battle_round",
        target="up_to_three_friendly_endless_multitude_units_within_range_of_bearer",
        duration="until_end_of_battle_round",
        effect="select_friendly_endless_multitude_units_for_ranged_benefit_of_cover",
        range_in=9.0,
        effect_params={
            "range": 9.0,
            "max_units": 3,
            "target_keyword": "ENDLESS MULTITUDE",
            "attack_type": "ranged",
            "grants_benefit_of_cover": True,
            "selection_battle_round": 1,
            "requires_bearer_alive": True,
            "optional": True,
        },
    ),
    "000008408004": EnhancementToolDescriptor(
        enhancement_id="000008408004",
        name="Piercing Talons",
        timing="on_critical_wound",
        target="bearer_unit_attacks",
        duration="constant_while_bearer_alive",
        effect="bearer_unit_critical_wound_ap_bonus",
        effect_params={"critical_wound_ap_bonus": 1, "requires_bearer_alive": True},
    ),
    "000008408005": EnhancementToolDescriptor(
        enhancement_id="000008408005",
        name="Adrenalised Onslaught",
        timing="fight_phase_move",
        target="bearer_unit",
        duration="constant_while_bearer_alive",
        effect="bearer_unit_pile_in_and_consolidate_distance_bonus",
        effect_params={
            "pile_in_distance_bonus": 3,
            "consolidate_distance_bonus": 3,
            "requires_bearer_alive": True,
        },
    ),
}

_TYRANIDS_UNENDING_SWARM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _TYRANIDS_UNENDING_SWARM_DESCRIPTORS.values()
}

_TYRANIDS_VANGUARD_ONSLAUGHT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008417003": EnhancementToolDescriptor(
        enhancement_id="000008417003",
        name="Chameleonic",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_stealth_and_ranged_benefit_of_cover_to_bearer_unit",
        effect_params={
            "grants_stealth": True,
            "grants_benefit_of_cover_vs_ranged": True,
            "requires_bearer_alive": True,
        },
    ),
    "000008417004": EnhancementToolDescriptor(
        enhancement_id="000008417004",
        name="Stalker",
        timing="start_of_battle",
        target="enemy_unit",
        duration="battle",
        effect="select_enemy_unit_for_bearer_hit_and_wound_bonus",
        effect_params={
            "hit_bonus": 1,
            "wound_bonus": 1,
            "applies_to_bearer_only": True,
        },
    ),
    "000008417005": EnhancementToolDescriptor(
        enhancement_id="000008417005",
        name="Neuronode",
        timing="after_deployment",
        target="friendly_vanguard_invader_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "allow_strategic_reserves": True,
            "redeploy_filters": ("VANGUARD INVADER",),
        },
    ),
}

_TYRANIDS_VANGUARD_ONSLAUGHT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _TYRANIDS_VANGUARD_ONSLAUGHT_DESCRIPTORS.values()
}

_TYRANIDS_CRUSHER_STAMPEDE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008404002": EnhancementToolDescriptor(
        enhancement_id="000008404002",
        name="Ominous Presence",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="objective_control_bonus",
        effect_params={"objective_control_bonus": 3, "bearer_only": True},
    ),
    "000008404003": EnhancementToolDescriptor(
        enhancement_id="000008404003",
        name="Enraged Reserves",
        timing="on_bearer_destroyed_by_melee",
        target="bearer",
        duration="instant",
        effect="melee_fight_on_death_after_attacks",
        effect_params={"roll": "D6", "success_on": 3, "bearer_only": True},
    ),
    "000008404004": EnhancementToolDescriptor(
        enhancement_id="000008404004",
        name="Null Nodules",
        timing="when_psychic_attack_allocated",
        target="bearer",
        duration="until_end_of_phase",
        effect="conditional_feel_no_pain",
        effect_params={
            "feel_no_pain": 5,
            "condition": "against psychic attacks",
            "once_per_battle_key": "null_nodules",
            "bearer_only": True,
            "optional": True,
        },
    ),
    "000008404005": EnhancementToolDescriptor(
        enhancement_id="000008404005",
        name="Monstrous Nemesis",
        timing="passive",
        target="bearer_melee_attacks_vs_monster_or_vehicle",
        duration="constant",
        effect="melee_wound_bonus",
        effect_params={"wound_bonus": 1, "target_keywords": ("MONSTER", "VEHICLE"), "bearer_only": True},
    ),
}

_TYRANIDS_CRUSHER_STAMPEDE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _TYRANIDS_CRUSHER_STAMPEDE_DESCRIPTORS.values()
}

_TYRANIDS_ASSIMILATION_SWARM_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008412003": EnhancementToolDescriptor(
        enhancement_id="000008412003",
        name="Instinctive Defence",
        timing="passive_conditional_aura",
        target="bearer_unit",
        duration="constant_conditional",
        effect="heroic_intervention_zero_cp_and_fights_first_while_bearer_within_friendly_harvester",
        effect_params={
            "stratagem_names": ("HEROIC INTERVENTION",),
            "harvester_range": 6.0,
            "required_friendly_keyword": "HARVESTER",
            "required_target_scope": "bearer_unit_only",
            "grants_fights_first": True,
            "requires_bearer_on_battlefield": True,
        },
    ),
    "000008412005": EnhancementToolDescriptor(
        enhancement_id="000008412005",
        name="Parasitic Biomorphology",
        timing="passive_with_first_fight_phase_kill_upgrade",
        target="bearer_unit_melee_weapons",
        duration="constant_with_persistent_upgrade",
        effect="unit_melee_strength_bonus_with_first_fight_phase_kill_unit_melee_attacks_bonus_near_harvester",
        effect_params={
            "melee_strength_bonus": 1,
            "melee_attacks_bonus": 1,
            "harvester_range": 6.0,
        },
    ),
}

_TYRANIDS_ASSIMILATION_SWARM_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _TYRANIDS_ASSIMILATION_SWARM_DESCRIPTORS.values()
}

_ORKS_BULLY_BOYZ_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008885002": EnhancementToolDescriptor(
        enhancement_id="000008885002",
        name="Big Gob",
        timing="fight_phase_start",
        target="enemy_unit_within_engagement_range_of_bearer",
        duration="immediate",
        effect="fight_phase_select_engagement_battleshock",
        effect_params={
            "battle_shock_test_modifier": -1,
            "requires_bearer_alive": True,
            "ability_key": "big_gob",
        },
    ),
    "000008885004": EnhancementToolDescriptor(
        enhancement_id="000008885004",
        name="’Eadstompa",
        timing="when_bearer_attacks_below_strength_target",
        target="bearer",
        duration="constant",
        effect="bearer_wound_reroll_vs_damaged_or_below_half_target",
        effect_params={
            "requires_bearer_alive": True,
            "reroll_values_vs_below_starting_strength": (1,),
            "reroll_full_vs_below_half_strength": True,
        },
    ),
    "000008885005": EnhancementToolDescriptor(
        enhancement_id="000008885005",
        name="Tellyporta",
        timing="declare_battle_formations",
        target="bearer_unit",
        duration="battle_setup",
        effect="grant_deep_strike",
        effect_params={"grant_to_bearer_unit": True},
    ),
}

_ORKS_BULLY_BOYZ_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ORKS_BULLY_BOYZ_DESCRIPTORS.values()
}

_ORKS_DA_BIG_HUNT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008868002": EnhancementToolDescriptor(
        enhancement_id="000008868002",
        name="Glory Hog",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_scouts",
        effect_params={"scouts_distance": 9.0},
    ),
    "000008868003": EnhancementToolDescriptor(
        enhancement_id="000008868003",
        name="Proper Killy",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="bearer_melee_damage_bonus",
        effect_params={"melee_damage_bonus": 1},
    ),
    "000008868004": EnhancementToolDescriptor(
        enhancement_id="000008868004",
        name="Skrag Every Stash!",
        timing="end_of_command_phase",
        target="controlled_objective_markers_within_bearer",
        duration="until_opponent_controls_at_start_or_end_of_turn",
        effect="sticky_objective_control",
        effect_params={
            "allow_embarked_transport": False,
            "source_scope": "bearer",
            "sticky_source": "unit_sticky_objective",
        },
    ),
    "000008868005": EnhancementToolDescriptor(
        enhancement_id="000008868005",
        name="Surly as a Squiggoth",
        timing="passive_while_leading",
        target="bearer_led_unit",
        duration="while_bearer_leading",
        effect="defensive_wound_roll_penalty",
        effect_params={
            "wound_roll_penalty": 1,
            "attack_type": "any",
            "requires_strength_gt_toughness": True,
            "requires_bearer_leading": True,
        },
    ),
}

_ORKS_DA_BIG_HUNT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ORKS_DA_BIG_HUNT_DESCRIPTORS.values()
}

_ORKS_DREAD_MOB_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008877002": EnhancementToolDescriptor(
        enhancement_id="000008877002",
        name="Gitfinder Googlez",
        timing="passive",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={"keywords": ("IGNORES COVER",), "attack_type": "ranged"},
    ),
    "000008877003": EnhancementToolDescriptor(
        enhancement_id="000008877003",
        name="Press It Fasta!",
        timing="when_selected_to_shoot_before_dread_mob_button_roll",
        target="bearer_unit",
        duration="until_end_of_phase",
        effect="selected_to_shoot_detachment_roll_augmentation",
        effect_params={
            "detachment_ability": "try_dat_button",
            "trigger": "shooting",
            "extra_rolls": 1,
            "requires_bearer_alive": True,
        },
    ),
    "000008877004": EnhancementToolDescriptor(
        enhancement_id="000008877004",
        name="Smoky Gubbinz",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="grant_stealth",
    ),
    "000008877005": EnhancementToolDescriptor(
        enhancement_id="000008877005",
        name="Supa-glowy Fing",
        timing="start_of_command_phase",
        target="visible_enemy_unit_within_range_of_bearer",
        duration="instant_or_until_start_of_next_owner_command_phase",
        effect="command_phase_visible_enemy_roll_table_battleshock_mortals_or_hit_penalty",
        range_in=18.0,
        effect_params={
            "requires_bearer_alive": True,
            "requires_visibility": True,
            "roll": "D6",
            "battle_shock_on": ("1-2",),
            "mortal_wounds_on": ("3-4",),
            "mortal_wounds_roll": "D3",
            "hit_penalty_on": ("5-6",),
            "hit_penalty": 1,
            "ability_key": "supa_glowy_fing",
        },
    ),
}

_ORKS_DREAD_MOB_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ORKS_DREAD_MOB_DESCRIPTORS.values()
}

_ORKS_FREEBOOTER_KREW_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010712002": EnhancementToolDescriptor(
        enhancement_id="000010712002",
        name="Da Kaptin",
        timing="start_of_any_phase_once_per_battle_round",
        target="friendly_battle_shocked_orks_unit_within_range_of_bearer",
        duration="instant",
        effect="clear_battleshock_for_friendly_unit_in_range_with_mortal_wounds_once_per_battle_round",
        range_in=12.0,
        effect_params={
            "required_target_faction_keyword": "ORKS",
            "requires_bearer_alive": True,
            "requires_target_battle_shocked": True,
            "mortal_wounds_roll": "D3",
            "once_per_battle_round": True,
            "ability_key": "da_kaptin",
        },
    ),
    "000010712003": EnhancementToolDescriptor(
        enhancement_id="000010712003",
        name="Git-spotter Squig",
        timing="passive",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={"keywords": ("IGNORES COVER",), "attack_type": "ranged"},
    ),
    "000010712005": EnhancementToolDescriptor(
        enhancement_id="000010712005",
        name="Razgit's Magik Map",
        timing="after_deployment",
        target="friendly_orks_infantry_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "allow_strategic_reserves": True,
            "redeploy_filters": ("ORKS", "INFANTRY"),
            "strategic_reserves_ignore_current_unit_count_limit": True,
        },
    ),
    "000010712004": EnhancementToolDescriptor(
        enhancement_id="000010712004",
        name="Bionik Workshop",
        timing="start_of_battle",
        target="bearer_unit",
        duration="until_end_of_battle",
        effect="start_of_battle_roll_persistent_bionik_branch_for_bearer_unit",
        effect_params={
            "roll": "D3",
            "ability_key": "bionik_workshop",
            "requires_bearer_alive": True,
            "roll_branches": {
                "1": {"branch_key": "legs", "label": "Bionik Legs"},
                "2": {"branch_key": "arms", "label": "Bionik Arms"},
                "3": {"branch_key": "bonce", "label": "Bionik Bonce"},
            },
        },
    ),
}

_ORKS_FREEBOOTER_KREW_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ORKS_FREEBOOTER_KREW_DESCRIPTORS.values()
}

_ORKS_GREEN_TIDE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008881002": EnhancementToolDescriptor(
        enhancement_id="000008881002",
        name="Bloodthirsty Belligerence",
        timing="passive_while_leading",
        target="bearer_led_unit",
        duration="constant_conditional",
        effect="reroll_advance_and_conditional_charge_reroll",
        effect_params={
            "reroll_advance": True,
            "reroll_charge_if_effective_model_count_at_least": 10,
            "effective_model_count_scope": "enhancement",
            "requires_bearer_leading": True,
        },
    ),
    "000008881003": EnhancementToolDescriptor(
        enhancement_id="000008881003",
        name="Brutal But Kunnin'",
        timing="command_phase",
        target="bearer",
        duration="instant",
        effect="command_phase_cp_roll_with_effective_model_count_bonus",
        effect_params={
            "roll": "D6",
            "success_on": 5,
            "cp_gain": 1,
            "requires_bearer_on_battlefield_or_embarked_transport": True,
            "roll_bonus_if_effective_model_count_at_least": 2,
            "effective_model_count_threshold": 10,
            "effective_model_count_scope": "enhancement",
        },
    ),
    "000008881004": EnhancementToolDescriptor(
        enhancement_id="000008881004",
        name="Ferocious Show Off",
        timing="while_bearer_fights",
        target="bearer_melee_weapons",
        duration="constant_conditional",
        effect="conditional_bearer_melee_strength_bonus",
        effect_params={
            "base_melee_strength_bonus": 1,
            "enhanced_melee_strength_bonus": 3,
            "enhanced_if_effective_model_count_at_least": 10,
            "effective_model_count_scope": "enhancement",
        },
    ),
    "000008881005": EnhancementToolDescriptor(
        enhancement_id="000008881005",
        name="Raucous Warcaller",
        timing="passive_while_leading",
        target="bearer_led_unit",
        duration="constant",
        effect="effective_model_count_floor_while_leading",
        effect_params={
            "effective_model_floor": 10,
            "effective_model_count_scopes": ("detachment", "stratagem"),
            "requires_bearer_leading": True,
        },
    ),
}

_ORKS_GREEN_TIDE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ORKS_GREEN_TIDE_DESCRIPTORS.values()
}

_ORKS_KULT_OF_SPEED_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000008872002": EnhancementToolDescriptor(
        enhancement_id="000008872002",
        name="Fasta Than Yooz",
        timing="on_disembark_after_transport_normal_move",
        target="bearer_unit",
        duration="that_turn",
        effect="allow_charge_after_disembark_from_transport_normal_move",
        effect_params={
            "allow_charge_after_normal_move": True,
            "requires_disembarked_from_moved_transport": True,
            "requires_bearer_alive": True,
        },
    ),
    "000008872003": EnhancementToolDescriptor(
        enhancement_id="000008872003",
        name="Speed Makes Right",
        timing="command_phase",
        target="bearer_or_transport_bearer_is_embarked_within",
        duration="instant",
        effect="command_phase_cp_roll_if_bearer_or_transport_within_enemy_range",
        effect_params={
            "roll": "D6",
            "success_on": 3,
            "cp_gain": 1,
            "enemy_range_max": 9.0,
            "enemy_range_reference": "bearer_or_transport",
            "requires_bearer_on_battlefield_or_embarked_transport": True,
        },
    ),
    "000008872004": EnhancementToolDescriptor(
        enhancement_id="000008872004",
        name="Squig-hide Tyres",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="bearer_unit_consolidate_distance_override",
        effect_params={
            "consolidate_distance_override": 6,
            "requires_bearer_alive": True,
        },
    ),
    "000008872005": EnhancementToolDescriptor(
        enhancement_id="000008872005",
        name="Wazblasta",
        timing="your_shooting_phase_after_bearer_unit_shoots",
        target="bearer_unit",
        duration="instant_optional_with_no_charge_until_end_of_turn",
        effect="post_shoot_reactive_normal_move_no_charge",
        effect_params={
            "move_range": 6,
            "requires_not_engagement_range": True,
            "requires_bearer_alive": True,
        },
    ),
}

_ORKS_KULT_OF_SPEED_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ORKS_KULT_OF_SPEED_DESCRIPTORS.values()
}

_ORKS_MORE_DAKKA_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009991002": EnhancementToolDescriptor(
        enhancement_id="000009991002",
        name="Da Gobshot Thunderbuss",
        timing="passive",
        target="bearer_ranged_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={
            "keywords": ("DEVASTATING WOUNDS", "HAZARDOUS"),
            "attack_type": "ranged",
            "target_scope": "bearer",
        },
    ),
    "000009991003": EnhancementToolDescriptor(
        enhancement_id="000009991003",
        name="Dead Shiny Shootas",
        timing="passive",
        target="bearer_unit_ranged_weapons",
        duration="constant",
        effect="grant_weapon_keywords",
        effect_params={
            "keywords": ("RAPID FIRE 1",),
            "attack_type": "ranged",
            "target_scope": "bearer_unit",
        },
    ),
    "000009991004": EnhancementToolDescriptor(
        enhancement_id="000009991004",
        name="Targetin' Squigs",
        timing="passive",
        target="bearer_unit_ranged_attacks",
        duration="constant",
        effect="modify_attack_rolls",
        effect_params={
            "attack_type": "ranged",
            "roll": "hit",
            "modifier": 1,
            "target_scope": "bearer_unit",
        },
    ),
    "000009991005": EnhancementToolDescriptor(
        enhancement_id="000009991005",
        name="Zog Off and Eat Dakka!",
        timing="passive",
        target="bearer_unit",
        duration="constant",
        effect="shoot_after_fall_back",
        effect_params={
            "attack_type": "ranged",
            "shoot_after_fall_back": True,
            "target_scope": "bearer_unit",
        },
    ),
}

_ORKS_MORE_DAKKA_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ORKS_MORE_DAKKA_DESCRIPTORS.values()
}

_ORKS_TAKTIKAL_BRIGADE_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000009795002": EnhancementToolDescriptor(
        enhancement_id="000009795002",
        name="Skwad Leader",
        timing="declare_battle_formations",
        target="bearer",
        duration="battle_setup_and_while_leading",
        effect="attach_to_kommandos_and_gain_infiltrators_stealth_while_leading",
        effect_params={
            "attachment_override_unit_names_any": ("Kommandos",),
            "requires_bearer_leading_unit_name": "Kommandos",
            "grants_while_leading": ("INFILTRATORS", "STEALTH"),
        },
    ),
    "000009795003": EnhancementToolDescriptor(
        enhancement_id="000009795003",
        name="Mek Kaptin",
        timing="declare_battle_formations",
        target="bearer",
        duration="battle_setup_and_constant",
        effect="attach_to_flash_gitz_and_ranged_hit_reroll",
        effect_params={
            "attachment_override_unit_names_any": ("Flash Gitz",),
            "attack_type": "ranged",
            "reroll_hit_full": True,
        },
    ),
    "000009795004": EnhancementToolDescriptor(
        enhancement_id="000009795004",
        name="Mork's Kunnin'",
        timing="after_deployment",
        target="friendly_orks_units",
        duration="redeploy_step",
        effect="redeploy_units",
        effect_params={
            "max_units": 3,
            "allow_strategic_reserves": True,
            "redeploy_filters": ("ORKS",),
            "strategic_reserves_ignore_current_unit_count_limit": True,
        },
    ),
    "000009795005": EnhancementToolDescriptor(
        enhancement_id="000009795005",
        name="Gob Boomer",
        timing="passive",
        target="bearer",
        duration="constant",
        effect="increase_taktik_issue_range",
        effect_params={"taktik_issue_range": 18.0, "default_issue_range": 6.0},
    ),
}

_ORKS_TAKTIKAL_BRIGADE_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _ORKS_TAKTIKAL_BRIGADE_DESCRIPTORS.values()
}

_LEAGUES_OF_VOTANN_BRANDFAST_OATHBAND_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010447002": EnhancementToolDescriptor(
        enhancement_id="000010447002",
        name="Tactical Alchemy",
        timing="command_phase",
        target="bearer_unit",
        duration="immediate",
        effect="spend_yp_then_roll_for_command_point_gain_if_bearer_unit_controls_midfield_objective",
        effect_params={"yp_cost": 1, "roll": "D6", "success_on": 4, "cp_gain": 1},
    ),
    "000010447003": EnhancementToolDescriptor(
        enhancement_id="000010447003",
        name="Trivärg Cyber Implant",
        timing="when_selected_to_shoot",
        target="bearer_unit",
        duration="until_end_of_phase",
        effect="grant_ranged_sustained_hits_after_disembark_or_optional_yp_spend",
        effect_params={"yp_cost": 2, "sustained_hits_value": 2, "auto_if_disembarked_this_turn": True},
    ),
    "000010447004": EnhancementToolDescriptor(
        enhancement_id="000010447004",
        name="Precursive Judgement",
        timing="overwatch_targeting",
        target="bearer_unit",
        duration="constant_while_wholly_within_transport_range",
        effect="fire_overwatch_zero_cp_and_hit_threshold_while_within_transport",
        range_in=6.0,
        effect_params={
            "stratagems": ("OVERWATCH", "FIRE OVERWATCH"),
            "overwatch_hit_threshold": 5,
            "transport_range_in": 6.0,
        },
    ),
    "000010447005": EnhancementToolDescriptor(
        enhancement_id="000010447005",
        name="Signature Restoration",
        timing="on_repair_resolution",
        target="forgewrought_expertise_target",
        duration="immediate",
        effect="increase_forgewrought_expertise_repair",
        effect_params={"additional_heal": 1},
    ),
}

_LEAGUES_OF_VOTANN_BRANDFAST_OATHBAND_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _LEAGUES_OF_VOTANN_BRANDFAST_OATHBAND_DESCRIPTORS.values()
}

_LEAGUES_OF_VOTANN_DELVE_ASSAULT_SHIFT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010443002": EnhancementToolDescriptor(
        enhancement_id="000010443002",
        name="Dêlvwerke Navigator",
        timing="reinforcements_step",
        target="friendly_cthonian_beserks_unit_visible_to_bearer",
        duration="immediate",
        effect="return_destroyed_cthonian_beserks_models_after_optional_yp_spend",
        effect_params={"base_models_returned": 1, "additional_model_per_yp": 2},
    ),
    "000010443003": EnhancementToolDescriptor(
        enhancement_id="000010443003",
        name="Multiwave System Jammer",
        timing="movement_phase",
        target="friendly_cthonian_unit_in_reserves",
        duration="until_end_of_phase",
        effect="treat_current_battle_round_as_one_higher_for_reserves_setup",
        effect_params={"once_per_battle": True, "round_bonus": 1},
    ),
    "000010443004": EnhancementToolDescriptor(
        enhancement_id="000010443004",
        name="Quake Supervisor",
        timing="passive",
        target="bearer_and_friendly_artillery_within_3",
        duration="constant_while_within_artillery_range",
        effect="grant_bearer_lone_operative_and_artillery_ranged_hit_bonus_vs_targets_visible_to_bearer",
        range_in=3.0,
        effect_params={"range_in": 3.0, "hit_bonus": 1},
    ),
    "000010443005": EnhancementToolDescriptor(
        enhancement_id="000010443005",
        name="Piledriver",
        timing="fight_unit_selected",
        target="bearer",
        duration="until_end_of_phase",
        effect="optional_yp_spend_adds_to_bearer_melee_damage",
        effect_params={"max_yp_spend": 2},
    ),
}

_LEAGUES_OF_VOTANN_DELVE_ASSAULT_SHIFT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _LEAGUES_OF_VOTANN_DELVE_ASSAULT_SHIFT_DESCRIPTORS.values()
}

_LEAGUES_OF_VOTANN_HEARTHFYRE_ARSENAL_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010451002": EnhancementToolDescriptor(
        enhancement_id="000010451002",
        name="Fârstrydr Node",
        timing="passive",
        target="bearer_unit",
        duration="constant_while_bearer_alive",
        effect="grant_deep_strike_to_bearer_unit",
        effect_params={
            "grants_deep_strike": True,
            "requires_bearer_alive": True,
        },
    ),
    "000010451003": EnhancementToolDescriptor(
        enhancement_id="000010451003",
        name="Calculated Tenacity",
        timing="while_bearer_is_leading",
        target="bearer_unit",
        duration="constant_while_bearer_is_leading",
        effect="objective_control_bonus",
        effect_params={
            "objective_control_bonus": 1,
            "requires_bearer_alive": True,
            "requires_bearer_leading": True,
        },
    ),
    "000010451004": EnhancementToolDescriptor(
        enhancement_id="000010451004",
        name="Mantle of Elders",
        timing="on_optimal_application_spend",
        target="bearer_unit",
        duration="instant",
        effect="optimal_application_yp_refund_on_successful_roll",
        effect_params={
            "refund_roll_threshold": 2,
            "refund_yp": 1,
            "requires_bearer_alive": True,
        },
    ),
    "000010451005": EnhancementToolDescriptor(
        enhancement_id="000010451005",
        name="Graviton Vault",
        timing="post_shoot_and_post_fight",
        target="enemy_monster_or_vehicle_hit_by_bearer",
        duration="until_start_of_next_turn",
        effect="post_shoot_and_post_fight_suppression",
        effect_params={
            "suppression_requires_monster_or_vehicle": True,
            "requires_bearer_alive": True,
        },
    ),
}

_LEAGUES_OF_VOTANN_HEARTHFYRE_ARSENAL_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _LEAGUES_OF_VOTANN_HEARTHFYRE_ARSENAL_DESCRIPTORS.values()
}

_LEAGUES_OF_VOTANN_MERCENARY_OATHBAND_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010708002": EnhancementToolDescriptor(
        enhancement_id="000010708002",
        name="Mercenary Prospector",
        timing="enemy_unit_destroyed_by_bearer_unit",
        target="bearer_unit",
        duration="instant",
        effect="gain_yield_points_on_destroyed_enemy_unit",
        effect_params={
            "yield_points_gain": 2,
            "requires_bearer_alive": True,
        },
    ),
    "000010708003": EnhancementToolDescriptor(
        enhancement_id="000010708003",
        name="Metaphysical Brokerage",
        timing="end_of_your_turn",
        target="bearer",
        duration="instant",
        effect="top_up_yield_points_gained_this_turn_to_minimum",
        effect_params={
            "minimum_yield_points_gained": 3,
            "requires_bearer_alive": True,
            "requires_bearer_on_battlefield": True,
        },
    ),
    "000010708004": EnhancementToolDescriptor(
        enhancement_id="000010708004",
        name="Etacarn SB9 Targeting Implant",
        timing="passive_and_when_selected_to_shoot_or_fight",
        target="bearer_unit",
        duration="constant_and_until_end_of_phase_on_activation",
        effect="reroll_hit_ones_and_optional_yp_spend_for_sustained_hits",
        effect_params={
            "reroll_hit_values": (1,),
            "yp_cost": 3,
            "sustained_hits_value": 1,
            "requires_bearer_alive": True,
        },
    ),
    "000010708005": EnhancementToolDescriptor(
        enhancement_id="000010708005",
        name="Asset Manipulator",
        timing="start_of_command_phase",
        target="enemy_units_within_range_of_bearer",
        duration="until_end_of_turn",
        effect="optional_yp_spend_enemy_objective_control_penalty_aura",
        range_in=3.0,
        effect_params={
            "yp_cost": 3,
            "range_in": 3.0,
            "objective_control_penalty": 1,
            "requires_bearer_alive": True,
        },
    ),
}

_LEAGUES_OF_VOTANN_MERCENARY_OATHBAND_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _LEAGUES_OF_VOTANN_MERCENARY_OATHBAND_DESCRIPTORS.values()
}

_LEAGUES_OF_VOTANN_PERSECUTION_PROSPECT_DESCRIPTORS: dict[str, EnhancementToolDescriptor] = {
    "000010439002": EnhancementToolDescriptor(
        enhancement_id="000010439002",
        name="Eye for Weakness",
        timing="passive",
        target="assailed_enemy_units_attacked_by_bearer_unit",
        duration="constant_while_bearer_alive",
        effect="wound_bonus_vs_assailed_targets",
        effect_params={
            "wound_roll_bonus": 1,
            "requires_bearer_alive": True,
        },
    ),
    "000010439003": EnhancementToolDescriptor(
        enhancement_id="000010439003",
        name="Writ of Acquisition",
        timing="post_shoot",
        target="assailed_enemy_units_hit_by_bearer_unit",
        duration="instant",
        effect="post_shoot_gain_yp_for_hit_assailed_units",
        effect_params={
            "yield_points_per_hit_unit": 1,
            "max_yield_points_gain": 3,
            "requires_bearer_alive": True,
        },
    ),
    "000010439004": EnhancementToolDescriptor(
        enhancement_id="000010439004",
        name="Surgical Saboteur",
        timing="post_shoot",
        target="hit_enemy_monster_or_vehicle",
        duration="until_start_of_next_shooting_phase",
        effect="post_shoot_select_hit_monster_or_vehicle_to_pin",
        effect_params={
            "move_penalty": -2,
            "charge_penalty": -2,
            "target_keywords_any": ("MONSTER", "VEHICLE"),
            "expires_phase": "SHOOTING_PHASE",
            "requires_bearer_alive": True,
        },
    ),
    "000010439005": EnhancementToolDescriptor(
        enhancement_id="000010439005",
        name="Nomad Strategist",
        timing="end_of_opponent_fight_phase_once_per_battle",
        target="friendly_hernkyn_units",
        duration="instant_once_per_battle",
        effect="once_per_battle_end_of_opponent_fight_phase_select_hernkyn_units_to_enter_strategic_reserves",
        effect_params={
            "once_per_battle_key": "nomad_strategist",
            "max_yp_spend": 4,
            "requires_bearer_alive": True,
            "requires_bearer_on_battlefield": True,
            "destination": "strategic_reserves",
        },
    ),
}

_LEAGUES_OF_VOTANN_PERSECUTION_PROSPECT_BY_NAME = {
    _normalize_name(desc.name): desc for desc in _LEAGUES_OF_VOTANN_PERSECUTION_PROSPECT_DESCRIPTORS.values()
}


def get_enhancement_tool_descriptor(*, enhancement_id: str = "", name: str = "") -> Optional[EnhancementToolDescriptor]:
    if enhancement_id:
        desc = _GORETRACK_ONSLAUGHT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CULT_OF_BLOOD_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GRIZZLED_COMPANY_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _BRIDGEHEAD_STRIKE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _COMBINED_ARMS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _HAMMER_OF_THE_EMPEROR_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _MECHANISED_ASSAULT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _RECON_ELEMENT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SIEGE_REGIMENT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _POSSESSED_SLAUGHTERBAND_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _VESSELS_OF_WRATH_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ADEPTA_SORORITAS_ARMY_OF_FAITH_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ADEPTA_SORORITAS_BRINGERS_OF_FLAME_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ADEPTA_SORORITAS_CHAMPIONS_OF_FAITH_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ADEPTA_SORORITAS_PENITENT_HOST_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AELDARI_GUARDIAN_BATTLEHOST_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AELDARI_SEER_COUNCIL_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AELDARI_CORSAIR_COTERIE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AELDARI_ELDRITCH_RAIDERS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AELDARI_WINDRIDER_HOST_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AELDARI_GHOSTS_OF_THE_WEBWAY_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AELDARI_SPIRIT_CONCLAVE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AELDARI_SERPENTS_BROOD_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AELDARI_DEVOTED_OF_YNNEAD_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _EXPERIMENTAL_PROTOTYPE_CADRE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _TAU_AUXILIARY_CADRE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _TAU_KROOT_HUNTING_PACK_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _MONTKA_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _RETALIATION_CADRE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _RAD_ZONE_CORPS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SKITARII_HUNTER_COHORT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _COHORT_CYBERNETICA_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DATA_PSALM_CONCLAVE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ADEPTUS_CUSTODES_AURIC_CHAMPIONS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ADEPTUS_CUSTODES_NULL_MAIDEN_VIGIL_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ADEPTUS_CUSTODES_SHIELD_HOST_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ADEPTUS_CUSTODES_SOLAR_SPEARHEAD_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ADEPTUS_CUSTODES_TALONS_OF_THE_EMPEROR_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _EXPLORATOR_MANIPLE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _HALOSCREED_BATTLE_CLADE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ERADICATION_COHORT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _INVASION_FLEET_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CABAL_OF_CHAOS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CHAOS_CULT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CREATIONS_OF_BILE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DECEPTORS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DREAD_TALONS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _FELLHAMMER_SIEGE_HOST_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _HURONS_MARAUDERS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _NIGHTMARE_HUNT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _PACTBOUND_ZEALOTS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _RENEGADE_RAIDERS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _RENEGADE_WARBAND_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SOULFORGED_WARPACK_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _VETERANS_OF_THE_LONG_WAR_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _REALSPACE_RAIDERS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _COVENITE_COTERIE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _REAPERS_WAGER_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _KABALITE_CARTEL_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPECTACLE_OF_SPITE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SKYSPLINTER_ASSAULT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _COURT_OF_THE_PHOENICIAN_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SLAANESHS_CHOSEN_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _COTERIE_OF_CONCEITED_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CARNIVAL_OF_EXCESS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DAEMONIC_INCURSION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SHADOW_LEGION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _BLOOD_LEGION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_FIRST_COMPANY_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_ANGELIC_INHERITORS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_THE_ANGELIC_HOST_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_THE_LOST_BRETHREN_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_UNFORGIVEN_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_ANVIL_SIEGE_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_FIRESTORM_ASSAULT_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_FORGEFATHERS_SEEKERS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_GLADIUS_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_GODHAMMER_ASSAULT_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_HAMMER_OF_AVERNII_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_INNER_CIRCLE_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_WRATH_OF_THE_ROCK_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_WRATHFUL_PROCESSION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_IRONSTORM_SPEARHEAD_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_LIBERATOR_ASSAULT_GROUP_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_LIBRARIUS_CONCLAVE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_LIONS_BLADE_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_ORBITAL_ASSAULT_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_CERAMITE_SENTINELS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_RECLAMATION_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_BASTION_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_BLADE_OF_ULTRAMAR_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_CHAMPIONS_OF_FENRIS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_SAGA_OF_THE_BEASTSLAYER_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_SAGA_OF_THE_BOLD_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_SAGA_OF_THE_HUNTER_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_SAGA_OF_THE_GREAT_WOLF_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_STORMLANCE_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_COMPANY_OF_HUNTERS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_VANGUARD_SPEARHEAD_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_SHADOWMARK_TALON_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_SPEARPOINT_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_COMPANIONS_OF_VEHEMENCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_EMPERORS_SHIELD_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_BLACK_SPEAR_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPACE_MARINES_VINDICATION_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _LEGION_OF_EXCESS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _PLAGUE_LEGION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DEATH_GUARD_CHAMPIONS_OF_CONTAGION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DEATH_GUARD_DEATH_LORDS_CHOSEN_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DEATH_GUARD_FLYBLOWN_HOST_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DEATH_GUARD_MORTARIONS_HAMMER_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DEATH_GUARD_TALLYBAND_SUMMONERS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DEATH_GUARD_SHAMBLEROT_VECTORIUM_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AGENTS_OF_THE_IMPERIUM_ORDO_XENOS_ALIEN_HUNTERS_DESCRIPTORS.get(str(enhancement_id))
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
        desc = _GREY_KNIGHTS_BROTHERHOOD_STRIKE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GREY_KNIGHTS_AUGURIUM_TASK_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GREY_KNIGHTS_BANISHERS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GREY_KNIGHTS_HALLOWED_CONCLAVE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GREY_KNIGHTS_SANCTIC_SPEARHEAD_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CHAOS_KNIGHTS_HOUNDPACK_LANCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CHAOS_KNIGHTS_HELHUNT_LANCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CHAOS_KNIGHTS_TRAITORIS_LANCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CHAOS_KNIGHTS_LORDS_OF_DREAD_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _IMPERIAL_KNIGHTS_GATE_WARDEN_LANCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _IMPERIAL_KNIGHTS_FREEBLADE_COMPANY_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _IMPERIAL_KNIGHTS_QUESTORIS_COMPANIONS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _IMPERIAL_KNIGHTS_SPEARHEAD_AT_ARMS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _VEILED_BLADE_ELIMINATION_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GENESTEALER_CULTS_HOST_OF_ASCENSION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GENESTEALER_CULTS_BIOSANCTIC_BROODSURGE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GENESTEALER_CULTS_BROOD_BROTHER_AUXILIA_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GENESTEALER_CULTS_FINAL_DAY_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GENESTEALER_CULTS_OUTLANDER_CLAW_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GENESTEALER_CULTS_XENOCREED_CONGREGATION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AGENTS_OF_THE_IMPERIUM_ORDO_HERETICUS_PURGATION_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AGENTS_OF_THE_IMPERIUM_ORDO_MALLEUS_DAEMON_HUNTERS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _AGENTS_OF_THE_IMPERIUM_IMPERIALIS_FLEET_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _TAU_KAUYON_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _THOUSAND_SONS_CHANGEHOST_OF_DECEIT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _THOUSAND_SONS_HEXWARP_THRALLBAND_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _THOUSAND_SONS_WARPFORGED_CABAL_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _THOUSAND_SONS_WARPMELD_PACT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _NECRONS_ANNIHILATION_LEGION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _NECRONS_AWAKENED_DYNASTY_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _NECRONS_CANOPTEK_COURT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _NECRONS_HYPERCRYPT_LEGION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _NECRONS_OBEISANCE_PHALANX_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _NECRONS_PANTHEON_OF_WOE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _NECRONS_CURSED_LEGION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _NECRONS_CRYPTEK_CONCLAVE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _NECRONS_STARSHATTER_ARSENAL_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _TYRANIDS_SUBTERRANEAN_ASSAULT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _TYRANIDS_SYNAPTIC_NEXUS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _TYRANIDS_WARRIOR_BIOFORM_ONSLAUGHT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _TYRANIDS_UNENDING_SWARM_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _TYRANIDS_VANGUARD_ONSLAUGHT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _TYRANIDS_CRUSHER_STAMPEDE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _TYRANIDS_ASSIMILATION_SWARM_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ORKS_BULLY_BOYZ_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ORKS_DA_BIG_HUNT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ORKS_DREAD_MOB_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ORKS_FREEBOOTER_KREW_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ORKS_GREEN_TIDE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ORKS_KULT_OF_SPEED_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ORKS_MORE_DAKKA_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _ORKS_TAKTIKAL_BRIGADE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _LEAGUES_OF_VOTANN_BRANDFAST_OATHBAND_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _LEAGUES_OF_VOTANN_DELVE_ASSAULT_SHIFT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _LEAGUES_OF_VOTANN_HEARTHFYRE_ARSENAL_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _LEAGUES_OF_VOTANN_MERCENARY_OATHBAND_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _LEAGUES_OF_VOTANN_PERSECUTION_PROSPECT_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
    key = _normalize_name(name)
    if not key:
        return None
    return (
        _GORETRACK_ONSLAUGHT_BY_NAME.get(key)
        or _CULT_OF_BLOOD_BY_NAME.get(key)
        or _GRIZZLED_COMPANY_BY_NAME.get(key)
        or _BRIDGEHEAD_STRIKE_BY_NAME.get(key)
        or _COMBINED_ARMS_BY_NAME.get(key)
        or _HAMMER_OF_THE_EMPEROR_BY_NAME.get(key)
        or _MECHANISED_ASSAULT_BY_NAME.get(key)
        or _RECON_ELEMENT_BY_NAME.get(key)
        or _SIEGE_REGIMENT_BY_NAME.get(key)
        or _POSSESSED_SLAUGHTERBAND_BY_NAME.get(key)
        or _VESSELS_OF_WRATH_BY_NAME.get(key)
        or _ADEPTA_SORORITAS_ARMY_OF_FAITH_BY_NAME.get(key)
        or _ADEPTA_SORORITAS_BRINGERS_OF_FLAME_BY_NAME.get(key)
        or _ADEPTA_SORORITAS_CHAMPIONS_OF_FAITH_BY_NAME.get(key)
        or _ADEPTA_SORORITAS_PENITENT_HOST_BY_NAME.get(key)
        or _AELDARI_GUARDIAN_BATTLEHOST_BY_NAME.get(key)
        or _AELDARI_SEER_COUNCIL_BY_NAME.get(key)
        or _AELDARI_CORSAIR_COTERIE_BY_NAME.get(key)
        or _AELDARI_ELDRITCH_RAIDERS_BY_NAME.get(key)
        or _AELDARI_WINDRIDER_HOST_BY_NAME.get(key)
        or _AELDARI_GHOSTS_OF_THE_WEBWAY_BY_NAME.get(key)
        or _AELDARI_SPIRIT_CONCLAVE_BY_NAME.get(key)
        or _AELDARI_SERPENTS_BROOD_BY_NAME.get(key)
        or _AELDARI_DEVOTED_OF_YNNEAD_BY_NAME.get(key)
        or _EXPERIMENTAL_PROTOTYPE_CADRE_BY_NAME.get(key)
        or _TAU_AUXILIARY_CADRE_BY_NAME.get(key)
        or _TAU_KROOT_HUNTING_PACK_BY_NAME.get(key)
        or _MONTKA_BY_NAME.get(key)
        or _RETALIATION_CADRE_BY_NAME.get(key)
        or _RAD_ZONE_CORPS_BY_NAME.get(key)
        or _SKITARII_HUNTER_COHORT_BY_NAME.get(key)
        or _COHORT_CYBERNETICA_BY_NAME.get(key)
        or _DATA_PSALM_CONCLAVE_BY_NAME.get(key)
        or _ADEPTUS_CUSTODES_AURIC_CHAMPIONS_BY_NAME.get(key)
        or _ADEPTUS_CUSTODES_NULL_MAIDEN_VIGIL_BY_NAME.get(key)
        or _ADEPTUS_CUSTODES_SHIELD_HOST_BY_NAME.get(key)
        or _ADEPTUS_CUSTODES_SOLAR_SPEARHEAD_BY_NAME.get(key)
        or _ADEPTUS_CUSTODES_TALONS_OF_THE_EMPEROR_BY_NAME.get(key)
        or _EXPLORATOR_MANIPLE_BY_NAME.get(key)
        or _HALOSCREED_BATTLE_CLADE_BY_NAME.get(key)
        or _ERADICATION_COHORT_BY_NAME.get(key)
        or _INVASION_FLEET_BY_NAME.get(key)
        or _CABAL_OF_CHAOS_BY_NAME.get(key)
        or _CHAOS_CULT_BY_NAME.get(key)
        or _CREATIONS_OF_BILE_BY_NAME.get(key)
        or _DECEPTORS_BY_NAME.get(key)
        or _DREAD_TALONS_BY_NAME.get(key)
        or _FELLHAMMER_SIEGE_HOST_BY_NAME.get(key)
        or _HURONS_MARAUDERS_BY_NAME.get(key)
        or _NIGHTMARE_HUNT_BY_NAME.get(key)
        or _PACTBOUND_ZEALOTS_BY_NAME.get(key)
        or _RENEGADE_RAIDERS_BY_NAME.get(key)
        or _RENEGADE_WARBAND_BY_NAME.get(key)
        or _SOULFORGED_WARPACK_BY_NAME.get(key)
        or _VETERANS_OF_THE_LONG_WAR_BY_NAME.get(key)
        or _REALSPACE_RAIDERS_BY_NAME.get(key)
        or _COVENITE_COTERIE_BY_NAME.get(key)
        or _REAPERS_WAGER_BY_NAME.get(key)
        or _KABALITE_CARTEL_BY_NAME.get(key)
        or _SPECTACLE_OF_SPITE_BY_NAME.get(key)
        or _SKYSPLINTER_ASSAULT_BY_NAME.get(key)
        or _COURT_OF_THE_PHOENICIAN_BY_NAME.get(key)
        or _SLAANESHS_CHOSEN_BY_NAME.get(key)
        or _COTERIE_OF_CONCEITED_BY_NAME.get(key)
        or _CARNIVAL_OF_EXCESS_BY_NAME.get(key)
        or _DAEMONIC_INCURSION_BY_NAME.get(key)
        or _SHADOW_LEGION_BY_NAME.get(key)
        or _BLOOD_LEGION_BY_NAME.get(key)
        or _SPACE_MARINES_FIRST_COMPANY_TASK_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_ANGELIC_INHERITORS_BY_NAME.get(key)
        or _SPACE_MARINES_THE_ANGELIC_HOST_BY_NAME.get(key)
        or _SPACE_MARINES_THE_LOST_BRETHREN_BY_NAME.get(key)
        or _SPACE_MARINES_UNFORGIVEN_TASK_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_ANVIL_SIEGE_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_FIRESTORM_ASSAULT_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_FORGEFATHERS_SEEKERS_BY_NAME.get(key)
        or _SPACE_MARINES_GLADIUS_TASK_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_GODHAMMER_ASSAULT_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_HAMMER_OF_AVERNII_BY_NAME.get(key)
        or _SPACE_MARINES_INNER_CIRCLE_TASK_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_WRATH_OF_THE_ROCK_BY_NAME.get(key)
        or _SPACE_MARINES_WRATHFUL_PROCESSION_BY_NAME.get(key)
        or _SPACE_MARINES_IRONSTORM_SPEARHEAD_BY_NAME.get(key)
        or _SPACE_MARINES_LIBERATOR_ASSAULT_GROUP_BY_NAME.get(key)
        or _SPACE_MARINES_LIBRARIUS_CONCLAVE_BY_NAME.get(key)
        or _SPACE_MARINES_LIONS_BLADE_TASK_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_ORBITAL_ASSAULT_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_CERAMITE_SENTINELS_BY_NAME.get(key)
        or _SPACE_MARINES_RECLAMATION_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_BASTION_TASK_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_BLADE_OF_ULTRAMAR_BY_NAME.get(key)
        or _SPACE_MARINES_CHAMPIONS_OF_FENRIS_BY_NAME.get(key)
        or _SPACE_MARINES_SAGA_OF_THE_BEASTSLAYER_BY_NAME.get(key)
        or _SPACE_MARINES_SAGA_OF_THE_BOLD_BY_NAME.get(key)
        or _SPACE_MARINES_SAGA_OF_THE_HUNTER_BY_NAME.get(key)
        or _SPACE_MARINES_SAGA_OF_THE_GREAT_WOLF_BY_NAME.get(key)
        or _SPACE_MARINES_STORMLANCE_TASK_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_COMPANY_OF_HUNTERS_BY_NAME.get(key)
        or _SPACE_MARINES_VANGUARD_SPEARHEAD_BY_NAME.get(key)
        or _SPACE_MARINES_SHADOWMARK_TALON_BY_NAME.get(key)
        or _SPACE_MARINES_SPEARPOINT_TASK_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_COMPANIONS_OF_VEHEMENCE_BY_NAME.get(key)
        or _SPACE_MARINES_EMPERORS_SHIELD_BY_NAME.get(key)
        or _SPACE_MARINES_BLACK_SPEAR_TASK_FORCE_BY_NAME.get(key)
        or _SPACE_MARINES_VINDICATION_TASK_FORCE_BY_NAME.get(key)
        or _LEGION_OF_EXCESS_BY_NAME.get(key)
        or _PLAGUE_LEGION_BY_NAME.get(key)
        or _DEATH_GUARD_CHAMPIONS_OF_CONTAGION_BY_NAME.get(key)
        or _DEATH_GUARD_DEATH_LORDS_CHOSEN_BY_NAME.get(key)
        or _DEATH_GUARD_FLYBLOWN_HOST_BY_NAME.get(key)
        or _DEATH_GUARD_MORTARIONS_HAMMER_BY_NAME.get(key)
        or _DEATH_GUARD_TALLYBAND_SUMMONERS_BY_NAME.get(key)
        or _DEATH_GUARD_SHAMBLEROT_VECTORIUM_BY_NAME.get(key)
        or _SCINTILLATING_LEGION_BY_NAME.get(key)
        or _GRAND_COVEN_BY_NAME.get(key)
        or _RUBRICAE_PHALANX_BY_NAME.get(key)
        or _WARPBANE_TASK_FORCE_BY_NAME.get(key)
        or _GREY_KNIGHTS_BROTHERHOOD_STRIKE_BY_NAME.get(key)
        or _GREY_KNIGHTS_AUGURIUM_TASK_FORCE_BY_NAME.get(key)
        or _GREY_KNIGHTS_BANISHERS_BY_NAME.get(key)
        or _GREY_KNIGHTS_HALLOWED_CONCLAVE_BY_NAME.get(key)
        or _GREY_KNIGHTS_SANCTIC_SPEARHEAD_BY_NAME.get(key)
        or _CHAOS_KNIGHTS_HOUNDPACK_LANCE_BY_NAME.get(key)
        or _CHAOS_KNIGHTS_HELHUNT_LANCE_BY_NAME.get(key)
        or _CHAOS_KNIGHTS_TRAITORIS_LANCE_BY_NAME.get(key)
        or _CHAOS_KNIGHTS_LORDS_OF_DREAD_BY_NAME.get(key)
        or _IMPERIAL_KNIGHTS_QUESTOR_FORGEPACT_BY_NAME.get(key)
        or _IMPERIAL_KNIGHTS_GATE_WARDEN_LANCE_BY_NAME.get(key)
        or _IMPERIAL_KNIGHTS_FREEBLADE_COMPANY_BY_NAME.get(key)
        or _IMPERIAL_KNIGHTS_QUESTORIS_COMPANIONS_BY_NAME.get(key)
        or _IMPERIAL_KNIGHTS_SPEARHEAD_AT_ARMS_BY_NAME.get(key)
        or _VEILED_BLADE_ELIMINATION_FORCE_BY_NAME.get(key)
        or _GENESTEALER_CULTS_HOST_OF_ASCENSION_BY_NAME.get(key)
        or _GENESTEALER_CULTS_BIOSANCTIC_BROODSURGE_BY_NAME.get(key)
        or _GENESTEALER_CULTS_BROOD_BROTHER_AUXILIA_BY_NAME.get(key)
        or _GENESTEALER_CULTS_FINAL_DAY_BY_NAME.get(key)
        or _GENESTEALER_CULTS_OUTLANDER_CLAW_BY_NAME.get(key)
        or _GENESTEALER_CULTS_XENOCREED_CONGREGATION_BY_NAME.get(key)
        or _AGENTS_OF_THE_IMPERIUM_ORDO_HERETICUS_PURGATION_FORCE_BY_NAME.get(key)
        or _AGENTS_OF_THE_IMPERIUM_ORDO_XENOS_ALIEN_HUNTERS_BY_NAME.get(key)
        or _AGENTS_OF_THE_IMPERIUM_ORDO_MALLEUS_DAEMON_HUNTERS_BY_NAME.get(key)
        or _AGENTS_OF_THE_IMPERIUM_IMPERIALIS_FLEET_BY_NAME.get(key)
        or _TAU_KROOT_HUNTING_PACK_BY_NAME.get(key)
        or _TAU_KAUYON_BY_NAME.get(key)
        or _THOUSAND_SONS_CHANGEHOST_OF_DECEIT_BY_NAME.get(key)
        or _THOUSAND_SONS_HEXWARP_THRALLBAND_BY_NAME.get(key)
        or _THOUSAND_SONS_WARPFORGED_CABAL_BY_NAME.get(key)
        or _THOUSAND_SONS_WARPMELD_PACT_BY_NAME.get(key)
        or _NECRONS_ANNIHILATION_LEGION_BY_NAME.get(key)
        or _NECRONS_AWAKENED_DYNASTY_BY_NAME.get(key)
        or _NECRONS_CANOPTEK_COURT_BY_NAME.get(key)
        or _NECRONS_HYPERCRYPT_LEGION_BY_NAME.get(key)
        or _NECRONS_OBEISANCE_PHALANX_BY_NAME.get(key)
        or _NECRONS_PANTHEON_OF_WOE_BY_NAME.get(key)
        or _NECRONS_CURSED_LEGION_BY_NAME.get(key)
        or _NECRONS_CRYPTEK_CONCLAVE_BY_NAME.get(key)
        or _NECRONS_STARSHATTER_ARSENAL_BY_NAME.get(key)
        or _TYRANIDS_SUBTERRANEAN_ASSAULT_BY_NAME.get(key)
        or _TYRANIDS_SYNAPTIC_NEXUS_BY_NAME.get(key)
        or _TYRANIDS_WARRIOR_BIOFORM_ONSLAUGHT_BY_NAME.get(key)
        or _TYRANIDS_UNENDING_SWARM_BY_NAME.get(key)
        or _TYRANIDS_VANGUARD_ONSLAUGHT_BY_NAME.get(key)
        or _TYRANIDS_CRUSHER_STAMPEDE_BY_NAME.get(key)
        or _TYRANIDS_ASSIMILATION_SWARM_BY_NAME.get(key)
        or _ORKS_BULLY_BOYZ_BY_NAME.get(key)
        or _ORKS_DA_BIG_HUNT_BY_NAME.get(key)
        or _ORKS_DREAD_MOB_BY_NAME.get(key)
        or _ORKS_FREEBOOTER_KREW_BY_NAME.get(key)
        or _ORKS_GREEN_TIDE_BY_NAME.get(key)
        or _ORKS_KULT_OF_SPEED_BY_NAME.get(key)
        or _ORKS_MORE_DAKKA_BY_NAME.get(key)
        or _ORKS_TAKTIKAL_BRIGADE_BY_NAME.get(key)
        or _LEAGUES_OF_VOTANN_BRANDFAST_OATHBAND_BY_NAME.get(key)
        or _LEAGUES_OF_VOTANN_DELVE_ASSAULT_SHIFT_BY_NAME.get(key)
        or _LEAGUES_OF_VOTANN_HEARTHFYRE_ARSENAL_BY_NAME.get(key)
        or _LEAGUES_OF_VOTANN_MERCENARY_OATHBAND_BY_NAME.get(key)
        or _LEAGUES_OF_VOTANN_PERSECUTION_PROSPECT_BY_NAME.get(key)
    )
