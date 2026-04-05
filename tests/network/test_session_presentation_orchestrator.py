from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.UI.session_presentation_orchestrator import SessionPresentationOrchestrator


class _FakeEventSystem:
    def __init__(self) -> None:
        self._subs: list[tuple[str, object, str | None]] = []

    def subscribe(self, event_name: str, handler, group: str | None = None) -> None:
        self._subs.append((event_name, handler, group))

    def unsubscribe_group(self, group: str) -> None:
        self._subs = [entry for entry in self._subs if entry[2] != group]

    def emit(self, event_name: str, **kwargs) -> None:
        for name, handler, _group in list(self._subs):
            if name == event_name:
                handler(**kwargs)


class _FakeGameView:
    def __init__(self) -> None:
        self.calls = []

    def set_game(self, game, game_map, player1, player2) -> None:
        self.calls.append((game, game_map, player1, player2))


class _FakeGame:
    def __init__(self, setup_phase: str) -> None:
        self.setup_phase = setup_phase
        self.event_system = _FakeEventSystem()


def test_presentation_orchestrator_updates_view_and_emits_envelopes() -> None:
    orchestrator = SessionPresentationOrchestrator(stream_id="local:test", viewer_player_id="p1")
    envelopes = []
    orchestrator.add_sink(lambda env: envelopes.append(env))

    view = _FakeGameView()
    orchestrator.bind_game_view(view)

    game = _FakeGame(setup_phase="SELECT_MISSION_OBJECTIVES")
    players = [SimpleNamespace(id="p1"), SimpleNamespace(id="p2")]

    orchestrator.publish_game_loaded(game=game, game_map="map", players=players)

    assert len(view.calls) == 1
    assert len(envelopes) == 1
    assert envelopes[0].sequence_id == 0
    assert envelopes[0].payload["kind"] == "game_loaded"
    assert envelopes[0].payload["player_ids"] == ["p1", "p2"]


def test_presentation_orchestrator_redacts_owner_only_payload_for_other_player() -> None:
    orchestrator = SessionPresentationOrchestrator(stream_id="network:test", viewer_player_id="p2")
    envelopes = []
    orchestrator.add_sink(lambda env: envelopes.append(env))

    orchestrator.publish_decision_request(
        {
            "decision_id": "d1",
            "decision_type": "CHOOSE",
            "player_id": "p1",
            "visibility": "owner_only",
        }
    )

    assert len(envelopes) == 1
    assert envelopes[0].payload["redacted"] is True
    assert envelopes[0].payload["kind"] == "decision_requested"


def test_presentation_orchestrator_emits_decision_events_from_game_event_system() -> None:
    orchestrator = SessionPresentationOrchestrator(stream_id="network:test", viewer_player_id="p1")
    envelopes = []
    orchestrator.add_sink(lambda env: envelopes.append(env))

    game = _FakeGame(setup_phase="CREATE_BATTLEFIELD")
    players = [SimpleNamespace(id="p1"), SimpleNamespace(id="p2")]
    orchestrator.publish_game_loaded(game=game, game_map="map", players=players)

    game.event_system.emit(
        "decision_requested",
        request={
            "decision_id": "d2",
            "decision_type": "CONFIRM_YES_NO",
            "player_id": "p1",
            "visibility": "owner_only",
        },
    )

    assert [entry.payload["kind"] for entry in envelopes] == ["game_loaded", "decision_requested"]
    assert [entry.sequence_id for entry in envelopes] == [0, 1]
