from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import radians

import pytest
from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import Map, RuinsTerrain, TerrainFactory
from warhammer40k_ai.pathing.dynamic_overlay import build_dynamic_overlay
from warhammer40k_ai.pathing.rules_profile import build_movement_profile
from warhammer40k_ai.pathing.surfaces import (
    GROUND_LAYER_KIND,
    RUINS_LAYER_KIND,
    SupportSurface,
    extract_ground_transit_obstacles,
    extract_support_surfaces,
    terrain_ignored_for_ground_transit,
    validate_pose_support_on_surface,
)
from warhammer40k_ai.pathing.world_snapshot import build_world_snapshot
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.utility.calcs import MovementType
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, movement: int = 6, base_size: str = "32mm"):
        self.name = name
        self.faction_data = {"name": "MirrorFaction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": "4",
                "Sv": "3",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name: str, *, faction: str = "MirrorFaction", x: float = 0.0, y: float = 0.0) -> Unit:
    unit = Unit(MockDatasheet(name))
    unit.faction = faction
    unit.deployed = True
    unit.models[0].model_base = Base(BaseType.CIRCULAR, 1.0)
    unit.models[0].set_location(x, y, 0.0, 0.0)
    unit.models[0].parent_unit = unit
    return unit


def _make_low_and_tall_wall_ruins() -> RuinsTerrain:
    footprint = Polygon([(0, 0), (6, 0), (6, 6), (0, 6)])
    low_wall = Polygon([(1.0, 0.2), (1.2, 0.2), (1.2, 3.0), (1.0, 3.0)])
    tall_wall = Polygon([(3.0, 0.2), (3.2, 0.2), (3.2, 3.0), (3.0, 3.0)])
    return RuinsTerrain(
        footprint=footprint,
        walls=[
            {"polygon": low_wall, "z_bottom": 0.0, "z_top": 2.0, "thickness": 0.2},
            {"polygon": tall_wall, "z_bottom": 0.0, "z_top": 5.0, "thickness": 0.2},
        ],
        openings=[],
        floors=[{"polygon": footprint, "elevation": 0.0, "thickness": 0.12}],
        height_map={},
    )


def test_phase_b_support_surface_extraction_contains_ground_and_ruins_layers() -> None:
    game_map = Map(60, 44)
    ruins = TerrainFactory.create_ruins([(10, 10), (20, 10), (20, 20), (10, 20)], wall_height=4.0, num_floors=2)
    game_map.add_terrain_feature(ruins)

    surfaces = extract_support_surfaces(game_map)
    ground = [surface for surface in surfaces if surface.layer_kind == GROUND_LAYER_KIND]
    ruins_floors = [surface for surface in surfaces if surface.layer_kind == RUINS_LAYER_KIND]

    assert len(ground) == 1
    assert len(ruins_floors) == len(ruins.floors)
    assert [surface.surface_z for surface in ruins_floors] == sorted(surface.surface_z for surface in ruins_floors)


def test_phase_b_low_terrain_is_ignored_for_ground_transit() -> None:
    game_map = Map(60, 44)
    ruins = _make_low_and_tall_wall_ruins()
    game_map.add_terrain_feature(ruins)

    moving = _make_unit("Moving")
    movement_profile = build_movement_profile(moving, MovementType.MOVE)
    ground_obstacles = extract_ground_transit_obstacles(game_map, movement_profile)

    assert len(ground_obstacles) == 1
    assert ground_obstacles[0].equals(ruins.walls[1]["polygon"])
    assert not terrain_ignored_for_ground_transit(ruins, movement_profile)


def test_phase_b_circular_support_validation_uses_polygon_erosion() -> None:
    support_surface = SupportSurface(
        surface_id="ruins:test:floor:1",
        layer_kind=RUINS_LAYER_KIND,
        polygon=Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
        surface_z=4.12,
        terrain_index=0,
        floor_index=1,
        terrain_type="RUINS",
    )
    base = Base(BaseType.CIRCULAR, 1.0)

    valid = validate_pose_support_on_surface(base, x=9.0, y=5.0, facing=0.0, surface=support_surface)
    invalid = validate_pose_support_on_surface(base, x=9.5, y=5.0, facing=0.0, surface=support_surface)

    assert valid.valid
    assert not invalid.valid
    assert "overhang" in invalid.reason.lower()


def test_phase_b_non_circular_support_validation_uses_exact_shape() -> None:
    support_surface = SupportSurface(
        surface_id="ruins:test:floor:2",
        layer_kind=RUINS_LAYER_KIND,
        polygon=Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
        surface_z=8.12,
        terrain_index=0,
        floor_index=2,
        terrain_type="RUINS",
    )
    base = Base(BaseType.ELLIPTICAL, (2.0, 1.0))

    valid = validate_pose_support_on_surface(base, x=8.0, y=5.0, facing=radians(0), surface=support_surface)
    invalid = validate_pose_support_on_surface(base, x=8.4, y=5.0, facing=radians(0), surface=support_surface)

    assert valid.valid
    assert not invalid.valid
    assert "footprint" in invalid.reason.lower()


def test_phase_b_world_snapshot_is_immutable_and_deterministic() -> None:
    game_map = Map(60, 44)
    ruins = TerrainFactory.create_ruins([(10, 10), (20, 10), (20, 20), (10, 20)], wall_height=4.0, num_floors=1)
    game_map.add_terrain_feature(ruins)

    moving = _make_unit("Moving")
    movement_profile = build_movement_profile(moving, MovementType.MOVE)

    snapshot_a = build_world_snapshot(game_map, movement_profile)
    snapshot_b = build_world_snapshot(game_map, movement_profile)

    assert snapshot_a.terrain_revision == snapshot_b.terrain_revision
    assert snapshot_a.support_surface_revision == snapshot_b.support_surface_revision
    assert snapshot_a.movement_profile_signature == snapshot_b.movement_profile_signature
    assert [surface.surface_id for surface in snapshot_a.support_surfaces] == [
        surface.surface_id for surface in snapshot_b.support_surfaces
    ]

    with pytest.raises(FrozenInstanceError):
        snapshot_a.terrain_revision = "mutated"


def test_phase_b_dynamic_overlay_uses_army_identity() -> None:
    game_map = Map(60, 44)
    moving = _make_unit("Moving", x=10.0, y=10.0)
    ally = _make_unit("Ally", x=13.0, y=10.0)
    enemy_same_faction = _make_unit("EnemyMirror", x=16.0, y=10.0)

    army_a = Army("MirrorFaction", "Detachment A")
    army_b = Army("MirrorFaction", "Detachment B")
    moving.set_parent_army(army_a)
    ally.set_parent_army(army_a)
    enemy_same_faction.set_parent_army(army_b)

    game_map.units = [moving, ally, enemy_same_faction]
    movement_profile = build_movement_profile(moving, MovementType.MOVE)
    overlay = build_dynamic_overlay(game_map, moving, movement_profile, moving_model=moving.models[0])

    assert len(overlay.enemy_blockers) == 1
    assert len(overlay.friendly_blockers) == 1
    assert overlay.enemy_blockers[0].model_id != overlay.friendly_blockers[0].model_id
