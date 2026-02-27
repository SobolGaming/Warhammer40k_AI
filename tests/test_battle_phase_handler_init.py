from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.UI.phases.phase_manager import BattlePhaseHandler
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.units.unit import MovementAction


class _DummyGame:
    def __init__(self, with_event_system: bool = True) -> None:
        self.event_system = EventSystem() if with_event_system else None


class _DummyGameView:
    def __init__(self, game) -> None:
        self.game = game


class _DummyDecisionQueue:
    def list(self):
        return []


class _DummyMovementChoiceDialog:
    def __init__(self, choice: str) -> None:
        self.choice = choice

    def show(self, unit, callback, _game_map, decision_request=None):
        assert decision_request is not None
        callback(self.choice)


class _DummyMovementGame:
    def __init__(self, *, apply_ok: bool = True) -> None:
        self.event_system = None
        self.map = object()
        self.decision_queue = _DummyDecisionQueue()
        self._player = SimpleNamespace(id="player-1")
        self.requested_decisions = []
        self.apply_ok = apply_ok

    def get_current_player(self):
        return self._player

    def request_decision(self, req):
        self.requested_decisions.append(req)
        return req

    def apply_command(self, _cmd):
        return SimpleNamespace(ok=self.apply_ok)


class _DummyMovementGameView:
    def __init__(self, game: _DummyMovementGame, *, choice: str = "advance") -> None:
        self.game = game
        self.movement_choice_dialog = _DummyMovementChoiceDialog(choice)
        self.selected_unit_for_movement = None
        self.movement_action = None
        self.selected_model_for_movement = None

    def _maybe_prompt_battle_focus_move(self, _unit, _choice, callback):
        callback()


class _DummyMovementUnit:
    def __init__(self) -> None:
        self.id = "unit-shalaxi"
        self.name = "Shalaxi Helbane"
        self.is_transport = False
        self.movement = 14
        self.round_state = SimpleNamespace(advance_roll=None)

    def get_engagement_state(self, _game_map):
        return SimpleNamespace(value=0)

    def get_available_move_actions(self, _engagement_state):
        return [
            MovementAction.MOVE.value,
            MovementAction.ADVANCE.value,
            MovementAction.REMAIN_STATIONARY.value,
        ]


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


def test_advance_choice_does_not_create_second_select_movement_decision() -> None:
    game = _DummyMovementGame(apply_ok=True)
    game_view = _DummyMovementGameView(game, choice="advance")
    handler = BattlePhaseHandler(game_view)
    unit = _DummyMovementUnit()

    handler._handle_movement_phase_selection(unit)

    assert len(game.requested_decisions) == 1
    assert "Advance with" not in str(game.requested_decisions[0].prompt)
    assert unit.id in handler._pending_advance_units


def test_movement_choice_not_processed_when_resolution_is_rejected() -> None:
    game = _DummyMovementGame(apply_ok=False)
    game_view = _DummyMovementGameView(game, choice="advance")
    handler = BattlePhaseHandler(game_view)
    unit = _DummyMovementUnit()
    seen = []
    handler._handle_movement_choice = lambda u, c: seen.append((u, c))

    handler._handle_movement_phase_selection(unit)

    assert len(game.requested_decisions) == 1
    assert seen == []
