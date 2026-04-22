from __future__ import annotations

from math import hypot
from typing import Any

from shapely.errors import GEOSException
from shapely.geometry import LineString

from .terrain_runtime import iter_terrain_areas
from ..utility.profiling_sections import profiled_section


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


@profiled_section("los.segment_blocked_by_terrain")
def segment_blocked_by_terrain_feature(
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    terrain: object,
    shooter_model: object,
    target_model: object,
) -> bool:
    """Return True if the segment is blocked by this terrain feature."""
    line2d = LineString([(p0[0], p0[1]), (p1[0], p1[1])])
    if line2d.length == 0:
        return False

    def z_at_fraction(fraction: float) -> float:
        return float(p0[2]) + fraction * (float(p1[2]) - float(p0[2]))

    footprint = getattr(terrain, "footprint", None)
    if footprint is None:
        return False

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

    shooter_shape = _model_base_shape(shooter_model)
    target_shape = _model_base_shape(target_model)
    if shooter_shape is None or target_shape is None:
        _append_reason(reason_trace, "INVALID_MODEL_GEOMETRY", "Shooter or target model lacks base geometry.")
        return result

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
                return result
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
            return result

    shooter_points = sample_model_points_3d(shooter_model, perimeter_points=6, z_levels=2)
    target_points = sample_model_points_3d(target_model, perimeter_points=6, z_levels=2)
    if not shooter_points or not target_points:
        _append_reason(reason_trace, "NO_SAMPLE_POINTS", "Visibility sampling could not resolve model points.")
        return result

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
                return result

    _append_reason(
        reason_trace,
        "LEGACY_LOS_BLOCKED",
        "All sampled line of sight paths are blocked by terrain.",
        metadata={"terrain_id": first_blocking_terrain_id},
    )
    return result


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
