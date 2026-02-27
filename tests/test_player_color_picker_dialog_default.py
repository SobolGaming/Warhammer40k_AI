from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.dialogs.player_color_picker_dialog import PlayerColorPickerDialog
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_PLAYER_COLOR


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def _build_request() -> DecisionRequest:
    options = [
        DecisionOption.create(
            "Hue 000",
            payload={"hue_degrees": 0, "rgb": [242, 36, 36], "action_id": "h000"},
        ),
        DecisionOption.create(
            "Hue 120",
            payload={"hue_degrees": 120, "rgb": [57, 255, 20], "action_id": "h120"},
        ),
        DecisionOption.create(
            "Hue 240",
            payload={"hue_degrees": 240, "rgb": [36, 36, 242], "action_id": "h240"},
        ),
    ]
    return DecisionRequest.create(
        DECISION_CHOOSE_PLAYER_COLOR,
        "Select color.",
        player_id="p1",
        options=options,
        context={"selection_kind": "player_color"},
    )


def test_player_color_picker_defaults_to_nearest_current_player_rgb() -> None:
    dialog = PlayerColorPickerDialog(1600, 900)
    request = _build_request()

    dialog.show(
        player_name="Player 1",
        on_confirm=lambda _option_id: None,
        on_cancel=lambda: None,
        decision_request=request,
        initial_hue_degrees=None,
        initial_rgb=(57, 255, 20),
    )

    assert dialog._selected_hue == 120


def test_player_color_picker_prefers_explicit_initial_hue_over_rgb() -> None:
    dialog = PlayerColorPickerDialog(1600, 900)
    request = _build_request()

    dialog.show(
        player_name="Player 1",
        on_confirm=lambda _option_id: None,
        on_cancel=lambda: None,
        decision_request=request,
        initial_hue_degrees=240,
        initial_rgb=(57, 255, 20),
    )

    assert dialog._selected_hue == 240
