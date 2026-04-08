from __future__ import annotations

import pytest

from warhammer40k_ai.battlefield.terrain_area_templates import (
    build_terrain_area_template_polygon,
    get_terrain_area_template,
)
from warhammer40k_ai.battlefield.terrain_layouts import instantiate_layout, instantiate_layout_runtime


def test_standard_terrain_area_templates_cover_preview_shapes() -> None:
    large_rectangle = get_terrain_area_template("large_rectangle")
    large_right_triangle = get_terrain_area_template("large_right_triangle")
    medium_rectangle = get_terrain_area_template("medium_rectangle")
    long_line = get_terrain_area_template("long_line")
    short_line = get_terrain_area_template("short_line")

    assert (large_rectangle.width, large_rectangle.height) == (11.5, 7.0)
    assert (large_right_triangle.width, large_right_triangle.height) == (11.5, 8.0)
    assert (medium_rectangle.width, medium_rectangle.height) == (6.0, 4.0)
    assert (long_line.width, long_line.height) == (10.0, 2.5)
    assert (short_line.width, short_line.height) == (6.0, 2.0)


def test_template_polygon_construction_handles_rectangle_triangle_and_lines() -> None:
    rectangle = build_terrain_area_template_polygon("large_rectangle")
    triangle = build_terrain_area_template_polygon("large_right_triangle")
    long_line = build_terrain_area_template_polygon("long_line")
    short_line = build_terrain_area_template_polygon("short_line")

    assert rectangle.bounds == pytest.approx((0.0, 0.0, 11.5, 7.0))
    assert triangle.bounds == pytest.approx((0.0, 0.0, 11.5, 8.0))
    assert long_line.bounds == pytest.approx((0.0, 0.0, 10.0, 2.5))
    assert short_line.bounds == pytest.approx((0.0, 0.0, 6.0, 2.0))
    assert triangle.area == pytest.approx(46.0)


def test_instantiate_layout_runtime_preserves_feature_entrypoint_and_authors_terrain_areas() -> None:
    runtime = instantiate_layout_runtime(1)
    features = instantiate_layout(1)

    assert len(runtime.features) == len(features)
    assert len(runtime.terrain_areas) == len(runtime.features)
    assert runtime.terrain_areas[0].layout_slot_id == "layout:1:slot:01"
    assert runtime.terrain_areas[0].id == "terrain_area:layout:1:slot:01"
    assert runtime.terrain_areas[0].related_feature_ids == (runtime.features[0].id,)
    assert runtime.terrain_areas[0].metadata["terrain_area_template_id"] == "large_rectangle"
