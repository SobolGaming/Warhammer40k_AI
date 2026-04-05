from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.UI.presentation_state_hydrator import HydratedPresentationState
from warhammer40k_ai.UI.session_presentation_orchestrator import SessionPresentationOrchestrator


def _capture(orchestrator: SessionPresentationOrchestrator):
    captured = []
    orchestrator.add_sink(lambda env: captured.append(env))
    return captured


def _emit_reference_transcript(orchestrator: SessionPresentationOrchestrator) -> None:
    game = SimpleNamespace(setup_phase="CREATE_BATTLEFIELD", event_system=SimpleNamespace(subscribe=lambda *_args, **_kwargs: None))
    players = [SimpleNamespace(id="p1"), SimpleNamespace(id="p2")]
    orchestrator.publish_game_loaded(game=game, game_map="map", players=players)
    orchestrator.publish_decision_request(
        {
            "decision_id": "d1",
            "decision_type": "CONFIRM_YES_NO",
            "player_id": "p1",
            "visibility": "owner_only",
        }
    )
    orchestrator.publish_decision_resolved(
        {"decision_id": "d1", "player_id": "p1"},
        {"decision_id": "d1", "player_id": "p1"},
    )


def test_local_and_network_orchestrators_emit_parity_payload_sequences() -> None:
    local = SessionPresentationOrchestrator(stream_id="local:stream", viewer_player_id="p1")
    network = SessionPresentationOrchestrator(stream_id="network:stream", viewer_player_id="p1")
    local_env = _capture(local)
    network_env = _capture(network)

    _emit_reference_transcript(local)
    _emit_reference_transcript(network)

    local_norm = [(env.sequence_id, env.payload) for env in local_env]
    network_norm = [(env.sequence_id, env.payload) for env in network_env]
    assert local_norm == network_norm


def test_presentation_hydrator_tracks_pending_decision_and_resolution() -> None:
    orchestrator = SessionPresentationOrchestrator(stream_id="stream", viewer_player_id="p1")
    captured = _capture(orchestrator)
    _emit_reference_transcript(orchestrator)

    pending_state = HydratedPresentationState.from_envelopes(captured[:2])
    assert "d1" in pending_state.pending_decisions

    final_state = HydratedPresentationState.from_envelopes(captured)
    assert final_state.latest_game_loaded is not None
    assert final_state.pending_decisions == {}


def test_presentation_hydrator_rejects_sequence_gaps() -> None:
    state = HydratedPresentationState()
    state.apply_envelope(SimpleNamespace(stream_id="s", sequence_id=0, payload={"kind": "game_loaded"}))
    with pytest.raises(ValueError):
        state.apply_envelope(SimpleNamespace(stream_id="s", sequence_id=2, payload={"kind": "decision_requested"}))
