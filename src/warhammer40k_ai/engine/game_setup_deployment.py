from __future__ import annotations

from .game_mixins.phase_handlers_mixin import GamePhaseHandlersMixin
from .game_mixins.reactive_decisions_mixin import GameReactiveDecisionsMixin
from .game_mixins.setup_deployment_reserves_mixin import GameSetupDeploymentReservesMixin
from .game_mixins.shooting_fight_handlers_mixin import GameShootingFightHandlersMixin
from .game_service_base import GameServiceBase


class SetupDeploymentService(
    GameSetupDeploymentReservesMixin,
    GameReactiveDecisionsMixin,
    GameShootingFightHandlersMixin,
    GamePhaseHandlersMixin,
    GameServiceBase,
):
    """Service boundary for setup, deployment, and reserves helpers."""

    pass
