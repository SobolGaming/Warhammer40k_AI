from __future__ import annotations

from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import Map, RuinsTerrain, TerrainFactory
from warhammer40k_ai.pathing.cache import clear_static_mesh_cache, get_static_mesh_cache
from warhammer40k_ai.pathing.cdt_mesh import build_surface_cdt_mesh, locate_triangles_for_point
from warhammer40k_ai.pathing.dynamic_overlay import build_dynamic_overlay
from warhammer40k_ai.pathing.rules_profile import build_movement_profile
from warhammer40k_ai.pathing.surface_graph import (
    build_surface_graph_for_query,
    build_surface_graph_static,
    plan_surface_graph_path,
)
from warhammer40k_ai.pathing.world_snapshot import build_world_snapshot
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


def _make_unit(name: str, *, x: float = 0.0, y: float = 0.0, faction: str = "MirrorFaction") -> Unit:
    unit = Unit(MockDatasheet(name))
    unit.faction = faction
    unit.deployed = True
    unit.models[0].model_base = Base(BaseType.CIRCULAR, 1.0)
    unit.models[0].set_location(x, y, 0.0, 0.0)
    unit.models[0].parent_unit = unit
    return unit


def test_phase_c_cdt_mesh_builds_fallback_mesh_and_portals() -> None:
    free_space = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 8.0), (0.0, 8.0)])
    mesh = build_surface_cdt_mesh("surface:test", free_space, prefer_constrained=True)

    assert mesh.triangulation_backend in {"shapely_triangulate_fallback", "shapely_constrained_delaunay"}
    assert len(mesh.triangles) >= 2
    assert len(mesh.portals) >= 1
    assert locate_triangles_for_point(mesh, 6.0, 4.0)


def test_phase_c_surface_graph_routes_around_tall_ground_obstacle() -> None:
    game_map = Map(20, 20)
    barrier_ruins = RuinsTerrain(
        footprint=Polygon([(9.5, 0.0), (10.5, 0.0), (10.5, 14.0), (9.5, 14.0)]),
        walls=[{"polygon": Polygon([(9.8, 0.0), (10.2, 0.0), (10.2, 14.0), (9.8, 14.0)]), "z_bottom": 0.0, "z_top": 6.0, "thickness": 0.4}],
        openings=[],
        floors=[],
        height_map={},
    )
    game_map.add_terrain_feature(barrier_ruins)

    moving = _make_unit("Mover", x=2.0, y=2.0)
    movement_profile = build_movement_profile(moving, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)

    result = plan_surface_graph_path(
        snapshot,
        movement_profile,
        start=(2.0, 2.0, 0.0),
        goal=(18.0, 2.0, 0.0),
        base_radius=0.4,
        footprint_class="disk",
    )

    assert result.success
    assert len(result.waypoints) >= 3
    assert max(point[1] for point in result.waypoints) > 14.0
    assert result.portal_path


def test_phase_c_surface_graph_uses_ground_to_floor_connectors() -> None:
    game_map = Map(30, 30)
    ruins = TerrainFactory.create_ruins([(8.0, 8.0), (16.0, 8.0), (16.0, 16.0), (8.0, 16.0)], wall_height=4.0, num_floors=1)
    game_map.add_terrain_feature(ruins)

    mover = _make_unit("Breacher", x=9.0, y=9.0)
    mover.can_move_through_ruins_walls = lambda: True
    mover.can_access_upper_floors = lambda: True

    movement_profile = build_movement_profile(mover, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)

    floor_z = ruins.floors[1]["elevation"] + ruins.floors[1]["thickness"]
    result = plan_surface_graph_path(
        snapshot,
        movement_profile,
        start=(9.0, 9.0, 0.0),
        goal=(9.0, 9.0, floor_z),
        base_radius=0.4,
        footprint_class="disk",
    )

    assert result.success
    assert result.connector_path
    assert len(result.surface_path) >= 2


def test_phase_c_upper_floor_to_ground_non_fly_succeeds() -> None:
    game_map = Map(30, 30)
    ruins = TerrainFactory.create_ruins([(8.0, 8.0), (16.0, 8.0), (16.0, 16.0), (8.0, 16.0)], wall_height=4.0, num_floors=1)
    game_map.add_terrain_feature(ruins)

    mover = _make_unit("Descender", x=9.0, y=9.0)
    mover.can_move_through_ruins_walls = lambda: True
    mover.can_access_upper_floors = lambda: True

    movement_profile = build_movement_profile(mover, MovementType.MOVE)
    assert not bool(movement_profile.terrain_transition_rules.get("is_fly_move", False))

    snapshot = build_world_snapshot(game_map, movement_profile)
    floor_z = ruins.floors[1]["elevation"] + ruins.floors[1]["thickness"]
    graph = build_surface_graph_for_query(
        snapshot,
        movement_profile,
        base_radius=0.4,
        footprint_class="disk",
    )
    assert any(connector.kind == "support_to_ground" for connector in graph.connectors)

    result = plan_surface_graph_path(
        snapshot,
        movement_profile,
        start=(9.0, 9.0, floor_z),
        goal=(6.0, 9.0, 0.0),
        base_radius=0.4,
        footprint_class="disk",
    )

    assert result.success
    assert all("fly_transition" not in connector_id for connector_id in result.connector_path)


def test_phase_c_static_mesh_cache_reuses_entries_for_same_key() -> None:
    clear_static_mesh_cache()
    game_map = Map(24, 24)
    moving = _make_unit("CacheRunner", x=2.0, y=2.0)
    movement_profile = build_movement_profile(moving, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)

    cache = get_static_mesh_cache()
    graph_a = build_surface_graph_static(snapshot, movement_profile, base_radius=0.4, footprint_class="disk")
    size_after_first = cache.size()
    graph_b = build_surface_graph_static(snapshot, movement_profile, base_radius=0.4, footprint_class="disk")

    assert size_after_first == 1
    assert cache.size() == 1
    assert graph_a.surface_meshes[0][1].triangulation_backend == graph_b.surface_meshes[0][1].triangulation_backend


def test_phase_c_different_radii_same_bucket_do_not_share_incorrect_mesh() -> None:
    clear_static_mesh_cache()
    game_map = Map(24, 24)
    moving = _make_unit("CacheRadius", x=2.0, y=2.0)
    movement_profile = build_movement_profile(moving, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)
    cache = get_static_mesh_cache()

    graph_small = build_surface_graph_static(snapshot, movement_profile, base_radius=0.41, footprint_class="disk")
    graph_large = build_surface_graph_static(snapshot, movement_profile, base_radius=0.49, footprint_class="disk")

    assert cache.size() == 2
    small_area = graph_small.surface_meshes[0][1].free_space.area
    large_area = graph_large.surface_meshes[0][1].free_space.area
    assert large_area < small_area


def test_phase_c_cache_separates_prefer_constrained_variants() -> None:
    clear_static_mesh_cache()
    game_map = Map(24, 24)
    moving = _make_unit("CacheConstraint", x=2.0, y=2.0)
    movement_profile = build_movement_profile(moving, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)
    cache = get_static_mesh_cache()

    graph_constrained = build_surface_graph_static(
        snapshot,
        movement_profile,
        base_radius=0.4,
        footprint_class="disk",
        prefer_constrained=True,
    )
    graph_fallback = build_surface_graph_static(
        snapshot,
        movement_profile,
        base_radius=0.4,
        footprint_class="disk",
        prefer_constrained=False,
    )

    assert cache.size() == 2
    assert graph_constrained.surface_meshes[0][1].triangulation_backend != ""
    assert graph_fallback.surface_meshes[0][1].triangulation_backend == "shapely_triangulate_fallback"


def test_phase_c_dynamic_overlay_applied_at_query_time() -> None:
    game_map = Map(22, 22)
    mover = _make_unit("Mover", x=2.0, y=10.0)
    enemy = _make_unit("Enemy", x=10.0, y=10.0, faction="OtherFaction")
    game_map.units = [mover, enemy]

    movement_profile = build_movement_profile(mover, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)

    no_overlay = plan_surface_graph_path(
        snapshot,
        movement_profile,
        start=(2.0, 10.0, 0.0),
        goal=(18.0, 10.0, 0.0),
        base_radius=0.4,
        footprint_class="disk",
        dynamic_overlay=None,
    )
    overlay = build_dynamic_overlay(game_map, mover, movement_profile, moving_model=mover.models[0])
    with_overlay = plan_surface_graph_path(
        snapshot,
        movement_profile,
        start=(2.0, 10.0, 0.0),
        goal=(18.0, 10.0, 0.0),
        base_radius=0.4,
        footprint_class="disk",
        dynamic_overlay=overlay,
    )

    assert no_overlay.success
    assert with_overlay.success
    assert with_overlay.distance_cost > no_overlay.distance_cost


def test_phase_c_connector_anchor_sampling_allows_alternate_overlap_transition() -> None:
    game_map = Map(30, 30)
    ruins = TerrainFactory.create_ruins(
        [(8.0, 8.0), (18.0, 8.0), (18.0, 18.0), (8.0, 18.0)],
        wall_height=4.0,
        num_floors=1,
    )
    game_map.add_terrain_feature(ruins)

    mover = _make_unit("Mover", x=9.0, y=9.0)
    mover.can_move_through_ruins_walls = lambda: True
    mover.can_access_upper_floors = lambda: True
    enemy = _make_unit("AnchorBlocker", x=13.0, y=13.0, faction="OtherFaction")
    game_map.units = [mover, enemy]

    movement_profile = build_movement_profile(mover, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)
    overlay = build_dynamic_overlay(game_map, mover, movement_profile, moving_model=mover.models[0])
    graph = build_surface_graph_for_query(
        snapshot,
        movement_profile,
        base_radius=0.4,
        footprint_class="disk",
        dynamic_overlay=overlay,
    )

    floor_surface = next(surface for surface in snapshot.support_surfaces if surface.surface_id.startswith("ruins:0:floor:1"))
    ground_to_floor = [
        connector
        for connector in graph.connectors
        if connector.source_surface_id == "ground:main" and connector.target_surface_id == floor_surface.surface_id
    ]
    assert len(ground_to_floor) >= 2
    assert any(connector.dynamic_blocked for connector in ground_to_floor)
    assert any(not connector.dynamic_blocked for connector in ground_to_floor)

    floor_z = float(floor_surface.surface_z)
    result = plan_surface_graph_path(
        snapshot,
        movement_profile,
        start=(9.0, 9.0, 0.0),
        goal=(13.0, 13.0, floor_z),
        base_radius=0.4,
        footprint_class="disk",
        dynamic_overlay=overlay,
    )
    assert result.success
    assert result.connector_path
