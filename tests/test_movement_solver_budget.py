from __future__ import annotations

from dataclasses import dataclass

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.engine.movement_intent import MovementIntent
from warhammer40k_ai.engine.movement_solver import generate_move_unit_candidates
from warhammer40k_ai.engine.time_manager import TimeManager


@dataclass
class _GameStub:
    time_manager: TimeManager


def _build_move_request(*, budget_ms: int) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id="player-1",
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": "unit-1", "movement_type": "move", "action": "confirm"},
            ),
            DecisionOption.create(
                "Skip",
                payload={"unit_id": "unit-1", "movement_type": "move", "action": "skip"},
            ),
        ],
        context={
            "unit_id": "unit-1",
            "movement_type": "move",
            "time_budget_ms": int(budget_ms),
        },
    )


def test_move_solver_uses_fallback_candidates_when_runtime_exceeds_budget(monkeypatch) -> None:
    game = _GameStub(time_manager=TimeManager())
    request = _build_move_request(budget_ms=10)
    intent = MovementIntent.from_context(request.context)
    expected_action_ids = [str(candidate.action_id) for candidate in list(request.candidates or [])]
    expected_mask = [bool(value) for value in list(request.mask or [])]

    def _solver(*_args, **_kwargs):
        return [CandidateAction(action_id="solver-action", params={"source": "solver"}, metadata={"fallback_mode": False})], [True]

    ticks = iter([100.0, 100.25])
    monkeypatch.setattr("warhammer40k_ai.engine.movement_solver._solver_candidates", _solver)
    monkeypatch.setattr("warhammer40k_ai.engine.time_manager.time.perf_counter", lambda: next(ticks))

    candidates, mask, wall_clock_ms, fallback_mode = generate_move_unit_candidates(game, request, intent)

    assert fallback_mode is True
    assert wall_clock_ms == 250
    assert [str(candidate.action_id) for candidate in list(candidates or [])] == expected_action_ids
    assert mask == expected_mask
    assert all(bool(dict(candidate.metadata or {}).get("fallback_mode", False)) for candidate in list(candidates or []))


def test_move_solver_keeps_solver_output_when_runtime_stays_within_budget(monkeypatch) -> None:
    game = _GameStub(time_manager=TimeManager())
    request = _build_move_request(budget_ms=25)
    intent = MovementIntent.from_context(request.context)

    def _solver(*_args, **_kwargs):
        return [CandidateAction(action_id="solver-action", params={"source": "solver"}, metadata={"fallback_mode": False})], [True]

    ticks = iter([300.0, 300.008])
    monkeypatch.setattr("warhammer40k_ai.engine.movement_solver._solver_candidates", _solver)
    monkeypatch.setattr("warhammer40k_ai.engine.time_manager.time.perf_counter", lambda: next(ticks))

    candidates, mask, wall_clock_ms, fallback_mode = generate_move_unit_candidates(game, request, intent)

    assert fallback_mode is False
    assert wall_clock_ms == 8
    assert [str(candidate.action_id) for candidate in list(candidates or [])] == ["solver-action"]
    assert mask == [True]
    assert bool(dict(candidates[0].metadata or {}).get("fallback_mode", False)) is False
