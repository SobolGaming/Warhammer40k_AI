from __future__ import annotations

import hashlib
from typing import Any, Iterable

from ..utility.placement_search import deployed_unit_bounds


def zone_bounds(
    zone: dict[str, Any] | None,
    *,
    default_bounds: tuple[float, float, float, float] | None = None,
) -> tuple[float, float, float, float] | None:
    zone_dict = dict(zone or {})
    explicit_bounds = zone_dict.get("bounds")
    if isinstance(explicit_bounds, (list, tuple)) and len(explicit_bounds) >= 4:
        try:
            return (
                float(min(explicit_bounds[0], explicit_bounds[1])),
                float(max(explicit_bounds[0], explicit_bounds[1])),
                float(min(explicit_bounds[2], explicit_bounds[3])),
                float(max(explicit_bounds[2], explicit_bounds[3])),
            )
        except (TypeError, ValueError):
            return default_bounds

    mission_zones = list(zone_dict.get("mission_zones", []) or [])
    xs: list[float] = []
    ys: list[float] = []
    for mission_zone in mission_zones:
        vertices = list(getattr(mission_zone, "vertices", []) or [])
        for vertex in vertices:
            if isinstance(vertex, (list, tuple)) and len(vertex) >= 2:
                xs.append(float(vertex[0]))
                ys.append(float(vertex[1]))
    if xs and ys:
        return (min(xs), max(xs), min(ys), max(ys))

    x_range = zone_dict.get("x_range")
    y_range = zone_dict.get("y_range")
    if (
        isinstance(x_range, (list, tuple))
        and isinstance(y_range, (list, tuple))
        and len(x_range) >= 2
        and len(y_range) >= 2
    ):
        return (
            float(min(x_range[0], x_range[1])),
            float(max(x_range[0], x_range[1])),
            float(min(y_range[0], y_range[1])),
            float(max(y_range[0], y_range[1])),
        )
    return default_bounds


def zone_center(
    zone: dict[str, Any] | None,
    *,
    default_bounds: tuple[float, float, float, float] | None = None,
) -> tuple[float, float]:
    zone_dict = dict(zone or {})
    explicit_center = zone_dict.get("center")
    if isinstance(explicit_center, (list, tuple)) and len(explicit_center) >= 2:
        try:
            return (float(explicit_center[0]), float(explicit_center[1]))
        except (TypeError, ValueError):
            pass

    mission_zones = list(zone_dict.get("mission_zones", []) or [])
    if mission_zones:
        xs: list[float] = []
        ys: list[float] = []
        for mission_zone in mission_zones:
            vertices = list(getattr(mission_zone, "vertices", []) or [])
            for vertex in vertices:
                if len(vertex) >= 2:
                    xs.append(float(vertex[0]))
                    ys.append(float(vertex[1]))
        if xs and ys:
            return (sum(xs) / float(len(xs)), sum(ys) / float(len(ys)))

    x_range = zone_dict.get("x_range")
    y_range = zone_dict.get("y_range")
    if (
        isinstance(x_range, (list, tuple))
        and isinstance(y_range, (list, tuple))
        and len(x_range) >= 2
        and len(y_range) >= 2
    ):
        return (
            (float(x_range[0]) + float(x_range[1])) / 2.0,
            (float(y_range[0]) + float(y_range[1])) / 2.0,
        )

    bounds = zone_bounds(zone_dict, default_bounds=default_bounds)
    if bounds is not None:
        min_x, max_x, min_y, max_y = bounds
        return ((float(min_x) + float(max_x)) / 2.0, (float(min_y) + float(max_y)) / 2.0)
    return (0.0, 0.0)


def point_in_zone(zone: dict[str, Any] | None, x: float, y: float) -> bool:
    zone_dict = dict(zone or {})
    contains_point = zone_dict.get("contains_point")
    if callable(contains_point):
        return bool(contains_point(float(x), float(y)))

    mission_zones = list(zone_dict.get("mission_zones", []) or [])
    if mission_zones:
        for mission_zone in mission_zones:
            contains_fn = getattr(mission_zone, "contains_point", None)
            if callable(contains_fn) and bool(contains_fn(float(x), float(y))):
                return True
        return False

    bounds = zone_bounds(zone_dict)
    if bounds is None:
        return True
    min_x, max_x, min_y, max_y = bounds
    return float(min_x) <= float(x) <= float(max_x) and float(min_y) <= float(y) <= float(max_y)


def axis_points(start: float, end: float, *, step: float, offset: float) -> list[float]:
    lo = float(min(start, end))
    hi = float(max(start, end))
    if hi - lo <= 1e-6:
        return [lo]
    values: list[float] = []
    first = lo + float(offset)
    if first > hi:
        first = lo
    cursor = first
    while cursor <= hi + 1e-6:
        values.append(round(float(cursor), 4))
        cursor += float(step)
    if not values:
        values = [round((lo + hi) / 2.0, 4)]
    return values


def ordered_offsets(*, unit_id: str, occupied_count: int, lattice_step: float) -> list[tuple[float, float]]:
    base: list[tuple[float, float]] = [(0.0, 0.0)]
    rings = [1, 2, 3, 4, 5, 6, 8, 10, 12]
    for ring in rings:
        step = float(ring) * float(lattice_step)
        base.extend(
            [
                (step, 0.0),
                (-step, 0.0),
                (0.0, step),
                (0.0, -step),
                (step, step),
                (step, -step),
                (-step, step),
                (-step, -step),
            ]
        )

    digest = hashlib.sha256(f"{unit_id}:{int(occupied_count)}".encode("utf-8")).hexdigest()
    rotate_by = int(digest[:8], 16) % max(1, len(base))
    return base[rotate_by:] + base[:rotate_by]


def lattice_candidate_positions(
    zone: dict[str, Any] | None,
    *,
    unit_id: str,
    occupied_count: int,
    lattice_step: float,
    default_bounds: tuple[float, float, float, float] | None = None,
) -> list[tuple[float, float]]:
    center_x, center_y = zone_center(zone, default_bounds=default_bounds)
    offsets = ordered_offsets(unit_id=unit_id, occupied_count=occupied_count, lattice_step=float(lattice_step))
    candidates: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()

    for dx, dy in offsets:
        x = float(center_x + dx)
        y = float(center_y + dy)
        key = (round(x, 3), round(y, 3))
        if key in seen:
            continue
        if not point_in_zone(zone, x, y):
            continue
        seen.add(key)
        candidates.append((x, y))

    if candidates:
        return candidates
    return [(float(center_x), float(center_y))]


def exhaustive_lattice_candidate_positions(
    zone: dict[str, Any] | None,
    *,
    unit_id: str,
    exhaustive_lattice_step: float,
    exhaustive_anchor_limit: int,
    default_bounds: tuple[float, float, float, float] | None = None,
) -> list[tuple[float, float]]:
    bounds = zone_bounds(zone, default_bounds=default_bounds)
    if bounds is None:
        return []
    min_x, max_x, min_y, max_y = bounds
    if min_x > max_x or min_y > max_y:
        return []

    center_x, center_y = zone_center(zone, default_bounds=default_bounds)
    candidates: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    step_primary = float(exhaustive_lattice_step)
    step_secondary = max(0.25, step_primary / 2.0)
    for step in (step_primary, step_secondary):
        offsets = (0.0, step / 2.0)
        for off_y in offsets:
            ys = axis_points(min_y, max_y, step=step, offset=off_y)
            if not ys:
                continue
            for off_x in offsets:
                xs = axis_points(min_x, max_x, step=step, offset=off_x)
                if not xs:
                    continue
                for y in ys:
                    for x in xs:
                        key = (round(float(x), 3), round(float(y), 3))
                        if key in seen:
                            continue
                        seen.add(key)
                        candidates.append((float(x), float(y)))

    def _scan_sort_key(point: tuple[float, float]) -> tuple[float, str]:
        x, y = point
        dist_sq = (float(x) - float(center_x)) ** 2 + (float(y) - float(center_y)) ** 2
        token = f"{unit_id}:{x:.3f}:{y:.3f}"
        tie = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return (float(dist_sq), tie)

    candidates.sort(key=_scan_sort_key)
    return candidates[: int(exhaustive_anchor_limit)]


def edge_first_axis_points(lo: float, hi: float, *, step: float, margin: float) -> list[float]:
    start = float(lo) + float(margin)
    end = float(hi) - float(margin)
    if end < start:
        return [float((lo + hi) * 0.5)]
    values: list[float] = []
    seen: set[float] = set()
    for offset in (0.0, float(step) * 0.5):
        for value in axis_points(start, end, step=float(step), offset=float(offset)):
            key = round(float(value), 4)
            if key in seen:
                continue
            seen.add(key)
            values.append(float(value))
    mid = (float(start) + float(end)) * 0.5
    values.sort(key=lambda value: (min(abs(value - start), abs(end - value)), abs(value - mid), value))
    return values


def back_to_front_axis_points(
    lo: float,
    hi: float,
    *,
    step: float,
    margin: float,
    forward_positive: bool,
) -> list[float]:
    start = float(lo) + float(margin)
    end = float(hi) - float(margin)
    if end < start:
        return [float((lo + hi) * 0.5)]
    values: list[float] = []
    if forward_positive:
        cursor = float(start)
        while cursor <= end + 1e-6:
            values.append(round(float(cursor), 4))
            cursor += float(step)
    else:
        cursor = float(end)
        while cursor >= start - 1e-6:
            values.append(round(float(cursor), 4))
            cursor -= float(step)
    if not values:
        values = [round(float((lo + hi) * 0.5), 4)]
    return [float(value) for value in values]


def packing_row_anchor_candidates(
    zone: dict[str, Any] | None,
    *,
    board_width: float,
    board_height: float,
    footprint: dict[str, float],
    lattice_step: float,
    default_bounds: tuple[float, float, float, float] | None = None,
) -> list[tuple[float, float]]:
    bounds = zone_bounds(zone, default_bounds=default_bounds)
    if bounds is None:
        return []
    min_x, max_x, min_y, max_y = bounds
    center_x, center_y = zone_center(zone, default_bounds=default_bounds)

    zone_dict = dict(zone or {})
    depth_axis = str(zone_dict.get("forward_axis", "") or "").strip().lower()
    forward_positive_value = zone_dict.get("forward_positive", None)
    if depth_axis in {"x", "y"} and isinstance(forward_positive_value, bool):
        depth_is_x = depth_axis == "x"
        forward_positive = bool(forward_positive_value)
    else:
        forward_dx = (float(board_width) * 0.5) - float(center_x)
        forward_dy = (float(board_height) * 0.5) - float(center_y)
        depth_is_x = abs(forward_dx) >= abs(forward_dy)
        forward_positive = forward_dx >= 0.0 if depth_is_x else forward_dy >= 0.0

    depth_margin = max(0.5, float(footprint["largest_radius"]) + 0.25)
    frontage_margin = max(0.5, float(footprint["largest_radius"]) + 0.25)
    depth_step = max(float(lattice_step), float(footprint["depth"]) * 0.9)
    frontage_step = max(float(lattice_step), float(footprint["width"]) * 0.9)
    if depth_is_x:
        depth_values = back_to_front_axis_points(
            min_x,
            max_x,
            step=depth_step,
            margin=depth_margin,
            forward_positive=forward_positive,
        )
        frontage_values = edge_first_axis_points(min_y, max_y, step=frontage_step, margin=frontage_margin)
    else:
        depth_values = back_to_front_axis_points(
            min_y,
            max_y,
            step=depth_step,
            margin=depth_margin,
            forward_positive=forward_positive,
        )
        frontage_values = edge_first_axis_points(min_x, max_x, step=frontage_step, margin=frontage_margin)

    candidates: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for row_idx, depth in enumerate(list(depth_values or [])):
        along_values = list(frontage_values or [])
        if row_idx % 2 == 1:
            along_values.reverse()
        for along in along_values:
            anchor = (float(depth), float(along)) if depth_is_x else (float(along), float(depth))
            key = (round(anchor[0], 3), round(anchor[1], 3))
            if key in seen:
                continue
            seen.add(key)
            if not point_in_zone(zone, anchor[0], anchor[1]):
                continue
            candidates.append(anchor)
    return candidates


def gap_anchor_candidates(
    zone: dict[str, Any] | None,
    *,
    occupied_units: Iterable[object],
    footprint: dict[str, float],
    default_bounds: tuple[float, float, float, float] | None = None,
) -> list[tuple[float, float]]:
    bounds = zone_bounds(zone, default_bounds=default_bounds)
    if bounds is None:
        return []
    min_x, max_x, min_y, max_y = bounds
    clearance = max(0.75, float(footprint["largest_radius"]) + 0.5)
    center_x, center_y = zone_center(zone, default_bounds=default_bounds)
    candidates: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for occupied in list(occupied_units or []):
        unit_bounds = deployed_unit_bounds(occupied)
        if unit_bounds is None:
            continue
        bx0, by0, bx1, by1 = unit_bounds
        cx = (float(bx0) + float(bx1)) * 0.5
        cy = (float(by0) + float(by1)) * 0.5
        options = (
            (float(bx0) - clearance, cy),
            (float(bx1) + clearance, cy),
            (cx, float(by0) - clearance),
            (cx, float(by1) + clearance),
            (float(bx0) - clearance, float(by0) - clearance),
            (float(bx0) - clearance, float(by1) + clearance),
            (float(bx1) + clearance, float(by0) - clearance),
            (float(bx1) + clearance, float(by1) + clearance),
        )
        for x, y in options:
            clamped = (
                float(max(min_x, min(max_x, float(x)))),
                float(max(min_y, min(max_y, float(y)))),
            )
            key = (round(clamped[0], 3), round(clamped[1], 3))
            if key in seen:
                continue
            seen.add(key)
            if not point_in_zone(zone, clamped[0], clamped[1]):
                continue
            candidates.append(clamped)
    candidates.sort(
        key=lambda point: (
            (float(point[0]) - float(center_x)) ** 2 + (float(point[1]) - float(center_y)) ** 2,
            point[0],
            point[1],
        )
    )
    return candidates
