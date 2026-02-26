from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..engine.presentation_envelope import PresentationEnvelope


@dataclass(frozen=True)
class PresentationEnvelopeView:
    """Read-only envelope passed to presentation sinks."""

    stream_id: str
    sequence_id: int
    payload: dict[str, Any]
    schema_version: str


class PresentationRedactionPolicy:
    """Simple player-scoped redaction policy for owner-only payloads."""

    def redact(self, payload: dict[str, Any], viewer_player_id: Optional[str]) -> dict[str, Any]:
        visibility = str(payload.get("visibility", "") or "").strip().lower()
        owner = str(payload.get("player_id", "") or "").strip()
        viewer = str(viewer_player_id or "").strip()
        if visibility == "owner_only" and owner and viewer and owner != viewer:
            return {
                "kind": payload.get("kind", "unknown"),
                "visibility": visibility,
                "redacted": True,
            }
        return payload


class SessionPresentationOrchestrator:
    """Shared local/network HUD projection fan-out."""

    def __init__(
        self,
        *,
        stream_id: str,
        viewer_player_id: Optional[str] = None,
        redaction_policy: Optional[PresentationRedactionPolicy] = None,
    ) -> None:
        sid = str(stream_id or "").strip()
        if not sid:
            raise ValueError("stream_id is required.")
        self._stream_id = sid
        self._viewer_player_id = viewer_player_id
        self._redaction_policy = redaction_policy or PresentationRedactionPolicy()
        self._sequence_id = 0
        self._sinks: list[Callable[[PresentationEnvelopeView], None]] = []
        self._game_view = None
        self._attached_game = None
        self._event_group = f"presentation_orchestrator:{sid}"

    def set_viewer_player_id(self, player_id: Optional[str]) -> None:
        self._viewer_player_id = player_id

    def add_sink(self, sink: Callable[[PresentationEnvelopeView], None]) -> None:
        self._sinks.append(sink)

    def bind_game_view(self, game_view: object) -> None:
        self._game_view = game_view

    @property
    def latest_sequence_id(self) -> int:
        return self._sequence_id

    def publish_game_loaded(
        self,
        *,
        game: object,
        game_map: object,
        players: list[object],
    ) -> None:
        self._attach_game_events(game)
        player_ids = [str(getattr(player, "id", "") or "") for player in list(players or [])]
        envelope = self._build_envelope(
            {
                "kind": "game_loaded",
                "player_ids": player_ids,
                "setup_phase": str(getattr(game, "setup_phase", "") or ""),
            }
        )
        self._emit(envelope)
        if self._game_view is not None:
            set_game = getattr(self._game_view, "set_game", None)
            if callable(set_game) and len(players) >= 2:
                set_game(game, game_map, players[0], players[1])

    def publish_decision_request(self, request: object) -> None:
        payload: dict[str, Any]
        if isinstance(request, dict):
            payload = dict(request)
        else:
            to_dict = getattr(request, "to_dict", None)
            payload = dict(to_dict() or {}) if callable(to_dict) else {}
        if not payload:
            return
        envelope = self._build_envelope(
            {
                "kind": "decision_requested",
                "player_id": str(payload.get("player_id", "") or ""),
                "decision_type": str(payload.get("decision_type", "") or ""),
                "decision_id": str(payload.get("decision_id", "") or ""),
                "visibility": str(payload.get("visibility", "owner_only") or "owner_only"),
            }
        )
        self._emit(envelope)

    def publish_decision_resolved(self, request: object, result: object) -> None:
        request_payload = dict(request) if isinstance(request, dict) else {}
        if not request_payload:
            to_dict = getattr(request, "to_dict", None)
            request_payload = dict(to_dict() or {}) if callable(to_dict) else {}
        result_payload = dict(result) if isinstance(result, dict) else {}
        if not result_payload:
            result_to_dict = getattr(result, "to_dict", None)
            result_payload = dict(result_to_dict() or {}) if callable(result_to_dict) else {}
        decision_id = str(
            request_payload.get("decision_id", "") or result_payload.get("decision_id", "") or ""
        )
        if not decision_id:
            return
        envelope = self._build_envelope(
            {
                "kind": "decision_resolved",
                "decision_id": decision_id,
                "player_id": str(
                    request_payload.get("player_id", "") or result_payload.get("player_id", "") or ""
                ),
                "visibility": "owner_only",
            }
        )
        self._emit(envelope)

    def _attach_game_events(self, game: object) -> None:
        if game is self._attached_game:
            return
        if self._attached_game is not None:
            old_events = getattr(self._attached_game, "event_system", None)
            unsubscribe = getattr(old_events, "unsubscribe_group", None) if old_events is not None else None
            if callable(unsubscribe):
                unsubscribe(self._event_group)
        self._attached_game = game
        event_system = getattr(game, "event_system", None)
        subscribe = getattr(event_system, "subscribe", None) if event_system is not None else None
        if callable(subscribe):
            subscribe("decision_requested", self._on_decision_requested, group=self._event_group)
            subscribe("decision_resolved", self._on_decision_resolved, group=self._event_group)

    def _on_decision_requested(self, request=None, **_kwargs) -> None:
        if request is None:
            return
        self.publish_decision_request(request)

    def _on_decision_resolved(self, request=None, result=None, **_kwargs) -> None:
        if request is None or result is None:
            return
        self.publish_decision_resolved(request, result)

    def _build_envelope(self, payload: dict[str, Any]) -> PresentationEnvelope:
        redacted_payload = self._redaction_policy.redact(payload, self._viewer_player_id)
        envelope = PresentationEnvelope(
            stream_id=self._stream_id,
            sequence_id=self._sequence_id,
            payload=redacted_payload,
        )
        self._sequence_id += 1
        return envelope

    def _emit(self, envelope: PresentationEnvelope) -> None:
        view = PresentationEnvelopeView(
            stream_id=envelope.stream_id,
            sequence_id=int(envelope.sequence_id),
            payload=dict(envelope.payload or {}),
            schema_version=envelope.schema_version,
        )
        for sink in list(self._sinks):
            sink(view)
