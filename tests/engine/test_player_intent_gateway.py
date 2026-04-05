from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.player_intent_gateway import IntentRoutedGameProxy, PlayerIntentGateway


def test_player_intent_gateway_routes_commands() -> None:
    seen = []

    def _apply(command: GameCommand):
        seen.append(command.kind)
        return SimpleNamespace(ok=True)

    gateway = PlayerIntentGateway(apply_command=_apply)
    result = gateway.submit_command(GameCommand.create("TEST_CMD"))

    assert result.ok is True
    assert seen == ["TEST_CMD"]


def test_player_intent_gateway_requires_decision_handler_when_submitting_requests() -> None:
    gateway = PlayerIntentGateway(apply_command=lambda _command: SimpleNamespace(ok=True))

    with pytest.raises(RuntimeError):
        gateway.submit_decision_request(SimpleNamespace())


def test_intent_routed_game_proxy_delegates_attributes_and_routes_intents() -> None:
    class _Game:
        def __init__(self) -> None:
            self.value = 3

    game = _Game()
    routed = {"commands": 0, "requests": 0}

    gateway = PlayerIntentGateway(
        apply_command=lambda _command: (routed.__setitem__("commands", routed["commands"] + 1) or SimpleNamespace(ok=True)),
        request_decision=lambda _request: routed.__setitem__("requests", routed["requests"] + 1),
    )
    proxy = IntentRoutedGameProxy(game, gateway)

    assert proxy.value == 3
    proxy.value = 7
    assert game.value == 7

    result = proxy.apply_command(GameCommand.create("PING"))
    proxy.request_decision(SimpleNamespace())

    assert result.ok is True
    assert routed == {"commands": 1, "requests": 1}
