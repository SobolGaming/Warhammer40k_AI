from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import (
    _apply_select_movement_action,
    _apply_move_unit,
    _validate_move_unit,
    _validate_select_movement_action,
)
from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT, DECISION_SELECT_MOVEMENT_ACTION
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.units.unit import MovementAction


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

    def _execute_action(self, action, destination, game_map):
        del destination, game_map
        if action != MovementAction.REMAIN_STATIONARY.value:
            raise ValueError(f"Invalid action: {action}")
        self.round_state.remained_stationary_this_round = True
        return True

    def is_alive(self) -> bool:
        return True

    def validate_charge_end_state(self, target_units, game_map) -> tuple[bool, str]:
        for target_unit in list(target_units or []):
            if not game_map.is_within_engagement_range(self, target_unit):
                return False, "not in engagement range"
        return True, ""


class _ArmyStub:
    def __init__(self, unit: _UnitStub) -> None:
        self.units = [unit]


class _PlayerStub:
    def __init__(self, army: _ArmyStub) -> None:
        self.army = army


class _GameStub:
    def __init__(self, unit: _UnitStub, enemy_unit: _UnitStub | None = None) -> None:
        friendly_army = _ArmyStub(unit)
        enemy_army = _ArmyStub(enemy_unit) if enemy_unit is not None else _ArmyStub(unit)
        unit.parent_army = friendly_army
        if enemy_unit is not None:
            enemy_unit.parent_army = enemy_army
        self.players = [_PlayerStub(friendly_army), _PlayerStub(enemy_army)]
        self.map = SimpleNamespace(
            units=[member for member in [unit, enemy_unit] if member is not None],
            is_within_engagement_range=lambda lhs, rhs: abs(lhs.models[0].get_location()[0] - rhs.models[0].get_location()[0]) <= 1.0,
            get_enemy_units=lambda moving_unit: [candidate for candidate in [enemy_unit] if candidate is not None and candidate is not moving_unit],
        )


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


def _build_move_skip_request(unit: _UnitStub, movement_type: str) -> tuple[DecisionRequest, DecisionResult]:
    option = DecisionOption.create(
        "Skip",
        payload={"unit_id": unit.id, "movement_type": movement_type, "action": "skip"},
    )
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id="player-1",
        options=[option],
        context={
            "unit_id": unit.id,
            "movement_type": movement_type,
            "phase_name": "MOVEMENT_PHASE",
            "phase_step": "MOVE_UNITS",
            "allow_skip": True,
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=option.option_id,
        payload={"action": "skip"},
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


def test_apply_move_unit_skip_after_advance_consumes_movement_activation() -> None:
    model = _ModelStub("model-skip-advance")
    unit = _UnitStub("unit-skip-advance", model)
    game = _GameStub(unit)
    request, result = _build_move_skip_request(unit, "advance")

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


def test_apply_select_movement_action_executes_stationary_with_enum_value() -> None:
    model = _ModelStub("model-4")
    unit = _UnitStub("unit-4", model)
    game = _GameStub(unit)
    option = DecisionOption.create(
        "Remain Stationary",
        payload={"unit_id": unit.id, "action_type": "stationary"},
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

    _apply_select_movement_action(game, request, result)

    assert unit.round_state.remained_stationary_this_round is True


def test_validate_move_unit_charge_uses_proposed_model_positions() -> None:
    model = _ModelStub("model-5")
    enemy_model = _ModelStub("enemy-model-1")
    unit = _UnitStub("unit-5", model)
    enemy = _UnitStub("enemy-5", enemy_model)
    enemy_model.set_location(4.0, 0.0, 0.0, 0.0)
    game = _GameStub(unit, enemy)
    option = DecisionOption.create(
        "Confirm",
        payload={"unit_id": unit.id, "movement_type": "charge", "action": "confirm"},
    )
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Charge unit",
        player_id="player-1",
        options=[option],
        context={"unit_id": unit.id, "movement_type": "charge", "target_unit_ids": [enemy.id]},
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=option.option_id,
        payload={
            "model_positions": [
                {
                    "model_id": unit.models[0]._id,
                    "position": [3.0, 0.0, 0.0],
                    "facing": 0.0,
                }
            ]
        },
    )

    errors = _validate_move_unit(game, request, result)

    assert errors == ()
