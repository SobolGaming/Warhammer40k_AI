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
