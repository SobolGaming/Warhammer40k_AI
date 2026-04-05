from __future__ import annotations

from dataclasses import dataclass

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_DEPLOYMENT_ZONE
from warhammer40k_ai.engine.decision_requests import build_deployment_zone_request
from warhammer40k_ai.engine.deployment_intent import DeploymentIntent
from warhammer40k_ai.engine.deployment_solver import generate_deployment_candidates
from warhammer40k_ai.engine.decisions import CandidateAction
from warhammer40k_ai.engine.time_manager import TimeManager


@dataclass
class _GameStub:
    time_manager: TimeManager
    decision_queue: object | None = None


class _PlayerStub:
    def __init__(self, player_id: str) -> None:
        self.id = player_id


def _build_request(*, budget_ms: int):
    game = _GameStub(time_manager=TimeManager())
    player = _PlayerStub("player-1")
    zones = [
        {"name": "Zone A", "zone_type": "defender", "x_range": [0.0, 30.0], "y_range": [0.0, 44.0]},
        {"name": "Zone B", "zone_type": "attacker", "x_range": [30.0, 60.0], "y_range": [0.0, 44.0]},
    ]
    request = build_deployment_zone_request(game, player, zones, queue_requests=False)
    assert request is not None
    request.context["time_budget_ms"] = int(budget_ms)
    return game, request


def test_deployment_solver_uses_fallback_candidates_when_budget_is_exceeded(monkeypatch) -> None:
    game, request = _build_request(budget_ms=10)
    intent = DeploymentIntent.from_context(request.context)
    expected_action_ids = [str(candidate.action_id) for candidate in list(request.candidates or [])]
    expected_mask = [bool(value) for value in list(request.mask or [])]

    def _solver(*_args, **_kwargs):
        return [CandidateAction(action_id="solver-action", params={"source": "solver"}, metadata={"fallback_mode": False})], [True]

    ticks = iter([500.0, 500.2])
    monkeypatch.setattr("warhammer40k_ai.engine.deployment_solver._solver_candidates", _solver)
    monkeypatch.setattr("warhammer40k_ai.engine.time_manager.time.perf_counter", lambda: next(ticks))

    candidates, mask, wall_clock_ms, fallback_mode = generate_deployment_candidates(game, request, intent)

    assert fallback_mode is True
    assert wall_clock_ms == 200
    assert [str(candidate.action_id) for candidate in list(candidates or [])] == expected_action_ids
    assert mask == expected_mask
    assert all(bool(dict(candidate.metadata or {}).get("fallback_mode", False)) for candidate in list(candidates or []))


def test_deployment_solver_keeps_solver_output_within_budget(monkeypatch) -> None:
    game, request = _build_request(budget_ms=25)
    intent = DeploymentIntent.from_context(request.context)

    def _solver(*_args, **_kwargs):
        return [CandidateAction(action_id="solver-action", params={"source": "solver"}, metadata={"fallback_mode": False})], [True]

    ticks = iter([700.0, 700.007])
    monkeypatch.setattr("warhammer40k_ai.engine.deployment_solver._solver_candidates", _solver)
    monkeypatch.setattr("warhammer40k_ai.engine.time_manager.time.perf_counter", lambda: next(ticks))

    candidates, mask, wall_clock_ms, fallback_mode = generate_deployment_candidates(game, request, intent)

    assert fallback_mode is False
    assert wall_clock_ms == 7
    assert [str(candidate.action_id) for candidate in list(candidates or [])] == ["solver-action"]
    assert mask == [True]
