from collections import OrderedDict
from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.battlefield.terrain_visibility import _visibility_context_cache_key


def test_map_state_generation_bumps_and_clears_visibility_cache_on_mutation():
    game_map = Map(width=60, height=44)
    game_map._visibility_context_cache = OrderedDict({("old",): {"visible": True}})

    game_map.add_terrain_feature(object())

    assert game_map.state_generation == 1
    assert game_map._visibility_context_cache == OrderedDict()


def test_empty_bulk_map_mutation_does_not_bump_generation():
    game_map = Map(width=60, height=44)

    game_map.add_terrain_features([])
    game_map.add_terrain_areas([])
    game_map.add_objectives([])

    assert game_map.state_generation == 0


def test_visibility_context_cache_key_includes_map_generation():
    game_map = Map(width=60, height=44)
    shooter = SimpleNamespace(name="Shooter", model_base=None)
    target = SimpleNamespace(name="Target", model_base=None)

    before = _visibility_context_cache_key(game_map, shooter, target)
    game_map.bump_state_generation("test")
    after = _visibility_context_cache_key(game_map, shooter, target)

    assert before != after
    assert before[1] == 0
    assert after[1] == 1
