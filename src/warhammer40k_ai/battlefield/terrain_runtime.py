from __future__ import annotations

import uuid
from enum import Enum, auto
from typing import Any

from shapely.geometry import Polygon


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
    terrain_type_obj = getattr(feature, "terrain_type", None)
    terrain_type_name = str(getattr(terrain_type_obj, "name", terrain_type_obj or "") or "").strip()
    return terrain_type_name or str(feature_key or "")


__all__ = [
    "TerrainFeature",
    "TerrainType",
    "resolve_terrain_feature",
    "resolve_terrain_feature_footprint",
    "resolve_terrain_feature_label",
    "terrain_feature_site_key",
]
