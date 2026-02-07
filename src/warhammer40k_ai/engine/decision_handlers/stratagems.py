from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import (
    DECISION_CHOOSE_IMPOSSIBLE_ECLIPSE_ZONE,
    DECISION_USE_CAREEN,
    DECISION_USE_GILDED_CHAMPION,
)
from ..decisions import DecisionRequest, DecisionResult
from ._helpers import (
    is_skip_choice,
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
