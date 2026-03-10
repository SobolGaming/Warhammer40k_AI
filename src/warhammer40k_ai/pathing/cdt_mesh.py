from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from shapely import STRtree
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Point, Polygon
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


def _extract_line_segment(geometry: BaseGeometry) -> Optional[LineString]:
    if isinstance(geometry, LineString):
        if float(geometry.length) > _LENGTH_EPSILON:
            return geometry
        return None
    if isinstance(geometry, MultiLineString):
        segments = sorted(
            (
                line
                for line in geometry.geoms
                if isinstance(line, LineString) and float(line.length) > _LENGTH_EPSILON
            ),
            key=lambda line: (-float(line.length), _geometry_sort_key(line)),
        )
        if segments:
            return segments[0]
        return None
    if isinstance(geometry, GeometryCollection):
        for geom in geometry.geoms:
            segment = _extract_line_segment(geom)
            if segment is not None:
                return segment
    return None


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

    tree = STRtree(triangles)
    portals: list[SurfacePortal] = []

    for tri_index, triangle in enumerate(triangles):
        candidate_indices = tree.query(triangle)
        if candidate_indices is None:
            continue
        for other_index in tuple(int(index) for index in candidate_indices):
            if other_index <= tri_index:
                continue
            other_triangle = triangles[other_index]
            if not triangle.touches(other_triangle):
                continue

            shared_boundary = triangle.boundary.intersection(other_triangle.boundary)
            segment = _extract_line_segment(shared_boundary)
            if segment is None or float(segment.length) <= _LENGTH_EPSILON:
                continue

            midpoint: Point = segment.interpolate(0.5, normalized=True)
            portals.append(
                SurfacePortal(
                    portal_id=f"{surface_id}:portal:{tri_index}:{other_index}",
                    surface_id=surface_id,
                    triangle_a=tri_index,
                    triangle_b=other_index,
                    segment=segment,
                    midpoint_xy=(float(midpoint.x), float(midpoint.y)),
                    length=float(segment.length),
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
