from __future__ import annotations

from typing import Optional

from .decisions import CandidateAction, DecisionOption, DecisionRequest


def create_decision_request(
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
    Engine-owned construction shim for UI/requesting layers.

    UI modules should avoid instantiating DecisionRequest directly and use this
    bridge so request construction remains anchored in engine code.
    """
    return DecisionRequest.create(
        decision_type,
        prompt,
        player_id=player_id,
        options=list(options or []),
        context=dict(context or {}),
        candidates=list(candidates or []),
        mask=list(mask) if mask is not None else None,
    )


def queue_decision_request(
    game: object,
    decision_type: str,
    prompt: str,
    *,
    player_id: Optional[str] = None,
    options: list[DecisionOption] | None = None,
    context: dict | None = None,
    candidates: list[CandidateAction] | None = None,
    mask: list[bool] | None = None,
) -> DecisionRequest:
    request = create_decision_request(
        decision_type,
        prompt,
        player_id=player_id,
        options=options,
        context=context,
        candidates=candidates,
        mask=mask,
    )
    request_fn = getattr(game, "request_decision", None)
    if not callable(request_fn):
        raise RuntimeError("Game missing request_decision.")
    request_fn(request)
    return request


def queue_existing_decision_request(game: object, request: DecisionRequest) -> DecisionRequest:
    if request is None:
        raise ValueError("Decision request is required.")
    request_fn = getattr(game, "request_decision", None)
    if not callable(request_fn):
        raise RuntimeError("Game missing request_decision.")
    request_fn(request)
    return request
