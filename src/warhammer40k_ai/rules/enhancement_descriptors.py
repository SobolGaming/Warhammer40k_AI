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
        desc = _COHORT_CYBERNETICA_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _DATA_PSALM_CONCLAVE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _EXPLORATOR_MANIPLE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _HALOSCREED_BATTLE_CLADE_DESCRIPTORS.get(str(enhancement_id))
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
        desc = _CHAOS_KNIGHTS_HOUNDPACK_LANCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CHAOS_KNIGHTS_TRAITORIS_LANCE_DESCRIPTORS.get(str(enhancement_id))
        if desc is not None:
            return desc
        desc = _CHAOS_KNIGHTS_LORDS_OF_DREAD_DESCRIPTORS.get(str(enhancement_id))
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
        or _COHORT_CYBERNETICA_BY_NAME.get(key)
        or _DATA_PSALM_CONCLAVE_BY_NAME.get(key)
        or _EXPLORATOR_MANIPLE_BY_NAME.get(key)
        or _HALOSCREED_BATTLE_CLADE_BY_NAME.get(key)
        or _INVASION_FLEET_BY_NAME.get(key)
        or _CABAL_OF_CHAOS_BY_NAME.get(key)
        or _SPECTACLE_OF_SPITE_BY_NAME.get(key)
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
        or _SCINTILLATING_LEGION_BY_NAME.get(key)
        or _GRAND_COVEN_BY_NAME.get(key)
        or _RUBRICAE_PHALANX_BY_NAME.get(key)
        or _WARPBANE_TASK_FORCE_BY_NAME.get(key)
        or _CHAOS_KNIGHTS_HOUNDPACK_LANCE_BY_NAME.get(key)
        or _CHAOS_KNIGHTS_TRAITORIS_LANCE_BY_NAME.get(key)
        or _CHAOS_KNIGHTS_LORDS_OF_DREAD_BY_NAME.get(key)
        or _VEILED_BLADE_ELIMINATION_FORCE_BY_NAME.get(key)
        or _GENESTEALER_CULTS_HOST_OF_ASCENSION_BY_NAME.get(key)
    )
