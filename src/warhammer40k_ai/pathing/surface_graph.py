from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from math import atan2, hypot
from typing import Mapping, Optional

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .cache import (
    StaticMeshCacheEntry,
    build_static_mesh_cache_key,
    clearance_bucket_for_radius,
    get_static_mesh_cache,
)
from .cdt_mesh import SurfaceCdtMesh, build_surface_cdt_mesh, locate_triangles_for_point
from .corridor import build_corridor
from .dynamic_overlay import DynamicOverlay
from .se2_refine import Se2RefineRequest, evaluate_se2_refine_trigger, refine_corridor_se2
from .surfaces import GROUND_LAYER_KIND, SupportSurface, resolve_support_surface_at_position
from .types import ConnectorId, MovementProfile, SurfaceId
from .world_snapshot import WorldSnapshot


@dataclass(frozen=True, eq=False)
class SurfaceConnector:
    connector_id: ConnectorId
    source_surface_id: SurfaceId
    target_surface_id: SurfaceId
    kind: str
    anchor_geometry: BaseGeometry
    anchor_xy: tuple[float, float]
    distance_cost: float
    requires_support_validation_source: bool
    requires_support_validation_target: bool
    allowed_for_profile: bool
    dynamic_blocked: bool
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, eq=False)
class SurfaceGraphStatic:
    surface_meshes: tuple[tuple[SurfaceId, SurfaceCdtMesh], ...]
    connectors: tuple[SurfaceConnector, ...]


@dataclass(frozen=True, eq=False)
class SurfaceGraphPathResult:
    success: bool
    waypoints: tuple[tuple[float, float, float], ...]
    distance_cost: float
    portal_path: tuple[str, ...]
    connector_path: tuple[ConnectorId, ...]
    surface_path: tuple[SurfaceId, ...]
    triangulation_backends: Mapping[SurfaceId, str]
    used_exact_refiner: bool = False
    failure_reason: Optional[str] = None
    debug_artifacts: Mapping[str, object] = field(default_factory=dict)


def _normalize_geometry(geometry: BaseGeometry) -> BaseGeometry:
    if geometry.is_empty:
        return geometry
    if geometry.is_valid:
        return geometry
    repaired = geometry.buffer(0.0)
    if repaired.is_valid:
        return repaired
    return geometry


def _ordered_support_surfaces(world_snapshot: WorldSnapshot) -> tuple[SupportSurface, ...]:
    return tuple(
        sorted(
            world_snapshot.support_surfaces,
            key=lambda surface: (
                float(surface.surface_z),
                int(surface.terrain_index),
                -1 if surface.floor_index is None else int(surface.floor_index),
                str(surface.surface_id),
            ),
        )
    )


def _surface_dynamic_cutouts(
    surface: SupportSurface,
    movement_profile: MovementProfile,
    dynamic_overlay: Optional[DynamicOverlay],
) -> tuple[BaseGeometry, ...]:
    if dynamic_overlay is None:
        return ()

    cutouts: list[BaseGeometry] = []
    z_tolerance = 1.0
    for blocker in dynamic_overlay.blockers:
        if abs(float(blocker.z_bottom) - float(surface.surface_z)) > z_tolerance:
            continue
        if blocker.is_enemy and movement_profile.can_move_through_enemy_models:
            continue
        if blocker.is_friendly and movement_profile.can_move_through_friendly_models:
            continue
        cutouts.append(blocker.footprint)
    return tuple(cutouts)


def build_surface_free_space(
    surface: SupportSurface,
    world_snapshot: WorldSnapshot,
    movement_profile: MovementProfile,
    *,
    base_radius: float,
    footprint_class: str = "disk",
    dynamic_overlay: Optional[DynamicOverlay] = None,
) -> BaseGeometry:
    free_space = _normalize_geometry(surface.polygon.intersection(world_snapshot.board_boundary))
    if free_space.is_empty:
        return free_space

    static_cutouts: list[BaseGeometry] = []
    if surface.layer_kind == GROUND_LAYER_KIND:
        static_cutouts.extend(world_snapshot.ground_transit_obstacles)
    static_cutouts.extend(_surface_dynamic_cutouts(surface, movement_profile, dynamic_overlay))

    if static_cutouts:
        cutout_union = unary_union(static_cutouts)
        free_space = _normalize_geometry(free_space.difference(cutout_union))
    if free_space.is_empty:
        return free_space

    if str(footprint_class).strip().lower() == "disk" and float(base_radius) > 0.0:
        free_space = _normalize_geometry(free_space.buffer(-float(base_radius), quad_segs=16))
    return free_space


def _connector_allowed_for_profile(
    movement_profile: MovementProfile,
    kind: str,
    source_surface: SupportSurface,
    target_surface: SupportSurface,
) -> bool:
    if kind == "fly_transition":
        return bool(movement_profile.terrain_transition_rules.get("is_fly_move", False))
    if kind == "breach_transition":
        return bool(movement_profile.can_breach_ruins_walls)
    if float(target_surface.surface_z) > 0.0 and not bool(movement_profile.can_end_on_upper_surfaces):
        return False
    return True


def _connector_distance_cost(
    movement_profile: MovementProfile,
    source_surface: SupportSurface,
    target_surface: SupportSurface,
) -> float:
    z_delta = abs(float(target_surface.surface_z) - float(source_surface.surface_z))
    if movement_profile.can_ignore_vertical_distance:
        return 0.0
    return z_delta


def _connector_dynamic_blocked(
    connector: SurfaceConnector,
    source_surface: SupportSurface,
    target_surface: SupportSurface,
    dynamic_overlay: Optional[DynamicOverlay],
    movement_profile: MovementProfile,
) -> bool:
    if dynamic_overlay is None:
        return False

    anchor = Point(float(connector.anchor_xy[0]), float(connector.anchor_xy[1]))
    z_tolerance = 1.0
    for blocker in dynamic_overlay.blockers:
        if blocker.is_enemy and movement_profile.can_move_through_enemy_models:
            continue
        if blocker.is_friendly and movement_profile.can_move_through_friendly_models:
            continue
        source_match = abs(float(blocker.z_bottom) - float(source_surface.surface_z)) <= z_tolerance
        target_match = abs(float(blocker.z_bottom) - float(target_surface.surface_z)) <= z_tolerance
        if not (source_match or target_match):
            continue
        if blocker.footprint.covers(anchor):
            return True
    return False


def _surface_pair_intersection(
    source_surface: SupportSurface,
    target_surface: SupportSurface,
) -> Optional[BaseGeometry]:
    intersection = source_surface.polygon.intersection(target_surface.polygon)
    if intersection.is_empty:
        return None
    return intersection


def _connector_kind_candidates(
    movement_profile: MovementProfile,
    source_surface: SupportSurface,
    target_surface: SupportSurface,
) -> tuple[str, ...]:
    source_is_ground = source_surface.layer_kind == GROUND_LAYER_KIND
    target_is_ground = target_surface.layer_kind == GROUND_LAYER_KIND

    if source_is_ground != target_is_ground:
        kinds = ["ground_to_support" if source_is_ground else "support_to_ground"]
        support_surface = target_surface if source_is_ground else source_surface
        if support_surface.terrain_type == "RUINS" and movement_profile.can_breach_ruins_walls:
            kinds.append("breach_transition")
        if bool(movement_profile.terrain_transition_rules.get("is_fly_move", False)):
            kinds.append("fly_transition")
        return tuple(kinds)
    if source_surface.layer_kind != GROUND_LAYER_KIND and target_surface.layer_kind != GROUND_LAYER_KIND:
        if (
            source_surface.terrain_type == "RUINS"
            and target_surface.terrain_type == "RUINS"
            and source_surface.terrain_index == target_surface.terrain_index
        ):
            kinds = ["floor_to_floor"]
        else:
            kinds = []
        if bool(movement_profile.terrain_transition_rules.get("is_fly_move", False)):
            kinds.append("fly_transition")
        return tuple(kinds)
    if bool(movement_profile.terrain_transition_rules.get("is_fly_move", False)):
        return ("fly_transition",)
    return ()


def build_surface_connectors(
    support_surfaces: tuple[SupportSurface, ...],
    movement_profile: MovementProfile,
    *,
    dynamic_overlay: Optional[DynamicOverlay] = None,
) -> tuple[SurfaceConnector, ...]:
    connectors: list[SurfaceConnector] = []

    for source_index, source_surface in enumerate(support_surfaces):
        for target_index, target_surface in enumerate(support_surfaces):
            if source_index == target_index:
                continue

            intersection = _surface_pair_intersection(source_surface, target_surface)
            if intersection is None:
                continue

            kinds = _connector_kind_candidates(movement_profile, source_surface, target_surface)
            if not kinds:
                continue

            anchor_point = intersection.representative_point()
            anchor_xy = (float(anchor_point.x), float(anchor_point.y))
            z_delta = abs(float(source_surface.surface_z) - float(target_surface.surface_z))
            for kind in kinds:
                allowed = _connector_allowed_for_profile(
                    movement_profile,
                    kind,
                    source_surface,
                    target_surface,
                )
                connector_id = (
                    f"{source_surface.surface_id}->{target_surface.surface_id}:"
                    f"{kind}:{source_index:03d}:{target_index:03d}"
                )
                connector = SurfaceConnector(
                    connector_id=connector_id,
                    source_surface_id=source_surface.surface_id,
                    target_surface_id=target_surface.surface_id,
                    kind=kind,
                    anchor_geometry=intersection,
                    anchor_xy=anchor_xy,
                    distance_cost=_connector_distance_cost(movement_profile, source_surface, target_surface),
                    requires_support_validation_source=source_surface.layer_kind != GROUND_LAYER_KIND,
                    requires_support_validation_target=target_surface.layer_kind != GROUND_LAYER_KIND,
                    allowed_for_profile=allowed,
                    dynamic_blocked=False,
                    metadata={
                        "source_surface_z": float(source_surface.surface_z),
                        "target_surface_z": float(target_surface.surface_z),
                        "z_delta": float(z_delta),
                        "intersection_area": float(getattr(intersection, "area", 0.0)),
                        "intersection_length": float(getattr(intersection, "length", 0.0)),
                    },
                )
                blocked = _connector_dynamic_blocked(
                    connector,
                    source_surface=source_surface,
                    target_surface=target_surface,
                    dynamic_overlay=dynamic_overlay,
                    movement_profile=movement_profile,
                )
                connectors.append(
                    SurfaceConnector(
                        connector_id=connector.connector_id,
                        source_surface_id=connector.source_surface_id,
                        target_surface_id=connector.target_surface_id,
                        kind=connector.kind,
                        anchor_geometry=connector.anchor_geometry,
                        anchor_xy=connector.anchor_xy,
                        distance_cost=connector.distance_cost,
                        requires_support_validation_source=connector.requires_support_validation_source,
                        requires_support_validation_target=connector.requires_support_validation_target,
                        allowed_for_profile=connector.allowed_for_profile,
                        dynamic_blocked=blocked,
                        metadata=connector.metadata,
                    )
                )

    connectors.sort(
        key=lambda connector: (
            str(connector.source_surface_id),
            str(connector.target_surface_id),
            str(connector.kind),
            str(connector.connector_id),
        )
    )
    return tuple(connectors)


def _mesh_pairs_to_dict(
    mesh_pairs: tuple[tuple[SurfaceId, SurfaceCdtMesh], ...],
) -> dict[SurfaceId, SurfaceCdtMesh]:
    return {surface_id: mesh for surface_id, mesh in mesh_pairs}


def build_surface_graph_static(
    world_snapshot: WorldSnapshot,
    movement_profile: MovementProfile,
    *,
    base_radius: float,
    footprint_class: str = "disk",
    prefer_constrained: bool = True,
    use_cache: bool = True,
) -> SurfaceGraphStatic:
    cache_key = build_static_mesh_cache_key(
        world_snapshot,
        footprint_class=footprint_class,
        base_clearance_bucket=clearance_bucket_for_radius(base_radius),
    )
    cache = get_static_mesh_cache()
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return SurfaceGraphStatic(
                surface_meshes=tuple(cached.surface_meshes),
                connectors=tuple(connector for connector in cached.connectors if isinstance(connector, SurfaceConnector)),
            )

    support_surfaces = _ordered_support_surfaces(world_snapshot)
    mesh_pairs: list[tuple[SurfaceId, SurfaceCdtMesh]] = []
    for surface in support_surfaces:
        free_space = build_surface_free_space(
            surface,
            world_snapshot,
            movement_profile,
            base_radius=base_radius,
            footprint_class=footprint_class,
            dynamic_overlay=None,
        )
        mesh = build_surface_cdt_mesh(
            surface.surface_id,
            free_space,
            prefer_constrained=prefer_constrained,
        )
        mesh_pairs.append((surface.surface_id, mesh))

    mesh_pairs.sort(key=lambda item: str(item[0]))
    connectors = build_surface_connectors(
        support_surfaces=support_surfaces,
        movement_profile=movement_profile,
        dynamic_overlay=None,
    )
    graph_static = SurfaceGraphStatic(
        surface_meshes=tuple(mesh_pairs),
        connectors=connectors,
    )
    if use_cache:
        cache.put(
            cache_key,
            StaticMeshCacheEntry(
                surface_meshes=graph_static.surface_meshes,
                connectors=tuple(graph_static.connectors),
            ),
        )
    return graph_static


def build_surface_graph_for_query(
    world_snapshot: WorldSnapshot,
    movement_profile: MovementProfile,
    *,
    base_radius: float,
    footprint_class: str = "disk",
    prefer_constrained: bool = True,
    use_cache: bool = True,
    dynamic_overlay: Optional[DynamicOverlay] = None,
) -> SurfaceGraphStatic:
    graph_static = build_surface_graph_static(
        world_snapshot,
        movement_profile,
        base_radius=base_radius,
        footprint_class=footprint_class,
        prefer_constrained=prefer_constrained,
        use_cache=use_cache,
    )
    static_meshes = _mesh_pairs_to_dict(graph_static.surface_meshes)
    query_mesh_pairs: list[tuple[SurfaceId, SurfaceCdtMesh]] = []
    for surface in _ordered_support_surfaces(world_snapshot):
        static_mesh = static_meshes.get(surface.surface_id)
        if static_mesh is None:
            continue
        if dynamic_overlay is None:
            query_mesh_pairs.append((surface.surface_id, static_mesh))
            continue
        dynamic_cutouts = _surface_dynamic_cutouts(surface, movement_profile, dynamic_overlay)
        if not dynamic_cutouts:
            query_mesh_pairs.append((surface.surface_id, static_mesh))
            continue

        free_space = build_surface_free_space(
            surface,
            world_snapshot,
            movement_profile,
            base_radius=base_radius,
            footprint_class=footprint_class,
            dynamic_overlay=dynamic_overlay,
        )
        mesh = build_surface_cdt_mesh(
            surface.surface_id,
            free_space,
            prefer_constrained=prefer_constrained,
        )
        query_mesh_pairs.append((surface.surface_id, mesh))

    surfaces_by_id = {surface.surface_id: surface for surface in world_snapshot.support_surfaces}
    connectors = []
    for connector in graph_static.connectors:
        source_surface = surfaces_by_id.get(connector.source_surface_id)
        target_surface = surfaces_by_id.get(connector.target_surface_id)
        if source_surface is None or target_surface is None:
            continue
        blocked = _connector_dynamic_blocked(
            connector,
            source_surface=source_surface,
            target_surface=target_surface,
            dynamic_overlay=dynamic_overlay,
            movement_profile=movement_profile,
        )
        connectors.append(
            SurfaceConnector(
                connector_id=connector.connector_id,
                source_surface_id=connector.source_surface_id,
                target_surface_id=connector.target_surface_id,
                kind=connector.kind,
                anchor_geometry=connector.anchor_geometry,
                anchor_xy=connector.anchor_xy,
                distance_cost=connector.distance_cost,
                requires_support_validation_source=connector.requires_support_validation_source,
                requires_support_validation_target=connector.requires_support_validation_target,
                allowed_for_profile=connector.allowed_for_profile,
                dynamic_blocked=blocked,
                metadata=connector.metadata,
            )
        )
    return SurfaceGraphStatic(
        surface_meshes=tuple(sorted(query_mesh_pairs, key=lambda item: str(item[0]))),
        connectors=tuple(connectors),
    )


def _node_distance(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
) -> float:
    return hypot(float(point_b[0]) - float(point_a[0]), float(point_b[1]) - float(point_a[1]))


def _connector_map_by_source(
    connectors: tuple[SurfaceConnector, ...],
) -> dict[SurfaceId, tuple[SurfaceConnector, ...]]:
    per_source: dict[SurfaceId, list[SurfaceConnector]] = {}
    for connector in connectors:
        per_source.setdefault(connector.source_surface_id, []).append(connector)
    return {
        source_id: tuple(
            sorted(connector_list, key=lambda connector: (str(connector.target_surface_id), str(connector.connector_id)))
        )
        for source_id, connector_list in per_source.items()
    }


def _blocked_triangles_by_overlay(
    surface_meshes: dict[SurfaceId, SurfaceCdtMesh],
    surfaces_by_id: dict[SurfaceId, SupportSurface],
    movement_profile: MovementProfile,
    dynamic_overlay: Optional[DynamicOverlay],
) -> dict[SurfaceId, frozenset[int]]:
    if dynamic_overlay is None:
        return {}

    z_tolerance = 1.0
    blocked: dict[SurfaceId, set[int]] = {surface_id: set() for surface_id in surface_meshes}
    for surface_id, mesh in surface_meshes.items():
        surface = surfaces_by_id.get(surface_id)
        if surface is None:
            continue
        applicable_blockers = []
        for blocker in dynamic_overlay.blockers:
            if blocker.is_enemy and movement_profile.can_move_through_enemy_models:
                continue
            if blocker.is_friendly and movement_profile.can_move_through_friendly_models:
                continue
            if abs(float(blocker.z_bottom) - float(surface.surface_z)) > z_tolerance:
                continue
            applicable_blockers.append(blocker)

        if not applicable_blockers:
            continue
        for triangle_index, triangle in enumerate(mesh.triangles):
            centroid = triangle.centroid
            for blocker in applicable_blockers:
                if blocker.footprint.covers(centroid):
                    blocked[surface_id].add(triangle_index)
                    break

    return {surface_id: frozenset(indices) for surface_id, indices in blocked.items() if indices}


def _connector_target_triangles(
    surface_meshes: dict[SurfaceId, SurfaceCdtMesh],
    connector: SurfaceConnector,
) -> tuple[int, ...]:
    target_mesh = surface_meshes.get(connector.target_surface_id)
    if target_mesh is None:
        return ()
    x, y = connector.anchor_xy
    return locate_triangles_for_point(target_mesh, x, y)


def _reconstruct_node_path(
    end_node: tuple[SurfaceId, int],
    came_from: Mapping[tuple[SurfaceId, int], tuple[tuple[SurfaceId, int], str, str]],
) -> tuple[tuple[tuple[SurfaceId, int], ...], tuple[tuple[str, str], ...]]:
    current = end_node
    node_path: list[tuple[SurfaceId, int]] = [current]
    transitions: list[tuple[str, str]] = []
    while current in came_from:
        prev, transition_kind, transition_id = came_from[current]
        transitions.append((transition_kind, transition_id))
        current = prev
        node_path.append(current)
    node_path.reverse()
    transitions.reverse()
    return tuple(node_path), tuple(transitions)


def _a_star_surface_triangles_candidates(
    *,
    start_surface_id: SurfaceId,
    start_triangles: tuple[int, ...],
    goal_surface_id: SurfaceId,
    goal_triangles: tuple[int, ...],
    goal_xy: tuple[float, float],
    goal_surface_z: float,
    surface_z_by_id: Mapping[SurfaceId, float],
    surface_meshes: dict[SurfaceId, SurfaceCdtMesh],
    connectors_by_source: dict[SurfaceId, tuple[SurfaceConnector, ...]],
    movement_profile: MovementProfile,
    blocked_triangles: Mapping[SurfaceId, frozenset[int]],
    max_paths: int = 1,
) -> tuple[tuple[tuple[tuple[SurfaceId, int], ...], tuple[tuple[str, str], ...]], ...]:
    goal_nodes = {(goal_surface_id, triangle) for triangle in goal_triangles}
    if not goal_nodes:
        return ()

    def heuristic(node: tuple[SurfaceId, int]) -> float:
        surface_id, triangle_index = node
        mesh = surface_meshes[surface_id]
        centroid_xy = mesh.triangle_centroids[triangle_index]
        horizontal = _node_distance(centroid_xy, goal_xy)
        if movement_profile.can_ignore_vertical_distance:
            return horizontal
        surface_z = float(surface_z_by_id.get(surface_id, 0.0))
        return horizontal + abs(surface_z - float(goal_surface_z))

    open_heap: list[tuple[float, int, tuple[SurfaceId, int]]] = []
    insertion_counter = 0
    g_score: dict[tuple[SurfaceId, int], float] = {}
    came_from: dict[tuple[SurfaceId, int], tuple[tuple[SurfaceId, int], str, str]] = {}

    for triangle_index in start_triangles:
        if int(triangle_index) in blocked_triangles.get(start_surface_id, frozenset()):
            continue
        node = (start_surface_id, triangle_index)
        g_score[node] = 0.0
        heapq.heappush(open_heap, (heuristic(node), insertion_counter, node))
        insertion_counter += 1

    if not open_heap:
        return ()

    path_candidates: list[tuple[tuple[tuple[SurfaceId, int], ...], tuple[tuple[str, str], ...]]] = []
    candidate_keys: set[tuple[tuple[SurfaceId, int], ...]] = set()
    visited: set[tuple[SurfaceId, int]] = set()
    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current in visited:
            continue
        if current in goal_nodes:
            reconstructed = _reconstruct_node_path(current, came_from)
            path_key = reconstructed[0]
            if path_key not in candidate_keys:
                candidate_keys.add(path_key)
                path_candidates.append(reconstructed)
            visited.add(current)
            if len(path_candidates) >= max(1, int(max_paths)):
                break
            continue
        visited.add(current)

        current_surface_id, current_triangle_index = current
        current_mesh = surface_meshes[current_surface_id]
        current_centroid = current_mesh.triangle_centroids[current_triangle_index]

        for neighbor_index, portal_id in current_mesh.triangle_neighbors[current_triangle_index]:
            if int(neighbor_index) in blocked_triangles.get(current_surface_id, frozenset()):
                continue
            neighbor = (current_surface_id, int(neighbor_index))
            move_cost = _node_distance(
                current_centroid,
                current_mesh.triangle_centroids[int(neighbor_index)],
            )
            tentative_g = g_score[current] + move_cost
            if tentative_g >= g_score.get(neighbor, float("inf")):
                continue
            g_score[neighbor] = tentative_g
            came_from[neighbor] = (current, "portal", str(portal_id))
            heapq.heappush(open_heap, (tentative_g + heuristic(neighbor), insertion_counter, neighbor))
            insertion_counter += 1

        for connector in connectors_by_source.get(current_surface_id, ()):
            if not connector.allowed_for_profile or connector.dynamic_blocked:
                continue
            if connector.kind == "fly_transition" and not bool(movement_profile.terrain_transition_rules.get("is_fly_move", False)):
                continue
            if connector.kind == "breach_transition" and not movement_profile.can_breach_ruins_walls:
                continue

            triangle = current_mesh.triangles[current_triangle_index]
            anchor_point = Point(float(connector.anchor_xy[0]), float(connector.anchor_xy[1]))
            if not triangle.covers(anchor_point):
                continue

            for target_triangle_index in _connector_target_triangles(surface_meshes, connector):
                if int(target_triangle_index) in blocked_triangles.get(connector.target_surface_id, frozenset()):
                    continue
                neighbor = (connector.target_surface_id, int(target_triangle_index))
                tentative_g = g_score[current] + float(connector.distance_cost)
                if tentative_g >= g_score.get(neighbor, float("inf")):
                    continue
                g_score[neighbor] = tentative_g
                came_from[neighbor] = (current, "connector", str(connector.connector_id))
                heapq.heappush(open_heap, (tentative_g + heuristic(neighbor), insertion_counter, neighbor))
                insertion_counter += 1

    return tuple(path_candidates)


def _a_star_surface_triangles(
    *,
    start_surface_id: SurfaceId,
    start_triangles: tuple[int, ...],
    goal_surface_id: SurfaceId,
    goal_triangles: tuple[int, ...],
    goal_xy: tuple[float, float],
    goal_surface_z: float,
    surface_z_by_id: Mapping[SurfaceId, float],
    surface_meshes: dict[SurfaceId, SurfaceCdtMesh],
    connectors_by_source: dict[SurfaceId, tuple[SurfaceConnector, ...]],
    movement_profile: MovementProfile,
    blocked_triangles: Mapping[SurfaceId, frozenset[int]],
) -> tuple[
    tuple[tuple[SurfaceId, int], ...],
    tuple[tuple[str, str], ...],
]:
    candidates = _a_star_surface_triangles_candidates(
        start_surface_id=start_surface_id,
        start_triangles=start_triangles,
        goal_surface_id=goal_surface_id,
        goal_triangles=goal_triangles,
        goal_xy=goal_xy,
        goal_surface_z=goal_surface_z,
        surface_z_by_id=surface_z_by_id,
        surface_meshes=surface_meshes,
        connectors_by_source=connectors_by_source,
        movement_profile=movement_profile,
        blocked_triangles=blocked_triangles,
        max_paths=1,
    )
    if not candidates:
        return (), ()
    return candidates[0]


def _group_surface_segments(
    node_path: tuple[tuple[SurfaceId, int], ...],
    transitions: tuple[tuple[str, str], ...],
) -> tuple[tuple[SurfaceId, tuple[int, ...], Optional[str]], ...]:
    if not node_path:
        return ()
    groups: list[tuple[SurfaceId, list[int], Optional[str]]] = [
        (node_path[0][0], [node_path[0][1]], None)
    ]
    for index, transition in enumerate(transitions):
        kind, transition_id = transition
        current_surface_id, _ = node_path[index]
        next_surface_id, next_triangle = node_path[index + 1]
        if kind == "portal" and current_surface_id == next_surface_id:
            groups[-1][1].append(next_triangle)  # type: ignore[index]
            continue
        groups[-1] = (groups[-1][0], groups[-1][1], transition_id)
        groups.append((next_surface_id, [next_triangle], None))
    return tuple((surface_id, tuple(triangle_indices), connector_id) for surface_id, triangle_indices, connector_id in groups)


def _surface_by_id(world_snapshot: WorldSnapshot) -> dict[SurfaceId, SupportSurface]:
    return {surface.surface_id: surface for surface in world_snapshot.support_surfaces}


def _connector_by_id(connectors: tuple[SurfaceConnector, ...]) -> dict[ConnectorId, SurfaceConnector]:
    return {connector.connector_id: connector for connector in connectors}


def _waypoint_distance_cost(
    points: tuple[tuple[float, float, float], ...],
    *,
    ignore_vertical: bool,
) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for index in range(1, len(points)):
        dx = float(points[index][0]) - float(points[index - 1][0])
        dy = float(points[index][1]) - float(points[index - 1][1])
        if ignore_vertical:
            total += hypot(dx, dy)
            continue
        dz = float(points[index][2]) - float(points[index - 1][2])
        total += (dx * dx + dy * dy + dz * dz) ** 0.5
    return float(total)


def _dedupe_waypoints(
    points: list[tuple[float, float, float]],
) -> tuple[tuple[float, float, float], ...]:
    deduped: list[tuple[float, float, float]] = []
    for point in points:
        x, y, z = (float(point[0]), float(point[1]), float(point[2]))
        if deduped:
            prev_x, prev_y, prev_z = deduped[-1]
            if abs(prev_x - x) <= 1e-9 and abs(prev_y - y) <= 1e-9 and abs(prev_z - z) <= 1e-9:
                continue
        deduped.append((x, y, z))
    return tuple(deduped)


def _pivot_cost_once_for_refiner(
    movement_profile: MovementProfile,
    model_base: object,
) -> float:
    if movement_profile.pivot_cost_mode == "none" or model_base is None:
        return 0.0

    terrain_rules = movement_profile.terrain_transition_rules
    is_aircraft = bool(terrain_rules.get("is_aircraft_unit", False))
    if is_aircraft:
        return 0.0

    has_circular_base = bool(getattr(model_base, "has_circular_base", False))
    is_vehicle = bool(terrain_rules.get("is_vehicle_unit", False))
    is_monster = bool(terrain_rules.get("is_monster_unit", False))

    radius = getattr(model_base, "radius", (0.0, 0.0))
    if isinstance(radius, tuple):
        base_size = max(float(radius[0]), float(radius[1]))
    else:
        base_size = float(radius)
    has_flying_base = bool(getattr(model_base, "is_flying_base", False))
    pivot_threshold = 32.0 / 25.4 / 2.0

    if is_vehicle and has_circular_base:
        if base_size > pivot_threshold and has_flying_base:
            return 2.0
        return 0.0
    if (is_vehicle or is_monster) and not has_circular_base:
        return 2.0
    if not has_circular_base:
        return 1.0
    return 0.0


def plan_surface_graph_path(
    world_snapshot: WorldSnapshot,
    movement_profile: MovementProfile,
    *,
    start: tuple[float, float, float],
    goal: tuple[float, float, float],
    base_radius: float,
    footprint_class: str = "disk",
    prefer_constrained: bool = True,
    dynamic_overlay: Optional[DynamicOverlay] = None,
    use_cache: bool = True,
    model_base: object = None,
    start_facing: Optional[float] = None,
    goal_facing: Optional[float] = None,
    enable_exact_refine: bool = True,
    exact_refine_max_paths: int = 3,
    exact_refine_safety_margin: float = 0.1,
) -> SurfaceGraphPathResult:
    graph = build_surface_graph_for_query(
        world_snapshot,
        movement_profile,
        base_radius=base_radius,
        footprint_class=footprint_class,
        prefer_constrained=prefer_constrained,
        use_cache=use_cache,
        dynamic_overlay=dynamic_overlay,
    )
    surface_meshes = _mesh_pairs_to_dict(graph.surface_meshes)
    surfaces_by_id = _surface_by_id(world_snapshot)
    connectors_by_source = _connector_map_by_source(graph.connectors)
    triangulation_backends = {surface_id: mesh.triangulation_backend for surface_id, mesh in graph.surface_meshes}

    start_surface = resolve_support_surface_at_position(
        world_snapshot.support_surfaces,
        x=float(start[0]),
        y=float(start[1]),
        z=float(start[2]),
        max_vertical_gap=1.0,
    )
    goal_surface = resolve_support_surface_at_position(
        world_snapshot.support_surfaces,
        x=float(goal[0]),
        y=float(goal[1]),
        z=float(goal[2]),
        max_vertical_gap=1.0,
    )
    if start_surface is None:
        return SurfaceGraphPathResult(
            success=False,
            waypoints=(),
            distance_cost=0.0,
            portal_path=(),
            connector_path=(),
            surface_path=(),
            triangulation_backends=triangulation_backends,
            failure_reason="Start position is not on a valid support surface",
        )
    if goal_surface is None:
        return SurfaceGraphPathResult(
            success=False,
            waypoints=(),
            distance_cost=0.0,
            portal_path=(),
            connector_path=(),
            surface_path=(),
            triangulation_backends=triangulation_backends,
            failure_reason="Goal position is not on a valid support surface",
        )

    start_mesh = surface_meshes.get(start_surface.surface_id)
    goal_mesh = surface_meshes.get(goal_surface.surface_id)
    if start_mesh is None or goal_mesh is None:
        return SurfaceGraphPathResult(
            success=False,
            waypoints=(),
            distance_cost=0.0,
            portal_path=(),
            connector_path=(),
            surface_path=(),
            triangulation_backends=triangulation_backends,
            failure_reason="Missing mesh for start or goal surface",
        )

    start_triangles = locate_triangles_for_point(start_mesh, float(start[0]), float(start[1]))
    goal_triangles = locate_triangles_for_point(goal_mesh, float(goal[0]), float(goal[1]))
    blocked_triangles = _blocked_triangles_by_overlay(
        surface_meshes=surface_meshes,
        surfaces_by_id=surfaces_by_id,
        movement_profile=movement_profile,
        dynamic_overlay=dynamic_overlay,
    )
    goal_triangles = tuple(
        triangle for triangle in goal_triangles if int(triangle) not in blocked_triangles.get(goal_surface.surface_id, frozenset())
    )
    if not start_triangles:
        return SurfaceGraphPathResult(
            success=False,
            waypoints=(),
            distance_cost=0.0,
            portal_path=(),
            connector_path=(),
            surface_path=(),
            triangulation_backends=triangulation_backends,
            failure_reason="Start is outside traversable free space after clearance erosion",
        )
    if not goal_triangles:
        return SurfaceGraphPathResult(
            success=False,
            waypoints=(),
            distance_cost=0.0,
            portal_path=(),
            connector_path=(),
            surface_path=(),
            triangulation_backends=triangulation_backends,
            failure_reason="Goal is outside traversable free space after clearance erosion",
        )

    max_candidate_paths = 1
    if enable_exact_refine and model_base is not None:
        max_candidate_paths = max(1, int(exact_refine_max_paths))

    path_candidates = _a_star_surface_triangles_candidates(
        start_surface_id=start_surface.surface_id,
        start_triangles=start_triangles,
        goal_surface_id=goal_surface.surface_id,
        goal_triangles=goal_triangles,
        goal_xy=(float(goal[0]), float(goal[1])),
        goal_surface_z=float(goal_surface.surface_z),
        surface_z_by_id={surface.surface_id: float(surface.surface_z) for surface in world_snapshot.support_surfaces},
        surface_meshes=surface_meshes,
        connectors_by_source=connectors_by_source,
        movement_profile=movement_profile,
        blocked_triangles=blocked_triangles,
        max_paths=max_candidate_paths,
    )
    if not path_candidates:
        return SurfaceGraphPathResult(
            success=False,
            waypoints=(),
            distance_cost=0.0,
            portal_path=(),
            connector_path=(),
            surface_path=(),
            triangulation_backends=triangulation_backends,
            failure_reason="No portal/connector route found",
        )

    connector_lookup = _connector_by_id(graph.connectors)
    candidate_failures: list[dict[str, object]] = []
    path_candidates = tuple(path_candidates)

    for candidate_rank, (node_path, transitions) in enumerate(path_candidates):
        grouped = _group_surface_segments(node_path, transitions)

        waypoints: list[tuple[float, float, float]] = [(float(start[0]), float(start[1]), float(start[2]))]
        portal_path: list[str] = []
        connector_path: list[ConnectorId] = []
        current_start_xy = (float(start[0]), float(start[1]))
        current_facing_value = float(start_facing) if start_facing is not None else None
        used_exact_refiner = False
        segment_refinements: list[dict[str, object]] = []
        candidate_failure_reason: Optional[str] = None

        for segment_index, (surface_id, triangle_path, connector_out_id) in enumerate(grouped):
            mesh = surface_meshes[surface_id]
            surface = surfaces_by_id[surface_id]

            if connector_out_id is not None:
                connector = connector_lookup.get(connector_out_id)
                if connector is None:
                    candidate_failure_reason = f"Connector '{connector_out_id}' missing from graph"
                    break
                end_xy = (float(connector.anchor_xy[0]), float(connector.anchor_xy[1]))
            else:
                end_xy = (float(goal[0]), float(goal[1]))

            corridor = build_corridor(
                mesh,
                triangle_path,
                start_xy=current_start_xy,
                goal_xy=end_xy,
            )
            portal_path.extend(corridor.portal_ids)

            segment_goal_facing = None
            if connector_out_id is None and segment_index == len(grouped) - 1 and goal_facing is not None:
                segment_goal_facing = float(goal_facing)

            refined_segment = False
            if enable_exact_refine and model_base is not None and corridor.total_distance > 1e-6:
                trigger = evaluate_se2_refine_trigger(
                    model_base=model_base,
                    footprint_class=footprint_class,
                    corridor=corridor,
                    mesh=mesh,
                    triangle_path=triangle_path,
                    start_facing=current_facing_value,
                    goal_facing=segment_goal_facing,
                    safety_margin=float(exact_refine_safety_margin),
                )
                if trigger.should_refine:
                    refine_result = refine_corridor_se2(
                        Se2RefineRequest(
                            surface=surface,
                            mesh=mesh,
                            triangle_path=triangle_path,
                            corridor=corridor,
                            model_base=model_base,
                            movement_profile=movement_profile,
                            dynamic_overlay=dynamic_overlay,
                            start_facing=current_facing_value,
                            goal_facing=segment_goal_facing,
                            safety_margin=float(exact_refine_safety_margin),
                            pivot_cost_once=_pivot_cost_once_for_refiner(movement_profile, model_base),
                        )
                    )
                    segment_refinements.append(
                        {
                            "segment_index": int(segment_index),
                            "surface_id": surface_id,
                            "trigger_reasons": trigger.reasons,
                            "corridor_min_clearance": trigger.corridor_min_clearance,
                            "footprint_max_width": trigger.footprint_max_width,
                            "theta_bins": trigger.theta_bins,
                            "used_refiner": bool(refine_result.success),
                            "failure_reason": refine_result.failure_reason,
                            "refiner_debug": dict(refine_result.debug_artifacts),
                        }
                    )
                    if not refine_result.success:
                        candidate_failure_reason = (
                            f"Exact corridor refinement failed on segment {segment_index}: {refine_result.failure_reason}"
                        )
                        break
                    refined_segment = True
                    used_exact_refiner = True
                    for pose in refine_result.poses[1:]:
                        waypoints.append((float(pose.x), float(pose.y), float(surface.surface_z)))
                    if refine_result.poses:
                        current_facing_value = float(refine_result.poses[-1].facing)
                else:
                    segment_refinements.append(
                        {
                            "segment_index": int(segment_index),
                            "surface_id": surface_id,
                            "trigger_reasons": trigger.reasons,
                            "corridor_min_clearance": trigger.corridor_min_clearance,
                            "footprint_max_width": trigger.footprint_max_width,
                            "theta_bins": trigger.theta_bins,
                            "used_refiner": False,
                        }
                    )
            elif enable_exact_refine and model_base is not None:
                segment_refinements.append(
                    {
                        "segment_index": int(segment_index),
                        "surface_id": surface_id,
                        "trigger_reasons": (),
                        "corridor_min_clearance": float("inf"),
                        "footprint_max_width": 0.0,
                        "theta_bins": 0,
                        "used_refiner": False,
                        "skip_reason": "zero_length_segment",
                    }
                )

            if not refined_segment:
                for point_xy in corridor.smoothed_waypoints_xy[1:]:
                    waypoints.append((float(point_xy[0]), float(point_xy[1]), float(surface.surface_z)))
                if len(corridor.smoothed_waypoints_xy) >= 2:
                    prev_x, prev_y = corridor.smoothed_waypoints_xy[-2]
                    next_x, next_y = corridor.smoothed_waypoints_xy[-1]
                    if abs(float(next_x) - float(prev_x)) > 1e-9 or abs(float(next_y) - float(prev_y)) > 1e-9:
                        current_facing_value = atan2(float(next_y) - float(prev_y), float(next_x) - float(prev_x))

            if connector_out_id is not None:
                connector = connector_lookup[connector_out_id]
                connector_path.append(connector.connector_id)
                target_surface = surfaces_by_id[connector.target_surface_id]
                waypoints.append(
                    (
                        float(connector.anchor_xy[0]),
                        float(connector.anchor_xy[1]),
                        float(target_surface.surface_z),
                    )
                )
                current_start_xy = (float(connector.anchor_xy[0]), float(connector.anchor_xy[1]))
            else:
                if segment_index == len(grouped) - 1 and waypoints:
                    waypoints[-1] = (float(goal[0]), float(goal[1]), float(goal[2]))

        if candidate_failure_reason is not None:
            candidate_failures.append(
                {
                    "candidate_rank": int(candidate_rank),
                    "failure_reason": candidate_failure_reason,
                    "node_path": node_path,
                    "transitions": transitions,
                    "segment_refinements": segment_refinements,
                }
            )
            continue

        waypoints_tuple = _dedupe_waypoints(waypoints)
        surface_path = tuple(dict.fromkeys(surface_id for surface_id, _ in node_path))
        return SurfaceGraphPathResult(
            success=True,
            waypoints=waypoints_tuple,
            distance_cost=_waypoint_distance_cost(
                waypoints_tuple,
                ignore_vertical=movement_profile.can_ignore_vertical_distance,
            ),
            portal_path=tuple(portal_path),
            connector_path=tuple(connector_path),
            surface_path=surface_path,
            triangulation_backends=triangulation_backends,
            used_exact_refiner=used_exact_refiner,
            failure_reason=None,
            debug_artifacts={
                "node_path": node_path,
                "transitions": transitions,
                "grouped_segments": grouped,
                "candidate_rank": int(candidate_rank),
                "candidate_count": len(path_candidates),
                "segment_refinements": segment_refinements,
                "final_facing": current_facing_value,
            },
        )

    return SurfaceGraphPathResult(
        success=False,
        waypoints=(),
        distance_cost=0.0,
        portal_path=(),
        connector_path=(),
        surface_path=(),
        triangulation_backends=triangulation_backends,
        used_exact_refiner=False,
        failure_reason="Exact corridor refinement failed for all candidate routes",
        debug_artifacts={
            "candidate_count": len(path_candidates),
            "candidate_failures": candidate_failures,
        },
    )


__all__ = [
    "SurfaceConnector",
    "SurfaceGraphPathResult",
    "SurfaceGraphStatic",
    "build_surface_connectors",
    "build_surface_free_space",
    "build_surface_graph_for_query",
    "build_surface_graph_static",
    "plan_surface_graph_path",
]
