from __future__ import annotations

import pytest
from shapely.geometry import Point

from warhammer40k_ai.battlefield.map import Map, TerrainFactory
from warhammer40k_ai.engine.deployment_headless import DeterministicDeploymentDecisionMaker


class _StubBase:
    has_circular_base = True

    def __init__(self, radius: float = 0.5) -> None:
        self._radius = float(radius)
        self.facing = 0.0

    def get_radius(self) -> float:
        return float(self._radius)

    def get_base_shape_at(self, x: float, y: float, facing: float):
        return Point(float(x), float(y)).buffer(self._radius)


class _StubModel:
    def __init__(self, model_id: str) -> None:
        self._id = model_id
        self.id = model_id
        self.model_base = _StubBase(radius=0.5)


class _StubUnit:
    def __init__(
        self,
        unit_id: str,
        *,
        must_start_in_reserves: bool,
        infiltrate: bool = False,
        map_obj: object | None = None,
    ) -> None:
        self._id = unit_id
        self.id = unit_id
        self._must_start_in_reserves = bool(must_start_in_reserves)
        self._infiltrate = bool(infiltrate)
        self._map = map_obj
        self.models = [_StubModel(f"{unit_id}:model")]
        self.name = f"Unit {unit_id}"
        self._army = type("ArmyLink", (), {"player": type("PlayerLink", (), {"id": "player:1"})()})()

    def must_start_in_reserves(self) -> bool:
        return bool(self._must_start_in_reserves)

    def has_infiltrate(self) -> bool:
        return bool(self._infiltrate)

    def get_parent_army(self):
        return self._army

    def calculate_model_positions(self, x, y, game_map, avoid_friendly_units=False, boundary_repulsors=None):
        use_map = self._map if self._map is not None else game_map
        z = float(use_map.get_height_at_point(float(x), float(y))) if use_map is not None else 0.0
        return [(float(x), float(y), z, 0.0)]


class _StubArmy:
    def __init__(self, units) -> None:
        self.units = list(units)
        self.validated_payload = None

    def validate_reserves_decisions(self, decisions):
        self.validated_payload = dict(decisions)
        return {"valid": True}


class _StubPlayer:
    def __init__(self, army) -> None:
        self._army = army

    def get_army(self):
        return self._army


class _ZoneStub:
    def __init__(self, min_x: float, max_x: float, min_y: float, max_y: float) -> None:
        self.vertices = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
        self.min_x = float(min_x)
        self.max_x = float(max_x)
        self.min_y = float(min_y)
        self.max_y = float(max_y)

    def contains_point(self, x: float, y: float) -> bool:
        return self.min_x <= float(x) <= self.max_x and self.min_y <= float(y) <= self.max_y


def test_forced_only_reserve_policy_keeps_optional_units_deployed() -> None:
    required = _StubUnit("unit:required", must_start_in_reserves=True)
    optional = _StubUnit("unit:optional", must_start_in_reserves=False)
    army = _StubArmy([required, optional])
    player = _StubPlayer(army)

    maker = DeterministicDeploymentDecisionMaker(game=object(), reserve_policy="forced_only")
    decisions = maker.declare_reserves(player)

    assert decisions == {
        "unit:required": "reserves",
        "unit:optional": "deploy",
    }
    assert army.validated_payload == decisions


def test_invalid_reserve_policy_raises_value_error() -> None:
    with pytest.raises(ValueError):
        DeterministicDeploymentDecisionMaker(game=object(), reserve_policy="unknown_policy")


def test_infiltrators_can_search_outside_assigned_deployment_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FlatMap:
        @staticmethod
        def get_height_at_point(_x: float, _y: float) -> float:
            return 0.0

    unit = _StubUnit("unit:infil", must_start_in_reserves=False, infiltrate=True, map_obj=_FlatMap())

    class _StubGame:
        def __init__(self) -> None:
            self.map = object()
            self.battlefield = type("BF", (), {"width": 60.0, "height": 44.0})()

        def is_valid_deployment_position(self, _unit, x: float, _y: float, _player_id: str) -> bool:
            return float(x) > 20.0

    game = _StubGame()
    maker = DeterministicDeploymentDecisionMaker(game=game)
    zone = {"name": "assigned", "mission_zones": [_ZoneStub(0.0, 10.0, 0.0, 44.0)]}

    # Isolate candidate-generation behavior from the full movement/deployment validator stack.
    monkeypatch.setattr("warhammer40k_ai.engine.deployment_headless.validate_decision", lambda *_args, **_kwargs: ())

    x, y = maker.choose_unit_deployment_position(unit, zone, already_deployed=[])
    assert float(x) > 20.0
    assert 0.0 <= float(y) <= 44.0


def test_headless_builder_prefers_upper_ruins_floor_for_single_model() -> None:
    game_map = Map(width=60, height=44)
    ruins = TerrainFactory.create_ruins(
        [(3.0, 18.0), (9.0, 18.0), (9.0, 26.0), (3.0, 26.0)],
        wall_height=4.0,
        num_floors=2,
    )
    game_map.add_terrain_feature(ruins)

    unit = _StubUnit("unit:ruins", must_start_in_reserves=False, infiltrate=False, map_obj=game_map)

    class _StubGame:
        def __init__(self, map_obj: Map) -> None:
            self.map = map_obj
            self.battlefield = type("BF", (), {"width": 60.0, "height": 44.0})()

    maker = DeterministicDeploymentDecisionMaker(game=_StubGame(game_map))
    payload = maker.build_deployment_model_positions(unit, (6.0, 22.0))

    assert payload
    pos = list(payload[0].get("position", []) or [])
    assert len(pos) >= 3
    # Ground floor in this engine is 0.12"; upper floors are 4.12" and 8.12".
    assert float(pos[2]) >= 4.12


def test_chosen_floor_payload_is_cached_for_deployment_manager_consumption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game_map = Map(width=60, height=44)
    ruins = TerrainFactory.create_ruins(
        [(3.0, 18.0), (9.0, 18.0), (9.0, 26.0), (3.0, 26.0)],
        wall_height=4.0,
        num_floors=2,
    )
    game_map.add_terrain_feature(ruins)

    unit = _StubUnit("unit:cached", must_start_in_reserves=False, infiltrate=False, map_obj=game_map)
    zone = {"name": "assigned", "mission_zones": [_ZoneStub(0.0, 10.0, 0.0, 44.0)]}

    class _StubGame:
        def __init__(self, map_obj: Map) -> None:
            self.map = map_obj
            self.battlefield = type("BF", (), {"width": 60.0, "height": 44.0})()

        def is_valid_deployment_position(self, _unit, _x: float, _y: float, _player_id: str) -> bool:
            return True

    # Force acceptance only for elevated placements so choose() must cache an upper-floor payload.
    def _validate_floor_only(_game, _request, result):
        model_positions = list((result.payload or {}).get("model_positions", []) or [])
        if not model_positions:
            return ("missing model_positions",)
        pos = list(model_positions[0].get("position", []) or [])
        if len(pos) < 3:
            return ("missing z",)
        return () if float(pos[2]) >= 4.12 else ("ground floor rejected for test",)

    monkeypatch.setattr("warhammer40k_ai.engine.deployment_headless.validate_decision", _validate_floor_only)

    maker = DeterministicDeploymentDecisionMaker(game=_StubGame(game_map))
    anchor = maker.choose_unit_deployment_position(unit, zone, already_deployed=[])
    payload = maker.build_deployment_model_positions(unit, anchor)
    assert payload
    pos = list(payload[0].get("position", []) or [])
    assert len(pos) >= 3
    assert float(pos[2]) >= 4.12
