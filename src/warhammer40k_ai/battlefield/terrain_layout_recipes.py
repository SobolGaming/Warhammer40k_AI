from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .terrain_area_templates import build_terrain_area_template_polygon, get_terrain_area_template
from .terrain_feature_renderers import TerrainPlacementSimple, TerrainPlacementSpec, render_terrain_feature
from .terrain_runtime import TerrainArea, TerrainFeature


@dataclass(frozen=True)
class TerrainLayoutSlotRecipe:
    placement: TerrainPlacementSimple | TerrainPlacementSpec
    terrain_area_template_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TerrainLayoutRecipe:
    layout_id: int
    display_name: str
    slots: tuple[TerrainLayoutSlotRecipe, ...]
    provisional: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TerrainLayoutRuntime:
    layout_id: int
    display_name: str
    features: tuple[TerrainFeature, ...]
    terrain_areas: tuple[TerrainArea, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


def _area_template_for_preset(preset: str) -> str:
    if str(preset).startswith("ruin_rect_6x4_"):
        return "medium_rectangle"
    return "large_rectangle"


def _slot_simple(preset: str, rotation_degrees: float, world_origin: tuple[float, float]) -> TerrainLayoutSlotRecipe:
    return TerrainLayoutSlotRecipe(
        placement=TerrainPlacementSimple(
            preset=preset, rotation_degrees=float(rotation_degrees), world_origin=tuple(world_origin)
        ),
        terrain_area_template_id=_area_template_for_preset(preset),
    )


def _layout_recipe(layout_id: int, display_name: str, slots: list[TerrainLayoutSlotRecipe]) -> TerrainLayoutRecipe:
    return TerrainLayoutRecipe(
        layout_id=int(layout_id),
        display_name=str(display_name),
        slots=tuple(slots),
        provisional=True,
        metadata={
            "terrain_layout_source": "pairing_authored_recipe",
            "terrain_area_template_system": "preview_11e_apr_2026",
        },
    )


_LAYOUT_RECIPES: dict[int, TerrainLayoutRecipe] = {
    1: _layout_recipe(
        1,
        "Preview Layout 1",
        [
            _slot_simple("ruin_rect_12x6_variant1", 90.0, (22.0, 28.0)),
            _slot_simple("ruin_rect_12x6_variant1", 270.0, (38.0, 16.0)),
            _slot_simple("ruin_rect_12x6_variant2", 270.0, (6.0, 17.0)),
            _slot_simple("ruin_rect_12x6_variant2", 90.0, (54.0, 27.0)),
            _slot_simple("ruin_rect_6x4_variant1", 90.0, (32.0, 0.0)),
            _slot_simple("ruin_rect_6x4_variant1", 270.0, (28.0, 44.0)),
            _slot_simple("ruin_rect_12x6_variant5", 0.0, (4.0, 22.0)),
            _slot_simple("ruin_rect_12x6_variant5", 180.0, (56.0, 22.0)),
            _slot_simple("ruin_rect_6x4_variant1", 135.0, (26.6, 20.6)),
            _slot_simple("ruin_rect_6x4_variant1", 315.0, (33.4, 23.4)),
            _slot_simple("ruin_rect_10x5_variant3", 45.0, (23.0, 10.0)),
            _slot_simple("ruin_rect_10x5_variant3", 225.0, (37.0, 34.0)),
        ],
    ),
    2: _layout_recipe(
        2,
        "Preview Layout 2",
        [
            _slot_simple("ruin_rect_12x6_variant1", math.degrees(math.atan2(4, 4.5)), (17.0, 15.5)),
            _slot_simple("ruin_rect_12x6_variant1", math.degrees(math.atan2(4, 4.5)) + 180.0, (43.0, 28.5)),
            _slot_simple("ruin_rect_12x6_variant2", 270.0, (8.0, 40.0)),
            _slot_simple("ruin_rect_12x6_variant2", 90.0, (52.0, 4.0)),
            _slot_simple("ruin_rect_12x6_variant4", 270.0, (5.0, 16.0)),
            _slot_simple("ruin_rect_12x6_variant4", 90.0, (55.0, 28.0)),
            _slot_simple("ruin_rect_10x5_variant1", 0.0, (20.0, 4.0)),
            _slot_simple("ruin_rect_10x5_variant1", 180.0, (40.0, 40.0)),
            _slot_simple("ruin_rect_6x4_variant1", 0.0, (30.0, 9.0)),
            _slot_simple("ruin_rect_6x4_variant1", 180.0, (30.0, 35.0)),
            _slot_simple("ruin_rect_6x4_variant1", 0.0, (52.0, 16.0)),
            _slot_simple("ruin_rect_6x4_variant1", 180.0, (8.0, 28.0)),
        ],
    ),
    3: _layout_recipe(
        3,
        "Preview Layout 3",
        [
            _slot_simple("ruin_rect_12x6_variant1", 180.0, (34.0, 10.0)),
            _slot_simple("ruin_rect_12x6_variant1", 0.0, (26.0, 34.0)),
            _slot_simple("ruin_rect_12x6_variant3", math.degrees(math.atan2(6, 10.4)) + 180.0, (14.2, 38.0)),
            _slot_simple("ruin_rect_12x6_variant3", math.degrees(math.atan2(6, 10.4)), (45.8, 6.0)),
            _slot_simple("ruin_rect_12x6_variant4", 270.0 + math.degrees(math.atan2(8, 9)), (2.0, 19.0)),
            _slot_simple("ruin_rect_12x6_variant4", 90.0 + math.degrees(math.atan2(8, 9)), (58.0, 25.0)),
            _slot_simple("ruin_rect_10x5_variant3", math.degrees(math.atan2(7.8, 6.0)), (21.0, 14.0)),
            _slot_simple("ruin_rect_10x5_variant3", 180.0 + math.degrees(math.atan2(7.8, 6.0)), (39.0, 30.0)),
            _slot_simple("ruin_rect_6x4_variant1", 0.0, (10.0, 4.0)),
            _slot_simple("ruin_rect_6x4_variant1", 180.0, (50.0, 40.0)),
            _slot_simple("ruin_rect_6x4_variant1", math.degrees(math.atan2(7.8, 6.0)) + 180.0, (22.8, 31.0)),
            _slot_simple("ruin_rect_6x4_variant1", math.degrees(math.atan2(7.8, 6.0)) + 0.0, (37.2, 13.0)),
        ],
    ),
    4: _layout_recipe(
        4,
        "Preview Layout 4",
        [
            _slot_simple("ruin_rect_12x6_variant1", math.degrees(math.atan2(4, 4.5)), (8.0, 27.5)),
            _slot_simple("ruin_rect_12x6_variant1", math.degrees(math.atan2(4, 4.5)) + 180.0, (52.0, 16.5)),
            _slot_simple("ruin_rect_12x6_variant2", 0.0, (12.0, 4.0)),
            _slot_simple("ruin_rect_12x6_variant2", 180.0, (48.0, 40.0)),
            _slot_simple("ruin_rect_12x6_variant4", math.degrees(math.atan2(9.5, 7)), (35.0, 2.5)),
            _slot_simple("ruin_rect_12x6_variant4", 180.0 + math.degrees(math.atan2(9.5, 7)), (25.0, 41.5)),
            _slot_simple("ruin_rect_10x5_variant2", 180.0 + math.degrees(math.atan2(7.6, 6.6)), (21.0, 27.0)),
            _slot_simple("ruin_rect_10x5_variant2", math.degrees(math.atan2(7.6, 6.6)), (39.0, 17.0)),
            _slot_simple("ruin_rect_6x4_variant1", 90.0, (8.0, 19.0)),
            _slot_simple("ruin_rect_6x4_variant1", 270.0, (52.0, 25.0)),
            _slot_simple("ruin_rect_6x4_variant1", 90.0, (12.0, 10.0)),
            _slot_simple("ruin_rect_6x4_variant1", 270.0, (48.0, 34.0)),
        ],
    ),
    5: _layout_recipe(
        5,
        "Preview Layout 5",
        [
            _slot_simple("ruin_rect_12x6_variant1", 180.0, (36.0, 10.0)),
            _slot_simple("ruin_rect_12x6_variant1", 0.0, (24.0, 34.0)),
            _slot_simple("ruin_rect_12x6_variant2", math.degrees(math.atan2(11, 5)) - 90.0, (5.0, 16.0)),
            _slot_simple("ruin_rect_12x6_variant2", math.degrees(math.atan2(11, 5)) + 90.0, (55.0, 28.0)),
            _slot_simple("ruin_rect_12x6_variant4", math.degrees(math.atan2(6.0, 10.4)), (46.5, 2.0)),
            _slot_simple("ruin_rect_12x6_variant4", 180.0 + math.degrees(math.atan2(6.0, 10.4)), (13.5, 42.0)),
            _slot_simple("ruin_rect_10x5_variant3", 0.0, (16.0, 24.0)),
            _slot_simple("ruin_rect_10x5_variant3", 180.0, (44.0, 20.0)),
            _slot_simple("ruin_rect_6x4_variant1", 0.0, (12.0, 4.0)),
            _slot_simple("ruin_rect_6x4_variant1", 180.0, (48.0, 40.0)),
            _slot_simple("ruin_rect_6x4_variant1", 0.0, (0.0, 24.0)),
            _slot_simple("ruin_rect_6x4_variant1", 180.0, (60.0, 20.0)),
        ],
    ),
    6: _layout_recipe(
        6,
        "Preview Layout 6",
        [
            _slot_simple("ruin_rect_12x6_variant1", math.degrees(math.atan2(4.5, 4.0)), (8.5, 27.0)),
            _slot_simple("ruin_rect_12x6_variant1", math.degrees(math.atan2(4.5, 4.0)) + 180.0, (51.5, 17.0)),
            _slot_simple("ruin_rect_12x6_variant2", 270.0, (20.0, 40.0)),
            _slot_simple("ruin_rect_12x6_variant2", 90.0, (40.0, 4.0)),
            _slot_simple("ruin_rect_12x6_variant4", 0.0, (10.0, 4.0)),
            _slot_simple("ruin_rect_12x6_variant4", 180.0, (50.0, 40.0)),
            _slot_simple("ruin_rect_10x5_variant2", math.degrees(math.atan2(7.4, 6.6)), (40.4, 18.6)),
            _slot_simple("ruin_rect_10x5_variant2", 180.0 + math.degrees(math.atan2(7.4, 6.6)), (19.6, 25.4)),
            _slot_simple("ruin_rect_6x4_variant1", 0.0, (24.0, 12.0)),
            _slot_simple("ruin_rect_6x4_variant1", 180.0, (36.0, 32.0)),
            _slot_simple("ruin_rect_6x4_variant1", 90.0, (10.0, 10.0)),
            _slot_simple("ruin_rect_6x4_variant1", 270.0, (50.0, 34.0)),
        ],
    ),
    7: _layout_recipe(
        7,
        "Preview Layout 7",
        [
            _slot_simple("ruin_rect_12x6_variant1", 90.0, (29.0, 3.0)),
            _slot_simple("ruin_rect_12x6_variant1", 270.0, (31.0, 41.0)),
            _slot_simple("ruin_rect_6x4_variant1", 0.0, (48.0, 0.0)),
            _slot_simple("ruin_rect_6x4_variant1", 180.0, (12.0, 44.0)),
            _slot_simple("ruin_rect_12x6_variant5", 90.0, (12.0, 28.0)),
            _slot_simple("ruin_rect_12x6_variant5", 270.0, (48.0, 16.0)),
            _slot_simple("ruin_rect_10x5_variant3", 270.0, (37.0, 18.0)),
            _slot_simple("ruin_rect_10x5_variant3", 90.0, (23.0, 26.0)),
            _slot_simple("ruin_rect_6x4_variant2", 90.0, (23.0, 20.0)),
            _slot_simple("ruin_rect_6x4_variant2", 270.0, (37.0, 24.0)),
            _slot_simple("ruin_rect_12x6_variant6", 90.0, (14.0, 8.0)),
            _slot_simple("ruin_rect_12x6_variant6", 270.0, (46.0, 36.0)),
        ],
    ),
    8: _layout_recipe(
        8,
        "Preview Layout 8",
        [
            _slot_simple("ruin_rect_12x6_variant1", 90.0, (28.0, 0.0)),
            _slot_simple("ruin_rect_12x6_variant1", 270.0, (32.0, 44.0)),
            _slot_simple("ruin_rect_12x6_variant3", math.degrees(math.atan2(4, 4.5)) + 180.0, (15.0, 40.0)),
            _slot_simple("ruin_rect_12x6_variant3", math.degrees(math.atan2(4, 4.5)), (45.0, 4.0)),
            _slot_simple("ruin_rect_6x4_variant1", 90.0, (37.0, 10.0)),
            _slot_simple("ruin_rect_6x4_variant1", 90.0, (37.0, 16.0)),
            _slot_simple("ruin_rect_6x4_variant1", 270.0, (23.0, 34.0)),
            _slot_simple("ruin_rect_6x4_variant1", 270.0, (23.0, 28.0)),
            _slot_simple("ruin_rect_12x6_variant5", 90.0, (19.0, 13.0)),
            _slot_simple("ruin_rect_12x6_variant5", 270.0, (41.0, 31.0)),
            _slot_simple("ruin_rect_10x5_variant2", 270.0 + math.degrees(math.atan2(8.0, 6.0)), (4.0, 10.0)),
            _slot_simple("ruin_rect_10x5_variant2", 90.0 + math.degrees(math.atan2(8.0, 6.0)), (56.0, 34.0)),
        ],
    ),
}


def available_layout_ids() -> tuple[int, ...]:
    return tuple(sorted(_LAYOUT_RECIPES))


def get_layout_recipe(layout_id: int) -> TerrainLayoutRecipe:
    layout_key = int(layout_id)
    if layout_key not in _LAYOUT_RECIPES:
        raise KeyError(f"Unknown terrain layout '{layout_id}'.")
    return _LAYOUT_RECIPES[layout_key]


def get_layout_feature_placements(layout_id: int) -> list[TerrainPlacementSimple | TerrainPlacementSpec]:
    recipe = get_layout_recipe(layout_id)
    return [slot.placement for slot in recipe.slots]


def instantiate_layout_runtime(layout_id: int) -> TerrainLayoutRuntime:
    recipe = get_layout_recipe(layout_id)
    features: list[TerrainFeature] = []
    terrain_areas: list[TerrainArea] = []
    for idx, slot in enumerate(recipe.slots, start=1):
        layout_slot_id = f"layout:{recipe.layout_id}:slot:{idx:02d}"
        feature = render_terrain_feature(slot.placement, layout_slot_id=layout_slot_id)
        features.append(feature)

        placement = slot.placement
        if not isinstance(placement, TerrainPlacementSimple):
            raise TypeError("Preview terrain layout runtime currently requires simple feature placements.")
        template = get_terrain_area_template(slot.terrain_area_template_id)
        polygon = build_terrain_area_template_polygon(
            slot.terrain_area_template_id,
            origin=placement.world_origin,
            rotation_degrees=placement.rotation_degrees,
        )
        terrain_areas.append(
            TerrainArea(
                polygon,
                area_id=f"terrain_area:layout:{recipe.layout_id}:slot:{idx:02d}",
                effect_tags=list(template.effect_tags),
                detection_range=template.detection_range,
                cover_mode=template.cover_mode,
                obscuring=template.obscuring,
                related_feature_ids=[str(feature.id)],
                layout_slot_id=layout_slot_id,
                metadata={
                    "layout_id": recipe.layout_id,
                    "layout_name": recipe.display_name,
                    "slot_index": idx,
                    "slot_preset": placement.preset,
                    "slot_rotation_degrees": float(placement.rotation_degrees),
                    "slot_origin": [float(placement.world_origin[0]), float(placement.world_origin[1])],
                    "terrain_area_template_id": template.template_id,
                    "preview_shape_approximation": True,
                    "provisional": True,
                    **dict(slot.metadata or {}),
                },
            )
        )

    return TerrainLayoutRuntime(
        layout_id=recipe.layout_id,
        display_name=recipe.display_name,
        features=tuple(features),
        terrain_areas=tuple(terrain_areas),
        metadata=dict(recipe.metadata or {}),
    )


__all__ = [
    "TerrainLayoutRecipe",
    "TerrainLayoutRuntime",
    "TerrainLayoutSlotRecipe",
    "available_layout_ids",
    "get_layout_feature_placements",
    "get_layout_recipe",
    "instantiate_layout_runtime",
]
