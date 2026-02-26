from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PRESENTATION_SCHEMA_VERSION = "1.0"


def _parse_schema_version(version: str) -> tuple[int, int]:
    text = str(version or "").strip()
    if not text or "." not in text:
        raise ValueError("schema_version must use major.minor format.")
    major_text, minor_text = text.split(".", 1)
    if not major_text.isdigit() or not minor_text.isdigit():
        raise ValueError("schema_version must use numeric major.minor format.")
    return int(major_text), int(minor_text)


def validate_schema_compatibility(schema_version: str) -> None:
    current_major, _current_minor = _parse_schema_version(PRESENTATION_SCHEMA_VERSION)
    version_major, _version_minor = _parse_schema_version(schema_version)
    if version_major != current_major:
        raise ValueError(
            f"Incompatible schema major version: {schema_version} (expected major {current_major})."
        )


@dataclass(frozen=True)
class PresentationEnvelope:
    """
    Canonical presentation event envelope for local/network parity.

    stream_id + sequence_id define deterministic ordering and idempotency semantics.
    """

    stream_id: str
    sequence_id: int
    payload: dict[str, Any]
    schema_version: str = PRESENTATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        validate_schema_compatibility(self.schema_version)
        if not str(self.stream_id or "").strip():
            raise ValueError("stream_id is required.")
        if int(self.sequence_id) < 0:
            raise ValueError("sequence_id must be >= 0.")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a dict.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "stream_id": self.stream_id,
            "sequence_id": int(self.sequence_id),
            "payload": dict(self.payload or {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PresentationEnvelope":
        if not isinstance(data, dict):
            raise ValueError("Envelope payload must be a dict.")
        if "sequence_id" not in data:
            raise ValueError("sequence_id is required.")
        return cls(
            schema_version=str(data.get("schema_version") or ""),
            stream_id=str(data.get("stream_id") or ""),
            sequence_id=int(data.get("sequence_id")),
            payload=dict(data.get("payload") or {}),
        )
