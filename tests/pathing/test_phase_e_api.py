from __future__ import annotations

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.pathing.api import (
    PathQuery,
    PathResult,
    Pose,
    compute_swept_interactions,
    plan_model_path,
    preview_model_path,
    validate_final_pose,
)
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


def _make_unit(name: str, *, x: float, y: float, faction: str = "MirrorFaction") -> Unit:
    unit = Unit(MockDatasheet(name))
    unit.faction = faction
    unit.deployed = True
    unit.models[0].model_base = Base(BaseType.CIRCULAR, 1.0)
    unit.models[0].set_location(x, y, 0.0, 0.0)
    unit.models[0].parent_unit = unit
    return unit


def test_phase_e_plan_preview_api_returns_path_result_and_legacy_payload() -> None:
    game_map = Map(20, 20)
    mover = _make_unit("Mover", x=2.0, y=2.0)
    game_map.units = [mover]

    query = PathQuery(
        model=mover.models[0],
        target=(8.0, 2.0, 0.0),
        movement_type=MovementType.MOVE,
        max_distance=12.0,
        game_map=game_map,
    )
    planned = plan_model_path(query)
    preview = preview_model_path(query)

    assert planned.valid
    assert preview.valid
    assert len(planned.waypoints) >= 2
    assert planned.waypoints[0][0] == 2.0
    assert planned.waypoints[-1][0] == 8.0
    legacy = planned.to_legacy_dict()
    assert legacy["valid"] is True
    assert len(legacy["path"]) >= 2


def test_phase_e_validate_final_pose_rejects_outside_boundary() -> None:
    game_map = Map(20, 20)
    mover = _make_unit("Mover", x=2.0, y=2.0)
    game_map.units = [mover]

    query = PathQuery(
        model=mover.models[0],
        target=(8.0, 2.0, 0.0),
        movement_type=MovementType.MOVE,
        max_distance=12.0,
        game_map=game_map,
    )
    validation = validate_final_pose(query, Pose(x=-1.0, y=2.0, z=0.0, facing=0.0))

    assert not validation.valid
    assert "outside battlefield boundaries" in validation.reason.lower()


def test_phase_e_compute_swept_interactions_reports_enemy_models_moved_over() -> None:
    game_map = Map(20, 20)
    mover = _make_unit("Mover", x=2.0, y=2.0, faction="MirrorFaction")
    enemy = _make_unit("Enemy", x=5.0, y=2.0, faction="OtherFaction")
    game_map.units = [mover, enemy]

    query = PathQuery(
        model=mover.models[0],
        target=(8.0, 2.0, 0.0),
        movement_type=MovementType.FALL_BACK,
        max_distance=12.0,
        game_map=game_map,
    )
    synthetic_path = PathResult(
        valid=True,
        poses=(
            Pose(x=2.0, y=2.0, z=0.0, facing=0.0),
            Pose(x=8.0, y=2.0, z=0.0, facing=0.0),
        ),
        waypoints=((2.0, 2.0, 0.0), (8.0, 2.0, 0.0)),
        distance_cost=6.0,
        pivot_cost=0.0,
        used_exact_refiner=False,
    )
    sweep = compute_swept_interactions(query, synthetic_path)

    assert sweep.intersects_enemy_models
    assert sweep.moved_over_enemy_model_ids


def test_phase_e_compute_swept_interactions_supports_vertical_overlap_gate() -> None:
    game_map = Map(20, 20)
    mover = _make_unit("Mover", x=2.0, y=2.0, faction="MirrorFaction")
    mover.models[0].set_location(2.0, 2.0, 5.0, 0.0)
    enemy = _make_unit("Enemy", x=5.0, y=2.0, faction="OtherFaction")
    enemy.models[0].set_location(5.0, 2.0, 0.0, 0.0)
    game_map.units = [mover, enemy]

    ungated_query = PathQuery(
        model=mover.models[0],
        target=(8.0, 2.0, 5.0),
        movement_type=MovementType.FALL_BACK,
        max_distance=12.0,
        game_map=game_map,
        sweep_require_vertical_overlap=False,
    )
    gated_query = PathQuery(
        model=mover.models[0],
        target=(8.0, 2.0, 5.0),
        movement_type=MovementType.FALL_BACK,
        max_distance=12.0,
        game_map=game_map,
        sweep_require_vertical_overlap=True,
    )
    synthetic_path = PathResult(
        valid=True,
        poses=(
            Pose(x=2.0, y=2.0, z=5.0, facing=0.0),
            Pose(x=8.0, y=2.0, z=5.0, facing=0.0),
        ),
        waypoints=((2.0, 2.0, 5.0), (8.0, 2.0, 5.0)),
        distance_cost=6.0,
        pivot_cost=0.0,
        used_exact_refiner=False,
    )

    ungated_sweep = compute_swept_interactions(ungated_query, synthetic_path)
    gated_sweep = compute_swept_interactions(gated_query, synthetic_path)

    assert ungated_sweep.intersects_enemy_models
    assert ungated_sweep.moved_over_enemy_model_ids
    assert not gated_sweep.intersects_enemy_models
    assert not gated_sweep.moved_over_enemy_model_ids
