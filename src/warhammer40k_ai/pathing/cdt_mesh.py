from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Optional

from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import triangulate

from .types import SurfaceId

_AREA_EPSILON = 1e-8
_LENGTH_EPSILON = 1e-8


@dataclass(frozen=True, eq=False)
class SurfacePortal:
    portal_id: str
    surface_id: SurfaceId
    triangle_a: int
    triangle_b: int
    segment: LineString
    midpoint_xy: tuple[float, float]
    length: float


@dataclass(frozen=True, eq=False)
class SurfaceCdtMesh:
    surface_id: SurfaceId
    triangulation_backend: str
    free_space: BaseGeometry
    triangles: tuple[Polygon, ...]
    triangle_centroids: tuple[tuple[float, float], ...]
    portals: tuple[SurfacePortal, ...]
    triangle_neighbors: tuple[tuple[tuple[int, str], ...], ...]


def _iter_polygons(geometry: BaseGeometry) -> tuple[Polygon, ...]:
    if geometry.is_empty:
        return ()
    if isinstance(geometry, Polygon):
        return (geometry,)
    if isinstance(geometry, MultiPolygon):
        return tuple(geom for geom in geometry.geoms if isinstance(geom, Polygon) and not geom.is_empty)
    if isinstance(geometry, GeometryCollection):
        polygons: list[Polygon] = []
        for geom in geometry.geoms:
            polygons.extend(_iter_polygons(geom))
        return tuple(polygons)
    return ()


def _geometry_sort_key(geometry: BaseGeometry) -> tuple[float, float, float, float, float]:
    min_x, min_y, max_x, max_y = geometry.bounds
    return (
        round(float(min_x), 6),
        round(float(min_y), 6),
        round(float(max_x), 6),
        round(float(max_y), 6),
        round(float(geometry.area), 6),
    )


def _polygon_edges(polygon: Polygon) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    coords = tuple((float(x), float(y)) for x, y in polygon.exterior.coords)
    edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for index in range(1, len(coords)):
        start = coords[index - 1]
        end = coords[index]
        if start == end:
            continue
        edges.append((start, end))
    return tuple(edges)


def _edge_line_record(
    tri_index: int,
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[tuple[float, float, float], tuple[int, float, float, float, float, float]] | None:
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length = hypot(dx, dy)
    if length <= _LENGTH_EPSILON:
        return None
    ux = dx / length
    uy = dy / length
    if ux < -1e-12 or (abs(ux) <= 1e-12 and uy < 0.0):
        ux = -ux
        uy = -uy
    nx = -uy
    ny = ux
    offset = (nx * float(start[0])) + (ny * float(start[1]))
    t0 = (ux * float(start[0])) + (uy * float(start[1]))
    t1 = (ux * float(end[0])) + (uy * float(end[1]))
    return (
        (round(ux, 8), round(uy, 8), round(offset, 8)),
        (int(tri_index), min(t0, t1), max(t0, t1), ux, uy, offset),
    )


def _point_on_edge_line(ux: float, uy: float, offset: float, projection: float) -> tuple[float, float]:
    nx = -uy
    ny = ux
    return (
        float(ux) * float(projection) + float(nx) * float(offset),
        float(uy) * float(projection) + float(ny) * float(offset),
    )


def _constrained_delaunay_available() -> bool:
    import shapely

    return hasattr(shapely, "constrained_delaunay_triangles")


def _triangulate_constrained(geometry: BaseGeometry) -> tuple[Polygon, ...]:
    import shapely

    constrained_fn = getattr(shapely, "constrained_delaunay_triangles")
    triangles_out: list[Polygon] = []
    for polygon in _iter_polygons(geometry):
        tri_geom = constrained_fn(polygon)
        for candidate in _iter_polygons(tri_geom):
            clipped = candidate.intersection(polygon)
            for clipped_polygon in _iter_polygons(clipped):
                if float(clipped_polygon.area) <= _AREA_EPSILON:
                    continue
                triangles_out.append(clipped_polygon)
    triangles_out.sort(key=_geometry_sort_key)
    return tuple(triangles_out)


def _triangulate_fallback(geometry: BaseGeometry) -> tuple[Polygon, ...]:
    triangles_out: list[Polygon] = []
    for polygon in _iter_polygons(geometry):
        for candidate in triangulate(polygon):
            clipped = candidate.intersection(polygon)
            for clipped_polygon in _iter_polygons(clipped):
                if float(clipped_polygon.area) <= _AREA_EPSILON:
                    continue
                triangles_out.append(clipped_polygon)

    triangles_out.sort(key=_geometry_sort_key)
    deduped: list[Polygon] = []
    seen: set[bytes] = set()
    for polygon in triangles_out:
        key = polygon.wkb
        if key in seen:
            continue
        seen.add(key)
        deduped.append(polygon)
    return tuple(deduped)


def triangulate_surface_free_space(
    free_space: BaseGeometry,
    *,
    prefer_constrained: bool = True,
) -> tuple[str, tuple[Polygon, ...]]:
    if free_space.is_empty:
        return ("none", ())

    if prefer_constrained and _constrained_delaunay_available():
        triangles = _triangulate_constrained(free_space)
        return ("shapely_constrained_delaunay", triangles)

    triangles = _triangulate_fallback(free_space)
    return ("shapely_triangulate_fallback", triangles)


def _build_portals(
    surface_id: SurfaceId,
    triangles: tuple[Polygon, ...],
) -> tuple[SurfacePortal, ...]:
    if not triangles:
        return ()

    edge_records: dict[tuple[float, float, float], list[tuple[int, float, float, float, float, float]]] = {}
    for tri_index, triangle in enumerate(triangles):
        for start, end in _polygon_edges(triangle):
            record = _edge_line_record(tri_index, start, end)
            if record is None:
                continue
            line_key, edge_record = record
            edge_records.setdefault(line_key, []).append(edge_record)

    portals: list[SurfacePortal] = []
    seen_pairs: set[tuple[int, int, tuple[float, float, float], float, float]] = set()

    for edge_key, records in edge_records.items():
        if len(records) < 2:
            continue
        records.sort(key=lambda record: (float(record[1]), float(record[2]), int(record[0])))
        for left_index in range(len(records)):
            tri_index, start_projection, end_projection, ux, uy, offset = records[left_index]
            for right_index in range(left_index + 1, len(records)):
                other_index, other_start, other_end, _other_ux, _other_uy, _other_offset = records[right_index]
                if other_start >= end_projection - _LENGTH_EPSILON:
                    break
                if other_index == tri_index:
                    continue
                overlap_start = max(float(start_projection), float(other_start))
                overlap_end = min(float(end_projection), float(other_end))
                if overlap_end - overlap_start <= _LENGTH_EPSILON:
                    continue
                triangle_a = min(int(tri_index), other_index)
                triangle_b = max(int(tri_index), other_index)
                pair_key = (
                    triangle_a,
                    triangle_b,
                    edge_key,
                    round(overlap_start, 8),
                    round(overlap_end, 8),
                )
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                segment = LineString(
                    [
                        _point_on_edge_line(float(ux), float(uy), float(offset), overlap_start),
                        _point_on_edge_line(float(ux), float(uy), float(offset), overlap_end),
                    ]
                )
                length = float(segment.length)
                if length <= _LENGTH_EPSILON:
                    continue
                midpoint: Point = segment.interpolate(0.5, normalized=True)
                portals.append(
                    SurfacePortal(
                        portal_id=f"{surface_id}:portal:{triangle_a}:{triangle_b}",
                        surface_id=surface_id,
                        triangle_a=triangle_a,
                        triangle_b=triangle_b,
                        segment=segment,
                        midpoint_xy=(float(midpoint.x), float(midpoint.y)),
                        length=length,
                    )
                )

    portals.sort(
        key=lambda portal: (
            int(portal.triangle_a),
            int(portal.triangle_b),
            round(float(portal.midpoint_xy[0]), 6),
            round(float(portal.midpoint_xy[1]), 6),
        )
    )
    return tuple(portals)


def _build_triangle_neighbors(
    triangle_count: int,
    portals: tuple[SurfacePortal, ...],
) -> tuple[tuple[tuple[int, str], ...], ...]:
    neighbor_lists: list[list[tuple[int, str]]] = [[] for _ in range(triangle_count)]
    for portal in portals:
        neighbor_lists[portal.triangle_a].append((portal.triangle_b, portal.portal_id))
        neighbor_lists[portal.triangle_b].append((portal.triangle_a, portal.portal_id))
    return tuple(
        tuple(sorted(neighbors, key=lambda item: (int(item[0]), str(item[1]))))
        for neighbors in neighbor_lists
    )


def build_surface_cdt_mesh(
    surface_id: SurfaceId,
    free_space: BaseGeometry,
    *,
    prefer_constrained: bool = True,
) -> SurfaceCdtMesh:
    backend_name, triangles = triangulate_surface_free_space(
        free_space,
        prefer_constrained=prefer_constrained,
    )
    centroids = tuple((float(triangle.centroid.x), float(triangle.centroid.y)) for triangle in triangles)
    portals = _build_portals(surface_id, triangles)
    triangle_neighbors = _build_triangle_neighbors(len(triangles), portals)
    return SurfaceCdtMesh(
        surface_id=surface_id,
        triangulation_backend=backend_name,
        free_space=free_space,
        triangles=triangles,
        triangle_centroids=centroids,
        portals=portals,
        triangle_neighbors=triangle_neighbors,
    )


def portal_by_id(
    mesh: SurfaceCdtMesh,
    portal_id: str,
) -> Optional[SurfacePortal]:
    for portal in mesh.portals:
        if portal.portal_id == portal_id:
            return portal
    return None


def locate_triangles_for_point(
    mesh: SurfaceCdtMesh,
    x: float,
    y: float,
) -> tuple[int, ...]:
    point = Point(float(x), float(y))
    located: list[int] = []
    for tri_index, triangle in enumerate(mesh.triangles):
        if triangle.covers(point):
            located.append(tri_index)
    return tuple(located)


__all__ = [
    "SurfaceCdtMesh",
    "SurfacePortal",
    "build_surface_cdt_mesh",
    "locate_triangles_for_point",
    "portal_by_id",
    "triangulate_surface_free_space",
]
