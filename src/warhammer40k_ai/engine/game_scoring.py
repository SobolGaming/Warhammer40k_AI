from __future__ import annotations


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
