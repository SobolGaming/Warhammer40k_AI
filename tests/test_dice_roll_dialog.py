from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.dialogs.dice_roll_dialog import DiceRollDialog
from warhammer40k_ai.engine.decision_kinds import DECISION_REQUEST_DICE_ROLL, DECISION_SELECT_DICE_REROLL
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def test_make_roll_resolves_decision_without_prebuilt_action_map() -> None:
    dialog = DiceRollDialog(1200, 800)
    req = DecisionRequest.create(
        DECISION_REQUEST_DICE_ROLL,
        "Advance roll for Shalaxi Helbane",
        player_id="p1",
        options=[DecisionOption.create("Make Roll", payload={"action_id": "roll"})],
        context={"roll_id": 1},
    )
    resolved: list[tuple[str, dict]] = []

    dialog.show(
        game=SimpleNamespace(roll_manager=None),
        player=SimpleNamespace(id="p1"),
        decision_request=req,
        on_resolve=lambda option_id, payload: resolved.append((option_id, payload)),
    )

    handled = dialog._handle_button_click("make_roll")

    assert handled is True
    assert resolved == [(req.options[0].option_id, {"selected_die_ids": []})]
    assert dialog.visible is True


def test_make_roll_keeps_follow_up_reroll_dialog_visible() -> None:
    dialog = DiceRollDialog(1200, 800)
    roll_req = DecisionRequest.create(
        DECISION_REQUEST_DICE_ROLL,
        "Advance roll for Shalaxi Helbane",
        player_id="p1",
        options=[DecisionOption.create("Make Roll", payload={"action_id": "roll"})],
        context={"roll_id": 2},
    )
    reroll_req = DecisionRequest.create(
        DECISION_SELECT_DICE_REROLL,
        "Re-roll options: Advance roll for Shalaxi Helbane",
        player_id="p1",
        options=[
            DecisionOption.create("No re-roll", payload={"action_id": "none"}),
            DecisionOption.create("Command Re-roll", payload={"action_id": "command_reroll"}),
        ],
        context={"roll_id": 2},
    )
    game = SimpleNamespace(roll_manager=None)
    player = SimpleNamespace(id="p1")

    def _on_resolve(_option_id: str, _payload: dict) -> None:
        dialog.show(
            game=game,
            player=player,
            decision_request=reroll_req,
            on_resolve=lambda _oid, _pl: None,
        )

    dialog.show(
        game=game,
        player=player,
        decision_request=roll_req,
        on_resolve=_on_resolve,
    )

    handled = dialog._handle_button_click("make_roll")

    assert handled is True
    assert dialog.visible is True
    assert dialog.decision_request is reroll_req


def test_reroll_buttons_align_with_keep_button() -> None:
    class _RollManagerStub:
        def __init__(self, state):
            self._state = state

        def get_roll(self, _roll_id: int):
            return self._state

    dialog = DiceRollDialog(1200, 800)
    req = DecisionRequest.create(
        DECISION_SELECT_DICE_REROLL,
        "Re-roll options: Advance roll for Shalaxi Helbane",
        player_id="p1",
        options=[
            DecisionOption.create("Keep", payload={"action_id": "none"}),
            DecisionOption.create("Re-roll Advance", payload={"action_id": "reroll_advance"}),
            DecisionOption.create("Command Re-roll", payload={"action_id": "command_reroll"}),
        ],
        context={"roll_id": 2},
    )
    roll_state = SimpleNamespace(
        status="rolled",
        spec={"reason": "Advance roll for Shalaxi Helbane", "roll_type": "advance"},
        dice=[{"die_id": "d0", "value": 3, "faces": 6, "is_derived": False}],
        sorted_ids=["d0"],
        per_die_success={"d0": None},
        total=3,
        sum_success=None,
        reroll_options=[
            {
                "action_id": "reroll_advance",
                "label": "Re-roll Advance",
                "mode": "all",
                "eligible_die_ids": ["d0"],
                "auto_select_all": True,
            },
            {
                "action_id": "command_reroll",
                "label": "Command Re-roll",
                "mode": "whole",
                "eligible_die_ids": ["d0"],
                "auto_select_all": True,
            },
        ],
    )

    dialog.show(
        game=SimpleNamespace(roll_manager=_RollManagerStub(roll_state)),
        player=SimpleNamespace(id="p1"),
        decision_request=req,
        on_resolve=lambda _option_id, _payload: None,
    )

    surface = pygame.Surface((1200, 800))
    dialog.draw(surface)

    keep_rect = dialog.buttons["no_reroll"]
    ability_rect = dialog.buttons["action:reroll_advance"]
    command_rect = dialog.buttons["command_reroll"]

    assert keep_rect.y == ability_rect.y
    assert keep_rect.y == command_rect.y


def test_confirm_reroll_does_not_hide_followup_reroll_request() -> None:
    dialog = DiceRollDialog(1200, 800)
    first_req = DecisionRequest.create(
        DECISION_SELECT_DICE_REROLL,
        "Re-roll options: Hit roll (6D6)",
        player_id="p1",
        options=[
            DecisionOption.create("No re-roll", payload={"action_id": "none"}),
            DecisionOption.create("Command Re-roll", payload={"action_id": "command_reroll"}),
        ],
        context={"roll_id": 2},
    )
    followup_req = DecisionRequest.create(
        DECISION_SELECT_DICE_REROLL,
        "Re-roll options: Hit roll (6D6)",
        player_id="p1",
        options=[
            DecisionOption.create("No re-roll", payload={"action_id": "none"}),
        ],
        context={"roll_id": 2},
    )

    state = SimpleNamespace(
        status="rolled",
        spec={"reason": "Hit roll (6D6)", "roll_type": "hit"},
        dice=[{"die_id": "d0", "value": 2, "faces": 6, "is_derived": False}],
        sorted_ids=["d0"],
        per_die_success={"d0": False},
        total=2,
        sum_success=None,
        reroll_options=[
            {
                "action_id": "command_reroll",
                "label": "Command Re-roll",
                "mode": "one",
                "eligible_die_ids": ["d0"],
                "max_select": 1,
            }
        ],
    )

    class _RollManagerStub:
        def get_roll(self, _roll_id: int):
            return state

    def _on_resolve(_option_id: str, _payload: dict) -> None:
        dialog.show(
            game=SimpleNamespace(roll_manager=_RollManagerStub()),
            player=SimpleNamespace(id="p1"),
            decision_request=followup_req,
            on_resolve=lambda _oid, _pl: None,
        )

    dialog.show(
        game=SimpleNamespace(roll_manager=_RollManagerStub()),
        player=SimpleNamespace(id="p1"),
        decision_request=first_req,
        on_resolve=_on_resolve,
    )
    dialog._active_action_id = "command_reroll"
    dialog._selected_die_ids = ["d0"]

    handled = dialog._handle_button_click("confirm_reroll")

    assert handled is True
    assert dialog.visible is True
    assert dialog.decision_request is followup_req
