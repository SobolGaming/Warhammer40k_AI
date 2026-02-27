from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.dialogs.movement_choice_dialog import MovementChoiceDialog
from warhammer40k_ai.UI.phases.phase_manager import BattlePhaseHandler


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


class _UnitStub:
    def __init__(self, *, moved_this_round: bool) -> None:
        self.name = "Unit Alpha"
        self.round_state = SimpleNamespace(moved_this_round=bool(moved_this_round))
        self.models = [SimpleNamespace(movement=6)]
        self.movement = 6
        self.is_transport = False


def test_movement_choice_dialog_disables_actions_when_unit_already_moved() -> None:
    dialog = MovementChoiceDialog(1600, 900)
    unit = _UnitStub(moved_this_round=True)
    dialog.show(unit, callback=lambda _choice: None, game_map=None, decision_request=None)

    assert dialog._movement_status_text() == "Already Moved this Phase"
    for action in ("move", "advance", "fall_back", "stationary"):
        assert dialog.is_action_available(action) is False
        assert dialog.button_states[action]["enabled"] is False


class _DecisionQueueStub:
    def list(self):
        return []


class _PlayerStub:
    id = "player-1"


class _GameStub:
    def __init__(self) -> None:
        self.decision_queue = _DecisionQueueStub()
        self.map = object()
        self.requested = []

    def get_current_player(self):
        return _PlayerStub()

    def request_decision(self, request) -> None:
        self.requested.append(request)


class _MovementChoiceDialogStub:
    def __init__(self) -> None:
        self.calls = []

    def show(self, *args, **kwargs) -> None:
        self.calls.append((args, kwargs))


class _GameViewStub:
    def __init__(self, game: _GameStub) -> None:
        self.game = game
        self.movement_choice_dialog = _MovementChoiceDialogStub()


def test_battle_phase_handler_does_not_publish_movement_choice_decision_for_moved_unit() -> None:
    game = _GameStub()
    game_view = _GameViewStub(game)
    handler = BattlePhaseHandler(game_view)
    unit = _UnitStub(moved_this_round=True)

    handler._handle_movement_phase_selection(unit)

    assert game.requested == []
    assert len(game_view.movement_choice_dialog.calls) == 1
    _, kwargs = game_view.movement_choice_dialog.calls[0]
    assert kwargs.get("decision_request") is None
