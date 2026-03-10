from __future__ import annotations

from math import pi

from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import Map, RuinsTerrain
from warhammer40k_ai.pathing.rules_profile import build_movement_profile
from warhammer40k_ai.pathing.surface_graph import plan_surface_graph_path
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
