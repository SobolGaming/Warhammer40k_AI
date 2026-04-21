from __future__ import annotations

from typing import Any, Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import (
    DECISION_CHOOSE_IMPOSSIBLE_ECLIPSE_ZONE,
    DECISION_SELECT_TOOL_ACTION,
    DECISION_USE_CAREEN,
    DECISION_USE_GILDED_CHAMPION,
)
from ..decisions import DecisionRequest, DecisionResult
from ._helpers import (
    is_skip_choice,
    resolve_entity,
    resolve_model,
    resolve_player,
    resolve_unit,
    validate_option_choice,
)


def _option_payload(request: DecisionRequest, result: DecisionResult) -> dict:
    for opt in list(getattr(request, "options", []) or []):
        if opt.option_id == result.option_id:
            return dict(getattr(opt, "payload", {}) or {})
    return {}


def _resolve_tool_action_value(game: object, value: Any) -> Any:
    if isinstance(value, dict):
        enum_ref = value.get("__enum_ref__")
        if isinstance(enum_ref, dict):
            return enum_ref.get("value")
        entity_ref = value.get("__entity_ref__")
        if isinstance(entity_ref, dict):
            entity_id = str(entity_ref.get("id", "") or "")
            entity_kind = str(entity_ref.get("kind", "") or "").strip().lower()
            if not entity_id:
                return None
            if entity_kind:
                resolved = resolve_entity(game, entity_id, kind=entity_kind)
                if resolved is not None:
                    return resolved
            for fallback_kind in ("unit", "model", "objective", "terrain", "player", "army", "wargear"):
                resolved = resolve_entity(game, entity_id, kind=fallback_kind)
                if resolved is not None:
                    return resolved
            return None
        return {str(key): _resolve_tool_action_value(game, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_tool_action_value(game, item) for item in value]
    return value


def _resolve_tool_action_kwargs(game: object, payload: dict[str, Any]) -> dict[str, Any]:
    raw_kwargs = payload.get("resolved_kwargs")
    if not isinstance(raw_kwargs, dict):
        raise RuntimeError("Tool action payload missing resolved_kwargs.")
    return {
        str(key): _resolve_tool_action_value(game, value)
        for key, value in dict(raw_kwargs or {}).items()
    }


def _resolve_tool_action_manager(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    player = resolve_player(game, payload.get("player_id") or request.player_id)
    if player is None:
        raise RuntimeError("Tool action player not found.")
    manager = getattr(player, "stratagems", None)
    if manager is None:
        raise RuntimeError("Tool action stratagem manager not found.")
    return manager, payload


def _prepare_tool_action(game: object, request: DecisionRequest, result: DecisionResult):
    manager, payload = _resolve_tool_action_manager(game, request, result)
    tool_family = str(payload.get("tool_family", "") or "stratagem").strip().lower()
    if tool_family != "stratagem":
        raise RuntimeError(f"Unsupported tool action family: {tool_family}")
    tool_name = str(payload.get("tool_name", "") or payload.get("stratagem_name", "") or "").strip()
    if not tool_name:
        raise RuntimeError("Tool action missing tool_name.")
    kwargs = _resolve_tool_action_kwargs(game, payload)
    return manager, tool_name, kwargs, payload


def _missing_tool_action_bindings(manager: object, tool_name: str, kwargs: dict[str, Any]) -> list[str]:
    get_by_name = getattr(manager, "get_by_name", None)
    stratagem = get_by_name(tool_name) if callable(get_by_name) else None
    missing_fn = getattr(manager, "_tool_action_missing_required_bindings", None)
    if stratagem is None or not callable(missing_fn):
        return []
    return list(missing_fn(stratagem, kwargs) or [])


def _record_escaped_malformed_tool_action(
    manager: object,
    tool_name: str,
    kwargs: dict[str, Any],
    missing_keys: list[str],
) -> None:
    get_by_name = getattr(manager, "get_by_name", None)
    stratagem = get_by_name(tool_name) if callable(get_by_name) else None
    record_fn = getattr(manager, "_record_tool_action_probe_diagnostic", None)
    if stratagem is None or not callable(record_fn):
        return
    record_fn(
        stratagem=stratagem,
        kwargs=kwargs,
        missing_keys=missing_keys,
        severity="ERROR",
        code="malformed_tool_candidate_escaped_preflight",
        resolver="select_tool_action_handler",
    )


def _validate_select_tool_action(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        try:
            _resolve_tool_action_manager(game, request, result)
        except RuntimeError as exc:
            return (str(exc),)
        return ()
    try:
        manager, tool_name, kwargs, payload = _prepare_tool_action(game, request, result)
    except RuntimeError as exc:
        return (str(exc),)
    missing = _missing_tool_action_bindings(manager, tool_name, kwargs)
    if missing:
        _record_escaped_malformed_tool_action(manager, tool_name, kwargs, missing)
        return (f"{tool_name} missing required tool context: {', '.join(missing)}.",)
    if not bool(getattr(manager, "can_use", None) and manager.can_use(tool_name, **kwargs)):
        return (f"{tool_name} is no longer a valid tool action.",)
    return ()


def _apply_select_tool_action(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        manager, payload = _resolve_tool_action_manager(game, request, result)
        tool_name = ""
        kwargs = {}
    else:
        manager, tool_name, kwargs, payload = _prepare_tool_action(game, request, result)
        missing = _missing_tool_action_bindings(manager, tool_name, kwargs)
        if missing:
            _record_escaped_malformed_tool_action(manager, tool_name, kwargs, missing)
            raise RuntimeError(f"{tool_name} missing required tool context: {', '.join(missing)}.")
    signature = str(dict(getattr(request, "context", {}) or {}).get("tool_action_signature", "") or "")
    if is_skip_choice(request, result):
        mark_skipped = getattr(manager, "_mark_tool_action_signature_skipped", None)
        if callable(mark_skipped) and signature:
            mark_skipped(signature)
        return None
    clear_skipped = getattr(manager, "_clear_tool_action_signature_skip", None)
    if callable(clear_skipped) and signature:
        clear_skipped(signature)
    ok = manager.use(tool_name, **kwargs)
    if not ok:
        raise RuntimeError(f"{tool_name} could not be applied.")
    return {
        "tool_family": str(payload.get("tool_family", "") or "stratagem"),
        "tool_name": tool_name,
    }


register_decision_handler(
    DECISION_SELECT_TOOL_ACTION,
    validate=_validate_select_tool_action,
    apply=_apply_select_tool_action,
)


def _prepare_gilded_champion(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    player = resolve_player(game, payload.get("player_id") or request.player_id)
    if player is None:
        raise RuntimeError("Gilded Champion player not found.")
    manager = getattr(player, "stratagems", None)
    if manager is None:
        raise RuntimeError("Gilded Champion stratagem manager not found.")
    model = resolve_model(game, payload.get("model_id") or payload.get("model"))
    if model is None:
        raise RuntimeError("Gilded Champion model not found.")
    ability_key = str(payload.get("ability_key", "") or "").strip().lower()
    ability_name = str(payload.get("ability_name", "") or "")
    phase_name = str(payload.get("phase_name", "") or "")
    source = str(payload.get("source", "datasheet") or "datasheet")
    prepared = manager._gilded_champion_prepare(
        model=model,
        ability_key=ability_key,
        ability_name=ability_name,
        phase_name=phase_name,
        source=source,
        game=game,
    )
    if prepared is None:
        raise RuntimeError("Gilded Champion context is no longer valid.")
    return manager, prepared


def _validate_use_gilded_champion(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    model_id = payload.get("model_id")
    ability_key = payload.get("ability_key")
    if not model_id or not ability_key:
        return ("Gilded Champion requires model_id and ability_key.",)
    try:
        _prepare_gilded_champion(game, request, result)
    except RuntimeError as exc:
        return (str(exc),)
    return ()


def _apply_use_gilded_champion(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    manager, prepared = _prepare_gilded_champion(game, request, result)
    ok = manager.use(
        "GILDED CHAMPION",
        model=prepared.get("model"),
        ability_key=prepared.get("ability_key", ""),
        ability_name=prepared.get("ability_name", ""),
        phase_name=prepared.get("phase_name", ""),
        source=prepared.get("source", "datasheet"),
        target_unit=prepared.get("target_unit"),
    )
    if not ok:
        raise RuntimeError("Gilded Champion could not be applied.")
    return prepared.get("model_id")


register_decision_handler(
    DECISION_USE_GILDED_CHAMPION,
    validate=_validate_use_gilded_champion,
    apply=_apply_use_gilded_champion,
)


def _prepare_careen(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    player = resolve_player(game, payload.get("player_id") or request.player_id)
    if player is None:
        raise RuntimeError("Careen player not found.")
    manager = getattr(player, "stratagems", None)
    if manager is None:
        raise RuntimeError("Careen stratagem manager not found.")
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit"))
    if unit is None:
        raise RuntimeError("Careen unit not found.")
    model = resolve_model(game, payload.get("model_id") or payload.get("model"))
    if model is None:
        raise RuntimeError("Careen model not found.")
    move_kind = str(payload.get("choice", "") or payload.get("move_kind", "") or payload.get("movement_type", "") or "")
    prepared = manager._careen_prepare(unit=unit, model=model, move_kind=move_kind)
    if prepared is None:
        raise RuntimeError("Careen context is no longer valid.")
    return manager, prepared


def _validate_use_careen(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        try:
            _prepare_careen(game, request, result)
        except RuntimeError as exc:
            return (str(exc),)
        return ()
    try:
        manager, prepared = _prepare_careen(game, request, result)
    except RuntimeError as exc:
        return (str(exc),)
    move_kind = str(prepared.get("move_kind", "") or "")
    if not move_kind:
        return ("Careen requires a move choice.",)
    if move_kind not in set(prepared.get("allowed_modes") or []):
        return ("Careen move choice is not allowed.",)
    if not manager._careen_can_use(prepared):
        return ("Careen cannot be used right now.",)
    return ()


def _apply_use_careen(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        manager, prepared = _prepare_careen(game, request, result)
        unit = prepared.get("unit")
        if unit is None:
            raise RuntimeError("Careen unit not found.")
        unit.resolve_careen_deadly_demise(game_map=getattr(game, "map", None), use_move=False)
        return None
    manager, prepared = _prepare_careen(game, request, result)
    unit = prepared.get("unit")
    model = prepared.get("model")
    move_kind = str(prepared.get("move_kind", "") or "")
    phase_name = str(prepared.get("phase_name", "") or "")
    ok = manager.use(
        "CAREEN!",
        unit=unit,
        target_unit=unit,
        model=model,
        move_kind=move_kind,
        phase_name=phase_name,
    )
    if not ok:
        raise RuntimeError("Careen could not be applied.")
    return prepared.get("unit_id")


register_decision_handler(
    DECISION_USE_CAREEN,
    validate=_validate_use_careen,
    apply=_apply_use_careen,
)


def _validate_choose_impossible_eclipse_zone(
    game: object,
    request: DecisionRequest,
    result: DecisionResult,
) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    zone = str(payload.get("zone", "") or payload.get("choice", "") or payload.get("selection", "") or "").strip().lower()
    if zone not in {"nml", "enemy", "both"}:
        return ("Impossible Eclipse requires selecting No Man's Land, opponent deployment, or both.",)
    return ()


def _apply_choose_impossible_eclipse_zone(
    game: object,
    request: DecisionRequest,
    result: DecisionResult,
):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    zone = str(payload.get("zone", "") or payload.get("choice", "") or payload.get("selection", "") or "").strip().lower()
    return zone or None


register_decision_handler(
    DECISION_CHOOSE_IMPOSSIBLE_ECLIPSE_ZONE,
    validate=_validate_choose_impossible_eclipse_zone,
    apply=_apply_choose_impossible_eclipse_zone,
)
