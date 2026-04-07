from warhammer40k_ai.engine.command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_NEXT_PHASE,
    CMD_REQUEST_DECISION,
    CMD_RESOLVE_DECISION,
    CMD_SELECT_MISSION,
    CMD_START_COMMAND_PHASE,
    CMD_SET_DEPLOYMENT_WAITING,
)
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game, SetupPhase
from warhammer40k_ai.engine.mission_selection import default_mission_selection
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl


def _make_game():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    army_one = Army.with_detachment("Chaos Daemons", "Test")
    army_two = Army.with_detachment("Chaos Daemons", "Test")
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


def test_start_command_phase_routes_through_command_dispatch():
    game = _make_game()
    game.setup_complete = True
    game.phase = BattleRoundPhases.COMMAND_PHASE

    game.start_command_phase()

    command_events = [event for event in game.event_log.events if event.event_type == "command_applied"]
    assert command_events
    assert command_events[-1].payload["kind"] == CMD_START_COMMAND_PHASE


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
    combination, layout = default_mission_selection()
    layout = {"layout": layout}
    cmd = GameCommand.create(
        CMD_SELECT_MISSION,
        player_id=game.get_current_player().id,
        payload={"combination": combination, "layout": layout},
    )
    result = game.apply_command(cmd)
    assert result.ok is True
    assert game.selected_mission_info["primary"] == combination["primary"]
    assert game.selected_mission_info["mission_pack_id"] == "chapter_approved_2025_2026"
    assert game.selected_mission_info["deployment_definition_id"] == combination["deployment_definition_id"]
    assert game.selected_mission_info["secondary_rule_set_id"] == "chapter_approved_2025_2026"
    for player in game.players:
        assert player.primary_mission is not None
        assert player.primary_mission.name == combination["primary"]


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


def test_resolve_decision_removes_request():
    game = _make_game()
    player_id = game.get_current_player().id
    option = DecisionOption.create("Yes", payload={"value": True})
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Use ability?",
        player_id=player_id,
        options=[option],
    )
    game.request_decision(request)
    cmd = GameCommand.create(
        CMD_RESOLVE_DECISION,
        player_id=player_id,
        payload={"decision_id": request.decision_id, "option_id": option.option_id},
    )
    result = game.apply_command(cmd)
    assert result.ok is True
    assert game.decision_queue.peek() is None


def test_resolve_decision_rejects_invalid_option():
    game = _make_game()
    player_id = game.get_current_player().id
    option = DecisionOption.create("Yes", payload={"value": True})
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Use ability?",
        player_id=player_id,
        options=[option],
    )
    game.request_decision(request)
    cmd = GameCommand.create(
        CMD_RESOLVE_DECISION,
        player_id=player_id,
        payload={"decision_id": request.decision_id, "option_id": "bad-option"},
    )
    result = game.apply_command(cmd)
    assert result.ok is False
    assert game.decision_queue.peek() is request


def test_resolve_decision_rejects_wrong_player():
    game = _make_game()
    option = DecisionOption.create("Yes", payload={"value": True})
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Use ability?",
        player_id=game.get_current_player().id,
        options=[option],
    )
    game.request_decision(request)
    cmd = GameCommand.create(
        CMD_RESOLVE_DECISION,
        player_id="other-player",
        payload={"decision_id": request.decision_id, "option_id": option.option_id},
    )
    result = game.apply_command(cmd)
    assert result.ok is False
    assert game.decision_queue.peek() is request


def test_request_decision_adds_request():
    game = _make_game()
    player_id = game.get_current_player().id
    option = DecisionOption.create("Yes", payload={"value": True})
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Use ability?",
        player_id=player_id,
        options=[option],
    )
    cmd = GameCommand.create(
        CMD_REQUEST_DECISION,
        player_id=player_id,
        payload={"decision": request.to_dict()},
    )
    result = game.apply_command(cmd)
    assert result.ok is True
    queued = game.decision_queue.get(request.decision_id)
    assert queued is not None
    assert queued.decision_type == DECISION_CONFIRM_YES_NO


def test_request_decision_rejects_wrong_player():
    game = _make_game()
    option = DecisionOption.create("Yes", payload={"value": True})
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Use ability?",
        player_id=game.get_current_player().id,
        options=[option],
    )
    cmd = GameCommand.create(
        CMD_REQUEST_DECISION,
        player_id="other-player",
        payload={"decision": request.to_dict()},
    )
    result = game.apply_command(cmd)
    assert result.ok is False
    assert game.decision_queue.get(request.decision_id) is None
