from __future__ import annotations

from warhammer40k_ai.engine.decision_controller import DecisionController, DecisionControllerHub
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionQueue, DecisionRequest


class _GameStub:
    def __init__(self) -> None:
        self.decision_queue = DecisionQueue()


class _RecordingController(DecisionController):
    def __init__(self, calls: list[str], name: str) -> None:
        super().__init__()
        self._calls = calls
        self._name = name

    def on_decision_requested(self, game: object, request: DecisionRequest) -> None:
        self._calls.append(f"requested:{self._name}:{request.decision_id}")


class _ResolvingController(DecisionController):
    def __init__(self, calls: list[str], name: str) -> None:
        super().__init__()
        self._calls = calls
        self._name = name

    def on_decision_requested(self, game: object, request: DecisionRequest) -> None:
        self._calls.append(f"requested:{self._name}:{request.decision_id}")
        game.decision_queue.pop(request.decision_id)


def _build_request() -> DecisionRequest:
    return DecisionRequest.create(
        "TEST_DECISION",
        "Choose one option",
        player_id="player-1",
        options=[DecisionOption.create("Only option", payload={"value": 1})],
    )


def test_decision_controller_hub_stops_dispatch_after_request_is_resolved() -> None:
    game = _GameStub()
    hub = DecisionControllerHub(game)
    calls: list[str] = []
    request = _build_request()
    game.decision_queue.add(request)
    hub.add_controller(_ResolvingController(calls, "resolver"))
    hub.add_controller(_RecordingController(calls, "after"))

    hub._on_decision_requested(request=request, game=game)

    assert calls == [f"requested:resolver:{request.decision_id}"]
    assert game.decision_queue.get(request.decision_id) is None


def test_decision_controller_hub_continues_when_request_stays_pending() -> None:
    game = _GameStub()
    hub = DecisionControllerHub(game)
    calls: list[str] = []
    request = _build_request()
    game.decision_queue.add(request)
    hub.add_controller(_RecordingController(calls, "first"))
    hub.add_controller(_RecordingController(calls, "second"))

    hub._on_decision_requested(request=request, game=game)

    assert calls == [
        f"requested:first:{request.decision_id}",
        f"requested:second:{request.decision_id}",
    ]
    assert game.decision_queue.get(request.decision_id) is request
