from __future__ import annotations

from typing import Any

from .descriptor_bundle import CompiledDescriptor, descriptor_id, iter_terrain, json_safe, safe_float


def footprint_points(feature: object) -> list[list[float]]:
    footprint = getattr(feature, "footprint", None)
    exterior = getattr(footprint, "exterior", None)
    coords = list(getattr(exterior, "coords", []) or []) if exterior is not None else []
    result: list[list[float]] = []
    for coord in coords:
        if not isinstance(coord, (list, tuple)) or len(coord) < 2:
            continue
        result.append([safe_float(coord[0]), safe_float(coord[1])])
    return result


def terrain_semantic_tags(terrain_type: str) -> list[str]:
    key = str(terrain_type or "").strip().upper()
    if key == "RUINS":
        return ["BLOCKER", "STAGING_ANCHOR", "BREACHABLE_REGION"]
    if key == "WOODS":
        return ["COVER_REGION", "SOFT_BLOCKER"]
    if key == "CRATER_AND_RUBBLE":
        return ["COVER_REGION", "DIFFICULT_REGION"]
    if key == "BARRICADE_AND_FUEL_PIPES":
        return ["LINEAR_BLOCKER", "COVER_REGION"]
    if key == "DEBRIS_AND_STATUARY":
        return ["COVER_REGION", "NO_END_MOVE_REGION"]
    if key == "HILLS_AND_SEALED_BUILDINGS":
        return ["ELEVATION_ANCHOR", "STAGING_ANCHOR"]
    return []


def build_terrain_descriptor_payload(feature: object) -> dict[str, Any]:
    terrain_type_obj = getattr(feature, "terrain_type", None)
    terrain_type = str(getattr(terrain_type_obj, "name", terrain_type_obj or "") or "")
    payload = {
        "terrain_id": str(getattr(feature, "id", "") or ""),
        "terrain_type": terrain_type,
        "geometry": {
            "footprint": footprint_points(feature),
            "bounding_box": json_safe(dict(getattr(feature, "bounding_box", {}) or {})),
        },
        "line_of_sight_semantics": {
            "has_walls": bool(getattr(feature, "walls", None)),
            "has_openings": bool(getattr(feature, "openings", None)),
        },
        "cover_semantics": {
            "provides_cover": bool(dict(getattr(feature, "traversal_rules", {}) or {}).get("provides_cover", False)),
        },
        "movement_semantics": json_safe(dict(getattr(feature, "traversal_rules", {}) or {})),
        "layer_count": int(len(list(getattr(feature, "floors", []) or []))),
        "semantic_tags": terrain_semantic_tags(terrain_type),
    }
    return json_safe(payload)


def compile_terrain_descriptors(game: object) -> tuple[CompiledDescriptor, ...]:
    descriptors: list[CompiledDescriptor] = []
    for feature in iter_terrain(game):
        payload = build_terrain_descriptor_payload(feature)
        descriptors.append(
            CompiledDescriptor(
                family="TerrainDescriptor",
                descriptor_id=descriptor_id("terrain_descriptor", payload),
                payload=payload,
            )
        )
    descriptors.sort(key=lambda descriptor: str(descriptor.descriptor_id))
    return tuple(descriptors)


__all__ = [
    "build_terrain_descriptor_payload",
    "compile_terrain_descriptors",
    "footprint_points",
    "terrain_semantic_tags",
]
