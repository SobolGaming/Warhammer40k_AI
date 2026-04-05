from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.utility.decision_utils import resolve_or_reuse_decision_value


class _QueueStub:
    def __init__(self, request: DecisionRequest | None) -> None:
        self._request = request

    def get(self, decision_id: str):
        if self._request is None:
            return None
        if str(getattr(self._request, "decision_id", "") or "") != str(decision_id or ""):
            return None
        return self._request


class _GameStub:
    def __init__(self, request: DecisionRequest | None) -> None:
        self.decision_queue = _QueueStub(request)
        self.commands = []

    def apply_command(self, command):
        self.commands.append(command)
        return SimpleNamespace(ok=True, value=SimpleNamespace(ok=True, value="manual-choice"))


def _build_request() -> DecisionRequest:
    return DecisionRequest.create(
        "TEST_DECISION",
        "Pick one",
        player_id="player-1",
        options=[DecisionOption.create("Use", payload={"choice": "use"})],
    )


def test_resolve_or_reuse_decision_value_reuses_settled_request() -> None:
    request = _build_request()
    game = _GameStub(request=None)
    settled_apply_result = SimpleNamespace(ok=True, value="auto-choice")
    request._resolved_decision_apply_result = settled_apply_result
    request._resolved_decision_value = "auto-choice"

    value, apply_result = resolve_or_reuse_decision_value(
        game,
        request,
        request.options[0].option_id,
        player_id="player-1",
    )

    assert value == "auto-choice"
    assert apply_result is settled_apply_result
    assert game.commands == []


def test_resolve_or_reuse_decision_value_dispatches_pending_request() -> None:
    request = _build_request()
    game = _GameStub(request=request)

    value, apply_result = resolve_or_reuse_decision_value(
        game,
        request,
        request.options[0].option_id,
        player_id="player-1",
    )

    assert value == "manual-choice"
    assert getattr(apply_result, "ok", False) is True
    assert len(game.commands) == 1
    assert game.commands[0].payload["decision_id"] == request.decision_id
