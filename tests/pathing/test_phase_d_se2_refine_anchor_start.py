from __future__ import annotations

from math import pi

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.pathing.corridor import build_corridor
from warhammer40k_ai.pathing.rules_profile import build_movement_profile
from warhammer40k_ai.pathing.se2_refine import Se2RefineRequest, refine_corridor_se2
from warhammer40k_ai.pathing.surface_graph import build_surface_graph_for_query, plan_surface_graph_path
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

