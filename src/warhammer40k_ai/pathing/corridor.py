from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable, Optional

from shapely.geometry import LineString

from .cdt_mesh import SurfaceCdtMesh, portal_by_id

_EPSILON = 1e-9


@dataclass(frozen=True, eq=False)
class CorridorResult:
    portal_ids: tuple[str, ...]
    raw_waypoints_xy: tuple[tuple[float, float], ...]
    smoothed_waypoints_xy: tuple[tuple[float, float], ...]
    total_distance: float


def _tri_area2(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _same_point(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(float(a[0]) - float(b[0])) <= _EPSILON and abs(float(a[1]) - float(b[1])) <= _EPSILON


def _segment_endpoints(segment: LineString) -> tuple[tuple[float, float], tuple[float, float]]:
    coords = tuple(segment.coords)
    if len(coords) < 2:
        point = (float(coords[0][0]), float(coords[0][1])) if coords else (0.0, 0.0)
        return point, point
    first = (float(coords[0][0]), float(coords[0][1]))
    last = (float(coords[-1][0]), float(coords[-1][1]))
    return first, last


def _portal_lr(
    apex: tuple[float, float],
    segment: LineString,
) -> tuple[tuple[float, float], tuple[float, float]]:
    first, last = _segment_endpoints(segment)
    if _tri_area2(apex, first, last) >= 0.0:
        return first, last
    return last, first


def _compute_total_distance(points: tuple[tuple[float, float], ...]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for index in range(1, len(points)):
        dx = float(points[index][0]) - float(points[index - 1][0])
        dy = float(points[index][1]) - float(points[index - 1][1])
        total += hypot(dx, dy)
    return float(total)


def _dedupe_points(points: Iterable[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    deduped: list[tuple[float, float]] = []
    for point in points:
        as_tuple = (float(point[0]), float(point[1]))
        if not deduped or not _same_point(deduped[-1], as_tuple):
            deduped.append(as_tuple)
    return tuple(deduped)


def portal_id_between_triangles(
    mesh: SurfaceCdtMesh,
    triangle_a: int,
    triangle_b: int,
) -> Optional[str]:
    if triangle_a < 0 or triangle_a >= len(mesh.triangle_neighbors):
        return None
    for neighbor_index, portal_id in mesh.triangle_neighbors[triangle_a]:
        if int(neighbor_index) == int(triangle_b):
            return str(portal_id)
    return None


def portal_ids_for_triangle_path(
    mesh: SurfaceCdtMesh,
    triangle_path: tuple[int, ...],
) -> tuple[str, ...]:
    if len(triangle_path) <= 1:
        return ()
    portal_ids: list[str] = []
    for index in range(1, len(triangle_path)):
        portal_id = portal_id_between_triangles(
            mesh,
            triangle_path[index - 1],
            triangle_path[index],
        )
        if portal_id is None:
            raise ValueError(
                f"Triangle path for surface {mesh.surface_id} is not contiguous at index {index - 1}->{index}"
            )
        portal_ids.append(portal_id)
    return tuple(portal_ids)


def string_pull_portals(
    start_xy: tuple[float, float],
    goal_xy: tuple[float, float],
    portal_segments: tuple[LineString, ...],
) -> tuple[tuple[float, float], ...]:
    start = (float(start_xy[0]), float(start_xy[1]))
    goal = (float(goal_xy[0]), float(goal_xy[1]))
    if not portal_segments:
        return _dedupe_points((start, goal))

    points: list[tuple[float, float]] = [start]

    apex = start
    left = start
    right = start
    apex_index = 0
    left_index = 0
    right_index = 0
    index = 0

    portals = tuple(portal_segments) + (LineString([goal, goal]),)

    while index < len(portals):
        portal_left, portal_right = _portal_lr(apex, portals[index])

        if _tri_area2(apex, right, portal_right) <= 0.0:
            if _same_point(apex, right) or _tri_area2(apex, left, portal_right) > 0.0:
                right = portal_right
                right_index = index + 1
            else:
                points.append(left)
                apex = left
                apex_index = left_index
                left = apex
                right = apex
                left_index = apex_index
                right_index = apex_index
                index = apex_index
                continue

        if _tri_area2(apex, left, portal_left) >= 0.0:
            if _same_point(apex, left) or _tri_area2(apex, right, portal_left) < 0.0:
                left = portal_left
                left_index = index + 1
            else:
                points.append(right)
                apex = right
                apex_index = right_index
                left = apex
                right = apex
                left_index = apex_index
                right_index = apex_index
                index = apex_index
                continue

        index += 1

    points.append(goal)
    return _dedupe_points(points)


def build_corridor(
    mesh: SurfaceCdtMesh,
    triangle_path: tuple[int, ...],
    *,
    start_xy: tuple[float, float],
    goal_xy: tuple[float, float],
) -> CorridorResult:
    portal_ids = portal_ids_for_triangle_path(mesh, triangle_path)
    portal_segments: list[LineString] = []
    raw_waypoints: list[tuple[float, float]] = [(float(start_xy[0]), float(start_xy[1]))]

    for portal_id in portal_ids:
        portal = portal_by_id(mesh, portal_id)
        if portal is None:
            raise ValueError(f"Portal '{portal_id}' not found in mesh '{mesh.surface_id}'")
        portal_segments.append(portal.segment)
        raw_waypoints.append((float(portal.midpoint_xy[0]), float(portal.midpoint_xy[1])))
    raw_waypoints.append((float(goal_xy[0]), float(goal_xy[1])))

    smoothed = string_pull_portals(
        start_xy=(float(start_xy[0]), float(start_xy[1])),
        goal_xy=(float(goal_xy[0]), float(goal_xy[1])),
        portal_segments=tuple(portal_segments),
    )
    raw_waypoints_tuple = _dedupe_points(raw_waypoints)
    return CorridorResult(
        portal_ids=portal_ids,
        raw_waypoints_xy=raw_waypoints_tuple,
        smoothed_waypoints_xy=smoothed,
        total_distance=_compute_total_distance(smoothed),
    )


__all__ = [
    "CorridorResult",
    "build_corridor",
    "portal_id_between_triangles",
    "portal_ids_for_triangle_path",
    "string_pull_portals",
]
