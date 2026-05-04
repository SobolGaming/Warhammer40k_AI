from __future__ import annotations

from contextlib import contextmanager

from shapely.errors import GEOSException
from shapely.geometry import Point, Polygon

from .terrain_runtime import resolve_terrain_feature_footprint


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def serialize_polygon_geometry(footprint: Polygon | None) -> dict | None:
    if footprint is None:
        return None
    return {
        "exterior": [[safe_float(x), safe_float(y)] for x, y in footprint.exterior.coords],
        "interiors": [
            [[safe_float(x), safe_float(y)] for x, y in ring.coords]
            for ring in footprint.interiors
        ],
    }


def deserialize_polygon_geometry(data: dict | None) -> Polygon | None:
    if not isinstance(data, dict):
        return None
    exterior = [tuple(vertex[:2]) for vertex in list(data.get("exterior", []) or []) if len(vertex) >= 2]
    if not exterior:
        return None
    interiors = [
        [tuple(vertex[:2]) for vertex in list(ring or []) if len(vertex) >= 2]
        for ring in list(data.get("interiors", []) or [])
    ]
    return Polygon(exterior, interiors)


def max_radius_for_polygon(footprint: Polygon | None) -> float:
    if footprint is None:
        return 0.0
    centroid = footprint.centroid
    cx = safe_float(centroid.x)
    cy = safe_float(centroid.y)
    max_radius = 0.0
    for x, y in footprint.exterior.coords:
        dx = safe_float(x) - cx
        dy = safe_float(y) - cy
        max_radius = max(max_radius, float((dx * dx + dy * dy) ** 0.5))
    return float(max_radius)


def control_region_shape(control_region: object, *, game_state: object | None = None):
    kind = str(getattr(control_region, "kind", "") or "").upper()
    footprint = getattr(control_region, "footprint", None)
    if kind == "OBJECTIVE_CONTROL_RADIUS":
        return Point(
            safe_float(getattr(control_region, "center_x", 0.0)),
            safe_float(getattr(control_region, "center_y", 0.0)),
        ).buffer(safe_float(getattr(control_region, "radius", 0.0)))
    if kind == "OBJECTIVE_CONTROL_FOOTPRINT":
        return footprint
    if kind == "OBJECTIVE_CONTROL_KEYED_FEATURE":
        if footprint is not None:
            return footprint
        return resolve_terrain_feature_footprint(game_state, getattr(control_region, "feature_key", None))
    return footprint


def control_region_centroid(control_region: object, *, game_state: object | None = None) -> tuple[float, float, float]:
    shape = control_region_shape(control_region, game_state=game_state)
    if shape is not None:
        try:
            centroid = shape.centroid
            return (safe_float(centroid.x), safe_float(centroid.y), safe_float(getattr(control_region, "center_z", 0.0)))
        except GEOSException:
            pass
    return (
        safe_float(getattr(control_region, "center_x", 0.0)),
        safe_float(getattr(control_region, "center_y", 0.0)),
        safe_float(getattr(control_region, "center_z", 0.0)),
    )


def model_overlaps_control_region(model: object, control_region: object, *, game_state: object | None = None) -> bool:
    model_base = getattr(model, "model_base", None)
    if model_base is None:
        return False
    kind = str(getattr(control_region, "kind", "") or "").upper()
    if kind == "OBJECTIVE_CONTROL_RADIUS" and bool(getattr(model_base, "has_circular_base", False)):
        radius = safe_float(getattr(control_region, "radius", 0.0))
        model_radius = safe_float(getattr(model_base, "get_radius", lambda: 0.0)(), 0.0)
        dx = safe_float(getattr(model_base, "x", 0.0)) - safe_float(getattr(control_region, "center_x", 0.0))
        dy = safe_float(getattr(model_base, "y", 0.0)) - safe_float(getattr(control_region, "center_y", 0.0))
        return bool(((dx * dx) + (dy * dy)) ** 0.5 <= (radius + model_radius))
    shape = control_region_shape(control_region, game_state=game_state)
    if shape is None:
        return False
    try:
        model_shape = model_base.get_base_shape()
        return bool(model_shape.intersects(shape))
    except (AttributeError, GEOSException, TypeError, ValueError):
        return False


def compute_player_objective_control(game_state: object, control_region: object) -> dict[object, int]:
    players = list(getattr(game_state, "players", []) or [])
    player_oc = {player: 0 for player in players}
    shared_model_oc_cache = getattr(game_state, "_objective_control_model_oc_cache", None)
    if not isinstance(shared_model_oc_cache, dict):
        shared_model_oc_cache = None
    had_prev_nurgles_cache = hasattr(game_state, "_objective_control_nurgles_gift_cache")
    prev_nurgles_cache = getattr(game_state, "_objective_control_nurgles_gift_cache", None) if had_prev_nurgles_cache else None
    if not isinstance(prev_nurgles_cache, dict):
        setattr(game_state, "_objective_control_nurgles_gift_cache", {})

    try:
        for player in players:
            army = getattr(player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                if bool(getattr(unit, "is_leader", False)) and getattr(unit, "attached_to", None) is not None:
                    continue
                if not bool(getattr(unit, "deployed", False)):
                    continue
                is_alive = getattr(unit, "is_alive", None)
                if callable(is_alive) and not bool(is_alive()):
                    continue
                get_models = getattr(unit, "get_models_for_collision", None)
                if callable(get_models):
                    models = list(get_models() or [])
                else:
                    models = list(getattr(unit, "models", []) or [])
                for model in models:
                    if not bool(getattr(model, "is_alive", False)):
                        continue
                    if not model_overlaps_control_region(model, control_region, game_state=game_state):
                        continue
                    if shared_model_oc_cache is None:
                        oc_value = int(getattr(model, "objective_control", 0) or 0)
                    else:
                        cache_key = int(id(model))
                        if cache_key not in shared_model_oc_cache:
                            shared_model_oc_cache[cache_key] = int(getattr(model, "objective_control", 0) or 0)
                        oc_value = int(shared_model_oc_cache[cache_key] or 0)
                    player_oc[player] += int(oc_value)
    finally:
        if not isinstance(prev_nurgles_cache, dict):
            if had_prev_nurgles_cache:
                setattr(game_state, "_objective_control_nurgles_gift_cache", prev_nurgles_cache)
            else:
                try:
                    delattr(game_state, "_objective_control_nurgles_gift_cache")
                except AttributeError:
                    pass
    return player_oc


@contextmanager
def objective_control_cache_scope(game_state: object):
    game_map = getattr(game_state, "map", None)
    had_prev_model_cache = hasattr(game_state, "_objective_control_model_oc_cache")
    prev_model_cache = getattr(game_state, "_objective_control_model_oc_cache", None) if had_prev_model_cache else None
    had_prev_nurgles_cache = hasattr(game_state, "_objective_control_nurgles_gift_cache")
    prev_nurgles_cache = (
        getattr(game_state, "_objective_control_nurgles_gift_cache", None) if had_prev_nurgles_cache else None
    )
    had_prev_enemy_engagement_oc_cache = (
        hasattr(game_map, "_objective_control_enemy_engagement_oc_divisors_cache") if game_map is not None else False
    )
    prev_enemy_engagement_oc_cache = (
        getattr(game_map, "_objective_control_enemy_engagement_oc_divisors_cache", None)
        if had_prev_enemy_engagement_oc_cache and game_map is not None
        else None
    )
    setattr(game_state, "_objective_control_model_oc_cache", {})
    setattr(game_state, "_objective_control_nurgles_gift_cache", {})
    if game_map is not None:
        setattr(game_map, "_objective_control_enemy_engagement_oc_divisors_cache", {})
    try:
        yield
    finally:
        if had_prev_model_cache:
            setattr(game_state, "_objective_control_model_oc_cache", prev_model_cache)
        else:
            try:
                delattr(game_state, "_objective_control_model_oc_cache")
            except AttributeError:
                pass
        if had_prev_nurgles_cache:
            setattr(game_state, "_objective_control_nurgles_gift_cache", prev_nurgles_cache)
        else:
            try:
                delattr(game_state, "_objective_control_nurgles_gift_cache")
            except AttributeError:
                pass
        if game_map is not None:
            if had_prev_enemy_engagement_oc_cache:
                setattr(
                    game_map,
                    "_objective_control_enemy_engagement_oc_divisors_cache",
                    prev_enemy_engagement_oc_cache,
                )
            else:
                try:
                    delattr(game_map, "_objective_control_enemy_engagement_oc_divisors_cache")
                except AttributeError:
                    pass


__all__ = [
    "compute_player_objective_control",
    "control_region_centroid",
    "control_region_shape",
    "deserialize_polygon_geometry",
    "max_radius_for_polygon",
    "model_overlaps_control_region",
    "objective_control_cache_scope",
    "safe_float",
    "serialize_polygon_geometry",
]
