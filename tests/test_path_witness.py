from __future__ import annotations

from shapely.geometry import Point, Polygon

from warhammer40k_ai.battlefield.map import RuinsTerrain
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.path_witness import (
    build_model_path_witness,
    current_model_positions,
    detect_normal_move_engagement_crossing,
    detect_terrain_sweep_collisions,
    validate_witness_contiguity,
)
from warhammer40k_ai.roster.player import Player


class _Base:
    def __init__(self, x: float, y: float, z: float = 0.0, facing: float = 0.0, radius: float = 0.5) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.facing = facing
        self._radius = radius

    def get_radius(self) -> float:
        return self._radius

    def get_base_shape(self):
        return Point(float(self.x), float(self.y)).buffer(float(self._radius), quad_segs=16)

    def get_base_shape_at(self, x: float, y: float, facing: float):
        return Point(float(x), float(y)).buffer(float(self._radius), quad_segs=16)

    def edge_to_edge_distance(self, other: "_Base") -> float:
        dx = float(self.x) - float(other.x)
        dy = float(self.y) - float(other.y)
        center = (dx * dx + dy * dy) ** 0.5
        return center - float(self._radius) - float(other._radius)


class _Model:
    def __init__(self, model_id: str, x: float, y: float) -> None:
        self._id = model_id
        self.model_base = _Base(x, y)
        self.is_alive = True
        self._movement = 8

    def get_location(self):
        return (self.model_base.x, self.model_base.y, self.model_base.z, self.model_base.facing)


class _Unit:
    def __init__(self, unit_id: str, model: _Model) -> None:
        self._id = unit_id
        self.id = unit_id
        self.name = unit_id
        self.models = [model]
        model.parent_unit = self
        self.deployed = True
        self.parent_army = None
        self.is_flying = False
        self.is_infantry = False
        self.is_beast = False
        self.is_imperium_primarch = False
        self.is_belisarius_cawl = False
        self.keywords: list[str] = []
        self.has_circular_base = True

    def get_parent_army(self):
        return self.parent_army

    def is_alive(self) -> bool:
        return True

    def has_super_heavy_walker(self) -> bool:
        return False


class _Army:
    def __init__(self, army_id: str, units: list[_Unit]) -> None:
        self._id = army_id
        self.id = army_id
        self.units = units
        self.player = None
        for unit in self.units:
            unit.parent_army = self

    def set_player(self, player: Player) -> None:
        self.player = player


def test_path_witness_contiguity_and_final_pose_validation() -> None:
    start_positions = [{"model_id": "m1", "position": [0.0, 0.0, 0.0], "facing": 0.0}]
    end_positions = [{"model_id": "m1", "position": [4.0, 0.0, 0.0], "facing": 0.0}]
    witness = build_model_path_witness(
        model_positions=end_positions,
        movement_type="move",
        start_positions=start_positions,
    )
    assert validate_witness_contiguity(witness, end_positions) == []

    broken = dict(witness)
    broken["models"] = [dict(witness["models"][0])]
    broken["models"][0]["final_pose"] = [5.0, 0.0, 0.0, 0.0]
    errors = validate_witness_contiguity(broken, end_positions)
    assert errors


def test_detect_normal_move_engagement_crossing() -> None:
    start_positions = [{"model_id": "m1", "position": [0.0, 0.0, 0.0], "facing": 0.0, "radius": 0.5}]
    end_positions = [{"model_id": "m1", "position": [4.0, 0.0, 0.0], "facing": 0.0, "radius": 0.5}]
    enemy_bases = [{"x": 2.0, "y": 0.0, "z": 0.0, "radius": 0.5}]
    errors = detect_normal_move_engagement_crossing(
        start_positions=start_positions,
        end_positions=end_positions,
        enemy_bases=enemy_bases,
    )
    assert errors


def test_detect_terrain_sweep_collisions_rejects_wall_crossing() -> None:
    start_positions = [
        {
            "model_id": "m1",
            "position": [0.0, 0.0, 0.0],
            "facing": 0.0,
            "radius": [0.5, 0.5],
            "base_type": "CIRCULAR",
        }
    ]
    end_positions = [
        {
            "model_id": "m1",
            "position": [4.0, 0.0, 0.0],
            "facing": 0.0,
            "radius": [0.5, 0.5],
            "base_type": "CIRCULAR",
        }
    ]
    wall = Polygon([(1.9, -1.0), (2.1, -1.0), (2.1, 1.0), (1.9, 1.0)])
    errors = detect_terrain_sweep_collisions(
        start_positions=start_positions,
        end_positions=end_positions,
        blocking_terrain_polygons=[wall],
    )
    assert errors


def test_move_validation_rejects_path_crossing_enemy_engagement() -> None:
    p1 = Player("P1")
    p2 = Player("P2")
    friendly_unit = _Unit("u1", _Model("m1", 0.0, 0.0))
    enemy_unit = _Unit("u2", _Model("em1", 2.0, 0.0))
    p1.army = _Army("a1", [friendly_unit])
    p2.army = _Army("a2", [enemy_unit])
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
    game.map.units = [friendly_unit, enemy_unit]

    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id=p1.id,
        options=[
            DecisionOption.create("Confirm", payload={"unit_id": friendly_unit.id, "movement_type": "move", "action": "confirm"}),
            DecisionOption.create("Skip", payload={"unit_id": friendly_unit.id, "movement_type": "move", "action": "skip"}),
        ],
        context={"unit_id": friendly_unit.id, "movement_type": "move"},
    )
    game.request_decision(request)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=p1.id,
        option_id=request.options[0].option_id,
        payload={
            "model_positions": [
                {"model_id": "m1", "position": [4.0, 0.0, 0.0], "facing": 0.0}
            ]
        },
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is False
    assert any("crosses engagement range" in str(err) for err in list(apply_result.errors or ()))


def test_move_validation_rejects_path_crossing_blocking_terrain() -> None:
    p1 = Player("P1")
    p2 = Player("P2")
    friendly_unit = _Unit("u1", _Model("m1", 24.0, 22.0))
    p1.army = _Army("a1", [friendly_unit])
    p2.army = _Army("a2", [])
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
    game.map.units = [friendly_unit]

    footprint = Polygon([(0.0, 0.0), (60.0, 0.0), (60.0, 44.0), (0.0, 44.0)])
    wall = Polygon([(30.25, 10.0), (30.35, 10.0), (30.35, 34.0), (30.25, 34.0)])
    ruins = RuinsTerrain(
        footprint=footprint,
        walls=[{"polygon": wall, "z_bottom": 0.0, "z_top": 6.0, "thickness": 0.1}],
        openings=[],
        floors=[],
        height_map={},
    )
    game.map.add_terrain_feature(ruins)

    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id=p1.id,
        options=[
            DecisionOption.create("Confirm", payload={"unit_id": friendly_unit.id, "movement_type": "move", "action": "confirm"}),
            DecisionOption.create("Skip", payload={"unit_id": friendly_unit.id, "movement_type": "move", "action": "skip"}),
        ],
        context={"unit_id": friendly_unit.id, "movement_type": "move"},
    )
    game.request_decision(request)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=p1.id,
        option_id=request.options[0].option_id,
        payload={
            "model_positions": [
                {
                    "model_id": "m1",
                    "position": [32.0, 7.2, 0.0],
                    "facing": 0.0,
                }
            ]
        },
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is False
    assert any("crosses blocking terrain" in str(err) for err in list(apply_result.errors or ()))
