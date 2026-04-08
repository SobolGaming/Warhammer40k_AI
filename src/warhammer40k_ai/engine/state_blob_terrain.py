from __future__ import annotations

from typing import Any

from ..battlefield.terrain_runtime import iter_terrain_areas
from .state_blob_rules import json_safe, safe_float


def _footprint_coords(entity: object) -> list[list[float]]:
    footprint = getattr(entity, "footprint", None)
    footprint_coords: list[list[float]] = []
    exterior = getattr(footprint, "exterior", None)
    coords = list(getattr(exterior, "coords", []) or []) if exterior is not None else []
    for coord in coords:
        if len(coord) >= 2:
            footprint_coords.append([safe_float(coord[0]), safe_float(coord[1])])
    return footprint_coords


def terrain_entries(game: object) -> list[dict[str, Any]]:
    game_map = getattr(game, "map", None)
    features = list(getattr(game_map, "terrain_features", []) or [])
    features.sort(key=lambda feature: str(getattr(feature, "id", "") or ""))
    entries: list[dict[str, Any]] = []
    for idx, feature in enumerate(features):
        feature_id = str(getattr(feature, "id", "") or f"terrain_{idx}")
        terrain_type_obj = getattr(feature, "terrain_type", None)
        terrain_type_name = str(getattr(terrain_type_obj, "name", terrain_type_obj or "") or "")
        bounding_box = json_safe(dict(getattr(feature, "bounding_box", {}) or {}))
        traversal_rules = json_safe(dict(getattr(feature, "traversal_rules", {}) or {}))
        entries.append(
            {
                "terrain_id": feature_id,
                "runtime_kind": "FEATURE",
                "terrain_type": terrain_type_name,
                "footprint": _footprint_coords(feature),
                "bounding_box": bounding_box,
                "traversal_rules": traversal_rules,
            }
        )

    for area in iter_terrain_areas(game):
        detection_range = getattr(area, "detection_range", None)
        entries.append(
            {
                "terrain_id": str(getattr(area, "id", "") or ""),
                "runtime_kind": "AREA",
                "terrain_type": "TERRAIN_AREA",
                "footprint": _footprint_coords(area),
                "effect_tags": sorted(
                    str(tag) for tag in list(getattr(area, "effect_tags", []) or []) if str(tag)
                ),
                "detection_range": None if detection_range is None else safe_float(detection_range),
                "cover_mode": str(getattr(area, "cover_mode", "") or ""),
                "obscuring": bool(getattr(area, "obscuring", False)),
                "related_feature_ids": sorted(
                    str(feature_id)
                    for feature_id in list(getattr(area, "related_feature_ids", []) or [])
                    if str(feature_id)
                ),
                "layout_slot_id": str(getattr(area, "layout_slot_id", "") or ""),
                "metadata": json_safe(dict(getattr(area, "metadata", {}) or {})),
            }
        )

    entries.sort(
        key=lambda entry: (
            0 if str(entry.get("runtime_kind", "") or "") == "FEATURE" else 1,
            str(entry["terrain_id"]),
        )
    )
    return entries


__all__ = ["terrain_entries"]
