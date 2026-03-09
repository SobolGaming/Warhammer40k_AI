from __future__ import annotations

from warhammer40k_ai.battlefield.map import Map, TerrainFactory
from warhammer40k_ai.engine.board_affordances import compute_board_affordance_summary


class _Objective:
    def __init__(self, objective_id: str, x: float, y: float) -> None:
        self.id = objective_id
        self.location = type("Loc", (), {"x": float(x), "y": float(y)})()


class _StubGame:
    def __init__(self, game_map: Map, objectives: list[_Objective]) -> None:
        self.map = game_map
        self.objectives = list(objectives)


def test_board_affordance_summary_includes_approach_metrics_and_cells() -> None:
    game_map = Map(width=60, height=44)
    game_map.add_terrain_feature(
        TerrainFactory.create_ruins(
            [(8.0, 8.0), (18.0, 8.0), (18.0, 18.0), (8.0, 18.0)],
            wall_height=4.0,
            num_floors=1,
        )
    )
    game_map.add_terrain_feature(
        TerrainFactory.create_woods(
            [(30.0, 10.0), (40.0, 10.0), (40.0, 20.0), (30.0, 20.0)],
            density=0.8,
        )
    )
    game = _StubGame(
        game_map,
        objectives=[_Objective("obj:a", 20.0, 26.0), _Objective("obj:b", 46.0, 30.0)],
    )
    summary = compute_board_affordance_summary(
        game,
        deployment_zone={"name": "left", "x_range": [0.0, 30.0], "y_range": [0.0, 44.0]},
    )
    payload = summary.to_dict()

    assert int(payload.get("terrain_feature_count", 0)) == 2
    assert int(payload.get("los_blocking_feature_count", 0)) >= 1
    assert int(payload.get("hidden_staging_cell_count", 0)) >= 0
    assert int(payload.get("must_expose_to_advance_cell_count", 0)) >= 0
    assert 0.0 <= float(payload.get("infantry_objective_approach_quality", 0.0)) <= 1.0
    assert 0.0 <= float(payload.get("vehicle_objective_approach_quality", 0.0)) <= 1.0
    assert set(dict(payload.get("reserve_entry_lane_quality", {})).keys()) == {
        "north_edge",
        "south_edge",
        "west_edge",
        "east_edge",
    }
    objective_rows = list(payload.get("objective_lane_distances", []) or [])
    assert objective_rows
    assert "best_route_blockers" in objective_rows[0]
    assert "infantry_approach_quality" in objective_rows[0]


def test_board_affordance_summary_is_not_ruins_only_and_is_deterministic() -> None:
    game_map = Map(width=60, height=44)
    game_map.add_terrain_feature(
        TerrainFactory.create_barricade((10.0, 22.0), (50.0, 22.0), height=3.0, thickness=1.0)
    )
    game = _StubGame(game_map, objectives=[_Objective("obj:mid", 30.0, 32.0)])

    zone = {"name": "south", "x_range": [0.0, 60.0], "y_range": [0.0, 22.0]}
    first = compute_board_affordance_summary(game, deployment_zone=zone).to_dict()
    second = compute_board_affordance_summary(game, deployment_zone=zone).to_dict()

    assert int(first.get("ruins_count", 0)) == 0
    assert int(first.get("los_blocking_feature_count", 0)) >= 1
    assert int(first.get("opening_constrained_vehicle_corridors", 0)) >= 1
    assert first == second
