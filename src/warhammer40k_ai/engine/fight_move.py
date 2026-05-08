from __future__ import annotations

import math
import time
from typing import Any

from shapely.geometry import Point
from shapely.ops import nearest_points

from ..battlefield.control_queries import control_region_centroid, control_region_shape
from ..battlefield.objective_sites import resolve_objective_site
from ..pathing.api import PathQuery, plan_model_path
from ..pathing.types import MovementType as PathMovementType
from ..utility.calcs import validate_unit_coherency_after_movement
from ..utility.entity_ids import get_entity_id
from .combat_timing import (
    CombatEngagementState,
    base_contact_center_distance,
    engagement_center_distance,
    engagement_state_for_models,
    geometry_profile_for_game,
)

_MOVEMENT_TYPE_BY_TAG = {
    "pile_in": PathMovementType.PILE_IN,
    "consolidate": PathMovementType.CONSOLIDATE,
}


def serialize_attached_unit_positions(unit: object) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    for model in attached_unit_models(unit):
        try:
            alive_value = getattr(model, "is_alive", True)
            alive = bool(alive_value() if callable(alive_value) else alive_value)
        except Exception:
            alive = False
        if not alive:
            continue
        model_id = str(get_entity_id(model) or "").strip()
        if not model_id:
            continue
        getter = getattr(model, "get_location", None)
        if callable(getter):
            location = tuple(getter() or ())
            x = float(location[0] if len(location) > 0 else 0.0)
            y = float(location[1] if len(location) > 1 else 0.0)
            z = float(location[2] if len(location) > 2 else 0.0)
            facing = float(location[3] if len(location) > 3 else getattr(getattr(model, "model_base", None), "facing", 0.0))
        else:
            base = getattr(model, "model_base", None)
            x = float(getattr(base, "x", 0.0) or 0.0)
            y = float(getattr(base, "y", 0.0) or 0.0)
            z = float(getattr(base, "z", 0.0) or 0.0)
            facing = float(getattr(base, "facing", 0.0) or 0.0)
        positions.append(
            {
                "model_id": model_id,
                "position": [x, y, z],
                "facing": facing,
            }
        )
    positions.sort(key=lambda entry: str(entry.get("model_id", "") or ""))
    return positions


def attached_unit_models(unit: object) -> list[object]:
    get_models = getattr(unit, "get_attached_unit_models", None)
    if callable(get_models):
        models = list(get_models() or [])
    else:
        models = list(getattr(unit, "models", []) or [])
    models.sort(key=lambda model: str(get_entity_id(model) or ""))
    return [model for model in models if model is not None]


def validate_fight_move_positions(
    game: object,
    unit: object,
    *,
    movement_type: str,
    model_positions: list[dict[str, Any]],
    max_distance: float,
    target_unit_ids: list[str] | None = None,
) -> list[str]:
    move_tag = str(movement_type or "").strip().lower()
    path_movement_type = _MOVEMENT_TYPE_BY_TAG.get(move_tag)
    if path_movement_type is None:
        return []
    if unit is None:
        return ["Move unit: fight move requires a unit."]
    if bool(getattr(unit, "is_aircraft", False)):
        return [f"Move unit: AIRCRAFT cannot {move_tag.replace('_', ' ')}."]
    game_map = getattr(game, "map", None)
    if game_map is None:
        return ["Move unit: fight move requires an active game map."]

    current_positions = serialize_attached_unit_positions(unit)
    current_by_id = {
        str(entry.get("model_id", "") or ""): dict(entry)
        for entry in list(current_positions or [])
        if entry is not None
    }
    requested_by_id = {
        str(entry.get("model_id", "") or ""): dict(entry)
        for entry in list(model_positions or [])
        if entry is not None
    }
    required_ids = sorted(current_by_id.keys())
    requested_ids = sorted(requested_by_id.keys())
    if requested_ids != required_ids:
        return ["Move unit: fight move payload must include all alive models in the unit."]

    target_units = _resolve_target_units(game, list(target_unit_ids or []))
    moved_models: list[object] = []
    snapshot = current_positions
    try:
        for model in attached_unit_models(unit):
            model_id = str(get_entity_id(model) or "").strip()
            if not model_id or model_id not in requested_by_id:
                continue
            desired = requested_by_id[model_id]
            current = current_by_id.get(model_id, {})
            if _positions_match(current, desired):
                continue
            pose = list(desired.get("position") or [])
            if len(pose) < 2:
                return [f"Move unit: fight move payload missing position for model {model_id}."]
            target = (
                float(pose[0]),
                float(pose[1]),
                float(pose[2] if len(pose) > 2 else getattr(getattr(model, "model_base", None), "z", 0.0)),
            )
            path_result = plan_model_path(
                PathQuery(
                    model=model,
                    target=target,
                    movement_type=path_movement_type,
                    max_distance=float(max_distance),
                    game_map=game_map,
                    target_units=tuple(target_units or ()),
                    moved_models_in_unit=tuple(moved_models),
                    debug_enabled=False,
                )
            )
            if not bool(path_result.valid):
                return [
                    f"Move unit: invalid {move_tag.replace('_', ' ')} path for model {model_id}: "
                    f"{str(path_result.failure_reason or 'illegal move')}"
                ]
            final_pose = path_result.poses[-1] if path_result.poses else None
            if final_pose is None:
                return [f"Move unit: fight move path missing final pose for model {model_id}."]
            if not _pose_matches_entry(final_pose, desired):
                return [f"Move unit: submitted {move_tag.replace('_', ' ')} position for model {model_id} is not replay-stable."]
            _apply_position_entry(model, desired)
            moved_models.append(model)
        final_positions = []
        for model in list(getattr(unit, "models", []) or []):
            model_id = str(get_entity_id(model) or "").strip()
            entry = requested_by_id.get(model_id)
            if entry is None:
                entry = _model_pose_entry(model)
            pose = list(entry.get("position") or [])
            final_positions.append(
                (
                    float(pose[0] if len(pose) > 0 else 0.0),
                    float(pose[1] if len(pose) > 1 else 0.0),
                    float(pose[2] if len(pose) > 2 else 0.0),
                )
            )
        coherent, _non_coherent = validate_unit_coherency_after_movement(unit, final_positions)
        if not coherent:
            return [f"Move unit: {move_tag.replace('_', ' ')} would break unit coherency."]
    finally:
        _restore_positions(unit, snapshot)
    return []


def plan_deterministic_fight_move(
    game: object,
    unit: object,
    *,
    movement_type: str,
    max_distance: float,
    target_unit_ids: list[str] | None = None,
    deadline: float | None = None,
) -> list[dict[str, Any]]:
    move_tag = str(movement_type or "").strip().lower()
    path_movement_type = _MOVEMENT_TYPE_BY_TAG.get(move_tag)
    snapshot = serialize_attached_unit_positions(unit)
    if path_movement_type is None or unit is None:
        return snapshot
    if bool(getattr(unit, "is_aircraft", False)):
        return snapshot
    game_map = getattr(game, "map", None)
    if game_map is None:
        return snapshot
    if deadline is not None:
        return snapshot

    target_units = _resolve_target_units(game, list(target_unit_ids or []))
    moved_models: list[object] = []
    try:
        for model in attached_unit_models(unit):
            if deadline is not None and time.perf_counter() >= float(deadline):
                break
            if _model_in_base_contact(model, unit=unit, game_map=game_map):
                continue
            current_pose = _model_pose_entry(model)
            chosen = None
            for target in _candidate_destinations(
                game,
                unit=unit,
                model=model,
                movement_type=move_tag,
                max_distance=float(max_distance),
            ):
                if deadline is not None and time.perf_counter() >= float(deadline):
                    break
                path_result = plan_model_path(
                    PathQuery(
                        model=model,
                        target=target,
                        movement_type=path_movement_type,
                        max_distance=float(max_distance),
                        game_map=game_map,
                        target_units=tuple(target_units or ()),
                        moved_models_in_unit=tuple(moved_models),
                        debug_enabled=False,
                    )
                )
                if not bool(path_result.valid) or not path_result.poses:
                    continue
                chosen = {
                    "model_id": str(get_entity_id(model) or ""),
                    "position": [
                        float(path_result.poses[-1].x),
                        float(path_result.poses[-1].y),
                        float(path_result.poses[-1].z),
                    ],
                    "facing": float(math.degrees(path_result.poses[-1].facing)),
                }
                break
            if chosen is None or _positions_match(current_pose, chosen):
                continue
            _apply_position_entry(model, chosen)
            moved_models.append(model)
        planned = serialize_attached_unit_positions(unit)
    finally:
        _restore_positions(unit, snapshot)
    errors = validate_fight_move_positions(
        game,
        unit,
        movement_type=move_tag,
        model_positions=planned,
        max_distance=float(max_distance),
        target_unit_ids=list(target_unit_ids or []),
    )
    if errors:
        return snapshot
    return planned


def _candidate_destinations(
    game: object,
    *,
    unit: object,
    model: object,
    movement_type: str,
    max_distance: float,
) -> list[tuple[float, float, float]]:
    geometry = geometry_profile_for_game(game)
    pose = _model_pose_entry(model)
    position = list(pose.get("position") or [0.0, 0.0, 0.0])
    current_x = float(position[0] if len(position) > 0 else 0.0)
    current_y = float(position[1] if len(position) > 1 else 0.0)
    current_z = float(position[2] if len(position) > 2 else 0.0)
    points: list[tuple[float, float, float]] = []
    seen: set[tuple[float, float, float]] = set()

    def _add(x: float, y: float, z: float) -> None:
        key = (round(float(x), 4), round(float(y), 4), round(float(z), 4))
        if key in seen:
            return
        seen.add(key)
        points.append((float(x), float(y), float(z)))

    for enemy_model in _enemy_models_for_unit(unit=unit, game=getattr(game, "map", None)):
        own_base = getattr(model, "model_base", None)
        enemy_base = getattr(enemy_model, "model_base", None)
        if own_base is None or enemy_base is None:
            continue
        own_radius = float(getattr(own_base, "get_longest_radius", lambda: getattr(own_base, "get_radius", lambda: 0.0)())())
        enemy_radius = float(getattr(enemy_base, "get_longest_radius", lambda: getattr(enemy_base, "get_radius", lambda: 0.0)())())
        contact_radius = base_contact_center_distance(
            own_radius,
            enemy_radius,
            geometry_profile=geometry,
        )
        engagement_radius = engagement_center_distance(
            own_radius,
            enemy_radius,
            geometry_profile=geometry,
        )
        base_angle = math.atan2(current_y - float(enemy_base.y), current_x - float(enemy_base.x))
        angle_offsets = (
            0.0,
            math.radians(15.0),
            math.radians(-15.0),
            math.radians(30.0),
            math.radians(-30.0),
            math.radians(45.0),
            math.radians(-45.0),
            math.radians(60.0),
            math.radians(-60.0),
        )
        preferred_radii = [contact_radius]
        if movement_type == "consolidate":
            preferred_radii.append(engagement_radius)
        for radius in preferred_radii:
            for offset in angle_offsets:
                angle = base_angle + offset
                _add(
                    float(enemy_base.x) + math.cos(angle) * float(radius),
                    float(enemy_base.y) + math.sin(angle) * float(radius),
                    current_z,
                )
        dx = float(enemy_base.x) - current_x
        dy = float(enemy_base.y) - current_y
        distance = math.hypot(dx, dy)
        if distance <= 1e-6:
            continue
        nx = dx / distance
        ny = dy / distance
        for fraction in (1.0, 0.85, 0.7, 0.55, 0.4, 0.25):
            travel = float(max_distance) * float(fraction)
            _add(current_x + (nx * travel), current_y + (ny * travel), current_z)

    if movement_type == "consolidate":
        current_point = Point(current_x, current_y)
        for surface in _objective_control_surfaces_for_game_map(getattr(game, "map", None)):
            shape = surface.get("shape")
            centroid = tuple(surface.get("centroid") or (0.0, 0.0, current_z))
            target_x = float(centroid[0] if len(centroid) > 0 else 0.0)
            target_y = float(centroid[1] if len(centroid) > 1 else 0.0)
            if shape is not None:
                nearest = nearest_points(current_point, shape)[1]
                target_x = float(getattr(nearest, "x", target_x) or target_x)
                target_y = float(getattr(nearest, "y", target_y) or target_y)
            dx = target_x - current_x
            dy = target_y - current_y
            distance = math.hypot(dx, dy)
            if distance <= 1e-6:
                continue
            nx = dx / distance
            ny = dy / distance
            for fraction in (1.0, 0.85, 0.7, 0.55, 0.4, 0.25):
                travel = float(max_distance) * float(fraction)
                _add(current_x + (nx * travel), current_y + (ny * travel), current_z)

    return points


def _resolve_target_units(game: object, target_unit_ids: list[str]) -> list[object]:
    resolver = getattr(game, "_resolve_unit_by_id", None)
    if not callable(resolver):
        return []
    units: list[object] = []
    seen: set[str] = set()
    for raw_value in list(target_unit_ids or []):
        unit_id = str(raw_value or "").strip()
        if not unit_id or unit_id in seen:
            continue
        seen.add(unit_id)
        target = resolver(unit_id)
        if target is not None:
            units.append(target)
    return units


def _enemy_models_for_unit(*, unit: object, game: object) -> list[object]:
    game_map = game
    if game_map is None:
        return []
    own_army_getter = getattr(unit, "get_parent_army", None)
    own_army = own_army_getter() if callable(own_army_getter) else getattr(unit, "parent_army", None)
    enemy_models: list[object] = []
    for other_unit in list(getattr(game_map, "units", []) or []):
        if other_unit is None:
            continue
        other_army_getter = getattr(other_unit, "get_parent_army", None)
        other_army = other_army_getter() if callable(other_army_getter) else getattr(other_unit, "parent_army", None)
        if own_army is not None and other_army is own_army:
            continue
        if bool(getattr(other_unit, "deployed", True)) is False:
            continue
        alive_fn = getattr(other_unit, "is_alive", None)
        if callable(alive_fn) and not bool(alive_fn()):
            continue
        for model in list(getattr(other_unit, "models", []) or []):
            try:
                alive_value = getattr(model, "is_alive", True)
                alive = bool(alive_value() if callable(alive_value) else alive_value)
            except Exception:
                alive = False
            if alive:
                enemy_models.append(model)
    enemy_models.sort(key=lambda model: str(get_entity_id(model) or ""))
    return enemy_models


def _model_in_base_contact(model: object, *, unit: object, game_map: object) -> bool:
    del unit
    if game_map is None:
        return False
    for enemy_model in _enemy_models_for_unit(unit=getattr(model, "parent_unit", None), game=game_map):
        if engagement_state_for_models(model, enemy_model) is CombatEngagementState.BASE_CONTACT:
            return True
    return False


def _objectives_for_game_map(game_map: object) -> list[object]:
    objectives = list(getattr(game_map, "objectives", []) or [])
    objectives.sort(
        key=lambda objective: (
            float(getattr(objective, "x", getattr(getattr(objective, "location", None), "x", 0.0)) or 0.0),
            float(getattr(objective, "y", getattr(getattr(objective, "location", None), "y", 0.0)) or 0.0),
        )
    )
    normalized: list[object] = []
    for objective in objectives:
        location = getattr(objective, "location", None)
        normalized.append(location if location is not None else objective)
    return normalized


def _objective_control_surfaces_for_game_map(game_map: object) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    for objective in list(getattr(game_map, "objectives", []) or []):
        site = resolve_objective_site(objective)
        if site is None or bool(getattr(site, "removed", False)):
            continue
        control_region = getattr(site, "control_region", None)
        shape = control_region_shape(control_region, game_state=getattr(game_map, "game", None)) if control_region is not None else None
        centroid = (
            control_region_centroid(control_region, game_state=getattr(game_map, "game", None))
            if control_region is not None
            else (
                float(getattr(site, "x", 0.0) or 0.0),
                float(getattr(site, "y", 0.0) or 0.0),
                float(getattr(site, "z", 0.0) or 0.0),
            )
        )
        surfaces.append(
            {
                "objective": objective,
                "site": site,
                "shape": shape,
                "centroid": centroid,
            }
        )
    surfaces.sort(
        key=lambda entry: (
            float(tuple(entry.get("centroid") or (0.0, 0.0, 0.0))[0]),
            float(tuple(entry.get("centroid") or (0.0, 0.0, 0.0))[1]),
        )
    )
    return surfaces


def _restore_positions(unit: object, snapshot: list[dict[str, Any]]) -> None:
    snapshot_by_id = {
        str(entry.get("model_id", "") or ""): dict(entry)
        for entry in list(snapshot or [])
        if entry is not None
    }
    for model in attached_unit_models(unit):
        entry = snapshot_by_id.get(str(get_entity_id(model) or "").strip())
        if entry is None:
            continue
        _apply_position_entry(model, entry)


def _apply_position_entry(model: object, entry: dict[str, Any]) -> None:
    pose = list(dict(entry or {}).get("position") or [])
    if len(pose) < 2:
        return
    x = float(pose[0])
    y = float(pose[1])
    z = float(pose[2] if len(pose) > 2 else getattr(getattr(model, "model_base", None), "z", 0.0))
    facing = float(dict(entry or {}).get("facing", getattr(getattr(model, "model_base", None), "facing", 0.0)) or 0.0)
    setter = getattr(model, "set_location", None)
    if callable(setter):
        setter(x, y, z, facing)


def _pose_matches_entry(pose: Any, entry: dict[str, Any], *, tolerance: float = 1e-4) -> bool:
    if pose is None:
        return False
    requested = list(dict(entry or {}).get("position") or [])
    if len(requested) < 2:
        return False
    requested_z = float(requested[2] if len(requested) > 2 else 0.0)
    requested_facing = float(dict(entry or {}).get("facing", 0.0) or 0.0)
    actual_facing = float(math.degrees(float(getattr(pose, "facing", 0.0) or 0.0)))
    return (
        abs(float(getattr(pose, "x", 0.0) or 0.0) - float(requested[0])) <= tolerance
        and abs(float(getattr(pose, "y", 0.0) or 0.0) - float(requested[1])) <= tolerance
        and abs(float(getattr(pose, "z", 0.0) or 0.0) - requested_z) <= tolerance
        and abs(actual_facing - requested_facing) <= 1e-2
    )


def _positions_match(lhs: dict[str, Any], rhs: dict[str, Any], *, tolerance: float = 1e-3) -> bool:
    lhs_pos = list(dict(lhs or {}).get("position") or [])
    rhs_pos = list(dict(rhs or {}).get("position") or [])
    while len(lhs_pos) < 3:
        lhs_pos.append(0.0)
    while len(rhs_pos) < 3:
        rhs_pos.append(0.0)
    lhs_facing = float(dict(lhs or {}).get("facing", 0.0) or 0.0)
    rhs_facing = float(dict(rhs or {}).get("facing", 0.0) or 0.0)
    return (
        abs(float(lhs_pos[0]) - float(rhs_pos[0])) <= tolerance
        and abs(float(lhs_pos[1]) - float(rhs_pos[1])) <= tolerance
        and abs(float(lhs_pos[2]) - float(rhs_pos[2])) <= tolerance
        and abs(lhs_facing - rhs_facing) <= 1e-2
    )


def _model_pose_entry(model: object) -> dict[str, Any]:
    model_id = str(get_entity_id(model) or "").strip()
    getter = getattr(model, "get_location", None)
    if callable(getter):
        location = tuple(getter() or ())
        x = float(location[0] if len(location) > 0 else 0.0)
        y = float(location[1] if len(location) > 1 else 0.0)
        z = float(location[2] if len(location) > 2 else 0.0)
        facing = float(location[3] if len(location) > 3 else getattr(getattr(model, "model_base", None), "facing", 0.0))
    else:
        base = getattr(model, "model_base", None)
        x = float(getattr(base, "x", 0.0) or 0.0)
        y = float(getattr(base, "y", 0.0) or 0.0)
        z = float(getattr(base, "z", 0.0) or 0.0)
        facing = float(getattr(base, "facing", 0.0) or 0.0)
    return {
        "model_id": model_id,
        "position": [x, y, z],
        "facing": facing,
    }
