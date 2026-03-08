from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import _validate_choice_from_options, register_decision_handler
from ..decision_kinds import (
    DECISION_ATTACH_LEADER,
    DECISION_ATTACH_SUPPORT_ARTILLERY,
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_DECLARE_RESERVES,
    DECISION_ASSIGN_TRANSPORT,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
    DECISION_SHADOW_ASSIGNMENT,
    DECISION_SCOUT_MOVE,
)
from ..decisions import DecisionOption, DecisionRequest, DecisionResult
from ...rules.imperial_agents_shadow_assignment import (
    army_supports_shadow_assignment,
    build_shadow_assignment_unit,
    get_shadow_assignment_candidate,
    shadow_assignment_candidates_for_unit,
    unit_has_shadow_assignment,
)
from ...utility.entity_ids import get_entity_id


def _find_option(request: DecisionRequest, option_id: str) -> DecisionOption | None:
    for opt in list(getattr(request, "options", []) or []):
        if opt.option_id == option_id:
            return opt
    return None


def _get_unit(game: object, unit_id: str):
    registry = getattr(game, "entity_registry", None)
    if registry is None:
        return None
    return registry.get(unit_id, kind="unit")


def _validate_choose_deployment_zone(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(_validate_choice_from_options(request, result))
    if errors:
        return errors
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    zone_choice_id = str(payload.get("zone_choice_id", "") or "")
    zone_key = str(payload.get("zone_key", "") or "")
    zone_index = payload.get("zone_index", None)
    if not zone_choice_id:
        return ("Deployment zone choice requires zone_choice_id.",)
    if not zone_key:
        return ("Deployment zone choice requires zone_key.",)
    try:
        zone_index_int = int(zone_index)
    except (TypeError, ValueError):
        return ("Deployment zone choice requires numeric zone_index.",)
    if zone_index_int < 0:
        return ("Deployment zone choice zone_index must be >= 0.",)
    allowed_ids = {str(value) for value in list(request.context.get("available_zone_choice_ids", []) or [])}
    if allowed_ids and zone_choice_id not in allowed_ids:
        return ("Selected deployment zone is not available.",)
    allowed_keys = {str(value) for value in list(request.context.get("available_zone_keys", []) or [])}
    if allowed_keys and zone_key not in allowed_keys:
        return ("Selected deployment zone key is not available.",)
    return ()


def _apply_choose_deployment_zone(game: object, request: DecisionRequest, result: DecisionResult) -> dict[str, object]:
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    return {
        "zone_choice_id": str(payload.get("zone_choice_id", "") or ""),
        "zone_key": str(payload.get("zone_key", "") or ""),
        "zone_index": int(payload.get("zone_index", 0) or 0),
    }


def _validate_select_next_deploy_unit(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(_validate_choice_from_options(request, result))
    if errors:
        return errors
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or "")
    if not unit_id:
        return ("Deployment unit selection requires unit_id.",)
    allowed_ids = {str(value) for value in list(request.context.get("unit_ids", []) or [])}
    if allowed_ids and unit_id not in allowed_ids:
        return ("Selected unit is not available to deploy.",)
    return ()


def _apply_select_next_deploy_unit(game: object, request: DecisionRequest, result: DecisionResult) -> dict[str, object]:
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    return {
        "unit_id": str(payload.get("unit_id", "") or ""),
    }


def _validate_attach_leader(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(_validate_choice_from_options(request, result))
    if errors:
        return errors
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    leader_id = str(payload.get("leader_id", "") or "")
    bodyguard_id = payload.get("bodyguard_id")
    if not leader_id:
        return ("Leader attachment requires leader_id.",)
    leader = _get_unit(game, leader_id)
    if leader is None:
        return ("Leader unit not found.",)
    if not bool(getattr(leader, "is_leader", False)):
        return ("Selected unit is not a leader.",)
    if bodyguard_id is None:
        return ()
    bodyguard = _get_unit(game, str(bodyguard_id or ""))
    if bodyguard is None:
        return ("Bodyguard unit not found.",)
    try:
        if not leader.can_attach_to(bodyguard):
            return ("Leader cannot attach to the selected unit.",)
    except Exception:
        return ("Leader attachment validation failed.",)
    return ()


def _apply_attach_leader(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    leader = _get_unit(game, str(payload.get("leader_id", "") or ""))
    bodyguard_id = payload.get("bodyguard_id")
    if leader is None:
        raise RuntimeError("Leader unit missing for attachment.")
    if bodyguard_id is None:
        leader.detach_from_unit()
        return None
    bodyguard = _get_unit(game, str(bodyguard_id or ""))
    if bodyguard is None:
        raise RuntimeError("Bodyguard unit missing for attachment.")
    leader.attach_to_unit(bodyguard)
    return None


def _validate_attach_support_artillery(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(_validate_choice_from_options(request, result))
    if errors:
        return errors
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    support_id = str(payload.get("support_unit_id", "") or "")
    bodyguard_id = payload.get("bodyguard_id")
    if not support_id:
        return ("Support artillery attachment requires support_unit_id.",)
    support = _get_unit(game, support_id)
    if support is None:
        return ("Joined support unit not found.",)
    if not bool(getattr(support, "has_joined_support_ability", lambda: False)()):
        return ("Selected unit does not have a joined-support attachment ability.",)
    requires_attach_fn = getattr(support, "joined_support_requires_attachment", None)
    requires_attachment = bool(requires_attach_fn()) if callable(requires_attach_fn) else False
    if bodyguard_id is None:
        if requires_attachment:
            return ("Selected joined support unit must attach to an eligible bodyguard unit.",)
        return ()
    bodyguard = _get_unit(game, str(bodyguard_id or ""))
    if bodyguard is None:
        return ("Bodyguard unit not found.",)
    try:
        if not support.can_join_support_artillery(bodyguard):
            return ("Joined support unit cannot join the selected unit.",)
    except Exception:
        return ("Joined-support attachment validation failed.",)
    return ()


def _apply_attach_support_artillery(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    support = _get_unit(game, str(payload.get("support_unit_id", "") or ""))
    bodyguard_id = payload.get("bodyguard_id")
    if support is None:
        raise RuntimeError("Joined support unit missing for attachment.")
    if bodyguard_id is None:
        support.detach_support_artillery()
        return None
    bodyguard = _get_unit(game, str(bodyguard_id or ""))
    if bodyguard is None:
        raise RuntimeError("Bodyguard unit missing for joined-support attachment.")
    support.attach_support_artillery_to(bodyguard)
    return None


def _validate_declare_reserves(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(_validate_choice_from_options(request, result))
    if errors:
        return errors
    payload = dict(result.payload or {})
    buckets = payload.get("unit_ids_by_bucket")
    if not isinstance(buckets, dict):
        return ("Reserves decision requires unit_ids_by_bucket.",)
    decisions: dict[str, str] = {}
    for status, ids in buckets.items():
        if status not in ("deploy", "reserves", "strategic_reserves"):
            return (f"Invalid reserves bucket: {status}",)
        if not isinstance(ids, list):
            return (f"unit_ids_by_bucket.{status} must be a list.",)
        for unit_id in ids:
            if unit_id in decisions:
                return ("Unit appears in multiple reserves buckets.",)
            decisions[str(unit_id)] = status
    player_id = request.player_id
    if not player_id:
        return ("Reserves decision requires player_id.",)
    player = getattr(game, "entity_registry", None).get(player_id, kind="player") if getattr(game, "entity_registry", None) else None
    if player is None:
        return ("Player not found for reserves decision.",)
    army = player.get_army()
    if army is None:
        return ("Army not found for reserves decision.",)
    validation = army.validate_reserves_decisions(decisions)
    if not validation.get("valid", False):
        return tuple(str(e) for e in validation.get("errors", []) or ["Reserves validation failed"])
    return ()


def _apply_declare_reserves(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    payload = dict(result.payload or {})
    buckets = payload.get("unit_ids_by_bucket") or {}
    decisions: dict[str, str] = {}
    for status, ids in buckets.items():
        for unit_id in list(ids or []):
            decisions[str(unit_id)] = str(status)
    player = getattr(game, "entity_registry", None).get(request.player_id, kind="player") if getattr(game, "entity_registry", None) else None
    if player is None:
        raise RuntimeError("Player not found for reserves decision.")
    army = player.get_army()
    if army is None:
        raise RuntimeError("Army not found for reserves decision.")
    if not game.apply_reserves_decisions(army, decisions):
        raise RuntimeError("Failed to apply reserves decisions.")
    return None


def _validate_assign_transport(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(_validate_choice_from_options(request, result))
    if errors:
        return errors
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or "")
    transport_id = payload.get("transport_id")
    if not unit_id:
        return ("Transport assignment requires unit_id.",)
    unit = _get_unit(game, unit_id)
    if unit is None:
        return ("Passenger unit not found.",)
    if transport_id is None:
        return ()
    transport = _get_unit(game, str(transport_id or ""))
    if transport is None:
        return ("Transport unit not found.",)
    try:
        if not bool(getattr(transport, "is_transport", False)):
            return ("Selected unit is not a transport.",)
        if not transport.can_transport(unit):
            return ("Transport cannot embark the selected unit.",)
    except Exception:
        return ("Transport assignment validation failed.",)
    return ()


def _apply_assign_transport(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit = _get_unit(game, str(payload.get("unit_id", "") or ""))
    transport_id = payload.get("transport_id")
    if unit is None:
        raise RuntimeError("Passenger unit missing for transport assignment.")
    if transport_id is None:
        try:
            current = getattr(unit, "embarked_in", None)
            if current is not None:
                current.remove_passenger(unit)
        except Exception:
            pass
        return None
    transport = _get_unit(game, str(transport_id or ""))
    if transport is None:
        raise RuntimeError("Transport unit missing for transport assignment.")
    unit.embark(transport, game_map=getattr(game, "map", None))
    try:
        unit.deployed = True
    except Exception:
        pass
    try:
        for leader in list(getattr(unit, "attached_leaders", []) or []):
            leader.deployed = True
    except Exception:
        pass
    return None


def _shadow_assignment_payload(request: DecisionRequest, result: DecisionResult) -> dict:
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    if not payload:
        payload = dict(getattr(result, "payload", {}) or {})
    return payload


def _shadow_assignment_source_unit(game: object, request: DecisionRequest, payload: dict):
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    if not unit_id:
        return None
    return _get_unit(game, unit_id)


def _replace_id_value(value: object, *, old_id: str, new_id: str):
    if isinstance(value, str):
        return new_id if value == old_id else value
    if isinstance(value, list):
        return [_replace_id_value(v, old_id=old_id, new_id=new_id) for v in value]
    if isinstance(value, tuple):
        return tuple(_replace_id_value(v, old_id=old_id, new_id=new_id) for v in value)
    if isinstance(value, dict):
        return {k: _replace_id_value(v, old_id=old_id, new_id=new_id) for k, v in value.items()}
    return value


def _rewrite_pending_request_unit_ids(game: object, *, old_id: str, new_id: str) -> None:
    if not old_id or not new_id or old_id == new_id:
        return
    queue = getattr(game, "decision_queue", None)
    if queue is None or not hasattr(queue, "list"):
        return
    for req in list(queue.list() or []):
        req.context = _replace_id_value(dict(getattr(req, "context", {}) or {}), old_id=old_id, new_id=new_id)
        for opt in list(getattr(req, "options", []) or []):
            opt.payload = _replace_id_value(dict(getattr(opt, "payload", {}) or {}), old_id=old_id, new_id=new_id)
        if hasattr(req, "candidates"):
            req.candidates = []
            req.mask = []
            req.mask_reasons = []
            req.finalize_candidates()


def _validate_shadow_assignment(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(_validate_choice_from_options(request, result))
    if errors:
        return errors

    payload = _shadow_assignment_payload(request, result)
    source_unit = _shadow_assignment_source_unit(game, request, payload)
    if source_unit is None:
        return ("Shadow Assignment source unit not found.",)
    if not unit_has_shadow_assignment(source_unit):
        return ("Selected unit does not have Shadow Assignment.",)

    army = getattr(source_unit, "get_parent_army", lambda: None)()
    if army is None:
        return ("Shadow Assignment source unit has no parent army.",)
    if not army_supports_shadow_assignment(army):
        return ("Shadow Assignment requires an Imperial Agents army.",)

    action = str(payload.get("action", "") or "").strip().lower()
    replacement_name = str(payload.get("replacement_name", "") or "").strip()
    replacement_datasheet_id = str(payload.get("replacement_datasheet_id", "") or "").strip()
    if action in {"", "skip"} and not replacement_name and not replacement_datasheet_id:
        return ()
    if action not in {"replace", "skip", ""}:
        return ("Shadow Assignment action must be 'replace' or 'skip'.",)
    if action == "skip":
        return ()
    if not replacement_name and not replacement_datasheet_id:
        return ("Shadow Assignment replacement is required.",)

    selected = get_shadow_assignment_candidate(
        replacement_name=replacement_name,
        replacement_datasheet_id=replacement_datasheet_id,
    )
    if selected is None:
        return ("Selected Shadow Assignment replacement is not valid.",)
    allowed = {
        (str(candidate.datasheet_id), str(candidate.name).strip().lower())
        for candidate in shadow_assignment_candidates_for_unit(source_unit, list(getattr(army, "units", []) or []))
    }
    key = (str(selected.datasheet_id), str(selected.name).strip().lower())
    if key not in allowed:
        return ("Selected Shadow Assignment replacement is not legal for this unit.",)
    return ()


def _apply_shadow_assignment(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _shadow_assignment_payload(request, result)
    source_unit = _shadow_assignment_source_unit(game, request, payload)
    if source_unit is None:
        raise RuntimeError("Shadow Assignment source unit missing.")
    action = str(payload.get("action", "") or "").strip().lower()
    replacement_name = str(payload.get("replacement_name", "") or "").strip()
    replacement_datasheet_id = str(payload.get("replacement_datasheet_id", "") or "").strip()
    if action in {"", "skip"} and not replacement_name and not replacement_datasheet_id:
        return None
    if action == "skip":
        return None

    selected = get_shadow_assignment_candidate(
        replacement_name=replacement_name,
        replacement_datasheet_id=replacement_datasheet_id,
    )
    if selected is None:
        raise RuntimeError("Shadow Assignment replacement candidate not found.")

    army = getattr(source_unit, "get_parent_army", lambda: None)()
    if army is None:
        raise RuntimeError("Shadow Assignment source unit has no parent army.")
    units = list(getattr(army, "units", []) or [])
    try:
        source_index = units.index(source_unit)
    except ValueError as exc:
        raise RuntimeError("Shadow Assignment source unit missing from army.") from exc

    new_unit = build_shadow_assignment_unit(selected)
    new_unit.set_parent_army(army)
    new_unit.deployed = bool(getattr(source_unit, "deployed", False))
    new_unit.reserve_status = str(getattr(source_unit, "reserve_status", "deployed") or "deployed")
    new_unit.reserve_turn_deployed = getattr(source_unit, "reserve_turn_deployed", None)
    new_unit.arrived_from_reserves_this_turn = bool(getattr(source_unit, "arrived_from_reserves_this_turn", False))
    new_unit.is_warlord = bool(getattr(source_unit, "is_warlord", False))

    old_unit_id = str(get_entity_id(source_unit) or "")
    army.units[source_index] = new_unit
    if getattr(army, "warlord", None) is source_unit:
        army.warlord = new_unit

    rebuild = getattr(game, "rebuild_entity_registry", None)
    if callable(rebuild):
        rebuild()
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()

    new_unit_id = str(get_entity_id(new_unit) or "")
    _rewrite_pending_request_unit_ids(game, old_id=old_unit_id, new_id=new_unit_id)
    return new_unit_id


def _validate_scout_move(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(_validate_choice_from_options(request, result))
    if errors:
        return errors
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    action = str(payload.get("action", "") or "")
    unit_id = str(payload.get("unit_id", "") or "")
    if not unit_id:
        return ("Scout move requires unit_id.",)
    unit = _get_unit(game, unit_id)
    if unit is None:
        return ("Scout unit not found.",)
    if action not in ("scout", "skip"):
        return ("Scout move action must be 'scout' or 'skip'.",)
    if action == "scout":
        model_positions = result.payload.get("model_positions")
        if isinstance(model_positions, list) and model_positions:
            for entry in model_positions:
                if not isinstance(entry, dict):
                    return ("Model position entry must be a dict.",)
                model_id = str(entry.get("model_id", "") or "")
                if not model_id:
                    return ("Model position entry missing model_id.",)
                model = getattr(game, "entity_registry", None).get(model_id, kind="model") if getattr(game, "entity_registry", None) else None
                if model is None:
                    return (f"Model not found: {model_id}",)
                pos = entry.get("position")
                if not isinstance(pos, (list, tuple)) or len(pos) < 2:
                    return ("Model position entry missing position.",)
            return ()
        dest = result.payload.get("destination")
        if not isinstance(dest, (list, tuple)) or len(dest) < 2:
            return ("Scout move requires destination coordinates.",)
    return ()


def _apply_scout_move(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    action = str(payload.get("action", "") or "")
    unit = _get_unit(game, str(payload.get("unit_id", "") or ""))
    if unit is None:
        raise RuntimeError("Scout unit missing.")
    if action == "skip":
        setattr(unit, "scout_move_made", True)
        return None
    model_positions = result.payload.get("model_positions")
    if isinstance(model_positions, list) and model_positions:
        for entry in model_positions:
            model_id = str(entry.get("model_id", "") or "")
            model = getattr(game, "entity_registry", None).get(model_id, kind="model") if getattr(game, "entity_registry", None) else None
            if model is None:
                continue
            pos = entry.get("position") or []
            if len(pos) < 2:
                continue
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else float(getattr(model.model_base, "z", 0.0))
            facing = entry.get("facing", None)
            if facing is None:
                facing = getattr(model.model_base, "facing", 0.0)
            model.set_location(x, y, z, float(facing))
        setattr(unit, "scout_move_made", True)
        return None
    dest = result.payload.get("destination")
    if not isinstance(dest, (list, tuple)) or len(dest) < 2:
        raise RuntimeError("Scout move destination missing.")
    x = float(dest[0])
    y = float(dest[1])
    z = float(dest[2]) if len(dest) > 2 else float(getattr(unit.models[0].model_base, "z", 0.0))
    if not unit.scout_move((x, y, z), getattr(game, "map", None)):
        raise RuntimeError("Scout move failed.")
    return None


register_decision_handler(DECISION_ATTACH_LEADER, validate=_validate_attach_leader, apply=_apply_attach_leader)
register_decision_handler(
    DECISION_ATTACH_SUPPORT_ARTILLERY,
    validate=_validate_attach_support_artillery,
    apply=_apply_attach_support_artillery,
)
register_decision_handler(
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    validate=_validate_choose_deployment_zone,
    apply=_apply_choose_deployment_zone,
)
register_decision_handler(DECISION_DECLARE_RESERVES, validate=_validate_declare_reserves, apply=_apply_declare_reserves)
register_decision_handler(DECISION_ASSIGN_TRANSPORT, validate=_validate_assign_transport, apply=_apply_assign_transport)
register_decision_handler(
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
    validate=_validate_select_next_deploy_unit,
    apply=_apply_select_next_deploy_unit,
)
register_decision_handler(DECISION_SHADOW_ASSIGNMENT, validate=_validate_shadow_assignment, apply=_apply_shadow_assignment)
register_decision_handler(DECISION_SCOUT_MOVE, validate=_validate_scout_move, apply=_apply_scout_move)
