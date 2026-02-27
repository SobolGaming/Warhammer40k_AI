from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import (
    _apply_move_unit,
    _validate_select_movement_action,
)
from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT, DECISION_SELECT_MOVEMENT_ACTION
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult


class _ModelStub:
    def __init__(self, model_id: str) -> None:
        self._id = model_id
        self.is_alive = True
        self.model_base = SimpleNamespace(z=0.0, facing=0.0)
        self._location = (0.0, 0.0, 0.0, 0.0)
        self.parent_unit = None

    def set_location(self, x: float, y: float, z: float, facing: float) -> None:
        self._location = (float(x), float(y), float(z), float(facing))
        self.model_base.z = float(z)
        self.model_base.facing = float(facing)

    def get_location(self):
        return self._location


class _UnitStub:
    def __init__(self, unit_id: str, model: _ModelStub) -> None:
        self._id = unit_id
        self.id = unit_id
        self.name = "Movement Test Unit"
        self.models = [model]
        model.parent_unit = self
        self.special_rules = {}
        self.round_state = SimpleNamespace(
            moved_this_round=False,
            remained_stationary_this_round=True,
            advanced_this_round=False,
            fell_back_this_round=False,
            move_modifier_choice=None,
            move_modifier_choice_pending=False,
            advance_modifier_choice=None,
            advance_modifier_choice_pending=False,
            charge_modifier_choice=None,
            charge_modifier_choice_pending=False,
            charge_modifier_choice_targets=[],
        )

    def get_attached_unit_members(self):
        return [self]


class _ArmyStub:
    def __init__(self, unit: _UnitStub) -> None:
        self.units = [unit]


class _PlayerStub:
    def __init__(self, army: _ArmyStub) -> None:
        self.army = army


class _GameStub:
    def __init__(self, unit: _UnitStub) -> None:
        self.players = [_PlayerStub(_ArmyStub(unit))]
        self.map = SimpleNamespace(units=[unit])


def _build_move_request(unit: _UnitStub, movement_type: str) -> tuple[DecisionRequest, DecisionResult]:
    option = DecisionOption.create(
        "Confirm",
        payload={"unit_id": unit.id, "movement_type": movement_type, "action": "confirm"},
    )
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id="player-1",
        options=[option],
        context={"unit_id": unit.id, "movement_type": movement_type},
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=option.option_id,
        payload={
            "model_positions": [
                {
                    "model_id": unit.models[0]._id,
                    "position": [3.0, 4.0, 0.0],
                    "facing": 0.0,
                }
            ]
        },
    )
    return request, result


def test_apply_move_unit_marks_advance_as_moved() -> None:
    model = _ModelStub("model-1")
    unit = _UnitStub("unit-1", model)
    game = _GameStub(unit)
    request, result = _build_move_request(unit, "advance")

    _apply_move_unit(game, request, result)

    assert unit.round_state.advanced_this_round is True
    assert unit.round_state.moved_this_round is True
    assert unit.round_state.remained_stationary_this_round is False


def test_apply_move_unit_marks_fall_back_as_moved() -> None:
    model = _ModelStub("model-2")
    unit = _UnitStub("unit-2", model)
    game = _GameStub(unit)
    request, result = _build_move_request(unit, "fall_back")

    _apply_move_unit(game, request, result)

    assert unit.round_state.fell_back_this_round is True
    assert unit.round_state.moved_this_round is True
    assert unit.round_state.remained_stationary_this_round is False


def test_validate_select_movement_action_rejects_unit_that_already_advanced() -> None:
    model = _ModelStub("model-3")
    unit = _UnitStub("unit-3", model)
    unit.round_state.advanced_this_round = True
    game = _GameStub(unit)
    option = DecisionOption.create(
        "Move",
        payload={"unit_id": unit.id, "action_type": "move"},
    )
    request = DecisionRequest.create(
        DECISION_SELECT_MOVEMENT_ACTION,
        "Select movement action",
        player_id="player-1",
        options=[option],
        context={"unit_id": unit.id},
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=option.option_id,
        payload={},
    )

    errors = _validate_select_movement_action(game, request, result)

    assert errors
    assert "already advanced" in str(errors[0]).lower()
