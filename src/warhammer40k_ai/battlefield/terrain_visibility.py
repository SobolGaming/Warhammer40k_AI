from __future__ import annotations

import copy
from collections import OrderedDict
from math import hypot
from typing import Any

from shapely.errors import GEOSException
from shapely.geometry import LineString

from .terrain_runtime import iter_terrain_areas
from ..utility.entity_ids import get_entity_id
from ..utility.profiling_sections import profiled_section


_VISIBILITY_CONTEXT_CACHE_MAX = 8192


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


def build_reason_trace_entry(code: str, detail: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "code": str(code or ""),
        "detail": str(detail or ""),
        "metadata": _json_safe(dict(metadata or {})),
    }


def _append_reason(
    trace: list[dict[str, Any]],
    code: str,
    detail: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    trace.append(build_reason_trace_entry(code, detail, metadata=metadata))


def sample_model_points_3d(model: object, perimeter_points: int = 8, z_levels: int = 3) -> list[tuple[float, float, float]]:
    """Sample points on a model's 3D volume for visibility tests."""
    model_base = getattr(model, "model_base", None)
    if model_base is None:
        return []
    base_shape = model_base.get_base_shape()
    exterior = getattr(base_shape, "exterior", None)
    if exterior is None:
        return []

    perimeter_samples: list[tuple[float, float]] = []
    if exterior.length > 0 and perimeter_points > 0:
        step = exterior.length / perimeter_points
        for i in range(perimeter_points):
            point = exterior.interpolate(step * i)
            perimeter_samples.append((float(point.x), float(point.y)))

    centroid = base_shape.centroid
    xy_points = [(float(centroid.x), float(centroid.y)), *perimeter_samples]

    z_bottom, z_top = model_base.volume_z_bounds()
    if z_levels <= 1:
        z_samples = [float(z_bottom) + 0.01]
    elif z_levels == 2:
        z_samples = [float(z_bottom) + 0.01, float(z_top) - 0.01]
    else:
        z_mid = (float(z_bottom) + float(z_top)) / 2.0
        z_samples = [float(z_bottom) + 0.01, z_mid, float(z_top) - 0.01]

    points_3d: list[tuple[float, float, float]] = []
    for x_pos, y_pos in xy_points:
        for z_pos in z_samples:
            points_3d.append((x_pos, y_pos, float(z_pos)))
    return points_3d


def _line_intersection_point(line2d: LineString, geometry: object):
    intersection = line2d.intersection(geometry)
    if intersection.is_empty:
        return None
    if intersection.geom_type == "Point":
        return intersection
    if intersection.geom_type in ("LineString", "MultiPoint", "MultiLineString"):
        return intersection.centroid
    return intersection.representative_point()


def _bounds_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (
        float(a[2]) < float(b[0])
        or float(a[0]) > float(b[2])
        or float(a[3]) < float(b[1])
        or float(a[1]) > float(b[3])
    )


def _segment_bounds_2d(p0: tuple[float, float, float], p1: tuple[float, float, float]) -> tuple[float, float, float, float]:
    x0 = float(p0[0])
    y0 = float(p0[1])
    x1 = float(p1[0])
    y1 = float(p1[1])
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _rounded_bounds(value: object) -> tuple[float, float, float, float]:
    bounds = tuple(getattr(value, "bounds", ()) or ())
    if len(bounds) != 4:
        return (0.0, 0.0, 0.0, 0.0)
    return tuple(round(float(item), 4) for item in bounds)  # type: ignore[return-value]


def _cache_entity_key(entity: object | None) -> str:
    if entity is None:
        return ""
    try:
        return str(get_entity_id(entity) or id(entity))
    except ValueError:
        return str(id(entity))


def _model_visibility_key(model: object) -> tuple[Any, ...]:
    base = getattr(model, "model_base", None)
    alive_value = getattr(model, "is_alive", True)
    alive = bool(alive_value() if callable(alive_value) else alive_value)
    if base is None:
        return (_cache_entity_key(model), alive, None)
    radius = getattr(base, "radius", None)
    if isinstance(radius, (list, tuple)):
        radius_key: Any = tuple(round(float(value), 4) for value in radius)
    else:
        try:
            radius_key = round(float(radius), 4)
        except (TypeError, ValueError):
            radius_key = None
    base_type = str(getattr(getattr(base, "base_type", None), "name", "") or "")
    return (
        _cache_entity_key(model),
        alive,
        round(float(getattr(base, "x", 0.0) or 0.0), 4),
        round(float(getattr(base, "y", 0.0) or 0.0), 4),
        round(float(getattr(base, "z", 0.0) or 0.0), 4),
        round(float(getattr(base, "facing", 0.0) or 0.0), 4),
        base_type,
        radius_key,
    )


def _unit_visibility_key(unit: object | None) -> tuple[Any, ...]:
    if unit is None:
        return ("",)
    return (
        _cache_entity_key(unit),
        bool(getattr(unit, "is_aircraft", False)),
        bool(getattr(unit, "is_towering", False)),
        bool(getattr(unit, "terrain_hidden_active", False)),
        getattr(unit, "terrain_hidden_detection_range", None),
        str(getattr(unit, "terrain_hidden_current_player_turn", "") or ""),
        str(getattr(unit, "terrain_hidden_previous_player_turn", "") or ""),
        str(getattr(unit, "terrain_hidden_last_shot_player_turn", "") or ""),
    )


def _terrain_visibility_signature(game_map: object) -> tuple[Any, ...]:
    rows: list[tuple[Any, ...]] = []
    for terrain in list(getattr(game_map, "terrain_features", []) or []):
        footprint = getattr(terrain, "footprint", None)
        wall_rows: list[tuple[Any, ...]] = []
        for wall in list(getattr(terrain, "walls", []) or []):
            if not isinstance(wall, dict):
                continue
            wall_rows.append(
                (
                    _rounded_bounds(wall.get("polygon")),
                    round(float(wall.get("z_bottom", 0.0) or 0.0), 4),
                    round(float(wall.get("z_top", wall.get("z_bottom", 0.0)) or 0.0), 4),
                )
            )
        opening_rows: list[tuple[Any, ...]] = []
        for opening in list(getattr(terrain, "openings", []) or []):
            if not isinstance(opening, dict):
                continue
            opening_rows.append(
                (
                    _rounded_bounds(opening.get("polygon")),
                    round(float(opening.get("z_bottom", 0.0) or 0.0), 4),
                    round(float(opening.get("z_top", 0.0) or 0.0), 4),
                    bool(opening.get("allows_los", False)),
                )
            )
        wall_rows.sort(key=lambda item: str(item))
        opening_rows.sort(key=lambda item: str(item))
        rows.append(
            (
                str(getattr(terrain, "id", "") or id(terrain)),
                str(getattr(getattr(terrain, "terrain_type", None), "name", "") or ""),
                _rounded_bounds(footprint),
                bool(getattr(terrain, "obscuring", False)),
                round(float(getattr(terrain, "height", 0.0) or 0.0), 4),
                round(float(getattr(terrain, "rim_height", 0.0) or 0.0), 4),
                tuple(wall_rows),
                tuple(opening_rows),
            )
        )
    rows.sort(key=lambda item: str(item[0]))
    area_rows: list[tuple[Any, ...]] = []
    for area in iter_terrain_areas(game_map):
        footprint = getattr(area, "footprint", None)
        area_rows.append(
            (
                str(getattr(area, "id", "") or id(area)),
                _rounded_bounds(footprint),
                bool(getattr(area, "obscuring", False)),
                getattr(area, "detection_range", None),
                tuple(sorted(str(tag or "") for tag in list(getattr(area, "effect_tags", []) or []))),
            )
        )
    area_rows.sort(key=lambda item: str(item[0]))
    return (tuple(rows), tuple(area_rows))


def _visibility_context_cache_key(game_map: object, shooter_model: object, target_model: object) -> tuple[Any, ...]:
    target_unit = getattr(target_model, "parent_unit", None)
    shooter_unit = getattr(shooter_model, "parent_unit", None)
    return (
        "visibility_context_v2",
        int(getattr(game_map, "state_generation", 0) or 0),
        bool(preview_visibility_semantics_enabled(game_map)),
        str(getattr(game_map, "preview_visibility_ruleset", "") or ""),
        str(getattr(game_map, "terrain_hidden_current_player_turn", "") or ""),
        str(getattr(game_map, "terrain_hidden_previous_player_turn", "") or ""),
        _model_visibility_key(shooter_model),
        _model_visibility_key(target_model),
        _unit_visibility_key(shooter_unit),
        _unit_visibility_key(target_unit),
        _terrain_visibility_signature(game_map),
    )


def _visibility_context_cache(game_map: object) -> OrderedDict:
    cache = getattr(game_map, "_visibility_context_cache", None)
    if isinstance(cache, OrderedDict):
        return cache
    cache = OrderedDict()
    try:
        setattr(game_map, "_visibility_context_cache", cache)
    except (AttributeError, TypeError):
        pass
    return cache


def _visibility_context_cache_get(game_map: object, key: tuple[Any, ...]) -> dict[str, Any] | None:
    cache = _visibility_context_cache(game_map)
    cached = cache.get(key)
    if cached is None:
        return None
    cache.move_to_end(key)
    return copy.deepcopy(cached)


def _visibility_context_cache_set(game_map: object, key: tuple[Any, ...], result: dict[str, Any]) -> None:
    cache = _visibility_context_cache(game_map)
    cache[key] = copy.deepcopy(result)
    cache.move_to_end(key)
    while len(cache) > _VISIBILITY_CONTEXT_CACHE_MAX:
        cache.popitem(last=False)


@profiled_section("los.segment_blocked_by_terrain")
def segment_blocked_by_terrain_feature(
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    terrain: object,
    shooter_model: object,
    target_model: object,
) -> bool:
    """Return True if the segment is blocked by this terrain feature."""
    footprint = getattr(terrain, "footprint", None)
    if footprint is None:
        return False
    line_bounds = _segment_bounds_2d(p0, p1)
    footprint_bounds = tuple(getattr(footprint, "bounds", ()) or ())
    if len(footprint_bounds) == 4 and not _bounds_overlap(line_bounds, footprint_bounds):
        return False

    line2d = LineString([(p0[0], p0[1]), (p1[0], p1[1])])
    if line2d.length == 0:
        return False

    def z_at_fraction(fraction: float) -> float:
        return float(p0[2]) + fraction * (float(p1[2]) - float(p0[2]))

    is_ruins = hasattr(terrain, "walls") and hasattr(terrain, "openings")
    if is_ruins:
        shooter_shape = getattr(getattr(shooter_model, "model_base", None), "get_base_shape", lambda: None)()
        target_shape = getattr(getattr(target_model, "model_base", None), "get_base_shape", lambda: None)()
        if shooter_shape is not None and target_shape is not None:
            shooter_inside_any = bool(footprint.intersects(shooter_shape))
            target_inside_any = bool(footprint.intersects(target_shape))
            shooter_wholly_within = bool(footprint.covers(shooter_shape))
            shooter_unit = getattr(shooter_model, "parent_unit", None)
            target_unit = getattr(target_model, "parent_unit", None)
            shooter_is_aircraft = bool(getattr(shooter_unit, "is_aircraft", False))
            target_is_aircraft = bool(getattr(target_unit, "is_aircraft", False))
            shooter_is_towering = bool(getattr(shooter_unit, "is_towering", False))

            if not (shooter_is_aircraft or target_is_aircraft):
                if not shooter_inside_any and not target_inside_any and line2d.intersects(footprint):
                    return True
                if shooter_inside_any and not shooter_wholly_within and not shooter_is_towering:
                    if not target_inside_any:
                        return True

    walls = getattr(terrain, "walls", None)
    openings = getattr(terrain, "openings", None)
    if walls:
        for wall in walls:
            wall_polygon = wall.get("polygon")
            if wall_polygon is None or not line2d.intersects(wall_polygon):
                continue
            intersection_point = _line_intersection_point(line2d, wall_polygon)
            if intersection_point is None:
                continue
            fraction = line2d.project(intersection_point) / line2d.length if line2d.length > 0 else 0.0
            if fraction <= 1e-6 or fraction >= 1.0 - 1e-6:
                continue
            z_here = z_at_fraction(fraction)
            z_bottom = float(wall.get("z_bottom", 0.0) or 0.0)
            z_top = float(wall.get("z_top", z_bottom) or z_bottom)
            if z_here < z_bottom or z_here > z_top:
                continue

            allowed = False
            if openings:
                for opening in openings:
                    if not bool(opening.get("allows_los", False)):
                        continue
                    opening_polygon = opening.get("polygon")
                    if opening_polygon is None or not opening_polygon.contains(intersection_point):
                        continue
                    opening_bottom = float(opening.get("z_bottom", -1e9) or -1e9)
                    opening_top = float(opening.get("z_top", 1e9) or 1e9)
                    if opening_bottom <= z_here <= opening_top:
                        allowed = True
                        break
            if not allowed:
                return True
        return False

    if not line2d.intersects(footprint):
        return False
    intersection_point = _line_intersection_point(line2d, footprint)
    if intersection_point is None:
        return False
    fraction = line2d.project(intersection_point) / line2d.length if line2d.length > 0 else 0.0
    if fraction <= 1e-6 or fraction >= 1.0 - 1e-6:
        return False
    z_here = z_at_fraction(fraction)

    min_z = 0.0
    max_z = 0.0
    if hasattr(terrain, "height"):
        max_z = float(getattr(terrain, "height", 0.0) or 0.0)
    elif hasattr(terrain, "rim_height"):
        max_z = float(getattr(terrain, "rim_height", 0.0) or 0.0)
    elif isinstance(getattr(terrain, "bounding_box", None), dict):
        bounding_box = getattr(terrain, "bounding_box", {}) or {}
        try:
            min_z = float((bounding_box.get("min", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))[2])
            max_z = float((bounding_box.get("max", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))[2])
        except (TypeError, ValueError, IndexError):
            min_z = 0.0
            max_z = 2.0
    else:
        max_z = 2.0

    return min_z <= z_here <= max_z


def is_fully_visible_due_to_terrain(
    shooter_model: object,
    target_model: object,
    terrain: object,
) -> bool:
    """True iff every sampled point on target is visible to shooter w.r.t. this terrain."""
    shooter_points = sample_model_points_3d(shooter_model, perimeter_points=8, z_levels=3)
    target_points = sample_model_points_3d(target_model, perimeter_points=8, z_levels=3)
    if not shooter_points or not target_points:
        return False

    for target_point in target_points:
        any_visible = False
        for shooter_point in shooter_points:
            if not segment_blocked_by_terrain_feature(shooter_point, target_point, terrain, shooter_model, target_model):
                any_visible = True
                break
        if not any_visible:
            return False
    return True


def _distance_between_models_2d(source_model: object, target_model: object) -> float:
    source_base = getattr(source_model, "model_base", None)
    target_base = getattr(target_model, "model_base", None)
    source_x = float(getattr(source_base, "x", 0.0) or 0.0)
    source_y = float(getattr(source_base, "y", 0.0) or 0.0)
    target_x = float(getattr(target_base, "x", 0.0) or 0.0)
    target_y = float(getattr(target_base, "y", 0.0) or 0.0)
    return float(hypot(target_x - source_x, target_y - source_y))


def _model_base_shape(model: object):
    model_base = getattr(model, "model_base", None)
    if model_base is None:
        return None
    return model_base.get_base_shape()


def _entity_has_keyword(entity: object | None, keyword: str) -> bool:
    if entity is None:
        return False
    has_any_keyword = getattr(entity, "has_any_keyword", None)
    if callable(has_any_keyword):
        try:
            return bool(has_any_keyword(keyword))
        except (TypeError, ValueError):
            return False
    return False


def _hidden_eligible(target_model: object) -> bool:
    target_unit = getattr(target_model, "parent_unit", None)
    explicit_values = [
        getattr(target_model, "terrain_hidden_eligible", None),
        getattr(target_unit, "terrain_hidden_eligible", None),
    ]
    for explicit in explicit_values:
        if explicit is not None:
            return bool(explicit)
    for keyword in ("INFANTRY", "BEAST", "SWARM"):
        if _entity_has_keyword(target_unit, keyword) or _entity_has_keyword(target_model, keyword):
            return True
    return False


def _hidden_turn_marker(target_model: object, name: str) -> str:
    target_unit = getattr(target_model, "parent_unit", None)
    for source in (target_model, target_unit):
        value = getattr(source, name, None)
        if value is None:
            continue
        marker = str(value or "").strip()
        if marker:
            return marker
    return ""


def _hidden_active(game_map: object, target_model: object, target_areas: list[object]) -> tuple[bool, float | None]:
    target_unit = getattr(target_model, "parent_unit", None)
    detection_range: float | None = None
    for area in target_areas:
        area_detection = getattr(area, "detection_range", None)
        if area_detection is not None:
            detection_range = float(area_detection)
            break
    for source in (target_model, target_unit):
        if source is None:
            continue
        explicit_range = getattr(source, "terrain_hidden_detection_range", None)
        if explicit_range is not None:
            detection_range = float(explicit_range)
            break

    for source in (target_model, target_unit):
        if source is None:
            continue
        explicit_hidden = getattr(source, "terrain_hidden_active", None)
        if explicit_hidden is not None:
            return bool(explicit_hidden), detection_range

    if not _hidden_eligible(target_model):
        return False, detection_range

    hidden_capable = False
    for area in target_areas:
        effect_tags = {str(tag).strip().upper() for tag in list(getattr(area, "effect_tags", []) or []) if str(tag).strip()}
        metadata = dict(getattr(area, "metadata", {}) or {})
        if "HIDDEN_CAPABLE" in effect_tags or "HIDDEN" in effect_tags or bool(metadata.get("hidden_capable", False)):
            hidden_capable = True
            break
    if not hidden_capable:
        return False, detection_range

    current_turn = _hidden_turn_marker(target_model, "terrain_hidden_current_player_turn")
    previous_turn = _hidden_turn_marker(target_model, "terrain_hidden_previous_player_turn")
    last_shot_turn = _hidden_turn_marker(target_model, "terrain_hidden_last_shot_player_turn")
    if not current_turn and not previous_turn:
        current_turn = str(getattr(game_map, "terrain_hidden_current_player_turn", "") or "").strip()
        previous_turn = str(getattr(game_map, "terrain_hidden_previous_player_turn", "") or "").strip()
    if not current_turn and not previous_turn:
        return False, detection_range
    if last_shot_turn and last_shot_turn in {current_turn, previous_turn}:
        return False, detection_range
    return True, detection_range


def _target_areas_for_model(game_map: object, target_model: object) -> list[object]:
    base_shape = _model_base_shape(target_model)
    if base_shape is None:
        return []
    areas: list[object] = []
    for area in iter_terrain_areas(game_map):
        footprint = getattr(area, "footprint", None)
        if footprint is None:
            continue
        try:
            if footprint.intersects(base_shape):
                areas.append(area)
        except GEOSException:
            continue
    areas.sort(key=lambda area: str(getattr(area, "id", "") or ""))
    return areas


def preview_visibility_semantics_enabled(game_map: object) -> bool:
    return bool(getattr(game_map, "preview_visibility_semantics_enabled", False))


@profiled_section("los.visibility_context")
def get_visibility_context_for_models(
    game_map: object,
    shooter_model: object,
    target_model: object,
) -> dict[str, Any]:
    cache_key = _visibility_context_cache_key(game_map, shooter_model, target_model)
    cached = _visibility_context_cache_get(game_map, cache_key)
    if cached is not None:
        return cached

    reason_trace: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "visible": False,
        "preview_visibility_semantics_enabled": preview_visibility_semantics_enabled(game_map),
        "preview_visibility_ruleset": str(getattr(game_map, "preview_visibility_ruleset", "") or ""),
        "hidden_state_active": False,
        "hidden_blocked": False,
        "hidden_detection_range": None,
        "detection_range_override_applies": False,
        "obscuring_state": False,
        "reason_trace": reason_trace,
    }

    def _cache_and_return() -> dict[str, Any]:
        _visibility_context_cache_set(game_map, cache_key, result)
        return result

    shooter_shape = _model_base_shape(shooter_model)
    target_shape = _model_base_shape(target_model)
    if shooter_shape is None or target_shape is None:
        _append_reason(reason_trace, "INVALID_MODEL_GEOMETRY", "Shooter or target model lacks base geometry.")
        return _cache_and_return()

    target_areas = _target_areas_for_model(game_map, target_model)
    if result["preview_visibility_semantics_enabled"]:
        hidden_active, detection_range = _hidden_active(game_map, target_model, target_areas)
        result["hidden_state_active"] = bool(hidden_active)
        result["hidden_detection_range"] = detection_range
        if hidden_active:
            distance = _distance_between_models_2d(shooter_model, target_model)
            _append_reason(
                reason_trace,
                "TARGET_HIDDEN_ACTIVE",
                "Target is in a provisional Hidden state.",
                metadata={"distance": distance, "detection_range": detection_range},
            )
            if detection_range is None or distance > float(detection_range):
                result["hidden_blocked"] = True
                _append_reason(
                    reason_trace,
                    "HIDDEN_BLOCKED_BY_DETECTION_RANGE",
                    "Target remains hidden because the shooter is outside detection range.",
                    metadata={"distance": distance, "detection_range": detection_range},
                )
                return _cache_and_return()
            result["detection_range_override_applies"] = True
            _append_reason(
                reason_trace,
                "DETECTION_RANGE_OVERRIDE_APPLIES",
                "Target is visible because the shooter is within detection range.",
                metadata={"distance": distance, "detection_range": detection_range},
            )

    shooter_center = shooter_shape.centroid
    target_center = target_shape.centroid
    line2d = LineString([(float(shooter_center.x), float(shooter_center.y)), (float(target_center.x), float(target_center.y))])
    if result["preview_visibility_semantics_enabled"]:
        for area in iter_terrain_areas(game_map):
            if not bool(getattr(area, "obscuring", False)):
                continue
            footprint = getattr(area, "footprint", None)
            if footprint is None:
                continue
            try:
                if not line2d.intersects(footprint):
                    continue
                shooter_inside = bool(footprint.intersects(shooter_shape))
                target_inside = bool(footprint.intersects(target_shape))
            except GEOSException:
                continue
            if shooter_inside and target_inside:
                continue
            result["obscuring_state"] = True
            _append_reason(
                reason_trace,
                "OBSCURING_AREA_BLOCKS_VISIBILITY",
                "An obscuring terrain area blocks visibility between the models.",
                metadata={"terrain_area_id": str(getattr(area, "id", "") or "")},
            )
            return _cache_and_return()

    shooter_points = sample_model_points_3d(shooter_model, perimeter_points=6, z_levels=2)
    target_points = sample_model_points_3d(target_model, perimeter_points=6, z_levels=2)
    if not shooter_points or not target_points:
        _append_reason(reason_trace, "NO_SAMPLE_POINTS", "Visibility sampling could not resolve model points.")
        return _cache_and_return()

    terrain_features = list(getattr(game_map, "terrain_features", []) or [])
    first_blocking_terrain_id = ""
    for target_point in target_points:
        for shooter_point in shooter_points:
            blocked = False
            for terrain in terrain_features:
                try:
                    if segment_blocked_by_terrain_feature(shooter_point, target_point, terrain, shooter_model, target_model):
                        blocked = True
                        first_blocking_terrain_id = str(getattr(terrain, "id", "") or "")
                        break
                except (GEOSException, TypeError, ValueError):
                    blocked = True
                    first_blocking_terrain_id = str(getattr(terrain, "id", "") or "")
                    break
            if not blocked:
                result["visible"] = True
                _append_reason(reason_trace, "LEGACY_LOS_CLEAR", "A sampled line of sight path is clear.")
                return _cache_and_return()

    _append_reason(
        reason_trace,
        "LEGACY_LOS_BLOCKED",
        "All sampled line of sight paths are blocked by terrain.",
        metadata={"terrain_id": first_blocking_terrain_id},
    )
    return _cache_and_return()


def can_model_see_model(game_map: object, shooter_model: object, target_model: object) -> bool:
    return bool(get_visibility_context_for_models(game_map, shooter_model, target_model).get("visible", False))


__all__ = [
    "build_reason_trace_entry",
    "can_model_see_model",
    "get_visibility_context_for_models",
    "is_fully_visible_due_to_terrain",
    "preview_visibility_semantics_enabled",
    "sample_model_points_3d",
    "segment_blocked_by_terrain_feature",
]
