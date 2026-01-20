from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from ..engine.game import Game
from ..engine.snapshot import snapshot_game
from ..engine.event_log import DeterministicEventLog
from ..engine.command_dispatcher import CommandResult
from .messages import CommandMessage, ErrorMessage, EventMessage, ResyncMessage, SnapshotMessage


def _current_event_id(event_log: DeterministicEventLog | None) -> int:
    if event_log is None or not getattr(event_log, "events", None):
        return 0
    return int(event_log.events[-1].event_id)


def _min_event_id(event_log: DeterministicEventLog | None) -> int:
    if event_log is None or not getattr(event_log, "events", None):
        return 0
    return int(event_log.events[0].event_id)


@dataclass
class EventStreamCursor:
    last_event_id: int = 0

    def validate_and_advance(self, events: Iterable[dict]) -> None:
        for event in list(events or []):
            if not isinstance(event, dict):
                raise ValueError("Event must be a dict.")
            event_id = event.get("event_id")
            if event_id is None:
                raise ValueError("Event missing event_id.")
            expected = self.last_event_id + 1
            if int(event_id) != expected:
                raise ValueError(f"Expected event_id {expected}, got {event_id}.")
            self.last_event_id = expected


def build_snapshot_message(game: Game) -> SnapshotMessage:
    snapshot = snapshot_game(game)
    return SnapshotMessage(snapshot=snapshot)


def build_resync_message(
    game: Game,
    *,
    since_event_id: int | None = None,
    reason: str | None = None,
) -> ResyncMessage:
    snapshot = snapshot_game(game)
    snapshot["events"] = []
    event_log = getattr(game, "event_log", None)
    events = event_log.serialize_events(since_event_id=since_event_id) if event_log is not None else []
    return ResyncMessage(snapshot=snapshot, events=list(events or []), reason=reason, since_event_id=since_event_id)


def _result_error_message(command_message: CommandMessage, result: CommandResult) -> ErrorMessage:
    context = {
        "command_id": command_message.command.command_id,
        "kind": command_message.command.kind,
    }
    return ErrorMessage(errors=list(result.errors or []), context=context)


def handle_command_message(
    game: Game,
    message: CommandMessage,
    *,
    require_client_sync: bool = True,
) -> List[EventMessage | ErrorMessage | ResyncMessage]:
    if message is None:
        raise ValueError("Command message is required.")
    event_log = getattr(game, "event_log", None)
    current_event_id = _current_event_id(event_log)

    if require_client_sync and message.client_last_event_id is not None:
        min_id = _min_event_id(event_log)
        client_id = int(message.client_last_event_id)
        if client_id < min_id or client_id != current_event_id:
            return [
                build_resync_message(
                    game,
                    since_event_id=message.client_last_event_id,
                    reason="client_out_of_sync",
                )
            ]

    start_event_id = current_event_id
    result = game.apply_command(message.command)

    messages: List[EventMessage | ErrorMessage | ResyncMessage] = []
    if not result.ok:
        messages.append(_result_error_message(message, result))
    if event_log is not None:
        new_events = event_log.serialize_events(since_event_id=start_event_id)
        if new_events:
            messages.append(EventMessage(events=list(new_events)))
    return messages
