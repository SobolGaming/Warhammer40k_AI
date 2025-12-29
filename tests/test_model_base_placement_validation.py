import math

import pytest

from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.utility.placement_validation import bases_overlap_3d
from warhammer40k_ai.utility.calcs import check_unit_coherency
from warhammer40k_ai.classes.unit import Unit


class _MockDatasheet:
    """Minimal datasheet stub to construct Units in tests."""
    def __init__(self, name: str, model_count: int = 2):
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "2",
            "Ld": "7", "OC": "1",
            # Must be parseable by Unit._parse_base_size; tests will override model_base anyway.
            "base_size": "25mm", "inv_sv": "7", "inv_sv_descr": "none"
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _unit_with_two_models() -> Unit:
    ds = _MockDatasheet("Placement Test Unit", model_count=2)
    return Unit(ds)


def _set_base(model, base: Base, x: float, y: float, z: float, facing_rad: float) -> None:
    model.model_base = base
    model.model_base.set_model_height(1.5)  # explicitly required by test cases
    model.model_base.set_position(float(x), float(y), float(z))
    model.model_base.set_facing(float(facing_rad))


def _touching_center_distance(base1: Base, base2: Base, direction_angle: float) -> float:
    """Compute the center-to-center distance that produces edge-touching along direction_angle."""
    r1 = float(base1.get_radius(direction_angle))
    r2 = float(base2.get_radius((direction_angle + math.pi) % (2.0 * math.pi)))
    return r1 + r2


def test_circular_touching_same_z_is_legal():
    unit = _unit_with_two_models()

    # 1" base means 0.5" radius
    b1 = Base(BaseType.CIRCULAR, 0.5)
    b2 = Base(BaseType.CIRCULAR, 0.5)

    _set_base(unit.models[0], b1, 1.0, 1.0, 0.0, 0.0)
    _set_base(unit.models[1], b2, 1.0, 2.0, 0.0, 0.0)  # 1" apart -> touching

    assert not bases_overlap_3d(unit.models[0].model_base, unit.models[1].model_base), "Touching bases should be legal (no overlap)"


def test_circular_exact_vertical_touching_is_legal():
    unit = _unit_with_two_models()

    b1 = Base(BaseType.CIRCULAR, 0.5)
    b2 = Base(BaseType.CIRCULAR, 0.5)

    _set_base(unit.models[0], b1, 1.0, 1.0, 0.0, 0.0)
    _set_base(unit.models[1], b2, 1.0, 1.0, 1.5, 0.0)  # exactly one model_height up

    assert not bases_overlap_3d(unit.models[0].model_base, unit.models[1].model_base), "Exact vertical touching should be legal"


def test_circular_coherency_at_edge_distance_two_inches_is_coherent():
    unit = _unit_with_two_models()

    b1 = Base(BaseType.CIRCULAR, 0.5)
    b2 = Base(BaseType.CIRCULAR, 0.5)

    _set_base(unit.models[0], b1, 1.0, 1.0, 0.0, 0.0)
    _set_base(unit.models[1], b2, 1.0, 4.0, 0.0, 0.0)  # centers 3" apart -> edge distance 2"

    coherency = check_unit_coherency(unit)
    assert coherency["coherent"], f"Expected coherent at edge distance 2\", got: {coherency}"


def test_circular_overlap_is_illegal():
    unit = _unit_with_two_models()

    b1 = Base(BaseType.CIRCULAR, 0.5)
    b2 = Base(BaseType.CIRCULAR, 0.5)

    _set_base(unit.models[0], b1, 1.0, 1.0, 0.0, 0.0)
    _set_base(unit.models[1], b2, 1.0, 1.99, 0.0, 0.0)  # distance 0.99" < 1.0" => overlap

    assert bases_overlap_3d(unit.models[0].model_base, unit.models[1].model_base), "Overlapping bases should be illegal"


@pytest.mark.parametrize("facing_deg", [0.0, 15.0, 30.0, 45.0, 75.0])
def test_elliptical_touching_at_various_facings_is_legal(facing_deg: float):
    unit = _unit_with_two_models()

    # Elliptical base: semi-axes in inches (arbitrary but non-circular)
    b1 = Base(BaseType.ELLIPTICAL, (1.0, 0.6))
    b2 = Base(BaseType.ELLIPTICAL, (1.0, 0.6))

    facing = math.radians(facing_deg)
    _set_base(unit.models[0], b1, 10.0, 10.0, 0.0, facing)
    _set_base(unit.models[1], b2, 0.0, 0.0, 0.0, facing)  # will overwrite below

    # Place model2 to the +X direction at exactly touching distance for the current facing
    angle = 0.0
    d = _touching_center_distance(b1, b2, angle)
    _set_base(unit.models[1], b2, 10.0 + d, 10.0, 0.0, facing)

    assert not bases_overlap_3d(b1, b2), f"Elliptical touching should be legal at facing={facing_deg}°"


@pytest.mark.parametrize("facing_deg", [0.0, 15.0, 30.0, 45.0, 90.0])
def test_hull_touching_at_various_facings_is_legal(facing_deg: float):
    unit = _unit_with_two_models()

    # Hull base: half-width/half-height in inches (rectangle)
    b1 = Base(BaseType.HULL, (1.2, 0.8))
    b2 = Base(BaseType.HULL, (1.2, 0.8))

    facing = math.radians(facing_deg)
    _set_base(unit.models[0], b1, 20.0, 20.0, 0.0, facing)
    _set_base(unit.models[1], b2, 0.0, 0.0, 0.0, facing)  # will overwrite below

    angle = 0.0
    d = _touching_center_distance(b1, b2, angle)
    _set_base(unit.models[1], b2, 20.0 + d, 20.0, 0.0, facing)

    assert not bases_overlap_3d(b1, b2), f"Hull touching should be legal at facing={facing_deg}°"


