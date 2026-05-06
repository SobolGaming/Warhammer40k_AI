from __future__ import annotations

from typing import TYPE_CHECKING

from ..utility.calcs import clear_enemy_model_cache
from ..utility.constants import TOTAL_ROUNDS
from .phase import BattleRoundPhases
import logging
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .game import Game


def next_phase(game: "Game") -> None:
    """Advance to the next phase."""
    # Phase-end system actions that should occur before we publish phase_end.
    # NOTE: Reinforcements (arriving from reserves) occur at the end of the Movement phase.
    try:
        if getattr(game.phase, "name", None) == "MOVEMENT_PHASE":
            queue = getattr(game, "decision_queue", None)
            pending_requests = list(queue.list() or []) if queue is not None and hasattr(queue, "list") else []
            if bool(getattr(game, "reinforcements_step_active", False)):
                if pending_requests:
                    return
                queue_mandatory = getattr(game, "_queue_mandatory_reinforcements_selection_if_needed", None)
                if callable(queue_mandatory):
                    queued = queue_mandatory(player=game.get_current_player())
                    pending_after_mandatory = (
                        list(queue.list() or []) if queue is not None and hasattr(queue, "list") else []
                    )
                    if queued is not None or pending_after_mandatory:
                        return
                game.end_reinforcements_step()
            else:
                game.handle_reserves_arrival_phase()
                pending_after = list(queue.list() or []) if queue is not None and hasattr(queue, "list") else []
                if pending_after:
                    return
                if bool(getattr(game, "reinforcements_step_active", False)):
                    queue_mandatory = getattr(game, "_queue_mandatory_reinforcements_selection_if_needed", None)
                    if callable(queue_mandatory):
                        queued = queue_mandatory(player=game.get_current_player())
                        pending_after_mandatory = (
                            list(queue.list() or []) if queue is not None and hasattr(queue, "list") else []
                        )
                        if queued is not None or pending_after_mandatory:
                            return
                    game.end_reinforcements_step()
    except Exception:
        pass
    try:
        end_reinforcements_step = getattr(game, "end_reinforcements_step", None)
        if callable(end_reinforcements_step) and bool(getattr(game, "reinforcements_step_active", False)):
            end_reinforcements_step()
    except Exception:
        pass

    # Publish end of current phase before advancing
    try:
        game.event_system.publish("phase_end", player=game.get_current_player(), phase=game.phase)
    except Exception:
        pass
    current_phase_value = game.phase.value
    next_phase_value = (current_phase_value + 1) % len(BattleRoundPhases)
    game.phase = BattleRoundPhases(next_phase_value)
    try:
        if hasattr(game.map, "bump_state_generation"):
            game.map.bump_state_generation(f"phase_changed:{getattr(game.phase, 'name', game.phase)}")
    except (AttributeError, TypeError):
        logger.debug("Unable to bump map state generation for phase change.", exc_info=True)
    final_battle_round_complete = False
    if next_phase_value == 0:
        players = list(getattr(game, "players", []) or [])
        if players:
            next_player_index = (int(getattr(game, "current_player_index", 0) or 0) + 1) % len(players)
            starting_index = getattr(game, "battle_round_starting_player_index", None)
            final_battle_round_complete = (
                starting_index is not None
                and next_player_index == int(starting_index)
                and int(getattr(game, "turn", 0) or 0) >= int(TOTAL_ROUNDS)
            )
    if next_phase_value != 0:
        try:
            refresh_csm_fn = getattr(game, "_refresh_csm_tyrannical_motivation_phase_state", None)
            if callable(refresh_csm_fn):
                refresh_csm_fn()
        except Exception:
            pass
    # Publish phase start for stratagem triggers
    if not final_battle_round_complete:
        try:
            game.event_system.publish("phase_start", player=game.get_current_player(), phase=game.phase)
        except Exception:
            pass
        try:
            if getattr(game.phase, "name", None) == "MOVEMENT_PHASE":
                queue_transport_choices = getattr(game, "_queue_movement_phase_start_transport_choices", None)
                if callable(queue_transport_choices) and queue_transport_choices(player=game.get_current_player()):
                    return
                queue_move_units = getattr(game, "_queue_movement_phase_move_units_selection", None)
                if callable(queue_move_units):
                    queue_move_units(player=game.get_current_player())
            elif getattr(game.phase, "name", None) == "SHOOTING_PHASE":
                queue_shooting = getattr(game, "_queue_shooting_phase_selection", None)
                if callable(queue_shooting):
                    queue_shooting(player=game.get_current_player())
            elif getattr(game.phase, "name", None) == "CHARGE_PHASE":
                queue_charge = getattr(game, "_queue_charge_phase_selection", None)
                if callable(queue_charge):
                    queue_charge(player=game.get_current_player())
            elif getattr(game.phase, "name", None) == "FIGHT_PHASE":
                ensure_fight = getattr(game, "_ensure_fight_phase_manager_started", None)
                if callable(ensure_fight):
                    ensure_fight()
        except Exception:
            pass

    # Phase-specific resets are no longer needed since we reset all round state at battle round start

    if next_phase_value == 0:  # If we've wrapped around to COMMAND_PHASE
        # End-of-turn scoring happens when a player's turn ends (before switching current player)
        try:
            game.end_of_turn_scoring()
        except Exception:
            pass
        # This means we've finished all phases for the current player
        # Switch to the next player
        game.current_player_index = (game.current_player_index + 1) % len(game.players)

        # Clear enemy model cache when switching players since enemy positions may have changed
        clear_enemy_model_cache(game.map)
        logger.info(f"INFO: Player switched to {game.get_current_player().name} - cleared enemy model cache")

        # Track who started this battle round if not already set
        if game.battle_round_starting_player_index is None:
            # This is the first player switch of the game - the previous player started the round
            game.battle_round_starting_player_index = (game.current_player_index - 1) % len(game.players)

        # Check if we've completed a full battle round (both players have had their turn)
        if game.current_player_index == game.battle_round_starting_player_index:
            # We've cycled back to the player who started this battle round
            # Score end-of-battle-round primaries
            try:
                game.end_of_battle_round_scoring()
            except Exception:
                pass
            game.turn += 1
            if int(getattr(game, "turn", 0) or 0) > int(TOTAL_ROUNDS):
                return
            try:
                if hasattr(game.map, "bump_state_generation"):
                    game.map.bump_state_generation("battle_round_advanced")
            except (AttributeError, TypeError):
                logger.debug("Unable to bump map state generation for battle-round advance.", exc_info=True)
            game.battle_round_starting_player_index = game.current_player_index  # This player starts the next round

            # Reset round state for ALL units at the start of a new battle round
            for player in game.players:
                for unit in player.get_army().units:
                    unit.initialize_round()
                # Army-level battle round start hook (faction rules/buffs)
                player.get_army().on_battle_round_start(game.turn)

            # Publish start-of-battle-round hook for UI/faction rules (best-effort)
            game.event_system.publish("battle_round_started", game=game, battle_round=game.turn)
        # Start of COMMAND_PHASE for the new current player
        try:
            game.start_command_phase()
        except Exception:
            pass
