from __future__ import annotations

from .terrain_feature_renderers import TerrainPlacementSimple, TerrainPlacementSpec
from .terrain_layout_recipes import (
    TerrainLayoutRuntime,
    available_layout_ids,
    get_layout_feature_placements,
    get_layout_recipe,
    instantiate_layout_runtime,
)
from .terrain_runtime import TerrainFeature


class TerrainLayoutsRegistry:
    """Compatibility facade for integer terrain layout ids."""

    @classmethod
    def layout_ids(cls) -> tuple[int, ...]:
        return available_layout_ids()

    @classmethod
    def get_layout_specs(cls, layout_id: int) -> list[TerrainPlacementSimple | TerrainPlacementSpec]:
        try:
            return get_layout_feature_placements(int(layout_id))
        except KeyError:
            return []


def instantiate_layout(layout_id: int) -> list[TerrainFeature]:
    try:
        runtime = instantiate_layout_runtime(int(layout_id))
    except KeyError:
        return []
    return list(runtime.features)


__all__ = [
    "TerrainLayoutRuntime",
    "TerrainLayoutsRegistry",
    "TerrainPlacementSimple",
    "TerrainPlacementSpec",
    "get_layout_recipe",
    "instantiate_layout",
    "instantiate_layout_runtime",
]
