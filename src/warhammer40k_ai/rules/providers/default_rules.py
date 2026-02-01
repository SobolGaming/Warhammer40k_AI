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
                ("model_destroyed", "_on_model_destroyed_phase_kill_tracking"),
                ("unit_destroyed", "_on_unit_destroyed_rules"),
                ("unit_destroyed", "_on_unit_destroyed_phase_kill_tracking"),
                ("unit_destroyed", "_on_unit_destroyed_transport_rules"),
                ("unit_destroyed", "_on_unit_destroyed_friendly_unit_destroyed_reposition"),
                ("unit_move_ended", "_on_unit_move_ended_detachment_rules"),
                ("unit_move_ended", "_on_unit_move_ended_charge_mortal_wounds"),
                ("unit_move_ended", "_on_unit_move_ended_move_over_mortal_wounds"),
                ("unit_move_ended", "_on_unit_move_ended_snared_mortal_wounds"),
                ("unit_move_ended", "_on_unit_move_ended_transport_reactive_disembark"),
                ("unit_set_up", "_on_unit_set_up_transport_reactive_disembark"),
                ("unit_set_up", "_on_unit_set_up_cry_of_the_wind"),
                ("unit_set_up", "_on_unit_set_up_setup_reactive_shoot_or_charge"),
                ("unit_disembarked", "_on_unit_disembarked_setup_reactive_shoot_or_charge"),
                ("unit_move_ended", "_on_unit_move_ended_loping_speed"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_battleshock"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_mortal_wounds_battleshock"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_wracking_agonies"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_snare"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_suppression"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_no_cover"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_ap_bonus"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_post_shoot_leadership_debuff"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_daemonic_poisons"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_blood_surge"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_cruel_amusement"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_blood_surge"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_brazen_fury"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_brazen_fury"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_frenzy"),
                ("fight_targets_selected", "_on_fight_targets_selected_frenzy"),
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_frenzy"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_frenzy"),
                ("fight_unit_selected", "_on_fight_unit_selected_daemonic_patrons"),
                ("phase_start", "_on_phase_start_target_tracking"),
                ("shooting_targets_selected", "_on_shooting_targets_selected_tracking"),
                ("charge_declared", "_on_charge_declared_tracking"),
                ("phase_start", "_on_phase_start_post_shoot_leadership_debuff_cleanup"),
                ("phase_start", "_on_phase_start_wracked_with_agonies_cleanup"),
                ("phase_start", "_on_phase_start_snared_cleanup"),
                ("phase_start", "_on_phase_start_movement_phase_visible_wound_bonus_cleanup"),
                ("phase_start", "_on_phase_start_engagement_battleshock"),
                ("phase_start", "_on_phase_start_hallowed_ground"),
                ("phase_start", "_on_phase_start_dance_of_death"),
                ("phase_end", "_on_phase_end_fight_phase_mortal_wounds"),
                ("phase_end", "_on_phase_end_charge_phase_bodyguard_loss"),
                ("phase_end", "_on_phase_end_leadership_cp_gain"),
                ("phase_end", "_on_phase_end_daemonic_patrons"),
                ("phase_end", "_on_phase_end_setup_reactive_shoot_or_charge"),
                ("phase_end", "_on_phase_end_movement_phase_visible_wound_bonus"),
                ("phase_end", "_on_phase_end_flickerjump_mortal_wounds"),
                ("fight_targets_selected", "_on_fight_targets_selected_tracking"),
                ("phase_end", "_on_phase_end_cleanup"),
                ("battle_round_started", "_on_battle_round_started_start_of_battle_keyword_rerolls"),
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
                ("shooting_targets_selected", "_on_shooting_targets_selected_dark_pacts"),
                ("fight_unit_selected", "_on_fight_unit_selected_dark_pacts"),
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="space_marines",
            predicate=lambda ctxs, _g: any_manager(
                ctxs,
                "space_marines_detachments",
                ("is_rage_cursed_onslaught",),
            ),
            subscriptions=[
                ("fight_unit_selected", "_on_fight_unit_selected_maddened_ferocity"),
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
                ("unit_shooting_resolved", "_on_unit_shooting_resolved_emperors_children"),
                ("fight_attacks_resolved", "_on_fight_attacks_resolved_emperors_children"),
                ("fight_unit_selected", "_on_fight_unit_selected_emperors_children"),
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
                ("shooting_targets_selected", "_on_shooting_targets_selected_power_from_pain"),
                ("fight_unit_selected", "_on_fight_unit_selected_power_from_pain"),
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
                ("is_needgaard_oathband",),
            ),
            subscriptions=[
                ("unit_destroyed", "_on_unit_destroyed_martial_leverage"),
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
            ],
        )
    )

    providers.append(
        RuleProvider(
            name="thousand_sons",
            predicate=lambda ctxs, _g: any_manager(ctxs, "cabal_of_sorcerers", ("_army_has_cabal",)),
            subscriptions=[
                ("phase_start", "_on_phase_start_cabal_of_sorcerers"),
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
            ],
        )
    )

    return providers
