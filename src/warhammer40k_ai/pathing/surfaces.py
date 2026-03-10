from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from ..utility.constants import RUINS_FLOOR_THICKNESS
from .types import MovementProfile, SurfaceId

GROUND_SURFACE_ID: SurfaceId = "ground:main"
GROUND_LAYER_KIND = "GROUND"
RUINS_LAYER_KIND = "RUINS_FLOOR"
ELEVATED_LAYER_KIND = "ELEVATED_SUPPORT"


@dataclass(frozen=True, eq=False)
class SupportSurface:
    surface_id: SurfaceId
    layer_kind: str
    polygon: BaseGeometry
    surface_z: float
    terrain_index: int
    floor_index: Optional[int]
    terrain_type: str
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SupportValidationResult:
    valid: bool
    reason: str
    surface_id: Optional[SurfaceId] = None


def _float_or_default(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _surface_sort_key(surface: SupportSurface) -> tuple[float, int, int, int, str]:
    if surface.layer_kind == GROUND_LAYER_KIND:
        layer_rank = 0
    elif surface.layer_kind == RUINS_LAYER_KIND:
        layer_rank = 1
    else:
        layer_rank = 2
    floor_index = surface.floor_index if surface.floor_index is not None else -1
    return (
        float(surface.surface_z),
        layer_rank,
        int(surface.terrain_index),
        int(floor_index),
        str(surface.surface_id),
    )


def _geometry_covers(container: BaseGeometry, target: BaseGeometry) -> bool:
    if hasattr(container, "covers"):
        return bool(container.covers(target))
    return bool(container.contains(target))


def _terrain_top_height(terrain_feature: object) -> float:
    if hasattr(terrain_feature, "height"):
        return _float_or_default(getattr(terrain_feature, "height"), 0.0)
    if hasattr(terrain_feature, "rim_height"):
        return _float_or_default(getattr(terrain_feature, "rim_height"), 0.0)
    bounding_box = getattr(terrain_feature, "bounding_box", None)
    if isinstance(bounding_box, dict):
        max_tuple = bounding_box.get("max")
        if isinstance(max_tuple, (list, tuple)) and len(max_tuple) >= 3:
            return _float_or_default(max_tuple[2], 0.0)
    return 0.0


def _iter_sorted_ruins_floors(terrain_feature: object) -> tuple[tuple[int, dict], ...]:
    indexed_floors: list[tuple[int, dict, float]] = []
    for floor_index, floor in enumerate(tuple(getattr(terrain_feature, "floors", ()) or ())):
        if not isinstance(floor, dict):
            continue
        elevation = _float_or_default(floor.get("elevation"), 0.0)
        indexed_floors.append((floor_index, floor, elevation))
    indexed_floors.sort(key=lambda item: (item[2], item[0]))
    return tuple((item[0], item[1]) for item in indexed_floors)


def extract_support_surfaces(game_map: object) -> tuple[SupportSurface, ...]:
    """Extract deterministic 2.5D support surfaces (ground + explicit elevated supports)."""
    boundary = getattr(game_map, "boundary", None)
    if boundary is None:
        raise ValueError("game_map.boundary is required to extract support surfaces")

    from ..battlefield.map import TerrainType

    surfaces: list[SupportSurface] = [
        SupportSurface(
            surface_id=GROUND_SURFACE_ID,
            layer_kind=GROUND_LAYER_KIND,
            polygon=boundary,
            surface_z=0.0,
            terrain_index=-1,
            floor_index=None,
            terrain_type="BOARD",
            metadata={"label": "Ground"},
        )
    ]

    for terrain_index, terrain_feature in enumerate(tuple(getattr(game_map, "terrain_features", ()) or ())):
        terrain_type = getattr(terrain_feature, "terrain_type", None)

        if terrain_type == TerrainType.RUINS:
            terrain_id = str(getattr(terrain_feature, "id", f"terrain:{terrain_index}") or f"terrain:{terrain_index}")
            for floor_index, floor in _iter_sorted_ruins_floors(terrain_feature):
                floor_polygon = floor.get("polygon")
                if floor_polygon is None:
                    floor_polygon = getattr(terrain_feature, "footprint", None)
                if floor_polygon is None:
                    continue
                elevation = _float_or_default(floor.get("elevation"), 0.0)
                thickness = _float_or_default(floor.get("thickness"), RUINS_FLOOR_THICKNESS)
                surface_z = float(elevation + thickness)
                surfaces.append(
                    SupportSurface(
                        surface_id=f"ruins:{terrain_index}:floor:{floor_index}",
                        layer_kind=RUINS_LAYER_KIND,
                        polygon=floor_polygon,
                        surface_z=surface_z,
                        terrain_index=terrain_index,
                        floor_index=floor_index,
                        terrain_type="RUINS",
                        metadata={
                            "terrain_id": terrain_id,
                            "elevation": elevation,
                            "thickness": thickness,
                        },
                    )
                )
            continue

        if terrain_type == TerrainType.HILLS_AND_SEALED_BUILDINGS:
            top_polygon = getattr(terrain_feature, "footprint", None)
            if top_polygon is None:
                continue
            top_z = _terrain_top_height(terrain_feature)
            if top_z <= 0.0:
                continue
            surfaces.append(
                SupportSurface(
                    surface_id=f"elevated:{terrain_index}:top",
                    layer_kind=ELEVATED_LAYER_KIND,
                    polygon=top_polygon,
                    surface_z=float(top_z),
                    terrain_index=terrain_index,
                    floor_index=0,
                    terrain_type="HILLS_AND_SEALED_BUILDINGS",
                    metadata={},
                )
            )

    surfaces.sort(key=_surface_sort_key)
    return tuple(surfaces)


def terrain_ignored_for_ground_transit(
    terrain_feature: object,
    movement_profile: MovementProfile,
) -> bool:
    """Return True when a terrain feature should not be treated as a ground routing obstacle."""
    from ..battlefield.map import TerrainType

    threshold = float(movement_profile.free_climb_height_inches)
    terrain_type = getattr(terrain_feature, "terrain_type", None)

    if terrain_type == TerrainType.RUINS:
        if movement_profile.can_breach_ruins_walls:
            return True
        if bool(movement_profile.terrain_transition_rules.get("is_fly_move", False)):
            return True
        for wall in tuple(getattr(terrain_feature, "walls", ()) or ()):
            if not isinstance(wall, dict):
                continue
            z_bottom = _float_or_default(wall.get("z_bottom"), 0.0)
            z_top = _float_or_default(wall.get("z_top"), 0.0)
            if (z_top - z_bottom) > threshold:
                return False
        return True

    if terrain_type == TerrainType.BARRICADE_AND_FUEL_PIPES:
        return _terrain_top_height(terrain_feature) <= threshold

    return _terrain_top_height(terrain_feature) <= threshold


def extract_ground_transit_obstacles(
    game_map: object,
    movement_profile: MovementProfile,
) -> tuple[BaseGeometry, ...]:
    """
    Extract deterministic static obstacle geometry for the ground layer.

    Low terrain (<= free_climb_height_inches) is omitted.
    """
    from ..battlefield.map import TerrainType

    obstacles: list[BaseGeometry] = []
    terrain_features = tuple(getattr(game_map, "terrain_features", ()) or ())
    threshold = float(movement_profile.free_climb_height_inches)
    fly_move = bool(movement_profile.terrain_transition_rules.get("is_fly_move", False))

    for terrain_feature in terrain_features:
        terrain_type = getattr(terrain_feature, "terrain_type", None)
        if terrain_type == TerrainType.RUINS:
            if movement_profile.can_breach_ruins_walls or fly_move:
                continue
            for wall in tuple(getattr(terrain_feature, "walls", ()) or ()):
                if not isinstance(wall, dict):
                    continue
                z_bottom = _float_or_default(wall.get("z_bottom"), 0.0)
                z_top = _float_or_default(wall.get("z_top"), 0.0)
                if (z_top - z_bottom) <= threshold:
                    continue
                wall_polygon = wall.get("polygon")
                if wall_polygon is not None:
                    obstacles.append(wall_polygon)
            continue

        if terrain_ignored_for_ground_transit(terrain_feature, movement_profile):
            continue
        if terrain_type == TerrainType.BARRICADE_AND_FUEL_PIPES:
            traversal_rules = getattr(terrain_feature, "traversal_rules", {}) or {}
            if not bool(traversal_rules.get("blocks_vehicles", False)):
                continue
            if not bool(movement_profile.terrain_transition_rules.get("is_vehicle_unit", False)):
                continue
            footprint = getattr(terrain_feature, "footprint", None)
            if footprint is not None:
                obstacles.append(footprint)

    # Stable ordering by bounds keeps deterministic obstacle sequence.
    obstacles.sort(key=lambda geom: tuple(round(v, 6) for v in geom.bounds))
    return tuple(obstacles)


def resolve_support_surface_at_position(
    surfaces: Iterable[SupportSurface],
    *,
    x: float,
    y: float,
    z: float,
    max_vertical_gap: float = 0.75,
) -> Optional[SupportSurface]:
    point = Point(float(x), float(y))
    candidates: list[tuple[float, float, str, SupportSurface]] = []
    for surface in tuple(surfaces):
        if not _geometry_covers(surface.polygon, point):
            continue
        vertical_gap = abs(float(surface.surface_z) - float(z))
        if vertical_gap > float(max_vertical_gap):
            continue
        candidates.append((vertical_gap, -float(surface.surface_z), str(surface.surface_id), surface))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][3]


def erode_support_polygon_for_circular_base(
    support_polygon: BaseGeometry,
    radius: float,
) -> BaseGeometry:
    if float(radius) <= 0.0:
        return support_polygon
    return support_polygon.buffer(-float(radius), quad_segs=16)


def validate_pose_support_on_surface(
    model_base: object,
    *,
    x: float,
    y: float,
    facing: float,
    surface: SupportSurface,
) -> SupportValidationResult:
    """Validate that a base pose is wholly supported by the selected support surface."""
    if surface.layer_kind == GROUND_LAYER_KIND:
        return SupportValidationResult(valid=True, reason="Ground surface", surface_id=surface.surface_id)

    has_compound_parts = bool(getattr(model_base, "has_compound_parts", lambda: False)())
    is_circular = bool(getattr(model_base, "has_circular_base", False))

    if is_circular and not has_compound_parts:
        radius_tuple = getattr(model_base, "radius", (0.0, 0.0))
        radius = _float_or_default(radius_tuple[0] if isinstance(radius_tuple, tuple) else radius_tuple, 0.0)
        eroded = erode_support_polygon_for_circular_base(surface.polygon, radius)
        if eroded.is_empty:
            return SupportValidationResult(
                valid=False,
                reason="Support area is smaller than base radius",
                surface_id=surface.surface_id,
            )
        center = Point(float(x), float(y))
        if _geometry_covers(eroded, center):
            return SupportValidationResult(valid=True, reason="Circular base fully supported", surface_id=surface.surface_id)
        return SupportValidationResult(valid=False, reason="Circular base would overhang support", surface_id=surface.surface_id)

    base_shape = model_base.get_base_shape_at(float(x), float(y), float(facing))
    if _geometry_covers(surface.polygon, base_shape):
        return SupportValidationResult(valid=True, reason="Exact base footprint supported", surface_id=surface.surface_id)
    return SupportValidationResult(valid=False, reason="Base footprint would overhang support", surface_id=surface.surface_id)


def validate_pose_support(
    model_base: object,
    surfaces: Iterable[SupportSurface],
    *,
    x: float,
    y: float,
    z: float,
    facing: float,
    max_vertical_gap: float = 0.75,
) -> SupportValidationResult:
    surface = resolve_support_surface_at_position(
        surfaces,
        x=float(x),
        y=float(y),
        z=float(z),
        max_vertical_gap=float(max_vertical_gap),
    )
    if surface is None:
        return SupportValidationResult(valid=False, reason="No support surface at pose", surface_id=None)
    return validate_pose_support_on_surface(
        model_base,
        x=float(x),
        y=float(y),
        facing=float(facing),
        surface=surface,
    )


__all__ = [
    "ELEVATED_LAYER_KIND",
    "GROUND_LAYER_KIND",
    "GROUND_SURFACE_ID",
    "RUINS_LAYER_KIND",
    "SupportSurface",
    "SupportValidationResult",
    "erode_support_polygon_for_circular_base",
    "extract_ground_transit_obstacles",
    "extract_support_surfaces",
    "resolve_support_surface_at_position",
    "terrain_ignored_for_ground_transit",
    "validate_pose_support",
    "validate_pose_support_on_surface",
]
