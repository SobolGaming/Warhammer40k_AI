from __future__ import annotations

from typing import Any

from ..battlefield.terrain_runtime import iter_terrain_areas
from ..battlefield.detection_markers import detection_markers_on_map
from ..battlefield.hidden_state import hidden_shooting_exemptions_on_map
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


def _terrain_cache_entry_signature(entity: object) -> tuple[object, ...]:
    terrain_type_obj = getattr(entity, "terrain_type", None)
    footprint = getattr(entity, "footprint", None)
    exterior = getattr(footprint, "exterior", None)
    coords = getattr(exterior, "coords", None) if exterior is not None else None
    try:
        coord_count = len(coords) if coords is not None else 0
    except TypeError:
        coord_count = 0
    return (
        str(getattr(entity, "id", "") or ""),
        str(getattr(terrain_type_obj, "name", terrain_type_obj or "") or ""),
        id(footprint),
        int(coord_count),
        str(getattr(entity, "bounding_box", "") or ""),
        str(getattr(entity, "traversal_rules", "") or ""),
        str(getattr(entity, "effect_tags", "") or ""),
        str(getattr(entity, "related_feature_ids", "") or ""),
        str(getattr(entity, "metadata", "") or ""),
    )


def _terrain_entries_cache_key(game: object) -> tuple[object, ...]:
    game_map = getattr(game, "map", None)
    features = list(getattr(game_map, "terrain_features", []) or [])
    features.sort(key=lambda feature: str(getattr(feature, "id", "") or ""))
    areas = iter_terrain_areas(game)
    return (
        "terrain_entries_v1",
        tuple(_terrain_cache_entry_signature(feature) for feature in features),
        tuple(_terrain_cache_entry_signature(area) for area in areas),
    )


def _copy_terrain_entries(entries: object) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for entry in list(entries or []):
        if isinstance(entry, dict):
            copied.append(dict(entry))
    return copied


def terrain_entries(game: object) -> list[dict[str, Any]]:
    game_map = getattr(game, "map", None)
    cache = getattr(game_map, "_state_blob_terrain_entries_cache", None) if game_map is not None else None
    cache_key = _terrain_entries_cache_key(game)
    if isinstance(cache, dict):
        cached = cache.get(cache_key)
        if cached is not None:
            return _copy_terrain_entries(cached)
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
    if game_map is not None:
        if not isinstance(cache, dict):
            cache = {}
            try:
                setattr(game_map, "_state_blob_terrain_entries_cache", cache)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                cache = None
        if isinstance(cache, dict):
            cache.clear()
            cache[cache_key] = tuple(dict(entry) for entry in entries)
    return entries


def detection_marker_entries(game: object) -> list[dict[str, Any]]:
    game_map = getattr(game, "map", game)
    entries = [json_safe(marker.to_dict()) for marker in detection_markers_on_map(game_map)]
    entries.sort(
        key=lambda entry: (
            str(entry.get("target_unit_id", "") or ""),
            str(entry.get("marker_id", "") or ""),
            str(entry.get("source_unit_id", "") or ""),
        )
    )
    return entries


def hidden_shooting_exemption_entries(game: object) -> list[dict[str, Any]]:
    game_map = getattr(game, "map", game)
    entries = [json_safe(exemption.to_dict()) for exemption in hidden_shooting_exemptions_on_map(game_map)]
    entries.sort(
        key=lambda entry: (
            str(entry.get("unit_id", "") or ""),
            str(entry.get("exemption_id", "") or ""),
            str(entry.get("source_id", "") or ""),
        )
    )
    return entries


__all__ = ["detection_marker_entries", "hidden_shooting_exemption_entries", "terrain_entries"]
