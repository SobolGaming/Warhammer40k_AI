from __future__ import annotations

import copy
from collections import OrderedDict
from dataclasses import dataclass, field
from math import hypot
from typing import Any

import shapely
from shapely.errors import GEOSException
from shapely.geometry import LineString, box
from shapely.strtree import STRtree

from .terrain_runtime import iter_terrain_areas
from .detection_markers import (
    VisibilityModifierQuery,
    coerce_visibility_modifier_query,
    collect_visibility_modifiers,
    detection_marker_signature,
    visibility_query_signature,
)
from .hidden_state import (
    hidden_preserving_exemption_ids_for_unit,
    hidden_shooting_exemption_signature,
    hidden_shot_breaks_hidden,
)
from ..utility.entity_ids import get_entity_id
from ..utility.profiling_sections import profile_section, profiled_section, record_value


_VISIBILITY_CONTEXT_CACHE_MAX = 8192
_VISIBILITY_FRAME_CONTEXT_CACHE_MAX = 8
_VISIBILITY_FRAME_LOS_CACHE_MAX = 8192
_VISIBILITY_FRAME_SEGMENT_CACHE_MAX = 32768


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
    terrain_features = list(getattr(game_map, "terrain_features", []) or [])
    terrain_cache_key = []
    for terrain in terrain_features:
        terrain_cache_key.append(
            (
                id(terrain),
                id(getattr(terrain, "footprint", None)),
                len(list(getattr(terrain, "walls", []) or [])),
                len(list(getattr(terrain, "openings", []) or [])),
                bool(getattr(terrain, "obscuring", False)),
                round(float(getattr(terrain, "height", 0.0) or 0.0), 4),
                round(float(getattr(terrain, "rim_height", 0.0) or 0.0), 4),
            )
        )
    area_cache_key = []
    for area in iter_terrain_areas(game_map):
        area_cache_key.append(
            (
                id(area),
                id(getattr(area, "footprint", None)),
                bool(getattr(area, "obscuring", False)),
                getattr(area, "detection_range", None),
                tuple(sorted(str(tag or "") for tag in list(getattr(area, "effect_tags", []) or []))),
            )
        )
    cache_key = (tuple(terrain_cache_key), tuple(area_cache_key))
    cached = getattr(game_map, "_terrain_visibility_signature_cache", None)
    if isinstance(cached, tuple) and len(cached) == 2 and cached[0] == cache_key:
        return cached[1]

    rows: list[tuple[Any, ...]] = []
    for terrain in terrain_features:
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
    result = (tuple(rows), tuple(area_rows))
    try:
        setattr(game_map, "_terrain_visibility_signature_cache", (cache_key, result))
    except (AttributeError, TypeError):
        pass
    return result


def _visibility_context_cache_key(
    game_map: object,
    shooter_model: object,
    target_model: object,
    visibility_query: VisibilityModifierQuery | dict[str, Any] | None = None,
) -> tuple[Any, ...]:
    target_unit = getattr(target_model, "parent_unit", None)
    shooter_unit = getattr(shooter_model, "parent_unit", None)
    terrain_revision = _visibility_revision(game_map, "terrain_visibility_revision")
    model_revision = _visibility_revision(game_map, "model_blocker_revision")
    modifier_revision = _visibility_revision(game_map, "visibility_modifier_revision")
    return (
        "visibility_context_v4",
        int(getattr(game_map, "state_generation", 0) or 0),
        terrain_revision,
        model_revision,
        modifier_revision,
        bool(preview_visibility_semantics_enabled(game_map)),
        str(getattr(game_map, "preview_visibility_ruleset", "") or ""),
        str(getattr(game_map, "terrain_hidden_current_player_turn", "") or ""),
        str(getattr(game_map, "terrain_hidden_previous_player_turn", "") or ""),
        detection_marker_signature(game_map),
        hidden_shooting_exemption_signature(game_map),
        visibility_query_signature(visibility_query),
        _model_visibility_key(shooter_model),
        _model_visibility_key(target_model),
        _unit_visibility_key(shooter_unit),
        _unit_visibility_key(target_unit),
        _terrain_visibility_signature(game_map) if terrain_revision <= 0 else (),
        _model_blocker_signature(game_map) if model_revision <= 0 else (),
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
    *,
    visibility_flags: tuple[bool, bool, bool] | None = None,
    line2d: LineString | None = None,
    line_length: float | None = None,
    line_bounds: tuple[float, float, float, float] | None = None,
    footprint_bounds: tuple[float, float, float, float] | None = None,
) -> bool:
    return _segment_blocked_by_terrain_feature_uncached(
        p0,
        p1,
        terrain,
        shooter_model,
        target_model,
        visibility_flags=visibility_flags,
        line2d=line2d,
        line_length=line_length,
        line_bounds=line_bounds,
        footprint_bounds=footprint_bounds,
    )


def _segment_blocked_by_terrain_feature_uncached(
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    terrain: object,
    shooter_model: object,
    target_model: object,
    *,
    visibility_flags: tuple[bool, bool, bool] | None = None,
    line2d: LineString | None = None,
    line_length: float | None = None,
    line_bounds: tuple[float, float, float, float] | None = None,
    footprint_bounds: tuple[float, float, float, float] | None = None,
) -> bool:
    """Return True if the segment is blocked by this terrain feature."""
    footprint = getattr(terrain, "footprint", None)
    if footprint is None:
        return False
    if line_bounds is None:
        line_bounds = _segment_bounds_2d(p0, p1)
    if footprint_bounds is None:
        footprint_bounds = tuple(getattr(footprint, "bounds", ()) or ())
    if len(footprint_bounds) == 4 and not _bounds_overlap(line_bounds, footprint_bounds):
        return False

    if line2d is None:
        line2d = LineString([(p0[0], p0[1]), (p1[0], p1[1])])
        line_length = float(line2d.length)
        if line_length == 0:
            return False
    elif line_length is None:
        line_length = float(line2d.length)

    z0 = float(p0[2])
    z_delta = float(p1[2]) - z0

    is_ruins = hasattr(terrain, "walls") and hasattr(terrain, "openings")
    if is_ruins:
        shooter_shape = getattr(getattr(shooter_model, "model_base", None), "get_base_shape", lambda: None)()
        target_shape = getattr(getattr(target_model, "model_base", None), "get_base_shape", lambda: None)()
        if shooter_shape is not None and target_shape is not None:
            shooter_inside_any = bool(footprint.intersects(shooter_shape))
            target_inside_any = bool(footprint.intersects(target_shape))
            shooter_wholly_within = bool(footprint.covers(shooter_shape))
            if visibility_flags is None:
                shooter_unit = getattr(shooter_model, "parent_unit", None)
                target_unit = getattr(target_model, "parent_unit", None)
                shooter_is_aircraft = bool(getattr(shooter_unit, "is_aircraft", False))
                target_is_aircraft = bool(getattr(target_unit, "is_aircraft", False))
                shooter_is_towering = bool(getattr(shooter_unit, "is_towering", False))
            else:
                shooter_is_aircraft, target_is_aircraft, shooter_is_towering = visibility_flags

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
            fraction = line2d.project(intersection_point) / line_length if line_length > 0 else 0.0
            if fraction <= 1e-6 or fraction >= 1.0 - 1e-6:
                continue
            z_here = z0 + fraction * z_delta
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
    fraction = line2d.project(intersection_point) / line_length if line_length > 0 else 0.0
    if fraction <= 1e-6 or fraction >= 1.0 - 1e-6:
        return False
    z_here = z0 + fraction * z_delta

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
    if hidden_shot_breaks_hidden(
        game_map,
        target_unit,
        last_shot_turn=last_shot_turn,
        current_turn=current_turn,
        previous_turn=previous_turn,
    ):
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


def _model_alive(model: object) -> bool:
    alive = getattr(model, "is_alive", True)
    return bool(alive() if callable(alive) else alive)


def _unit_alive(unit: object | None) -> bool:
    if unit is None:
        return False
    alive = getattr(unit, "is_alive", True)
    return bool(alive() if callable(alive) else alive)


def _visibility_models_for_unit(unit: object | None) -> tuple[object, ...]:
    if unit is None:
        return ()
    getter = getattr(unit, "get_models_for_collision", None)
    if callable(getter):
        return tuple(getter() or ())
    return tuple(getattr(unit, "models", ()) or ())


def _terrain_z_bounds(terrain: object) -> tuple[float, float]:
    if hasattr(terrain, "height"):
        return 0.0, float(getattr(terrain, "height", 0.0) or 0.0)
    if hasattr(terrain, "rim_height"):
        return 0.0, float(getattr(terrain, "rim_height", 0.0) or 0.0)
    bounding_box = getattr(terrain, "bounding_box", None)
    if isinstance(bounding_box, dict):
        min_value = bounding_box.get("min", (0.0, 0.0, 0.0))
        max_value = bounding_box.get("max", (0.0, 0.0, 0.0))
        if (
            isinstance(min_value, (tuple, list))
            and isinstance(max_value, (tuple, list))
            and len(min_value) >= 3
            and len(max_value) >= 3
        ):
            return float(min_value[2]), float(max_value[2])
    return 0.0, 2.0


def _geometry_bounds(geometry: object | None) -> tuple[float, float, float, float] | None:
    if geometry is None:
        return None
    try:
        raw_bounds = tuple(getattr(geometry, "bounds", ()) or ())
    except (GEOSException, TypeError, ValueError):
        return None
    if len(raw_bounds) != 4:
        return None
    return (
        float(raw_bounds[0]),
        float(raw_bounds[1]),
        float(raw_bounds[2]),
        float(raw_bounds[3]),
    )


def _prepare_geometry(geometry: object | None) -> object | None:
    if geometry is None:
        return None
    try:
        shapely.prepare(geometry)
    except (AttributeError, GEOSException, TypeError, ValueError):
        pass
    return geometry


def _visibility_revision(game_map: object, attr_name: str) -> int:
    fallback = int(getattr(game_map, "state_generation", 0) or 0)
    return int(getattr(game_map, attr_name, fallback) or 0)


def _model_blocker_signature(game_map: object) -> tuple[Any, ...]:
    rows: list[tuple[Any, ...]] = []
    for unit in list(getattr(game_map, "units", []) or []):
        unit_id = _cache_entity_key(unit)
        if not _unit_alive(unit) or not bool(getattr(unit, "deployed", True)):
            rows.append((unit_id, False))
            continue
        model_rows = tuple(
            _model_visibility_key(model)
            for model in _visibility_models_for_unit(unit)
            if _model_alive(model)
        )
        rows.append((unit_id, True, model_rows))
    rows.sort(key=lambda item: str(item[0]))
    return tuple(rows)


def _frame_context_cache_key(game_map: object) -> tuple[Any, ...]:
    terrain_revision = _visibility_revision(game_map, "terrain_visibility_revision")
    model_revision = _visibility_revision(game_map, "model_blocker_revision")
    modifier_revision = _visibility_revision(game_map, "visibility_modifier_revision")
    model_signature: tuple[Any, ...] = ()
    if model_revision <= 0:
        model_signature = _model_blocker_signature(game_map)
    terrain_signature: tuple[Any, ...] = ()
    if terrain_revision <= 0:
        terrain_signature = _terrain_visibility_signature(game_map)
    return (
        "visibility_frame_context_v1",
        terrain_revision,
        model_revision,
        modifier_revision,
        bool(preview_visibility_semantics_enabled(game_map)),
        str(getattr(game_map, "preview_visibility_ruleset", "") or ""),
        str(getattr(game_map, "terrain_hidden_current_player_turn", "") or ""),
        str(getattr(game_map, "terrain_hidden_previous_player_turn", "") or ""),
        detection_marker_signature(game_map),
        hidden_shooting_exemption_signature(game_map),
        terrain_signature,
        model_signature,
    )


def _visibility_frame_context_cache(game_map: object) -> OrderedDict:
    cache = getattr(game_map, "_visibility_frame_context_cache", None)
    if isinstance(cache, OrderedDict):
        return cache
    cache = OrderedDict()
    try:
        setattr(game_map, "_visibility_frame_context_cache", cache)
    except (AttributeError, TypeError):
        pass
    return cache


def _query_tree(
    tree: STRtree | None,
    records: tuple[object, ...],
    geometry: object,
) -> list[object]:
    if tree is None:
        return []
    indexes = tree.query(geometry)
    return [records[int(index)] for index in indexes]


def _quantized_point(point: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        round(float(point[0]), 4),
        round(float(point[1]), 4),
        round(float(point[2]), 4),
    )


@dataclass(frozen=True, slots=True)
class TerrainVisibilityRecord:
    stable_id: str
    terrain: object
    footprint: object | None
    bounds: tuple[float, float, float, float] | None
    z_bounds: tuple[float, float]
    is_ruins: bool
    has_walls: bool


@dataclass(frozen=True, slots=True)
class WallVisibilityRecord:
    stable_id: str
    terrain_id: str
    polygon: object
    bounds: tuple[float, float, float, float]
    z_bottom: float
    z_top: float


@dataclass(frozen=True, slots=True)
class OpeningVisibilityRecord:
    stable_id: str
    terrain_id: str
    polygon: object
    bounds: tuple[float, float, float, float]
    z_bottom: float
    z_top: float


@dataclass(frozen=True, slots=True)
class ModelVisibilityGeometry:
    stable_id: str
    model: object
    shape: object
    bounds: tuple[float, float, float, float]
    z_bounds: tuple[float, float]
    center_xy: tuple[float, float]


@dataclass(frozen=True, slots=True)
class ModelBlockerRecord:
    stable_id: str
    unit_id: str
    model_id: str
    model: object
    shape: object
    bounds: tuple[float, float, float, float]
    z_bounds: tuple[float, float]


@dataclass(slots=True)
class VisibilityFrameContext:
    game_map: object
    terrain_visibility_revision: int
    model_blocker_revision: int
    visibility_modifier_revision: int
    terrain_records: tuple[TerrainVisibilityRecord, ...]
    wall_records: tuple[WallVisibilityRecord, ...]
    opening_records: tuple[OpeningVisibilityRecord, ...]
    model_blocker_records: tuple[ModelBlockerRecord, ...]
    terrain_tree: STRtree | None
    wall_tree: STRtree | None
    opening_tree: STRtree | None
    model_blocker_tree: STRtree | None
    model_geometry_by_id: dict[str, ModelVisibilityGeometry] = field(default_factory=dict)
    staged_points_by_key: dict[tuple[Any, ...], tuple[tuple[float, float, float], ...]] = field(default_factory=dict)
    los_cache: OrderedDict = field(default_factory=OrderedDict)
    segment_cache: OrderedDict = field(default_factory=OrderedDict)
    openings_by_terrain_id: dict[str, tuple[OpeningVisibilityRecord, ...]] = field(default_factory=dict)
    _count_metrics: dict[str, int] = field(default_factory=dict)

    def _record_count(self, name: str, amount: int = 1) -> None:
        metric_name = str(name or "unnamed")
        self._count_metrics[metric_name] = int(self._count_metrics.get(metric_name, 0) or 0) + int(amount)

    def _flush_count_metrics(self) -> None:
        if not self._count_metrics:
            return
        for name, total in tuple(self._count_metrics.items()):
            if total:
                record_value(name, total)
        self._count_metrics.clear()

    def _model_geometry(self, model: object) -> ModelVisibilityGeometry | None:
        model_id = _cache_entity_key(model)
        cached = self.model_geometry_by_id.get(model_id)
        if cached is not None:
            return cached
        base = getattr(model, "model_base", None)
        if base is None:
            return None
        shape = _prepare_geometry(base.get_base_shape())
        if shape is None:
            return None
        bounds = _geometry_bounds(shape)
        if bounds is None:
            return None
        volume_bounds = getattr(base, "volume_z_bounds", None)
        if callable(volume_bounds):
            z_bounds = tuple(float(value) for value in volume_bounds())
        else:
            z = float(getattr(base, "z", 0.0) or 0.0)
            z_bounds = (z, z)
        center = shape.centroid
        geometry = ModelVisibilityGeometry(
            stable_id=model_id,
            model=model,
            shape=shape,
            bounds=bounds,
            z_bounds=(float(z_bounds[0]), float(z_bounds[1])),
            center_xy=(float(center.x), float(center.y)),
        )
        self.model_geometry_by_id[model_id] = geometry
        return geometry

    def _sample_points(self, model: object, *, perimeter_points: int, z_levels: int) -> tuple[tuple[float, float, float], ...]:
        key = ("samples", _model_visibility_key(model), int(perimeter_points), int(z_levels))
        cached = self.staged_points_by_key.get(key)
        if cached is not None:
            return cached
        samples = tuple(sample_model_points_3d(model, perimeter_points=perimeter_points, z_levels=z_levels))
        self.staged_points_by_key[key] = samples
        return samples

    def _center_point(self, geometry: ModelVisibilityGeometry, z_mode: str = "mid") -> tuple[float, float, float]:
        z_bottom, z_top = geometry.z_bounds
        if z_mode == "bottom":
            z_value = z_bottom + 0.01
        elif z_mode == "top":
            z_value = z_top - 0.01
        else:
            z_value = (z_bottom + z_top) / 2.0
        return (geometry.center_xy[0], geometry.center_xy[1], float(z_value))

    def _edge_points_toward(
        self,
        model: object,
        toward_xy: tuple[float, float],
        *,
        limit: int = 4,
    ) -> tuple[tuple[float, float, float], ...]:
        samples = self._sample_points(model, perimeter_points=8, z_levels=3)
        if not samples:
            return ()
        center_samples = samples[:3]
        edge_samples = samples[3:]
        ranked = sorted(
            edge_samples,
            key=lambda point: (
                (float(point[0]) - toward_xy[0]) ** 2 + (float(point[1]) - toward_xy[1]) ** 2,
                round(float(point[2]), 4),
                round(float(point[0]), 4),
                round(float(point[1]), 4),
            ),
        )
        return tuple([*center_samples[:1], *ranked[:limit]])

    def _staged_segment_pairs(
        self,
        shooter_model: object,
        target_model: object,
        shooter_geometry: ModelVisibilityGeometry,
        target_geometry: ModelVisibilityGeometry,
    ) -> tuple[tuple[str, tuple[float, float, float], tuple[float, float, float]], ...]:
        pairs: list[tuple[str, tuple[float, float, float], tuple[float, float, float]]] = []
        seen: set[tuple[tuple[float, float, float], tuple[float, float, float]]] = set()

        def add(stage: str, p0: tuple[float, float, float], p1: tuple[float, float, float]) -> None:
            key = (_quantized_point(p0), _quantized_point(p1))
            if key in seen:
                return
            seen.add(key)
            pairs.append((stage, p0, p1))

        add("center", self._center_point(shooter_geometry), self._center_point(target_geometry))
        for z_mode in ("bottom", "top"):
            add("vertical", self._center_point(shooter_geometry, z_mode), self._center_point(target_geometry))
            add("vertical", self._center_point(shooter_geometry), self._center_point(target_geometry, z_mode))

        shooter_edge_points = self._edge_points_toward(shooter_model, target_geometry.center_xy)
        target_edge_points = self._edge_points_toward(target_model, shooter_geometry.center_xy)
        for p0 in shooter_edge_points:
            for p1 in target_edge_points:
                add("edge", p0, p1)

        shooter_points = self._sample_points(shooter_model, perimeter_points=8, z_levels=3)
        target_points = self._sample_points(target_model, perimeter_points=8, z_levels=3)
        for p0 in shooter_points:
            for p1 in target_points:
                add("full", p0, p1)
        return tuple(pairs)

    def _enemy_unit_ids(self, shooter_unit: object | None) -> tuple[str, ...]:
        get_enemy_units = getattr(self.game_map, "get_enemy_units", None)
        if callable(get_enemy_units) and shooter_unit is not None:
            enemy_units = list(get_enemy_units(shooter_unit) or [])
        else:
            enemy_units = []
        return tuple(sorted(_cache_entity_key(unit) for unit in enemy_units if unit is not None))

    def _line_candidates(
        self,
        tree: STRtree | None,
        records: tuple[object, ...],
        line2d: LineString,
        p0: tuple[float, float, float],
        p1: tuple[float, float, float],
    ) -> list[object]:
        candidates = _query_tree(tree, records, line2d)
        if len(candidates) > 1:
            candidates.sort(key=lambda record: str(getattr(record, "stable_id", "")))
        record_value("los.strtree_candidates", len(candidates))
        return candidates

    def _pair_candidate_sets(
        self,
        shooter_geometry: ModelVisibilityGeometry,
        target_geometry: ModelVisibilityGeometry,
        *,
        include_model_blockers: bool,
    ) -> tuple[tuple[object, ...], tuple[object, ...], tuple[object, ...]]:
        sx0, sy0, sx1, sy1 = shooter_geometry.bounds
        tx0, ty0, tx1, ty1 = target_geometry.bounds
        query_geometry = box(min(sx0, tx0), min(sy0, ty0), max(sx1, tx1), max(sy1, ty1))

        terrain_candidates = _query_tree(self.terrain_tree, self.terrain_records, query_geometry)
        wall_candidates = _query_tree(self.wall_tree, self.wall_records, query_geometry)
        model_candidates = (
            _query_tree(self.model_blocker_tree, self.model_blocker_records, query_geometry)
            if include_model_blockers
            else []
        )
        if len(terrain_candidates) > 1:
            terrain_candidates.sort(key=lambda record: str(getattr(record, "stable_id", "")))
        if len(wall_candidates) > 1:
            wall_candidates.sort(key=lambda record: str(getattr(record, "stable_id", "")))
        if len(model_candidates) > 1:
            model_candidates.sort(key=lambda record: str(getattr(record, "stable_id", "")))
        record_value(
            "los.pair_strtree_candidates",
            len(terrain_candidates) + len(wall_candidates) + len(model_candidates),
        )
        return tuple(terrain_candidates), tuple(wall_candidates), tuple(model_candidates)

    def _segment_cache_get(self, key: tuple[Any, ...]) -> tuple[bool, str] | None:
        cached = self.segment_cache.get(key)
        if cached is None:
            self._record_count("los.segment_cache_miss")
            return None
        self.segment_cache.move_to_end(key)
        self._record_count("los.segment_cache_hit")
        return bool(cached[0]), str(cached[1])

    def _segment_cache_set(self, key: tuple[Any, ...], blocked: bool, blocker_id: str) -> None:
        self.segment_cache[key] = (bool(blocked), str(blocker_id or ""))
        self.segment_cache.move_to_end(key)
        while len(self.segment_cache) > _VISIBILITY_FRAME_SEGMENT_CACHE_MAX:
            self.segment_cache.popitem(last=False)

    def segment_is_blocked(
        self,
        p0: tuple[float, float, float],
        p1: tuple[float, float, float],
        *,
        shooter_unit_id: str,
        target_unit_ids: tuple[str, ...],
        enemy_unit_ids: tuple[str, ...],
        shooter_is_aircraft: bool,
        target_is_aircraft: bool,
        shooter_is_towering: bool,
        shooter_ruins_states: tuple[tuple[str, bool, bool], ...],
        target_ruins_states: tuple[tuple[str, bool], ...],
        ruleset_signature: tuple[Any, ...],
        terrain_candidates: tuple[object, ...] | None = None,
        wall_candidates: tuple[object, ...] | None = None,
        model_candidates: tuple[object, ...] | None = None,
    ) -> tuple[bool, str]:
        self._record_count("los.segment_tests")
        if abs(float(p0[0]) - float(p1[0])) <= 1e-9 and abs(float(p0[1]) - float(p1[1])) <= 1e-9:
            return False, ""
        segment_key: tuple[Any, ...] | None = None
        if bool(getattr(self.game_map, "enable_visibility_segment_cache", False)):
            segment_key = (
                "segment_block_v1",
                _quantized_point(p0),
                _quantized_point(p1),
                self.terrain_visibility_revision,
                self.model_blocker_revision,
                shooter_unit_id,
                target_unit_ids,
                enemy_unit_ids,
                bool(shooter_is_aircraft),
                bool(target_is_aircraft),
                bool(shooter_is_towering),
                shooter_ruins_states,
                target_ruins_states,
                ruleset_signature,
            )
            cached = self._segment_cache_get(segment_key)
            if cached is not None:
                return cached

        def result(blocked: bool, blocker_id: str) -> tuple[bool, str]:
            if segment_key is not None:
                self._segment_cache_set(segment_key, blocked, blocker_id)
            return bool(blocked), str(blocker_id or "")

        target_ruins_by_id = {terrain_id: inside for terrain_id, inside in target_ruins_states}
        shooter_ruins_by_id = {
            terrain_id: (inside, wholly)
            for terrain_id, inside, wholly in shooter_ruins_states
        }
        if not (shooter_is_aircraft or target_is_aircraft or shooter_is_towering):
            for terrain_id, (shooter_inside, shooter_wholly) in shooter_ruins_by_id.items():
                if shooter_inside and not shooter_wholly and not bool(target_ruins_by_id.get(terrain_id, False)):
                    self._record_count("los.first_blocker_exits")
                    return result(True, str(terrain_id))

        line2d = LineString([(float(p0[0]), float(p0[1])), (float(p1[0]), float(p1[1]))])
        line_length = float(line2d.length)
        if line_length == 0:
            return False, ""
        line_bounds = _segment_bounds_2d(p0, p1)
        z0 = float(p0[2])
        z_delta = float(p1[2]) - z0

        def z_at_t(t: float) -> float:
            return z0 + t * z_delta

        if terrain_candidates is None:
            terrain_candidates = tuple(self._line_candidates(self.terrain_tree, self.terrain_records, line2d, p0, p1))
        if wall_candidates is None:
            wall_candidates = tuple(self._line_candidates(self.wall_tree, self.wall_records, line2d, p0, p1))
        if model_candidates is None:
            model_candidates = (
                tuple(self._line_candidates(self.model_blocker_tree, self.model_blocker_records, line2d, p0, p1))
                if enemy_unit_ids
                else ()
            )

        for terrain in terrain_candidates:
            if not isinstance(terrain, TerrainVisibilityRecord) or terrain.footprint is None or terrain.bounds is None:
                continue
            if not _bounds_overlap(line_bounds, terrain.bounds):
                continue
            if terrain.is_ruins:
                shooter_inside, shooter_wholly = shooter_ruins_by_id.get(terrain.stable_id, (False, False))
                target_inside = bool(target_ruins_by_id.get(terrain.stable_id, False))
                if not (shooter_is_aircraft or target_is_aircraft):
                    if not shooter_inside and not target_inside:
                        self._record_count("los.exact_predicate_calls")
                        if terrain.footprint.intersects(line2d):
                            self._record_count("los.first_blocker_exits")
                            return result(True, terrain.stable_id)
                    if shooter_inside and not shooter_wholly and not shooter_is_towering and not target_inside:
                        self._record_count("los.first_blocker_exits")
                        return result(True, terrain.stable_id)
                continue
            if terrain.has_walls:
                continue
            self._record_count("los.exact_predicate_calls")
            if not terrain.footprint.intersects(line2d):
                continue
            inter_pt = _line_intersection_point(line2d, terrain.footprint)
            if inter_pt is None:
                continue
            t = line2d.project(inter_pt) / line_length if line_length > 0 else 0.0
            if t <= 1e-6 or t >= 1.0 - 1e-6:
                continue
            z_here = z_at_t(t)
            min_z, max_z = terrain.z_bounds
            if min_z <= z_here <= max_z:
                self._record_count("los.first_blocker_exits")
                return result(True, terrain.stable_id)

        for wall in wall_candidates:
            if not isinstance(wall, WallVisibilityRecord):
                continue
            if not _bounds_overlap(line_bounds, wall.bounds):
                continue
            self._record_count("los.exact_predicate_calls")
            if not wall.polygon.intersects(line2d):
                continue
            inter_pt = _line_intersection_point(line2d, wall.polygon)
            if inter_pt is None:
                continue
            t = line2d.project(inter_pt) / line_length if line_length > 0 else 0.0
            if t <= 1e-6 or t >= 1.0 - 1e-6:
                continue
            z_here = z_at_t(t)
            if z_here < wall.z_bottom or z_here > wall.z_top:
                continue
            allowed = False
            for opening in self.openings_by_terrain_id.get(wall.terrain_id, ()):
                if not _bounds_overlap((inter_pt.x, inter_pt.y, inter_pt.x, inter_pt.y), opening.bounds):
                    continue
                self._record_count("los.exact_predicate_calls")
                if not opening.polygon.contains(inter_pt):
                    continue
                if opening.z_bottom <= z_here <= opening.z_top:
                    allowed = True
                    break
            if not allowed:
                self._record_count("los.first_blocker_exits")
                return result(True, wall.stable_id)

        enemy_id_set = set(enemy_unit_ids)
        target_id_set = set(target_unit_ids)
        for blocker in model_candidates:
            if not isinstance(blocker, ModelBlockerRecord):
                continue
            if blocker.unit_id not in enemy_id_set or blocker.unit_id in target_id_set:
                continue
            if not _bounds_overlap(line_bounds, blocker.bounds):
                continue
            self._record_count("los.exact_predicate_calls")
            if not blocker.shape.intersects(line2d):
                continue
            inter_pt = _line_intersection_point(line2d, blocker.shape)
            if inter_pt is None:
                continue
            t = line2d.project(inter_pt) / line_length if line_length > 0 else 0.0
            if t <= 1e-6 or t >= 1.0 - 1e-6:
                continue
            z_here = z_at_t(t)
            z_bottom, z_top = blocker.z_bounds
            if z_bottom <= z_here <= z_top:
                self._record_count("los.first_blocker_exits")
                return result(True, blocker.stable_id)

        return result(False, "")

    def _ruins_states(
        self,
        shape: object,
        *,
        include_wholly: bool,
    ) -> tuple[tuple[Any, ...], ...]:
        states: list[tuple[Any, ...]] = []
        for terrain in self.terrain_records:
            if not terrain.is_ruins or terrain.footprint is None:
                continue
            try:
                inside = bool(terrain.footprint.intersects(shape))
                if include_wholly:
                    wholly = bool(terrain.footprint.covers(shape))
                    states.append((terrain.stable_id, inside, wholly))
                else:
                    states.append((terrain.stable_id, inside))
            except GEOSException:
                if include_wholly:
                    states.append((terrain.stable_id, False, False))
                else:
                    states.append((terrain.stable_id, False))
        states.sort(key=lambda item: str(item[0]))
        return tuple(states)

    def can_model_see_model(
        self,
        shooter_model: object,
        target_model: object,
        *,
        shooter_unit: object | None = None,
        target_unit: object | None = None,
        visibility_query: VisibilityModifierQuery | dict[str, Any] | None = None,
        include_model_blockers: bool = True,
    ) -> tuple[bool, str, str]:
        if not _model_alive(shooter_model) or not _model_alive(target_model):
            return False, "", "invalid_model"
        shooter_geometry = self._model_geometry(shooter_model)
        target_geometry = self._model_geometry(target_model)
        if shooter_geometry is None or target_geometry is None:
            return False, "", "invalid_geometry"
        shooter_unit = shooter_unit if shooter_unit is not None else getattr(shooter_model, "parent_unit", None)
        target_unit = target_unit if target_unit is not None else getattr(target_model, "parent_unit", None)
        shooter_unit_id = _cache_entity_key(shooter_unit)
        target_unit_ids = tuple(
            sorted(
                {
                    _cache_entity_key(target_unit),
                    _cache_entity_key(getattr(target_model, "parent_unit", target_unit)),
                }
            )
        )
        enemy_unit_ids = self._enemy_unit_ids(shooter_unit) if include_model_blockers else ()
        shooter_ruins_states = self._ruins_states(shooter_geometry.shape, include_wholly=True)
        target_ruins_states = self._ruins_states(target_geometry.shape, include_wholly=False)
        ruleset_signature = (
            bool(preview_visibility_semantics_enabled(self.game_map)),
            str(getattr(self.game_map, "preview_visibility_ruleset", "") or ""),
            visibility_query_signature(visibility_query),
        )
        shooter_is_aircraft = bool(getattr(shooter_unit, "is_aircraft", False))
        target_is_aircraft = bool(getattr(target_unit, "is_aircraft", False))
        shooter_is_towering = bool(getattr(shooter_unit, "is_towering", False))
        terrain_candidates, wall_candidates, model_candidates = self._pair_candidate_sets(
            shooter_geometry,
            target_geometry,
            include_model_blockers=bool(enemy_unit_ids),
        )

        try:
            for stage, p0, p1 in self._staged_segment_pairs(shooter_model, target_model, shooter_geometry, target_geometry):
                blocked, blocker_id = self.segment_is_blocked(
                    p0,
                    p1,
                    shooter_unit_id=shooter_unit_id,
                    target_unit_ids=target_unit_ids,
                    enemy_unit_ids=enemy_unit_ids,
                    shooter_is_aircraft=shooter_is_aircraft,
                    target_is_aircraft=target_is_aircraft,
                    shooter_is_towering=shooter_is_towering,
                    shooter_ruins_states=shooter_ruins_states,
                    target_ruins_states=target_ruins_states,
                    ruleset_signature=ruleset_signature,
                    terrain_candidates=terrain_candidates,
                    wall_candidates=wall_candidates,
                    model_candidates=model_candidates,
                )
                if not blocked:
                    record_value(f"los.visible_stage.{stage}", 1)
                    return True, stage, ""
            return False, "blocked", ""
        finally:
            self._flush_count_metrics()

    def can_model_see_unit(
        self,
        shooter_model: object,
        target_unit: object,
        *,
        shooter_unit: object | None = None,
        visibility_query: VisibilityModifierQuery | dict[str, Any] | None = None,
    ) -> bool:
        if not _model_alive(shooter_model) or not _unit_alive(target_unit):
            return False
        target_models = tuple(model for model in _visibility_models_for_unit(target_unit) if _model_alive(model))
        if not target_models:
            return False
        shooter_unit = shooter_unit if shooter_unit is not None else getattr(shooter_model, "parent_unit", None)
        cache_key = (
            "model_to_unit_los_v1",
            _model_visibility_key(shooter_model),
            _cache_entity_key(shooter_unit),
            _cache_entity_key(target_unit),
            tuple(_model_visibility_key(model) for model in target_models),
            self.terrain_visibility_revision,
            self.model_blocker_revision,
            self.visibility_modifier_revision,
            visibility_query_signature(visibility_query),
        )
        cached = self.los_cache.get(cache_key)
        if cached is not None:
            self.los_cache.move_to_end(cache_key)
            record_value("los.unit_cache_hit", 1)
            return bool(cached)
        record_value("los.unit_cache_miss", 1)

        shooter_geometry = self._model_geometry(shooter_model)
        if shooter_geometry is None:
            self.los_cache[cache_key] = False
            return False
        target_models = tuple(
            sorted(
                target_models,
                key=lambda model: (
                    _distance_between_models_2d(shooter_model, model),
                    _cache_entity_key(model),
                ),
            )
        )
        for target_model in target_models:
            visible, _stage, _blocker_id = self.can_model_see_model(
                shooter_model,
                target_model,
                shooter_unit=shooter_unit,
                target_unit=getattr(target_model, "parent_unit", target_unit),
                visibility_query=visibility_query,
                include_model_blockers=True,
            )
            if visible:
                self.los_cache[cache_key] = True
                self.los_cache.move_to_end(cache_key)
                while len(self.los_cache) > _VISIBILITY_FRAME_LOS_CACHE_MAX:
                    self.los_cache.popitem(last=False)
                return True
        self.los_cache[cache_key] = False
        self.los_cache.move_to_end(cache_key)
        while len(self.los_cache) > _VISIBILITY_FRAME_LOS_CACHE_MAX:
            self.los_cache.popitem(last=False)
        return False


def _build_visibility_frame_context(game_map: object) -> VisibilityFrameContext:
    with profile_section("los.frame_context_build"):
        terrain_records: list[TerrainVisibilityRecord] = []
        wall_records: list[WallVisibilityRecord] = []
        opening_records: list[OpeningVisibilityRecord] = []
        openings_by_terrain_id: dict[str, list[OpeningVisibilityRecord]] = {}
        for terrain_index, terrain in enumerate(list(getattr(game_map, "terrain_features", []) or [])):
            terrain_id = str(getattr(terrain, "id", "") or f"terrain:{id(terrain)}:{terrain_index}")
            footprint = _prepare_geometry(getattr(terrain, "footprint", None))
            footprint_bounds = _geometry_bounds(footprint)
            walls = tuple(getattr(terrain, "walls", None) or ())
            openings = tuple(getattr(terrain, "openings", None) or ())
            has_walls = bool(walls)
            terrain_records.append(
                TerrainVisibilityRecord(
                    stable_id=terrain_id,
                    terrain=terrain,
                    footprint=footprint,
                    bounds=footprint_bounds,
                    z_bounds=_terrain_z_bounds(terrain),
                    is_ruins=hasattr(terrain, "walls") and hasattr(terrain, "openings") and footprint is not None,
                    has_walls=has_walls,
                )
            )
            for wall_index, wall in enumerate(walls):
                if not isinstance(wall, dict):
                    continue
                polygon = _prepare_geometry(wall.get("polygon"))
                bounds = _geometry_bounds(polygon)
                if polygon is None or bounds is None:
                    continue
                wall_records.append(
                    WallVisibilityRecord(
                        stable_id=f"{terrain_id}:wall:{wall_index}",
                        terrain_id=terrain_id,
                        polygon=polygon,
                        bounds=bounds,
                        z_bottom=float(wall.get("z_bottom", 0.0) or 0.0),
                        z_top=float(wall.get("z_top", wall.get("z_bottom", 0.0)) or 0.0),
                    )
                )
            for opening_index, opening in enumerate(openings):
                if not isinstance(opening, dict) or not bool(opening.get("allows_los", False)):
                    continue
                polygon = _prepare_geometry(opening.get("polygon"))
                bounds = _geometry_bounds(polygon)
                if polygon is None or bounds is None:
                    continue
                record = OpeningVisibilityRecord(
                    stable_id=f"{terrain_id}:opening:{opening_index}",
                    terrain_id=terrain_id,
                    polygon=polygon,
                    bounds=bounds,
                    z_bottom=float(opening.get("z_bottom", -1e9) or -1e9),
                    z_top=float(opening.get("z_top", 1e9) or 1e9),
                )
                opening_records.append(record)
                openings_by_terrain_id.setdefault(terrain_id, []).append(record)

        model_records: list[ModelBlockerRecord] = []
        model_geometry_by_id: dict[str, ModelVisibilityGeometry] = {}
        for unit in list(getattr(game_map, "units", []) or []):
            if not _unit_alive(unit) or not bool(getattr(unit, "deployed", True)):
                continue
            unit_id = _cache_entity_key(unit)
            for model in _visibility_models_for_unit(unit):
                if not _model_alive(model):
                    continue
                base = getattr(model, "model_base", None)
                if base is None:
                    continue
                shape = _prepare_geometry(base.get_base_shape())
                bounds = _geometry_bounds(shape)
                if shape is None or bounds is None:
                    continue
                volume_bounds = getattr(base, "volume_z_bounds", None)
                if callable(volume_bounds):
                    z_values = tuple(float(value) for value in volume_bounds())
                else:
                    z = float(getattr(base, "z", 0.0) or 0.0)
                    z_values = (z, z)
                model_id = _cache_entity_key(model)
                center = shape.centroid
                geometry = ModelVisibilityGeometry(
                    stable_id=model_id,
                    model=model,
                    shape=shape,
                    bounds=bounds,
                    z_bounds=(float(z_values[0]), float(z_values[1])),
                    center_xy=(float(center.x), float(center.y)),
                )
                model_geometry_by_id[model_id] = geometry
                model_records.append(
                    ModelBlockerRecord(
                        stable_id=f"{unit_id}:{model_id}",
                        unit_id=unit_id,
                        model_id=model_id,
                        model=model,
                        shape=shape,
                        bounds=bounds,
                        z_bounds=geometry.z_bounds,
                    )
                )

        terrain_geometries = [record.footprint for record in terrain_records if record.footprint is not None]
        terrain_tree_records = tuple(record for record in terrain_records if record.footprint is not None)
        wall_geometries = [record.polygon for record in wall_records]
        model_geometries = [record.shape for record in model_records]
        opening_geometries = [record.polygon for record in opening_records]
        record_value("los.frame_terrain_records", len(terrain_tree_records))
        record_value("los.frame_wall_records", len(wall_records))
        record_value("los.frame_model_records", len(model_records))
        return VisibilityFrameContext(
            game_map=game_map,
            terrain_visibility_revision=_visibility_revision(game_map, "terrain_visibility_revision"),
            model_blocker_revision=_visibility_revision(game_map, "model_blocker_revision"),
            visibility_modifier_revision=_visibility_revision(game_map, "visibility_modifier_revision"),
            terrain_records=terrain_tree_records,
            wall_records=tuple(wall_records),
            opening_records=tuple(opening_records),
            model_blocker_records=tuple(model_records),
            terrain_tree=STRtree(terrain_geometries) if terrain_geometries else None,
            wall_tree=STRtree(wall_geometries) if wall_geometries else None,
            opening_tree=STRtree(opening_geometries) if opening_geometries else None,
            model_blocker_tree=STRtree(model_geometries) if model_geometries else None,
            model_geometry_by_id=model_geometry_by_id,
            openings_by_terrain_id={
                terrain_id: tuple(sorted(records, key=lambda record: record.stable_id))
                for terrain_id, records in openings_by_terrain_id.items()
            },
        )


def get_visibility_frame_context(game_map: object) -> VisibilityFrameContext:
    cache_key = _frame_context_cache_key(game_map)
    cache = _visibility_frame_context_cache(game_map)
    cached = cache.get(cache_key)
    if isinstance(cached, VisibilityFrameContext):
        cache.move_to_end(cache_key)
        record_value("los.frame_context_cache_hit", 1)
        return cached
    record_value("los.frame_context_cache_miss", 1)
    context = _build_visibility_frame_context(game_map)
    cache[cache_key] = context
    cache.move_to_end(cache_key)
    while len(cache) > _VISIBILITY_FRAME_CONTEXT_CACHE_MAX:
        cache.popitem(last=False)
    return context


def preview_visibility_semantics_enabled(game_map: object) -> bool:
    return bool(getattr(game_map, "preview_visibility_semantics_enabled", False))


@profiled_section("los.visibility_context")
def get_visibility_context_for_models(
    game_map: object,
    shooter_model: object,
    target_model: object,
    *,
    visibility_query: VisibilityModifierQuery | dict[str, Any] | None = None,
) -> dict[str, Any]:
    cache_key = _visibility_context_cache_key(game_map, shooter_model, target_model, visibility_query)
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
        "hidden_detection_range_base": None,
        "detection_marker_delta": 0.0,
        "attack_scoped_detection_range_delta": 0.0,
        "fixed_detection_range_override": None,
        "applied_detection_marker_ids": [],
        "applied_visibility_modifier_ids": [],
        "hidden_shooting_exemption_ids": [],
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
    shooter_unit = getattr(shooter_model, "parent_unit", None)
    target_unit = getattr(target_model, "parent_unit", None)
    segment_visibility_flags = (
        bool(getattr(shooter_unit, "is_aircraft", False)),
        bool(getattr(target_unit, "is_aircraft", False)),
        bool(getattr(shooter_unit, "is_towering", False)),
    )

    target_areas = _target_areas_for_model(game_map, target_model)
    if result["preview_visibility_semantics_enabled"]:
        hidden_active, detection_range = _hidden_active(game_map, target_model, target_areas)
        result["hidden_state_active"] = bool(hidden_active)
        result["hidden_detection_range"] = detection_range
        result["hidden_detection_range_base"] = detection_range
        result["hidden_shooting_exemption_ids"] = list(hidden_preserving_exemption_ids_for_unit(game_map, target_unit))
        if hidden_active:
            modifier_query = coerce_visibility_modifier_query(
                visibility_query,
                source_unit=shooter_unit,
                target_unit=target_unit,
                base_detection_range=detection_range,
            )
            modifier_result = collect_visibility_modifiers(game_map, modifier_query)
            result.update(modifier_result.to_context_fields())
            for entry in modifier_result.reason_trace:
                reason_trace.append(entry)
            detection_range = modifier_result.effective_detection_range
            distance = _distance_between_models_2d(shooter_model, target_model)
            _append_reason(
                reason_trace,
                "TARGET_HIDDEN_ACTIVE",
                "Target is in a provisional Hidden state.",
                metadata={
                    "distance": distance,
                    "detection_range": detection_range,
                    "base_detection_range": result["hidden_detection_range_base"],
                },
            )
            if detection_range is None or distance > float(detection_range):
                result["hidden_blocked"] = True
                _append_reason(
                    reason_trace,
                    "HIDDEN_BLOCKED_BY_DETECTION_RANGE",
                    "Target remains hidden because the shooter is outside detection range.",
                    metadata={
                        "distance": distance,
                        "detection_range": detection_range,
                        "base_detection_range": result["hidden_detection_range_base"],
                    },
                )
                return _cache_and_return()
            result["detection_range_override_applies"] = True
            _append_reason(
                reason_trace,
                "DETECTION_RANGE_OVERRIDE_APPLIES",
                "Target is visible because the shooter is within detection range.",
                metadata={
                    "distance": distance,
                    "detection_range": detection_range,
                    "base_detection_range": result["hidden_detection_range_base"],
                },
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

    context = get_visibility_frame_context(game_map)
    visible, stage, blocker_id = context.can_model_see_model(
        shooter_model,
        target_model,
        shooter_unit=shooter_unit,
        target_unit=target_unit,
        visibility_query=visibility_query,
        include_model_blockers=False,
    )
    if visible:
        result["visible"] = True
        _append_reason(
            reason_trace,
            "INDEXED_LOS_CLEAR",
            "A sampled line of sight path is clear.",
            metadata={"stage": stage},
        )
        return _cache_and_return()

    _append_reason(
        reason_trace,
        "INDEXED_LOS_BLOCKED",
        "All sampled line of sight paths are blocked.",
        metadata={"stage": stage, "blocker_id": blocker_id},
    )
    return _cache_and_return()


def can_model_see_model(
    game_map: object,
    shooter_model: object,
    target_model: object,
    *,
    visibility_query: VisibilityModifierQuery | dict[str, Any] | None = None,
) -> bool:
    return bool(
        get_visibility_context_for_models(
            game_map,
            shooter_model,
            target_model,
            visibility_query=visibility_query,
        ).get("visible", False)
    )


__all__ = [
    "VisibilityFrameContext",
    "build_reason_trace_entry",
    "can_model_see_model",
    "get_visibility_frame_context",
    "get_visibility_context_for_models",
    "is_fully_visible_due_to_terrain",
    "preview_visibility_semantics_enabled",
    "sample_model_points_3d",
    "segment_blocked_by_terrain_feature",
]
