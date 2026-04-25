from __future__ import annotations

from .game_mixins.phase_handlers_mixin import GamePhaseHandlersMixin
from .game_service_base import GameServiceBase


class PhaseHandlerService(GamePhaseHandlersMixin, GameServiceBase):
    """Service boundary for phase start/end rule handlers."""

    pass
