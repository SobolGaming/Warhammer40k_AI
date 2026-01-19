from warhammer40k_ai.engine.command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_NEXT_PHASE,
    CMD_SELECT_MISSION,
    CMD_SET_DEPLOYMENT_WAITING,
)
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game, SetupPhase
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl


def _make_game():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    army_one = Army("Chaos Daemons", "Test")
    army_two = Army("Chaos Daemons", "Test")
    player_one = Player("P1", PlayerControl.LOCAL, army_one)
    player_two = Player("P2", PlayerControl.REMOTE, army_two)
    game = Game(bf, players=[player_one, player_two])
    return game


def test_next_phase_requires_setup_complete():
    game = _make_game()
    game.setup_complete = False
    start_phase = game.phase
    cmd = GameCommand.create(CMD_NEXT_PHASE, player_id=game.get_current_player().id)
    result = game.apply_command(cmd)
    assert result.ok is False
    assert game.phase == start_phase


def test_next_phase_advances_when_setup_complete():
    game = _make_game()
    game.setup_complete = True
    game.phase = BattleRoundPhases.COMMAND_PHASE
    cmd = GameCommand.create(CMD_NEXT_PHASE, player_id=game.get_current_player().id)
    result = game.apply_command(cmd)
    assert result.ok is True
    assert game.phase == BattleRoundPhases.MOVEMENT_PHASE


def test_execute_setup_phase_rejects_unknown_payload_keys():
    game = _make_game()
    cmd = GameCommand.create(
        CMD_EXECUTE_SETUP_PHASE,
        player_id=game.get_current_player().id,
        payload={"manual_phases": True, "decision_makers": {"x": 1}},
    )
    result = game.apply_command(cmd)
    assert result.ok is False


def test_select_mission_sets_primary_cards():
    game = _make_game()
    combination = {"id": "TEST1", "primary": "Take and Hold", "deployment": "Test"}
    layout = {"layout": 1}
    cmd = GameCommand.create(
        CMD_SELECT_MISSION,
        player_id=game.get_current_player().id,
        payload={"combination": combination, "layout": layout},
    )
    result = game.apply_command(cmd)
    assert result.ok is True
    assert game.selected_mission_info["primary"] == "Take and Hold"
    for player in game.players:
        assert player.primary_mission is not None
        assert player.primary_mission.name == "Take and Hold"


def test_set_deployment_waiting_flag():
    game = _make_game()
    game.waiting_for_deployment_input = True
    cmd = GameCommand.create(
        CMD_SET_DEPLOYMENT_WAITING,
        player_id=game.get_current_player().id,
        payload={"value": False},
    )
    result = game.apply_command(cmd)
    assert result.ok is True
    assert game.waiting_for_deployment_input is False


def test_advance_setup_phase_returns_value():
    game = _make_game()
    game.setup_complete = False
    game.setup_phase = SetupPhase.RESOLVE_PREBATTLE_RULES
    cmd = GameCommand.create(CMD_ADVANCE_SETUP_PHASE, player_id=game.get_current_player().id)
    result = game.apply_command(cmd)
    assert result.ok is True
    assert result.value is True
    assert game.setup_complete is True
