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
        desc = _POSSESSED_SLAUGHTERBAND_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _VESSELS_OF_WRATH_DESCRIPTORS.get(str(enhancement_id))
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
        desc = _MONTKA_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _RAD_ZONE_CORPS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _INVASION_FLEET_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CABAL_OF_CHAOS_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _SPECTACLE_OF_SPITE_DESCRIPTORS.get(str(enhancement_id))
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
        desc = _VEILED_BLADE_ELIMINATION_FORCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _GENESTEALER_CULTS_HOST_OF_ASCENSION_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
    key = _normalize_name(name)
    if not key:
        return None
    return (
        _GORETRACK_ONSLAUGHT_BY_NAME.get(key)
        or _CULT_OF_BLOOD_BY_NAME.get(key)
        or _GRIZZLED_COMPANY_BY_NAME.get(key)
        or _POSSESSED_SLAUGHTERBAND_BY_NAME.get(key)
        or _VESSELS_OF_WRATH_BY_NAME.get(key)
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
        or _MONTKA_BY_NAME.get(key)
        or _RAD_ZONE_CORPS_BY_NAME.get(key)
        or _INVASION_FLEET_BY_NAME.get(key)
        or _CABAL_OF_CHAOS_BY_NAME.get(key)
        or _SPECTACLE_OF_SPITE_BY_NAME.get(key)
        or _COURT_OF_THE_PHOENICIAN_BY_NAME.get(key)
        or _SLAANESHS_CHOSEN_BY_NAME.get(key)
        or _COTERIE_OF_CONCEITED_BY_NAME.get(key)
        or _CARNIVAL_OF_EXCESS_BY_NAME.get(key)
        or _DAEMONIC_INCURSION_BY_NAME.get(key)
        or _SHADOW_LEGION_BY_NAME.get(key)
        or _PLAGUE_LEGION_BY_NAME.get(key)
        or _SCINTILLATING_LEGION_BY_NAME.get(key)
        or _GRAND_COVEN_BY_NAME.get(key)
        or _RUBRICAE_PHALANX_BY_NAME.get(key)
        or _WARPBANE_TASK_FORCE_BY_NAME.get(key)
        or _VEILED_BLADE_ELIMINATION_FORCE_BY_NAME.get(key)
        or _GENESTEALER_CULTS_HOST_OF_ASCENSION_BY_NAME.get(key)
    )
