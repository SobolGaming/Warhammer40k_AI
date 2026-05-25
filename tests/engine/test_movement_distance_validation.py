from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import _validate_movement_action_distance_match
from warhammer40k_ai.engine.movement_distance import movement_distance_profile


def _unit_with_model(*, movement: float = 6.0):
    model = SimpleNamespace(
        id="model-1",
        is_alive=True,
        get_location=lambda: [0.0, 0.0, 0.0, 0.0],
        model_base=SimpleNamespace(radius=[1.0, 1.0], base_type=SimpleNamespace(name="CIRCULAR")),
    )
    unit = SimpleNamespace(models=[model], movement=movement, has_circular_base=True)
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


def test_advance_distance_match_allows_small_surface_replay_delta() -> None:
    unit, model = _unit_with_model()
    errors = _validate_movement_action_distance_match(
        SimpleNamespace(map=None),
        unit,
        [{"model_id": model.id, "position": [11.004, 0.0, 0.0], "facing": 0.0}],
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


def test_movement_distance_profile_uses_3d_displacement() -> None:
    unit, model = _unit_with_model(movement=12.0)

    profile = movement_distance_profile(
        unit,
        [{"model_id": model.id, "position": [3.0, 4.0, 12.0], "facing": 0.0}],
    )

    assert round(profile.max_distance, 3) == 13.0


def test_movement_distance_profile_adds_pivot_cost_for_pivoted_non_round_base() -> None:
    unit, model = _unit_with_model(movement=12.0)
    unit.has_circular_base = False

    profile = movement_distance_profile(
        unit,
        [{"model_id": model.id, "position": [3.0, 4.0, 0.0], "facing": 90.0}],
    )

    assert profile.entries[0].pivoted is True
    assert profile.entries[0].pivot_cost == 1.0
    assert profile.entries[0].displacement == 5.0
    assert profile.max_distance == 6.0
