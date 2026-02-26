from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HydratedPresentationState:
    latest_game_loaded: dict[str, Any] | None = None
    pending_decisions: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_sequence_by_stream: dict[str, int] = field(default_factory=dict)

    def apply_envelope(self, envelope: object) -> None:
        stream_id = str(getattr(envelope, "stream_id", "") or "")
        sequence_id = int(getattr(envelope, "sequence_id"))
        payload = dict(getattr(envelope, "payload", {}) or {})
        if not stream_id:
            raise ValueError("Envelope stream_id is required.")
        if sequence_id < 0:
            raise ValueError("Envelope sequence_id must be >= 0.")

        last = int(self.last_sequence_by_stream.get(stream_id, -1))
        if sequence_id <= last:
            return
        if sequence_id != last + 1:
            raise ValueError(
                f"Out-of-order envelope for stream {stream_id}: expected {last + 1}, got {sequence_id}."
            )
        self.last_sequence_by_stream[stream_id] = sequence_id
        self._apply_payload(payload)

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        kind = str(payload.get("kind", "") or "")
        if kind == "game_loaded":
            self.latest_game_loaded = dict(payload)
            return
        if kind == "decision_requested":
            if bool(payload.get("redacted", False)):
                return
            decision_id = str(payload.get("decision_id", "") or "")
            if decision_id:
                self.pending_decisions[decision_id] = dict(payload)
            return
        if kind == "decision_resolved":
            decision_id = str(payload.get("decision_id", "") or "")
            if decision_id:
                self.pending_decisions.pop(decision_id, None)
            return

    @classmethod
    def from_envelopes(cls, envelopes: list[object]) -> "HydratedPresentationState":
        state = cls()
        for envelope in list(envelopes or []):
            state.apply_envelope(envelope)
        return state
