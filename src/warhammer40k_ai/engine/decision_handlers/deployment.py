from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import _validate_choice_from_options, register_decision_handler
from ..decision_kinds import (
    DECISION_ATTACH_LEADER,
    DECISION_ATTACH_SUPPORT_ARTILLERY,
    DECISION_DECLARE_RESERVES,
    DECISION_ASSIGN_TRANSPORT,
    DECISION_SCOUT_MOVE,
)
from ..decisions import DecisionOption, DecisionRequest, DecisionResult


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
        return ("Support artillery unit not found.",)
    if not bool(getattr(support, "has_support_artillery_ability", lambda: False)()):
        return ("Selected unit does not have Support Artillery.",)
    if bodyguard_id is None:
        return ()
    bodyguard = _get_unit(game, str(bodyguard_id or ""))
    if bodyguard is None:
        return ("Guardian Defenders unit not found.",)
    try:
        if not support.can_join_support_artillery(bodyguard):
            return ("Support artillery cannot join the selected unit.",)
    except Exception:
        return ("Support artillery attachment validation failed.",)
    return ()


def _apply_attach_support_artillery(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    support = _get_unit(game, str(payload.get("support_unit_id", "") or ""))
    bodyguard_id = payload.get("bodyguard_id")
    if support is None:
        raise RuntimeError("Support artillery unit missing for attachment.")
    if bodyguard_id is None:
        support.detach_support_artillery()
        return None
    bodyguard = _get_unit(game, str(bodyguard_id or ""))
    if bodyguard is None:
        raise RuntimeError("Bodyguard unit missing for support attachment.")
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
register_decision_handler(DECISION_DECLARE_RESERVES, validate=_validate_declare_reserves, apply=_apply_declare_reserves)
register_decision_handler(DECISION_ASSIGN_TRANSPORT, validate=_validate_assign_transport, apply=_apply_assign_transport)
register_decision_handler(DECISION_SCOUT_MOVE, validate=_validate_scout_move, apply=_apply_scout_move)
