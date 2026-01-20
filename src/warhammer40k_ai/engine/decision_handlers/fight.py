from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import (
    DECISION_ALLOCATE_DAMAGE,
    DECISION_ALLOCATE_MELEE_TARGETS,
    DECISION_ALLOCATE_TARGETS,
    DECISION_DECLARE_MELEE_WEAPONS,
    DECISION_SELECT_FIGHTER,
    DECISION_SELECT_FIGHT_TARGETS,
    DECISION_SELECT_PRECISION_TARGET,
    DECISION_SELECT_TARGET_MODEL,
    DECISION_SPLIT_ATTACKS,
)
from ..decisions import DecisionRequest, DecisionResult
from ._helpers import find_option, resolve_model, resolve_unit, resolve_wargear, validate_option_choice


def _option_payload(request: DecisionRequest, result: DecisionResult) -> dict:
    opt = find_option(request, result.option_id)
    return dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}


def _validate_select_fighter(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id", payload.get("unit"))
    unit = resolve_unit(game, unit_val)
    if unit is None:
        return ("Fight selection requires a valid unit.",)
    return ()


def _apply_select_fighter(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id", payload.get("unit"))
    return resolve_unit(game, unit_val)


def _validate_select_targets(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id", request.context.get("unit_id"))
    if unit_val is not None and resolve_unit(game, unit_val) is None:
        return ("Fighting unit not found for target selection.",)
    target_ids = result.payload.get("target_unit_ids")
    if target_ids is None:
        target_single = result.payload.get("target_unit_id")
        if target_single is None:
            return ("Target selection requires target_unit_ids.",)
        target_ids = [target_single]
    if not isinstance(target_ids, list) or not target_ids:
        return ("Target selection requires a non-empty target_unit_ids list.",)
    for target_val in target_ids:
        if resolve_unit(game, target_val) is None:
            return ("Target unit not found.",)
    return ()


def _apply_select_targets(game: object, request: DecisionRequest, result: DecisionResult):
    target_ids = result.payload.get("target_unit_ids")
    if target_ids is None:
        target_single = result.payload.get("target_unit_id")
        target_ids = [target_single] if target_single is not None else []
    units = []
    for target_val in list(target_ids or []):
        unit = resolve_unit(game, target_val)
        if unit is not None:
            units.append(unit)
    return units


def _validate_declare_melee_weapons(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id", request.context.get("unit_id"))
    if unit_val is not None and resolve_unit(game, unit_val) is None:
        return ("Melee weapon declaration unit not found.",)
    bundles = result.payload.get("weapon_bundles") or result.payload.get("weapon_declarations")
    if not isinstance(bundles, list) or not bundles:
        return ("Melee weapon declaration requires weapon_bundles.",)
    for entry in bundles:
        if not isinstance(entry, dict):
            return ("Weapon bundle entry must be a dict.",)
        model_val = entry.get("model_id", entry.get("model"))
        wargear_val = entry.get("wargear_id", entry.get("wargear"))
        profile_name = str(entry.get("profile_name", "") or "")
        if not model_val or not wargear_val or not profile_name:
            return ("Weapon bundle requires model_id, wargear_id, and profile_name.",)
        model = resolve_model(game, model_val)
        wargear = resolve_wargear(game, wargear_val)
        if model is None or wargear is None:
            return ("Weapon bundle model/wargear not found.",)
        profiles = getattr(wargear, "profiles", {}) or {}
        if profile_name not in profiles:
            return ("Weapon bundle profile not found.",)
    return ()


def _apply_declare_melee_weapons(game: object, request: DecisionRequest, result: DecisionResult):
    bundles = result.payload.get("weapon_bundles") or result.payload.get("weapon_declarations") or []
    declarations = []
    for entry in list(bundles or []):
        if not isinstance(entry, dict):
            continue
        model = resolve_model(game, entry.get("model_id", entry.get("model")))
        wargear = resolve_wargear(game, entry.get("wargear_id", entry.get("wargear")))
        profile_name = str(entry.get("profile_name", "") or "")
        if model is None or wargear is None:
            continue
        profile = getattr(wargear, "profiles", {}).get(profile_name)
        if profile is None:
            continue
        declarations.append(
            {
                "model": model,
                "weapon_profile": profile,
                "wargear": wargear,
                "profile_name": profile_name,
            }
        )
    return declarations


def _validate_allocate_melee_targets(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    declarations = result.payload.get("attack_declarations")
    if not isinstance(declarations, list) or not declarations:
        return ("Attack declarations are required.",)
    for entry in declarations:
        if not isinstance(entry, dict):
            return ("Attack declaration entry must be a dict.",)
        model_val = entry.get("model_id", entry.get("model"))
        wargear_val = entry.get("wargear_id", entry.get("wargear"))
        profile_name = str(entry.get("profile_name", "") or "")
        target_val = entry.get("target_unit_id", entry.get("target_unit"))
        if not model_val or not wargear_val or not profile_name or not target_val:
            return ("Attack declaration requires model_id, wargear_id, profile_name, and target_unit_id.",)
        if resolve_model(game, model_val) is None:
            return ("Attack declaration model not found.",)
        wargear = resolve_wargear(game, wargear_val)
        if wargear is None:
            return ("Attack declaration wargear not found.",)
        profiles = getattr(wargear, "profiles", {}) or {}
        if profile_name not in profiles:
            return ("Attack declaration profile not found.",)
        if resolve_unit(game, target_val) is None:
            return ("Attack declaration target unit not found.",)
    return ()


def _apply_allocate_melee_targets(game: object, request: DecisionRequest, result: DecisionResult):
    declarations = []
    for entry in list(result.payload.get("attack_declarations") or []):
        if not isinstance(entry, dict):
            continue
        model = resolve_model(game, entry.get("model_id", entry.get("model")))
        wargear = resolve_wargear(game, entry.get("wargear_id", entry.get("wargear")))
        profile_name = str(entry.get("profile_name", "") or "")
        target_unit = resolve_unit(game, entry.get("target_unit_id", entry.get("target_unit")))
        if model is None or wargear is None or target_unit is None:
            continue
        profile = getattr(wargear, "profiles", {}).get(profile_name)
        if profile is None:
            continue
        decl = {
            "model": model,
            "weapon_profile": profile,
            "wargear": wargear,
            "profile_name": profile_name,
            "target_unit": target_unit,
        }
        if "attacks_override" in entry:
            decl["attacks_override"] = int(entry.get("attacks_override") or 0)
        if "attacks_override_modifiers" in entry:
            decl["attacks_override_modifiers"] = list(entry.get("attacks_override_modifiers") or [])
        if "attacks_override_note" in entry:
            decl["attacks_override_note"] = str(entry.get("attacks_override_note", "") or "")
        declarations.append(decl)
    return declarations


def _validate_allocate_targets(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    allocations = result.payload.get("target_allocations")
    if not isinstance(allocations, dict) or not allocations:
        return ("Target allocations require target_allocations dict.",)
    for target_val, model_vals in allocations.items():
        if resolve_unit(game, target_val) is None:
            return ("Target allocation unit not found.",)
        if not isinstance(model_vals, list) or not model_vals:
            return ("Target allocation models must be a non-empty list.",)
        for model_val in model_vals:
            if resolve_model(game, model_val) is None:
                return ("Target allocation model not found.",)
    return ()


def _apply_allocate_targets(game: object, request: DecisionRequest, result: DecisionResult):
    allocations = {}
    for target_val, model_vals in dict(result.payload.get("target_allocations") or {}).items():
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            continue
        models = []
        for model_val in list(model_vals or []):
            model = resolve_model(game, model_val)
            if model is not None:
                models.append(model)
        if models:
            allocations[target_unit] = models
    return allocations


def _validate_split_attacks(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    allocations = result.payload.get("split_allocations")
    if not isinstance(allocations, dict) or not allocations:
        return ("Split attacks require split_allocations dict.",)
    for target_val, count in allocations.items():
        if resolve_unit(game, target_val) is None:
            return ("Split target unit not found.",)
        try:
            int(count)
        except (TypeError, ValueError):
            return ("Split allocation counts must be integers.",)
    return ()


def _apply_split_attacks(game: object, request: DecisionRequest, result: DecisionResult):
    allocations = {}
    for target_val, count in dict(result.payload.get("split_allocations") or {}).items():
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            continue
        allocations[target_unit] = int(count or 0)
    attack_info = dict(result.payload.get("attack_info") or {})
    return {"allocations": allocations, "attack_info": attack_info}


def _validate_select_model(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    model_val = payload.get("model_id", payload.get("model"))
    if model_val in (None, ""):
        return ()
    if resolve_model(game, model_val) is None:
        return ("Selected model not found.",)
    return ()


def _apply_select_model(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    model_val = payload.get("model_id", payload.get("model"))
    if model_val in (None, ""):
        return None
    return resolve_model(game, model_val)


def _validate_select_precision(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    model_val = payload.get("model_id", payload.get("model"))
    if model_val in (None, ""):
        return ()
    if resolve_model(game, model_val) is None:
        return ("Precision target model not found.",)
    return ()


def _apply_select_precision(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    model_val = payload.get("model_id", payload.get("model"))
    if model_val in (None, ""):
        return None
    return resolve_model(game, model_val)


def _validate_allocate_damage(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    model_val = payload.get("model_id", payload.get("model"))
    if model_val in (None, ""):
        return ()
    if resolve_model(game, model_val) is None:
        return ("Damage allocation model not found.",)
    return ()


def _apply_allocate_damage(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    model_val = payload.get("model_id", payload.get("model"))
    if model_val in (None, ""):
        return None
    return resolve_model(game, model_val)


register_decision_handler(DECISION_SELECT_FIGHTER, validate=_validate_select_fighter, apply=_apply_select_fighter)
register_decision_handler(DECISION_SELECT_FIGHT_TARGETS, validate=_validate_select_targets, apply=_apply_select_targets)
register_decision_handler(DECISION_DECLARE_MELEE_WEAPONS, validate=_validate_declare_melee_weapons, apply=_apply_declare_melee_weapons)
register_decision_handler(DECISION_ALLOCATE_MELEE_TARGETS, validate=_validate_allocate_melee_targets, apply=_apply_allocate_melee_targets)
register_decision_handler(DECISION_ALLOCATE_TARGETS, validate=_validate_allocate_targets, apply=_apply_allocate_targets)
register_decision_handler(DECISION_SPLIT_ATTACKS, validate=_validate_split_attacks, apply=_apply_split_attacks)
register_decision_handler(DECISION_SELECT_TARGET_MODEL, validate=_validate_select_model, apply=_apply_select_model)
register_decision_handler(DECISION_SELECT_PRECISION_TARGET, validate=_validate_select_precision, apply=_apply_select_precision)
register_decision_handler(DECISION_ALLOCATE_DAMAGE, validate=_validate_allocate_damage, apply=_apply_allocate_damage)
