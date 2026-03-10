from __future__ import annotations

from typing import Optional

from .decisions import CandidateAction, DecisionOption, DecisionRequest

def _is_context_subset(request_context: dict, expected_context: dict) -> bool:
    for key, expected_value in dict(expected_context or {}).items():
        if key not in request_context:
            return False
        if request_context.get(key) != expected_value:
            return False
    return True


def require_pending_decision_request(
    game: object | None,
    decision_type: str,
    prompt: str,
    *,
    player_id: Optional[str] = None,
    options: list[DecisionOption] | None = None,
    context: dict | None = None,
    candidates: list[CandidateAction] | None = None,
    mask: list[bool] | None = None,
) -> DecisionRequest:
    """
    Return an already-issued pending request from the authoritative queue.

    UI callers must consume existing requests and must not originate request
    construction/enqueue via UI code paths.
    """
    del prompt, options, candidates, mask
    if game is None:
        raise RuntimeError(f"Cannot consume pending decision '{decision_type}' without game context.")
    queue = getattr(game, "decision_queue", None)
    list_fn = getattr(queue, "list", None) if queue is not None else None
    if not callable(list_fn):
        raise RuntimeError(f"Game missing decision queue for pending decision '{decision_type}'.")
    pending_requests = list(list_fn() or [])
    expected_context = dict(context or {})
    for request in pending_requests:
        if str(getattr(request, "decision_type", "")) != str(decision_type):
            continue
        if player_id is not None and str(getattr(request, "player_id", "")) != str(player_id):
            continue
        request_context = dict(getattr(request, "context", {}) or {})
        if expected_context and not _is_context_subset(request_context, expected_context):
            continue
        return request
    raise RuntimeError(f"No pending decision request found for '{decision_type}'.")
