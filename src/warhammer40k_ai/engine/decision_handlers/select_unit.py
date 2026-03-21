from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import DECISION_SELECT_UNIT
from ..decisions import DecisionRequest, DecisionResult
from ._helpers import find_option, get_unit, validate_option_choice


def _selected_payload(request: DecisionRequest, result: DecisionResult) -> dict:
    option = find_option(request, getattr(result, "option_id", ""))
    payload = dict(getattr(option, "payload", {}) or {}) if option is not None else {}
    merged = dict(payload)
    merged.update(dict(getattr(result, "payload", {}) or {}))
    return merged


def _validate_select_unit(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors

    payload = _selected_payload(request, result)
    action = str(payload.get("action", "") or "").strip().lower()
    if action == "pass":
        if not bool(getattr(request, "context", {}).get("allow_pass", False)):
            return ("Select unit: pass is not allowed for this request.",)
        return ()

    option = find_option(request, getattr(result, "option_id", ""))
    option_payload = dict(getattr(option, "payload", {}) or {}) if option is not None else {}
    option_unit_id = str(option_payload.get("unit_id", "") or "").strip()
    result_unit_id = str(getattr(result, "payload", {}).get("unit_id", "") or "").strip()
    selected_unit_id = result_unit_id or option_unit_id
    if not selected_unit_id:
        return ("Select unit requires unit_id.",)
    if result_unit_id and option_unit_id and result_unit_id != option_unit_id:
        return ("Select unit: payload unit_id does not match selected option.",)

    allowed_ids = {
        str(value or "").strip()
        for value in list(getattr(request, "context", {}).get("allowed_unit_ids", []) or [])
        if str(value or "").strip()
    }
    if allowed_ids and selected_unit_id not in allowed_ids:
        return ("Select unit: selected unit is not allowed for this request.",)

    unit = get_unit(game, selected_unit_id)
    if unit is None:
        return ("Select unit: unit not found.",)
    return ()


def _apply_select_unit(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _selected_payload(request, result)
    pass_selected = str(payload.get("action", "") or "").strip().lower() == "pass"
    selected_unit_id = str(payload.get("unit_id", "") or "").strip() or None
    selected_unit = None if pass_selected or not selected_unit_id else get_unit(game, selected_unit_id)

    hook = getattr(game, "on_select_unit_resolved", None)
    if callable(hook):
        hook_value = hook(
            request=request,
            selected_unit_id=selected_unit_id,
            selected_unit=selected_unit,
            payload=dict(payload),
            pass_selected=pass_selected,
        )
        if hook_value is not None:
            return hook_value

    return {
        "selected_unit_id": selected_unit_id,
        "pass_selected": pass_selected,
        "payload": dict(payload),
    }


register_decision_handler(
    DECISION_SELECT_UNIT,
    validate=_validate_select_unit,
    apply=_apply_select_unit,
)
