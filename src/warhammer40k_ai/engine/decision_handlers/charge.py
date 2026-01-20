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
    target_id = str(payload.get("target_unit_id", "") or "")
    if not attacker_id or not target_id:
        return ("Charge declaration requires unit_id and target_unit_id.",)
    attacker = get_unit(game, attacker_id)
    target = get_unit(game, target_id)
    if attacker is None or target is None:
        return ("Charge declaration units not found.",)
    try:
        if not attacker.can_declare_charge_against(target, game):
            return ("Unit cannot declare a charge against this target.",)
    except Exception:
        return ("Charge validation failed.",)
    return ()


def _apply_declare_charge(game: object, request: DecisionRequest, result: DecisionResult):
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    attacker = get_unit(game, str(payload.get("unit_id", "") or ""))
    target = get_unit(game, str(payload.get("target_unit_id", "") or ""))
    if attacker is None or target is None:
        raise RuntimeError("Charge declaration units missing.")
    declare_fn = getattr(game, "declare_charge", None)
    if not callable(declare_fn):
        raise RuntimeError("Game missing declare_charge.")
    return declare_fn(attacker, target)


register_decision_handler(DECISION_DECLARE_CHARGE, validate=_validate_declare_charge, apply=_apply_declare_charge)
