from __future__ import annotations

import hashlib
import json
import uuid
from enum import Enum, auto
from typing import Any

from shapely.geometry import Point, Polygon


class TerrainType(Enum):
    """Types of terrain features."""

    CRATER_AND_RUBBLE = auto()
    BARRICADE_AND_FUEL_PIPES = auto()
    DEBRIS_AND_STATUARY = auto()
    HILLS_AND_SEALED_BUILDINGS = auto()
    WOODS = auto()
    RUINS = auto()


class TerrainFeature:
    """Base class for all terrain features using polygon-based approach."""

    def __init__(
        self,
        terrain_type: TerrainType,
        footprint: Polygon,
        bounding_box: dict,
        traversal_rules: dict | None = None,
    ) -> None:
        self._id = str(uuid.uuid4())
        self.terrain_type = terrain_type
        self.footprint = footprint
        self.bounding_box = bounding_box
        self.traversal_rules = traversal_rules or {}
        self.shadow_of_chaos_owner_ids: set[str] = set()

    @property
    def id(self) -> str:
        return self._id

    def point_in_bounds(self, position) -> bool:
        x, y, z = position
        min_x, min_y, min_z = self.bounding_box["min"]
        max_x, max_y, max_z = self.bounding_box["max"]
        return bool(min_x <= x <= max_x and min_y <= y <= max_y and min_z <= z <= max_z)

    def can_unit_traverse(self, unit) -> bool:
        del unit
        return True


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _json_safe(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, set):
        items = [_json_safe(inner) for inner in value]
        return sorted(items, key=lambda inner: str(inner))
    return str(value)


def _footprint_points(footprint: Polygon | None) -> list[list[float]]:
    if footprint is None or not isinstance(footprint, Polygon):
        return []
    exterior = getattr(footprint, "exterior", None)
    coords = list(getattr(exterior, "coords", []) or []) if exterior is not None else []
    points: list[list[float]] = []
    for coord in coords:
        if not isinstance(coord, (list, tuple)) or len(coord) < 2:
            continue
        points.append([_safe_float(coord[0]), _safe_float(coord[1])])
    return points


def terrain_feature_type_name(feature: object) -> str:
    terrain_type_obj = getattr(feature, "terrain_type", None)
    return str(getattr(terrain_type_obj, "name", terrain_type_obj or "") or "").strip()


def build_terrain_area_id(
    *,
    footprint: Polygon | None,
    effect_tags: tuple[str, ...] = (),
    detection_range: float | None = None,
    cover_mode: str = "",
    obscuring: bool = False,
    related_feature_ids: tuple[str, ...] = (),
    layout_slot_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> str:
    payload = {
        "footprint": _footprint_points(footprint),
        "effect_tags": sorted(str(tag) for tag in list(effect_tags or []) if str(tag)),
        "detection_range": None if detection_range is None else _safe_float(detection_range),
        "cover_mode": str(cover_mode or ""),
        "obscuring": bool(obscuring),
        "related_feature_ids": sorted(
            str(feature_id) for feature_id in list(related_feature_ids or []) if str(feature_id)
        ),
        "layout_slot_id": str(layout_slot_id or ""),
        "metadata": _json_safe(dict(metadata or {})),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return f"terrain_area:{digest[:16]}"


class TerrainArea:
    """Terrain-area runtime object kept separate from terrain features."""

    def __init__(
        self,
        footprint: Polygon | None,
        *,
        area_id: str | None = None,
        effect_tags: list[str] | tuple[str, ...] | None = None,
        detection_range: float | None = None,
        cover_mode: str | None = None,
        obscuring: bool = False,
        related_feature_ids: list[str] | tuple[str, ...] | None = None,
        layout_slot_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.footprint = footprint if isinstance(footprint, Polygon) else None
        self.effect_tags = tuple(
            sorted(str(tag) for tag in list(effect_tags or []) if str(tag).strip())
        )
        self.detection_range = None if detection_range is None else _safe_float(detection_range)
        self.cover_mode = str(cover_mode or "")
        self.obscuring = bool(obscuring)
        self.related_feature_ids = tuple(
            sorted(
                str(feature_id)
                for feature_id in list(related_feature_ids or [])
                if str(feature_id).strip()
            )
        )
        self.layout_slot_id = str(layout_slot_id or "")
        self.metadata = dict(metadata or {})
        self._id = str(area_id or "").strip() or build_terrain_area_id(
            footprint=self.footprint,
            effect_tags=self.effect_tags,
            detection_range=self.detection_range,
            cover_mode=self.cover_mode,
            obscuring=self.obscuring,
            related_feature_ids=self.related_feature_ids,
            layout_slot_id=self.layout_slot_id,
            metadata=self.metadata,
        )

    @property
    def id(self) -> str:
        return self._id

    def point_in_footprint(self, position: tuple[float, float, float] | tuple[float, float] | list[float]) -> bool:
        if self.footprint is None:
            return False
        if not isinstance(position, (list, tuple)) or len(position) < 2:
            return False
        x = _safe_float(position[0])
        y = _safe_float(position[1])
        return bool(self.footprint.intersects(Point(x, y)))


def terrain_feature_site_key(feature: object) -> str:
    explicit_key = str(getattr(feature, "objective_site_key", "") or "").strip()
    if explicit_key:
        return explicit_key
    feature_id = str(getattr(feature, "id", "") or "").strip()
    if feature_id:
        return f"terrain_feature:{feature_id}"
    terrain_type = str(getattr(getattr(feature, "terrain_type", None), "name", "") or "").strip().lower()
    return f"terrain_feature:{terrain_type or 'unknown'}"


def resolve_terrain_feature(game_or_map: object, feature_key: str | None) -> object | None:
    key = str(feature_key or "").strip()
    if not key:
        return None
    game_map = getattr(game_or_map, "map", game_or_map)
    for feature in list(getattr(game_map, "terrain_features", []) or []):
        if terrain_feature_site_key(feature) == key:
            return feature
        if str(getattr(feature, "id", "") or "").strip() == key:
            return feature
    return None


def resolve_terrain_feature_footprint(game_or_map: object, feature_key: str | None) -> Polygon | None:
    feature = resolve_terrain_feature(game_or_map, feature_key)
    footprint = getattr(feature, "footprint", None)
    if footprint is None or not isinstance(footprint, Polygon):
        return None
    return footprint


def resolve_terrain_feature_label(game_or_map: object, feature_key: str | None) -> str:
    feature = resolve_terrain_feature(game_or_map, feature_key)
    if feature is None:
        return str(feature_key or "")
    terrain_type_name = terrain_feature_type_name(feature)
    return terrain_type_name or str(feature_key or "")


def terrain_runtime_kind(entity: object) -> str:
    if isinstance(entity, TerrainArea):
        return "AREA"
    return "FEATURE"


def terrain_area_from_feature(feature: object) -> TerrainArea:
    feature_id = str(getattr(feature, "id", "") or "").strip()
    terrain_type_name = terrain_feature_type_name(feature)
    traversal_rules = dict(getattr(feature, "traversal_rules", {}) or {})
    effect_tags = ["FEATURE_ADAPTER"]
    if terrain_type_name:
        effect_tags.append(terrain_type_name)
    if traversal_rules.get("provides_cover", False):
        effect_tags.append("LEGACY_COVER")
    layout_slot_id = str(getattr(feature, "layout_slot_id", "") or "").strip()
    metadata = {
        "adapter_kind": "feature_footprint",
        "source_feature_id": feature_id,
        "source_feature_key": terrain_feature_site_key(feature),
        "source_terrain_type": terrain_type_name,
        "legacy_traversal_rules": traversal_rules,
    }
    return TerrainArea(
        getattr(feature, "footprint", None),
        area_id=f"terrain_area:feature:{feature_id or terrain_type_name.lower() or 'unknown'}",
        effect_tags=effect_tags,
        cover_mode="LEGACY_FEATURE_RULES" if traversal_rules.get("provides_cover", False) else "",
        related_feature_ids=[feature_id] if feature_id else [],
        layout_slot_id=layout_slot_id,
        metadata=metadata,
    )


def iter_explicit_terrain_areas(game_or_map: object) -> list[TerrainArea]:
    game_map = getattr(game_or_map, "map", game_or_map)
    areas = list(getattr(game_map, "terrain_areas", []) or [])
    return sorted(areas, key=lambda area: str(getattr(area, "id", "") or ""))


def iter_terrain_areas(game_or_map: object, *, include_adapters: bool = True) -> list[TerrainArea]:
    game_map = getattr(game_or_map, "map", game_or_map)
    explicit_areas = iter_explicit_terrain_areas(game_map)
    if not include_adapters:
        return explicit_areas

    related_feature_ids: set[str] = set()
    seen_area_ids = {str(getattr(area, "id", "") or "") for area in explicit_areas}
    areas = list(explicit_areas)
    for area in explicit_areas:
        related_feature_ids.update(str(feature_id) for feature_id in list(getattr(area, "related_feature_ids", []) or []))

    terrain_features = list(getattr(game_map, "terrain_features", []) or [])
    terrain_features.sort(key=lambda feature: str(getattr(feature, "id", "") or ""))
    for feature in terrain_features:
        feature_id = str(getattr(feature, "id", "") or "").strip()
        if feature_id and feature_id in related_feature_ids:
            continue
        adapter = terrain_area_from_feature(feature)
        adapter_id = str(getattr(adapter, "id", "") or "")
        if adapter_id in seen_area_ids:
            continue
        areas.append(adapter)
        seen_area_ids.add(adapter_id)
    areas.sort(key=lambda area: str(getattr(area, "id", "") or ""))
    return areas


def iter_runtime_terrain(game_or_map: object) -> list[object]:
    game_map = getattr(game_or_map, "map", game_or_map)
    terrain_features = list(getattr(game_map, "terrain_features", []) or [])
    terrain_features.sort(key=lambda feature: str(getattr(feature, "id", "") or ""))
    runtime_terrain = list(terrain_features)
    runtime_terrain.extend(iter_terrain_areas(game_map))
    runtime_terrain.sort(
        key=lambda entity: (
            0 if terrain_runtime_kind(entity) == "FEATURE" else 1,
            str(getattr(entity, "id", "") or ""),
        )
    )
    return runtime_terrain


def resolve_terrain_area(game_or_map: object, terrain_area_id: str | None) -> TerrainArea | None:
    area_id = str(terrain_area_id or "").strip()
    if not area_id:
        return None
    for area in iter_terrain_areas(game_or_map):
        if str(getattr(area, "id", "") or "").strip() == area_id:
            return area
    return None


def resolve_terrain_area_footprint(game_or_map: object, terrain_area_id: str | None) -> Polygon | None:
    area = resolve_terrain_area(game_or_map, terrain_area_id)
    footprint = getattr(area, "footprint", None)
    if footprint is None or not isinstance(footprint, Polygon):
        return None
    return footprint


def resolve_terrain_area_label(game_or_map: object, terrain_area_id: str | None) -> str:
    area = resolve_terrain_area(game_or_map, terrain_area_id)
    if area is None:
        return str(terrain_area_id or "")
    tags = list(getattr(area, "effect_tags", []) or [])
    if tags:
        return str(tags[0])
    metadata = dict(getattr(area, "metadata", {}) or {})
    label = str(metadata.get("label", "") or metadata.get("source_terrain_type", "") or "").strip()
    return label or str(getattr(area, "id", "") or terrain_area_id or "")


__all__ = [
    "TerrainArea",
    "TerrainFeature",
    "TerrainType",
    "build_terrain_area_id",
    "iter_explicit_terrain_areas",
    "iter_runtime_terrain",
    "iter_terrain_areas",
    "resolve_terrain_feature",
    "resolve_terrain_feature_footprint",
    "resolve_terrain_feature_label",
    "resolve_terrain_area",
    "resolve_terrain_area_footprint",
    "resolve_terrain_area_label",
    "terrain_area_from_feature",
    "terrain_feature_site_key",
    "terrain_feature_type_name",
    "terrain_runtime_kind",
]
