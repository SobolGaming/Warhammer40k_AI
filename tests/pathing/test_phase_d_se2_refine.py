from __future__ import annotations

from math import pi

from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import Map, RuinsTerrain, TerrainFactory
from warhammer40k_ai.pathing.corridor import build_corridor
from warhammer40k_ai.pathing.rules_profile import build_movement_profile
from warhammer40k_ai.pathing.se2_refine import Se2RefineRequest, refine_corridor_se2
from warhammer40k_ai.pathing.surface_graph import (
    _pivot_cost_once_for_refiner,
    build_surface_graph_for_query,
    plan_surface_graph_path,
)
from warhammer40k_ai.pathing.surfaces import SupportSurface
from warhammer40k_ai.pathing.world_snapshot import build_world_snapshot
from warhammer40k_ai.utility.calcs import MovementType
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, movement: int = 10, base_size: str = "32mm"):
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


def _make_unit(name: str, *, x: float, y: float, base: Base) -> Unit:
    unit = Unit(MockDatasheet(name))
    unit.faction = "MirrorFaction"
    unit.deployed = True
    unit.models[0].model_base = base
    unit.models[0].set_location(x, y, 0.0, 0.0)
    unit.models[0].parent_unit = unit
    unit.can_move_through_ruins_walls = lambda: False
    return unit


def _doorway_map(*, width: float) -> Map:
    game_map = Map(24, 24)
    half = float(width) / 2.0
    lower_wall = Polygon([(11.8, 0.0), (12.2, 0.0), (12.2, 12.0 - half), (11.8, 12.0 - half)])
    upper_wall = Polygon([(11.8, 12.0 + half), (12.2, 12.0 + half), (12.2, 24.0), (11.8, 24.0)])
    ruins = RuinsTerrain(
        footprint=Polygon([(0.0, 0.0), (24.0, 0.0), (24.0, 24.0), (0.0, 24.0)]),
        walls=[
            {"polygon": lower_wall, "z_bottom": 0.0, "z_top": 6.0, "thickness": 0.4},
            {"polygon": upper_wall, "z_bottom": 0.0, "z_top": 6.0, "thickness": 0.4},
        ],
        openings=[],
        floors=[],
        height_map={},
    )
    game_map.add_terrain_feature(ruins)
    return game_map


def _l_tunnel_map() -> Map:
    game_map = Map(24, 24)
    block_right_bottom = Polygon([(3.4, 0.0), (24.0, 0.0), (24.0, 12.6), (3.4, 12.6)])
    block_left_strip = Polygon([(0.0, 0.0), (2.0, 0.0), (2.0, 24.0), (0.0, 24.0)])
    block_top_strip = Polygon([(0.0, 14.0), (24.0, 14.0), (24.0, 24.0), (0.0, 24.0)])
    ruins = RuinsTerrain(
        footprint=Polygon([(0.0, 0.0), (24.0, 0.0), (24.0, 24.0), (0.0, 24.0)]),
        walls=[
            {"polygon": block_right_bottom, "z_bottom": 0.0, "z_top": 6.0, "thickness": 0.4},
            {"polygon": block_left_strip, "z_bottom": 0.0, "z_top": 6.0, "thickness": 0.4},
            {"polygon": block_top_strip, "z_bottom": 0.0, "z_top": 6.0, "thickness": 0.4},
        ],
        openings=[],
        floors=[],
        height_map={},
    )
    game_map.add_terrain_feature(ruins)
    return game_map


def _surface_by_id(snapshot, surface_id: str) -> SupportSurface:
    for surface in snapshot.support_surfaces:
        if surface.surface_id == surface_id:
            return surface
    raise AssertionError(f"Unknown surface_id '{surface_id}'")


def _build_same_surface_refine_request(
    *,
    snapshot,
    movement_profile,
    model_base: Base,
    footprint_class: str,
    base_radius: float,
    start: tuple[float, float, float],
    goal: tuple[float, float, float],
    start_facing: float,
    goal_facing: float,
) -> Se2RefineRequest:
    global_path = plan_surface_graph_path(
        snapshot,
        movement_profile,
        start=start,
        goal=goal,
        base_radius=base_radius,
        footprint_class=footprint_class,
        enable_exact_refine=False,
    )
    assert global_path.success
    grouped_segments = global_path.debug_artifacts.get("grouped_segments")
    assert isinstance(grouped_segments, tuple)
    assert grouped_segments
    surface_id, triangle_path, connector_out_id = grouped_segments[0]
    assert connector_out_id is None

    graph = build_surface_graph_for_query(
        snapshot,
        movement_profile,
        base_radius=base_radius,
        footprint_class=footprint_class,
    )
    mesh_by_surface = {surface_key: mesh for surface_key, mesh in graph.surface_meshes}
    mesh = mesh_by_surface[surface_id]
    corridor = build_corridor(
        mesh,
        triangle_path,
        start_xy=(float(start[0]), float(start[1])),
        goal_xy=(float(goal[0]), float(goal[1])),
    )
    return Se2RefineRequest(
        surface=_surface_by_id(snapshot, surface_id),
        mesh=mesh,
        triangle_path=triangle_path,
        corridor=corridor,
        model_base=model_base,
        movement_profile=movement_profile,
        start_facing=float(start_facing),
        goal_facing=float(goal_facing),
    )


def test_phase_d_oval_through_narrow_doorway_requires_exact_refinement() -> None:
    game_map = _doorway_map(width=1.15)
    oval_base = Base(BaseType.ELLIPTICAL, (1.2, 0.5))
    mover = _make_unit("OvalMover", x=4.0, y=12.0, base=oval_base)

    movement_profile = build_movement_profile(mover, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)
    result = plan_surface_graph_path(
        snapshot,
        movement_profile,
        start=(4.0, 12.0, 0.0),
        goal=(20.0, 12.0, 0.0),
        base_radius=1.2,
        footprint_class="oval",
        model_base=oval_base,
        start_facing=pi / 2.0,
        goal_facing=0.0,
        enable_exact_refine=True,
    )

    assert result.success
    assert result.used_exact_refiner
    assert result.debug_artifacts.get("segment_refinements")
    final_facing = float(result.debug_artifacts.get("final_facing", 0.0))
    assert abs(final_facing) <= (pi / 5.0)


def test_phase_d_exact_refiner_start_pose_is_anchored() -> None:
    game_map = Map(24, 24)
    oval_base = Base(BaseType.ELLIPTICAL, (1.1, 0.5))
    mover = _make_unit("AnchorStart", x=3.0, y=4.0, base=oval_base)

    movement_profile = build_movement_profile(mover, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)
    request = _build_same_surface_refine_request(
        snapshot=snapshot,
        movement_profile=movement_profile,
        model_base=oval_base,
        footprint_class="oval",
        base_radius=1.1,
        start=(3.0, 4.0, 0.0),
        goal=(18.0, 18.0, 0.0),
        start_facing=pi / 3.0,
        goal_facing=0.0,
    )
    refined = refine_corridor_se2(request)

    assert refined.success
    first_pose = refined.poses[0]
    assert abs(first_pose.x - 3.0) <= 1e-6
    assert abs(first_pose.y - 4.0) <= 1e-6
    assert abs(first_pose.facing - (pi / 3.0)) <= 1e-6


def test_phase_d_exact_refiner_terminal_pose_is_anchored() -> None:
    game_map = Map(24, 24)
    oval_base = Base(BaseType.ELLIPTICAL, (1.1, 0.5))
    mover = _make_unit("AnchorEnd", x=3.0, y=4.0, base=oval_base)

    movement_profile = build_movement_profile(mover, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)
    request = _build_same_surface_refine_request(
        snapshot=snapshot,
        movement_profile=movement_profile,
        model_base=oval_base,
        footprint_class="oval",
        base_radius=1.1,
        start=(3.0, 4.0, 0.0),
        goal=(18.0, 18.0, 0.0),
        start_facing=pi / 3.0,
        goal_facing=pi / 4.0,
    )
    refined = refine_corridor_se2(request)

    assert refined.success
    final_pose = refined.poses[-1]
    assert abs(final_pose.x - 18.0) <= 1e-6
    assert abs(final_pose.y - 18.0) <= 1e-6
    assert abs(final_pose.facing - (pi / 4.0)) <= 1e-6


def test_phase_d_hull_in_l_tunnel_global_corridor_exists_but_exact_refine_rejects() -> None:
    game_map = _l_tunnel_map()
    hull_base = Base(BaseType.HULL, (1.5, 0.6))
    mover = _make_unit("HullMover", x=2.7, y=2.6, base=hull_base)

    movement_profile = build_movement_profile(mover, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)

    global_only = plan_surface_graph_path(
        snapshot,
        movement_profile,
        start=(2.7, 2.6, 0.0),
        goal=(12.5, 13.3, 0.0),
        base_radius=1.5,
        footprint_class="hull",
        enable_exact_refine=False,
    )
    assert global_only.success

    exact = plan_surface_graph_path(
        snapshot,
        movement_profile,
        start=(2.7, 2.6, 0.0),
        goal=(12.5, 13.3, 0.0),
        base_radius=1.5,
        footprint_class="hull",
        model_base=hull_base,
        start_facing=pi / 2.0,
        goal_facing=0.0,
        enable_exact_refine=True,
    )

    assert not exact.success
    assert "Exact corridor refinement failed" in str(exact.failure_reason)
    candidate_failures = exact.debug_artifacts.get("candidate_failures")
    assert isinstance(candidate_failures, list)
    assert candidate_failures


def test_phase_d_non_circular_connector_transition_is_anchor_continuous() -> None:
    game_map = Map(30, 30)
    ruins = TerrainFactory.create_ruins(
        [(8.0, 8.0), (18.0, 8.0), (18.0, 18.0), (8.0, 18.0)],
        wall_height=4.0,
        num_floors=1,
    )
    game_map.add_terrain_feature(ruins)

    oval_base = Base(BaseType.ELLIPTICAL, (0.5, 0.25))
    mover = _make_unit("ConnectorOval", x=9.0, y=9.0, base=oval_base)
    mover.can_move_through_ruins_walls = lambda: True
    mover.can_access_upper_floors = lambda: True

    movement_profile = build_movement_profile(mover, MovementType.MOVE)
    snapshot = build_world_snapshot(game_map, movement_profile)
    floor_z = ruins.floors[1]["elevation"] + ruins.floors[1]["thickness"]
    graph = build_surface_graph_for_query(
        snapshot,
        movement_profile,
        base_radius=0.5,
        footprint_class="oval",
    )
    floor_connectors = [
        connector
        for connector in graph.connectors
        if connector.source_surface_id == "ground:main" and connector.target_surface_id == "ruins:0:floor:1"
    ]
    assert floor_connectors
    connector_anchor = floor_connectors[0].anchor_xy

    result = plan_surface_graph_path(
        snapshot,
        movement_profile,
        start=(9.0, 9.0, 0.0),
        goal=(float(connector_anchor[0]), float(connector_anchor[1]), floor_z),
        base_radius=0.5,
        footprint_class="oval",
        model_base=oval_base,
        start_facing=pi / 2.0,
        goal_facing=0.0,
        enable_exact_refine=True,
    )

    assert result.success
    assert result.used_exact_refiner
    assert result.connector_path
    vertical_transition_index = None
    for index in range(1, len(result.waypoints)):
        if abs(result.waypoints[index][2] - result.waypoints[index - 1][2]) > 1e-6:
            vertical_transition_index = index
            break
    assert vertical_transition_index is not None
    i = int(vertical_transition_index)
    assert abs(result.waypoints[i][0] - result.waypoints[i - 1][0]) <= 1e-6
    assert abs(result.waypoints[i][1] - result.waypoints[i - 1][1]) <= 1e-6


def test_phase_d_refiner_pivot_cost_semantics() -> None:
    aircraft_base = Base(BaseType.HULL, (1.4, 0.6))
    aircraft_unit = _make_unit("Aircraft", x=2.0, y=2.0, base=aircraft_base)
    aircraft_unit.keywords = ["Aircraft", "Vehicle"]
    aircraft_profile = build_movement_profile(aircraft_unit, MovementType.MOVE)
    assert _pivot_cost_once_for_refiner(aircraft_profile, aircraft_base) == 0.0

    monster_base = Base(BaseType.HULL, (1.4, 0.6))
    monster_unit = _make_unit("Monster", x=2.0, y=2.0, base=monster_base)
    monster_unit.keywords = ["Monster"]
    monster_profile = build_movement_profile(monster_unit, MovementType.MOVE)
    assert _pivot_cost_once_for_refiner(monster_profile, monster_base) == 2.0

    infantry_base = Base(BaseType.ELLIPTICAL, (0.9, 0.45))
    infantry_unit = _make_unit("Infantry", x=2.0, y=2.0, base=infantry_base)
    infantry_unit.keywords = ["Infantry"]
    infantry_profile = build_movement_profile(infantry_unit, MovementType.MOVE)
    assert _pivot_cost_once_for_refiner(infantry_profile, infantry_base) == 1.0

    flying_vehicle_base = Base(BaseType.CIRCULAR, 1.0)
    setattr(flying_vehicle_base, "is_flying_base", True)
    flying_vehicle_unit = _make_unit("FlyingVehicle", x=2.0, y=2.0, base=flying_vehicle_base)
    flying_vehicle_unit.keywords = ["Vehicle"]
    flying_vehicle_profile = build_movement_profile(flying_vehicle_unit, MovementType.MOVE)
    assert _pivot_cost_once_for_refiner(flying_vehicle_profile, flying_vehicle_base) == 2.0
