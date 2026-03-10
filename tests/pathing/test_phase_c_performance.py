from __future__ import annotations

from time import perf_counter

import pytest
from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import Map, RuinsTerrain
from warhammer40k_ai.pathing.api import PathQuery, plan_model_path
from warhammer40k_ai.utility.calcs import (
    MovementType,
    a_star_unified,
    build_collision_trees,
    build_movement_profile,
    get_validation_rules,
)
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, movement: int = 10, base_size: str = "32mm"):
        self.name = name
        self.faction_data = {"name": "PerfFaction"}
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


def _make_unit(name: str, *, x: float, y: float) -> Unit:
    unit = Unit(MockDatasheet(name))
    unit.deployed = True
    unit.models[0].model_base = Base(BaseType.CIRCULAR, 0.6)
    unit.models[0].set_location(x, y, 0.0, 0.0)
    unit.models[0].parent_unit = unit
    return unit


def _build_benchmark_map() -> Map:
    game_map = Map(40, 30)
    for x in range(8, 36, 6):
        if (x // 6) % 2 == 0:
            wall = Polygon([(x, 0.0), (x + 0.7, 0.0), (x + 0.7, 20.0), (x, 20.0)])
        else:
            wall = Polygon([(x, 10.0), (x + 0.7, 10.0), (x + 0.7, 30.0), (x, 30.0)])
        game_map.add_terrain_feature(
            RuinsTerrain(
                footprint=Polygon([(0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0)]),
                walls=[{"polygon": wall, "z_bottom": 0.0, "z_top": 6.0, "thickness": 0.7}],
                openings=[],
                floors=[],
                height_map={},
            )
        )
    return game_map


@pytest.mark.slow
def test_phase_c_circular_common_case_repeated_queries_faster_than_legacy_quantized() -> None:
    game_map = _build_benchmark_map()
    mover = _make_unit("PerfMover", x=2.0, y=2.0)
    game_map.units = [mover]
    model = mover.models[0]
    target = (37.0, 28.0, 0.0)

    query = PathQuery(
        model=model,
        target=target,
        movement_type=MovementType.MOVE,
        max_distance=200.0,
        game_map=game_map,
        use_cache=True,
        enable_exact_refine=False,  # Circular common-case benchmark.
    )

    warm_new = plan_model_path(query)
    assert warm_new.valid

    movement_profile = build_movement_profile(mover, MovementType.MOVE)
    warm_trees = build_collision_trees(
        mover,
        MovementType.MOVE,
        game_map,
        moving_model=model,
        moved_models_in_unit=set(),
        max_distance=200.0,
        movement_profile=movement_profile,
    )
    warm_rules = get_validation_rules(
        MovementType.MOVE,
        moving_unit=mover,
        movement_profile=movement_profile,
    )
    warm_legacy = a_star_unified(
        model,
        target,
        200.0,
        warm_trees,
        warm_rules,
        game_map,
        MovementType.MOVE,
    )
    assert bool(warm_legacy.get("valid", False))

    iterations_per_sample = 4
    sample_count = 3
    new_samples: list[float] = []
    legacy_samples: list[float] = []

    for _ in range(sample_count):
        new_start = perf_counter()
        for _ in range(iterations_per_sample):
            result = plan_model_path(query)
            assert result.valid
        new_samples.append(perf_counter() - new_start)

        legacy_start = perf_counter()
        for _ in range(iterations_per_sample):
            profile = build_movement_profile(mover, MovementType.MOVE)
            trees = build_collision_trees(
                mover,
                MovementType.MOVE,
                game_map,
                moving_model=model,
                moved_models_in_unit=set(),
                max_distance=200.0,
                movement_profile=profile,
            )
            rules = get_validation_rules(
                MovementType.MOVE,
                moving_unit=mover,
                movement_profile=profile,
            )
            legacy = a_star_unified(
                model,
                target,
                200.0,
                trees,
                rules,
                game_map,
                MovementType.MOVE,
            )
            assert bool(legacy.get("valid", False))
        legacy_samples.append(perf_counter() - legacy_start)

    new_samples.sort()
    legacy_samples.sort()
    median_new = new_samples[len(new_samples) // 2]
    median_legacy = legacy_samples[len(legacy_samples) // 2]

    # Allow a small margin to reduce CI flake while still guarding regressions.
    assert median_new <= median_legacy * 1.05
