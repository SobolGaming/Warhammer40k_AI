from __future__ import annotations

from typing import Any

from .state_blob_rules import json_safe, safe_float


def terrain_entries(game: object) -> list[dict[str, Any]]:
    game_map = getattr(game, "map", None)
    terrain = list(getattr(game_map, "terrain_features", []) or [])
    entries: list[dict[str, Any]] = []
    for idx, feature in enumerate(terrain):
        feature_id = str(getattr(feature, "id", "") or f"terrain_{idx}")
        terrain_type_obj = getattr(feature, "terrain_type", None)
        terrain_type_name = str(getattr(terrain_type_obj, "name", terrain_type_obj or "") or "")
        footprint = getattr(feature, "footprint", None)
        footprint_coords: list[list[float]] = []
        exterior = getattr(footprint, "exterior", None)
        coords = list(getattr(exterior, "coords", []) or []) if exterior is not None else []
        for coord in coords:
            if len(coord) >= 2:
                footprint_coords.append([safe_float(coord[0]), safe_float(coord[1])])
        bounding_box = json_safe(dict(getattr(feature, "bounding_box", {}) or {}))
        traversal_rules = json_safe(dict(getattr(feature, "traversal_rules", {}) or {}))
        entries.append(
            {
                "terrain_id": feature_id,
                "terrain_type": terrain_type_name,
                "footprint": footprint_coords,
                "bounding_box": bounding_box,
                "traversal_rules": traversal_rules,
            }
        )
    entries.sort(key=lambda entry: str(entry["terrain_id"]))
    return entries


__all__ = ["terrain_entries"]
