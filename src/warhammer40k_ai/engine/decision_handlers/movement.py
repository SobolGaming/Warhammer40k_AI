from __future__ import annotations

from typing import Iterable, Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import (
    DECISION_DISEMBARK,
    DECISION_EMBARK,
    DECISION_MOVE_UNIT,
    DECISION_PICK_OBJECTIVE,
    DECISION_PICK_POINT,
    DECISION_RESOLVE_COHERENCY,
    DECISION_SELECT_FLOOR,
    DECISION_SELECT_MOVEMENT_ACTION,
)
from ..decisions import DecisionRequest, DecisionResult
from ._helpers import (
    apply_model_positions,
    find_option,
    get_model,
    get_objective,
    get_unit,
    is_skip_choice,
    validate_model_positions,
    validate_option_choice,
)


def _movement_members(unit) -> list:
    try:
        members = list(unit.get_attached_unit_members() or [])
    except Exception:
        members = []
    return members or [unit]


def _clear_battle_focus_reactive_flags(unit) -> None:
    for member in _movement_members(unit):
        sr = getattr(member, "special_rules", None)
        if not isinstance(sr, dict):
            continue
        for key in (
            "battle_focus_reactive_move_max",
            "battle_focus_reactive_move_source",
            "battle_focus_reactive_move_expires_phase",
        ):
            sr.pop(key, None)


def _validate_select_movement_action(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or "")
    action = str(payload.get("action_type", "") or "")
    if not unit_id:
        return ("Movement action requires unit_id.",)
    if not action:
        return ("Movement action requires action_type.",)
    unit = get_unit(game, unit_id)
    if unit is None:
        return ("Movement action unit not found.",)
    return ()


def _apply_select_movement_action(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    action = str(payload.get("action_type", "") or "")
    unit = get_unit(game, str(payload.get("unit_id", "") or ""))
    if unit is None:
        raise RuntimeError("Movement action unit missing.")
    if action == "stationary":
        try:
            unit._execute_action("remain_stationary", (0, 0, 0), getattr(game, "map", None))
        except Exception as exc:
            raise RuntimeError(f"Stationary action failed: {exc}") from exc
    return None


def _validate_move_unit(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    if not unit_id:
        return ("Move unit requires unit_id.",)
    unit = get_unit(game, unit_id)
    if unit is None:
        return ("Move unit: unit not found.",)
    if bool(result.payload.get("skipped", False)):
        return ()
    model_positions = result.payload.get("model_positions")
    errors = validate_model_positions(game, unit, model_positions, context="Move unit")
    if errors:
        return errors
    return ()


def _apply_move_unit(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    unit = get_unit(game, unit_id)
    if unit is None:
        raise RuntimeError("Move unit: unit not found.")
    movement_type = str(payload.get("movement_type", "") or request.context.get("movement_type", "") or "")
    if bool(result.payload.get("skipped", False)):
        if movement_type == "reactive":
            _clear_battle_focus_reactive_flags(unit)
        return None
    model_positions = list(result.payload.get("model_positions") or [])
    apply_model_positions(game, model_positions)

    members = _movement_members(unit)
    for member in members:
        if movement_type == "advance":
            member.round_state.advanced_this_round = True
        elif movement_type == "fall_back":
            member.round_state.fell_back_this_round = True
        elif movement_type in ("move", "pile_in", "consolidate", "charge"):
            member.round_state.moved_this_round = True
            member.round_state.remained_stationary_this_round = False
        if movement_type == "loping_speed":
            member.mark_loping_speed_used(game)
        if movement_type == "blood_surge":
            member.mark_blood_surge_used(game)
    if movement_type == "reactive":
        _clear_battle_focus_reactive_flags(unit)
    return None


def _validate_resolve_coherency(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    if not unit_id:
        return ("Coherency resolution requires unit_id.",)
    unit = get_unit(game, unit_id)
    if unit is None:
        return ("Coherency resolution: unit not found.",)
    to_remove = result.payload.get("model_ids")
    if not isinstance(to_remove, list) or not to_remove:
        return ("Coherency resolution requires model_ids list.",)
    for model_id in to_remove:
        model = get_model(game, str(model_id or ""))
        if model is None:
            return (f"Model not found: {model_id}",)
        if getattr(model, "parent_unit", None) is not unit:
            return ("Model does not belong to the unit.",)
    return ()


def _apply_resolve_coherency(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    unit = get_unit(game, unit_id)
    if unit is None:
        raise RuntimeError("Coherency resolution: unit not found.")
    to_remove = list(result.payload.get("model_ids") or [])
    for model_id in to_remove:
        model = get_model(game, str(model_id or ""))
        if model is None:
            continue
        try:
            model.wounds = 0
        except Exception:
            pass
        model.die()
    return None


def _validate_embark(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or "")
    transport_id = payload.get("transport_id")
    if not unit_id:
        return ("Embark requires unit_id.",)
    unit = get_unit(game, unit_id)
    transport = get_unit(game, str(transport_id or "")) if transport_id is not None else None
    if unit is None:
        return ("Embark unit not found.",)
    if transport_id is None:
        return ()
    if transport is None:
        return ("Embark transport not found.",)
    if not bool(getattr(transport, "is_transport", False)):
        return ("Embark requires a transport unit.",)
    try:
        if not transport.can_transport(unit):
            return ("Transport cannot embark selected unit.",)
    except Exception:
        return ("Embark validation failed.",)
    return ()


def _apply_embark(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit = get_unit(game, str(payload.get("unit_id", "") or ""))
    transport_id = payload.get("transport_id")
    if unit is None:
        raise RuntimeError("Embark: unit missing.")
    if transport_id is None:
        return None
    transport = get_unit(game, str(transport_id or ""))
    if transport is None:
        raise RuntimeError("Embark: transport missing.")
    unit.embark(transport, game_map=getattr(game, "map", None))
    return None


def _validate_disembark(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or "")
    transport_id = payload.get("transport_id")
    if not unit_id:
        return ("Disembark requires unit_id.",)
    unit = get_unit(game, unit_id)
    if unit is None:
        return ("Disembark unit not found.",)
    if transport_id is None:
        return ()
    transport = get_unit(game, str(transport_id or ""))
    if transport is None:
        return ("Disembark transport not found.",)
    model_positions = result.payload.get("model_positions")
    if model_positions is not None:
        errors = validate_model_positions(game, unit, model_positions, context="Disembark")
        if errors:
            return errors
        game_map = getattr(game, "map", None)
        if game_map is None:
            return ("Disembark requires game map for manual positions.",)
        for entry in list(model_positions or []):
            model = get_model(game, str(entry.get("model_id", "") or ""))
            if model is None:
                continue
            pos = entry.get("position") or []
            if len(pos) < 2:
                continue
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else float(getattr(model.model_base, "z", 0.0))
            check = unit.validate_disembark_placement(
                model,
                x,
                y,
                z,
                transport_unit=transport,
                game_map=game_map,
                max_distance=3.0,
                require_not_in_engagement=True,
            )
            if not bool(check.get("valid", False)):
                reason = str(check.get("reason", "") or "Invalid disembark placement.")
                return (reason,)
    return ()


def _apply_disembark(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit = get_unit(game, str(payload.get("unit_id", "") or ""))
    transport_id = payload.get("transport_id")
    if unit is None:
        raise RuntimeError("Disembark: unit missing.")
    if transport_id is None:
        return None
    transport = get_unit(game, str(transport_id or ""))
    if transport is None:
        raise RuntimeError("Disembark: transport missing.")
    model_positions = result.payload.get("model_positions")
    if model_positions is not None:
        apply_model_positions(game, list(model_positions or []))
        game_map = getattr(game, "map", None)
        if game_map is None:
            raise RuntimeError("Disembark requires an active game map.")
        return bool(
            unit.finalize_manual_disembark(
                game_map=game_map,
                transport_unit=transport,
                destroyed_transport=False,
                emergency=False,
                current_turn=getattr(game, "turn", 1),
            )
        )
    unit.disembark(game_map=getattr(game, "map", None), transport_unit=transport, current_turn=getattr(game, "turn", 1))
    return None


def _validate_pick_point(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = dict(result.payload or {})
    point = payload.get("point")
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return ("Point selection requires point coordinates.",)
    try:
        float(point[0])
        float(point[1])
        if len(point) > 2:
            float(point[2])
    except (TypeError, ValueError):
        return ("Point coordinates must be numeric.",)
    return ()


def _apply_pick_point(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    if is_skip_choice(request, result):
        return None
    payload = dict(result.payload or {})
    point = payload.get("point") or []
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    x = float(point[0])
    y = float(point[1])
    if len(point) > 2:
        z = float(point[2])
        return (x, y, z)
    return (x, y)


def _validate_pick_objective(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = dict(result.payload or {})
    objective_id = payload.get("objective_id")
    if not objective_id:
        opt = find_option(request, result.option_id)
        opt_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
        objective_id = opt_payload.get("objective_id")
    if not objective_id:
        return ("Objective selection requires objective_id.",)
    if get_objective(game, str(objective_id or "")) is None:
        return ("Objective not found.",)
    return ()


def _apply_pick_objective(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    if is_skip_choice(request, result):
        return None
    payload = dict(result.payload or {})
    objective_id = payload.get("objective_id")
    if not objective_id:
        opt = find_option(request, result.option_id)
        opt_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
        objective_id = opt_payload.get("objective_id")
    if not objective_id:
        return None
    return get_objective(game, str(objective_id or ""))


def _validate_select_floor(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = dict(result.payload or {})
    floor = payload.get("floor")
    if floor is None:
        opt = find_option(request, result.option_id)
        opt_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
        floor = opt_payload.get("floor")
    if floor is None:
        return ("Floor selection requires floor value.",)
    try:
        int(floor)
    except (TypeError, ValueError):
        return ("Floor value must be an integer.",)
    return ()


def _apply_select_floor(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    if is_skip_choice(request, result):
        return None
    payload = dict(result.payload or {})
    floor = payload.get("floor")
    if floor is None:
        opt = find_option(request, result.option_id)
        opt_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
        floor = opt_payload.get("floor")
    if floor is None:
        return None
    try:
        return int(floor)
    except (TypeError, ValueError):
        return None


register_decision_handler(
    DECISION_SELECT_MOVEMENT_ACTION,
    validate=_validate_select_movement_action,
    apply=_apply_select_movement_action,
)
register_decision_handler(DECISION_MOVE_UNIT, validate=_validate_move_unit, apply=_apply_move_unit)
register_decision_handler(
    DECISION_RESOLVE_COHERENCY,
    validate=_validate_resolve_coherency,
    apply=_apply_resolve_coherency,
)
register_decision_handler(DECISION_EMBARK, validate=_validate_embark, apply=_apply_embark)
register_decision_handler(DECISION_DISEMBARK, validate=_validate_disembark, apply=_apply_disembark)
register_decision_handler(DECISION_PICK_POINT, validate=_validate_pick_point, apply=_apply_pick_point)
register_decision_handler(DECISION_PICK_OBJECTIVE, validate=_validate_pick_objective, apply=_apply_pick_objective)
register_decision_handler(DECISION_SELECT_FLOOR, validate=_validate_select_floor, apply=_apply_select_floor)
