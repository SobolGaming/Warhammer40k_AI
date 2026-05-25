from __future__ import annotations

from types import SimpleNamespace

from shapely.geometry import box

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
        if hasattr(self.model_base, "x"):
            self.model_base.x = float(x)
        if hasattr(self.model_base, "y"):
            self.model_base.y = float(y)
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
        self.movement = 12
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


class _SquareBase:
    def __init__(self, radius: float = 0.5) -> None:
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.facing = 0.0
        self.radius = [float(radius), float(radius)]
        self.base_type = SimpleNamespace(name="RECTANGULAR")

    def get_base_shape_at(self, x: float, y: float, _facing: float):
        return box(float(x) - self.radius[0], float(y) - self.radius[1], float(x) + self.radius[0], float(y) + self.radius[1])

    def get_radius(self) -> float:
        return float(max(self.radius))


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
            terrain_features=[],
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


def _movement_phase_move_validation(
    unit: _UnitStub,
    *,
    movement_type: str,
    destination_x: float,
    max_distance: float,
) -> tuple[DecisionRequest, DecisionResult]:
    option = DecisionOption.create(
        "Confirm",
        payload={"unit_id": unit.id, "movement_type": movement_type, "action": "confirm"},
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
            "max_distance": max_distance,
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=option.option_id,
        payload={
            "model_positions": [
                {
                    "model_id": unit.models[0]._id,
                    "position": [float(destination_x), 0.0, 0.0],
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


def test_validate_move_unit_rejects_advance_when_normal_move_reaches_endpoint() -> None:
    model = _ModelStub("model-short-advance")
    unit = _UnitStub("unit-short-advance", model)
    game = _GameStub(unit)
    request, result = _movement_phase_move_validation(
        unit,
        movement_type="advance",
        destination_x=10.0,
        max_distance=18.0,
    )

    errors = _validate_move_unit(game, request, result)

    assert errors
    assert "advance selected" in str(errors[0]).lower()
    assert "normal move" in str(errors[0]).lower()


def test_validate_move_unit_rejects_normal_move_beyond_normal_distance() -> None:
    model = _ModelStub("model-long-normal")
    unit = _UnitStub("unit-long-normal", model)
    game = _GameStub(unit)
    request, result = _movement_phase_move_validation(
        unit,
        movement_type="move",
        destination_x=13.0,
        max_distance=12.0,
    )

    errors = _validate_move_unit(game, request, result)

    assert errors
    assert "normal move selected" in str(errors[0]).lower()
    assert "exceeding" in str(errors[0]).lower()


def test_validate_move_unit_allows_advance_only_when_endpoint_exceeds_normal_distance() -> None:
    model = _ModelStub("model-long-advance")
    unit = _UnitStub("unit-long-advance", model)
    game = _GameStub(unit)
    request, result = _movement_phase_move_validation(
        unit,
        movement_type="advance",
        destination_x=13.0,
        max_distance=18.0,
    )

    errors = _validate_move_unit(game, request, result)

    assert errors == ()


def test_validate_move_unit_rejects_final_ruins_wall_overlap() -> None:
    model = _ModelStub("model-wall-overlap")
    model.model_base = _SquareBase(radius=0.5)
    model.set_location(0.0, 1.0, 0.0, 0.0)
    unit = _UnitStub("unit-wall-overlap", model)
    game = _GameStub(unit)
    game.map.terrain_features = [
        SimpleNamespace(
            terrain_type=SimpleNamespace(name="RUINS"),
            footprint=box(2.0, 0.0, 4.0, 3.0),
            walls=[{"polygon": box(2.75, 0.0, 3.25, 3.0), "z_bottom": 0.0, "z_top": 5.0}],
        )
    ]
    request, result = _movement_phase_move_validation(
        unit,
        movement_type="move",
        destination_x=3.0,
        max_distance=12.0,
    )
    result.payload["model_positions"][0]["position"] = [3.0, 1.0, 0.0]

    errors = _validate_move_unit(game, request, result)

    assert errors
    assert "ruins wall" in str(errors[0]).lower()


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


def test_apply_select_movement_action_does_not_store_pre_roll_advance_endpoint() -> None:
    model = _ModelStub("model-advance-plan")
    unit = _UnitStub("unit-advance-plan", model)
    game = _GameStub(unit)
    option = DecisionOption.create(
        "Advance",
        payload={"unit_id": unit.id, "action_type": "advance"},
    )
    request = DecisionRequest.create(
        DECISION_SELECT_MOVEMENT_ACTION,
        "Select movement action",
        player_id="player-1",
        options=[option],
        context={"unit_id": unit.id},
    )
    setattr(request, "_resolution_in_progress", True)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=option.option_id,
        payload={
            "planned_model_positions": [
                {"model_id": model._id, "position": [18.0, 0.0, 0.0], "facing": 0.0}
            ],
            "planned_movement_distance_inches": 18.0,
        },
    )

    _apply_select_movement_action(game, request, result)

    assert unit.round_state.planned_movement_type is None
    assert unit.round_state.planned_movement_model_positions is None
    assert unit.round_state.planned_movement_distance_inches is None


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
