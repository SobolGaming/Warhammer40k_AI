from __future__ import annotations

from typing import Any, Tuple

from .messages import PROTOCOL_VERSION, _ensure_jsonable
from .transport import CONTROL_MESSAGE_TYPES


def build_control_message(message_type: str, payload: dict) -> dict:
    message_type = str(message_type or "")
    if message_type not in CONTROL_MESSAGE_TYPES:
        raise ValueError(f"Unknown control message type: {message_type}.")
    if not isinstance(payload, dict):
        raise ValueError("Control message payload must be a dict.")
    _ensure_jsonable(payload, "control.payload")
    return {
        "type": message_type,
        "protocol_version": PROTOCOL_VERSION,
        "payload": dict(payload),
    }


def parse_control_message(data: dict) -> Tuple[str, dict]:
    if not isinstance(data, dict):
        raise ValueError("Control message must be a dict.")
    message_type = data.get("type")
    if message_type not in CONTROL_MESSAGE_TYPES:
        raise ValueError(f"Unknown control message type: {message_type}.")
    version = data.get("protocol_version")
    if version is None or int(version) != PROTOCOL_VERSION:
        raise ValueError("Unsupported protocol version.")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Control message payload must be a dict.")
    _ensure_jsonable(payload, "control.payload")
    return str(message_type), dict(payload)
