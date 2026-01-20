from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import _validate_choice_from_options, register_decision_handler
from ..decision_kinds import DECISION_CONFIRM_EXAMPLE, DECISION_CONFIRM_YES_NO
from ..decisions import DecisionRequest, DecisionResult


def _validate_confirm(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return _validate_choice_from_options(request, result)


def _apply_confirm(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    return None


register_decision_handler(DECISION_CONFIRM_YES_NO, validate=_validate_confirm, apply=_apply_confirm)
register_decision_handler(DECISION_CONFIRM_EXAMPLE, validate=_validate_confirm, apply=_apply_confirm)
