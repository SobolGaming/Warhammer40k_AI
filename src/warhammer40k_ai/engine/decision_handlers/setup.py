from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import _validate_choice_from_options, register_decision_handler
from ..decision_kinds import DECISION_CHOOSE_MISSION, DECISION_CONFIRM_MODAL
from ..decisions import DecisionOption, DecisionRequest, DecisionResult


def _find_option(request: DecisionRequest, option_id: str) -> DecisionOption | None:
    for opt in list(getattr(request, "options", []) or []):
        if opt.option_id == option_id:
            return opt
    return None


def _validate_choose_mission(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(_validate_choice_from_options(request, result))
    if errors:
        return errors
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    combo = payload.get("combination")
    if not isinstance(combo, dict):
        return ("Mission selection requires combination dict in option payload.",)
    required = {"id", "primary", "deployment", "layouts"}
    missing = required - set(combo.keys())
    if missing:
        return (f"Mission combination missing keys: {sorted(missing)}",)
    layout = result.payload.get("layout")
    if layout is None:
        return ("Mission selection requires layout in result payload.",)
    if layout not in list(combo.get("layouts", []) or []):
        return ("Selected layout is not valid for this mission combination.",)
    return ()


def _apply_choose_mission(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    combo = payload.get("combination")
    layout = result.payload.get("layout")
    apply_fn = getattr(game, "_apply_selected_mission", None)
    if not callable(apply_fn):
        raise RuntimeError("Game missing _apply_selected_mission.")
    apply_fn(combo, layout)
    return None


def _validate_confirm_modal(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return _validate_choice_from_options(request, result)


def _apply_confirm_modal(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    return None


register_decision_handler(DECISION_CHOOSE_MISSION, validate=_validate_choose_mission, apply=_apply_choose_mission)
register_decision_handler(DECISION_CONFIRM_MODAL, validate=_validate_confirm_modal, apply=_apply_confirm_modal)
