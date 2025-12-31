import pytest

from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.classes.player import Player, PlayerType


class DummyArmy:
    def __init__(self):
        self.units = []
        self.player = None

    def set_player(self, p):
        self.player = p


class DummyUnit:
    def __init__(self, name: str, *, titanic: bool = False):
        self.name = name
        self.deployed = False
        self.reserve_status = "deployed"
        self.is_attached_leader = False
        self.is_embarked = False
        self.embarked_in = None
        self._titanic = titanic

    @property
    def is_titanic(self) -> bool:
        return bool(self._titanic)


def _make_game():
    battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    p_def = Player("Defender", PlayerType.HUMAN, army=DummyArmy())
    p_att = Player("Attacker", PlayerType.HUMAN, army=DummyArmy())
    game = Game(battlefield, players=[p_def, p_att])
    game.turn = 1
    game.defender_index = 0
    game.attacker_index = 1
    game.deployment_turn_index = game.defender_index
    return game, p_def, p_att


def test_deployment_titanic_skips_next_turn_and_opponent_deploys_twice():
    game, p_def, p_att = _make_game()
    titan = DummyUnit("Titan", titanic=True)
    def2 = DummyUnit("Defender Unit 2", titanic=False)
    att1 = DummyUnit("Attacker Unit 1", titanic=False)
    att2 = DummyUnit("Attacker Unit 2", titanic=False)
    p_def.army.units = [titan, def2]
    p_att.army.units = [att1, att2]

    assert game.is_deployment_phase()
    assert game.get_current_deployment_player() == p_def

    # Defender deploys TITANIC -> attacker gets next, and defender will be skipped once later
    titan.deployed = True
    game.advance_deployment_turn(titan)
    assert game.get_current_deployment_player() == p_att

    # Attacker deploys one -> defender would normally go next, but is skipped, so attacker goes again
    att1.deployed = True
    game.advance_deployment_turn(att1)
    assert game.get_current_deployment_player() == p_att

    # Attacker deploys second -> now we can return to defender
    att2.deployed = True
    game.advance_deployment_turn(att2)
    assert game.get_current_deployment_player() == p_def


def test_deployment_titanic_skip_is_ignored_if_opponent_has_no_units_left():
    game, p_def, p_att = _make_game()
    titan = DummyUnit("Titan", titanic=True)
    def2 = DummyUnit("Defender Unit 2", titanic=False)
    p_def.army.units = [titan, def2]
    p_att.army.units = []

    assert game.is_deployment_phase()
    assert game.get_current_deployment_player() == p_def

    # Defender deploys TITANIC but opponent has no units -> defender should keep deploying
    titan.deployed = True
    game.advance_deployment_turn(titan)
    assert game.get_current_deployment_player() == p_def


