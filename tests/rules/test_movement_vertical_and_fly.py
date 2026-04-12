import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from warhammer40k_ai.pathing.api import PathQuery, plan_model_path
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.battlefield.map import Map, TerrainFactory
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, clear_collision_caches
from warhammer40k_ai.utility.constants import RUINS_FLOOR_THICKNESS
from warhammer40k_ai.utility.model_base import Base, BaseType


class MockDatasheet:
    """Minimal datasheet for movement tests."""
    def __init__(
        self,
        name,
        movement=6,
        model_count=1,
        base_size="25mm",
        keywords=None,
        abilities=None,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = keywords or []
        self.faction_keywords = []
        self.datasheets_unit_composition = [
            {"description": f"{model_count} Test Models"}
        ]
        self.datasheets_models_cost = [
            {"description": f"{model_count} models", "cost": 100}
        ]
        self.datasheets_models = [{
            "M": str(movement), "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none"
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name, *, keywords=None, movement=6, faction="A", abilities=None):
    datasheet = MockDatasheet(
        name,
        movement=movement,
        keywords=keywords or [],
        abilities=abilities,
    )
    unit = Unit(datasheet)
    unit.models[0].model_base = Base(BaseType.CIRCULAR, 1.0)
    unit.deployed = True
    unit.faction = faction
    return unit


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


def test_fly_move_over_enemy_models():
    game_map = Map(48, 72)

    # FLY infantry should move over enemy infantry.
    fly_unit = _make_unit("Flyer", keywords=["Fly"], faction="A")
    enemy_unit = _make_unit("Enemy", keywords=[], faction="B")
    fly_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy_unit.models[0].set_location(12.0, 10.0, 0.0, 0.0)
    game_map.units = [fly_unit, enemy_unit]

    target = (15.2, 10.0, 0.0)
    result = unified_pathfinding(
        model=fly_unit.models[0],
        target=target,
        movement_type=MovementType.MOVE,
        max_distance=6.0,
        game_map=game_map,
    )
    assert result["valid"], "FLY should be able to move over enemy infantry"

    clear_collision_caches()
    # Non-FLY should be blocked by the same enemy.
    ground_unit = _make_unit("Walker", keywords=[], faction="A")
    ground_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    game_map.units = [ground_unit, enemy_unit]

    blocked = unified_pathfinding(
        model=ground_unit.models[0],
        target=target,
        movement_type=MovementType.MOVE,
        max_distance=6.0,
        game_map=game_map,
    )
    assert not blocked["valid"], "Non-FLY should be blocked by enemy models"

    clear_collision_caches()
    # FLY (non-vehicle) should NOT move over enemy vehicles.
    enemy_vehicle = _make_unit("Enemy Vehicle", keywords=["Vehicle"], faction="B")
    enemy_vehicle.models[0].set_location(12.0, 10.0, 0.0, 0.0)
    game_map.units = [fly_unit, enemy_vehicle]

    blocked_big = unified_pathfinding(
        model=fly_unit.models[0],
        target=target,
        movement_type=MovementType.MOVE,
        max_distance=6.0,
        game_map=game_map,
    )
    assert not blocked_big["valid"], "FLY infantry should be blocked by enemy VEHICLE models"

    clear_collision_caches()
    # FLY vehicle should be able to move over enemy vehicles.
    fly_vehicle = _make_unit("Fly Vehicle", keywords=["Fly", "Vehicle"], faction="A")
    fly_vehicle.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    game_map.units = [fly_vehicle, enemy_vehicle]

    allowed_big = unified_pathfinding(
        model=fly_vehicle.models[0],
        target=target,
        movement_type=MovementType.MOVE,
        max_distance=6.0,
        game_map=game_map,
    )
    assert allowed_big["valid"], "FLY vehicles should be able to move over enemy VEHICLE models"


def test_flip_belt_ignores_vertical_distance():
    game_map = Map(24, 24)
    ruins_vertices = [(4.0, 4.0), (8.0, 4.0), (8.0, 8.0), (4.0, 8.0)]
    ruins = TerrainFactory.create_ruins(ruins_vertices, wall_height=3.0, num_floors=1)
    game_map.add_terrain_feature(ruins)

    start_x, start_y = 6.0, 6.0
    ground_z = game_map.get_height_at_point(start_x, start_y)
    upper_floor = ruins.floors[1]
    target_z = float(upper_floor.get("elevation", 0.0)) + float(upper_floor.get("thickness", RUINS_FLOOR_THICKNESS))

    infantry_unit = _make_unit("Infantry", keywords=["Infantry"], movement=2, faction="A")
    infantry_unit.models[0].set_location(start_x, start_y, ground_z, 0.0)
    game_map.units = [infantry_unit]

    blocked = unified_pathfinding(
        model=infantry_unit.models[0],
        target=(start_x, start_y, target_z),
        movement_type=MovementType.MOVE,
        max_distance=2.0,
        game_map=game_map,
    )
    assert not blocked["valid"], "Vertical distance should make this move too long without Flip Belt"

    flip_unit = _make_unit("Flip Belt Unit", keywords=["Infantry"], movement=2, faction="A")
    flip_unit.add_ability(Ability("Flip Belt", "", "Ignore any vertical distance.", "Wargear"))
    flip_unit.models[0].set_location(start_x, start_y, ground_z, 0.0)
    game_map.units = [flip_unit]

    allowed = unified_pathfinding(
        model=flip_unit.models[0],
        target=(start_x, start_y, target_z),
        movement_type=MovementType.MOVE,
        max_distance=2.0,
        game_map=game_map,
    )
    assert allowed["valid"], "Flip Belt should ignore vertical distance for the move"


_PHASE_MOVE_PASSTHROUGH_ABILITY = {
    "name": "Scuttling Walker",
    "description": (
        "Each time this unit makes a Normal, Advance or Fall Back move, it can move through models "
        "(excluding TITANIC models) and terrain features. When doing so, it can move within Engagement "
        "Range of enemy models, but cannot end that move within Engagement Range of them, and any "
        "Desperate Escape test is automatically passed."
    ),
    "type": "Datasheet",
    "parameter": "",
}


def test_phase_move_passthrough_allows_path_through_tall_terrain():
    game_map = Map(20, 20)
    ruins = TerrainFactory.create_ruins(
        [(9.5, 0.0), (10.5, 0.0), (10.5, 14.0), (9.5, 14.0)],
        wall_height=6.0,
        num_floors=0,
    )
    game_map.add_terrain_feature(ruins)

    mover = _make_unit(
        "PhaseWalker",
        movement=16,
        faction="A",
        abilities=[_PHASE_MOVE_PASSTHROUGH_ABILITY],
    )
    mover.models[0].model_base = Base(BaseType.CIRCULAR, 0.4)
    mover.models[0].set_location(2.0, 2.0, 0.0, 0.0)
    game_map.units = [mover]

    result = unified_pathfinding(
        model=mover.models[0],
        target=(18.0, 2.0, 0.0),
        movement_type=MovementType.MOVE,
        max_distance=16.0,
        game_map=game_map,
    )
    assert result["valid"], "Phase-through terrain movement should not route around blocking ruins walls"
    assert float(result["distance"]) <= 16.0 + 1e-6


def test_phase_move_passthrough_routes_around_titanic_blockers():
    game_map = Map(48, 48)
    mover = _make_unit(
        "PhaseWalker",
        movement=8,
        faction="A",
        abilities=[_PHASE_MOVE_PASSTHROUGH_ABILITY],
    )
    titanic = _make_unit("Titanic Blocker", keywords=["TITANIC", "VEHICLE"], movement=8, faction="B")
    mover.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    titanic.models[0].set_location(12.0, 10.0, 0.0, 0.0)
    game_map.units = [mover, titanic]

    result = plan_model_path(
        PathQuery(
            model=mover.models[0],
            target=(15.2, 10.0, 0.0),
            movement_type=MovementType.MOVE,
            max_distance=60.0,
            game_map=game_map,
            enable_exact_refine=False,
        )
    )
    assert result.valid, "TITANIC blockers should stay blocking, but the planner should find a legal route around them"
    assert float(result.distance_cost + result.pivot_cost) > 5.2
