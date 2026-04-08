from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shapely.affinity import rotate as sh_rotate, scale as sh_scale, translate as sh_translate
from shapely.geometry import Polygon


@dataclass(frozen=True)
class TerrainAreaTemplate:
    template_id: str
    display_name: str
    shape_kind: str
    width: float
    height: float
    effect_tags: tuple[str, ...] = ()
    cover_mode: str = "SAVE_BONUS_COMPATIBILITY"
    obscuring: bool = True
    detection_range: float | None = 15.0
    metadata: dict[str, Any] = field(default_factory=dict)


def _rect_polygon(width: float, height: float) -> Polygon:
    return Polygon(
        [
            (0.0, 0.0),
            (float(width), 0.0),
            (float(width), float(height)),
            (0.0, float(height)),
        ]
    )


def _right_triangle_polygon(width: float, height: float) -> Polygon:
    return Polygon(
        [
            (0.0, 0.0),
            (float(width), 0.0),
            (0.0, float(height)),
        ]
    )


STANDARD_TERRAIN_AREA_TEMPLATES: dict[str, TerrainAreaTemplate] = {
    "large_rectangle": TerrainAreaTemplate(
        template_id="large_rectangle",
        display_name='Large Rectangle 7" x 11.5"',
        shape_kind="rectangle",
        width=11.5,
        height=7.0,
        effect_tags=("PREVIEW_11E_TERRAIN_AREA", "HIDDEN_CAPABLE"),
        metadata={"published_size_inches": [7.0, 11.5]},
    ),
    "large_right_triangle": TerrainAreaTemplate(
        template_id="large_right_triangle",
        display_name='Large Right Triangle 8" x 11.5"',
        shape_kind="right_triangle",
        width=11.5,
        height=8.0,
        effect_tags=("PREVIEW_11E_TERRAIN_AREA", "HIDDEN_CAPABLE"),
        metadata={"published_size_inches": [8.0, 11.5]},
    ),
    "medium_rectangle": TerrainAreaTemplate(
        template_id="medium_rectangle",
        display_name='Medium Rectangle 6" x 4"',
        shape_kind="rectangle",
        width=6.0,
        height=4.0,
        effect_tags=("PREVIEW_11E_TERRAIN_AREA", "HIDDEN_CAPABLE"),
        metadata={"published_size_inches": [6.0, 4.0]},
    ),
    "long_line": TerrainAreaTemplate(
        template_id="long_line",
        display_name='Long Line 10" x 2.5"',
        shape_kind="rectangle",
        width=10.0,
        height=2.5,
        effect_tags=("PREVIEW_11E_TERRAIN_AREA",),
        metadata={"published_size_inches": [10.0, 2.5], "template_role": "line"},
    ),
    "short_line": TerrainAreaTemplate(
        template_id="short_line",
        display_name='Short Line 6" x 2"',
        shape_kind="rectangle",
        width=6.0,
        height=2.0,
        effect_tags=("PREVIEW_11E_TERRAIN_AREA",),
        metadata={"published_size_inches": [6.0, 2.0], "template_role": "line"},
    ),
}


def get_terrain_area_template(template_id: str) -> TerrainAreaTemplate:
    key = str(template_id or "").strip().lower()
    if key not in STANDARD_TERRAIN_AREA_TEMPLATES:
        raise KeyError(f"Unknown terrain area template '{template_id}'.")
    return STANDARD_TERRAIN_AREA_TEMPLATES[key]


def build_terrain_area_template_polygon(
    template_id: str,
    *,
    origin: tuple[float, float] = (0.0, 0.0),
    rotation_degrees: float = 0.0,
    mirror_x: bool = False,
    mirror_y: bool = False,
) -> Polygon:
    template = get_terrain_area_template(template_id)
    if template.shape_kind == "rectangle":
        polygon = _rect_polygon(template.width, template.height)
    elif template.shape_kind == "right_triangle":
        polygon = _right_triangle_polygon(template.width, template.height)
    else:
        raise ValueError(f"Unsupported terrain area template shape '{template.shape_kind}'.")

    if mirror_x or mirror_y:
        polygon = sh_scale(
            polygon,
            xfact=-1.0 if mirror_x else 1.0,
            yfact=-1.0 if mirror_y else 1.0,
            origin=(0.0, 0.0),
        )
    if rotation_degrees:
        polygon = sh_rotate(polygon, rotation_degrees, origin=(0.0, 0.0), use_radians=False)
    if origin != (0.0, 0.0):
        polygon = sh_translate(polygon, xoff=float(origin[0]), yoff=float(origin[1]))
    return polygon


__all__ = [
    "STANDARD_TERRAIN_AREA_TEMPLATES",
    "TerrainAreaTemplate",
    "build_terrain_area_template_polygon",
    "get_terrain_area_template",
]
