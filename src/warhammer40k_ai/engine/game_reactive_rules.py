from __future__ import annotations

from .game_mixins.reactive_decisions_mixin import GameReactiveDecisionsMixin
from .game_service_base import GameServiceBase


class ReactiveRulesService(GameReactiveDecisionsMixin, GameServiceBase):
    """Service boundary for reactive decision and interrupt helpers."""

    pass
