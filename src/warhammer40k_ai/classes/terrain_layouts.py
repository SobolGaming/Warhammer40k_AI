from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Literal

from shapely.affinity import rotate as sh_rotate, translate as sh_translate, scale as sh_scale

from .map import TerrainFeature, TerrainFactory, RuinsTerrain
from shapely.geometry import Polygon as _ShPoly
import math


LongWallSide = Literal['left', 'right', 'top', 'bottom']


@dataclass
class TerrainPlacementSpec:
    """Specification for placing a preset terrain piece on the battlefield.

    - `preset`: identifier of the preset factory to call
    - `footprint`: four vertices of the target footprint rectangle in world coords
    - `long_wall_side`: for ruins that have a designated long wall, which side of the
      rectangle that long wall should be flush to. Use 'left'/'right' for vertical
      rectangles (height > width) and 'top'/'bottom' for horizontal rectangles (width > height).
    """

    preset: Literal['ruin_rect_12x6_variant1', 'ruin_rect_12x6_variant2', 'ruin_rect_12x6_variant3']
    footprint: List[Tuple[float, float]]
    long_wall_side: LongWallSide


def _apply_affine_to_ruins(
    ruin: RuinsTerrain,
    rotation_degrees: float,
    translate_xy: Tuple[float, float],
    scale_xy: Tuple[float, float] | None = None,
    scale_origin: Tuple[float, float] = (0.0, 0.0),
) -> RuinsTerrain:
    """Apply rotation/scale/translation to all geometries of a RuinsTerrain in-place and
    update its footprint and bounding box accordingly.

    Rotation is applied around origin (0,0) before translation. If `scale_xy` is provided, scaling
    occurs first about origin, then rotation, then translation.
    """
    # Scale (optional)
    if scale_xy is not None:
        sx, sy = scale_xy
        ruin.footprint = sh_scale(ruin.footprint, xfact=sx, yfact=sy, origin=scale_origin)
        for wall in ruin.walls:
            wall['polygon'] = sh_scale(wall['polygon'], xfact=sx, yfact=sy, origin=scale_origin)
        for opening in ruin.openings:
            opening['polygon'] = sh_scale(opening['polygon'], xfact=sx, yfact=sy, origin=scale_origin)
        for floor in ruin.floors:
            floor['polygon'] = sh_scale(floor['polygon'], xfact=sx, yfact=sy, origin=scale_origin)

    # Rotate
    if rotation_degrees:
        ruin.footprint = sh_rotate(ruin.footprint, rotation_degrees, origin=(0.0, 0.0), use_radians=False)
        for wall in ruin.walls:
            wall['polygon'] = sh_rotate(wall['polygon'], rotation_degrees, origin=(0.0, 0.0), use_radians=False)
        for opening in ruin.openings:
            opening['polygon'] = sh_rotate(opening['polygon'], rotation_degrees, origin=(0.0, 0.0), use_radians=False)
        for floor in ruin.floors:
            floor['polygon'] = sh_rotate(floor['polygon'], rotation_degrees, origin=(0.0, 0.0), use_radians=False)

    # Translate
    tx, ty = translate_xy
    ruin.footprint = sh_translate(ruin.footprint, xoff=tx, yoff=ty)
    for wall in ruin.walls:
        wall['polygon'] = sh_translate(wall['polygon'], xoff=tx, yoff=ty)
    for opening in ruin.openings:
        opening['polygon'] = sh_translate(opening['polygon'], xoff=tx, yoff=ty)
    for floor in ruin.floors:
        floor['polygon'] = sh_translate(floor['polygon'], xoff=tx, yoff=ty)

    # Recompute bounding box
    bounds = ruin.footprint.bounds
    max_z = max(
        [wall["z_top"] for wall in ruin.walls]
        + [floor["elevation"] + floor.get("thickness", 0.5) for floor in ruin.floors]
        + [0.0]
    )
    ruin.bounding_box = {"min": (bounds[0], bounds[1], 0.0), "max": (bounds[2], bounds[3], max_z)}

    return ruin


def _place_ruin_with_rotated_footprint(
    ruin: RuinsTerrain,
    spec: TerrainPlacementSpec,
    base_long_edge_start: Tuple[float, float],
    base_long_edge_end: Tuple[float, float],
) -> RuinsTerrain:
    """Place ruin by mapping its authored long edge to the requested target rectangle long edge.

    This uses an edge-to-edge rigid transform (rotation + translation) with no scaling.
    """
    if len(spec.footprint) != 4:
        raise ValueError("Footprint must contain exactly 4 vertices for rectangular placement")

    tgt_poly = _ShPoly(spec.footprint)
    if tgt_poly.is_empty or not tgt_poly.is_valid:
        raise ValueError("Invalid footprint polygon for placement")

    mrr = tgt_poly.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)[:-1]
    if len(coords) != 4:
        raise ValueError("Target footprint must be a quadrilateral")

    edges = []  # (p0, p1, vec, length)
    for i in range(4):
        p0 = coords[i]
        p1 = coords[(i + 1) % 4]
        vx = p1[0] - p0[0]
        vy = p1[1] - p0[1]
        length = math.hypot(vx, vy)
        edges.append((p0, p1, (vx, vy), length))

    lengths = sorted({round(e[3], 6) for e in edges})
    if len(lengths) != 2:
        raise ValueError("Target footprint edges must have exactly two distinct lengths")
    long_len, short_len = max(lengths), min(lengths)

    base_long, base_short = 12.0, 6.0
    tol = 0.1
    dims_ok = (abs(long_len - base_long) <= tol and abs(short_len - base_short) <= tol) or \
              (abs(long_len - base_short) <= tol and abs(short_len - base_long) <= tol)
    if not dims_ok:
        raise ValueError(
            f"Target footprint sides {long_len:.2f}/{short_len:.2f} do not match preset 12.00/6.00 (no scaling supported)"
        )

    centroid = mrr.centroid

    def edge_outward_dir(p0, p1):
        mx, my = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
        nx, ny = mx - centroid.x, my - centroid.y
        nlen = math.hypot(nx, ny) or 1.0
        return (nx / nlen, ny / nlen)

    axis_target = {
        'right': (1.0, 0.0),
        'left': (-1.0, 0.0),
        'top': (0.0, -1.0),
        'bottom': (0.0, 1.0),
    }[spec.long_wall_side]

    long_edges = [e for e in edges if abs(e[3] - long_len) < tol]
    if not long_edges:
        raise ValueError("Could not identify long edges for target footprint")

    # Choose the target long edge with outward normal matching the requested side
    best_edge = None
    best_dot = -1e9
    for p0, p1, vec, length in long_edges:
        ox, oy = edge_outward_dir(p0, p1)
        dot = ox * axis_target[0] + oy * axis_target[1]
        if dot > best_dot:
            best_dot = dot
            best_edge = (p0, p1)

    if best_edge is None:
        raise ValueError("Failed to select matching long edge for long_wall_side")

    # Order target edge endpoints deterministically: for horizontal-ish edges by x, else by y
    p0, p1 = best_edge
    ex, ey = p1[0] - p0[0], p1[1] - p0[1]
    if abs(ex) >= abs(ey):
        t_start, t_end = (p0, p1) if p0[0] <= p1[0] else (p1, p0)
    else:
        t_start, t_end = (p0, p1) if p0[1] <= p1[1] else (p1, p0)

    # Compute base edge direction and target edge direction
    bx, by = base_long_edge_end[0] - base_long_edge_start[0], base_long_edge_end[1] - base_long_edge_start[1]
    tx, ty = t_end[0] - t_start[0], t_end[1] - t_start[1]
    b_ang = math.atan2(by, bx)
    t_ang = math.atan2(ty, tx)
    rot_deg = math.degrees(t_ang - b_ang)

    # Rotate ruin about origin
    ruin = _apply_affine_to_ruins(ruin, rotation_degrees=rot_deg, translate_xy=(0.0, 0.0))

    # Rotate base start to find its current position, then translate to target start
    rad = math.radians(rot_deg)
    ca, sa = math.cos(rad), math.sin(rad)
    bsx, bsy = base_long_edge_start
    bsx_r = bsx * ca - bsy * sa
    bsy_r = bsx * sa + bsy * ca
    dx = t_start[0] - bsx_r
    dy = t_start[1] - bsy_r
    ruin = _apply_affine_to_ruins(ruin, rotation_degrees=0.0, translate_xy=(dx, dy))
    return ruin


def _instantiate_ruin_rect_12x6_variant1(spec: TerrainPlacementSpec) -> RuinsTerrain:
    ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant1()
    # Base long edge: bottom from (0,0) -> (12,0)
    return _place_ruin_with_rotated_footprint(ruin, spec, base_long_edge_start=(0.0, 0.0), base_long_edge_end=(12.0, 0.0))


def _instantiate_ruin_rect_12x6_variant2(spec: TerrainPlacementSpec) -> RuinsTerrain:
    ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant2()
    # Base long edge: top from (0,6) -> (12,6)
    return _place_ruin_with_rotated_footprint(ruin, spec, base_long_edge_start=(0.0, 6.0), base_long_edge_end=(12.0, 6.0))


def _instantiate_ruin_rect_12x6_variant3(spec: TerrainPlacementSpec) -> RuinsTerrain:
    ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant3()
    # Base long edge: bottom from (0,0) -> (12,0) (opposite side from variant2)
    return _place_ruin_with_rotated_footprint(ruin, spec, base_long_edge_start=(0.0, 0.0), base_long_edge_end=(12.0, 0.0))


def _instantiate_from_spec(spec: TerrainPlacementSpec) -> TerrainFeature:
    if spec.preset == 'ruin_rect_12x6_variant1':
        return _instantiate_ruin_rect_12x6_variant1(spec)
    if spec.preset == 'ruin_rect_12x6_variant2':
        return _instantiate_ruin_rect_12x6_variant2(spec)
    if spec.preset == 'ruin_rect_12x6_variant3':
        return _instantiate_ruin_rect_12x6_variant3(spec)
    raise ValueError(f"Unknown preset '{spec.preset}'")


class TerrainLayoutsRegistry:
    """Registry of terrain layouts (1..8) mapping to terrain placement specs.

    Extend this for additional layouts as needed.
    """

    _layouts: dict[int, List[TerrainPlacementSpec]] = {
        1: [
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(16.0, 28.0), (22.0, 28.0), (22.0, 40.0), (16.0, 40.0)],
                long_wall_side='right',
            ),
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(38.0, 4.0), (44.0, 4.0), (44.0, 16.0), (38.0, 16.0)],
                long_wall_side='left',
            ),
        ],
        2: [
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(13.0, 20.0), (17.0, 15.5), (26.0, 23.5), (22.0, 28.0)],
                long_wall_side='right',
            ),
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(34.0, 20.5), (38.0, 16.0), (47.0, 24.0), (43.0, 28.5)],
                long_wall_side='left',
            ),
        ],
        3: [
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(22.0, 4.0), (34.0, 4.0), (34.0, 10.0), (22.0, 10.0)],
                long_wall_side='bottom',
            ),
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(26.0, 32.0), (38.0, 32.0), (38.0, 38.0), (26.0, 38.0)],
                long_wall_side='top',
            ),
        ],
        4: [
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(4.0, 32.0), (8.0, 27.5), (17.0, 35.5), (13.0, 40.0)],
                long_wall_side='right',
            ),
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(43.0, 8.5), (47.0, 4.0), (56.0, 12.0), (52.0, 16.5)],
                long_wall_side='left',
            ),
        ],
        5: [
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(24.0, 4.0), (36.0, 4.0), (36.0, 10.0), (24.0, 10.0)],
                long_wall_side='bottom',
            ),
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(24.0, 34.0), (36.0, 34.0), (36.0, 40.0), (24.0, 40.0)],
                long_wall_side='top',
            ),
        ],
        6: [
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(4.0, 31.0), (8.5, 27.0), (16.5, 36.0), (12.0, 40.0)],
                long_wall_side='right',
            ),
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(43.5, 8.0), (48.0, 4.0), (56.0, 13.0), (51.5, 17.0)],
                long_wall_side='left',
            ),
        ],
        7: [
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(23.0, 3.0), (29.0, 3.0), (29.0, 15.0), (23.0, 15.0)],
                long_wall_side='right',
            ),
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(31.0, 29.0), (37.0, 29.0), (37.0, 41.0), (31.0, 41.0)],
                long_wall_side='left',
            ),
        ],
        8: [
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(22.0, 0.0), (28.0, 0.0), (28.0, 12.0), (22.0, 12.0)],
                long_wall_side='right',
            ),
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(32.0, 32.0), (38.0, 32.0), (38.0, 44.0), (32.0, 44.0)],
                long_wall_side='left',
            ),
        ],
    }

    @classmethod
    def get_layout_specs(cls, layout_id: int) -> List[TerrainPlacementSpec]:
        return cls._layouts.get(layout_id, [])


def instantiate_layout(layout_id: int) -> List[TerrainFeature]:
    """Instantiate all terrain features for the given layout id.

    Returns a list of fully placed terrain features ready to be added to `Map`.
    """
    specs = TerrainLayoutsRegistry.get_layout_specs(layout_id)
    features: List[TerrainFeature] = []
    for spec in specs:
        try:
            feature = _instantiate_from_spec(spec)
            features.append(feature)
        except Exception as e:
            # Log and continue with other features instead of aborting layout
            print(f"⚠️ Terrain placement failed for preset {spec.preset}: {e}")
    return features


