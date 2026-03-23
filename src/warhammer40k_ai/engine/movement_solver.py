from __future__ import annotations

import math
import time
from typing import Any

from .decisions import CandidateAction, DecisionRequest
from .movement_intent import MovementIntent
from .path_witness import build_model_path_witness_for_unit, current_model_positions


def _resolve_unit(game: object, unit_id: str):
    resolver = getattr(game, "_resolve_unit_by_id", None)
    if callable(resolver):
        unit = resolver(unit_id)
        if unit is not None:
            return unit
    for player in list(getattr(game, "players", []) or []):
        army = getattr(player, "army", None)
        for unit in list(getattr(army, "units", []) or []):
            uid = str(getattr(unit, "id", "") or getattr(unit, "_id", "") or "")
            if uid == str(unit_id or ""):
                return unit
    return None


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _entry_position(entry: dict[str, Any]) -> tuple[float, float, float]:
    position = list(dict(entry or {}).get("position", []) or [])
    return (
        _safe_float(position[0] if len(position) > 0 else 0.0),
        _safe_float(position[1] if len(position) > 1 else 0.0),
        _safe_float(position[2] if len(position) > 2 else 0.0),
    )


def _model_entries(unit: object) -> list[object]:
    models = list(getattr(unit, "models", []) or [])
    models.sort(key=lambda model: str(getattr(model, "id", "") or getattr(model, "_id", "") or ""))
    return [model for model in models if model is not None]


def _unit_army(unit: object) -> object | None:
    get_parent_army = getattr(unit, "get_parent_army", None)
    if callable(get_parent_army):
        return get_parent_army()
    return getattr(unit, "parent_army", None)


def _position_centroid(model_positions: list[dict[str, Any]]) -> tuple[float, float]:
    points: list[tuple[float, float]] = []
    for entry in list(model_positions or []):
        position = list(dict(entry or {}).get("position", []) or [])
        if len(position) < 2:
            continue
        points.append((_safe_float(position[0]), _safe_float(position[1])))
    if not points:
        return (0.0, 0.0)
    return (
        sum(point[0] for point in points) / float(len(points)),
        sum(point[1] for point in points) / float(len(points)),
    )


def _alive_unit_positions(unit: object) -> list[tuple[float, float, float]]:
    positions: list[tuple[float, float, float]] = []
    for model in _model_entries(unit):
        is_alive_value = getattr(model, "is_alive", True)
        is_alive = bool(is_alive_value() if callable(is_alive_value) else is_alive_value)
        if not is_alive:
            continue
        getter = getattr(model, "get_location", None)
        if not callable(getter):
            continue
        location = getter()
        if not isinstance(location, (list, tuple)) or len(location) < 2:
            continue
        positions.append(
            (
                _safe_float(location[0]),
                _safe_float(location[1]),
                _safe_float(location[2] if len(location) > 2 else 0.0),
            )
        )
    return positions


def _enemy_centroids(game: object, unit: object) -> list[tuple[float, float]]:
    own_army = _unit_army(unit)
    centroids: list[tuple[float, float]] = []
    for player in list(getattr(game, "players", []) or []):
        army = getattr(player, "army", None)
        if army is None:
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else None
        if army is None or army is own_army:
            continue
        for other_unit in list(getattr(army, "units", []) or []):
            if other_unit is None:
                continue
            positions = _alive_unit_positions(other_unit)
            if not positions:
                continue
            count = float(len(positions))
            centroids.append(
                (
                    sum(point[0] for point in positions) / count,
                    sum(point[1] for point in positions) / count,
                )
            )
    return centroids


def _objective_points(game: object) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for objective in list(getattr(game, "objectives", []) or []):
        location = getattr(objective, "location", None)
        x = getattr(location, "x", None)
        y = getattr(location, "y", None)
        if x is None or y is None:
            continue
        points.append((_safe_float(x), _safe_float(y)))
    return points


def _distance_2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _nearest_distance(origin: tuple[float, float], targets: list[tuple[float, float]]) -> float:
    if not targets:
        return 0.0
    return min(_distance_2d(origin, target) for target in targets)


def _resolve_target_units(game: object, target_unit_ids: list[str]) -> list[object]:
    units: list[object] = []
    seen: set[str] = set()
    for raw_value in list(target_unit_ids or []):
        unit_id = str(raw_value or "").strip()
        if not unit_id or unit_id in seen:
            continue
        seen.add(unit_id)
        unit = _resolve_unit(game, unit_id)
        if unit is not None:
            units.append(unit)
    return units


def _apply_positions_to_unit(unit: object, model_positions: list[dict[str, Any]]) -> None:
    models_by_id = {
        str(getattr(model, "id", "") or getattr(model, "_id", "") or ""): model
        for model in _model_entries(unit)
    }
    for entry in list(model_positions or []):
        model_id = str(dict(entry or {}).get("model_id", "") or "")
        model = models_by_id.get(model_id)
        if model is None:
            continue
        x, y, z = _entry_position(dict(entry or {}))
        facing = _safe_float(dict(entry or {}).get("facing", 0.0), 0.0)
        setter = getattr(model, "set_location", None)
        if callable(setter):
            setter(float(x), float(y), float(z), float(facing))


def _charge_end_state_valid(
    unit: object,
    *,
    model_positions: list[dict[str, Any]],
    target_units: list[object],
    game_map: object,
) -> bool:
    validate_charge_end_state = getattr(unit, "validate_charge_end_state", None)
    if not callable(validate_charge_end_state):
        return False
    snapshot = current_model_positions(unit)
    _apply_positions_to_unit(unit, model_positions)
    try:
        ok, _reason = validate_charge_end_state(target_units, game_map)
    finally:
        _apply_positions_to_unit(unit, snapshot)
    return bool(ok)


def _translate_positions_by_delta(
    game: object,
    *,
    start_positions: list[dict[str, Any]],
    delta_x: float,
    delta_y: float,
    facing: float,
) -> list[dict[str, Any]]:
    translated: list[dict[str, Any]] = []
    game_map = getattr(game, "map", None)
    get_height = getattr(game_map, "get_height_at_point", None)
    for entry in list(start_positions or []):
        model_id = str(dict(entry or {}).get("model_id", "") or "")
        if not model_id:
            continue
        x, y, z = _entry_position(dict(entry or {}))
        next_x = float(x + delta_x)
        next_y = float(y + delta_y)
        next_z = float(z)
        if callable(get_height):
            next_z = _safe_float(get_height(next_x, next_y), next_z)
        translated.append(
            {
                "model_id": model_id,
                "position": [next_x, next_y, next_z],
                "facing": float(facing),
            }
        )
    return translated


def _build_charge_model_positions(
    game: object,
    *,
    unit: object,
    start_positions: list[dict[str, Any]],
    destination: tuple[float, float, float],
) -> list[dict[str, Any]]:
    if not start_positions:
        return []
    start_anchor = _entry_position(dict(start_positions[0] or {}))
    delta_x = float(destination[0]) - float(start_anchor[0])
    delta_y = float(destination[1]) - float(start_anchor[1])
    facing = math.degrees(math.atan2(delta_y, delta_x)) if abs(delta_x) > 1e-6 or abs(delta_y) > 1e-6 else 0.0

    calculate_positions = getattr(unit, "calculate_model_positions", None)
    if callable(calculate_positions):
        game_map = getattr(game, "map", None)
        boundary_repulsors = None
        repulsor_builder = getattr(unit, "_get_reduced_boundary_repulsors", None)
        if callable(repulsor_builder) and game_map is not None:
            try:
                boundary_repulsors = repulsor_builder(game_map)
            except Exception:
                boundary_repulsors = None
        try:
            generated = (
                calculate_positions(
                    float(destination[0]),
                    float(destination[1]),
                    game_map,
                    boundary_repulsors=boundary_repulsors,
                )
                if boundary_repulsors is not None
                else calculate_positions(float(destination[0]), float(destination[1]), game_map)
            )
        except TypeError:
            generated = calculate_positions(float(destination[0]), float(destination[1]), game_map)
        if isinstance(generated, list) and len(generated) == len(start_positions):
            model_positions: list[dict[str, Any]] = []
            for entry, generated_position in zip(start_positions, generated):
                if not isinstance(generated_position, (list, tuple)) or len(generated_position) < 2:
                    return []
                position = [
                    _safe_float(generated_position[0]),
                    _safe_float(generated_position[1]),
                    _safe_float(generated_position[2] if len(generated_position) > 2 else destination[2]),
                ]
                generated_facing = generated_position[3] if len(generated_position) > 3 else facing
                model_positions.append(
                    {
                        "model_id": str(dict(entry or {}).get("model_id", "") or ""),
                        "position": position,
                        "facing": float(_safe_float(generated_facing, facing)),
                    }
                )
            return model_positions

    return _translate_positions_by_delta(
        game,
        start_positions=start_positions,
        delta_x=delta_x,
        delta_y=delta_y,
        facing=facing,
    )


def _charge_candidate(
    game: object,
    *,
    request: DecisionRequest,
    unit: object,
    confirm_option: object,
    start_positions: list[dict[str, Any]],
    max_distance: float,
    target_units: list[object],
    rules_bundle_id: str,
    intent: MovementIntent,
) -> CandidateAction | None:
    if not target_units:
        return None
    destination_finder = getattr(game, "_find_charge_destination", None)
    if not callable(destination_finder):
        return None
    game_map = getattr(game, "map", None)
    if game_map is None:
        return None
    destination = None
    for target_unit in list(target_units or []):
        destination = destination_finder(unit, target_unit, max_distance=float(max_distance))
        if destination is None:
            continue
        model_positions = _build_charge_model_positions(
            game,
            unit=unit,
            start_positions=start_positions,
            destination=destination,
        )
        if not model_positions:
            continue
        if not _charge_end_state_valid(
            unit,
            model_positions=model_positions,
            target_units=target_units,
            game_map=game_map,
        ):
            continue
        confirm_action_id = request.action_id_for_option_id(getattr(confirm_option, "option_id", None))
        confirm_payload = dict(getattr(confirm_option, "payload", {}) or {})
        confirm_payload.pop("action_id", None)
        confirm_payload["model_positions"] = model_positions
        witness = build_model_path_witness_for_unit(
            unit=unit,
            model_positions=model_positions,
            movement_type="charge",
        )
        store = getattr(game, "path_witness_store", None)
        if store is None:
            raise RuntimeError("Game is missing path_witness_store.")
        path_witness_ref = store.put(witness)
        origin = _position_centroid(start_positions)
        new_origin = _position_centroid(model_positions)
        target_points = [
            (_safe_float(point[0]), _safe_float(point[1]))
            for point in (_alive_unit_positions(target_unit) or [])
        ]
        enemy_distance_delta = 0.0
        if target_points:
            enemy_distance_delta = _nearest_distance(origin, target_points) - _nearest_distance(new_origin, target_points)
        movement_distance = max(0.0, _distance_2d(origin, new_origin))
        rules_provenance_refs = [rules_bundle_id] if rules_bundle_id else []
        return CandidateAction(
            action_id=str(confirm_action_id),
            params=confirm_payload,
            metadata={
                "candidate_kind": "charge",
                "solver_ms": 0,
                "fallback_mode": False,
                "intent_hash": intent.stable_hash(),
                "path_witness_ref": path_witness_ref,
                "movement_distance_inches": float(round(movement_distance, 4)),
                "distance_to_enemy_delta": float(round(enemy_distance_delta, 4)),
                "distance_to_objective_delta": 0.0,
                "screen_coverage_score": 0.0,
                "coherency_score": 0.0,
                "threat_score": 1.0,
                "projected_score_delta_next_window": max(0.0, enemy_distance_delta) * 0.25,
                "projected_score_delta_round": max(0.0, enemy_distance_delta) * 0.35,
                "projected_deny_delta_next_window": 0.0,
                "projected_control_delta": max(0.0, enemy_distance_delta) * 0.1,
                "projected_action_enablement_delta": 1.0 + max(0.0, enemy_distance_delta) * 0.2,
                "projected_exposure_delta": 0.0,
                "projected_trade_ev": max(0.0, enemy_distance_delta) * 0.1,
                "projected_melee_staging_delta": max(0.0, enemy_distance_delta),
                "cover_delta": 0.0,
                "los_delta": 0.0,
                "resource_delta": 0.0,
                "rules_provenance_refs": rules_provenance_refs,
            },
        )
    return None


def _movement_goal(
    game: object,
    unit: object,
    start_positions: list[dict[str, Any]],
    *,
    intent: MovementIntent,
    movement_type: str,
) -> tuple[float, float]:
    origin = _position_centroid(start_positions)
    enemy_points = _enemy_centroids(game, unit)
    objective_points = _objective_points(game)
    weights = dict(intent.weights or {})
    score_weight = max(0.0, _safe_float(weights.get("score"), 0.0))
    deny_weight = max(0.0, _safe_float(weights.get("deny"), 0.0))
    trade_weight = max(0.0, _safe_float(weights.get("trade"), 0.0))
    safety_weight = max(0.0, _safe_float(weights.get("safety"), 0.0))

    desired_affordances = {
        str(value or "").strip().upper()
        for value in list(intent.desired_affordances or [])
        if str(value or "").strip()
    }
    score_focus = 0.0
    if desired_affordances & {
        "HOLD_SCORE_SOURCE",
        "STAGE_FOR_NEXT_WINDOW",
        "SAFE_STAGING",
        "MIDBOARD_STAGING",
    }:
        score_focus += 0.2
    if desired_affordances & {"SCREEN_DEPTH", "RESERVE_DENIAL", "FORWARD_SCREEN"}:
        score_focus += 0.1

    enemy_focus = 0.25 + (trade_weight * 0.45) + (deny_weight * 0.2)
    objective_focus = 0.35 + (score_weight * 0.8) + score_focus + (safety_weight * 0.1)
    if str(movement_type or "").strip().lower() == "advance":
        enemy_focus += 0.1

    best_goal = origin
    best_score = float("-inf")
    for goal in list(enemy_points) + list(objective_points):
        enemy_delta = 0.0
        objective_delta = 0.0
        if enemy_points:
            enemy_delta = _nearest_distance(origin, enemy_points) - _nearest_distance(goal, enemy_points)
        if objective_points:
            objective_delta = _nearest_distance(origin, objective_points) - _nearest_distance(goal, objective_points)
        score = enemy_delta * enemy_focus + objective_delta * objective_focus
        if score > best_score:
            best_score = score
            best_goal = goal
    return best_goal


def _translate_model_positions(
    game: object,
    *,
    start_positions: list[dict[str, Any]],
    goal: tuple[float, float],
    max_distance: float,
    unit: object,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    if not start_positions or max_distance <= 0.0:
        return list(start_positions), {
            "movement_distance": 0.0,
            "enemy_distance_delta": 0.0,
            "objective_distance_delta": 0.0,
        }

    origin = _position_centroid(start_positions)
    dx = float(goal[0]) - float(origin[0])
    dy = float(goal[1]) - float(origin[1])
    distance = math.hypot(dx, dy)
    if distance <= 1e-6:
        return list(start_positions), {
            "movement_distance": 0.0,
            "enemy_distance_delta": 0.0,
            "objective_distance_delta": 0.0,
        }

    enemy_points = _enemy_centroids(game, unit)
    objective_points = _objective_points(game)
    desired_standoff = 9.0
    travel = min(float(max_distance), max(0.0, distance - desired_standoff))
    if travel <= 0.05:
        travel = min(float(max_distance), distance)
    if travel <= 0.05:
        return list(start_positions), {
            "movement_distance": 0.0,
            "enemy_distance_delta": 0.0,
            "objective_distance_delta": 0.0,
        }

    nx = dx / distance
    ny = dy / distance
    shift_x = nx * travel
    shift_y = ny * travel
    facing = math.degrees(math.atan2(ny, nx))

    translated: list[dict[str, Any]] = []
    game_map = getattr(game, "map", None)
    for entry in list(start_positions or []):
        model_id = str(dict(entry or {}).get("model_id", "") or "")
        position = list(dict(entry or {}).get("position", []) or [])
        if not model_id or len(position) < 2:
            continue
        next_x = _safe_float(position[0]) + shift_x
        next_y = _safe_float(position[1]) + shift_y
        next_z = _safe_float(position[2] if len(position) > 2 else 0.0)
        get_height = getattr(game_map, "get_height_at_point", None)
        if callable(get_height):
            next_z = _safe_float(get_height(next_x, next_y), next_z)
        translated.append(
            {
                "model_id": model_id,
                "position": [float(next_x), float(next_y), float(next_z)],
                "facing": float(facing),
            }
        )

    new_origin = _position_centroid(translated)
    enemy_delta = 0.0
    objective_delta = 0.0
    if enemy_points:
        enemy_delta = _nearest_distance(origin, enemy_points) - _nearest_distance(new_origin, enemy_points)
    if objective_points:
        objective_delta = _nearest_distance(origin, objective_points) - _nearest_distance(new_origin, objective_points)
    return translated, {
        "movement_distance": float(travel),
        "enemy_distance_delta": float(enemy_delta),
        "objective_distance_delta": float(objective_delta),
    }


def _fallback_candidates(request: DecisionRequest) -> tuple[list[CandidateAction], list[bool]]:
    fallback: list[CandidateAction] = []
    for candidate in list(request.candidates or []):
        metadata = dict(candidate.metadata or {})
        metadata["fallback_mode"] = True
        fallback.append(
            CandidateAction(
                action_id=str(candidate.action_id),
                params=dict(candidate.params or {}),
                metadata=metadata,
            )
        )
    mask = [bool(v) for v in list(request.mask or [])]
    if len(mask) != len(fallback):
        mask = [True] * len(fallback)
    return fallback, mask


def _solver_candidates(game: object, request: DecisionRequest, intent: MovementIntent) -> tuple[list[CandidateAction], list[bool]]:
    ctx = dict(getattr(request, "context", {}) or {})
    movement_type = str(ctx.get("movement_type", "move") or "move")
    unit_id = str(ctx.get("unit_id", "") or "")
    unit = _resolve_unit(game, unit_id)
    skip_option = None
    confirm_option = None
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        action = str(payload.get("action", "") or "").lower()
        if action == "skip":
            skip_option = option
        else:
            confirm_option = option

    candidates: list[CandidateAction] = []
    if skip_option is not None:
        skip_action_id = request.action_id_for_option_id(getattr(skip_option, "option_id", None))
        skip_payload = dict(getattr(skip_option, "payload", {}) or {})
        skip_payload.pop("action_id", None)
        candidates.append(
            CandidateAction(
                action_id=str(skip_action_id),
                params=skip_payload,
                metadata={
                    "candidate_kind": "noop",
                    "solver_ms": 0,
                    "fallback_mode": False,
                    "intent_hash": intent.stable_hash(),
                },
            )
        )

    if confirm_option is not None and unit is not None:
        start_positions = current_model_positions(unit)
        try:
            max_distance = float(ctx.get("max_distance", 0.0) or 0.0)
        except (TypeError, ValueError):
            max_distance = 0.0
        if max_distance <= 0.0:
            max_distance = 6.0
        rules_bundle_id = str(ctx.get("rules_bundle_id", "") or "")
        if movement_type == "charge":
            target_units = _resolve_target_units(game, list(ctx.get("target_unit_ids", []) or []))
            charge_candidate = _charge_candidate(
                game,
                request=request,
                unit=unit,
                confirm_option=confirm_option,
                start_positions=start_positions,
                max_distance=float(max_distance),
                target_units=target_units,
                rules_bundle_id=rules_bundle_id,
                intent=intent,
            )
            if charge_candidate is not None:
                candidates.append(charge_candidate)
        else:
            confirm_action_id = request.action_id_for_option_id(getattr(confirm_option, "option_id", None))
            confirm_payload = dict(getattr(confirm_option, "payload", {}) or {})
            confirm_payload.pop("action_id", None)
            goal = _movement_goal(
                game,
                unit,
                start_positions,
                intent=intent,
                movement_type=movement_type,
            )
            model_positions, movement_metrics = _translate_model_positions(
                game,
                start_positions=start_positions,
                goal=goal,
                max_distance=float(max_distance),
                unit=unit,
            )
            confirm_payload["model_positions"] = model_positions
            witness = build_model_path_witness_for_unit(
                unit=unit,
                model_positions=model_positions,
                movement_type=movement_type,
            )
            store = getattr(game, "path_witness_store", None)
            if store is None:
                raise RuntimeError("Game is missing path_witness_store.")
            path_witness_ref = store.put(witness)
            weights = dict(intent.weights or {})
            score_weight = float(weights.get("score", 0.0))
            deny_weight = float(weights.get("deny", 0.0))
            safety_weight = float(weights.get("safety", 0.0))
            coherency_weight = float(weights.get("coherency", 0.0))
            action_enable_weight = float(weights.get("action_enable", 0.0))
            trade_weight = float(weights.get("trade", 0.0))
            movement_distance = max(0.0, _safe_float(movement_metrics.get("movement_distance"), 0.0))
            enemy_distance_delta = max(0.0, _safe_float(movement_metrics.get("enemy_distance_delta"), 0.0))
            objective_distance_delta = max(0.0, _safe_float(movement_metrics.get("objective_distance_delta"), 0.0))
            rules_provenance_refs = [rules_bundle_id] if rules_bundle_id else []
            candidates.append(
                CandidateAction(
                    action_id=str(confirm_action_id),
                    params=confirm_payload,
                    metadata={
                        "candidate_kind": "move",
                        "solver_ms": 0,
                        "fallback_mode": False,
                        "intent_hash": intent.stable_hash(),
                        "path_witness_ref": path_witness_ref,
                        "movement_distance_inches": float(round(movement_distance, 4)),
                        "distance_to_enemy_delta": float(round(enemy_distance_delta, 4)),
                        "distance_to_objective_delta": float(round(objective_distance_delta, 4)),
                        "screen_coverage_score": float(deny_weight + action_enable_weight),
                        "coherency_score": coherency_weight,
                        "threat_score": float(max(0.0, 1.0 - safety_weight)),
                        "projected_score_delta_next_window": score_weight * (1.0 + objective_distance_delta * 0.35 + enemy_distance_delta * 0.2),
                        "projected_score_delta_round": score_weight * (1.4 + objective_distance_delta * 0.45 + enemy_distance_delta * 0.25),
                        "projected_deny_delta_next_window": deny_weight * (1.0 + enemy_distance_delta * 0.25),
                        "projected_control_delta": (score_weight + deny_weight) * (0.7 + objective_distance_delta * 0.3 + enemy_distance_delta * 0.1),
                        "projected_action_enablement_delta": action_enable_weight * (1.0 + movement_distance * 0.12 + enemy_distance_delta * 0.14),
                        "projected_exposure_delta": -safety_weight + movement_distance * 0.02 - objective_distance_delta * 0.01,
                        "projected_trade_ev": trade_weight - (1.0 - safety_weight) * 0.25 + enemy_distance_delta * 0.08,
                        "projected_melee_staging_delta": enemy_distance_delta * 0.1,
                        "cover_delta": safety_weight * 0.5,
                        "los_delta": score_weight * 0.25 - safety_weight * 0.15 + objective_distance_delta * 0.03,
                        "resource_delta": -max(0.0, action_enable_weight * 0.1),
                        "rules_provenance_refs": rules_provenance_refs,
                    },
                )
            )

    candidates.sort(key=lambda candidate: str(candidate.action_id))
    top_k = int(ctx.get("movement_top_k", 2) or 2)
    if top_k > 0:
        candidates = candidates[:top_k]
    mask = [True] * len(candidates)
    return candidates, mask


def generate_move_unit_candidates(game: object, request: DecisionRequest, intent: MovementIntent) -> tuple[list[CandidateAction], list[bool], int, bool]:
    ctx = dict(getattr(request, "context", {}) or {})
    budget_ms = int(ctx.get("time_budget_ms", 0) or 0)
    time_manager = getattr(game, "time_manager", None)
    if time_manager is None or budget_ms <= 0:
        start = time.perf_counter()
        candidates, mask = _solver_candidates(game, request, intent)
        wall_clock_ms = int(round((time.perf_counter() - start) * 1000.0))
        return candidates, mask, wall_clock_ms, False

    def _action(_deadline: float):
        return _solver_candidates(game, request, intent)

    def _fallback():
        return _fallback_candidates(request)

    (candidates, mask), fallback_mode, wall_clock_ms = time_manager.run_with_time_budget(
        budget_ms=budget_ms,
        action=_action,
        fallback=_fallback,
    )
    return candidates, mask, int(wall_clock_ms), bool(fallback_mode)
