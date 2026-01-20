from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from ..engine.commands import GameCommand

PROTOCOL_VERSION = 1


def _ensure_envelope(data: dict, expected_type: str) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Message payload must be a dict.")
    msg_type = data.get("type")
    if msg_type != expected_type:
        raise ValueError(f"Expected message type '{expected_type}', got '{msg_type}'.")
    version = data.get("protocol_version", None)
    if version is None:
        raise ValueError("Message missing protocol_version.")
    if int(version) != PROTOCOL_VERSION:
        raise ValueError(f"Unsupported protocol version: {version}.")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Message payload must be a dict.")
    return payload


def _wrap_envelope(message_type: str, payload: dict) -> dict:
    return {
        "type": message_type,
        "protocol_version": PROTOCOL_VERSION,
        "payload": payload,
    }


def _ensure_jsonable(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for idx, item in enumerate(value):
            _ensure_jsonable(item, f"{path}[{idx}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings; got {type(key).__name__}.")
            _ensure_jsonable(item, f"{path}.{key}")
        return
    raise ValueError(f"{path} contains non-serializable value: {type(value).__name__}.")


def _serialize_command(command: GameCommand) -> dict:
    if command is None:
        raise ValueError("Command is required.")
    data = command.to_dict()
    if not data.get("command_id"):
        raise ValueError("Command requires command_id.")
    if not data.get("kind"):
        raise ValueError("Command requires kind.")
    payload = data.get("payload", {}) or {}
    metadata = data.get("metadata", {}) or {}
    if not isinstance(payload, dict):
        raise ValueError("Command payload must be a dict.")
    if not isinstance(metadata, dict):
        raise ValueError("Command metadata must be a dict.")
    _ensure_jsonable(payload, "command.payload")
    _ensure_jsonable(metadata, "command.metadata")
    return data


def _deserialize_command(data: dict) -> GameCommand:
    if not isinstance(data, dict):
        raise ValueError("Command payload must be a dict.")
    cmd = GameCommand.from_dict(data)
    if not cmd.command_id:
        raise ValueError("Command requires command_id.")
    if not cmd.kind:
        raise ValueError("Command requires kind.")
    _ensure_jsonable(cmd.payload or {}, "command.payload")
    _ensure_jsonable(cmd.metadata or {}, "command.metadata")
    return cmd


@dataclass(frozen=True)
class SnapshotMessage:
    snapshot: dict

    def to_dict(self) -> dict:
        if not isinstance(self.snapshot, dict):
            raise ValueError("Snapshot must be a dict.")
        payload = {"snapshot": dict(self.snapshot)}
        return _wrap_envelope("snapshot", payload)

    @classmethod
    def from_dict(cls, data: dict) -> "SnapshotMessage":
        payload = _ensure_envelope(data, "snapshot")
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict):
            raise ValueError("Snapshot payload must be a dict.")
        return cls(snapshot=dict(snapshot))


@dataclass(frozen=True)
class CommandMessage:
    command: GameCommand
    client_last_event_id: Optional[int] = None

    def to_dict(self) -> dict:
        payload: dict[str, Any] = {"command": _serialize_command(self.command)}
        if self.client_last_event_id is not None:
            payload["client_last_event_id"] = int(self.client_last_event_id)
        return _wrap_envelope("command", payload)

    @classmethod
    def from_dict(cls, data: dict) -> "CommandMessage":
        payload = _ensure_envelope(data, "command")
        command_payload = payload.get("command")
        cmd = _deserialize_command(command_payload)
        last_event_id = payload.get("client_last_event_id", None)
        if last_event_id is not None:
            last_event_id = int(last_event_id)
        return cls(command=cmd, client_last_event_id=last_event_id)


@dataclass(frozen=True)
class EventMessage:
    events: List[dict]

    def to_dict(self) -> dict:
        if not isinstance(self.events, list):
            raise ValueError("Events must be a list.")
        payload = {"events": [dict(e) for e in list(self.events or [])]}
        return _wrap_envelope("event", payload)

    @classmethod
    def from_dict(cls, data: dict) -> "EventMessage":
        payload = _ensure_envelope(data, "event")
        events = payload.get("events")
        if not isinstance(events, list):
            raise ValueError("Event payload must be a list.")
        normalized: List[dict] = []
        for idx, event in enumerate(events):
            if not isinstance(event, dict):
                raise ValueError(f"Event at index {idx} must be a dict.")
            if "event_id" not in event or "type" not in event:
                raise ValueError("Event must include event_id and type.")
            normalized.append(dict(event))
        return cls(events=normalized)


@dataclass(frozen=True)
class ErrorMessage:
    errors: List[str]
    context: Optional[dict] = None

    def to_dict(self) -> dict:
        if not isinstance(self.errors, list) or not all(isinstance(e, str) for e in self.errors):
            raise ValueError("Errors must be a list of strings.")
        payload: dict[str, Any] = {"errors": list(self.errors)}
        if self.context is not None:
            if not isinstance(self.context, dict):
                raise ValueError("Error context must be a dict.")
            payload["context"] = dict(self.context)
        return _wrap_envelope("error", payload)

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorMessage":
        payload = _ensure_envelope(data, "error")
        errors = payload.get("errors")
        if not isinstance(errors, list) or not all(isinstance(e, str) for e in errors):
            raise ValueError("Error payload requires errors list.")
        context = payload.get("context")
        if context is not None and not isinstance(context, dict):
            raise ValueError("Error context must be a dict.")
        return cls(errors=list(errors), context=dict(context) if isinstance(context, dict) else None)


@dataclass(frozen=True)
class ResyncMessage:
    snapshot: dict
    events: List[dict]
    reason: Optional[str] = None
    since_event_id: Optional[int] = None

    def to_dict(self) -> dict:
        if not isinstance(self.snapshot, dict):
            raise ValueError("Snapshot must be a dict.")
        if not isinstance(self.events, list):
            raise ValueError("Events must be a list.")
        payload: dict[str, Any] = {
            "snapshot": dict(self.snapshot),
            "events": [dict(e) for e in list(self.events or [])],
        }
        if self.reason is not None:
            payload["reason"] = str(self.reason)
        if self.since_event_id is not None:
            payload["since_event_id"] = int(self.since_event_id)
        return _wrap_envelope("resync", payload)

    @classmethod
    def from_dict(cls, data: dict) -> "ResyncMessage":
        payload = _ensure_envelope(data, "resync")
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict):
            raise ValueError("Resync snapshot must be a dict.")
        events = payload.get("events")
        if not isinstance(events, list):
            raise ValueError("Resync events must be a list.")
        reason = payload.get("reason")
        since_event_id = payload.get("since_event_id")
        if since_event_id is not None:
            since_event_id = int(since_event_id)
        return cls(
            snapshot=dict(snapshot),
            events=[dict(e) for e in list(events or [])],
            reason=str(reason) if reason is not None else None,
            since_event_id=since_event_id,
        )


def parse_message(data: dict) -> SnapshotMessage | CommandMessage | EventMessage | ErrorMessage | ResyncMessage:
    if not isinstance(data, dict):
        raise ValueError("Message must be a dict.")
    msg_type = data.get("type")
    if msg_type == "snapshot":
        return SnapshotMessage.from_dict(data)
    if msg_type == "command":
        return CommandMessage.from_dict(data)
    if msg_type == "event":
        return EventMessage.from_dict(data)
    if msg_type == "error":
        return ErrorMessage.from_dict(data)
    if msg_type == "resync":
        return ResyncMessage.from_dict(data)
    raise ValueError(f"Unknown message type: {msg_type}")
