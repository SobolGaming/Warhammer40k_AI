from __future__ import annotations

import logging

from .phase import BattleRoundPhases

logger = logging.getLogger(__name__)


def complete_setup_and_start_battle_round(game) -> bool:
    """Finalize setup, seed the first battle round, and enter the first command phase."""
    game.setup_complete = True
    for player in list(game.players or []):
        if player is None:
            raise RuntimeError("Missing player when applying aircraft reserve updates.")
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Missing army for {player.name} when applying aircraft reserve updates.")
        for unit in list(army.units):
            if unit is None:
                continue
            if not bool(getattr(unit, "is_aircraft", False)):
                continue
            if bool(getattr(unit, "hover_mode", False)):
                continue
            if str(getattr(unit, "reserve_status", "deployed")) != "reserves":
                continue
            unit.set_reserve_status("strategic_reserves")
    if game.first_turn_player_index is not None:
        game.current_player_index = game.first_turn_player_index
    else:
        game.current_player_index = game.attacker_index if game.attacker_index is not None else 0

    game.battle_round_starting_player_index = game.current_player_index
    game.phase = BattleRoundPhases.COMMAND_PHASE

    for player in list(game.players or []):
        if player is None:
            raise RuntimeError("Missing player when starting battle round.")
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Missing army for {player.name} when starting battle round.")
        for unit in list(army.units):
            unit.initialize_round()
        army.on_battle_round_start(game.turn)
    game.event_system.publish("battle_round_started", game=game, battle_round=game.turn)

    game.start_command_phase()

    first_turn_player = game.get_current_player()
    if game.first_turn_player_index == game.attacker_index:
        role = "Attacker"
    elif game.first_turn_player_index == game.defender_index:
        role = "Defender"
    else:
        role = "Player"
    logger.info("Setup complete! %s (%s) goes first", first_turn_player.name, role)
    return True
