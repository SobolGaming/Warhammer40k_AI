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
    DECISION_SELECT_EXPLODING_HORRORS_MODELS,
    DECISION_SELECT_EXPLODING_HORRORS_TARGET,
    DECISION_SELECT_PRECISION_TARGET,
    DECISION_SELECT_TARGET_MODEL,
    DECISION_SPLIT_ATTACKS,
)
from ..decisions import DecisionRequest, DecisionResult
from ._helpers import find_option, is_skip_choice, resolve_model, resolve_unit, resolve_wargear, validate_option_choice


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


def _validate_select_exploding_horrors_target(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    target_val = payload.get("target_unit_id", payload.get("unit_id", payload.get("unit")))
    if target_val is None:
        return ("Exploding Horrors requires a target unit or skip.",)
    if resolve_unit(game, target_val) is None:
        return ("Exploding Horrors target unit not found.",)
    return ()


def _apply_select_exploding_horrors_target(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    target_val = payload.get("target_unit_id", payload.get("unit_id", payload.get("unit")))
    return resolve_unit(game, target_val)


def _validate_select_exploding_horrors_models(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    model_ids = result.payload.get("model_ids")
    if not isinstance(model_ids, list) or not model_ids:
        return ("Exploding Horrors requires model_ids.",)
    ctx = getattr(request, "context", {}) or {}
    allowed_ids = {str(v) for v in list(ctx.get("allowed_model_ids") or []) if v is not None}
    unit_val = ctx.get("unit_id")
    unit = resolve_unit(game, unit_val) if unit_val is not None else None
    seen: set[str] = set()
    for mid in list(model_ids or []):
        mid = str(mid or "")
        if not mid:
            return ("Exploding Horrors requires valid model_ids.",)
        if mid in seen:
            return ("Exploding Horrors model_ids must be unique.",)
        seen.add(mid)
        model = resolve_model(game, mid)
        if model is None:
            return ("Exploding Horrors model not found.",)
        if unit is not None and getattr(model, "parent_unit", None) is not unit:
            return ("Exploding Horrors model does not belong to the unit.",)
        if allowed_ids and mid not in allowed_ids:
            return ("Exploding Horrors model is not eligible.",)
    return ()


def _apply_select_exploding_horrors_models(game: object, request: DecisionRequest, result: DecisionResult):
    models = []
    for mid in list(result.payload.get("model_ids") or []):
        model = resolve_model(game, mid)
        if model is not None:
            models.append(model)
    return models


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
    ctx = dict(getattr(request, "context", {}) or {})
    allowed_ids = {str(v) for v in list(ctx.get("allowed_model_ids") or []) if v is not None}
    if allowed_ids and str(model_val) not in allowed_ids:
        return ("Precision target model is not eligible.",)
    if resolve_model(game, model_val) is None:
        return ("Precision target model not found.",)
    return ()


def _apply_select_precision(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    model_val = payload.get("model_id", payload.get("model"))
    if model_val in (None, ""):
        ctx = dict(getattr(request, "context", {}) or {})
        seq_id = ctx.get("sequence_id")
        save_index = ctx.get("save_index")
        if seq_id is not None and save_index is not None:
            mgr = getattr(game, "attack_manager", None)
            if mgr is not None:
                try:
                    seq = mgr.sequences.get(int(seq_id))
                except Exception:
                    seq = None
                if seq is not None:
                    try:
                        mgr.resume_after_precision_choice(game, seq, int(save_index), None)
                    except Exception:
                        pass
        return None
    model = resolve_model(game, model_val)
    ctx = dict(getattr(request, "context", {}) or {})
    seq_id = ctx.get("sequence_id")
    save_index = ctx.get("save_index")
    if seq_id is not None and save_index is not None:
        mgr = getattr(game, "attack_manager", None)
        if mgr is not None:
            try:
                seq = mgr.sequences.get(int(seq_id))
            except Exception:
                seq = None
            if seq is not None:
                try:
                    mgr.resume_after_precision_choice(game, seq, int(save_index), str(model_val))
                except Exception:
                    pass
    return model


def _validate_allocate_damage(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    model_val = payload.get("model_id", payload.get("model"))
    ctx = dict(getattr(request, "context", {}) or {})
    if model_val in (None, "") or str(payload.get("action", "") or "") == "skip":
        if not bool(ctx.get("allow_skip", True)):
            return ("Skipping damage allocation is not allowed.",)
        return ()
    allowed_ids = {str(v) for v in list(ctx.get("allowed_model_ids") or []) if v is not None}
    if allowed_ids and str(model_val) not in allowed_ids:
        return ("Damage allocation model is not eligible.",)
    if resolve_model(game, model_val) is None:
        return ("Damage allocation model not found.",)
    return ()


def _apply_allocate_damage(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    model_val = payload.get("model_id", payload.get("model"))
    if model_val in (None, ""):
        return None
    model = resolve_model(game, model_val)
    ctx = dict(getattr(request, "context", {}) or {})
    selection_kind = str(ctx.get("selection_kind", "") or "")
    seq_id = ctx.get("sequence_id")
    if seq_id is not None:
        mgr = getattr(game, "attack_manager", None)
        if mgr is not None:
            try:
                seq = mgr.sequences.get(int(seq_id))
            except Exception:
                seq = None
            if seq is not None:
                try:
                    if selection_kind == "wound_allocation":
                        mgr.resume_after_damage_allocation(game, seq, int(ctx.get("save_index", 0) or 0), str(model_val))
                    elif selection_kind == "hazardous":
                        mgr.resume_after_hazardous_allocation(game, seq, str(model_val))
                    elif selection_kind == "mortal_wound":
                        mgr.resume_after_mortal_allocation(game, seq, int(ctx.get("mortal_entry_index", 0) or 0), str(model_val))
                except Exception:
                    pass
        return model

    if selection_kind == "unit_mortal_wound":
        unit_val = ctx.get("unit_id")
        unit = resolve_unit(game, unit_val)
        if unit is not None:
            remaining = int(ctx.get("remaining_wounds", 0) or 0)
            if remaining > 0:
                from ...utility.damage_allocation import DamageAllocationCtx
                alloc_ctx = DamageAllocationCtx(
                    reason=str(ctx.get("reason", "") or "Allocate mortal wound"),
                    damage_source=str(ctx.get("damage_source", "") or "mortal"),
                    weapon_name=str(ctx.get("weapon_name", "") or ""),
                    attacker_name=str(ctx.get("attacker_name", "") or ""),
                )
                try:
                    unit._apply_mortal_wounds_to_unit(
                        unit,
                        remaining,
                        game_map=getattr(game, "map", None),
                        is_psychic_attack=bool(ctx.get("is_psychic_attack", False)),
                        initial_model=model,
                        allocation_ctx=alloc_ctx,
                        allow_initial_model_outside_candidates=True,
                    )
                except Exception:
                    pass
        return model

    return model


register_decision_handler(DECISION_SELECT_FIGHTER, validate=_validate_select_fighter, apply=_apply_select_fighter)
register_decision_handler(DECISION_SELECT_FIGHT_TARGETS, validate=_validate_select_targets, apply=_apply_select_targets)
register_decision_handler(
    DECISION_SELECT_EXPLODING_HORRORS_TARGET,
    validate=_validate_select_exploding_horrors_target,
    apply=_apply_select_exploding_horrors_target,
)
register_decision_handler(
    DECISION_SELECT_EXPLODING_HORRORS_MODELS,
    validate=_validate_select_exploding_horrors_models,
    apply=_apply_select_exploding_horrors_models,
)
register_decision_handler(DECISION_DECLARE_MELEE_WEAPONS, validate=_validate_declare_melee_weapons, apply=_apply_declare_melee_weapons)
register_decision_handler(DECISION_ALLOCATE_MELEE_TARGETS, validate=_validate_allocate_melee_targets, apply=_apply_allocate_melee_targets)
register_decision_handler(DECISION_ALLOCATE_TARGETS, validate=_validate_allocate_targets, apply=_apply_allocate_targets)
register_decision_handler(DECISION_SPLIT_ATTACKS, validate=_validate_split_attacks, apply=_apply_split_attacks)
register_decision_handler(DECISION_SELECT_TARGET_MODEL, validate=_validate_select_model, apply=_apply_select_model)
register_decision_handler(DECISION_SELECT_PRECISION_TARGET, validate=_validate_select_precision, apply=_apply_select_precision)
register_decision_handler(DECISION_ALLOCATE_DAMAGE, validate=_validate_allocate_damage, apply=_apply_allocate_damage)
