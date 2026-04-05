from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import RuinsTerrain, validate_ruins_placement
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.utility.constants import RUINS_FLOOR_HEIGHT, RUINS_FLOOR_THICKNESS
from warhammer40k_ai.utility.model_base import Base, BaseType


class _Unit:
    def can_access_upper_floors(self) -> bool:
        return True


def _make_model(name: str, height: float) -> Model:
    base = Base(BaseType.CIRCULAR, 0.5)
    base.set_model_height(height)
    model = Model(
        name=name,
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


def _make_three_floor_ruins() -> RuinsTerrain:
    footprint = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    floors = []
    for level in range(3):
        floors.append({
            "polygon": footprint,
            "elevation": level * RUINS_FLOOR_HEIGHT,
            "thickness": RUINS_FLOOR_THICKNESS,
        })
    return RuinsTerrain(footprint=footprint, walls=[], openings=[], floors=floors, height_map={})


def test_ruins_upper_floor_clearance_blocks_tall_model():
    unit = _Unit()
    ruins = _make_three_floor_ruins()
    model = _make_model("tall", height=3.0)

    z_floor1 = RUINS_FLOOR_HEIGHT + RUINS_FLOOR_THICKNESS
    result = validate_ruins_placement(unit, (5.0, 5.0, z_floor1), [ruins], moving_model=model)

    assert not result["valid"]
    assert "vertical gap" in result.get("reason", "")
    assert result.get("floor_level") == 1


def test_ruins_upper_floor_clearance_allows_short_model():
    unit = _Unit()
    ruins = _make_three_floor_ruins()
    model = _make_model("short", height=2.0)

    z_floor1 = RUINS_FLOOR_HEIGHT + RUINS_FLOOR_THICKNESS
    result = validate_ruins_placement(unit, (5.0, 5.0, z_floor1), [ruins], moving_model=model)

    assert result["valid"]
    assert result.get("floor_level") == 1
