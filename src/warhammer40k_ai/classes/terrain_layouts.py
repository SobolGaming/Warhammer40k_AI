from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Literal

from shapely.affinity import rotate as sh_rotate, translate as sh_translate, scale as sh_scale

from .map import TerrainFeature, TerrainFactory, RuinsTerrain


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

    # Determine target bounds and dimensions
    xs = [p[0] for p in spec.footprint]
    ys = [p[1] for p in spec.footprint]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    target_width = x_max - x_min
    target_height = y_max - y_min

    # Base preset dims
    base_width = 12.0
    base_height = 6.0

    # Validate proportions; allow exact or swapped orientation. No arbitrary scaling for now.
    dims_ok = (
        abs(target_width - base_width) < 1e-6 and abs(target_height - base_height) < 1e-6
    ) or (
        abs(target_width - base_height) < 1e-6 and abs(target_height - base_width) < 1e-6
    )
    if not dims_ok:
        raise ValueError(
            f"Target footprint {target_width:.2f}x{target_height:.2f} does not match preset 12.00x6.00 (no scaling supported)"
        )

    # Decide rotation to align long side and place designated long wall edge.
    rotation_degrees = 0.0
    translate_xy = (0.0, 0.0)

    if target_width > target_height:  # 12x6 orientation (long edge horizontal)
        # Long wall is authored on the bottom (south) edge at y=0.
        if spec.long_wall_side not in ('bottom', 'top'):
            raise ValueError("For 12x6 horizontal placement, long_wall_side must be 'bottom' or 'top'")
        if spec.long_wall_side == 'bottom':
            rotation_degrees = 0.0  # keep south -> bottom
        else:  # 'top'
            rotation_degrees = 180.0  # south -> top
    else:  # 6x12 orientation (long edge vertical)
        if spec.long_wall_side not in ('left', 'right'):
            raise ValueError("For 6x12 vertical placement, long_wall_side must be 'left' or 'right'")
        if spec.long_wall_side == 'right':
            # Rotate -90deg: south edge maps to east (right)
            rotation_degrees = -90.0
        else:  # 'left'
            # Rotate +90deg: south edge maps to west (left)
            rotation_degrees = 90.0
    
    # First apply rotation around origin
    ruin = _apply_affine_to_ruins(ruin, rotation_degrees=rotation_degrees, translate_xy=(0.0, 0.0))
    
    # Compute rotated bounds and translate so that min corner aligns to (x_min, y_min)
    rminx, rminy, rmaxx, rmaxy = ruin.footprint.bounds
    dx = x_min - rminx
    dy = y_min - rminy
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
        # Layout 1 example with two 6x12-placed ruins and explicit long wall orientation
        1: [
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(16.0, 28.0), (22.0, 28.0), (22.0, 40.0), (16.0, 40.0)],
                long_wall_side='left',
            ),
            TerrainPlacementSpec(
                preset='ruin_rect_12x6_variant1',
                footprint=[(38.0, 4.0), (44.0, 4.0), (44.0, 16.0), (38.0, 16.0)],
                long_wall_side='right',
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
        feature = _instantiate_from_spec(spec)
        features.append(feature)
    return features


