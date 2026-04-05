from __future__ import annotations

from typing import Any


def get_state(game) -> dict[str, Any]:
    return {
        "players": game.players,
        "battlefield": game.battlefield,
        "map": game.map,
        "current_player": game.get_current_player(),
        "turn": game.turn,
        "phase": game.phase,
    }


def save_snapshot(game) -> dict:
    """Serialize the current game state into a snapshot payload."""
    from .snapshot import snapshot_game

    return snapshot_game(game)


def load_snapshot(snapshot: dict):
    """Load a game instance from a snapshot payload."""
    from .snapshot import load_game_snapshot

    return load_game_snapshot(snapshot)
