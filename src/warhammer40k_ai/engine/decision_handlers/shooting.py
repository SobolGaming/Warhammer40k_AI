from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import (
    DECISION_DECLARE_FIRING_DECK,
    DECISION_DECLARE_SHOTS,
    DECISION_REROLL_ROLL,
    DECISION_SELECT_OVERWATCH_SHOOTER,
    DECISION_SELECT_WEAPON,
)
from ..decisions import DecisionRequest, DecisionResult
from ._helpers import find_option, get_model, get_unit, get_wargear, validate_option_choice


def _validate_select_weapon(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or "")
    wargear_id = str(payload.get("wargear_id", "") or "")
    profile_name = str(payload.get("profile_name", "") or "")
    if not unit_id or not wargear_id or not profile_name:
        return ("Weapon selection requires unit_id, wargear_id, and profile_name.",)
    unit = get_unit(game, unit_id)
    wargear = get_wargear(game, wargear_id)
    if unit is None or wargear is None:
        return ("Weapon selection units not found.",)
    profiles = getattr(wargear, "profiles", {}) or {}
    if profile_name not in profiles:
        return ("Weapon profile not found.",)
    return ()


def _apply_select_weapon(game: object, request: DecisionRequest, result: DecisionResult):
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    return {
        "unit_id": str(payload.get("unit_id", "") or ""),
        "wargear_id": str(payload.get("wargear_id", "") or ""),
        "profile_name": str(payload.get("profile_name", "") or ""),
    }


def _validate_select_overwatch(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    if bool(result.payload.get("skipped", False)) or str(payload.get("action", "") or "") == "skip":
        return ()
    unit_id = str(payload.get("unit_id", "") or "")
    if not unit_id:
        return ("Overwatch selection requires unit_id.",)
    if get_unit(game, unit_id) is None:
        return ("Overwatch unit not found.",)
    return ()


def _apply_select_overwatch(game: object, request: DecisionRequest, result: DecisionResult):
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    if bool(result.payload.get("skipped", False)) or str(payload.get("action", "") or "") == "skip":
        return None
    return get_unit(game, str(payload.get("unit_id", "") or ""))


def _validate_declare_shots(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    if not unit_id:
        return ("Shooting declaration requires unit_id.",)
    unit = get_unit(game, unit_id)
    if unit is None:
        return ("Shooting unit not found.",)
    if bool(result.payload.get("skipped", False)) or str(payload.get("action", "") or "") == "skip":
        return ()
    declarations = result.payload.get("declarations")
    if not isinstance(declarations, list) or not declarations:
        return ("Shooting declaration requires declarations list.",)
    for decl in declarations:
        if not isinstance(decl, dict):
            return ("Declaration entry must be a dict.",)
        wargear_id = str(decl.get("wargear_id", "") or "")
        profile_name = str(decl.get("profile_name", "") or "")
        target_id = str(decl.get("target_unit_id", "") or "")
        model_ids = decl.get("model_ids")
        if not wargear_id or not profile_name or not target_id:
            return ("Declaration missing wargear_id/profile_name/target_unit_id.",)
        wargear = get_wargear(game, wargear_id)
        if wargear is None:
            return ("Declaration wargear not found.",)
        profiles = getattr(wargear, "profiles", {}) or {}
        if profile_name not in profiles:
            return ("Declaration weapon profile not found.",)
        if get_unit(game, target_id) is None:
            return ("Declaration target unit not found.",)
        if not isinstance(model_ids, list) or not model_ids:
            return ("Declaration requires model_ids list.",)
        for model_id in model_ids:
            model = get_model(game, str(model_id or ""))
            if model is None:
                return ("Declaration model not found.",)
    return ()


def _apply_declare_shots(game: object, request: DecisionRequest, result: DecisionResult):
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    unit = get_unit(game, unit_id)
    if unit is None:
        raise RuntimeError("Shooting unit missing.")
    if bool(result.payload.get("skipped", False)) or str(payload.get("action", "") or "") == "skip":
        return False
    game_map = getattr(game, "map", None)
    out_of_phase = bool(request.context.get("out_of_phase", False))
    declarations = []
    for decl in list(result.payload.get("declarations") or []):
        wargear = get_wargear(game, str(decl.get("wargear_id", "") or ""))
        if wargear is None:
            continue
        profile_name = str(decl.get("profile_name", "") or "")
        profile = getattr(wargear, "profiles", {}).get(profile_name)
        if profile is None:
            continue
        target_unit = get_unit(game, str(decl.get("target_unit_id", "") or ""))
        if target_unit is None:
            continue
        models = []
        for model_id in list(decl.get("model_ids") or []):
            model = get_model(game, str(model_id or ""))
            if model is not None:
                models.append(model)
        if not models:
            continue
        entry = {"weapon_profile": profile, "target_unit": target_unit, "models": models}
        fd_ids = decl.get("firing_deck_source_model_ids")
        if isinstance(fd_ids, list) and fd_ids:
            fd_models = [m for m in (get_model(game, str(mid or "")) for mid in fd_ids) if m is not None]
            if fd_models:
                entry["firing_deck_source_models"] = fd_models
        declarations.append(entry)
    if not declarations:
        return False
    return bool(unit.execute_shooting_declarations(declarations, game_map, out_of_phase=out_of_phase))


def _validate_firing_deck(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = dict(result.payload or {})
    selections = payload.get("selected_entries")
    if selections is None:
        return ("Firing deck requires selected_entries.",)
    if not isinstance(selections, list):
        return ("selected_entries must be a list.",)
    for entry in selections:
        if not isinstance(entry, dict):
            return ("selected_entries must contain dicts.",)
        wargear_id = str(entry.get("wargear_id", "") or "")
        profile_name = str(entry.get("profile_name", "") or "")
        model_id = str(entry.get("model_id", "") or "")
        if not wargear_id or not profile_name or not model_id:
            return ("Firing deck entry missing wargear_id/profile_name/model_id.",)
        if get_wargear(game, wargear_id) is None:
            return ("Firing deck wargear not found.",)
        if get_model(game, model_id) is None:
            return ("Firing deck model not found.",)
    return ()


def _apply_firing_deck(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    transport = get_unit(game, str(payload.get("transport_id", "") or request.context.get("transport_id", "") or ""))
    if transport is None:
        raise RuntimeError("Firing deck transport missing.")
    selections = []
    for entry in list(result.payload.get("selected_entries") or []):
        wargear = get_wargear(game, str(entry.get("wargear_id", "") or ""))
        model = get_model(game, str(entry.get("model_id", "") or ""))
        if wargear is None or model is None:
            continue
        profile_name = str(entry.get("profile_name", "") or "")
        profile = getattr(wargear, "profiles", {}).get(profile_name)
        if profile is None:
            continue
        selections.append(
            {
                "model": model,
                "wargear": wargear,
                "profile": profile,
                "profile_name": profile_name,
            }
        )
    transport.apply_firing_deck_virtual_wargear(selections)
    return None


def _validate_reroll(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return validate_option_choice(request, result)


def _apply_reroll(game: object, request: DecisionRequest, result: DecisionResult):
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    return bool(payload.get("reroll", False))


register_decision_handler(DECISION_SELECT_WEAPON, validate=_validate_select_weapon, apply=_apply_select_weapon)
register_decision_handler(DECISION_DECLARE_SHOTS, validate=_validate_declare_shots, apply=_apply_declare_shots)
register_decision_handler(DECISION_DECLARE_FIRING_DECK, validate=_validate_firing_deck, apply=_apply_firing_deck)
register_decision_handler(DECISION_SELECT_OVERWATCH_SHOOTER, validate=_validate_select_overwatch, apply=_apply_select_overwatch)
register_decision_handler(DECISION_REROLL_ROLL, validate=_validate_reroll, apply=_apply_reroll)
