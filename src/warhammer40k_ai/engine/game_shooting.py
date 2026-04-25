from __future__ import annotations

from .game_mixins.shooting_fight_handlers_mixin import GameShootingFightHandlersMixin
from .game_service_base import GameServiceBase


class ShootingService(GameShootingFightHandlersMixin, GameServiceBase):
    """Service boundary for shooting and heavyweight fight handlers."""

    pass
