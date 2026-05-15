from types import SimpleNamespace

from shapely.geometry import Polygon

from warhammer40k_ai.engine import state_blob_terrain


def test_terrain_entries_reuse_map_cache_until_terrain_signature_changes(monkeypatch):
    feature = SimpleNamespace(
        id="terrain-a",
        terrain_type=SimpleNamespace(name="RUINS"),
        footprint=Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
        bounding_box={},
        traversal_rules={},
    )
    game_map = SimpleNamespace(terrain_features=[feature])
    game = SimpleNamespace(map=game_map)

    first = state_blob_terrain.terrain_entries(game)
    assert first

    def unexpected_footprint(_entity):
        raise AssertionError("cached terrain entries should not rebuild footprint coordinates")

    monkeypatch.setattr(state_blob_terrain, "_footprint_coords", unexpected_footprint)
    second = state_blob_terrain.terrain_entries(game)

    assert second == first
