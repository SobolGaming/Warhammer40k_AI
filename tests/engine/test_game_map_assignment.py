from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.engine.game import Battlefield, Game


def test_game_map_assignment_restores_back_reference():
    game = Game(Battlefield(width=60, height=44))
    replacement = Map(width=44, height=30)

    game.map = replacement

    assert game.map is replacement
    assert replacement.game is game


def test_game_set_map_restores_back_reference():
    game = Game(Battlefield(width=60, height=44))
    replacement = Map(width=44, height=30)

    game.set_map(replacement)

    assert game.map is replacement
    assert replacement.game is game
