from __future__ import annotations

from .game_mixins.missions_scoring_actions_mixin import GameMissionsScoringActionsMixin


class GameScoringService(GameMissionsScoringActionsMixin):
    """Service boundary for mission scoring and mission action helpers."""

    def __init__(self, game):
        object.__setattr__(self, "_game", game)

    def __getattribute__(self, name: str):
        if not name.startswith("__") and name != "_game":
            game = object.__getattribute__(self, "__dict__").get("_game")
            if game is not None:
                game_attrs = getattr(game, "__dict__", None)
                if isinstance(game_attrs, dict) and name in game_attrs:
                    return game_attrs[name]
        return super().__getattribute__(name)

    def __getattr__(self, name: str):
        return getattr(self._game, name)

    def __setattr__(self, name: str, value) -> None:
        if name == "_game":
            object.__setattr__(self, name, value)
            return
        setattr(self._game, name, value)

    def __deepcopy__(self, memo):
        return self


def get_winner(game):
    """Return the winning player or ``None`` if the game is not over or drawn."""
    if game.is_game_over():
        game.finalize_battle_scoring()
        if not game.players:
            return None
        max_vp = max((player.get_score() for player in game.players), default=0)
        winners = [player for player in game.players if player.get_score() == max_vp]
        if len(winners) != 1:
            return None
        return winners[0]
    return None


def get_loser(game):
    if game.is_game_over():
        game.finalize_battle_scoring()
        if not game.players:
            return None
        min_vp = min((player.get_score() for player in game.players), default=0)
        losers = [player for player in game.players if player.get_score() == min_vp]
        if len(losers) != 1:
            return None
        return losers[0]
    return None
