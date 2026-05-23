from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import _validate_movement_action_distance_match


def _unit_with_model(*, movement: float = 6.0):
    model = SimpleNamespace(
        id="model-1",
        is_alive=True,
        get_location=lambda: [0.0, 0.0, 0.0, 0.0],
        model_base=SimpleNamespace(radius=[1.0, 1.0], base_type=SimpleNamespace(name="CIRCULAR")),
    )
    unit = SimpleNamespace(models=[model], movement=movement)
    return unit, model


def test_advance_distance_match_allows_tiny_replay_rounding_delta() -> None:
    unit, model = _unit_with_model()
    errors = _validate_movement_action_distance_match(
        SimpleNamespace(map=None),
        unit,
        [{"model_id": model.id, "position": [11.0005, 0.0, 0.0], "facing": 0.0}],
        movement_type="advance",
        ctx={"phase_name": "MOVEMENT_PHASE", "phase_step": "MOVE_UNITS", "max_distance": 11.0},
    )

    assert errors == ()


def test_advance_distance_match_rejects_real_overrun() -> None:
    unit, model = _unit_with_model()
    errors = _validate_movement_action_distance_match(
        SimpleNamespace(map=None),
        unit,
        [{"model_id": model.id, "position": [11.01, 0.0, 0.0], "facing": 0.0}],
        movement_type="advance",
        ctx={"phase_name": "MOVEMENT_PHASE", "phase_step": "MOVE_UNITS", "max_distance": 11.0},
    )

    assert errors
    assert "exceeding the selected Advance distance" in errors[0]
