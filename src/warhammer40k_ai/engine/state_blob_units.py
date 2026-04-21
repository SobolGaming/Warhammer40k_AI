from __future__ import annotations

from typing import Any

from ..battlefield.control_queries import deserialize_polygon_geometry
from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
from ..utility.entity_ids import get_entity_id
from .state_blob_objectives import objective_entries
from .state_blob_rules import safe_float, sorted_players


def alive_models(unit: object) -> list[object]:
    models = list(getattr(unit, "models", []) or [])
    alive: list[object] = []
    for model in models:
        is_alive_value = getattr(model, "is_alive", True)
        alive_flag = bool(is_alive_value() if callable(is_alive_value) else is_alive_value)
        if alive_flag:
            alive.append(model)
    return alive


def model_position(model: object) -> tuple[float, float, float]:
    getter = getattr(model, "get_location", None)
    if callable(getter):
        location = getter()
        if isinstance(location, (list, tuple)) and len(location) >= 3:
            return (safe_float(location[0]), safe_float(location[1]), safe_float(location[2]))
    base = getattr(model, "model_base", None)
    return (
        safe_float(getattr(base, "x", 0.0), 0.0),
        safe_float(getattr(base, "y", 0.0), 0.0),
        safe_float(getattr(base, "z", 0.0), 0.0),
    )


def unit_centroid(unit: object, *, alive_models_override: list[object] | None = None) -> tuple[float, float, float]:
    models = list(alive_models_override) if alive_models_override is not None else alive_models(unit)
    if not models:
        position = getattr(unit, "position", None)
        if isinstance(position, (list, tuple)) and len(position) >= 3:
            return (safe_float(position[0]), safe_float(position[1]), safe_float(position[2]))
        if isinstance(position, (list, tuple)) and len(position) >= 2:
            return (safe_float(position[0]), safe_float(position[1]), 0.0)
        return (0.0, 0.0, 0.0)
    total_x = 0.0
    total_y = 0.0
    total_z = 0.0
    for model in models:
        x, y, z = model_position(model)
        total_x += x
        total_y += y
        total_z += z
    count = float(len(models))
    return (total_x / count, total_y / count, total_z / count)


def _reserve_metadata_value(unit: object, key: str, default: Any = "") -> Any:
    value = getattr(unit, key, None)
    if value not in (None, ""):
        return value
    special_rules = getattr(unit, "special_rules", None)
    if isinstance(special_rules, dict):
        return special_rules.get(key, default)
    return default


def reserve_last_arrival_failure(unit: object) -> dict[str, Any] | str:
    failure = _reserve_metadata_value(unit, "reserve_last_arrival_failure", "")
    if not isinstance(failure, dict):
        return str(failure or "")
    return {
        "reason": str(failure.get("reason", "") or ""),
        "anchor_attempts": int(failure.get("anchor_attempts", 0) or 0),
        "build_calls": int(failure.get("build_calls", 0) or 0),
        "validation_rejects": int(failure.get("validation_rejects", 0) or 0),
        "quick_rejects": int(failure.get("quick_rejects", 0) or 0),
        "timed_out": bool(failure.get("timed_out", False)),
        "elapsed_ms": int(failure.get("elapsed_ms", 0) or 0),
    }


def distance_2d(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    return ((dx * dx) + (dy * dy)) ** 0.5


def fast_horizontal_edge_distance(base_a: object, base_b: object) -> float | None:
    try:
        circular_a = bool(getattr(base_a, "has_circular_base", False))
        circular_b = bool(getattr(base_b, "has_circular_base", False))
        if not (circular_a and circular_b):
            return None
        ax = safe_float(getattr(base_a, "x", 0.0), 0.0)
        ay = safe_float(getattr(base_a, "y", 0.0), 0.0)
        bx = safe_float(getattr(base_b, "x", 0.0), 0.0)
        by = safe_float(getattr(base_b, "y", 0.0), 0.0)
        ar = safe_float(getattr(base_a, "get_radius", lambda: 0.0)(), 0.0)
        br = safe_float(getattr(base_b, "get_radius", lambda: 0.0)(), 0.0)
    except (AttributeError, TypeError, ValueError):
        return None
    center_distance = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    return max(0.0, float(center_distance - (ar + br)))


def base_horizontal_radius(base: object) -> float:
    try:
        if bool(getattr(base, "has_circular_base", False)):
            return max(0.0, safe_float(getattr(base, "get_radius", lambda: 0.0)(), 0.0))
        longest_radius_fn = getattr(base, "get_longest_radius", None)
        if callable(longest_radius_fn):
            return max(0.0, safe_float(longest_radius_fn(), 0.0))
    except (AttributeError, TypeError, ValueError):
        return 0.0
    return 0.0


def unit_outer_radius(
    unit: object,
    *,
    centroid: tuple[float, float, float] | None = None,
    alive_models_override: list[object] | None = None,
) -> float:
    models = list(alive_models_override) if alive_models_override is not None else alive_models(unit)
    if not models:
        return 0.0
    cx, cy, _cz = centroid if centroid is not None else unit_centroid(unit)
    outer = 0.0
    for model in models:
        base = getattr(model, "model_base", None)
        if base is None:
            continue
        bx = safe_float(getattr(base, "x", 0.0), 0.0)
        by = safe_float(getattr(base, "y", 0.0), 0.0)
        radius = base_horizontal_radius(base)
        dist = (((bx - cx) ** 2) + ((by - cy) ** 2)) ** 0.5 + radius
        if dist > outer:
            outer = dist
    return float(outer)


def max_movement(unit: object) -> float:
    models = alive_models(unit)
    if not models:
        return 0.0
    max_move = 0.0
    for model in models:
        value = getattr(model, "_movement", None)
        if value is None:
            value = getattr(model, "movement", 0)
        max_move = max(max_move, safe_float(value, 0.0))
    return max_move


def is_unit_in_engagement_range(
    unit: object,
    enemy_units: list[object],
    *,
    centroid_cache: dict[str, tuple[float, float, float]] | None = None,
    outer_radius_cache: dict[str, float] | None = None,
    alive_models_cache: dict[str, list[object]] | None = None,
) -> bool:
    unit_id = str(get_entity_id(unit))
    if alive_models_cache is not None and unit_id in alive_models_cache:
        unit_models = list(alive_models_cache[unit_id])
    else:
        unit_models = alive_models(unit)
        if alive_models_cache is not None:
            alive_models_cache[unit_id] = list(unit_models)
    if not unit_models:
        return False

    if centroid_cache is not None and unit_id in centroid_cache:
        centroid = tuple(centroid_cache[unit_id])
    else:
        centroid = unit_centroid(unit, alive_models_override=unit_models)
        if centroid_cache is not None:
            centroid_cache[unit_id] = centroid
    if outer_radius_cache is not None and unit_id in outer_radius_cache:
        outer = safe_float(outer_radius_cache[unit_id], 0.0)
    else:
        outer = unit_outer_radius(unit, centroid=centroid, alive_models_override=unit_models)
        if outer_radius_cache is not None:
            outer_radius_cache[unit_id] = float(outer)
    max_engagement = float(ENGAGEMENT_RANGE_HORIZONTAL)

    for model in unit_models:
        base = getattr(model, "model_base", None)
        if base is None:
            continue
        for enemy in enemy_units:
            enemy_id = str(get_entity_id(enemy))
            if alive_models_cache is not None and enemy_id in alive_models_cache:
                enemy_models = list(alive_models_cache[enemy_id])
            else:
                enemy_models = alive_models(enemy)
                if alive_models_cache is not None:
                    alive_models_cache[enemy_id] = list(enemy_models)
            if not enemy_models:
                continue
            if centroid_cache is not None and enemy_id in centroid_cache:
                enemy_centroid = tuple(centroid_cache[enemy_id])
            else:
                enemy_centroid = unit_centroid(enemy, alive_models_override=enemy_models)
                if centroid_cache is not None:
                    centroid_cache[enemy_id] = enemy_centroid
            if outer_radius_cache is not None and enemy_id in outer_radius_cache:
                enemy_outer = safe_float(outer_radius_cache[enemy_id], 0.0)
            else:
                enemy_outer = unit_outer_radius(
                    enemy,
                    centroid=enemy_centroid,
                    alive_models_override=enemy_models,
                )
                if outer_radius_cache is not None:
                    outer_radius_cache[enemy_id] = float(enemy_outer)
            if distance_2d(centroid, enemy_centroid) > (outer + enemy_outer + max_engagement):
                continue
            for enemy_model in enemy_models:
                enemy_base = getattr(enemy_model, "model_base", None)
                if enemy_base is None:
                    continue
                horizontal = fast_horizontal_edge_distance(base, enemy_base)
                if horizontal is None:
                    horizontal = safe_float(base.edge_to_edge_distance(enemy_base), 9999.0)
                vertical = abs(safe_float(getattr(base, "z", 0.0)) - safe_float(getattr(enemy_base, "z", 0.0)))
                if horizontal <= float(ENGAGEMENT_RANGE_HORIZONTAL) and vertical <= float(ENGAGEMENT_RANGE_VERTICAL):
                    return True
    return False


def objective_ids_in_range(unit: object, entries: list[dict[str, Any]]) -> list[str]:
    in_range: list[str] = []
    for model in alive_models(unit):
        x, y, _z = model_position(model)
        base = getattr(model, "model_base", None)
        model_radius = safe_float(getattr(base, "get_radius", lambda: 0.0)(), 0.0) if base is not None else 0.0
        for objective in entries:
            control_region = dict(objective.get("control_region", {}) or {})
            kind = str(control_region.get("kind", "") or "").upper()
            if kind in {"OBJECTIVE_CONTROL_FOOTPRINT", "OBJECTIVE_CONTROL_KEYED_FEATURE"}:
                footprint = deserialize_polygon_geometry(control_region.get("footprint"))
                if footprint is None:
                    continue
                try:
                    if base is not None and base.get_base_shape().intersects(footprint):
                        in_range.append(str(objective["objective_id"]))
                except (AttributeError, TypeError, ValueError):
                    continue
                continue
            ox, oy, _oz = control_region.get("center", objective["position"])
            control_radius = safe_float(control_region.get("radius", objective["control_radius"]), 0.0)
            dx = float(x) - float(ox)
            dy = float(y) - float(oy)
            if ((dx * dx) + (dy * dy)) ** 0.5 <= (control_radius + model_radius):
                in_range.append(str(objective["objective_id"]))
    return sorted(set(in_range))


def unit_entries(game: object, *, viewer_id: str | None, include_hidden: bool) -> list[dict[str, Any]]:
    objectives = objective_entries(game)
    players = sorted_players(game)
    objective_centroids = [tuple(objective["position"]) for objective in objectives]
    player_units: dict[str, list[object]] = {}
    all_units: list[object] = []
    for player in players:
        army = getattr(player, "army", None)
        units_for_player = list(getattr(army, "units", []) or [])
        player_key = str(getattr(player, "id", "") or "")
        player_units[player_key] = units_for_player
        all_units.extend(units_for_player)

    centroid_cache: dict[str, tuple[float, float, float]] = {}
    outer_radius_cache: dict[str, float] = {}
    alive_models_cache: dict[str, list[object]] = {}
    for unit in all_units:
        unit_id = str(get_entity_id(unit))
        unit_models = alive_models(unit)
        alive_models_cache[unit_id] = list(unit_models)
        centroid = unit_centroid(unit, alive_models_override=unit_models)
        centroid_cache[unit_id] = centroid
        outer_radius_cache[unit_id] = unit_outer_radius(
            unit,
            centroid=centroid,
            alive_models_override=unit_models,
        )

    enemy_units_by_player: dict[str, list[object]] = {}
    for player in players:
        player_key = str(getattr(player, "id", "") or "")
        enemy_units: list[object] = []
        for other_player in players:
            if other_player is player:
                continue
            other_key = str(getattr(other_player, "id", "") or "")
            enemy_units.extend(player_units.get(other_key, []))
        enemy_units_by_player[player_key] = enemy_units

    units: list[tuple[str, dict[str, Any]]] = []
    for player in players:
        player_key = str(getattr(player, "id", "") or "")
        for unit in player_units.get(player_key, []):
            unit_id = str(get_entity_id(unit))
            models = list(getattr(unit, "models", []) or [])
            unit_models = list(alive_models_cache.get(unit_id, alive_models(unit)))
            enemies = enemy_units_by_player.get(player_key, [])
            centroid = tuple(centroid_cache.get(unit_id, unit_centroid(unit)))
            enemy_centroids = [
                tuple(centroid_cache.get(str(get_entity_id(enemy)), unit_centroid(enemy)))
                for enemy in enemies
                if enemy is not None
            ]
            move = max_movement(unit)
            nearest_enemy = min((distance_2d(centroid, enemy) for enemy in enemy_centroids), default=9999.0)
            nearest_objective = min((distance_2d(centroid, objective) for objective in objective_centroids), default=9999.0)
            in_range_objectives = objective_ids_in_range(unit, objectives)
            threat_flags = {
                "can_reach_enemy_engagement_this_turn": bool(nearest_enemy <= (move + 12.0 + float(ENGAGEMENT_RANGE_HORIZONTAL))),
                "can_reach_score_source_this_turn": bool(nearest_objective <= move),
            }
            entry: dict[str, Any] = {
                "unit_id": unit_id,
                "owner_player_id": str(getattr(player, "id", "") or ""),
                "name": str(getattr(unit, "name", "") or ""),
                "model_count": int(len(models)),
                "alive_model_count": int(len(unit_models)),
                "position": [float(centroid[0]), float(centroid[1]), float(centroid[2])],
                "in_engagement_range": bool(
                    is_unit_in_engagement_range(
                        unit,
                        enemies,
                        centroid_cache=centroid_cache,
                        outer_radius_cache=outer_radius_cache,
                        alive_models_cache=alive_models_cache,
                    )
                ),
                "control_region_ids_in_range": [f"region:objective:{oid}" for oid in in_range_objectives],
                "score_source_ids_in_range": [f"score_source:objective:{oid}" for oid in in_range_objectives],
                "threat_flags": threat_flags,
            }
            if include_hidden or str(getattr(player, "id", "") or "") == str(viewer_id or ""):
                entry["reserve_status"] = str(getattr(unit, "reserve_status", "") or "")
                entry["reserve_source"] = str(_reserve_metadata_value(unit, "reserve_source", "") or "")
                entry["reserve_mandatory_start"] = bool(
                    _reserve_metadata_value(unit, "reserve_mandatory_start", False)
                )
                entry["reserve_latest_arrival_round"] = int(
                    _reserve_metadata_value(unit, "reserve_latest_arrival_round", 0) or 0
                )
                entry["reserve_last_arrival_failure"] = reserve_last_arrival_failure(unit)
            units.append((unit_id, entry))
    units.sort(key=lambda item: item[0])
    return [entry for _unit_id, entry in units]


__all__ = ["unit_entries"]
