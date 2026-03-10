from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional

from shapely.geometry.base import BaseGeometry

from .surfaces import SupportSurface, extract_ground_transit_obstacles, extract_support_surfaces
from .types import MovementProfile


@dataclass(frozen=True, eq=False)
class WorldSnapshot:
    terrain_revision: str
    support_surface_revision: str
    movement_profile_signature: str
    board_boundary: BaseGeometry
    support_surfaces: tuple[SupportSurface, ...]
    ground_transit_obstacles: tuple[BaseGeometry, ...]


def _hash_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


def _round(value: object) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return 0.0


def _geometry_signature(geometry: BaseGeometry) -> dict[str, object]:
    bounds = tuple(_round(v) for v in geometry.bounds)
    return {
        "bounds": bounds,
        "area": _round(getattr(geometry, "area", 0.0)),
        "length": _round(getattr(geometry, "length", 0.0)),
        "type": str(getattr(geometry, "geom_type", "")),
    }


def _terrain_feature_signature(terrain_index: int, terrain_feature: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "terrain_index": int(terrain_index),
        "terrain_type": str(getattr(getattr(terrain_feature, "terrain_type", None), "name", "")),
    }
    footprint = getattr(terrain_feature, "footprint", None)
    if footprint is not None:
        payload["footprint"] = _geometry_signature(footprint)

    floors_payload: list[dict[str, object]] = []
    for floor_index, floor in enumerate(tuple(getattr(terrain_feature, "floors", ()) or ())):
        if not isinstance(floor, dict):
            continue
        floor_payload: dict[str, object] = {
            "floor_index": int(floor_index),
            "elevation": _round(floor.get("elevation", 0.0)),
            "thickness": _round(floor.get("thickness", 0.0)),
        }
        polygon = floor.get("polygon")
        if polygon is not None:
            floor_payload["polygon"] = _geometry_signature(polygon)
        floors_payload.append(floor_payload)
    if floors_payload:
        payload["floors"] = floors_payload

    walls_payload: list[dict[str, object]] = []
    for wall_index, wall in enumerate(tuple(getattr(terrain_feature, "walls", ()) or ())):
        if not isinstance(wall, dict):
            continue
        wall_payload: dict[str, object] = {
            "wall_index": int(wall_index),
            "z_bottom": _round(wall.get("z_bottom", 0.0)),
            "z_top": _round(wall.get("z_top", 0.0)),
            "thickness": _round(wall.get("thickness", 0.0)),
        }
        polygon = wall.get("polygon")
        if polygon is not None:
            wall_payload["polygon"] = _geometry_signature(polygon)
        walls_payload.append(wall_payload)
    if walls_payload:
        payload["walls"] = walls_payload
    return payload


def terrain_revision(game_map: object) -> str:
    terrain_features = tuple(getattr(game_map, "terrain_features", ()) or ())
    payload: dict[str, object] = {
        "boundary": _geometry_signature(getattr(game_map, "boundary")),
        "terrain": [
            _terrain_feature_signature(terrain_index, terrain_feature)
            for terrain_index, terrain_feature in enumerate(terrain_features)
        ],
    }
    return _hash_payload(payload)


def movement_profile_signature(movement_profile: MovementProfile) -> str:
    payload = asdict(movement_profile)
    return _hash_payload(payload)


def support_surface_revision(support_surfaces: tuple[SupportSurface, ...]) -> str:
    payload = {
        "surfaces": [
            {
                "surface_id": str(surface.surface_id),
                "layer_kind": str(surface.layer_kind),
                "surface_z": _round(surface.surface_z),
                "terrain_index": int(surface.terrain_index),
                "floor_index": -1 if surface.floor_index is None else int(surface.floor_index),
                "terrain_type": str(surface.terrain_type),
                "polygon": _geometry_signature(surface.polygon),
            }
            for surface in support_surfaces
        ]
    }
    return _hash_payload(payload)


def build_world_snapshot(
    game_map: object,
    movement_profile: MovementProfile,
    *,
    precomputed_surfaces: Optional[tuple[SupportSurface, ...]] = None,
) -> WorldSnapshot:
    surfaces = precomputed_surfaces or extract_support_surfaces(game_map)
    ground_obstacles = extract_ground_transit_obstacles(game_map, movement_profile)
    return WorldSnapshot(
        terrain_revision=terrain_revision(game_map),
        support_surface_revision=support_surface_revision(surfaces),
        movement_profile_signature=movement_profile_signature(movement_profile),
        board_boundary=getattr(game_map, "boundary"),
        support_surfaces=tuple(surfaces),
        ground_transit_obstacles=tuple(ground_obstacles),
    )


__all__ = [
    "WorldSnapshot",
    "build_world_snapshot",
    "movement_profile_signature",
    "support_surface_revision",
    "terrain_revision",
]
