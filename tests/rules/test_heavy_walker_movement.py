import os
import sys

from shapely.geometry import Polygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from warhammer40k_ai.battlefield.map import RuinsTerrain, TerrainType
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_terrain_blocking_polygons, get_validation_rules


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "8",
                "Sv": "3",
                "W": "10",
                "Ld": "7",
                "OC": "3",
                "base_size": "60mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def _heavy_walker_unit() -> Unit:
    ability = {
        "name": "Heavy Walker",
        "description": (
            "Each time this model makes a Normal, Advance or Fall Back move, it can move over models "
            "(excluding TITANIC models) and terrain features that are 4\" or less in height as if they were not there."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    return Unit(_MockDatasheet("Heavy Walker Unit", abilities=[ability]))


def test_heavy_walker_parses_and_sets_model_traversal_rules():
    unit = _heavy_walker_unit()
    sr = dict(getattr(unit, "special_rules", {}) or {})

    assert set(sr.get("bearer_unit_phase_move_models_only_types", []) or []) >= {"move", "advance", "fall_back"}
    assert set(sr.get("bearer_unit_phase_move_models_only_block_titanic_types", []) or []) >= {
        "move",
        "advance",
        "fall_back",
    }
    assert float(sr.get("move_over_low_terrain_height_value", 0.0) or 0.0) == 4.0
    assert set(sr.get("move_over_low_terrain_height_types", []) or []) >= {"move", "advance", "fall_back"}

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=unit)
    assert bool(move_rules.get("can_move_through_enemy_models")) is True
    assert bool(move_rules.get("can_move_through_friendly_models")) is True
    assert bool(move_rules.get("can_move_through_terrain", False)) is False
    assert bool(move_rules.get("block_titanic_models")) is True
    assert bool(move_rules.get("cannot_move_within_engagement_range", False)) is True

    charge_rules = get_validation_rules(MovementType.CHARGE, moving_unit=unit)
    assert bool(charge_rules.get("can_move_through_enemy_models", False)) is False
    assert bool(charge_rules.get("can_move_through_terrain", False)) is False


def test_heavy_walker_ignores_only_low_terrain_by_height():
    unit = _heavy_walker_unit()

    footprint = Polygon([(0, 0), (8, 0), (8, 8), (0, 8)])
    low_wall = Polygon([(2.0, 0.25), (2.25, 0.25), (2.25, 3.0), (2.0, 3.0)])
    tall_wall = Polygon([(5.0, 0.25), (5.25, 0.25), (5.25, 3.0), (5.0, 3.0)])
    ruins = RuinsTerrain(
        footprint=footprint,
        walls=[
            {"polygon": low_wall, "z_bottom": 0.0, "z_top": 4.0, "thickness": 0.25},
            {"polygon": tall_wall, "z_bottom": 0.0, "z_top": 5.0, "thickness": 0.25},
        ],
        openings=[],
        floors=[],
        height_map={},
    )
    assert ruins.terrain_type == TerrainType.RUINS

    move_polys = get_terrain_blocking_polygons(unit, ruins, movement_type=MovementType.MOVE)
    assert len(move_polys) == 1
    assert move_polys[0].equals(tall_wall)

    charge_polys = get_terrain_blocking_polygons(unit, ruins, movement_type=MovementType.CHARGE)
    assert len(charge_polys) == 2
