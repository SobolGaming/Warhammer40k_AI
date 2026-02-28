from __future__ import annotations

from types import MethodType, SimpleNamespace

from warhammer40k_ai.UI.game_ui import GameView
from warhammer40k_ai.engine.event.system import EventSystem


class _HookHarness:
    def __init__(self, game: object):
        self.game = game
        self._subscribed_event_system = None
        self._subscribed_game = None
        self._ui_event_hook_group = ""
        self._decision_controller = None

    def __getattr__(self, name: str):
        if name.startswith("_on_"):
            return lambda **_kwargs: None
        raise AttributeError(name)


def _subscriber_count(event_system: EventSystem) -> int:
    return sum(len(items) for items in list(event_system.subscribers.values()))


def test_subscribe_event_hooks_is_idempotent_for_same_game():
    game = SimpleNamespace(event_system=EventSystem())
    harness = _HookHarness(game)
    harness._unsubscribe_event_hooks = MethodType(GameView._unsubscribe_event_hooks, harness)

    GameView._subscribe_event_hooks(harness)
    first = _subscriber_count(game.event_system)
    assert first > 0

    GameView._subscribe_event_hooks(harness)
    second = _subscriber_count(game.event_system)
    assert second == first


def test_subscribe_event_hooks_detaches_old_game_on_swap():
    game_one = SimpleNamespace(event_system=EventSystem())
    game_two = SimpleNamespace(event_system=EventSystem())
    harness = _HookHarness(game_one)
    harness._unsubscribe_event_hooks = MethodType(GameView._unsubscribe_event_hooks, harness)

    GameView._subscribe_event_hooks(harness)
    first = _subscriber_count(game_one.event_system)
    assert first > 0

    harness.game = game_two
    GameView._subscribe_event_hooks(harness)

    assert _subscriber_count(game_one.event_system) == 0
    assert _subscriber_count(game_two.event_system) == first
