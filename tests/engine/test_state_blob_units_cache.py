from types import SimpleNamespace

from warhammer40k_ai.engine.state_blob_units import (
    is_unit_in_engagement_range,
    min_enemy_engagement_edge_distance,
)


def test_state_blob_reuses_model_pair_edge_distances_between_enemy_distance_and_engagement() -> None:
    calls = []

    class CountedBase:
        has_circular_base = False
        z = 0.0

        def edge_to_edge_distance(self, _other):
            calls.append("edge")
            return 0.5

    model = SimpleNamespace(id="model:source", is_alive=True, model_base=CountedBase())
    enemy_model = SimpleNamespace(id="model:enemy", is_alive=True, model_base=CountedBase())
    unit = SimpleNamespace(id="unit:source", deployed=True, models=[model])
    enemy = SimpleNamespace(id="unit:enemy", deployed=True, models=[enemy_model])
    alive_models_cache = {}
    edge_distance_cache = {}

    assert min_enemy_engagement_edge_distance(
        unit,
        [enemy],
        alive_models_cache=alive_models_cache,
        edge_distance_cache=edge_distance_cache,
    ) == 0.5
    assert is_unit_in_engagement_range(
        unit,
        [enemy],
        alive_models_cache=alive_models_cache,
        edge_distance_cache=edge_distance_cache,
    ) is True
    assert len(calls) == 1

