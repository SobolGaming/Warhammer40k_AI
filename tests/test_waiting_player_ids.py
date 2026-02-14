from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decisions import DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.phase import SetupPhase
from warhammer40k_ai.roster.player import Player


def test_waiting_player_id_from_decision_queue():
    p1 = Player("P1")
    p2 = Player("P2")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

    req1 = DecisionRequest.create("TEST_DECISION", "Test decision 1", player_id=p1.id)
    req2 = DecisionRequest.create("TEST_DECISION", "Test decision 2", player_id=p2.id)
    game.request_decision(req1)
    game.request_decision(req2)

    assert game.get_waiting_player_id() == p1.id
    assert game.get_waiting_player_ids() == {p1.id}


def test_waiting_player_id_deployment_setup():
    p1 = Player("P1")
    p2 = Player("P2")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
    game.setup_complete = False
    game.setup_phase = SetupPhase.DEPLOY_ARMIES
    game.deployment_turn_index = 1

    assert game.get_waiting_player_id() == p2.id
    assert game.get_waiting_player_ids() == {p2.id}


def test_waiting_player_id_battle_current_player():
    p1 = Player("P1")
    p2 = Player("P2")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
    game.setup_complete = True
    game.current_player_index = 0

    assert game.get_waiting_player_id() == p1.id
    assert game.get_waiting_player_ids() == {p1.id}
