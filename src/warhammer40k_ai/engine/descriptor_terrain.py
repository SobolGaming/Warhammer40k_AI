from __future__ import annotations

from typing import Any

from ..battlefield.terrain_runtime import terrain_feature_type_name, terrain_runtime_kind
from .descriptor_bundle import CompiledDescriptor, descriptor_id, iter_terrain, json_safe, safe_float


def footprint_points(entity: object) -> list[list[float]]:
    footprint = getattr(entity, "footprint", None)
    exterior = getattr(footprint, "exterior", None)
    coords = list(getattr(exterior, "coords", []) or []) if exterior is not None else []
    result: list[list[float]] = []
    for coord in coords:
        if not isinstance(coord, (list, tuple)) or len(coord) < 2:
            continue
        result.append([safe_float(coord[0]), safe_float(coord[1])])
    return result


def terrain_feature_semantic_tags(terrain_type: str) -> list[str]:
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


def terrain_area_semantic_tags(area: object) -> list[str]:
    tags = [str(tag) for tag in list(getattr(area, "effect_tags", []) or []) if str(tag).strip()]
    if bool(getattr(area, "obscuring", False)):
        tags.append("OBSCURING_AREA")
    cover_mode = str(getattr(area, "cover_mode", "") or "").strip()
    if cover_mode:
        tags.append(f"COVER_MODE:{cover_mode}")
    detection_range = getattr(area, "detection_range", None)
    if detection_range is not None:
        tags.append("DETECTION_RANGE")
    return sorted(set(tags))


def build_terrain_descriptor_payload(entity: object) -> dict[str, Any]:
    runtime_kind = terrain_runtime_kind(entity)
    if runtime_kind == "AREA":
        payload = {
            "terrain_id": str(getattr(entity, "id", "") or ""),
            "terrain_runtime_kind": "AREA",
            "terrain_type": "TERRAIN_AREA",
            "geometry": {
                "footprint": footprint_points(entity),
                "bounding_box": {},
            },
            "line_of_sight_semantics": {
                "obscuring": bool(getattr(entity, "obscuring", False)),
                "blocks_visibility_through_area": bool(getattr(entity, "obscuring", False)),
            },
            "cover_semantics": {
                "provides_cover": bool(str(getattr(entity, "cover_mode", "") or "").strip()),
                "cover_mode": str(getattr(entity, "cover_mode", "") or ""),
            },
            "movement_semantics": {},
            "layer_count": 0,
            "semantic_tags": terrain_area_semantic_tags(entity),
            "terrain_area": {
                "terrain_area_id": str(getattr(entity, "id", "") or ""),
                "effect_tags": [str(tag) for tag in list(getattr(entity, "effect_tags", []) or []) if str(tag)],
                "detection_range": getattr(entity, "detection_range", None),
                "related_feature_ids": [
                    str(feature_id)
                    for feature_id in list(getattr(entity, "related_feature_ids", []) or [])
                    if str(feature_id)
                ],
                "layout_slot_id": str(getattr(entity, "layout_slot_id", "") or ""),
                "metadata": json_safe(dict(getattr(entity, "metadata", {}) or {})),
            },
        }
        return json_safe(payload)

    terrain_type = terrain_feature_type_name(entity)
    payload = {
        "terrain_id": str(getattr(entity, "id", "") or ""),
        "terrain_runtime_kind": "FEATURE",
        "terrain_type": terrain_type,
        "geometry": {
            "footprint": footprint_points(entity),
            "bounding_box": json_safe(dict(getattr(entity, "bounding_box", {}) or {})),
        },
        "line_of_sight_semantics": {
            "has_walls": bool(getattr(entity, "walls", None)),
            "has_openings": bool(getattr(entity, "openings", None)),
        },
        "cover_semantics": {
            "provides_cover": bool(dict(getattr(entity, "traversal_rules", {}) or {}).get("provides_cover", False)),
        },
        "movement_semantics": json_safe(dict(getattr(entity, "traversal_rules", {}) or {})),
        "layer_count": int(len(list(getattr(entity, "floors", []) or []))),
        "semantic_tags": terrain_feature_semantic_tags(terrain_type),
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
    "terrain_area_semantic_tags",
    "terrain_feature_semantic_tags",
]
