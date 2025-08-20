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

    preset: Literal['ruin_rect_12x6_variant1']
    footprint: List[Tuple[float, float]]
    long_wall_side: LongWallSide


def _apply_affine_to_ruins(ruin: RuinsTerrain, rotation_degrees: float, translate_xy: Tuple[float, float], scale_xy: Tuple[float, float] | None = None) -> RuinsTerrain:
    """Apply rotation/scale/translation to all geometries of a RuinsTerrain in-place and
    update its footprint and bounding box accordingly.

    Rotation is applied around origin (0,0) before translation. If `scale_xy` is provided, scaling
    occurs first about origin, then rotation, then translation.
    """
    # Scale (optional)
    if scale_xy is not None:
        sx, sy = scale_xy
        ruin.footprint = sh_scale(ruin.footprint, xfact=sx, yfact=sy, origin=(0.0, 0.0))
        for wall in ruin.walls:
            wall['polygon'] = sh_scale(wall['polygon'], xfact=sx, yfact=sy, origin=(0.0, 0.0))
        for opening in ruin.openings:
            opening['polygon'] = sh_scale(opening['polygon'], xfact=sx, yfact=sy, origin=(0.0, 0.0))
        for floor in ruin.floors:
            floor['polygon'] = sh_scale(floor['polygon'], xfact=sx, yfact=sy, origin=(0.0, 0.0))

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


def _instantiate_ruin_rect_12x6_variant1(spec: TerrainPlacementSpec) -> RuinsTerrain:
    """Create and place the 12x6 preset ruin according to the placement spec.

    The preset is authored as a 12x6 rectangle at origin with its distinctive long wall
    along the 12" edge at y=0 (the "bottom" edge in base orientation). We rotate and
    translate it so that its footprint matches the provided rectangle and the long wall
    is flush to the requested side.
    """
    ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant1()

    if len(spec.footprint) != 4:
        raise ValueError("Footprint must contain exactly 4 vertices for rectangular placement")

    # Support rotated placement: use oriented minimum bounding rectangle
    tgt_poly = _ShPoly(spec.footprint)
    if tgt_poly.is_empty or not tgt_poly.is_valid:
        raise ValueError("Invalid footprint polygon for placement")

    mrr = tgt_poly.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)[:-1]
    if len(coords) != 4:
        raise ValueError("Target footprint must be a quadrilateral")

    # Compute side vectors and lengths
    edges = []  # (p0, p1, vec, length)
    for i in range(4):
        p0 = coords[i]
        p1 = coords[(i + 1) % 4]
        vx = p1[0] - p0[0]
        vy = p1[1] - p0[1]
        length = math.hypot(vx, vy)
        edges.append((p0, p1, (vx, vy), length))

    # Identify distinct side lengths (long ~12, short ~6)
    lengths = sorted({round(e[3], 6) for e in edges})
    if len(lengths) != 2:
        raise ValueError("Target footprint edges must have exactly two distinct lengths")
    long_len, short_len = max(lengths), min(lengths)

    # Validate against preset dimensions (allow tiny tolerance)
    base_long, base_short = 12.0, 6.0
    # Accept small numeric deviations (e.g., 12.04/6.02). Use absolute tolerance of 0.1".
    tol = 0.1
    dims_ok = (abs(long_len - base_long) <= tol and abs(short_len - base_short) <= tol) or \
              (abs(long_len - base_short) <= tol and abs(short_len - base_long) <= tol)
    if not dims_ok:
        raise ValueError(
            f"Target footprint sides {long_len:.2f}/{short_len:.2f} do not match preset 12.00/6.00 (no scaling supported)"
        )

    # Determine desired side for long wall based on long_wall_side and world axes
    # Compute outward direction for each edge using centroid->midpoint vector
    centroid = mrr.centroid
    def edge_outward_dir(p0, p1):
        mx, my = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
        nx, ny = mx - centroid.x, my - centroid.y
        nlen = math.hypot(nx, ny) or 1.0
        return (nx / nlen, ny / nlen)

    # Axis preferences for side labels
    axis_target = {
        'right': (1.0, 0.0),
        'left': (-1.0, 0.0),
        'top': (0.0, 1.0),
        'bottom': (0.0, -1.0),
    }[spec.long_wall_side]

    # Filter candidate edges to long edges (length ~ long_len)
    long_edges = [e for e in edges if abs(e[3] - long_len) < tol]
    if not long_edges:
        raise ValueError("Could not identify long edges for target footprint")

    # Pick the long edge whose outward direction best matches the requested side
    best_edge = None
    best_dot = -1e9
    for p0, p1, vec, length in long_edges:
        ox, oy = edge_outward_dir(p0, p1)
        dot = ox * axis_target[0] + oy * axis_target[1]
        if dot > best_dot:
            best_dot = dot
            best_edge = (p0, p1, (ox, oy), vec)

    if best_edge is None:
        raise ValueError("Failed to select matching long edge for long_wall_side")

    # Compute rotation: rotate base outward normal (0,-1) to match selected outward normal
    base_normal = (0.0, -1.0)
    tgt_normal = best_edge[2]
    base_angle = math.atan2(base_normal[1], base_normal[0])
    tgt_angle = math.atan2(tgt_normal[1], tgt_normal[0])
    rotation_degrees = math.degrees(tgt_angle - base_angle)

    # Apply rotation around origin
    ruin = _apply_affine_to_ruins(ruin, rotation_degrees=rotation_degrees, translate_xy=(0.0, 0.0))

    # Translate to align centroids (rigid transform to overlay footprints)
    rcentroid = ruin.footprint.centroid
    dx = centroid.x - rcentroid.x
    dy = centroid.y - rcentroid.y
    ruin = _apply_affine_to_ruins(ruin, rotation_degrees=0.0, translate_xy=(dx, dy))
    return ruin


def _instantiate_from_spec(spec: TerrainPlacementSpec) -> TerrainFeature:
    if spec.preset == 'ruin_rect_12x6_variant1':
        return _instantiate_ruin_rect_12x6_variant1(spec)
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
        ],
        4: [
        ],
        5: [
        ],
        6: [
        ],
        7: [
        ],
        8: [
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


