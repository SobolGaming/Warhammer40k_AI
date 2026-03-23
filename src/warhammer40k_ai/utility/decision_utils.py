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


def resolve_decision_command(
    game: object,
    request: DecisionRequest,
    option_id: str,
    *,
    result_payload: Optional[dict] = None,
    player_id: Optional[str] = None,
):
    if request is None:
        raise ValueError("Decision request is required.")
    payload = {
        "decision_id": request.decision_id,
        "option_id": option_id,
        "result_payload": dict(result_payload or {}),
    }
    cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=player_id or request.player_id, payload=payload)
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
