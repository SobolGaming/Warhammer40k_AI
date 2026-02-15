from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.dialogs.overwatch_shooter_dialog import OverwatchShooterDialog
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def test_show_auto_cancels_when_no_candidates_or_options() -> None:
    dialog = OverwatchShooterDialog(1200, 800)
    req = DecisionRequest.create("SELECT_OVERWATCH_SHOOTER", "Pick shooter", player_id="p1", options=[])
    cancelled: list[bool] = []

    shown = dialog.show(
        [],
        None,
        lambda _option_id: None,
        on_cancel=lambda: cancelled.append(True),
        decision_request=req,
    )

    assert shown is False
    assert dialog.visible is False
    assert cancelled == [True]


def test_show_maps_decision_options_to_units_and_skip_entry() -> None:
    dialog = OverwatchShooterDialog(1200, 800)
    shooter = SimpleNamespace(id="unit-1", name="Shooter")
    req = DecisionRequest.create(
        "SELECT_OVERWATCH_SHOOTER",
        "Pick shooter",
        player_id="p1",
        options=[
            DecisionOption.create("Shooter", payload={"unit_id": "unit-1"}),
            DecisionOption.create("Skip", payload={"action": "skip"}),
        ],
    )

    shown = dialog.show(
        [shooter],
        SimpleNamespace(name="Enemy"),
        lambda _option_id: None,
        title="Select Overwatch Shooter",
        decision_request=req,
    )

    assert shown is True
    assert dialog.visible is True
    assert len(dialog.candidates) == 2
    assert len(dialog._option_entries) == 2
    assert dialog.selected_index == 0
    dialog.hide()


def test_show_handles_non_entity_candidates_with_decision_request() -> None:
    dialog = OverwatchShooterDialog(1200, 800)
    req = DecisionRequest.create(
        "CHOOSE_ASPECT",
        "Choose an option",
        player_id="p1",
        options=[
            DecisionOption.create("Skip", payload={"action": "skip"}),
            DecisionOption.create("Swift as the Wind", payload={"choice": "SWIFT_AS_THE_WIND", "unit_id": "unit-1"}),
        ],
    )

    shown = dialog.show(
        ["Skip", "Swift"],
        None,
        lambda _option_id: None,
        title="Battle Focus",
        decision_request=req,
    )

    assert shown is True
    assert dialog.visible is True
    assert len(dialog.candidates) == 2
    assert len(dialog._option_entries) == 2
    dialog.hide()
