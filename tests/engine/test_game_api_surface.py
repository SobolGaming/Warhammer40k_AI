from pathlib import Path

from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.game_mixins.phase_handlers_mixin import GamePhaseHandlersMixin
from warhammer40k_ai.engine.game_mixins.reactive_decisions_mixin import GameReactiveDecisionsMixin
from warhammer40k_ai.engine.game_mixins.missions_scoring_actions_mixin import (
    GameMissionsScoringActionsMixin,
)
from warhammer40k_ai.engine.game_mixins.setup_deployment_reserves_mixin import (
    GameSetupDeploymentReservesMixin,
)
from warhammer40k_ai.engine.game_mixins.shooting_fight_handlers_mixin import (
    GameShootingFightHandlersMixin,
)


EXPECTED_PUBLIC_GAME_CALLABLES = {
    "add_command",
    "add_decision_controller",
    "add_objective",
    "add_player",
    "advance_deployment_turn",
    "advance_setup_phase",
    "apply_command",
    "apply_reserves_decisions",
    "apply_transport_assignments",
    "attempt_charge",
    "auto_deploy_unit",
    "award_vp",
    "begin_reinforcements_step",
    "can_place_unit_arriving_from_reserves",
    "can_player_deploy_unit",
    "can_score_objectives",
    "can_start_burn_objective",
    "can_start_cleanse",
    "can_start_establish_locus",
    "can_start_move_hazard",
    "can_start_sabotage",
    "can_start_terraform",
    "can_start_the_ritual",
    "clear_deployment_actions",
    "complete_deployment_phase",
    "continue_charge_after_emergency_combat_embarkation",
    "declare_charge",
    "end_of_battle_round_scoring",
    "end_of_turn_scoring",
    "end_reinforcements_step",
    "enqueue_command",
    "execute_create_battlefield_phase",
    "execute_current_setup_phase",
    "execute_declare_battle_formations_phase",
    "execute_deploy_armies_phase",
    "execute_determine_attacker_defender_phase",
    "execute_determine_first_turn_order_phase",
    "execute_muster_armies_phase",
    "execute_redeploy_units_phase",
    "execute_resolve_prebattle_rules_phase",
    "execute_select_mission_objectives_phase",
    "finalize_battle_scoring",
    "find_valid_reserves_position",
    "get_attacker",
    "get_battle_round",
    "get_battlefield_size",
    "get_boundary_repulsors",
    "get_charge_roll_modifiers",
    "get_current_deployment_player",
    "get_current_player",
    "get_current_setup_phase",
    "get_defender",
    "get_deployable_units",
    "get_distance_between_units",
    "get_distance_to_battlefield_edge",
    "get_distance_to_enemy_deployment_zone",
    "get_distance_to_enemy_models",
    "get_eligible_charging_units",
    "get_eligible_fighting_units",
    "get_enemy_units",
    "get_fight_first_units",
    "get_fight_phase_units_by_stage",
    "get_first_turn_player_index",
    "get_loser",
    "get_max_charge_distance",
    "get_opponent",
    "get_or_create_tier1_plan",
    "get_or_create_tier2_task_bundle",
    "get_pregame_flow_state",
    "get_remaining_combatant_units",
    "get_ruleset_context",
    "get_state",
    "get_units_in_reserves",
    "get_units_that_can_arrive_from_reserves",
    "get_units_that_must_arrive_from_reserves",
    "get_waiting_player_id",
    "get_waiting_player_ids",
    "get_winner",
    "handle_reserves_arrival_phase",
    "in_command_context",
    "install_decision_providers",
    "is_charge_phase",
    "is_charge_phase_complete",
    "is_command_phase",
    "is_deployment_phase",
    "is_fight_phase",
    "is_fight_phase_complete",
    "is_game_over",
    "is_in_setup_phase",
    "is_model_wholly_in_deployment_zone",
    "is_movement_phase",
    "is_position_in_deployment_zone",
    "is_position_in_enemy_deployment_zone",
    "is_position_wholly_in_deployment_zone",
    "is_shooting_phase",
    "is_valid_deployment_position",
    "is_valid_single_model_deployment",
    "is_valid_strategic_reserves_edge",
    "load_snapshot",
    "next_command",
    "next_phase",
    "on_select_unit_resolved",
    "process_command_queue",
    "process_player_reserves_arrivals",
    "queue_bodyguard_loss",
    "queue_phoenix_gem_return",
    "rebuild_entity_registry",
    "record_deployment_action",
    "record_model_destroyed",
    "record_unit_destroyed",
    "refresh_rule_subscribers",
    "request_decision",
    "request_dice_roll",
    "request_mission_selection",
    "resolve_bodyguard_loss_immediately",
    "resolve_charge_end_mortal_wounds",
    "resolve_decision",
    "resolve_emergency_combat_embarkation",
    "resolve_end_of_fight_embark",
    "resolve_fight_phase_end_mortal_wounds",
    "resolve_floating_death_mortal_wounds",
    "resolve_frenzy_melee_attacks",
    "resolve_grenade_pack_flyover",
    "resolve_move_over_mortal_wounds",
    "resolve_stasis_bomb",
    "roll_aggressive_leader_beast_distance",
    "roll_bestial_rage_distance",
    "roll_blistering_assault_distance",
    "roll_blood_surge_distance",
    "roll_brazen_fury_distance",
    "roll_horde_move_distance",
    "roll_loping_speed_distance",
    "roll_unhinged_vengeance_distance",
    "save_snapshot",
    "set_attacker_defender",
    "set_map",
    "set_selected_mission",
    "set_waiting_for_deployment_input",
    "start_burn_objective_action",
    "start_cleanse_action",
    "start_command_phase",
    "start_establish_locus_action",
    "start_move_hazard_action",
    "start_sabotage_action",
    "start_terraform_action",
    "start_the_ritual_action",
    "sync_deployment_zones_to_attacker_defender",
}

REQUIRED_PRIVATE_GAME_HOOKS = {
    "_apply_charge_modifiers",
    "_collect_charge_modifiers",
    "_find_charge_destination",
    "_finalize_successful_charge_move",
    "_get_charge_roll_spec",
    "_record_engaged_enemies_at_turn_start",
}


def test_game_public_api_snapshot() -> None:
    public = {
        name
        for name in dir(Game)
        if not name.startswith("_") and callable(getattr(Game, name))
    }

    assert EXPECTED_PUBLIC_GAME_CALLABLES <= public


def test_game_private_compatibility_hooks() -> None:
    missing = {
        name
        for name in REQUIRED_PRIVATE_GAME_HOOKS
        if not callable(getattr(Game, name, None))
    }

    assert not missing


def test_game_facade_is_service_backed() -> None:
    legacy_mixins = {
        GameMissionsScoringActionsMixin,
        GamePhaseHandlersMixin,
        GameReactiveDecisionsMixin,
        GameSetupDeploymentReservesMixin,
        GameShootingFightHandlersMixin,
    }
    assert not (legacy_mixins & set(Game.__mro__))
    assert callable(getattr(Game, "_ensure_scoring_service", None))
    assert callable(getattr(Game, "_ensure_setup_deployment_service", None))
    assert callable(getattr(Game, "_ensure_phase_handlers_service", None))
    assert callable(getattr(Game, "_ensure_reactive_rules_service", None))
    assert callable(getattr(Game, "_ensure_shooting_service", None))


def test_game_facade_line_count_budget() -> None:
    game_path = Path(__file__).resolve().parents[2] / "src/warhammer40k_ai/engine/game.py"
    assert len(game_path.read_text().splitlines()) <= 1500
