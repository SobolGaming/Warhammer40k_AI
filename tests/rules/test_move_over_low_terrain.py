import os
import sys

import pytest

from shapely.geometry import Polygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from warhammer40k_ai.battlefield.map import RuinsTerrain, TerrainType
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_terrain_blocking_polygons


class MockDatasheet:
    def __init__(self, name, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def test_move_over_low_terrain_applies_only_to_move_types():
    ability = {
        "name": "Serpentine",
        "description": (
            "Each time this model makes a Normal, Advance or Fall Back move, it can move over "
            "sections of terrain features that are 4\" or less in height."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = Unit(MockDatasheet("Test Unit", abilities=[ability]))

    footprint = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
    wall_poly = Polygon([(2, 0.2), (2.2, 0.2), (2.2, 3.0), (2, 3.0)])
    ruins = RuinsTerrain(
        footprint=footprint,
        walls=[{"polygon": wall_poly, "z_bottom": 0.0, "z_top": 4.0, "thickness": 0.2}],
        openings=[],
        floors=[],
        height_map={},
    )
    assert ruins.terrain_type == TerrainType.RUINS

    # Normal move should ignore <=4" wall segments.
    move_polys = get_terrain_blocking_polygons(unit, ruins, movement_type=MovementType.MOVE)
    assert move_polys == []

    # Charge move should still be blocked (ability is not active for charges).
    charge_polys = get_terrain_blocking_polygons(unit, ruins, movement_type=MovementType.CHARGE)
    assert len(charge_polys) == 1
    assert charge_polys[0].equals(wall_poly)
