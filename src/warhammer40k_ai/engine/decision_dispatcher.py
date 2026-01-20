from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .decisions import DecisionRequest, DecisionResult

DecisionValidator = Callable[[object, DecisionRequest, DecisionResult], Sequence[str]]
DecisionApplier = Callable[[object, DecisionRequest, DecisionResult], Any]


@dataclass(frozen=True)
class DecisionApplyResult:
    decision_id: str
    decision_type: str
    ok: bool
    errors: tuple[str, ...] = ()
    value: Any = None


@dataclass(frozen=True)
class DecisionHandler:
    decision_type: str
    validate: DecisionValidator
    apply: DecisionApplier


_HANDLERS: dict[str, DecisionHandler] = {}


def register_decision_handler(
    decision_type: str,
    *,
    validate: DecisionValidator,
    apply: DecisionApplier,
) -> None:
    if decision_type in _HANDLERS:
        raise ValueError(f"Decision handler already registered: {decision_type}")
    _HANDLERS[decision_type] = DecisionHandler(
        decision_type=decision_type,
        validate=validate,
        apply=apply,
    )


def dispatch_decision(game: object, request: DecisionRequest, result: DecisionResult) -> DecisionApplyResult:
    if request is None:
        return DecisionApplyResult(decision_id="", decision_type="", ok=False, errors=("Missing decision request",))
    if result is None:
        return DecisionApplyResult(
            decision_id=request.decision_id,
            decision_type=request.decision_type,
            ok=False,
            errors=("Missing decision result",),
        )
    handler = _HANDLERS.get(request.decision_type)
    if handler is None:
        return DecisionApplyResult(
            decision_id=request.decision_id,
            decision_type=request.decision_type,
            ok=False,
            errors=(f"Unknown decision type: {request.decision_type}",),
        )
    errors = tuple(handler.validate(game, request, result) or ())
    if errors:
        return DecisionApplyResult(
            decision_id=request.decision_id,
            decision_type=request.decision_type,
            ok=False,
            errors=errors,
        )
    value = handler.apply(game, request, result)
    return DecisionApplyResult(
        decision_id=request.decision_id,
        decision_type=request.decision_type,
        ok=True,
        value=value,
    )


def _validate_choice_from_options(request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    options = list(getattr(request, "options", []) or [])
    if not options:
        return ("Decision has no options to choose from.",)
    if result.option_id not in {opt.option_id for opt in options}:
        return ("Selected option_id is not valid for this decision.",)
    return ()


def validate_decision(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    if request is None:
        return ("Missing decision request",)
    if result is None:
        return ("Missing decision result",)
    handler = _HANDLERS.get(request.decision_type)
    if handler is None:
        return (f"Unknown decision type: {request.decision_type}",)
    return tuple(handler.validate(game, request, result) or ())


# Ensure default decision handlers are registered.
from . import decision_handlers  # noqa: E402,F401
