from __future__ import annotations

from typing import Iterable, List

from ..context import RulesContext, any_faction, any_manager
from ..registry import RuleProvider


def _register_stratagems(game: object, event_system: object, group: str) -> bool:
    if game is None or event_system is None:
        return False
    try:
        players = list(getattr(game, "players", []) or [])
    except Exception:
        players = []
    registered = False
    for player in players:
        stratagems = getattr(player, "stratagems", None)
        enable_fn = getattr(stratagems, "enable_event_subscriptions", None)
        if callable(enable_fn):
            enable_fn(event_system=event_system, group=group)
            registered = True
    return registered


def _unregister_stratagems(game: object, event_system: object, group: str) -> None:
    if game is None or event_system is None:
        return
    try:
        players = list(getattr(game, "players", []) or [])
    except Exception:
        players = []
    for player in players:
        stratagems = getattr(player, "stratagems", None)
        disable_fn = getattr(stratagems, "disable_event_subscriptions", None)
        if callable(disable_fn):
            disable_fn(event_system=event_system, group=group)


def build_default_rule_providers() -> List[RuleProvider]:
    providers: List[RuleProvider] = []

    providers.append(
        RuleProvider(
            name="core",
            subscriptions=[
                ("model_destroyed", "_on_model_destroyed_rules"),
                ("model_destroyed", "_on_model_destroyed_friendly_keyword_range_battleshock"),
                ("model_destroyed", "_on_model_destroyed_friendly_destroyed_model_weapon_attacks_override"),
                ("model_destroyed", "_on_model_destroyed_tally_of_pestilence"),
                ("model_destroyed", "_on_model_destroyed_phase_kill_tracking"),
                ("model_destroyed", "_on_model_destroyed_death_guard_final_ingredient"),
                ("model_destroyed", "_on_model_destroyed_spirit_snare"),
                ("model_destroyed", "_on_model_destroyed_spirit_conclave_shepherds"),
                ("model_destroyed", "_on_model_destroyed_curse_of_the_walking_pox"),
                ("model_destroyed", "_on_model_destroyed_parasitic_infection"),
                ("battle_shock_test_resolved", "_on_battle_shock_test_resolved_enemy_failed_battleshock_aura"),
                ("unit_destroyed", "_on_unit_destroyed_rules"),
                ("unit_destroyed", "_on_unit_destroyed_battleshock_on_kill"),
                ("unit_destroyed", "_on_unit_destroyed_phase_kill_tracking"),
                ("unit_destroyed", "_on_unit_destroyed_transport_rules"),
                ("unit_destroyed", "_on_unit_destroyed_tyranids_detachments"),
                ("bodyguard_unit_destroyed", "_on_bodyguard_unit_destroyed_cp_gain"),
                ("unit_destroyed", "_on_unit_destroyed_friendly_unit_destroyed_reposition"),
                ("unit_destroyed", "_on_unit_destroyed_storm_of_vengeance"),
                ("unit_destroyed", "_on_unit_destroyed_explosive_blight"),
                ("unit_destroyed", "_on_unit_destroyed_extraction_of_fresh_disease"),
                ("unit_move_ended", "_on_unit_move_ended_detachment_rules"),
                ("unit_move_ended", "_on_unit_move_ended_charge_mortal_wounds"),
                ("unit_move_ended", "_on_unit_move_ended_charge_battleshock"),
                ("unit_move_ended", "_on_unit_move_ended_bomb_squigs"),
                ("unit_move_ended", "_on_unit_move_ended_plunder"),
                ("unit_move_ended", "_on_unit_move_ended_move_over_mortal_wounds"),
                ("unit_move_ended", "_on_unit_move_ended_move_over_battleshock"),
                ("unit_move_ended", "_on_unit_move_ended_move_over_no_cover"),
                ("unit_move_ended", "_on_unit_move_ended_grenade_pack_flyover"),
                ("unit_move_ended", "_on_unit_move_ended_diseased_influence"),
                ("unit_move_ended", "_on_unit_move_ended_snared_mortal_wounds"),
                ("unit_move_ended", "_on_unit_move_ended_gravitic_pulse"),
                ("unit_move_ended", "_on_unit_move_ended_transport_reactive_disembark"),
                ("unit_set_up", "_on_unit_set_up_transport_reactive_disembark"),
                ("unit_set_up", "_on_unit_set_up_grenade_pack_flyover"),
                ("unit_set_up", "_on_unit_set_up_deep_strike_enemy_range_mortal_wounds_battleshock"),
                ("unit_set_up", "_on_unit_set_up_cry_of_the_wind"),
                ("unit_set_up", "_on_unit_set_up_a_foot_in_the_future"),
                ("unit_set_up", "_on_unit_set_up_grey_knights_detachments"),
                ("unit_set_up", "_on_unit_set_up_drukhari_detachments"),
                ("unit_set_up", "_on_unit_set_up_genestealer_cults_detachments"),
                ("unit_set_up", "_on_unit_set_up_tyranids_detachments"),
                ("unit_set_up", "_on_unit_set_up_orks_detachments"),
                ("unit_set_up", "_on_unit_set_up_csm_detachment_rules"),
                ("unit_set_up", "_on_unit_set_up_seeker_of_lost_relics"),
                ("unit_set_up", "_on_unit_set_up_setup_reactive_shoot_or_charge"),
                ("unit_set_up", "_on_unit_set_up_hyperspace_hunters"),
                ("unit_set_up", "_on_unit_set_up_deep_strike_setup_model_shoot"),
                ("unit_disembarked", "_on_unit_disembarked_csm_detachment_rules"),
                ("unit_disembarked", "_on_unit_disembarked_setup_reactive_shoot_or_charge"),
                ("unit_move_ended", "_on_unit_move_ended_hypersensory_abilities"),
                ("unit_move_ended", "_on_unit_move_ended_loping_speed"),
                ("unit_move_started", "_on_unit_move_started_enemy_fall_back_end_normal_move"),
                ("unit_move_ended", "_on_unit_move_ended_enemy_fall_back_end_normal_move"),
                ("unit_move_ended", "_on_unit_move_ended_enemy_move_range_mortal_threshold"),
                ("unit_move_ended", "_on_unit_move_ended_floating_death"),
                ("unit_move_started", "_on_unit_move_started_spirit_mark"),
                ("unit_move_ended", "_on_unit_move_ended_spirit_mark"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_battleshock"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_crit_hit_threshold"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_disembark_wound_reroll"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_disembark_hit_reroll"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_disembark_psychic_hit_wound_bonus"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_disembark_ap_bonus"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_mortal_wounds_battleshock"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_monster_vehicle_mortal_threshold"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_wracking_agonies"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_snare"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_stormwracked"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_pinned"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_aflame"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_shocked"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_suppression"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_afflicted"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_no_cover"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_no_overwatch"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_ap_bonus"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_keyword_strength_bonus"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_keyword_hit_bonus"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_keyword_wound_bonus"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_keyword_wound_reroll"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_keyword_hit_reroll_ones"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_oath_of_moment_backup_promotion"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_storm_of_vengeance"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_tau_advanced_scouting"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_shoot_again"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_leadership_debuff"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_thousand_sons_psychic_hit_markers"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_tactical_acumen"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_daemonic_poisons"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_gift_of_chaos"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_spore_laced_shock_waves"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_thundershock"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_concussive_wave"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_harvester_of_souls"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_inflamed_reprisal"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_parasitic_infection"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_curse_of_the_walking_pox"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_repulsor_grid"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_stabilised_disembarkation"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_cold_fervour"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_prototype_weapon_system"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_blood_surge"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_repair_barge"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_inflamed_reprisal"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_cruel_amusement"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_master_of_magicks"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_technosorcerous_augmentations"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_cold_fervour"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_hand_of_asuryan"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_nova_charge"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_prototype_weapon_system"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_shieldbreaker"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_cat_unit"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_ammo_runt"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_ratling_battlemutt"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_sacrificial_dagger"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_sacrificial_blessing"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_twisted_sorceries"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_spore_laced_shock_waves"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_thundershock"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_concussive_wave"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_tremor_quake"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_harvester_of_souls"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_stabilised_disembarkation"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_atavistic_instigation"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_blood_surge"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_repair_barge"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_guns_blazing"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_guns_blazing"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_brazen_fury"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_brazen_fury"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_hypersensory_abilities"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_horde_move"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_horde_move"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_blistering_assault"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_blistering_assault"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_bestial_rage"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_bestial_rage"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_aggressive_leader_beast"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_aggressive_leader_beast"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_frenzy"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_integrated_tactics"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_orks_try_dat_button"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_orks_selected_to_shoot_utilities"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_selected_to_shoot_unit_named_ranged_bonus"),
                ("fight_targets_selected", "_on_fight_targets_selected_frenzy"),
                ("fight_targets_selected", "_on_fight_targets_selected_cold_fervour"),
                ("fight_targets_selected", "_on_fight_targets_selected_hysterical_frenzy"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_frenzy"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_cold_fervour"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_frenzy"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_post_fight_battleshock"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_post_fight_suppression"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_soul_trap"),
                ("fight_unit_selected", "_on_fight_unit_selected_daemonic_patrons"),
                ("fight_unit_selected", "_on_fight_unit_selected_plasmacyte"),
                ("fight_unit_selected", "_on_fight_unit_selected_biological_warfare"),
                ("fight_unit_selected", "_on_fight_unit_selected_deeds_of_heroism"),
                ("fight_unit_selected", "_on_fight_unit_selected_alchemicus_familiar"),
                ("fight_unit_selected", "_on_fight_unit_selected_target_keyword_melee_weapon_keyword"),
                ("fight_unit_selected", "_on_fight_unit_selected_charged_melee_weapon_keywords"),
                ("fight_unit_selected", "_on_fight_unit_selected_extremis_trigger_word"),
                ("fight_unit_selected", "_on_fight_unit_selected_sacrificial_dagger"),
                ("fight_unit_selected", "_on_fight_unit_selected_sacrificial_blessing"),
                ("fight_unit_selected", "_on_fight_unit_selected_twisted_sorceries"),
                ("fight_unit_selected", "_on_fight_unit_selected_enemy_melee_hit_penalty"),
                ("fight_unit_selected", "_on_fight_unit_selected_selected_to_fight_reroll_choice"),
                ("fight_unit_selected", "_on_fight_unit_selected_harbinger_of_death"),
                ("fight_unit_selected", "_on_fight_unit_selected_embodied_prophecy"),
                ("fight_unit_selected", "_on_fight_unit_selected_hypermorphic_fury"),
                ("fight_unit_selected", "_on_fight_unit_selected_pious_fervour"),
                ("fight_unit_selected", "_on_fight_unit_selected_orks_try_dat_button"),
                ("fight_targets_selected", "_on_fight_targets_selected_boon_of_death"),
                ("fight_targets_selected", "_on_fight_targets_selected_repair_barge"),
                ("phase_start", "_on_phase_start_target_tracking"),
                ("phase_start", "_on_phase_start_ds8_support_turret_cleanup"),
                ("phase_start", "_on_phase_start_command_phase_cp_rolls"),
                ("phase_start", "_on_phase_start_genestealer_cults_claimed_for_the_cult"),
                ("phase_start", "_on_phase_start_cult_infiltration"),
                ("phase_start", "_on_phase_start_orks_thievin_scavengers"),
                ("phase_start", "_on_phase_start_fiery_conviction"),
                ("phase_start", "_on_phase_start_master_of_shadows"),
                ("phase_start", "_on_phase_start_neuroloids_cleanup"),
                ("phase_start", "_on_phase_start_death_guard_detachments"),
                ("phase_start", "_on_phase_start_tyranids_detachments"),
                ("phase_start", "_on_phase_start_fight_phase_target_attack_bonus"),
                ("phase_start", "_on_phase_start_inflamed_infections"),
                ("phase_start", "_on_phase_start_data_spike"),
                ("phase_start", "_on_phase_start_paroxysm"),
                ("phase_start", "_on_phase_start_accelerator_mandible"),
                ("phase_start", "_on_phase_start_spirit_of_gork"),
                ("phase_start", "_on_phase_start_malign_sacrifice"),
                ("phase_start", "_on_phase_start_malice_made_manifest"),
                ("phase_start", "_on_phase_start_to_slay_the_warmaster"),
                ("phase_start", "_on_phase_start_dark_ritual"),
                ("phase_start", "_on_phase_start_seed_spore_mines"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_tracking"),
                ("charge_declared", "_on_charge_declared_tracking"),
                ("charge_declared", "_on_charge_declared_shock_and_awe"),
                ("phase_start", "_on_phase_start_post_shoot_leadership_debuff_cleanup"),
                ("phase_start", "_on_phase_start_post_shoot_duration_cleanup"),
                ("phase_start", "_on_phase_start_shooting_phase_visible_battleshock"),
                ("phase_start", "_on_phase_start_shooting_phase_visible_hit_bonus"),
                ("phase_start", "_on_phase_start_shooting_phase_keyword_hit_reroll_ones"),
                ("phase_start", "_on_phase_start_forgefather"),
                ("phase_start", "_on_phase_start_shooting_phase_blight_bombardment"),
                ("phase_start", "_on_phase_start_shooting_phase_eater_plague"),
                ("phase_start", "_on_phase_start_death_hex"),
                ("phase_start", "_on_phase_start_astra_militarum_psychic_barrier"),
                ("phase_start", "_on_phase_start_opponent_shooting_phase_disrupt"),
                ("phase_start", "_on_phase_start_opponent_movement_phase_gravitic_pulse"),
                ("phase_start", "_on_phase_start_wracked_with_agonies_cleanup"),
                ("phase_start", "_on_phase_start_snared_cleanup"),
                ("phase_start", "_on_phase_start_stormwracked_cleanup"),
                ("phase_start", "_on_phase_start_owner_command_phase_attack_hit_penalty_cleanup"),
                ("phase_start", "_on_phase_start_post_shoot_suppression_cleanup"),
                ("phase_start", "_on_phase_start_post_shoot_afflicted_cleanup"),
                ("phase_start", "_on_phase_start_pinned_cleanup"),
                ("phase_start", "_on_phase_start_gravitic_pulse_cleanup"),
                ("phase_start", "_on_phase_start_misfortune_cleanup"),
                ("phase_start", "_on_phase_start_nurgles_rot_cleanup"),
                ("phase_start", "_on_phase_start_death_hex_cleanup"),
                ("phase_start", "_on_phase_start_movement_phase_visible_wound_bonus_cleanup"),
                ("phase_start", "_on_phase_start_movement_phase_visible_hit_bonus_cleanup"),
                ("phase_start", "_on_phase_start_genestealer_cults_final_day_cleanup"),
                ("phase_start", "_on_phase_start_spirit_mark_cleanup"),
                ("phase_start", "_on_phase_start_engagement_battleshock"),
                ("phase_start", "_on_phase_start_fight_phase_select_engagement_battleshock"),
                ("phase_start", "_on_phase_start_fight_phase_select_engagement_mortal_table"),
                ("phase_start", "_on_phase_start_fight_phase_select_enemy_melee_hit_penalty"),
                ("phase_start", "_on_phase_start_tocsin_of_misery"),
                ("phase_start", "_on_phase_start_imperial_agents_psychic_veil_cleanup"),
                ("phase_start", "_on_phase_start_soulless_horror"),
                ("phase_start", "_on_phase_start_oath_of_rynn"),
                ("phase_start", "_on_phase_start_neuroloids"),
                ("phase_start", "_on_phase_start_command_phase_enemy_no_cover"),
                ("phase_start", "_on_phase_start_imperial_agents_psychic_veil"),
                ("phase_start", "_on_phase_start_harbinger_of_despair_battleshock"),
                ("phase_start", "_on_phase_start_blinding_spray"),
                ("phase_start", "_on_phase_start_empowered_by_death"),
                ("phase_start", "_on_phase_start_herald_of_ynnead"),
                ("phase_start", "_on_phase_start_hallowed_ground"),
                ("phase_start", "_on_phase_start_prescient_redeployment"),
                ("phase_start", "_on_phase_start_dance_of_death"),
                ("phase_start", "_on_phase_start_spawn_termagants"),
                ("phase_start", "_on_phase_start_tears_of_isha"),
                ("phase_start", "_on_phase_start_word_of_phoenix"),
                ("phase_end", "_on_phase_end_fight_phase_mortal_wounds"),
                ("phase_end", "_on_phase_end_aflame_cleanup"),
                ("phase_end", "_on_phase_end_shocked_cleanup"),
                ("phase_end", "_on_phase_end_transport_end_of_fight_embark"),
                ("phase_end", "_on_phase_end_transport_opponent_movement_embark"),
                ("phase_end", "_on_phase_end_resurrection_orb"),
                ("phase_end", "_on_phase_end_sweeping_advance"),
                ("phase_end", "_on_phase_end_raid_and_run"),
                ("phase_end", "_on_phase_end_charge_phase_bodyguard_loss"),
                ("phase_end", "_on_phase_end_the_great_wolf_watches"),
                ("phase_end", "_on_phase_end_miraculous_saviour"),
                ("phase_end", "_on_phase_end_opponent_fight_phase_strategic_reserves"),
                ("phase_end", "_on_phase_end_fight_phase_destroyed_strategic_reserves"),
                ("phase_end", "_on_phase_end_wrath_of_the_first_khan"),
                ("phase_end", "_on_phase_end_plough_through_the_enemy"),
                ("phase_end", "_on_phase_end_soul_eater"),
                ("phase_end", "_on_phase_end_transport_reactive_disembark"),
                ("phase_end", "_on_phase_end_leadership_cp_gain"),
                ("phase_end", "_on_phase_end_command_phase_regain_wounds"),
                ("phase_end", "_on_phase_end_command_phase_mortal_table"),
                ("phase_end", "_on_phase_end_daemonic_patrons"),
                ("phase_end", "_on_phase_end_setup_reactive_shoot_or_charge"),
                ("phase_end", "_on_phase_end_hyperspace_hunters"),
                ("phase_end", "_on_phase_end_movement_phase_visible_wound_bonus"),
                ("phase_end", "_on_phase_end_movement_phase_visible_hit_bonus"),
                ("phase_end", "_on_phase_end_movement_phase_pinned"),
                ("phase_end", "_on_phase_end_misfortune"),
                ("phase_end", "_on_phase_end_nurgles_rot"),
                ("phase_end", "_on_phase_end_seed_the_garden_of_nurgle"),
                ("phase_end", "_on_phase_end_shooting_phase_disrupt_cleanup"),
                ("phase_end", "_on_phase_end_aeldari_strength_from_death_lethal_intent"),
                ("phase_end", "_on_phase_end_movement_phase_mortal_table"),
                ("phase_end", "_on_phase_end_orks_da_jump"),
                ("phase_end", "_on_phase_end_ds8_support_turret"),
                ("phase_end", "_on_phase_end_flickerjump_mortal_wounds"),
                ("phase_end", "_on_phase_end_genestealer_cults_final_day_psionic_parasitism"),
                ("phase_end", "_on_phase_end_lost_brethren_vengeful_onslaught"),
                ("phase_end", "_on_phase_end_post_fight_suppression_cleanup"),
                ("phase_end", "_on_phase_end_necrons_atomic_energy_manipulator"),
                ("fight_targets_selected", "_on_fight_targets_selected_tracking"),
                ("phase_end", "_on_phase_end_cleanup"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_gift_of_chaos"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_curse_of_the_walking_pox"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_death_guard_final_ingredient"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_lethal_ichor"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_allocated_melee_mortal_retaliation"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_repair_barge"),
                ("battle_round_started", "_on_battle_round_started_start_of_battle_keyword_rerolls"),
                ("battle_round_started", "_on_battle_round_started_enhancement_start_of_battle_rolls"),
                ("phase_start", "_on_phase_start_optional_abilities"),
                ("phase_start", "_on_phase_start_custodes_enhancements"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="stratagems",
            register_fn=_register_stratagems,
            unregister_fn=_unregister_stratagems,
        )
    )

    providers.append(
        RuleProvider(
            name="lifecycle",
            subscriptions=[
                ("unit_set_up", "_on_unit_set_up_lifecycle"),
                ("unit_destroyed", "_on_unit_destroyed_lifecycle"),
                ("unit_state_changed", "_on_unit_state_changed_lifecycle"),
                ("unit_reserve_status_changed", "_on_unit_state_changed_lifecycle"),
                ("unit_embarked", "_on_unit_state_changed_lifecycle"),
                ("unit_disembarked", "_on_unit_state_changed_lifecycle"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="aeldari",
            predicate=lambda ctxs, _g: any_manager(ctxs, "battle_focus", ("_army_has_battle_focus",)),
            subscriptions=[
                ("unit_move_started", "_on_unit_move_started_battle_focus"),
                ("unit_move_ended", "_on_unit_move_ended_battle_focus"),
                ("fight_unit_selected", "_on_fight_unit_selected_battle_focus"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_path_of_warrior"),
                ("fight_unit_selected", "_on_fight_unit_selected_path_of_warrior"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_battle_focus"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_aspect_shrine"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_aspect_shrine"),
                ("phase_start", "_on_phase_start_aeldari_enhancements"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="chaos_space_marines",
            predicate=lambda ctxs, _g: any_faction(ctxs, "CSM"),
            subscriptions=[
                ("phase_start", "_on_phase_start_spirit_thief"),
                ("phase_start", "_on_phase_start_corrupt_machine_spirits"),
                ("phase_start", "_on_phase_start_herald_of_the_apocalypse"),
                ("phase_start", "_on_phase_start_master_of_mechanisms_cleanup"),
                ("phase_start", "_on_phase_start_master_of_mechanisms"),
                ("phase_end", "_on_phase_end_enrage_machine_spirits"),
                ("unit_move_started", "_on_unit_move_started_detachment_rules"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_dark_pacts"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_daemonic_ordnance"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_warp_rift_firepower"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_reorder_reality"),
                ("fight_unit_selected", "_on_fight_unit_selected_dark_pacts"),
                ("charge_declared", "_on_charge_declared_detachment_rules"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="grey_knights",
            predicate=lambda ctxs, _g: any_faction(ctxs, "GK"),
            subscriptions=[
                ("phase_start", "_on_phase_start_master_of_mechanisms_cleanup"),
                ("phase_start", "_on_phase_start_master_of_mechanisms"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_grey_knights_sigil_of_exigence"),
                ("fight_unit_selected", "_on_fight_unit_selected_hammer_aflame"),
                ("fight_unit_selected", "_on_fight_unit_selected_channelled_force"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="adeptus_mechanicus",
            predicate=lambda ctxs, _g: any_faction(ctxs, "ADM"),
            subscriptions=[
                ("phase_start", "_on_phase_start_master_of_mechanisms_cleanup"),
                ("phase_start", "_on_phase_start_master_of_mechanisms"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="necrons",
            predicate=lambda ctxs, _g: any_faction(ctxs, "NEC"),
            subscriptions=[
                ("phase_end", "_on_phase_start_master_of_mechanisms"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="orks",
            predicate=lambda ctxs, _g: any_faction(ctxs, "ORK"),
            subscriptions=[
                ("phase_start", "_on_phase_start_master_of_mechanisms_cleanup"),
                ("phase_end", "_on_phase_start_master_of_mechanisms"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="chaos_knights",
            predicate=lambda ctxs, _g: any_faction(ctxs, "QT"),
            subscriptions=[
                ("shooting_targets_selected", "_on_shooting_targets_selected_iconoclast_dark_sacrifice"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_malefic_surge"),
                ("fight_unit_selected", "_on_fight_unit_selected_iconoclast_dark_sacrifice"),
                ("fight_unit_selected", "_on_fight_unit_selected_malefic_surge"),
                ("fight_targets_selected", "_on_fight_targets_selected_malefic_surge"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="space_marines",
            predicate=lambda ctxs, _g: any_manager(
                ctxs,
                "space_marines_detachments",
                (
                    "is_1st_company_task_force",
                    "is_rage_cursed_onslaught",
                    "is_bastion_task_force",
                    "is_liberator_assault_group",
                    "is_hammer_of_avernii",
                    "is_saga_of_the_bold",
                    "is_saga_of_the_beastslayer",
                    "is_saga_of_the_hunter",
                    "is_saga_of_the_great_wolf",
                ),
            ),
            subscriptions=[
                ("fight_unit_selected", "_on_fight_unit_selected_maddened_ferocity"),
                ("fight_unit_selected", "_on_fight_unit_selected_red_thirst"),
                ("fight_unit_selected", "_on_fight_unit_selected_vehement_aggression"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_iron_resolve"),
                ("fight_targets_selected", "_on_fight_targets_selected_iron_resolve"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_heroes_all"),
                ("fight_unit_selected", "_on_fight_unit_selected_heroes_all"),
                ("fight_unit_selected", "_on_fight_unit_selected_master_of_wolves_ferocious_strike"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_interlocking_tactics"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_legendary_slayers"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_heroes_all"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_interlocking_tactics"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_legendary_slayers"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_pack_quarry"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_interlocking_tactics"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_legendary_slayers"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_pack_quarry"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_heroes_all"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_oath_of_moment_backup_promotion"),
                ("unit_destroyed", "_on_unit_destroyed_recalculating"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="imperial_knights",
            predicate=lambda ctxs, _g: any_manager(ctxs, "code_chivalric", ("_army_has_code_chivalric",))
            or any_manager(ctxs, "bondsman", ("_army_has_bondsman",)),
            subscriptions=[
                ("shooting_targets_selected", "_on_shooting_targets_selected_code_chivalric"),
                ("fight_unit_selected", "_on_fight_unit_selected_code_chivalric"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_code_chivalric"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_code_chivalric"),
                ("model_destroyed", "_on_model_destroyed_code_chivalric"),
                ("unit_destroyed", "_on_unit_destroyed_code_chivalric"),
                ("phase_start", "_on_phase_start_imperial_knights_enhancements"),
                ("phase_end", "_on_phase_end_imperial_knights_enhancements"),
                ("phase_start", "_on_phase_start_bondsman"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_bondsman"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_bondsman"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="adeptus_custodes",
            predicate=lambda ctxs, _g: any_faction(ctxs, "AC"),
            subscriptions=[
                ("fight_unit_selected", "_on_fight_unit_selected_martial_katah"),
                ("battle_round_started", "_on_battle_round_started_adeptus_custodes"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="emperors_children",
            predicate=lambda ctxs, _g: any_manager(
                ctxs,
                "emperors_children_detachments",
                (
                    "is_mercurial_host",
                    "is_peerless_bladesmen",
                    "is_rapid_evisceration",
                    "is_carnival_of_excess",
                    "is_coterie_of_conceited",
                    "is_slaaneshs_chosen",
                    "is_court_of_the_phoenician",
                ),
            ),
            subscriptions=[
                ("battle_round_started", "_on_battle_round_started_emperors_children"),
                ("unit_destroyed", "_on_unit_destroyed_emperors_children"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_emperors_children"),
                ("fight_targets_selected", "_on_fight_targets_selected_emperors_children"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_emperors_children"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_emperors_children"),
                ("fight_unit_selected", "_on_fight_unit_selected_emperors_children"),
                ("phase_start", "_on_phase_start_emperors_children_enhancements"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="drukhari",
            predicate=lambda ctxs, _g: any_manager(
                ctxs,
                "power_from_pain",
                ("_army_has_power_from_pain",),
            ),
            subscriptions=[
                ("battle_round_started", "_on_battle_round_started_drukhari"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_power_from_pain"),
                ("fight_unit_selected", "_on_fight_unit_selected_power_from_pain"),
                ("fight_unit_selected", "_on_fight_unit_selected_eye_of_spite"),
                ("fight_targets_selected", "_on_fight_targets_selected_drukhari_detachments"),
                ("unit_move_started", "_on_unit_move_started_power_from_pain"),
                ("charge_declared", "_on_charge_declared_power_from_pain"),
                ("phase_start", "_on_phase_start_power_from_pain"),
                ("phase_end", "_on_phase_end_power_from_pain"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_power_from_pain"),
                ("fight_sequence_complete", "_on_fight_sequence_complete_power_from_pain"),
                ("unit_destroyed", "_on_unit_destroyed_power_from_pain"),
                ("battle_shock_test_resolved", "_on_battle_shock_test_resolved_power_from_pain"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="leagues_of_votann",
            predicate=lambda ctxs, _g: any_manager(
                ctxs,
                "leagues_of_votann_detachments",
                (
                    "is_brandfast_oathband",
                    "is_delve_assault_shift",
                    "is_needgaard_oathband",
                    "is_hearthband",
                    "is_hearthfyre_arsenal",
                    "is_mercenary_oathband",
                    "is_persecution_prospect",
                ),
            ),
            subscriptions=[
                ("unit_destroyed", "_on_unit_destroyed_martial_leverage"),
                ("unit_destroyed", "_on_unit_destroyed_seized_opportunity"),
                ("unit_destroyed", "_on_unit_destroyed_mercenary_prospector"),
                ("phase_start", "_on_phase_start_tactical_alchemy"),
                ("phase_start", "_on_phase_start_asset_manipulator"),
                ("phase_end", "_on_phase_end_forgewrought_expertise"),
                ("phase_end", "_on_phase_end_ruthless_reinvestment"),
                ("phase_start", "_on_phase_start_persecution_prospect_assailed_cleanup"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_etacarn_sb9_targeting_implant"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_trivarg_cyber_implant"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_oathbound_speculator"),
                ("fight_unit_selected", "_on_fight_unit_selected_etacarn_sb9_targeting_implant"),
                ("fight_unit_selected", "_on_fight_unit_selected_oathbound_speculator"),
                ("fight_unit_selected", "_on_fight_unit_selected_piledriver"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_iron_ambassador"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_bastion_shield"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_geomantic_hunters"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_resource_transmutation"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_optimal_application"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_persecution_prospect"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_quake_multigenerator"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_graviton_vault"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_resource_transmutation"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_persecution_prospect"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_unhinged_vengeance"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_unhinged_vengeance"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_graviton_vault"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="world_eaters",
            predicate=lambda ctxs, _g: any_faction(ctxs, "WE"),
            subscriptions=[
                ("unit_destroyed", "_on_unit_destroyed_bloodshed_points"),
                ("unit_destroyed", "_on_unit_destroyed_blood_tithe"),
                ("phase_start", "_on_phase_start_world_eaters_enhancements"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="chaos_daemons_enhancements",
            predicate=lambda ctxs, _g: any_faction(ctxs, "CD"),
            subscriptions=[
                ("phase_start", "_on_phase_start_chaos_daemons_enhancements"),
                ("phase_end", "_on_phase_end_chaos_daemons_enhancements"),
                ("phase_end", "_on_phase_end_movement_phase_symphony_of_pain"),
                ("battle_shock_test_resolved", "_on_battle_shock_test_resolved_maggot_maws"),
                ("fight_unit_selected", "_on_fight_unit_selected_furys_cage"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="thousand_sons",
            predicate=lambda ctxs, _g: any_manager(ctxs, "cabal_of_sorcerers", ("_army_has_cabal",)),
            subscriptions=[
                ("shooting_targets_selected", "_on_shooting_targets_selected_thousand_sons_warpfire_infusion"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_thousand_sons_warpmeld_sacrifice"),
                ("fight_unit_selected", "_on_fight_unit_selected_thousand_sons_warpfire_infusion"),
                ("fight_unit_selected", "_on_fight_unit_selected_thousand_sons_warpmeld_sacrifice"),
                ("fight_targets_selected", "_on_fight_targets_selected_thousand_sons_warpmeld_sacrifice"),
                ("phase_start", "_on_phase_start_thousand_sons_flow_of_magic"),
                ("phase_start", "_on_phase_start_thousand_sons_enhancements"),
                ("phase_start", "_on_phase_start_cabal_of_sorcerers"),
                ("phase_end", "_on_phase_end_thousand_sons_warpmeld_sacrifice"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="tau",
            predicate=lambda ctxs, _g: any_manager(ctxs, "for_the_greater_good", ("_army_has_ftgg",)),
            subscriptions=[
                ("phase_start", "_on_phase_start_for_the_greater_good"),
                ("phase_end", "_on_phase_end_for_the_greater_good"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="astra_militarum",
            predicate=lambda ctxs, _g: any_manager(ctxs, "voice_of_command", ("_army_has_voice",)),
            subscriptions=[
                ("phase_start", "_on_phase_start_voice_of_command"),
                ("phase_end", "_on_phase_end_voice_of_command"),
                ("unit_set_up", "_on_unit_set_up_voice_of_command_reactive_command"),
                ("battle_shock_test_resolved", "_on_battle_shock_test_resolved_voice_of_command"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="grey_knights",
            predicate=lambda ctxs, _g: any_manager(ctxs, "gate_of_infinity", ("_army_has_gate",)),
            subscriptions=[
                ("phase_end", "_on_phase_end_gate_of_infinity"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="chaos_daemons",
            predicate=lambda ctxs, _g: any_manager(ctxs, "shadow_form"),
            subscriptions=[
                ("battle_shock_test_resolved", "_on_battle_shock_test_resolved_shadow_form"),
                ("phase_end", "_on_phase_end_grotesque_regeneration"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="chaos_knights",
            predicate=lambda ctxs, _g: any_manager(ctxs, "harbingers_of_dread", ("_army_has_harbingers",)),
            subscriptions=[
                ("battle_shock_test_resolved", "_on_battle_shock_test_resolved_harbingers"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="genestealer_cults",
            predicate=lambda ctxs, _g: any_manager(ctxs, "cult_ambush", ("_army_has_rule",)),
            subscriptions=[
                ("unit_destroyed", "_on_unit_destroyed_cult_ambush"),
                ("unit_move_ended", "_on_unit_move_ended_cult_ambush"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="adepta_sororitas",
            predicate=lambda ctxs, _g: any_manager(ctxs, "acts_of_faith", ("_army_has_rule",)),
            subscriptions=[
                ("unit_destroyed", "_on_unit_destroyed_acts_of_faith"),
                ("model_destroyed_before_removal", "_on_model_destroyed_acts_of_faith"),
                ("fight_unit_selected", "_on_fight_unit_selected_acts_of_faith"),
                ("battle_shock_test_resolved", "_on_battle_shock_test_resolved_acts_of_faith"),
                ("phase_end", "_on_phase_end_acts_of_faith_enhancements"),
            ],
        )
    )

    return providers
