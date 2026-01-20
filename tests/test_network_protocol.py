import pytest

from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.command_kinds import CMD_SET_DEPLOYMENT_WAITING
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.network.messages import CommandMessage, ErrorMessage, EventMessage, ResyncMessage, parse_message
from warhammer40k_ai.network.protocol import EventStreamCursor, build_resync_message, handle_command_message


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
    with pytest.raises(ValueError):
        cursor.validate_and_advance([{"event_id": 4, "type": "roll_made", "payload": {}}])


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
