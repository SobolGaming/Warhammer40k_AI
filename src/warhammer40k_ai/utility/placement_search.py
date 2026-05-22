from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
from shapely.strtree import STRtree

from .calcs import build_formation_templates, get_terrain_blocking_polygons
from .entity_ids import get_entity_id
from .unit_models import alive_unit_group_models, unit_group_models


@dataclass(frozen=True)
class PlacementSearchContext:
    terrain_polygons: tuple[Any, ...]
    boundary_repulsors: tuple[Any, ...]
    blocker_polygons: tuple[Any, ...]
    tree: STRtree
    enemy_blocking_count: int
    friendly_blocking_count: int


def _alive(value: object) -> bool:
    if callable(value):
        return bool(value())
    return bool(value)


def model_longest_radius(model: object) -> float:
    base = getattr(model, "model_base", None)
    if base is None:
        return 0.5
    get_longest_radius = getattr(base, "get_longest_radius", None)
    if callable(get_longest_radius):
        try:
            return float(get_longest_radius() or 0.0)
        except (TypeError, ValueError):
            return 0.5
    get_radius = getattr(base, "get_radius", None)
    if callable(get_radius):
        try:
            return float(get_radius() or 0.0)
        except (TypeError, ValueError):
            return 0.5
    radius = getattr(base, "radius", None)
    if isinstance(radius, (list, tuple)) and radius:
        try:
            return float(radius[0] or 0.0)
        except (TypeError, ValueError):
            return 0.5
    try:
        return float(radius or 0.0)
    except (TypeError, ValueError):
        return 0.5


def unit_largest_model_radius(unit: object) -> float:
    largest = 0.0
    for model in unit_group_models(unit):
        largest = max(float(largest), float(max(0.0, model_longest_radius(model))))
    return float(largest or 0.5)


def estimated_unit_pack_spacing(unit: object) -> float:
    largest = unit_largest_model_radius(unit)
    return float(max(0.5, 2.0 * float(largest) * 0.8))


def estimate_unit_pack_footprint(unit: object) -> dict[str, float]:
    models = int(len(unit_group_models(unit)) or 1)
    largest = unit_largest_model_radius(unit)
    spacing = estimated_unit_pack_spacing(unit)
    cols = int(max(1, int(np.ceil(np.sqrt(models)))))
    rows = int(max(1, int(np.ceil(float(models) / float(cols)))))
    width = float((cols - 1) * spacing + (2.0 * largest))
    depth = float((rows - 1) * spacing + (2.0 * largest))
    radius = float(max(width, depth) * 0.5)
    return {
        "largest_radius": float(largest),
        "spacing": float(spacing),
        "width": float(max(width, 2.0 * largest)),
        "depth": float(max(depth, 2.0 * largest)),
        "radius": float(max(radius, largest)),
    }


def deployed_unit_bounds(unit: object) -> tuple[float, float, float, float] | None:
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")
    found = False
    for model in alive_unit_group_models(unit):
        base = getattr(model, "model_base", None)
        if base is None:
            continue
        get_base_shape = getattr(base, "get_base_shape", None)
        if not callable(get_base_shape):
            continue
        shape = get_base_shape()
        if shape is None or bool(getattr(shape, "is_empty", False)):
            continue
        bx0, by0, bx1, by1 = shape.bounds
        min_x = min(min_x, float(bx0))
        min_y = min(min_y, float(by0))
        max_x = max(max_x, float(bx1))
        max_y = max(max_y, float(by1))
        found = True
    if not found:
        return None
    return (float(min_x), float(min_y), float(max_x), float(max_y))


def build_placement_search_context(
    unit: object,
    game_map: object,
    *,
    avoid_friendly_units: bool,
    boundary_repulsors: list[Any] | tuple[Any, ...] | None = None,
) -> PlacementSearchContext:
    boundary = tuple(list(boundary_repulsors or []) or [])
    terrain_polygons: list[Any] = []
    terrain_features = list(getattr(game_map, "terrain_features", []) or [])
    for terrain_feature in terrain_features:
        terrain_polygons.extend(list(get_terrain_blocking_polygons(unit, terrain_feature) or []))

    enemy_models = list(getattr(game_map, "get_enemy_models", lambda _unit: [])(unit) or [])
    blocking_models = list(enemy_models)
    friendly_count = 0
    if avoid_friendly_units:
        friendly_units = list(getattr(game_map, "get_friendly_units", lambda _unit: [])(unit) or [])
        for friendly_unit in friendly_units:
            if friendly_unit is unit:
                continue
            models = unit_group_models(friendly_unit, include_pending=False)
            blocking_models.extend(models)
            friendly_count += len(models)

    blocker_polygons: list[Any] = []
    for model in list(blocking_models or []):
        alive = _alive(getattr(model, "is_alive", True))
        if not alive:
            continue
        base = getattr(model, "model_base", None)
        if base is None:
            continue
        get_base_shape = getattr(base, "get_base_shape", None)
        if not callable(get_base_shape):
            continue
        shape = get_base_shape()
        if shape is None or bool(getattr(shape, "is_empty", False)):
            continue
        blocker_polygons.append(shape)

    tree = STRtree([*terrain_polygons, *boundary, *blocker_polygons])
    return PlacementSearchContext(
        terrain_polygons=tuple(terrain_polygons),
        boundary_repulsors=boundary,
        blocker_polygons=tuple(blocker_polygons),
        tree=tree,
        enemy_blocking_count=int(len(enemy_models)),
        friendly_blocking_count=int(max(0, friendly_count)),
    )


@lru_cache(maxsize=128)
def _cached_template_rows(model_count: int, spacing_key: float) -> tuple[tuple[str, tuple[tuple[float, float], ...]], ...]:
    templates = build_formation_templates(int(model_count), float(spacing_key))
    frozen: list[tuple[str, tuple[tuple[float, float], ...]]] = []
    for name, offsets in dict(templates or {}).items():
        rows = tuple((float(row[0]), float(row[1])) for row in np.asarray(offsets, dtype=float))
        frozen.append((str(name), rows))
    frozen.sort(key=lambda item: item[0])
    return tuple(frozen)


def cached_formation_templates(model_count: int, spacing: float) -> dict[str, np.ndarray]:
    spacing_key = round(float(spacing), 4)
    rows = _cached_template_rows(int(model_count), float(spacing_key))
    return {
        str(name): np.asarray(values, dtype=float).copy()
        for name, values in rows
    }


def stable_board_occupancy_key(units: list[object] | tuple[object, ...] | None) -> tuple[str, ...]:
    rows: list[str] = []
    for unit in list(units or []):
        unit_id = str(get_entity_id(unit) or "")
        if not unit_id:
            continue
        bounds = deployed_unit_bounds(unit)
        if bounds is None:
            continue
        bx0, by0, bx1, by1 = bounds
        rows.append(
            f"{unit_id}:{bx0:.3f}:{by0:.3f}:{bx1:.3f}:{by1:.3f}"
        )
    rows.sort()
    return tuple(rows)
