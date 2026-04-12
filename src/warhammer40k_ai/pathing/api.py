from __future__ import annotations

from dataclasses import replace
from math import atan2
from typing import Mapping, Optional

from shapely.geometry import Point
from shapely import STRtree

from ..utility.entity_ids import maybe_entity_id
from .dynamic_overlay import build_dynamic_overlay
from .rules_profile import build_movement_profile
from .surface_graph import plan_surface_graph_path
from .surfaces import validate_pose_support
from .sweep import (
    intersects_enemy_models,
    list_models_moved_over,
    sweep_vertical_segments,
    swept_footprint,
)
from .types import PathQuery, PathResult, Pose, SweepResult, ValidationResult
from .validation import (
    build_collision_trees as build_validation_collision_trees,
    get_pivot_cost as get_validation_pivot_cost,
    get_validation_rules as get_validation_rule_set,
    is_position_valid_unified_detailed as validate_position_detailed,
)
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
            total += (dx * dx + dy * dy) ** 0.5
            continue
        dz = float(points[index][2]) - float(points[index - 1][2])
        total += (dx * dx + dy * dy + dz * dz) ** 0.5
    return float(total)


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

    unit = getattr(query.model, "parent_unit", None)
    if unit is None:
        return 0.0
    return float(get_validation_pivot_cost(unit))


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


def _build_validation_rules(query: PathQuery, movement_profile: object) -> dict[str, object]:
    moving_unit = getattr(query.model, "parent_unit", None)
    target_units = tuple(query.target_units or ())
    rules = dict(
        get_validation_rule_set(
            query.movement_type,
            query.target_unit,
            moving_unit=moving_unit,
            target_units=target_units,
            movement_profile=movement_profile,
        )
    )
    move_tag = str(getattr(query.movement_type, "value", query.movement_type) or "").strip().lower()
    if move_tag == "charge" and query.target_unit is not None and moving_unit is not None:
        engagement_check = getattr(query.game_map, "is_within_engagement_range", None)
        if callable(engagement_check):
            unit_already_engaged = bool(engagement_check(moving_unit, query.target_unit))
            if unit_already_engaged and bool(rules.get("must_end_in_engagement_range", False)):
                rules["must_end_in_engagement_range"] = False
                rules["allow_engagement_range_movement"] = True
    return rules


def _eligible_emplacement_platform_polygons(
    game_map: object,
    moving_model: object,
) -> dict[str, object]:
    if game_map is None or moving_model is None:
        return {}
    get_entries = getattr(game_map, "get_emplacement_platform_surface_entries", None)
    if not callable(get_entries):
        get_entries = getattr(game_map, "_iter_emplacement_platform_surface_entries", None)
    if not callable(get_entries):
        return {}

    polygons: dict[str, object] = {}
    for entry in tuple(get_entries(moving_model=moving_model, require_eligibility=True) or ()):
        source_unit = entry.get("source_unit")
        polygon = entry.get("polygon")
        source_unit_id = maybe_entity_id(source_unit)
        if source_unit_id is None or polygon is None:
            continue
        polygons[str(source_unit_id)] = polygon
    return polygons


def _rebuild_dynamic_overlay(dynamic_overlay: object, blockers: list[object]) -> object:
    friendly_blockers = tuple(blocker for blocker in blockers if blocker.is_friendly)
    enemy_blockers = tuple(blocker for blocker in blockers if blocker.is_enemy)
    friendly_shapes = tuple(blocker.footprint for blocker in friendly_blockers)
    enemy_shapes = tuple(blocker.footprint for blocker in enemy_blockers)
    friendly_tree = STRtree(friendly_shapes) if friendly_shapes else None
    enemy_tree = STRtree(enemy_shapes) if enemy_shapes else None
    enemy_engagement_shapes = dynamic_overlay.enemy_engagement_shapes
    enemy_engagement_tree = dynamic_overlay.enemy_engagement_tree
    if len(enemy_blockers) != len(dynamic_overlay.enemy_blockers):
        enemy_engagement_shapes = tuple(
            shape
            for shape, blocker in zip(dynamic_overlay.enemy_engagement_shapes, dynamic_overlay.enemy_blockers)
            if blocker in enemy_blockers
        )
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


def _direct_emplacement_platform_waypoints(
    query: PathQuery,
    movement_profile: object,
    *,
    start: tuple[float, float, float],
    target: tuple[float, float, float],
) -> tuple[tuple[float, float, float], ...]:
    placement_fn = getattr(query.game_map, "get_emplacement_platform_placement", None)
    if not callable(placement_fn):
        return ()
    target_platform = placement_fn(
        query.model,
        x=float(target[0]),
        y=float(target[1]),
        z=float(target[2]),
        require_eligibility=True,
    )
    if not bool(target_platform.get("applies", False)):
        start_platform = placement_fn(
            query.model,
            x=float(start[0]),
            y=float(start[1]),
            z=float(start[2]),
            require_eligibility=True,
        )
        if not bool(start_platform.get("applies", False)):
            return ()

    waypoints = (
        (float(start[0]), float(start[1]), float(start[2])),
        (float(target[0]), float(target[1]), float(target[2])),
    )
    poses = _build_pose_sequence(
        waypoints,
        start_facing=float(_model_start_pose(query.model)[3]),
        goal_facing=float(query.goal_facing) if query.goal_facing is not None else None,
    )
    validation_rules = _build_validation_rules(query, movement_profile)
    collision_trees = _build_collision_trees_for_query(query, movement_profile)
    final_validation = _validate_final_pose_with_context(
        query,
        poses[-1],
        movement_profile=movement_profile,
        validation_rules=validation_rules,
        collision_trees=collision_trees,
    )
    if not final_validation.valid:
        return ()
    transit_validation = _validate_transit_path_with_context(
        query,
        poses,
        validation_rules=validation_rules,
        collision_trees=collision_trees,
    )
    if not transit_validation.valid:
        return ()
    return waypoints


def _overlay_for_query(
    dynamic_overlay: object,
    query: PathQuery,
    movement_profile: object,
    validation_rules: Mapping[str, object],
    *,
    for_pathfinding: bool = True,
) -> object:
    moved_tokens = _moved_model_identity_tokens(query)
    moved_set = set(moved_tokens)
    platform_polygons = _eligible_emplacement_platform_polygons(query.game_map, query.model)
    terrain_rules = dict(getattr(movement_profile, "terrain_transition_rules", {}) or {})
    is_fly_move = bool(terrain_rules.get("is_fly_move", False))
    can_fly_over_big_models = bool(terrain_rules.get("can_fly_over_big_models", False))
    allow_through_enemy = bool(
        validation_rules.get(
            "can_move_through_enemy_models",
            getattr(movement_profile, "can_move_through_enemy_models", False),
        )
    )
    allow_through_friendly = bool(
        validation_rules.get(
            "can_move_through_friendly_models",
            getattr(movement_profile, "can_move_through_friendly_models", False),
        )
    )
    ignore_enemy_models_blocking = bool(validation_rules.get("ignore_enemy_models_blocking", False))
    block_titanic_models = bool(
        validation_rules.get(
            "block_titanic_models",
            getattr(movement_profile, "block_titanic_models", False),
        )
    )
    block_monster_vehicle_models = bool(
        validation_rules.get(
            "block_monster_vehicle_models",
            getattr(movement_profile, "block_monster_vehicle_models", False),
        )
    )

    blockers: list[object] = []
    for blocker in dynamic_overlay.blockers:
        if getattr(blocker, "is_same_unit", False):
            if not moved_set:
                continue
            if str(blocker.model_id) not in moved_set:
                continue
        platform_polygon = platform_polygons.get(str(getattr(blocker, "unit_id", "") or ""))
        if platform_polygon is not None and bool(getattr(blocker, "is_friendly", False)):
            adjusted_footprint = blocker.footprint.difference(platform_polygon)
            if adjusted_footprint.is_empty:
                continue
            blocker = replace(blocker, footprint=adjusted_footprint)
        if not for_pathfinding:
            blockers.append(blocker)
            continue
        if bool(getattr(blocker, "is_aircraft", False)):
            # AIRCRAFT are not transit blockers during movement; endpoint legality is checked separately.
            continue
        if bool(getattr(blocker, "is_enemy", False)) and allow_through_enemy:
            if block_titanic_models and bool(getattr(blocker, "is_titanic", False)):
                blockers.append(blocker)
                continue
            blocks_big_models = block_monster_vehicle_models or (
                is_fly_move
                and not can_fly_over_big_models
                and not ignore_enemy_models_blocking
            )
            if blocks_big_models and bool(getattr(blocker, "is_big_model", False)):
                blockers.append(blocker)
                continue
            continue
        if bool(getattr(blocker, "is_friendly", False)) and allow_through_friendly:
            continue
        blockers.append(blocker)

    if len(blockers) == len(dynamic_overlay.blockers):
        if all(blocker is original for blocker, original in zip(blockers, dynamic_overlay.blockers)):
            return dynamic_overlay
    return _rebuild_dynamic_overlay(dynamic_overlay, blockers)


def _build_collision_trees_for_query(query: PathQuery, movement_profile: object) -> dict[str, object]:
    moving_unit = getattr(query.model, "parent_unit", None)
    moved_models_in_unit = set(tuple(query.moved_models_in_unit or ()))
    return build_validation_collision_trees(
        moving_unit,
        query.movement_type,
        query.game_map,
        moving_model=query.model,
        moved_models_in_unit=moved_models_in_unit,
        max_distance=float(query.max_distance),
        target_position=_tuple_target(query.target, _model_start_pose(query.model)[2]),
        movement_profile=movement_profile,
    )


def _validate_final_pose_with_context(
    query: PathQuery,
    pose: Pose,
    *,
    movement_profile: object,
    validation_rules: Mapping[str, object],
    collision_trees: Mapping[str, object],
) -> ValidationResult:
    model = query.model
    model_base = getattr(model, "model_base", None)
    if model_base is None:
        return ValidationResult(valid=False, reason="Invalid input: model has no base")

    pose_shape = model_base.get_base_shape_at(float(pose.x), float(pose.y), float(pose.facing))
    boundary = getattr(query.game_map, "boundary", None)
    if boundary is not None and not boundary.covers(pose_shape):
        return ValidationResult(valid=False, reason="Position outside battlefield boundaries")

    world_snapshot = build_world_snapshot(query.game_map, movement_profile, moving_model=model)
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

    legacy_validation = validate_position_detailed(
        (float(pose.x), float(pose.y), float(pose.z)),
        model,
        dict(collision_trees),
        dict(validation_rules),
        query.game_map,
        is_final_position=True,
    )
    if not bool(legacy_validation.get("valid", False)):
        return ValidationResult(
            valid=False,
            reason=str(legacy_validation.get("reason", "Invalid final position")),
        )

    moving_unit = getattr(model, "parent_unit")
    dynamic_overlay = build_dynamic_overlay(
        query.game_map,
        moving_unit,
        movement_profile,
        moving_model=model,
    )
    dynamic_overlay = _overlay_for_query(
        dynamic_overlay,
        query,
        movement_profile,
        validation_rules,
        for_pathfinding=False,
    )
    surface_point = Point(float(pose.x), float(pose.y))
    for blocker in dynamic_overlay.blockers:
        if blocker.footprint.disjoint(surface_point) and blocker.footprint.disjoint(pose_shape):
            continue
        overlap_area = float(pose_shape.intersection(blocker.footprint).area)
        if overlap_area > 1e-6:
            return ValidationResult(valid=False, reason="Position blocked by another model")

    return ValidationResult(valid=True, reason=str(legacy_validation.get("reason", "Valid final position")))


def _validate_transit_path_with_context(
    query: PathQuery,
    poses: tuple[Pose, ...],
    *,
    validation_rules: Mapping[str, object],
    collision_trees: Mapping[str, object],
) -> ValidationResult:
    if len(poses) < 2:
        return ValidationResult(valid=True, reason="Valid path")

    model_base = getattr(query.model, "model_base", None)
    model_facing = float(getattr(model_base, "facing", 0.0) or 0.0)
    model_radius = 0.5
    if model_base is not None:
        get_radius = getattr(model_base, "get_longest_radius", None)
        if callable(get_radius):
            model_radius = max(0.05, float(get_radius()))
    sample_step = max(0.05, min(0.2, model_radius * 0.5))
    terrain_tree = collision_trees.get("terrain")

    def _tree_query_indices(tree: object, query_geometry: object) -> tuple[int, ...]:
        query_fn = getattr(tree, "query", None)
        if not callable(query_fn):
            return ()
        indices = query_fn(query_geometry)
        if indices is None:
            return ()
        try:
            return tuple(int(value) for value in indices)
        except TypeError:
            return (int(indices),)

    for segment_index in range(1, len(poses)):
        prev_pose = poses[segment_index - 1]
        next_pose = poses[segment_index]
        if terrain_tree is not None and model_base is not None:
            start_shape = model_base.get_base_shape_at(float(prev_pose.x), float(prev_pose.y), model_facing)
            end_shape = model_base.get_base_shape_at(float(next_pose.x), float(next_pose.y), model_facing)
            swept_shape = start_shape.union(end_shape).convex_hull
            terrain_geometries = getattr(terrain_tree, "geometries", ())
            for hit_index in _tree_query_indices(terrain_tree, swept_shape):
                if not (0 <= int(hit_index) < len(terrain_geometries)):
                    continue
                if swept_shape.intersects(terrain_geometries[int(hit_index)]):
                    return ValidationResult(valid=False, reason="Path crosses terrain between waypoints")

        dx = float(next_pose.x) - float(prev_pose.x)
        dy = float(next_pose.y) - float(prev_pose.y)
        dz = float(next_pose.z) - float(prev_pose.z)
        segment_distance = (dx * dx + dy * dy + dz * dz) ** 0.5
        samples = max(1, int(segment_distance / sample_step))
        for sample_index in range(1, samples + 1):
            if segment_index == len(poses) - 1 and sample_index == samples:
                # Final pose is validated by `_validate_final_pose_with_context`.
                continue
            blend = float(sample_index) / float(samples)
            sample_position = (
                float(prev_pose.x) + dx * blend,
                float(prev_pose.y) + dy * blend,
                float(prev_pose.z) + dz * blend,
            )
            validation = validate_position_detailed(
                sample_position,
                query.model,
                dict(collision_trees),
                dict(validation_rules),
                query.game_map,
                is_final_position=False,
            )
            if not bool(validation.get("valid", False)):
                return ValidationResult(
                    valid=False,
                    reason=str(validation.get("reason", "Invalid movement segment")),
                )

    return ValidationResult(valid=True, reason="Valid path")


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
    validation_rules = _build_validation_rules(query, movement_profile)
    move_tag = str(getattr(query.movement_type, "value", query.movement_type) or "").strip().lower()
    enable_exact_refine = bool(query.enable_exact_refine) and move_tag not in {"pile_in", "consolidate"}
    world_snapshot = build_world_snapshot(query.game_map, movement_profile, moving_model=model)
    dynamic_overlay = build_dynamic_overlay(
        query.game_map,
        moving_unit,
        movement_profile,
        moving_model=model,
    )
    dynamic_overlay = _overlay_for_query(
        dynamic_overlay,
        query,
        movement_profile,
        validation_rules,
        for_pathfinding=True,
    )
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
        enable_exact_refine=enable_exact_refine,
        exact_refine_max_paths=int(query.exact_refine_max_paths),
        exact_refine_safety_margin=float(query.exact_refine_safety_margin),
    )
    path_debug_artifacts = dict(graph_path.debug_artifacts) if query.debug_enabled else {}
    used_exact_refiner = bool(graph_path.used_exact_refiner)
    if not graph_path.success:
        fallback_waypoints = _direct_emplacement_platform_waypoints(
            query,
            movement_profile,
            start=(start_x, start_y, start_z),
            target=target,
        )
        if not fallback_waypoints:
            return PathResult(
                valid=False,
                poses=(),
                waypoints=(),
                distance_cost=0.0,
                pivot_cost=0.0,
                used_exact_refiner=used_exact_refiner,
                failure_reason=str(graph_path.failure_reason or "No portal/connector route found"),
                debug_artifacts=path_debug_artifacts,
            )
        waypoints = tuple(fallback_waypoints)
        distance_cost = _waypoint_distance_cost(
            waypoints,
            ignore_vertical=bool(movement_profile.can_ignore_vertical_distance),
        )
        if query.debug_enabled:
            path_debug_artifacts["fallback_mode"] = "direct_emplacement_platform"
            path_debug_artifacts["fallback_waypoint_count"] = len(waypoints)
    else:
        waypoints = tuple(graph_path.waypoints)
        distance_cost = float(graph_path.distance_cost)
        used_exact_refiner = bool(graph_path.used_exact_refiner)

    poses = _build_pose_sequence(
        waypoints,
        start_facing=float(start_facing),
        goal_facing=float(query.goal_facing) if query.goal_facing is not None else None,
    )
    pivot_cost = _pivot_cost_for_path(query, poses, movement_profile)
    total_distance = float(distance_cost) + float(pivot_cost)
    if total_distance > float(query.max_distance) + 1e-6:
        return PathResult(
            valid=False,
            poses=poses,
            waypoints=waypoints,
            distance_cost=float(distance_cost),
            pivot_cost=float(pivot_cost),
            used_exact_refiner=used_exact_refiner,
            failure_reason=f"Distance limit exceeded: {total_distance:.2f}\" > {float(query.max_distance):.2f}\"",
            debug_artifacts=path_debug_artifacts,
        )

    if poses:
        collision_trees = _build_collision_trees_for_query(query, movement_profile)
        validation = _validate_final_pose_with_context(
            query,
            poses[-1],
            movement_profile=movement_profile,
            validation_rules=validation_rules,
            collision_trees=collision_trees,
        )
        if not validation.valid:
            return PathResult(
                valid=False,
                poses=poses,
                waypoints=waypoints,
                distance_cost=float(distance_cost),
                pivot_cost=float(pivot_cost),
                used_exact_refiner=used_exact_refiner,
                failure_reason=str(validation.reason),
                debug_artifacts=dict(validation.debug_artifacts) if query.debug_enabled else {},
            )
        transit_validation = _validate_transit_path_with_context(
            query,
            poses,
            validation_rules=validation_rules,
            collision_trees=collision_trees,
        )
        if not transit_validation.valid:
            return PathResult(
                valid=False,
                poses=poses,
                waypoints=waypoints,
                distance_cost=float(distance_cost),
                pivot_cost=float(pivot_cost),
                used_exact_refiner=used_exact_refiner,
                failure_reason=str(transit_validation.reason),
                debug_artifacts=path_debug_artifacts,
            )

    provisional = PathResult(
        valid=True,
        poses=poses,
        waypoints=waypoints,
        distance_cost=float(distance_cost),
        pivot_cost=float(pivot_cost),
        used_exact_refiner=used_exact_refiner,
        moved_over_enemy_model_ids=(),
        failure_reason=None,
        debug_artifacts=path_debug_artifacts,
    )
    sweep = compute_swept_interactions(query, provisional)
    debug_artifacts = dict(provisional.debug_artifacts)
    if query.debug_enabled:
        debug_artifacts["sweep"] = dict(sweep.debug_artifacts)
    return PathResult(
        valid=True,
        poses=poses,
        waypoints=waypoints,
        distance_cost=float(distance_cost),
        pivot_cost=float(pivot_cost),
        used_exact_refiner=used_exact_refiner,
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
    validation_rules = _build_validation_rules(query, movement_profile)
    collision_trees = _build_collision_trees_for_query(query, movement_profile)
    return _validate_final_pose_with_context(
        query,
        pose,
        movement_profile=movement_profile,
        validation_rules=validation_rules,
        collision_trees=collision_trees,
    )


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
    validation_rules = _build_validation_rules(query, movement_profile)
    dynamic_overlay = build_dynamic_overlay(
        query.game_map,
        moving_unit,
        movement_profile,
        moving_model=model,
    )
    dynamic_overlay = _overlay_for_query(
        dynamic_overlay,
        query,
        movement_profile,
        validation_rules,
        for_pathfinding=False,
    )
    swept_shape = swept_footprint(path.poses, model_base)
    require_vertical_overlap = bool(getattr(query, "sweep_require_vertical_overlap", False))
    vertical_segments = (
        sweep_vertical_segments(path.poses, model_base)
        if require_vertical_overlap
        else ()
    )
    moved_over_ids = list_models_moved_over(
        swept_shape,
        dynamic_overlay.enemy_blockers,
        require_vertical_overlap=require_vertical_overlap,
        vertical_segments=vertical_segments,
    )
    intersects = intersects_enemy_models(
        swept_shape,
        dynamic_overlay.enemy_blockers,
        require_vertical_overlap=require_vertical_overlap,
        vertical_segments=vertical_segments,
    )
    debug_artifacts: dict[str, object] = {}
    if query.debug_enabled:
        debug_artifacts = {
            "swept_shape_area": float(swept_shape.area),
            "enemy_blocker_count": len(dynamic_overlay.enemy_blockers),
            "require_vertical_overlap": require_vertical_overlap,
            "vertical_segment_count": len(vertical_segments),
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
