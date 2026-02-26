from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .command_dispatcher import CommandResult
from .commands import GameCommand
from .decisions import DecisionRequest


class PlayerIntentGateway:
    """Shared intake point for UI-originated commands/decisions."""

    def __init__(
        self,
        *,
        apply_command: Callable[[GameCommand], CommandResult],
        request_decision: Callable[[DecisionRequest], None] | None = None,
    ) -> None:
        self._apply_command = apply_command
        self._request_decision = request_decision

    def submit_command(self, command: GameCommand) -> CommandResult:
        if command is None:
            raise ValueError("command is required.")
        return self._apply_command(command)

    def submit_decision_request(self, request: DecisionRequest) -> None:
        if request is None:
            return
        if self._request_decision is None:
            raise RuntimeError("Decision request submission is not configured.")
        self._request_decision(request)


class IntentRoutedGameProxy:
    """
    Game facade that routes player intents through a shared gateway while
    delegating all other access to the wrapped game object.
    """

    def __init__(self, game: object, gateway: PlayerIntentGateway) -> None:
        object.__setattr__(self, "_game", game)
        object.__setattr__(self, "_gateway", gateway)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._game, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_game", "_gateway"}:
            object.__setattr__(self, name, value)
            return
        setattr(self._game, name, value)

    def apply_command(self, command: GameCommand):
        return self._gateway.submit_command(command)

    def request_decision(self, request: DecisionRequest) -> None:
        self._gateway.submit_decision_request(request)
