from __future__ import annotations

from typing import Any, Optional, Tuple

from ..engine.command_kinds import CMD_RESOLVE_DECISION
from ..engine.commands import GameCommand
from ..engine.decisions import DecisionRequest


def decision_request_is_pending(game: object, request: DecisionRequest) -> bool:
    if request is None:
        return False
    queue = getattr(game, "decision_queue", None)
    if queue is None or not hasattr(queue, "get"):
        return False
    decision_id = str(getattr(request, "decision_id", "") or "")
    if not decision_id:
        return False
    return queue.get(decision_id) is not None


def require_synchronous_decision_resolution(
    game: object,
    request: DecisionRequest,
    *,
    detail: str,
) -> None:
    if decision_request_is_pending(game, request):
        raise RuntimeError(str(detail or "Decision request remained pending without a synchronous owner."))


def resolve_decision_command(
    game: object,
    request: DecisionRequest,
    option_id: str,
    *,
    result_payload: Optional[dict] = None,
    player_id: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    if request is None:
        raise ValueError("Decision request is required.")
    payload = {
        "decision_id": request.decision_id,
        "option_id": option_id,
        "result_payload": dict(result_payload or {}),
    }
    cmd = GameCommand.create(
        CMD_RESOLVE_DECISION,
        player_id=player_id or request.player_id,
        payload=payload,
        metadata=dict(metadata or {}),
    )
    return game.apply_command(cmd)


def resolve_or_reuse_decision_value(
    game: object,
    request: DecisionRequest,
    option_id: str,
    *,
    result_payload: Optional[dict] = None,
    player_id: Optional[str] = None,
) -> Tuple[Any, Any]:
    if not decision_request_is_pending(game, request):
        apply_result = getattr(request, "_resolved_decision_apply_result", None)
        if apply_result is not None:
            return getattr(request, "_resolved_decision_value", None), apply_result
    return resolve_decision_value(
        game,
        request,
        option_id,
        result_payload=result_payload,
        player_id=player_id,
    )


def resolve_decision_value(
    game: object,
    request: DecisionRequest,
    option_id: str,
    *,
    result_payload: Optional[dict] = None,
    player_id: Optional[str] = None,
) -> Tuple[Any, Any]:
    cmd_result = resolve_decision_command(
        game,
        request,
        option_id,
        result_payload=result_payload,
        player_id=player_id,
    )
    apply_result = getattr(cmd_result, "value", None)
    if apply_result is None or not getattr(apply_result, "ok", False):
        return None, apply_result
    return getattr(apply_result, "value", None), apply_result


def option_id_for_boolean_choice(request: DecisionRequest, choice: bool) -> Optional[str]:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice", False)) == bool(choice):
            return str(getattr(option, "option_id", "") or "")
    return None


def option_id_for_payload_value(request: DecisionRequest, payload_key: str, expected_value: Any) -> Optional[str]:
    key = str(payload_key or "")
    if not key:
        return None
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if payload.get(key) == expected_value:
            return str(getattr(option, "option_id", "") or "")
    return None


def option_id_for_skip_action(request: DecisionRequest) -> Optional[str]:
    return option_id_for_payload_value(request, "action", "skip")


def choice_from_decision_value(value: Any) -> Optional[bool]:
    if isinstance(value, dict) and "choice" in value:
        return bool(value.get("choice"))
    if isinstance(value, bool):
        return bool(value)
    return None


def resolve_or_reuse_confirmation_choice(
    game: object,
    request: DecisionRequest,
    *,
    preselected_choice: Optional[bool] = None,
    player_id: Optional[str] = None,
) -> Tuple[Optional[bool], Any]:
    if request is None:
        return None, None
    option_id = None
    result_payload = None
    if decision_request_is_pending(game, request):
        if preselected_choice is None:
            return None, None
        option_id = option_id_for_boolean_choice(request, bool(preselected_choice))
        result_payload = {"choice": bool(preselected_choice)}
    else:
        options = list(getattr(request, "options", []) or [])
        if options:
            option_id = str(getattr(options[0], "option_id", "") or "")
    if not option_id:
        return None, None
    value, apply_result = resolve_or_reuse_decision_value(
        game,
        request,
        option_id,
        result_payload=result_payload,
        player_id=player_id,
    )
    choice = choice_from_decision_value(value)
    if (
        choice is None
        and preselected_choice is not None
        and apply_result is not None
        and getattr(apply_result, "ok", False)
    ):
        choice = bool(preselected_choice)
    return choice, apply_result


def resolve_or_reuse_payload_choice(
    game: object,
    request: DecisionRequest,
    *,
    payload_key: str,
    preselected_value: Any = None,
    use_skip_when_pending: bool = False,
    player_id: Optional[str] = None,
) -> Tuple[Any, Any]:
    if request is None:
        return None, None
    option_id = None
    result_payload = None
    if decision_request_is_pending(game, request):
        if preselected_value is not None:
            option_id = option_id_for_payload_value(request, payload_key, preselected_value)
            result_payload = {str(payload_key or ""): preselected_value}
        elif use_skip_when_pending:
            option_id = option_id_for_skip_action(request)
    else:
        options = list(getattr(request, "options", []) or [])
        if options:
            option_id = str(getattr(options[0], "option_id", "") or "")
    if not option_id:
        return None, None
    value, apply_result = resolve_or_reuse_decision_value(
        game,
        request,
        option_id,
        result_payload=result_payload,
        player_id=player_id,
    )
    if isinstance(value, dict) and str(payload_key or "") in value:
        return value.get(str(payload_key or "")), apply_result
    return value, apply_result
