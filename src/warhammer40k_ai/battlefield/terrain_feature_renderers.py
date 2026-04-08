from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from shapely.affinity import rotate as sh_rotate, scale as sh_scale, translate as sh_translate
from shapely.geometry import Polygon as _ShPoly

from .map import RuinsTerrain, TerrainFactory
from .terrain_runtime import TerrainFeature


LongWallSide = Literal["left", "right", "top", "bottom"]

RuinPresetId = Literal[
    "ruin_rect_12x6_variant1",
    "ruin_rect_12x6_variant2",
    "ruin_rect_12x6_variant3",
    "ruin_rect_12x6_variant4",
    "ruin_rect_12x6_variant5",
    "ruin_rect_12x6_variant6",
    "ruin_rect_10x5_variant1",
    "ruin_rect_10x5_variant2",
    "ruin_rect_10x5_variant3",
    "ruin_rect_6x4_variant1",
    "ruin_rect_6x4_variant2",
]


@dataclass(frozen=True)
class TerrainPlacementSpec:
    preset: RuinPresetId
    footprint: list[tuple[float, float]]
    long_wall_side: LongWallSide


@dataclass(frozen=True)
class TerrainPlacementSimple:
    preset: RuinPresetId
    rotation_degrees: float
    world_origin: tuple[float, float]


def apply_affine_to_ruins(
    ruin: RuinsTerrain,
    rotation_degrees: float,
    translate_xy: tuple[float, float],
    scale_xy: tuple[float, float] | None = None,
    scale_origin: tuple[float, float] = (0.0, 0.0),
) -> RuinsTerrain:
    if scale_xy is not None:
        sx, sy = scale_xy
        ruin.footprint = sh_scale(ruin.footprint, xfact=sx, yfact=sy, origin=scale_origin)
        for wall in ruin.walls:
            wall["polygon"] = sh_scale(wall["polygon"], xfact=sx, yfact=sy, origin=scale_origin)
        for opening in ruin.openings:
            opening["polygon"] = sh_scale(opening["polygon"], xfact=sx, yfact=sy, origin=scale_origin)
        for floor in ruin.floors:
            floor["polygon"] = sh_scale(floor["polygon"], xfact=sx, yfact=sy, origin=scale_origin)

    if rotation_degrees:
        ruin.footprint = sh_rotate(ruin.footprint, rotation_degrees, origin=(0.0, 0.0), use_radians=False)
        for wall in ruin.walls:
            wall["polygon"] = sh_rotate(wall["polygon"], rotation_degrees, origin=(0.0, 0.0), use_radians=False)
        for opening in ruin.openings:
            opening["polygon"] = sh_rotate(opening["polygon"], rotation_degrees, origin=(0.0, 0.0), use_radians=False)
        for floor in ruin.floors:
            floor["polygon"] = sh_rotate(floor["polygon"], rotation_degrees, origin=(0.0, 0.0), use_radians=False)

    tx, ty = translate_xy
    ruin.footprint = sh_translate(ruin.footprint, xoff=tx, yoff=ty)
    for wall in ruin.walls:
        wall["polygon"] = sh_translate(wall["polygon"], xoff=tx, yoff=ty)
    for opening in ruin.openings:
        opening["polygon"] = sh_translate(opening["polygon"], xoff=tx, yoff=ty)
    for floor in ruin.floors:
        floor["polygon"] = sh_translate(floor["polygon"], xoff=tx, yoff=ty)

    bounds = ruin.footprint.bounds
    max_z = max(
        [wall["z_top"] for wall in ruin.walls]
        + [floor["elevation"] + floor.get("thickness", 0.5) for floor in ruin.floors]
        + [0.0]
    )
    ruin.bounding_box = {"min": (bounds[0], bounds[1], 0.0), "max": (bounds[2], bounds[3], max_z)}
    return ruin


def _is_axis_aligned_rect(points: list[tuple[float, float]], tol: float = 1e-6) -> bool:
    if len(points) != 4:
        return False
    edges: list[tuple[float, float]] = []
    for idx in range(4):
        x0, y0 = points[idx]
        x1, y1 = points[(idx + 1) % 4]
        dx = x1 - x0
        dy = y1 - y0
        if abs(dx) < tol and abs(dy) < tol:
            continue
        if not (abs(dx) < tol or abs(dy) < tol):
            return False
        edges.append((dx, dy))
    return len(edges) == 4


def _place_ruin_with_rotated_footprint(
    ruin: RuinsTerrain,
    spec: TerrainPlacementSpec,
    *,
    base_long_edge_start: tuple[float, float],
    base_long_edge_end: tuple[float, float],
) -> RuinsTerrain:
    if len(spec.footprint) != 4:
        raise ValueError("Footprint must contain exactly 4 vertices for rectangular placement")
    tgt_poly = _ShPoly(spec.footprint)
    if tgt_poly.is_empty or not tgt_poly.is_valid:
        raise ValueError("Invalid footprint polygon for placement")

    mrr = tgt_poly.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)[:-1]
    if len(coords) != 4:
        raise ValueError("Target footprint must be a quadrilateral")

    edges: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float], float]] = []
    for idx in range(4):
        p0 = coords[idx]
        p1 = coords[(idx + 1) % 4]
        vx = p1[0] - p0[0]
        vy = p1[1] - p0[1]
        length = math.hypot(vx, vy)
        edges.append((p0, p1, (vx, vy), length))

    lengths = sorted({round(edge[3], 6) for edge in edges})
    if len(lengths) != 2:
        raise ValueError("Target footprint edges must have exactly two distinct lengths")
    long_len = max(lengths)
    short_len = min(lengths)
    tol = 0.1
    if not (
        (abs(long_len - 12.0) <= tol and abs(short_len - 6.0) <= tol)
        or (abs(long_len - 6.0) <= tol and abs(short_len - 12.0) <= tol)
    ):
        raise ValueError(
            f"Target footprint sides {long_len:.2f}/{short_len:.2f} do not match preset 12.00/6.00 (no scaling supported)"
        )

    centroid = mrr.centroid

    def _edge_outward_dir(p0: tuple[float, float], p1: tuple[float, float]) -> tuple[float, float]:
        mx = (p0[0] + p1[0]) * 0.5
        my = (p0[1] + p1[1]) * 0.5
        nx = mx - centroid.x
        ny = my - centroid.y
        nlen = math.hypot(nx, ny) or 1.0
        return (nx / nlen, ny / nlen)

    axis_target = {
        "right": (1.0, 0.0),
        "left": (-1.0, 0.0),
        "top": (0.0, -1.0),
        "bottom": (0.0, 1.0),
    }[spec.long_wall_side]

    best_edge: tuple[tuple[float, float], tuple[float, float]] | None = None
    best_dot = -1e9
    for p0, p1, _vec, length in edges:
        if abs(length - long_len) >= tol:
            continue
        ox, oy = _edge_outward_dir(p0, p1)
        dot = ox * axis_target[0] + oy * axis_target[1]
        if dot > best_dot:
            best_dot = dot
            best_edge = (p0, p1)
    if best_edge is None:
        raise ValueError("Failed to select matching long edge for long_wall_side")

    p0, p1 = best_edge
    ex = p1[0] - p0[0]
    ey = p1[1] - p0[1]
    if abs(ex) >= abs(ey):
        t_start, t_end = (p0, p1) if p0[0] <= p1[0] else (p1, p0)
    else:
        t_start, t_end = (p0, p1) if p0[1] <= p1[1] else (p1, p0)

    bx = base_long_edge_end[0] - base_long_edge_start[0]
    by = base_long_edge_end[1] - base_long_edge_start[1]
    tx = t_end[0] - t_start[0]
    ty = t_end[1] - t_start[1]
    rot_deg = math.degrees(math.atan2(ty, tx) - math.atan2(by, bx))

    ruin = apply_affine_to_ruins(ruin, rotation_degrees=rot_deg, translate_xy=(0.0, 0.0))
    rad = math.radians(rot_deg)
    ca = math.cos(rad)
    sa = math.sin(rad)
    bsx, bsy = base_long_edge_start
    bsx_r = bsx * ca - bsy * sa
    bsy_r = bsx * sa + bsy * ca
    dx = t_start[0] - bsx_r
    dy = t_start[1] - bsy_r
    return apply_affine_to_ruins(ruin, rotation_degrees=0.0, translate_xy=(dx, dy))


def _place_ruin_axis_aligned(ruin: RuinsTerrain, spec: TerrainPlacementSpec, *, base_edge_label: str) -> RuinsTerrain:
    if len(spec.footprint) != 4:
        return ruin

    xs = [point[0] for point in spec.footprint]
    ys = [point[1] for point in spec.footprint]
    x_min = min(xs)
    x_max = max(xs)
    y_min = min(ys)
    y_max = max(ys)
    width = x_max - x_min
    height = y_max - y_min

    if width >= height:
        if spec.long_wall_side not in ("top", "bottom"):
            return ruin
        if base_edge_label == "top":
            rotation_degrees = 0.0 if spec.long_wall_side == "top" else 180.0
        else:
            rotation_degrees = 0.0 if spec.long_wall_side == "bottom" else 180.0
        ruin = apply_affine_to_ruins(ruin, rotation_degrees=rotation_degrees, translate_xy=(0.0, 0.0))
        rminx, rminy, rmaxx, rmaxy = ruin.footprint.bounds
        dy = (y_max - rmaxy) if spec.long_wall_side == "top" else (y_min - rminy)
        ruin = apply_affine_to_ruins(ruin, rotation_degrees=0.0, translate_xy=(0.0, dy))
        rminx, _rminy, rmaxx, _rmaxy = ruin.footprint.bounds
        dx = (x_min + (width - (rmaxx - rminx)) / 2.0) - rminx
        return apply_affine_to_ruins(ruin, rotation_degrees=0.0, translate_xy=(dx, 0.0))

    if spec.long_wall_side not in ("left", "right"):
        return ruin
    if base_edge_label == "top":
        rotation_degrees = 90.0 if spec.long_wall_side == "left" else -90.0
    else:
        rotation_degrees = -90.0 if spec.long_wall_side == "left" else 90.0
    ruin = apply_affine_to_ruins(ruin, rotation_degrees=rotation_degrees, translate_xy=(0.0, 0.0))
    rminx, rminy, rmaxx, rmaxy = ruin.footprint.bounds
    dx = (x_max - rmaxx) if spec.long_wall_side == "left" else (x_min - rminx)
    ruin = apply_affine_to_ruins(ruin, rotation_degrees=0.0, translate_xy=(dx, 0.0))
    _rminx, rminy, _rmaxx, rmaxy = ruin.footprint.bounds
    dy = (y_min + (height - (rmaxy - rminy)) / 2.0) - rminy
    return apply_affine_to_ruins(ruin, rotation_degrees=0.0, translate_xy=(0.0, dy))


def _preset_ruin(spec: TerrainPlacementSimple | TerrainPlacementSpec) -> RuinsTerrain:
    if spec.preset == "ruin_rect_12x6_variant1":
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant1()
    elif spec.preset == "ruin_rect_12x6_variant2":
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant2()
    elif spec.preset == "ruin_rect_12x6_variant3":
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant3()
    elif spec.preset == "ruin_rect_12x6_variant4":
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant4()
    elif spec.preset == "ruin_rect_12x6_variant5":
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant5()
    elif spec.preset == "ruin_rect_12x6_variant6":
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant6()
    elif spec.preset == "ruin_rect_10x5_variant1":
        ruin = TerrainFactory.create_preset_ruin_rect_10x5_variant1()
    elif spec.preset == "ruin_rect_10x5_variant2":
        ruin = TerrainFactory.create_preset_ruin_rect_10x5_variant2()
    elif spec.preset == "ruin_rect_10x5_variant3":
        ruin = TerrainFactory.create_preset_ruin_rect_10x5_variant3()
    elif spec.preset == "ruin_rect_6x4_variant1":
        ruin = TerrainFactory.create_preset_ruin_rect_6x4_variant1()
    elif spec.preset == "ruin_rect_6x4_variant2":
        ruin = TerrainFactory.create_preset_ruin_rect_6x4_variant2()
    else:
        raise ValueError(f"Unknown preset '{spec.preset}'")
    return ruin


def render_terrain_feature(
    spec: TerrainPlacementSimple | TerrainPlacementSpec,
    *,
    layout_slot_id: str = "",
) -> TerrainFeature:
    if isinstance(spec, TerrainPlacementSimple):
        ruin = _preset_ruin(spec)
        ruin = apply_affine_to_ruins(ruin, rotation_degrees=spec.rotation_degrees, translate_xy=(0.0, 0.0))
        ruin = apply_affine_to_ruins(ruin, rotation_degrees=0.0, translate_xy=spec.world_origin)
    else:
        if spec.preset == "ruin_rect_12x6_variant1":
            ruin = _preset_ruin(spec)
            if _is_axis_aligned_rect(spec.footprint):
                ruin = _place_ruin_axis_aligned(ruin, spec, base_edge_label="bottom")
            else:
                ruin = _place_ruin_with_rotated_footprint(
                    ruin,
                    spec,
                    base_long_edge_start=(0.0, 0.0),
                    base_long_edge_end=(12.0, 0.0),
                )
        elif spec.preset == "ruin_rect_12x6_variant2":
            ruin = _preset_ruin(spec)
            if _is_axis_aligned_rect(spec.footprint):
                ruin = _place_ruin_axis_aligned(ruin, spec, base_edge_label="top")
            else:
                ruin = _place_ruin_with_rotated_footprint(
                    ruin,
                    spec,
                    base_long_edge_start=(0.0, 6.0),
                    base_long_edge_end=(12.0, 6.0),
                )
        elif spec.preset == "ruin_rect_12x6_variant3":
            ruin = _preset_ruin(spec)
            if _is_axis_aligned_rect(spec.footprint):
                ruin = _place_ruin_axis_aligned(ruin, spec, base_edge_label="bottom")
            else:
                ruin = _place_ruin_with_rotated_footprint(
                    ruin,
                    spec,
                    base_long_edge_start=(0.0, 0.0),
                    base_long_edge_end=(12.0, 0.0),
                )
        elif spec.preset in {
            "ruin_rect_12x6_variant4",
            "ruin_rect_12x6_variant5",
            "ruin_rect_12x6_variant6",
            "ruin_rect_10x5_variant1",
            "ruin_rect_10x5_variant2",
            "ruin_rect_10x5_variant3",
            "ruin_rect_6x4_variant1",
            "ruin_rect_6x4_variant2",
        }:
            raise ValueError(f"{spec.preset} must be placed using TerrainPlacementSimple")
        else:
            raise ValueError(f"Unknown preset '{spec.preset}'")

    if layout_slot_id:
        ruin.layout_slot_id = str(layout_slot_id)
    return ruin


__all__ = [
    "LongWallSide",
    "RuinPresetId",
    "TerrainPlacementSimple",
    "TerrainPlacementSpec",
    "apply_affine_to_ruins",
    "render_terrain_feature",
]
