from __future__ import annotations

from dataclasses import dataclass

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.engine.movement_intent import MovementIntent
from warhammer40k_ai.engine.movement_solver import generate_move_unit_candidates
from warhammer40k_ai.engine.path_witness import PathWitnessStore
from warhammer40k_ai.engine.time_manager import TimeManager


@dataclass
class _GameStub:
    time_manager: TimeManager


class _BaseStub:
    has_circular_base = True

    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.facing = 0.0

    def get_radius(self) -> float:
        return 0.5


class _WeaponStub:
    def __init__(self, *, melee: bool, ranged: bool) -> None:
        self._melee = bool(melee)
        self._ranged = bool(ranged)

    def is_melee(self) -> bool:
        return bool(self._melee)

    def is_ranged(self) -> bool:
        return bool(self._ranged)


class _ModelStub:
    def __init__(self, model_id: str, *, x: float, y: float, melee: bool, ranged: bool) -> None:
        self.id = model_id
        self._id = model_id
        self.model_base = _BaseStub(x, y)
        self.wargear = [_WeaponStub(melee=melee, ranged=ranged)]
        self.is_alive = True

    def get_location(self):
        return (self.model_base.x, self.model_base.y, self.model_base.z, self.model_base.facing)

    def set_location(self, x: float, y: float, z: float, facing: float) -> None:
        self.model_base.x = float(x)
        self.model_base.y = float(y)
        self.model_base.z = float(z)
        self.model_base.facing = float(facing)


class _ArmyStub:
    def __init__(self, units) -> None:
        self.units = list(units)


class _UnitStub:
    def __init__(self, unit_id: str, models, army=None) -> None:
        self.id = unit_id
        self._id = unit_id
        self.models = list(models)
        self.parent_army = army
        for model in self.models:
            model.parent_unit = self

    def get_parent_army(self):
        return self.parent_army

    def validate_charge_end_state(self, target_units, game_map) -> tuple[bool, str]:
        for target_unit in list(target_units or []):
            if not game_map.is_within_engagement_range(self, target_unit):
                return False, "not in engagement range"
        return True, ""


class _PlayerStub:
    def __init__(self, army) -> None:
        self.army = army

    def get_army(self):
        return self.army


class _MapStub:
    @staticmethod
    def get_height_at_point(_x: float, _y: float) -> float:
        return 0.0

    @staticmethod
    def is_within_engagement_range(lhs, rhs) -> bool:
        lhs_pos = lhs.models[0].get_location()
        rhs_pos = rhs.models[0].get_location()
        return abs(float(lhs_pos[0]) - float(rhs_pos[0])) <= 1.0 and abs(float(lhs_pos[1]) - float(rhs_pos[1])) <= 1.0


@dataclass
class _LiveGameStub:
    time_manager: TimeManager
    path_witness_store: PathWitnessStore
    players: list[object]
    map: object
    objectives: list[object]

    def _find_charge_destination(self, _charging_unit, target_unit, *, max_distance: float):
        target_x, target_y, target_z, *_rest = target_unit.models[0].get_location()
        return (float(target_x) - min(float(max_distance), 1.0), float(target_y), float(target_z))


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


def test_move_solver_generates_actual_forward_translation_for_melee_unit() -> None:
    mover_model = _ModelStub("model:mover", x=0.0, y=0.0, melee=True, ranged=False)
    enemy_model = _ModelStub("model:enemy", x=20.0, y=0.0, melee=False, ranged=True)
    mover_army = _ArmyStub([])
    enemy_army = _ArmyStub([])
    mover_unit = _UnitStub("unit:mover", [mover_model], army=mover_army)
    enemy_unit = _UnitStub("unit:enemy", [enemy_model], army=enemy_army)
    mover_army.units = [mover_unit]
    enemy_army.units = [enemy_unit]
    objective = type("ObjectiveStub", (), {"location": type("LocationStub", (), {"x": -10.0, "y": 0.0})()})()
    game = _LiveGameStub(
        time_manager=TimeManager(),
        path_witness_store=PathWitnessStore(),
        players=[_PlayerStub(mover_army), _PlayerStub(enemy_army)],
        map=_MapStub(),
        objectives=[objective],
    )
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id="player-1",
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": "unit:mover", "movement_type": "move", "action": "confirm"},
            ),
            DecisionOption.create(
                "Skip",
                payload={"unit_id": "unit:mover", "movement_type": "move", "action": "skip"},
            ),
        ],
        context={
            "unit_id": "unit:mover",
            "movement_type": "move",
            "max_distance": 6.0,
        },
    )
    intent = MovementIntent.from_context(request.context)

    candidates, mask, wall_clock_ms, fallback_mode = generate_move_unit_candidates(game, request, intent)

    assert fallback_mode is False
    assert wall_clock_ms >= 0
    assert mask == [True, True]
    confirm_candidate = next(candidate for candidate in candidates if dict(candidate.params or {}).get("action") == "confirm")
    model_positions = list(dict(confirm_candidate.params or {}).get("model_positions", []) or [])
    assert model_positions
    pos = list(model_positions[0].get("position", []) or [])
    assert len(pos) >= 2
    assert float(pos[0]) != 0.0
    metadata = dict(confirm_candidate.metadata or {})
    assert float(metadata.get("movement_distance_inches", 0.0) or 0.0) > 0.0
    assert (
        float(metadata.get("distance_to_enemy_delta", 0.0) or 0.0) > 0.0
        or float(metadata.get("distance_to_objective_delta", 0.0) or 0.0) > 0.0
    )
    assert str(metadata.get("path_witness_ref", "") or "").startswith("pathwitness://")


def test_move_solver_generates_targeted_charge_candidate_reaching_engagement_range() -> None:
    mover_model = _ModelStub("model:mover", x=0.0, y=0.0, melee=True, ranged=False)
    enemy_model = _ModelStub("model:enemy", x=11.0, y=0.0, melee=False, ranged=True)
    mover_army = _ArmyStub([])
    enemy_army = _ArmyStub([])
    mover_unit = _UnitStub("unit:mover", [mover_model], army=mover_army)
    enemy_unit = _UnitStub("unit:enemy", [enemy_model], army=enemy_army)
    mover_army.units = [mover_unit]
    enemy_army.units = [enemy_unit]
    game = _LiveGameStub(
        time_manager=TimeManager(),
        path_witness_store=PathWitnessStore(),
        players=[_PlayerStub(mover_army), _PlayerStub(enemy_army)],
        map=_MapStub(),
        objectives=[],
    )
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Charge unit",
        player_id="player-1",
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": "unit:mover", "movement_type": "charge", "action": "confirm"},
            ),
            DecisionOption.create(
                "Skip",
                payload={"unit_id": "unit:mover", "movement_type": "charge", "action": "skip"},
            ),
        ],
        context={
            "unit_id": "unit:mover",
            "movement_type": "charge",
            "max_distance": 12.0,
            "target_unit_ids": ["unit:enemy"],
        },
    )
    intent = MovementIntent.from_context(request.context)

    candidates, mask, wall_clock_ms, fallback_mode = generate_move_unit_candidates(game, request, intent)

    assert fallback_mode is False
    assert wall_clock_ms >= 0
    assert mask == [True, True]
    confirm_candidate = next(candidate for candidate in candidates if dict(candidate.params or {}).get("action") == "confirm")
    metadata = dict(confirm_candidate.metadata or {})
    assert metadata.get("candidate_kind") == "charge"
    model_positions = list(dict(confirm_candidate.params or {}).get("model_positions", []) or [])
    assert len(model_positions) == 1
    position = list(model_positions[0].get("position", []) or [])
    assert len(position) >= 2
    assert abs(float(position[0]) - 10.0) <= 1e-6
    assert float(metadata.get("distance_to_enemy_delta", 0.0) or 0.0) > 0.0


def test_move_solver_charge_prefers_heuristic_endpoint_before_routed_search() -> None:
    mover_model = _ModelStub("model:mover", x=0.0, y=0.0, melee=True, ranged=False)
    enemy_model = _ModelStub("model:enemy", x=11.0, y=0.0, melee=False, ranged=True)
    mover_army = _ArmyStub([])
    enemy_army = _ArmyStub([])
    mover_unit = _UnitStub("unit:mover", [mover_model], army=mover_army)
    enemy_unit = _UnitStub("unit:enemy", [enemy_model], army=enemy_army)
    mover_army.units = [mover_unit]
    enemy_army.units = [enemy_unit]
    game = _LiveGameStub(
        time_manager=TimeManager(),
        path_witness_store=PathWitnessStore(),
        players=[_PlayerStub(mover_army), _PlayerStub(enemy_army)],
        map=_MapStub(),
        objectives=[],
    )

    def _should_not_be_called(*_args, **_kwargs):
        raise AssertionError("_find_charge_destination should not be needed for a simple heuristic charge.")

    game._find_charge_destination = _should_not_be_called
    game._iter_charge_destination_candidates = lambda *_args, **_kwargs: [(10.0, 0.0, 0.0)]
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Charge unit",
        player_id="player-1",
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": "unit:mover", "movement_type": "charge", "action": "confirm"},
            ),
            DecisionOption.create(
                "Skip",
                payload={"unit_id": "unit:mover", "movement_type": "charge", "action": "skip"},
            ),
        ],
        context={
            "unit_id": "unit:mover",
            "movement_type": "charge",
            "max_distance": 12.0,
            "target_unit_ids": ["unit:enemy"],
        },
    )
    intent = MovementIntent.from_context(request.context)

    candidates, mask, wall_clock_ms, fallback_mode = generate_move_unit_candidates(game, request, intent)

    assert fallback_mode is False
    assert wall_clock_ms >= 0
    assert mask == [True, True]
    confirm_candidate = next(candidate for candidate in candidates if dict(candidate.params or {}).get("action") == "confirm")
    metadata = dict(confirm_candidate.metadata or {})
    assert metadata.get("candidate_kind") == "charge"
    assert metadata.get("candidate_source") == "heuristic_endpoint"
