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
from ...utility.entity_ids import get_entity_id


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


def _maybe_request_move_modifier_choice(game: object, unit: object, *, action_type: str) -> None:
    if unit is None or not bool(getattr(game, "is_authoritative", True)):
        return
    try:
        from ..decision_kinds import DECISION_CHOOSE_MOVE_MODIFIER_IGNORES
        from ..decisions import DecisionOption, DecisionRequest
        from ...rules.wrathful_presence import driven_by_ultimate_rage_applies, DRIVEN_BY_ULTIMATE_RAGE_NAME
        from ...rules.emperors_children import INTERNAL_RIVALRIES_NAME
        from ...utility.modifier_choice import CHOICE_LABELS, options_for_numeric_modifiers
    except Exception:
        return
    army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
    mgr = None
    if army is not None:
        mgr = getattr(army, "emperors_children", None)
        if mgr is None:
            mgr = getattr(army, "emperors_children_detachments", None)
    internal_rivalries = bool(mgr and getattr(mgr, "internal_rivalries_applies", lambda _u: False)(unit))
    driven_by_rage = bool(driven_by_ultimate_rage_applies(unit, game_map=getattr(game, "map", None)))
    if not internal_rivalries and not driven_by_rage:
        return
    ability_name = INTERNAL_RIVALRIES_NAME if internal_rivalries else DRIVEN_BY_ULTIMATE_RAGE_NAME
    try:
        if getattr(unit.round_state, "move_modifier_choice", None):
            return
    except Exception:
        pass
    queue = getattr(game, "decision_queue", None)
    if queue is not None and hasattr(queue, "list"):
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_MOVE_MODIFIER_IGNORES:
                continue
            ctx = getattr(req, "context", {}) or {}
            if str(ctx.get("unit_id", "")) == str(get_entity_id(unit)):
                return

    try:
        model = next((m for m in list(getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)), None)
    except Exception:
        model = None
    if model is None:
        return
    try:
        base_val = int(getattr(model, "_movement", getattr(model, "movement", 0)) or 0)
    except Exception:
        base_val = 0
    try:
        mods, _scabrous, _map = unit._collect_characteristic_modifiers(
            model,
            "movement",
            base_val=base_val,
            base_raw=getattr(model, "_movement_raw", None),
            game_map=getattr(game, "map", None),
        )
    except Exception:
        mods = []
    options = options_for_numeric_modifiers(mods, base_val=base_val)
    if not options:
        return
    req_options = [DecisionOption.create(CHOICE_LABELS.get(opt, str(opt)), payload={"choice": opt}) for opt in options]
    request = DecisionRequest.create(
        DECISION_CHOOSE_MOVE_MODIFIER_IGNORES,
        "Choose which modifiers to ignore.",
        player_id=getattr(getattr(unit.get_parent_army(), "player", None), "id", None),
        options=req_options,
        context={
            "unit_id": get_entity_id(unit),
            "action_type": str(action_type or ""),
            "ability_name": ability_name,
        },
    )
    if hasattr(game, "request_decision"):
        game.request_decision(request)
    try:
        unit.round_state.move_modifier_choice_pending = True
    except Exception:
        pass


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
    elif action == "advance":
        _maybe_request_move_modifier_choice(game, unit, action_type=action)
        if bool(getattr(game, "is_authoritative", True)):
            try:
                unit.prepare_advance()
            except Exception as exc:
                raise RuntimeError(f"Advance roll request failed: {exc}") from exc
    elif action in ("move", "fall_back"):
        _maybe_request_move_modifier_choice(game, unit, action_type=action)
        if action == "move":
            try:
                player = getattr(getattr(unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            try:
                queue_fn = getattr(game, "_queue_movement_phase_normal_move_weapon_attacks_bonus", None)
                if callable(queue_fn):
                    queue_fn(player=player, unit=unit)
            except Exception:
                pass
            try:
                queue_fn = getattr(game, "_queue_movement_phase_flickerjump", None)
                if callable(queue_fn):
                    queue_fn(player=player, unit=unit)
            except Exception:
                pass
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
    ctx = dict(getattr(request, "context", {}) or {})
    allow_skip = bool(ctx.get("allow_skip", True))
    if is_skip_choice(request, result):
        if not allow_skip:
            return ("Move unit: skipping is not allowed for this placement.",)
        return ()
    model_positions = result.payload.get("model_positions")
    errors = validate_model_positions(game, unit, model_positions, context="Move unit")
    if errors:
        return errors
    allowed_ids = ctx.get("allowed_model_ids")
    placement_kind = str(ctx.get("placement_kind", "") or "")
    if allowed_ids is not None:
        allowed_set = {str(v) for v in list(allowed_ids or []) if v is not None}
        if not allowed_set:
            return ("Move unit: allowed_model_ids is empty.",)
        seen: set[str] = set()
        for entry in list(model_positions or []):
            mid = str(entry.get("model_id", "") or "")
            if not mid:
                return ("Move unit: model_positions missing model_id.",)
            if mid in seen:
                return ("Move unit: duplicate model_id in model_positions.",)
            seen.add(mid)
        if seen != allowed_set:
            return ("Move unit: model_positions must include all and only allowed_model_ids.",)
    if placement_kind or allowed_ids is not None:
        placement_errors = _validate_placement_positions(
            game,
            unit,
            model_positions,
            allowed_ids=allowed_ids,
            placement_kind=placement_kind,
        )
        if placement_errors:
            return placement_errors
    return ()


def _validate_placement_positions(
    game: object,
    unit: object,
    model_positions: object,
    *,
    allowed_ids: object = None,
    placement_kind: str | None = None,
) -> Sequence[str]:
    if not isinstance(model_positions, list) or not model_positions:
        return ("Move unit: placement requires model_positions.",)
    game_map = getattr(game, "map", None)
    if game_map is None:
        return ()

    from ...battlefield.map import validate_ruins_placement
    from ...utility.placement_validation import bases_overlap_3d
    from ...utility.calcs import validate_unit_coherency_after_movement
    from ...utility.entity_ids import get_entity_id

    allowed_set = None
    if allowed_ids is not None:
        allowed_set = {str(v) for v in list(allowed_ids or []) if v is not None}

    positions_by_id: dict[str, tuple[float, float, float, float]] = {}
    candidate_bases: dict[str, object] = {}

    collision_fn = getattr(game_map, "check_collision_with_obstacles", None)
    if not callable(collision_fn):
        collision_fn = getattr(game_map, "check_collision_with_terrain", None)

    for entry in list(model_positions or []):
        mid = str(entry.get("model_id", "") or "")
        if not mid:
            return ("Move unit: model_positions missing model_id.",)
        model = get_model(game, mid)
        if model is None:
            return (f"Move unit: model not found: {mid}",)
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return ("Move unit: model_positions missing position.",)
        x = float(pos[0])
        y = float(pos[1])
        z = float(pos[2]) if len(pos) > 2 else float(getattr(model.model_base, "z", 0.0))
        facing = entry.get("facing", None)
        if facing is None:
            facing = float(getattr(model.model_base, "facing", 0.0))
        else:
            facing = float(facing)
        positions_by_id[mid] = (x, y, z, facing)

        if hasattr(game_map, "is_within_boundary") and not game_map.is_within_boundary(model, destination=(x, y)):
            return ("Move unit: placement outside battlefield boundary.",)
        if callable(collision_fn) and collision_fn(model, destination=(x, y)):
            return ("Move unit: placement collides with terrain.",)
        ruins_validation = validate_ruins_placement(unit, (x, y, z), game_map.terrain_features, moving_model=model)
        if not ruins_validation.get("valid", False):
            return (f"Move unit: RUINS placement invalid: {ruins_validation.get('reason', 'invalid')}",)

        if hasattr(unit, "_create_potential_base"):
            base = unit._create_potential_base(x, y, z, facing, model=model)
        else:
            base = getattr(model, "model_base", None)
        if base is None:
            return ("Move unit: unable to resolve model base for placement.",)
        candidate_bases[mid] = base

    # Check overlap against existing models in this unit (excluding pending/placed models)
    for other in list(getattr(unit, "models", []) or []):
        if not getattr(other, "is_alive", True):
            continue
        if getattr(other, "_pending_placement", False):
            continue
        other_id = str(get_entity_id(other))
        if other_id in candidate_bases:
            continue
        other_base = getattr(other, "model_base", None)
        if other_base is None:
            continue
        for base in candidate_bases.values():
            if bases_overlap_3d(base, other_base):
                return ("Move unit: placement overlaps another model in the unit.",)

    # Check overlap among newly placed models
    ids = list(candidate_bases.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if bases_overlap_3d(candidate_bases[ids[i]], candidate_bases[ids[j]]):
                return ("Move unit: placement overlaps between placed models.",)

    # Check overlap against other units on the battlefield
    for other_unit in list(getattr(game_map, "units", []) or []):
        if other_unit is unit:
            continue
        try:
            other_models = list(other_unit.get_models_for_collision() or [])
        except Exception:
            other_models = list(getattr(other_unit, "models", []) or [])
        for other in list(other_models or []):
            if not getattr(other, "is_alive", True):
                continue
            other_base = getattr(other, "model_base", None)
            if other_base is None:
                continue
            for base in candidate_bases.values():
                if bases_overlap_3d(base, other_base):
                    return ("Move unit: placement overlaps another unit.",)

    # Coherency validation (placements must end in coherency)
    final_positions: list[tuple[float, float, float]] = []
    for model in list(getattr(unit, "models", []) or []):
        mid = str(get_entity_id(model))
        if mid in positions_by_id:
            x, y, z, _f = positions_by_id[mid]
            final_positions.append((x, y, z))
        else:
            try:
                pos = model.get_location()
                final_positions.append((float(pos[0]), float(pos[1]), float(pos[2])))
            except Exception:
                final_positions.append((0.0, 0.0, 0.0))

    is_coherent, _non_coherent = validate_unit_coherency_after_movement(
        unit, final_positions, ignore_pending=False
    )
    if not is_coherent:
        return ("Move unit: placement breaks unit coherency.",)

    # Ensure only allowed ids are placed (if provided)
    if allowed_set is not None:
        if set(candidate_bases.keys()) != allowed_set:
            return ("Move unit: placement must include all allowed models.",)

    if str(placement_kind or "") == "deployment":
        deployment_errors = _validate_deployment_positions(game, unit, model_positions)
        if deployment_errors:
            return deployment_errors
    if str(placement_kind or "") == "reserves_arrival":
        reserves_errors = _validate_reserves_arrival_positions(game, unit, model_positions)
        if reserves_errors:
            return reserves_errors

    return ()


def _validate_deployment_positions(
    game: object,
    unit: object,
    model_positions: object,
) -> Sequence[str]:
    validate_fn = getattr(game, "is_valid_single_model_deployment", None)
    if not callable(validate_fn):
        return ()
    player_id = None
    army = getattr(unit, "get_parent_army", None)
    if callable(army):
        army = army()
    else:
        army = getattr(unit, "parent_army", None)
    if army is not None:
        player = getattr(army, "player", None)
        player_id = getattr(player, "id", None) if player is not None else None
    if not player_id:
        return ("Move unit: deployment requires player_id.",)
    for entry in list(model_positions or []):
        model_id = str(entry.get("model_id", "") or "")
        if not model_id:
            return ("Move unit: deployment missing model_id.",)
        model = get_model(game, model_id)
        if model is None:
            return (f"Move unit: deployment model not found: {model_id}",)
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return ("Move unit: deployment position missing coordinates.",)
        x = float(pos[0])
        y = float(pos[1])
        z = float(pos[2]) if len(pos) > 2 else float(getattr(model.model_base, "z", 0.0))
        check = validate_fn(model, x, y, z, player_id)
        if not bool(check.get("valid", False)):
            reason = str(check.get("reason", "") or "invalid")
            return (f"Move unit: deployment invalid: {reason}",)
    return ()


def _validate_reserves_arrival_positions(
    game: object,
    unit: object,
    model_positions: object,
) -> Sequence[str]:
    evaluation = _evaluate_reserves_arrival_positions(game, unit, model_positions)
    if evaluation.get("errors"):
        return tuple(evaluation.get("errors") or [])
    return ()


def _evaluate_reserves_arrival_positions(
    game: object,
    unit: object,
    model_positions: object,
) -> dict:
    errors: list[str] = []
    if unit is None:
        return {"errors": ["Reserves arrival requires a unit."]}
    if not bool(getattr(unit, "is_in_reserves", lambda: False)()):
        return {"errors": ["Unit is not in reserves."]}
    try:
        if not unit.can_arrive_from_reserves(getattr(game, "turn", 0)):
            return {"errors": ["Unit cannot arrive from reserves this turn."]}
    except Exception:
        return {"errors": ["Reserves arrival eligibility check failed."]}

    if not isinstance(model_positions, list) or not model_positions:
        return {"errors": ["Reserves arrival requires model positions."]}

    from ...utility.entity_ids import get_entity_id

    positions_by_id: dict[str, tuple[float, float, float, float]] = {}
    for entry in list(model_positions or []):
        model_id = str(entry.get("model_id", "") or "")
        if not model_id:
            return {"errors": ["Reserves arrival missing model_id."]}
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return {"errors": ["Reserves arrival missing position coordinates."]}
        try:
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else 0.0
        except (TypeError, ValueError):
            return {"errors": ["Reserves arrival position coordinates must be numeric."]}
        facing = entry.get("facing")
        if facing is None:
            facing = 0.0
        try:
            facing_val = float(facing)
        except (TypeError, ValueError):
            facing_val = 0.0
        positions_by_id[model_id] = (x, y, z, facing_val)

    prospective: list[tuple[float, float, float, float]] = []
    for model in list(getattr(unit, "models", []) or []):
        mid = str(get_entity_id(model))
        if mid not in positions_by_id:
            return {"errors": ["Reserves arrival missing positions for all models."]}
        prospective.append(positions_by_id[mid])

    game_map = getattr(game, "map", None)
    battlefield = getattr(game, "battlefield", None)
    width = None
    height = None
    if battlefield is not None:
        try:
            width = float(getattr(battlefield, "width", None))
            height = float(getattr(battlefield, "height", None))
        except Exception:
            width = None
            height = None
    if (width is None or height is None) and game_map is not None:
        try:
            width = float(getattr(game_map, "width", None))
            height = float(getattr(game_map, "height", None))
        except Exception:
            width = None
            height = None
    if width is None or height is None:
        return {"errors": errors}

    def _model_radius(model) -> float:
        mb = getattr(model, "model_base", None)
        if mb is None:
            return 1.0
        if hasattr(mb, "get_longest_radius"):
            return float(mb.get_longest_radius())
        if hasattr(mb, "get_radius"):
            return float(mb.get_radius())
        r = getattr(mb, "radius", None)
        if isinstance(r, (list, tuple)) and r:
            return float(r[0])
        return float(r) if r is not None else 1.0

    def _center_dist_to_edge(x: float, y: float, edge: str) -> float:
        if edge == "own":
            return float(y)
        if edge == "enemy":
            return float(height - y)
        if edge == "left":
            return float(x)
        if edge == "right":
            return float(width - x)
        return float("inf")

    strategic_ok = False
    strategic_used_edge_touch = False
    selected_edge: str | None = None

    if bool(getattr(unit, "is_in_strategic_reserves", lambda: False)()):
        for edge in ("own", "left", "right", "enemy"):
            ok_all = True
            used_touch = False
            for model, (x, y, _z, _facing) in zip(list(getattr(unit, "models", []) or []), prospective):
                r = float(_model_radius(model))
                d = _center_dist_to_edge(x, y, edge)
                max_center = 6.0 - r
                if max_center >= 0.0:
                    if d > max_center + 1e-6:
                        ok_all = False
                        break
                else:
                    if abs(d - float(r)) > 0.25:
                        ok_all = False
                        break
                    used_touch = True
            if ok_all:
                strategic_ok = True
                strategic_used_edge_touch = bool(used_touch)
                selected_edge = edge
                break

    deep_strike_ok = True
    if bool(getattr(unit, "is_in_strategic_reserves", lambda: False)()):
        try:
            deep_strike_ok = bool(getattr(unit, "has_deep_strike", lambda: False)())
        except Exception:
            deep_strike_ok = False
        if not strategic_ok and not deep_strike_ok:
            return {"errors": ["Reserves arrival must be within 6\" of a battlefield edge."]}

    battlefield_edge = selected_edge if strategic_ok else None

    try:
        min_enemy_distance = float(getattr(game, "_warp_rifts_min_distance")(unit) or 9.0)
    except Exception:
        min_enemy_distance = 9.0

    if battlefield_edge is None:
        try:
            if hasattr(unit, "get_deep_strike_min_distance_override"):
                override = unit.get_deep_strike_min_distance_override()
            else:
                override = None
        except Exception:
            override = None
        if override:
            min_enemy_distance = min(float(min_enemy_distance), float(override))

    try:
        from ...utility.aura_utils import horizontal_distance_between_bases_2d
    except Exception:
        horizontal_distance_between_bases_2d = None
    enemy_units = []
    try:
        player = unit.get_parent_army().player
        enemy_units = list(getattr(game, "get_enemy_units", lambda _p: [])(player) or [])
    except Exception:
        enemy_units = []
    enemy_models = []
    for enemy in list(enemy_units or []):
        try:
            if not getattr(enemy, "is_alive", lambda: True)():
                continue
        except Exception:
            if not getattr(enemy, "is_alive", True):
                continue
        if not bool(getattr(enemy, "deployed", False)):
            continue
        if str(getattr(enemy, "reserve_status", "deployed")) != "deployed":
            continue
        if getattr(enemy, "embarked_in", None) is not None:
            continue
        if bool(getattr(enemy, "is_embarked", False)):
            continue
        for em in list(getattr(enemy, "models", []) or []):
            if not getattr(em, "is_alive", True):
                continue
            enemy_models.append(em)

    if callable(horizontal_distance_between_bases_2d):
        for model, (x, y, z, facing) in zip(list(getattr(unit, "models", []) or []), prospective):
            try:
                base = unit._create_potential_base(x, y, z, facing, model=model)
            except Exception:
                base = None
            if base is None:
                continue
            for em in list(enemy_models or []):
                try:
                    dist = float(horizontal_distance_between_bases_2d(base, em.model_base))
                except Exception:
                    continue
                if dist < float(min_enemy_distance):
                    return {"errors": [f"Reserves arrival must be more than {int(min_enemy_distance)}\" from enemy models."]}

    try:
        if bool(getattr(game, "_reserves_denial_violated")(unit, prospective)):
            return {"errors": ["Reserves arrival position is denied by an enemy ability."]}
    except Exception:
        pass

    pending_deep_strike = False
    if bool(getattr(unit, "is_in_strategic_reserves", lambda: False)()):
        pending_deep_strike = bool(deep_strike_ok and not strategic_ok)
    else:
        pending_deep_strike = True

    return {
        "errors": errors,
        "prospective": prospective,
        "battlefield_edge": battlefield_edge,
        "edge_touch": bool(strategic_ok and strategic_used_edge_touch),
        "pending_deep_strike": bool(pending_deep_strike),
    }


def _apply_move_unit(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    ctx = dict(getattr(request, "context", {}) or {})
    unit_id = str(payload.get("unit_id", "") or ctx.get("unit_id", "") or "")
    unit = get_unit(game, unit_id)
    if unit is None:
        raise RuntimeError("Move unit: unit not found.")
    movement_type = str(payload.get("movement_type", "") or request.context.get("movement_type", "") or "")
    placement_kind = str(ctx.get("placement_kind", "") or "")
    if bool(result.payload.get("skipped", False)):
        if movement_type == "reactive":
            _clear_battle_focus_reactive_flags(unit)
        if placement_kind == "reserves_arrival":
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            for k in (
                "cloudstrider_deep_strike_min_distance",
                "cloudstrider_choice_turn",
                "cloudstrider_choice_turn_owner",
                "cloudstrider_no_charge_turn",
                "cloudstrider_no_charge_turn_owner",
            ):
                sr.pop(k, None)
            unit.special_rules = sr
        return None
    model_positions = list(result.payload.get("model_positions") or [])
    apply_model_positions(game, model_positions)

    allowed_ids = {str(v) for v in list(ctx.get("allowed_model_ids") or []) if v is not None}
    if placement_kind or allowed_ids:
        for entry in list(model_positions or []):
            model_id = str(entry.get("model_id", "") or "")
            model = get_model(game, model_id)
            if model is None:
                continue
            model._pending_placement = False
            model._pending_placement_source = None
        if hasattr(unit, "update_coherency"):
            unit.update_coherency()
    if placement_kind == "deployment":
        _finalize_deployment_move(game, unit, model_positions)
    if placement_kind == "reserves_arrival":
        _finalize_reserves_arrival_move(game, unit, model_positions)
    if bool(ctx.get("redeploy_followup", False)):
        try:
            unit_id = str(ctx.get("redeploy_unit_id", "") or unit_id)
            followup = getattr(game, "_on_redeploy_placement_resolved", None)
            if callable(followup):
                followup(unit_id)
        except Exception:
            pass

    members = _movement_members(unit)
    for member in members:
        if movement_type == "advance":
            member.round_state.advanced_this_round = True
        elif movement_type == "fall_back":
            member.round_state.fell_back_this_round = True
        elif movement_type in ("move", "pile_in", "consolidate", "charge"):
            member.round_state.moved_this_round = True
            member.round_state.remained_stationary_this_round = False
        try:
            if movement_type in ("move", "advance", "fall_back"):
                member.round_state.move_modifier_choice = None
                member.round_state.move_modifier_choice_pending = False
            if movement_type == "advance":
                member.round_state.advance_modifier_choice = None
                member.round_state.advance_modifier_choice_pending = False
            if movement_type == "charge":
                member.round_state.charge_modifier_choice = None
                member.round_state.charge_modifier_choice_pending = False
                member.round_state.charge_modifier_choice_targets = []
        except Exception:
            pass
        if movement_type == "loping_speed":
            member.mark_loping_speed_used(game)
        if movement_type == "blood_surge":
            member.mark_blood_surge_used(game)
        if movement_type == "brazen_fury":
            member.mark_brazen_fury_used(game)
    if movement_type == "reactive":
        _clear_battle_focus_reactive_flags(unit)
    return None


def _finalize_deployment_move(game: object, unit: object, model_positions: list[dict]) -> None:
    if unit is None:
        return
    unit.deployed = True
    leaders = list(getattr(unit, "attached_leaders", []) or [])
    supports = list(getattr(unit, "attached_support_units", []) or [])
    for member in leaders + supports:
        member.deployed = True
        member.reserve_status = getattr(unit, "reserve_status", "deployed")
        member.reserve_turn_deployed = getattr(unit, "reserve_turn_deployed", None)

    game_map = getattr(game, "map", None)
    if game_map is not None:
        units_list = getattr(game_map, "units", None)
        if isinstance(units_list, list) and unit not in units_list:
            units_list.append(unit)

    positions = []
    for entry in list(model_positions or []):
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        try:
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else 0.0
        except (TypeError, ValueError):
            continue
        positions.append((x, y, z))
    if positions:
        ux = sum(p[0] for p in positions) / len(positions)
        uy = sum(p[1] for p in positions) / len(positions)
        uz = sum(p[2] for p in positions) / len(positions)
        unit.position = (ux, uy, uz)

    army = getattr(unit, "get_parent_army", None)
    if callable(army):
        army = army()
    else:
        army = getattr(unit, "parent_army", None)
    player = getattr(army, "player", None) if army is not None else None
    if player is not None and hasattr(game, "record_deployment_action"):
        game.record_deployment_action(player, unit, "deployed", getattr(unit, "position", None))
    if hasattr(game, "advance_deployment_turn"):
        game.advance_deployment_turn(unit)


def _finalize_reserves_arrival_move(game: object, unit: object, model_positions: list[dict]) -> None:
    if unit is None:
        return
    evaluation = _evaluate_reserves_arrival_positions(game, unit, model_positions)
    errors = list(evaluation.get("errors") or [])
    if errors:
        raise RuntimeError("; ".join(str(e) for e in errors if e))

    # Track special arrival flags (edge touch / deep strike) for downstream rules.
    try:
        if evaluation.get("edge_touch"):
            setattr(unit, "_pending_reserves_edge_touch", True)
        elif hasattr(unit, "_pending_reserves_edge_touch"):
            delattr(unit, "_pending_reserves_edge_touch")
    except Exception:
        pass
    try:
        setattr(unit, "_pending_reserves_deep_strike", bool(evaluation.get("pending_deep_strike", False)))
    except Exception:
        pass

    # Update unit centroid position for convenience.
    positions = []
    for entry in list(model_positions or []):
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        try:
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else 0.0
        except (TypeError, ValueError):
            continue
        positions.append((x, y, z))
    if positions:
        ux = sum(p[0] for p in positions) / len(positions)
        uy = sum(p[1] for p in positions) / len(positions)
        uz = sum(p[2] for p in positions) / len(positions)
        unit.position = (ux, uy, uz)

    game_map = getattr(game, "map", None)
    if game_map is not None and hasattr(game_map, "units"):
        try:
            if unit not in game_map.units:
                game_map.units.append(unit)
        except Exception:
            pass

    try:
        turn = int(getattr(game, "turn", 0) or 0)
    except Exception:
        turn = 0
    try:
        unit._finalize_reserves_arrival(turn, game_map)
    except Exception as exc:
        raise RuntimeError(f"Reserves arrival finalize failed: {exc}") from exc


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
