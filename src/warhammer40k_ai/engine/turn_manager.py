from __future__ import annotations

from typing import TYPE_CHECKING

from ..utility.calcs import clear_enemy_model_cache
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
            game.handle_reserves_arrival_phase()
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
    # Publish phase start for stratagem triggers
    try:
        game.event_system.publish("phase_start", player=game.get_current_player(), phase=game.phase)
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
        clear_enemy_model_cache(id(game.map))
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
