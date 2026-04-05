from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import RuinsTerrain, validate_ruins_placement
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.utility.calcs import (
    MovementType,
    can_end_move_on_terrain,
    can_traverse_freely,
    get_terrain_blocking_polygons,
    is_terrain_impassable,
)
from warhammer40k_ai.utility.constants import RUINS_FLOOR_HEIGHT, RUINS_FLOOR_THICKNESS
from warhammer40k_ai.utility.model_base import Base, BaseType


class _UnitStub:
    def __init__(self, *, can_access_upper=True, flying=False, super_heavy=False):
        self._can_access_upper = can_access_upper
        self.is_flying = flying
        self._super_heavy = super_heavy
        self.is_infantry = False
        self.is_beast = False
        self.is_imperium_primarch = False
        self.is_belisarius_cawl = False
        self.keywords = []

    def can_access_upper_floors(self) -> bool:
        return self._can_access_upper

    def has_super_heavy_walker(self) -> bool:
        return self._super_heavy


def _make_model(radius=1.0, height=2.0) -> Model:
    base = Base(BaseType.CIRCULAR, radius)
    base.set_model_height(height)
    model = Model(
        name="Test",
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=6,
        objective_control=1,
        model_base=base,
    )
    model.set_location(0.0, 0.0, 0.0, 0.0)
    return model


def _make_basic_ruins() -> RuinsTerrain:
    footprint = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    floors = [{
        "polygon": footprint,
        "elevation": 0.0,
        "thickness": RUINS_FLOOR_THICKNESS,
    }]
    return RuinsTerrain(footprint=footprint, walls=[], openings=[], floors=floors, height_map={})


def test_ruins_ground_floor_toe_in_is_legal():
    unit = _UnitStub()
    ruins = _make_basic_ruins()
    model = _make_model(radius=1.0)

    result = validate_ruins_placement(
        unit,
        (9.5, 5.0, RUINS_FLOOR_THICKNESS),
        [ruins],
        moving_model=model,
    )

    assert result["valid"]
    assert result["floor_level"] == 0


def test_ruins_ground_floor_toe_in_can_end_move():
    unit = _UnitStub()
    ruins = _make_basic_ruins()
    model = _make_model(radius=1.0)
    model.parent_unit = unit
    model.set_location(9.5, 5.0, RUINS_FLOOR_THICKNESS, 0.0)

    assert can_end_move_on_terrain(model, ruins)


def test_ruins_upper_floor_overhang_is_rejected():
    unit = _UnitStub(can_access_upper=True)
    footprint = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    floors = [
        {"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS},
        {"polygon": footprint, "elevation": RUINS_FLOOR_HEIGHT, "thickness": RUINS_FLOOR_THICKNESS},
    ]
    ruins = RuinsTerrain(footprint=footprint, walls=[], openings=[], floors=floors, height_map={})
    model = _make_model(radius=1.0)

    result = validate_ruins_placement(
        unit,
        (9.5, 5.0, RUINS_FLOOR_HEIGHT + RUINS_FLOOR_THICKNESS),
        [ruins],
        moving_model=model,
    )

    assert not result["valid"]
    assert "overhang" in result.get("reason", "").lower()


def test_ruins_low_walls_do_not_block_path():
    unit = _UnitStub()
    footprint = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
    low_wall = Polygon([(2, 0.2), (2.2, 0.2), (2.2, 3.0), (2, 3.0)])
    ruins = RuinsTerrain(
        footprint=footprint,
        walls=[{"polygon": low_wall, "z_bottom": 0.0, "z_top": 2.0, "thickness": 0.2}],
        openings=[],
        floors=[],
        height_map={},
    )

    assert can_traverse_freely(unit, ruins)
    assert get_terrain_blocking_polygons(unit, ruins) == []


def test_ruins_super_heavy_walker_ignores_walls():
    unit = _UnitStub(super_heavy=True)
    footprint = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
    tall_wall = Polygon([(2, 0.2), (2.2, 0.2), (2.2, 3.0), (2, 3.0)])
    ruins = RuinsTerrain(
        footprint=footprint,
        walls=[{"polygon": tall_wall, "z_bottom": 0.0, "z_top": 6.0, "thickness": 0.2}],
        openings=[],
        floors=[],
        height_map={},
    )

    assert get_terrain_blocking_polygons(unit, ruins, movement_type=MovementType.MOVE) == []
    assert not is_terrain_impassable(unit, ruins, movement_type=MovementType.MOVE)
