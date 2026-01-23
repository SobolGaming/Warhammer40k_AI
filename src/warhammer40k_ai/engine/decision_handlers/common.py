from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import _validate_choice_from_options, register_decision_handler
from ..decision_kinds import DECISION_CONFIRM_EXAMPLE, DECISION_CONFIRM_YES_NO
from ..decisions import DecisionRequest, DecisionResult


def _validate_confirm(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return _validate_choice_from_options(request, result)


def _apply_confirm(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    ctx = dict(getattr(request, "context", {}) or {})
    ability = str(ctx.get("ability", "") or "").strip().lower()
    if ability != "hover_mode":
        return None

    unit_id = str(ctx.get("unit_id", "") or "")
    choice = None
    selected_option = None
    for opt in list(getattr(request, "options", []) or []):
        if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
            selected_option = opt
            break
    if selected_option is not None:
        payload = dict(getattr(selected_option, "payload", {}) or {})
        if "choice" in payload:
            choice = bool(payload.get("choice"))
        if not unit_id:
            unit_id = str(payload.get("unit_id", "") or "")
    if choice is None:
        if "choice" in result.payload:
            choice = bool(result.payload.get("choice"))

    if not unit_id:
        return None

    unit = None
    resolver = getattr(game, "_resolve_unit_by_id", None)
    if callable(resolver):
        unit = resolver(unit_id)
    if unit is None:
        for player in list(getattr(game, "players", []) or []):
            if player is None:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            for candidate in list(getattr(army, "units", []) or []):
                if candidate is None:
                    continue
                if str(getattr(candidate, "_id", "")) == unit_id or str(getattr(candidate, "id", "")) == unit_id:
                    unit = candidate
                    break
            if unit is not None:
                break

    if unit is None or choice is None:
        return None
    setter = getattr(unit, "set_hover_mode", None)
    if callable(setter):
        setter(bool(choice))
    else:
        unit.hover_mode = bool(choice)
    unit.hover_declared = True
    return None


register_decision_handler(DECISION_CONFIRM_YES_NO, validate=_validate_confirm, apply=_apply_confirm)
register_decision_handler(DECISION_CONFIRM_EXAMPLE, validate=_validate_confirm, apply=_apply_confirm)
