import pytest

from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.command_kinds import CMD_SET_DEPLOYMENT_WAITING
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_PLAYER_COLOR
from warhammer40k_ai.engine.decision_requests import build_player_color_selection_requests
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.network.messages import CommandMessage, ErrorMessage, EventMessage, ResyncMessage, parse_message
from warhammer40k_ai.network.protocol import EventStreamCursor, build_resync_message, handle_command_message
from warhammer40k_ai.roster.player import Player
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


def test_command_message_roundtrip():
    command = GameCommand.create(
        CMD_SET_DEPLOYMENT_WAITING,
        player_id="p1",
        payload={"value": True},
        metadata={"source": "test"},
    )
    message = CommandMessage(command=command, client_last_event_id=5)
    payload = message.to_dict()
    parsed = parse_message(payload)
    assert isinstance(parsed, CommandMessage)
    assert parsed.command.kind == CMD_SET_DEPLOYMENT_WAITING
    assert parsed.command.player_id == "p1"
    assert parsed.command.payload["value"] is True
    assert parsed.client_last_event_id == 5


def test_event_stream_cursor_validation():
    cursor = EventStreamCursor()
    cursor.validate_and_advance(
        [
            {"event_id": 1, "type": "command_applied", "payload": {}},
            {"event_id": 2, "type": "roll_made", "payload": {}},
        ]
    )
    assert cursor.last_event_id == 2
    # Forward jumps are tolerated (resync will correct state).
    cursor.validate_and_advance([{"event_id": 4, "type": "roll_made", "payload": {}}])
    assert cursor.last_event_id == 4
    # Backward or duplicate events are still rejected.
    with pytest.raises(ValueError):
        cursor.validate_and_advance([{"event_id": 3, "type": "roll_made", "payload": {}}])


def test_handle_command_message_success():
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    command = GameCommand.create(CMD_SET_DEPLOYMENT_WAITING, payload={"value": True})
    message = CommandMessage(command=command, client_last_event_id=0)
    messages = handle_command_message(game, message, require_client_sync=True)
    assert messages
    event_messages = [m for m in messages if isinstance(m, EventMessage)]
    assert event_messages
    events = event_messages[0].events
    assert events[-1]["type"] == "command_applied"


def test_handle_command_message_error_includes_event():
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    command = GameCommand.create(CMD_SET_DEPLOYMENT_WAITING, payload={})
    message = CommandMessage(command=command)
    messages = handle_command_message(game, message, require_client_sync=False)
    assert any(isinstance(m, ErrorMessage) for m in messages)
    event_messages = [m for m in messages if isinstance(m, EventMessage)]
    assert event_messages
    assert any(evt["type"] == "command_rejected" for evt in event_messages[0].events)


def test_handle_command_message_triggers_resync_on_desync():
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    first = GameCommand.create(CMD_SET_DEPLOYMENT_WAITING, payload={"value": True})
    game.apply_command(first)

    second = GameCommand.create(CMD_SET_DEPLOYMENT_WAITING, payload={"value": False})
    message = CommandMessage(command=second, client_last_event_id=0)
    messages = handle_command_message(game, message, require_client_sync=True)

    assert len(messages) == 1
    assert isinstance(messages[0], ResyncMessage)
    resync = messages[0]
    assert resync.reason == "client_out_of_sync"
    assert resync.snapshot.get("events", None) == []
    assert resync.events


def test_build_resync_message():
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    command = GameCommand.create(CMD_SET_DEPLOYMENT_WAITING, payload={"value": True})
    game.apply_command(command)
    resync = build_resync_message(game, since_event_id=0, reason="test")
    assert resync.snapshot.get("events", None) == []
    assert resync.reason == "test"
    assert len(resync.events) >= 1


def test_resync_snapshot_includes_player_color_state_and_pending_color_decisions():
    player_one = Player("Player One")
    player_two = Player("Player Two")
    game = Game(Battlefield(width=60, height=44), players=[player_one, player_two])
    game.turn = 1

    player_one.set_ui_color([31, 62, 93], hue_degrees=120, selected=True, source="selected")
    created = build_player_color_selection_requests(game, [player_two], queue_requests=True)
    assert len(created) == 1
    request = created[0]
    chosen = request.options[3]

    pending_resync = build_resync_message(game, since_event_id=0, reason="pending_player_color")
    players_by_id = {
        str(entry.get("id", "") or ""): dict(entry.get("state", {}) or {})
        for entry in list(pending_resync.snapshot.get("players", []) or [])
    }
    assert players_by_id[player_one.id]["ui_color_rgb"] == [31, 62, 93]
    assert players_by_id[player_one.id]["ui_color_hue_degrees"] == 120
    assert players_by_id[player_one.id]["ui_color_selected"] is True
    pending_decisions = [
        d
        for d in list(pending_resync.snapshot.get("decisions", []) or [])
        if d.get("decision_type") == DECISION_CHOOSE_PLAYER_COLOR
    ]
    assert len(pending_decisions) == 1
    pending_action_ids = [str(c.get("action_id", "") or "") for c in list(pending_decisions[0].get("candidates", []) or [])]
    assert pending_action_ids == sorted(pending_action_ids)

    applied = resolve_decision_command(game, request, chosen.option_id, player_id=player_two.id)
    assert bool(getattr(applied, "ok", False))

    resolved_resync = build_resync_message(game, since_event_id=0, reason="resolved_player_color")
    resolved_players = {
        str(entry.get("id", "") or ""): dict(entry.get("state", {}) or {})
        for entry in list(resolved_resync.snapshot.get("players", []) or [])
    }
    assert resolved_players[player_two.id]["ui_color_rgb"] == list(chosen.payload["rgb"])
    assert resolved_players[player_two.id]["ui_color_hue_degrees"] == int(chosen.payload["hue_degrees"])
    assert resolved_players[player_two.id]["ui_color_selected"] is True
    assert resolved_players[player_two.id]["ui_color_source"] == "selected"
    assert all(
        d.get("decision_type") != DECISION_CHOOSE_PLAYER_COLOR
        for d in list(resolved_resync.snapshot.get("decisions", []) or [])
    )


def test_game_snapshot_api_roundtrip():
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 1
    snapshot = game.save_snapshot()
    loaded = Game.load_snapshot(snapshot)
    assert isinstance(loaded, Game)


def test_game_snapshot_api_gating():
    game = Game(Battlefield(width=60, height=44), players=[])
    game.turn = 0
    with pytest.raises(RuntimeError):
        _ = game.save_snapshot()
