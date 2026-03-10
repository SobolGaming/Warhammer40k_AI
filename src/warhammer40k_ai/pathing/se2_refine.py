from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, hypot, pi
from typing import Optional

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .cdt_mesh import SurfaceCdtMesh
from .corridor import CorridorResult
from .dynamic_overlay import DynamicOverlay
from .surfaces import GROUND_LAYER_KIND, SupportSurface, validate_pose_support_on_surface
from .types import MovementProfile, SurfaceId

_ANGLE_EPSILON = 1e-6
_DISTANCE_EPSILON = 1e-9
_START_THETA_KEY = -1
_GOAL_THETA_KEY = -2


@dataclass(frozen=True, eq=False)
class Se2Pose:
    x: float
    y: float
    z: float
    facing: float
    surface_id: SurfaceId
    pivot_used: bool


@dataclass(frozen=True, eq=False)
class Se2RefineTrigger:
    should_refine: bool
    reasons: tuple[str, ...]
    corridor_min_clearance: float
    corridor_min_portal_width: float
    footprint_max_width: float
    footprint_min_width: float
    theta_bins: int


@dataclass(frozen=True, eq=False)
class Se2RefineRequest:
    surface: SupportSurface
    mesh: SurfaceCdtMesh
    triangle_path: tuple[int, ...]
    corridor: CorridorResult
    model_base: object
    movement_profile: MovementProfile
    dynamic_overlay: Optional[DynamicOverlay] = None
    start_facing: Optional[float] = None
    goal_facing: Optional[float] = None
    safety_margin: float = 0.1
    theta_bins_default: int = 16
    theta_bins_hull: int = 24
    lateral_bins: int = 5
    step_size: float = 0.35
    transition_sample_step: float = 0.2
    transition_sample_yaw: float = pi / 18.0
    max_turn_per_step: float = pi / 4.0
    pivot_cost_once: float = 0.0


@dataclass(frozen=True, eq=False)
class Se2RefineResult:
    success: bool
    poses: tuple[Se2Pose, ...]
    pivot_used: bool
    distance_cost: float
    failure_reason: Optional[str] = None
    debug_artifacts: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, eq=False)
class _SpineSample:
    s: float
    x: float
    y: float
    tangent_x: float
    tangent_y: float


@dataclass(frozen=True, eq=False)
class _StateRecord:
    cost: float
    pose: Se2Pose
    parent: Optional[tuple[int, tuple[int, int, bool]]]


def _normalize_angle(angle: float) -> float:
    two_pi = 2.0 * pi
    normalized = float(angle) % two_pi
    if normalized < 0.0:
        normalized += two_pi
    return normalized


def _shortest_angle_delta(source: float, target: float) -> float:
    delta = _normalize_angle(target) - _normalize_angle(source)
    if delta > pi:
        delta -= 2.0 * pi
    elif delta < -pi:
        delta += 2.0 * pi
    return float(delta)


def _is_non_circular_base(model_base: object, footprint_class: str) -> bool:
    if model_base is None:
        return str(footprint_class).strip().lower() != "disk"
    has_circular = bool(getattr(model_base, "has_circular_base", False))
    return not has_circular


def _footprint_dimensions(model_base: object) -> tuple[float, float]:
    radius = getattr(model_base, "radius", (0.0, 0.0))
    if isinstance(radius, tuple):
        rx = float(radius[0])
        ry = float(radius[1])
    else:
        rx = float(radius)
        ry = float(radius)
    min_width = 2.0 * min(rx, ry)
    max_width = 2.0 * max(rx, ry)

    has_compound_parts = bool(getattr(model_base, "has_compound_parts", lambda: False)())
    if has_compound_parts:
        shape = model_base.get_base_shape_at(0.0, 0.0, 0.0)
        min_x, min_y, max_x, max_y = shape.bounds
        min_width = max(0.0, min(max_x - min_x, max_y - min_y))
        max_width = max(max_width, max(max_x - min_x, max_y - min_y))

    base_type_name = str(getattr(getattr(model_base, "base_type", None), "name", ""))
    if base_type_name == "HULL":
        max_width = max(max_width, 2.0 * hypot(rx, ry))
    return float(min_width), float(max_width)


def _theta_bin_count(model_base: object, default_bins: int, hull_bins: int) -> int:
    if model_base is None:
        return int(default_bins)
    base_type_name = str(getattr(getattr(model_base, "base_type", None), "name", ""))
    if base_type_name == "HULL":
        return int(hull_bins)
    radius = getattr(model_base, "radius", (0.0, 0.0))
    if isinstance(radius, tuple):
        major = max(float(radius[0]), float(radius[1]))
        if major >= 1.75:
            return int(hull_bins)
    return int(default_bins)


def _build_theta_bins(theta_bins: int) -> tuple[float, ...]:
    count = max(4, int(theta_bins))
    step = (2.0 * pi) / float(count)
    return tuple(_normalize_angle(step * float(index)) for index in range(count))


def _nearest_theta_indices(theta: float, bins: tuple[float, ...], *, count: int) -> tuple[int, ...]:
    ranked = sorted(
        range(len(bins)),
        key=lambda index: (
            abs(_shortest_angle_delta(theta, bins[index])),
            index,
        ),
    )
    if not ranked:
        return ()
    return tuple(ranked[: max(1, int(count))])


def _iter_segment_vectors(points_xy: tuple[tuple[float, float], ...]) -> tuple[tuple[float, float, float], ...]:
    segments: list[tuple[float, float, float]] = []
    for index in range(1, len(points_xy)):
        x0, y0 = points_xy[index - 1]
        x1, y1 = points_xy[index]
        dx = float(x1) - float(x0)
        dy = float(y1) - float(y0)
        length = hypot(dx, dy)
        if length <= _DISTANCE_EPSILON:
            continue
        segments.append((dx / length, dy / length, length))
    return tuple(segments)


def _sample_spine(points_xy: tuple[tuple[float, float], ...], *, step_size: float) -> tuple[_SpineSample, ...]:
    if not points_xy:
        return ()
    points = tuple((float(point[0]), float(point[1])) for point in points_xy)
    if len(points) == 1:
        return (_SpineSample(s=0.0, x=points[0][0], y=points[0][1], tangent_x=1.0, tangent_y=0.0),)

    cumulative: list[float] = [0.0]
    for index in range(1, len(points)):
        cumulative.append(cumulative[-1] + hypot(points[index][0] - points[index - 1][0], points[index][1] - points[index - 1][1]))
    total_length = cumulative[-1]
    if total_length <= _DISTANCE_EPSILON:
        tangent = _iter_segment_vectors(points)
        tangent_x = tangent[0][0] if tangent else 1.0
        tangent_y = tangent[0][1] if tangent else 0.0
        return tuple(
            _SpineSample(s=0.0, x=point[0], y=point[1], tangent_x=tangent_x, tangent_y=tangent_y)
            for point in points
        )

    sample_step = max(0.1, float(step_size))
    sample_distances: list[float] = []
    distance = 0.0
    while distance < total_length:
        sample_distances.append(distance)
        distance += sample_step
    if not sample_distances or abs(sample_distances[-1] - total_length) > 1e-6:
        sample_distances.append(total_length)

    samples: list[_SpineSample] = []
    segment_index = 0
    for sample_distance in sample_distances:
        while segment_index + 1 < len(cumulative) and cumulative[segment_index + 1] < sample_distance - _DISTANCE_EPSILON:
            segment_index += 1
        if segment_index + 1 >= len(points):
            segment_index = len(points) - 2
        start_distance = cumulative[segment_index]
        end_distance = cumulative[segment_index + 1]
        segment_length = max(end_distance - start_distance, _DISTANCE_EPSILON)
        blend = max(0.0, min(1.0, (sample_distance - start_distance) / segment_length))
        x0, y0 = points[segment_index]
        x1, y1 = points[segment_index + 1]
        x = x0 + (x1 - x0) * blend
        y = y0 + (y1 - y0) * blend
        tangent_dx = x1 - x0
        tangent_dy = y1 - y0
        tangent_length = hypot(tangent_dx, tangent_dy)
        if tangent_length <= _DISTANCE_EPSILON:
            tangent_x = 1.0
            tangent_y = 0.0
        else:
            tangent_x = tangent_dx / tangent_length
            tangent_y = tangent_dy / tangent_length
        samples.append(
            _SpineSample(
                s=float(sample_distance),
                x=float(x),
                y=float(y),
                tangent_x=float(tangent_x),
                tangent_y=float(tangent_y),
            )
        )
    return tuple(samples)


def _corridor_geometry(mesh: SurfaceCdtMesh, triangle_path: tuple[int, ...]) -> BaseGeometry:
    if not triangle_path:
        return mesh.free_space
    corridor_triangles = tuple(mesh.triangles[index] for index in triangle_path if 0 <= int(index) < len(mesh.triangles))
    if not corridor_triangles:
        return mesh.free_space
    return mesh.free_space.intersection(unary_union(corridor_triangles))


def _corridor_min_clearance(
    corridor_geometry: BaseGeometry,
    corridor: CorridorResult,
    portal_widths: tuple[float, ...],
) -> float:
    candidates: list[float] = [float(width) for width in portal_widths if float(width) > 0.0]
    if not corridor_geometry.is_empty and not corridor_geometry.boundary.is_empty:
        for point_x, point_y in corridor.smoothed_waypoints_xy:
            boundary_distance = corridor_geometry.boundary.distance(Point(float(point_x), float(point_y)))
            candidates.append(2.0 * float(boundary_distance))
    if not candidates:
        return float("inf")
    return float(min(candidates))


def evaluate_se2_refine_trigger(
    *,
    model_base: Optional[object],
    footprint_class: str,
    corridor: CorridorResult,
    mesh: SurfaceCdtMesh,
    triangle_path: tuple[int, ...],
    start_facing: Optional[float],
    goal_facing: Optional[float],
    safety_margin: float = 0.1,
) -> Se2RefineTrigger:
    if model_base is None:
        return Se2RefineTrigger(
            should_refine=False,
            reasons=(),
            corridor_min_clearance=float("inf"),
            corridor_min_portal_width=float("inf"),
            footprint_max_width=0.0,
            footprint_min_width=0.0,
            theta_bins=16,
        )

    corridor_geometry = _corridor_geometry(mesh, triangle_path)
    portal_widths: list[float] = []
    for portal_id in corridor.portal_ids:
        portal = next((candidate for candidate in mesh.portals if candidate.portal_id == portal_id), None)
        if portal is not None:
            portal_widths.append(float(portal.length))
    min_portal_width = float(min(portal_widths)) if portal_widths else float("inf")
    min_width, max_width = _footprint_dimensions(model_base)
    min_clearance = _corridor_min_clearance(corridor_geometry, corridor, tuple(portal_widths))
    theta_bins = _theta_bin_count(model_base, 16, 24)

    reasons: list[str] = []
    has_compound_parts = bool(getattr(model_base, "has_compound_parts", lambda: False)())
    non_circular = _is_non_circular_base(model_base, footprint_class)
    if non_circular:
        reasons.append("non_circular_base")
    if has_compound_parts:
        reasons.append("compound_base")
    if min_clearance < (max_width + float(safety_margin)):
        reasons.append("narrow_corridor")
    if min_portal_width < (max_width + float(safety_margin)):
        reasons.append("narrow_portal")

    if start_facing is not None and goal_facing is not None and (non_circular or has_compound_parts):
        facing_delta = abs(_shortest_angle_delta(float(start_facing), float(goal_facing)))
        if facing_delta >= (pi / 8.0):
            reasons.append("significant_facing_delta")

    return Se2RefineTrigger(
        should_refine=bool(reasons),
        reasons=tuple(dict.fromkeys(reasons)),
        corridor_min_clearance=float(min_clearance),
        corridor_min_portal_width=float(min_portal_width),
        footprint_max_width=float(max_width),
        footprint_min_width=float(min_width),
        theta_bins=int(theta_bins),
    )


def _lateral_offsets(max_offset: float, lateral_bins: int) -> tuple[float, ...]:
    if max_offset <= 0.05:
        return (0.0,)
    bins = max(3, int(lateral_bins))
    half = bins // 2
    offsets: list[float] = []
    for index in range(-half, half + 1):
        offsets.append(float(max_offset) * (float(index) / float(max(1, half))))
    offsets.sort(key=lambda value: (abs(value), value))
    deduped: list[float] = []
    for value in offsets:
        if deduped and abs(deduped[-1] - value) <= 1e-6:
            continue
        deduped.append(value)
    return tuple(deduped)


def _closest_zero_offset_index(offsets: tuple[float, ...]) -> int:
    if not offsets:
        return 0
    return min(range(len(offsets)), key=lambda index: abs(float(offsets[index])))


def _offset_xy(sample: _SpineSample, lateral_offset: float) -> tuple[float, float]:
    normal_x = -float(sample.tangent_y)
    normal_y = float(sample.tangent_x)
    return (
        float(sample.x) + normal_x * float(lateral_offset),
        float(sample.y) + normal_y * float(lateral_offset),
    )


def _pose_valid(
    request: Se2RefineRequest,
    corridor_geometry: BaseGeometry,
    *,
    x: float,
    y: float,
    theta: float,
) -> tuple[bool, Optional[str]]:
    pose_shape = request.model_base.get_base_shape_at(float(x), float(y), float(theta))
    if not corridor_geometry.covers(pose_shape):
        return False, "footprint_outside_corridor"

    if request.surface.layer_kind != GROUND_LAYER_KIND:
        support_check = validate_pose_support_on_surface(
            request.model_base,
            x=float(x),
            y=float(y),
            facing=float(theta),
            surface=request.surface,
        )
        if not support_check.valid:
            return False, "unsupported_on_surface"

    if request.dynamic_overlay is None:
        return True, None

    z_here = float(request.surface.surface_z)
    for blocker in request.dynamic_overlay.blockers:
        if blocker.is_enemy and request.movement_profile.can_move_through_enemy_models:
            continue
        if blocker.is_friendly and request.movement_profile.can_move_through_friendly_models:
            continue
        if z_here < (float(blocker.z_bottom) - 1.0) or z_here > (float(blocker.z_top) + 1.0):
            continue
        if pose_shape.intersects(blocker.footprint):
            return False, "dynamic_overlap"
    return True, None


def _transition_valid(
    request: Se2RefineRequest,
    corridor_geometry: BaseGeometry,
    *,
    prev_pose: Se2Pose,
    next_x: float,
    next_y: float,
    next_theta: float,
) -> tuple[bool, Optional[str]]:
    dx = float(next_x) - float(prev_pose.x)
    dy = float(next_y) - float(prev_pose.y)
    travel = hypot(dx, dy)
    yaw = abs(_shortest_angle_delta(float(prev_pose.facing), float(next_theta)))
    steps = max(
        1,
        int(travel / max(0.05, float(request.transition_sample_step))),
        int(yaw / max(0.05, float(request.transition_sample_yaw))),
    )

    for index in range(1, steps + 1):
        blend = float(index) / float(steps)
        sample_x = float(prev_pose.x) + dx * blend
        sample_y = float(prev_pose.y) + dy * blend
        sample_theta = _normalize_angle(float(prev_pose.facing) + _shortest_angle_delta(float(prev_pose.facing), float(next_theta)) * blend)
        valid, reason = _pose_valid(
            request,
            corridor_geometry,
            x=sample_x,
            y=sample_y,
            theta=sample_theta,
        )
        if not valid:
            return False, reason
    return True, None


def _pose_distance_cost(prev_pose: Se2Pose, next_x: float, next_y: float) -> float:
    return float(hypot(float(next_x) - float(prev_pose.x), float(next_y) - float(prev_pose.y)))


def _choose_goal_record(
    layer: dict[tuple[int, int, bool], _StateRecord],
    theta_bins: tuple[float, ...],
    goal_facing: Optional[float],
) -> Optional[tuple[tuple[int, int, bool], _StateRecord]]:
    if not layer:
        return None
    if goal_facing is None:
        key = min(layer, key=lambda state_key: layer[state_key].cost)
        return key, layer[key]

    bin_step = (2.0 * pi) / float(max(1, len(theta_bins)))
    tolerance = max(bin_step * 1.5, pi / 10.0)
    eligible = [
        (state_key, record)
        for state_key, record in layer.items()
        if abs(_shortest_angle_delta(record.pose.facing, float(goal_facing))) <= tolerance
    ]
    if eligible:
        return min(eligible, key=lambda item: item[1].cost)

    return min(layer.items(), key=lambda item: item[1].cost + abs(_shortest_angle_delta(item[1].pose.facing, float(goal_facing))))


def refine_corridor_se2(request: Se2RefineRequest) -> Se2RefineResult:
    if request.model_base is None:
        return Se2RefineResult(
            success=False,
            poses=(),
            pivot_used=False,
            distance_cost=0.0,
            failure_reason="SE(2) refiner requires a model base",
            debug_artifacts={},
        )

    corridor_geometry = _corridor_geometry(request.mesh, request.triangle_path)
    if corridor_geometry.is_empty:
        return Se2RefineResult(
            success=False,
            poses=(),
            pivot_used=False,
            distance_cost=0.0,
            failure_reason="Corridor geometry is empty",
            debug_artifacts={},
        )

    spine = _sample_spine(request.corridor.smoothed_waypoints_xy, step_size=float(request.step_size))
    if len(spine) < 2:
        return Se2RefineResult(
            success=False,
            poses=(),
            pivot_used=False,
            distance_cost=0.0,
            failure_reason="Corridor spine is too short",
            debug_artifacts={},
        )

    min_width, max_width = _footprint_dimensions(request.model_base)
    theta_count = _theta_bin_count(request.model_base, request.theta_bins_default, request.theta_bins_hull)
    theta_bins = _build_theta_bins(theta_count)

    clearance_radii = [corridor_geometry.boundary.distance(Point(sample.x, sample.y)) for sample in spine]
    max_lateral = max(0.0, max(clearance_radii) - (min_width * 0.5) - float(request.safety_margin))
    offsets = _lateral_offsets(max_lateral, request.lateral_bins)
    zero_lateral_index = _closest_zero_offset_index(offsets)

    start_direction = atan2(spine[0].tangent_y, spine[0].tangent_x)
    start_facing = _normalize_angle(float(request.start_facing) if request.start_facing is not None else float(start_direction))
    goal_facing = _normalize_angle(float(request.goal_facing)) if request.goal_facing is not None else None
    start_anchor_xy = (float(spine[0].x), float(spine[0].y))
    goal_anchor_xy = (float(spine[-1].x), float(spine[-1].y))

    layers: list[dict[tuple[int, int, bool], _StateRecord]] = []
    first_layer: dict[tuple[int, int, bool], _StateRecord] = {}
    start_key = (zero_lateral_index, _START_THETA_KEY, False)
    start_valid, _ = _pose_valid(
        request,
        corridor_geometry,
        x=float(start_anchor_xy[0]),
        y=float(start_anchor_xy[1]),
        theta=float(start_facing),
    )
    if start_valid:
        first_layer[start_key] = _StateRecord(
            cost=0.0,
            pose=Se2Pose(
                x=float(start_anchor_xy[0]),
                y=float(start_anchor_xy[1]),
                z=float(request.surface.surface_z),
                facing=float(start_facing),
                surface_id=request.surface.surface_id,
                pivot_used=False,
            ),
            parent=None,
        )

    if not first_layer:
        return Se2RefineResult(
            success=False,
            poses=(),
            pivot_used=False,
            distance_cost=0.0,
            failure_reason="No valid start state for exact refinement",
            debug_artifacts={
                "spine_samples": len(spine),
                "theta_bins": len(theta_bins),
                "lateral_offsets": offsets,
            },
        )

    layers.append(first_layer)
    # Explicit in-place start-rotation layer; every rotated start state has a
    # parent edge from the exact requested start pose.
    start_rotation_layer: dict[tuple[int, int, bool], _StateRecord] = {
        start_key: _StateRecord(
            cost=0.0,
            pose=first_layer[start_key].pose,
            parent=(0, start_key),
        )
    }
    for theta_index in _nearest_theta_indices(start_facing, theta_bins, count=min(8, len(theta_bins))):
        theta = float(theta_bins[theta_index])
        if abs(_shortest_angle_delta(start_facing, theta)) <= _ANGLE_EPSILON:
            continue
        valid, _ = _pose_valid(
            request,
            corridor_geometry,
            x=float(start_anchor_xy[0]),
            y=float(start_anchor_xy[1]),
            theta=theta,
        )
        if not valid:
            continue
        yaw_delta = abs(_shortest_angle_delta(start_facing, theta))
        pivot_used = True
        transition_cost = float(yaw_delta) * 0.05
        transition_cost += float(request.pivot_cost_once)
        state_key = (zero_lateral_index, int(theta_index), pivot_used)
        existing = start_rotation_layer.get(state_key)
        if existing is not None and transition_cost >= existing.cost - 1e-9:
            continue
        start_rotation_layer[state_key] = _StateRecord(
            cost=transition_cost,
            pose=Se2Pose(
                x=float(start_anchor_xy[0]),
                y=float(start_anchor_xy[1]),
                z=float(request.surface.surface_z),
                facing=float(theta),
                surface_id=request.surface.surface_id,
                pivot_used=pivot_used,
            ),
            parent=(0, start_key),
        )
    layers.append(start_rotation_layer)
    transition_failures: dict[str, int] = {}
    final_sample_index = len(spine) - 1

    for sample_index in range(1, len(spine)):
        prev_layer_index = len(layers) - 1
        prev_layer = layers[prev_layer_index]
        current_layer: dict[tuple[int, int, bool], _StateRecord] = {}
        sample = spine[sample_index]
        final_sample = sample_index == final_sample_index

        if final_sample:
            lateral_candidates = ((zero_lateral_index, 0.0),)
        else:
            lateral_candidates = tuple((index, offset) for index, offset in enumerate(offsets))

        for prev_key, prev_record in sorted(prev_layer.items(), key=lambda item: (item[1].cost, item[0])):
            prev_theta = float(prev_record.pose.facing)
            candidate_theta_indices = sorted(
                range(len(theta_bins)),
                key=lambda idx: (abs(_shortest_angle_delta(prev_theta, theta_bins[idx])), idx),
            )
            if final_sample and goal_facing is not None:
                theta_candidates: tuple[tuple[int, float], ...] = ((_GOAL_THETA_KEY, float(goal_facing)),)
            else:
                theta_candidates = tuple((int(theta_index), float(theta_bins[theta_index])) for theta_index in candidate_theta_indices)

            for lateral_index, lateral_offset in lateral_candidates:
                if final_sample:
                    x, y = goal_anchor_xy
                else:
                    x, y = _offset_xy(sample, lateral_offset)
                for theta_index, theta in theta_candidates:
                    yaw_delta = abs(_shortest_angle_delta(prev_theta, theta))
                    is_in_place_rotation = _pose_distance_cost(prev_record.pose, x, y) <= _DISTANCE_EPSILON
                    if yaw_delta > float(request.max_turn_per_step) and not is_in_place_rotation:
                        continue
                    valid, reason = _pose_valid(request, corridor_geometry, x=x, y=y, theta=theta)
                    if not valid:
                        if reason is not None:
                            transition_failures[reason] = transition_failures.get(reason, 0) + 1
                        continue

                    transition_ok, transition_reason = _transition_valid(
                        request,
                        corridor_geometry,
                        prev_pose=prev_record.pose,
                        next_x=x,
                        next_y=y,
                        next_theta=theta,
                    )
                    if not transition_ok:
                        if transition_reason is not None:
                            transition_failures[transition_reason] = transition_failures.get(transition_reason, 0) + 1
                        continue

                    rotated = yaw_delta > _ANGLE_EPSILON
                    pivot_used = bool(prev_record.pose.pivot_used or rotated)
                    state_key = (lateral_index, int(theta_index), pivot_used)
                    transition_cost = _pose_distance_cost(prev_record.pose, x, y)
                    new_cost = prev_record.cost + transition_cost
                    if rotated:
                        new_cost += float(yaw_delta) * 0.05
                    if pivot_used and not prev_record.pose.pivot_used:
                        new_cost += float(request.pivot_cost_once)

                    existing = current_layer.get(state_key)
                    if existing is not None and new_cost >= existing.cost - 1e-9:
                        continue

                    current_layer[state_key] = _StateRecord(
                        cost=float(new_cost),
                        pose=Se2Pose(
                            x=float(x),
                            y=float(y),
                            z=float(request.surface.surface_z),
                            facing=float(theta),
                            surface_id=request.surface.surface_id,
                            pivot_used=pivot_used,
                        ),
                        parent=(prev_layer_index, prev_key),
                    )

        if not current_layer:
            most_common_failure = None
            if transition_failures:
                most_common_failure = max(transition_failures, key=lambda key: transition_failures[key])
            return Se2RefineResult(
                success=False,
                poses=(),
                pivot_used=False,
                distance_cost=0.0,
                failure_reason="Exact corridor refinement exhausted all states",
                debug_artifacts={
                    "failed_at_sample_index": int(sample_index),
                    "spine_samples": len(spine),
                    "theta_bins": len(theta_bins),
                    "lateral_offsets": offsets,
                    "dominant_rejection_reason": most_common_failure,
                    "rejection_counts": dict(sorted(transition_failures.items())),
                    "corridor_min_clearance": _corridor_min_clearance(
                        corridor_geometry,
                        request.corridor,
                        tuple(portal.length for portal in request.mesh.portals if portal.portal_id in request.corridor.portal_ids),
                    ),
                    "footprint_min_width": float(min_width),
                    "footprint_max_width": float(max_width),
                },
            )

        layers.append(current_layer)

    final_choice = _choose_goal_record(layers[-1], theta_bins, goal_facing)
    if final_choice is None:
        return Se2RefineResult(
            success=False,
            poses=(),
            pivot_used=False,
            distance_cost=0.0,
            failure_reason="No terminal SE(2) state found",
            debug_artifacts={},
        )

    final_key, final_record = final_choice
    reconstruction: list[Se2Pose] = []
    layer_index = len(layers) - 1
    current_key = final_key
    while layer_index >= 0:
        record = layers[layer_index][current_key]
        reconstruction.append(record.pose)
        if record.parent is None:
            break
        layer_index, current_key = record.parent
    reconstruction.reverse()

    if not reconstruction:
        return Se2RefineResult(
            success=False,
            poses=(),
            pivot_used=False,
            distance_cost=0.0,
            failure_reason="SE(2) reconstruction produced no poses",
            debug_artifacts={},
        )

    first_pose = reconstruction[0]
    if hypot(float(first_pose.x) - float(start_anchor_xy[0]), float(first_pose.y) - float(start_anchor_xy[1])) > 1e-6:
        return Se2RefineResult(
            success=False,
            poses=(),
            pivot_used=False,
            distance_cost=0.0,
            failure_reason="Exact refiner did not anchor start pose",
            debug_artifacts={
                "observed_start_pose": (float(first_pose.x), float(first_pose.y), float(first_pose.facing)),
                "expected_start_pose": (float(start_anchor_xy[0]), float(start_anchor_xy[1]), float(start_facing)),
            },
        )
    if abs(_shortest_angle_delta(float(first_pose.facing), float(start_facing))) > 1e-6:
        return Se2RefineResult(
            success=False,
            poses=(),
            pivot_used=False,
            distance_cost=0.0,
            failure_reason="Exact refiner did not preserve requested start facing",
            debug_artifacts={
                "observed_start_pose": (float(first_pose.x), float(first_pose.y), float(first_pose.facing)),
                "expected_start_pose": (float(start_anchor_xy[0]), float(start_anchor_xy[1]), float(start_facing)),
            },
        )

    last_pose = reconstruction[-1]
    if hypot(float(last_pose.x) - float(goal_anchor_xy[0]), float(last_pose.y) - float(goal_anchor_xy[1])) > 1e-6:
        return Se2RefineResult(
            success=False,
            poses=(),
            pivot_used=False,
            distance_cost=0.0,
            failure_reason="Exact refiner did not anchor segment endpoint",
            debug_artifacts={
                "observed_end_pose": (float(last_pose.x), float(last_pose.y), float(last_pose.facing)),
                "expected_end_pose": (float(goal_anchor_xy[0]), float(goal_anchor_xy[1]), float(goal_facing) if goal_facing is not None else None),
                "layer_count": len(layers),
                "final_key": final_key,
            },
        )
    if goal_facing is not None and abs(_shortest_angle_delta(float(last_pose.facing), float(goal_facing))) > 1e-6:
        return Se2RefineResult(
            success=False,
            poses=(),
            pivot_used=False,
            distance_cost=0.0,
            failure_reason="Exact refiner did not anchor requested final facing",
            debug_artifacts={
                "observed_end_pose": (float(last_pose.x), float(last_pose.y), float(last_pose.facing)),
                "expected_end_pose": (float(goal_anchor_xy[0]), float(goal_anchor_xy[1]), float(goal_facing)),
            },
        )

    distance_cost = 0.0
    for index in range(1, len(reconstruction)):
        distance_cost += hypot(
            float(reconstruction[index].x) - float(reconstruction[index - 1].x),
            float(reconstruction[index].y) - float(reconstruction[index - 1].y),
        )

    return Se2RefineResult(
        success=True,
        poses=tuple(reconstruction),
        pivot_used=bool(final_record.pose.pivot_used),
        distance_cost=float(distance_cost),
        failure_reason=None,
        debug_artifacts={
            "spine_samples": len(spine),
            "theta_bins": len(theta_bins),
            "lateral_offsets": offsets,
            "start_anchor_xy": start_anchor_xy,
            "goal_anchor_xy": goal_anchor_xy,
            "corridor_min_clearance": _corridor_min_clearance(
                corridor_geometry,
                request.corridor,
                tuple(portal.length for portal in request.mesh.portals if portal.portal_id in request.corridor.portal_ids),
            ),
            "footprint_min_width": float(min_width),
            "footprint_max_width": float(max_width),
        },
    )


__all__ = [
    "Se2Pose",
    "Se2RefineRequest",
    "Se2RefineResult",
    "Se2RefineTrigger",
    "evaluate_se2_refine_trigger",
    "refine_corridor_se2",
]
