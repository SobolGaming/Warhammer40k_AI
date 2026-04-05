from __future__ import annotations

from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import Map, RuinsTerrain
from warhammer40k_ai.pathing.api import PathQuery, plan_model_path
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.utility.calcs import MovementType
from warhammer40k_ai.utility.model_base import Base, BaseType


class _UnitStub:
    def __init__(self) -> None:
        self.name = "mover"
        self.faction = "A"
        self.models: list[Model] = []
        self.is_flying = False
        self.is_infantry = False
        self.is_beast = False
        self.is_imperium_primarch = False
        self.is_belisarius_cawl = False
        self.is_monster = False
        self.is_vehicle = False
        self.is_titanic = False
        self.deployed = True
        self.keywords: list[str] = []
        self.parent_army = self
        self.has_circular_base = True

    def get_parent_army(self):
        return self

    def is_alive(self) -> bool:
        return True

    def get_models_for_collision(self) -> list[Model]:
        return list(self.models)

    def has_super_heavy_walker(self) -> bool:
        return False


def _path_sweeps_into_wall(path: list[tuple[float, float, float]], model: Model, wall: Polygon) -> bool:
    for i in range(len(path) - 1):
        x0, y0, _ = path[i]
        x1, y1, _ = path[i + 1]
        for step in range(61):
            t = step / 60.0
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            if model.model_base.get_base_shape_at(x, y, model.model_base.facing).intersects(wall):
                return True
    return False


def unified_pathfinding(
    model,
    target,
    movement_type,
    max_distance,
    game_map,
    target_unit=None,
    target_units=None,
    moved_models_in_unit=None,
):
    if len(target) == 2:
        target_3d = (float(target[0]), float(target[1]), float(model.model_base.z))
    else:
        target_3d = (float(target[0]), float(target[1]), float(target[2]))
    return plan_model_path(
        PathQuery(
            model=model,
            target=target_3d,
            movement_type=movement_type,
            max_distance=float(max_distance),
            game_map=game_map,
            target_unit=target_unit,
            target_units=tuple(target_units or ()),
            moved_models_in_unit=tuple(moved_models_in_unit or ()),
        )
    ).to_legacy_dict()


def test_unified_pathfinding_avoids_segment_wall_crossing() -> None:
    game_map = Map(60, 44)
    footprint = Polygon([(0.0, 0.0), (60.0, 0.0), (60.0, 44.0), (0.0, 44.0)])
    wall = Polygon([(30.25, 10.0), (30.35, 10.0), (30.35, 34.0), (30.25, 34.0)])
    ruins = RuinsTerrain(
        footprint=footprint,
        walls=[{"polygon": wall, "z_bottom": 0.0, "z_top": 6.0, "thickness": 0.1}],
        openings=[],
        floors=[],
        height_map={},
    )
    game_map.add_terrain_feature(ruins)

    unit = _UnitStub()
    base = Base(BaseType.CIRCULAR, 0.1)
    model = Model("Mover", 12, 4, 3, 2, 6, 1, base)
    model.set_location(24.0, 22.0, 0.0, 0.0)
    model.parent_unit = unit
    unit.models = [model]
    game_map.units = [unit]

    result = unified_pathfinding(
        model=model,
        target=(32.0, 7.2, 0.0),
        movement_type=MovementType.MOVE,
        max_distance=30.0,
        game_map=game_map,
    )
    assert result["valid"] is True
    assert not _path_sweeps_into_wall(list(result["path"] or []), model, wall)
