from __future__ import annotations

from warhammer40k_ai.UI.phases.phase_manager import BattlePhaseHandler
from warhammer40k_ai.engine.event.system import EventSystem


class _DummyGame:
    def __init__(self, with_event_system: bool = True) -> None:
        self.event_system = EventSystem() if with_event_system else None


class _DummyGameView:
    def __init__(self, game) -> None:
        self.game = game


def test_battle_phase_handler_initializes_pending_movement_state() -> None:
    handler = BattlePhaseHandler(_DummyGameView(_DummyGame(with_event_system=False)))

    assert handler._pending_advance_units == set()
    assert handler._pending_charge_units == {}
    assert handler._pending_move_modifier_actions == {}
    assert handler._pending_pre_move_ability_actions == {}


def test_battle_phase_handler_subscribes_to_roll_made_events() -> None:
    game = _DummyGame(with_event_system=True)
    handler = BattlePhaseHandler(_DummyGameView(game))

    subscribers = list(game.event_system.subscribers.get("roll_made", []))
    assert subscribers
    assert any(
        getattr(callback, "__self__", None) is handler and group == "default"
        for callback, group in subscribers
    )

