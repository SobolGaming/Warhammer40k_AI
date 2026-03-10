from __future__ import annotations

from math import atan2
from typing import Optional

from shapely.geometry import Point
from shapely import STRtree

from ..utility.entity_ids import maybe_entity_id
from .dynamic_overlay import build_dynamic_overlay
from .rules_profile import build_movement_profile
from .surface_graph import plan_surface_graph_path
from .surfaces import validate_pose_support
from .sweep import intersects_enemy_models, list_models_moved_over, swept_footprint
from .types import PathQuery, PathResult, Pose, SweepResult, ValidationResult
from .world_snapshot import build_world_snapshot


def _tuple_target(target: tuple[float, float, float] | tuple[float, float], fallback_z: float) -> tuple[float, float, float]:
    if len(target) == 2:
        return (float(target[0]), float(target[1]), float(fallback_z))
    return (float(target[0]), float(target[1]), float(target[2]))


def _model_start_pose(model: object) -> tuple[float, float, float, float]:
    location_getter = getattr(model, "get_location", None)
    location = tuple(location_getter() or ()) if callable(location_getter) else ()
    if len(location) >= 3:
        x, y, z = float(location[0]), float(location[1]), float(location[2])
    else:
        base = getattr(model, "model_base")
        x = float(getattr(base, "x", 0.0))
        y = float(getattr(base, "y", 0.0))
        z = float(getattr(base, "z", 0.0))
    facing = float(getattr(getattr(model, "model_base"), "facing", 0.0) or 0.0)
    return (x, y, z, facing)


def _base_radius_and_footprint_class(model_base: object) -> tuple[float, str]:
    radius = getattr(model_base, "radius", (0.0, 0.0))
    if isinstance(radius, tuple):
        radius_value = max(float(radius[0]), float(radius[1]))
    else:
        radius_value = float(radius)

    has_circular_base = bool(getattr(model_base, "has_circular_base", False))
    has_compound_parts = bool(getattr(model_base, "has_compound_parts", lambda: False)())
    if has_circular_base and not has_compound_parts:
        return radius_value, "disk"

    base_type_name = str(getattr(getattr(model_base, "base_type", None), "name", "")).upper()
    if base_type_name == "HULL":
        return radius_value, "hull"
    return radius_value, "oval"


def _build_pose_sequence(
    waypoints: tuple[tuple[float, float, float], ...],
    *,
    start_facing: float,
    goal_facing: Optional[float],
) -> tuple[Pose, ...]:
    if not waypoints:
        return ()

    facings: list[float] = []
    for index in range(len(waypoints)):
        if index == 0:
            facings.append(float(start_facing))
            continue
        prev = waypoints[index - 1]
        curr = waypoints[index]
        dx = float(curr[0]) - float(prev[0])
        dy = float(curr[1]) - float(prev[1])
        if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
            facings.append(float(facings[-1]))
            continue
        facings.append(float(atan2(dy, dx)))
    if goal_facing is not None:
        facings[-1] = float(goal_facing)

    return tuple(
        Pose(
            x=float(point[0]),
            y=float(point[1]),
            z=float(point[2]),
            facing=float(facing),
        )
        for point, facing in zip(waypoints, facings)
    )


def _pivot_cost_for_path(
    query: PathQuery,
    poses: tuple[Pose, ...],
    movement_profile: object,
) -> float:
    if len(poses) < 2:
        return 0.0
    if str(getattr(movement_profile, "pivot_cost_mode", "none")) == "none":
        return 0.0

    first_facing = float(poses[0].facing)
    last_facing = float(poses[-1].facing)
    if abs(last_facing - first_facing) <= 1e-6:
        return 0.0

    from ..utility.calcs import get_pivot_cost

    unit = getattr(query.model, "parent_unit", None)
    if unit is None:
        return 0.0
    return float(get_pivot_cost(unit))


def _moved_model_identity_tokens(query: PathQuery) -> tuple[str, ...]:
    moved = tuple(query.moved_models_in_unit or ())
    if not moved:
        return ()
    tokens: set[str] = set()
    models = tuple(getattr(getattr(query.model, "parent_unit", None), "models", ()) or ())
    for item in moved:
        if isinstance(item, int):
            index = int(item)
            if 0 <= index < len(models):
                model = models[index]
                token = maybe_entity_id(model)
                if token:
                    tokens.add(str(token))
            continue
        token = maybe_entity_id(item)
        if token:
            tokens.add(str(token))
    return tuple(sorted(tokens))


def _overlay_for_query(dynamic_overlay: object, query: PathQuery) -> object:
    moved_tokens = _moved_model_identity_tokens(query)
    moved_set = set(moved_tokens)

    blockers: list[object] = []
    for blocker in dynamic_overlay.blockers:
        if getattr(blocker, "is_same_unit", False):
            if not moved_set:
                continue
            if str(blocker.model_id) not in moved_set:
                continue
        blockers.append(blocker)

    if len(blockers) == len(dynamic_overlay.blockers):
        return dynamic_overlay

    friendly_blockers = tuple(blocker for blocker in blockers if blocker.is_friendly)
    enemy_blockers = tuple(blocker for blocker in blockers if blocker.is_enemy)
    friendly_shapes = tuple(blocker.footprint for blocker in friendly_blockers)
    enemy_shapes = tuple(blocker.footprint for blocker in enemy_blockers)
    friendly_tree = STRtree(friendly_shapes) if friendly_shapes else None
    enemy_tree = STRtree(enemy_shapes) if enemy_shapes else None
    enemy_engagement_shapes = dynamic_overlay.enemy_engagement_shapes
    enemy_engagement_tree = dynamic_overlay.enemy_engagement_tree
    if len(enemy_blockers) != len(dynamic_overlay.enemy_blockers):
        enemy_engagement_shapes = tuple(shape for shape, blocker in zip(dynamic_overlay.enemy_engagement_shapes, dynamic_overlay.enemy_blockers) if blocker in enemy_blockers)
        enemy_engagement_tree = STRtree(enemy_engagement_shapes) if enemy_engagement_shapes else None
    return dynamic_overlay.__class__(
        blockers=tuple(blockers),
        friendly_blockers=friendly_blockers,
        enemy_blockers=enemy_blockers,
        friendly_tree=friendly_tree,
        enemy_tree=enemy_tree,
        enemy_engagement_shapes=enemy_engagement_shapes,
        enemy_engagement_tree=enemy_engagement_tree,
    )


def plan_model_path(query: PathQuery) -> PathResult:
    model = query.model
    if model is None:
        return PathResult(
            valid=False,
            poses=(),
            waypoints=(),
            distance_cost=0.0,
            pivot_cost=0.0,
            used_exact_refiner=False,
            failure_reason="Invalid input: model is None",
        )

    model_base = getattr(model, "model_base", None)
    if model_base is None:
        return PathResult(
            valid=False,
            poses=(),
            waypoints=(),
            distance_cost=0.0,
            pivot_cost=0.0,
            used_exact_refiner=False,
            failure_reason="Invalid input: model has no base",
        )

    if float(query.max_distance) <= 0.0:
        return PathResult(
            valid=False,
            poses=(),
            waypoints=(),
            distance_cost=0.0,
            pivot_cost=0.0,
            used_exact_refiner=False,
            failure_reason="Invalid input: max_distance must be positive",
        )

    start_x, start_y, start_z, start_facing = _model_start_pose(model)
    target = _tuple_target(query.target, start_z)
    moving_unit = getattr(model, "parent_unit")
    target_units = tuple(query.target_units or ())
    movement_profile = build_movement_profile(
        moving_unit,
        query.movement_type,
        target_unit=query.target_unit,
        target_units=target_units,
    )
    world_snapshot = build_world_snapshot(query.game_map, movement_profile)
    dynamic_overlay = build_dynamic_overlay(
        query.game_map,
        moving_unit,
        movement_profile,
        moving_model=model,
    )
    dynamic_overlay = _overlay_for_query(dynamic_overlay, query)
    base_radius, footprint_class = _base_radius_and_footprint_class(model_base)
    graph_path = plan_surface_graph_path(
        world_snapshot,
        movement_profile,
        start=(start_x, start_y, start_z),
        goal=target,
        base_radius=float(base_radius),
        footprint_class=footprint_class,
        prefer_constrained=bool(query.prefer_constrained),
        dynamic_overlay=dynamic_overlay,
        use_cache=bool(query.use_cache),
        model_base=model_base,
        start_facing=float(start_facing),
        goal_facing=float(query.goal_facing) if query.goal_facing is not None else None,
        enable_exact_refine=bool(query.enable_exact_refine),
        exact_refine_max_paths=int(query.exact_refine_max_paths),
        exact_refine_safety_margin=float(query.exact_refine_safety_margin),
    )
    if not graph_path.success:
        debug_artifacts = dict(graph_path.debug_artifacts) if query.debug_enabled else {}
        return PathResult(
            valid=False,
            poses=(),
            waypoints=(),
            distance_cost=0.0,
            pivot_cost=0.0,
            used_exact_refiner=bool(graph_path.used_exact_refiner),
            failure_reason=str(graph_path.failure_reason or "No portal/connector route found"),
            debug_artifacts=debug_artifacts,
        )

    waypoints = tuple(graph_path.waypoints)
    poses = _build_pose_sequence(
        waypoints,
        start_facing=float(start_facing),
        goal_facing=float(query.goal_facing) if query.goal_facing is not None else None,
    )
    pivot_cost = _pivot_cost_for_path(query, poses, movement_profile)
    total_distance = float(graph_path.distance_cost) + float(pivot_cost)
    if total_distance > float(query.max_distance) + 1e-6:
        return PathResult(
            valid=False,
            poses=poses,
            waypoints=waypoints,
            distance_cost=float(graph_path.distance_cost),
            pivot_cost=float(pivot_cost),
            used_exact_refiner=bool(graph_path.used_exact_refiner),
            failure_reason=f"Distance limit exceeded: {total_distance:.2f}\" > {float(query.max_distance):.2f}\"",
            debug_artifacts=dict(graph_path.debug_artifacts) if query.debug_enabled else {},
        )

    if poses:
        validation = validate_final_pose(query, poses[-1])
        if not validation.valid:
            return PathResult(
                valid=False,
                poses=poses,
                waypoints=waypoints,
                distance_cost=float(graph_path.distance_cost),
                pivot_cost=float(pivot_cost),
                used_exact_refiner=bool(graph_path.used_exact_refiner),
                failure_reason=str(validation.reason),
                debug_artifacts=dict(validation.debug_artifacts) if query.debug_enabled else {},
            )

    provisional = PathResult(
        valid=True,
        poses=poses,
        waypoints=waypoints,
        distance_cost=float(graph_path.distance_cost),
        pivot_cost=float(pivot_cost),
        used_exact_refiner=bool(graph_path.used_exact_refiner),
        moved_over_enemy_model_ids=(),
        failure_reason=None,
        debug_artifacts=dict(graph_path.debug_artifacts) if query.debug_enabled else {},
    )
    sweep = compute_swept_interactions(query, provisional)
    debug_artifacts = dict(provisional.debug_artifacts)
    if query.debug_enabled:
        debug_artifacts["sweep"] = dict(sweep.debug_artifacts)
    return PathResult(
        valid=True,
        poses=poses,
        waypoints=waypoints,
        distance_cost=float(graph_path.distance_cost),
        pivot_cost=float(pivot_cost),
        used_exact_refiner=bool(graph_path.used_exact_refiner),
        moved_over_enemy_model_ids=tuple(sweep.moved_over_enemy_model_ids),
        failure_reason=None,
        debug_artifacts=debug_artifacts,
    )


def preview_model_path(query: PathQuery) -> PathResult:
    return plan_model_path(query)


def validate_final_pose(query: PathQuery, pose: Pose) -> ValidationResult:
    model = query.model
    if model is None:
        return ValidationResult(valid=False, reason="Invalid input: model is None")

    model_base = getattr(model, "model_base", None)
    if model_base is None:
        return ValidationResult(valid=False, reason="Invalid input: model has no base")

    pose_shape = model_base.get_base_shape_at(float(pose.x), float(pose.y), float(pose.facing))
    boundary = getattr(query.game_map, "boundary", None)
    if boundary is not None and not boundary.covers(pose_shape):
        return ValidationResult(valid=False, reason="Position outside battlefield boundaries")

    moving_unit = getattr(model, "parent_unit")
    target_units = tuple(query.target_units or ())
    movement_profile = build_movement_profile(
        moving_unit,
        query.movement_type,
        target_unit=query.target_unit,
        target_units=target_units,
    )
    world_snapshot = build_world_snapshot(query.game_map, movement_profile)
    support_validation = validate_pose_support(
        model_base,
        world_snapshot.support_surfaces,
        x=float(pose.x),
        y=float(pose.y),
        z=float(pose.z),
        facing=float(pose.facing),
    )
    if not support_validation.valid:
        return ValidationResult(valid=False, reason=str(support_validation.reason))

    dynamic_overlay = build_dynamic_overlay(
        query.game_map,
        moving_unit,
        movement_profile,
        moving_model=model,
    )
    dynamic_overlay = _overlay_for_query(dynamic_overlay, query)
    surface_point = Point(float(pose.x), float(pose.y))
    for blocker in dynamic_overlay.blockers:
        if blocker.footprint.disjoint(surface_point) and blocker.footprint.disjoint(pose_shape):
            continue
        overlap_area = float(pose_shape.intersection(blocker.footprint).area)
        if overlap_area > 1e-6:
            return ValidationResult(valid=False, reason="Position blocked by another model")

    return ValidationResult(valid=True, reason="Valid final position")


def compute_swept_interactions(query: PathQuery, path: PathResult) -> SweepResult:
    if not path.poses:
        return SweepResult(
            moved_over_enemy_model_ids=(),
            intersects_enemy_models=False,
            debug_artifacts={},
        )

    model = query.model
    model_base = getattr(model, "model_base", None)
    if model_base is None:
        return SweepResult(
            moved_over_enemy_model_ids=(),
            intersects_enemy_models=False,
            debug_artifacts={},
        )

    moving_unit = getattr(model, "parent_unit")
    movement_profile = build_movement_profile(
        moving_unit,
        query.movement_type,
        target_unit=query.target_unit,
        target_units=tuple(query.target_units or ()),
    )
    dynamic_overlay = build_dynamic_overlay(
        query.game_map,
        moving_unit,
        movement_profile,
        moving_model=model,
    )
    dynamic_overlay = _overlay_for_query(dynamic_overlay, query)
    swept_shape = swept_footprint(path.poses, model_base)
    moved_over_ids = list_models_moved_over(swept_shape, dynamic_overlay.enemy_blockers)
    intersects = intersects_enemy_models(swept_shape, dynamic_overlay.enemy_blockers)
    debug_artifacts: dict[str, object] = {}
    if query.debug_enabled:
        debug_artifacts = {
            "swept_shape_area": float(swept_shape.area),
            "enemy_blocker_count": len(dynamic_overlay.enemy_blockers),
        }
    return SweepResult(
        moved_over_enemy_model_ids=tuple(moved_over_ids),
        intersects_enemy_models=bool(intersects),
        debug_artifacts=debug_artifacts,
    )


__all__ = [
    "PathQuery",
    "PathResult",
    "Pose",
    "SweepResult",
    "ValidationResult",
    "compute_swept_interactions",
    "plan_model_path",
    "preview_model_path",
    "validate_final_pose",
]
