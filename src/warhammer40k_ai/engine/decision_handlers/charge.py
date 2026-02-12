from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import DECISION_DECLARE_CHARGE
from ..decisions import DecisionRequest, DecisionResult
from ._helpers import find_option, get_unit, validate_option_choice


def _validate_declare_charge(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    attacker_id = str(payload.get("unit_id", "") or "")
    out_of_turn = bool(payload.get("out_of_turn", False) or request.context.get("out_of_turn", False))
    selected_ids = list(result.payload.get("target_unit_ids", []) or [])
    if not selected_ids:
        target_id = str(payload.get("target_unit_id", "") or "")
        if target_id:
            selected_ids = [target_id]
    if not attacker_id or not selected_ids:
        return ("Charge declaration requires unit_id and target_unit_ids.",)
    attacker = get_unit(game, attacker_id)
    option_targets = {
        str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")
        for opt in list(getattr(request, "options", []) or [])
    }
    if any(str(tid) not in option_targets for tid in selected_ids):
        return ("Charge targets must be selected from valid options.",)
    targets = [get_unit(game, str(tid)) for tid in selected_ids]
    if attacker is None or any(t is None for t in targets):
        return ("Charge declaration units not found.",)
    try:
        if not attacker.can_declare_charge(game, out_of_turn=out_of_turn):
            return ("Unit cannot declare a charge.",)
        for target in targets:
            if not attacker.can_declare_charge_against(target, game, out_of_turn=out_of_turn):
                return ("Unit cannot declare a charge against one or more targets.",)
        sycophantic_active_fn = getattr(attacker, "_carnival_sycophantic_surge_active_for_charge", None)
        sycophantic_target_fn = getattr(attacker, "_carnival_sycophantic_target_condition_met", None)
        if callable(sycophantic_active_fn) and bool(sycophantic_active_fn(game=game)):
            if not callable(sycophantic_target_fn):
                return ("Unit cannot declare this charge (missing target condition validator).",)
            if not any(bool(sycophantic_target_fn(target, game)) for target in list(targets or [])):
                return ("At least one charge target must be within Engagement Range of a friendly EMPEROR'S CHILDREN unit.",)
    except Exception:
        return ("Charge validation failed.",)
    return ()


def _apply_declare_charge(game: object, request: DecisionRequest, result: DecisionResult):
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    out_of_turn = bool(payload.get("out_of_turn", False) or request.context.get("out_of_turn", False))
    attacker = get_unit(game, str(payload.get("unit_id", "") or ""))
    selected_ids = list(result.payload.get("target_unit_ids", []) or [])
    if not selected_ids:
        target_id = str(payload.get("target_unit_id", "") or "")
        if target_id:
            selected_ids = [target_id]
    targets = [get_unit(game, str(tid)) for tid in selected_ids]
    if attacker is None or any(t is None for t in targets):
        raise RuntimeError("Charge declaration units missing.")
    declare_fn = getattr(game, "declare_charge", None)
    if not callable(declare_fn):
        raise RuntimeError("Game missing declare_charge.")
    return declare_fn(attacker, targets, out_of_turn=out_of_turn)


register_decision_handler(DECISION_DECLARE_CHARGE, validate=_validate_declare_charge, apply=_apply_declare_charge)
