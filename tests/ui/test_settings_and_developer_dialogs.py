from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.dialogs.developer_menu_dialog import DeveloperMenuDialog
from warhammer40k_ai.UI.dialogs.settings_dialog import SettingsDialog


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def test_settings_dialog_applies_developer_controls_toggle() -> None:
    dialog = SettingsDialog(1200, 800)
    applied_values: list[bool] = []

    dialog.show(
        enable_developer_controls=False,
        on_apply=lambda enabled: applied_values.append(bool(enabled)),
    )

    assert dialog.visible is True
    assert dialog._handle_button_click("toggle_dev_controls") is True
    assert dialog._handle_button_click("apply") is True
    assert dialog.visible is False
    assert applied_values == [True]


def test_developer_menu_toggle_updates_state_via_callback() -> None:
    dialog = DeveloperMenuDialog(1200, 800)
    toggles: list[bool] = []

    def _on_toggle(desired: bool) -> bool:
        toggles.append(bool(desired))
        return bool(desired)

    dialog.show(profiling_enabled=False, on_toggle_profiling=_on_toggle)

    assert dialog._handle_button_click("toggle_profiling") is True
    assert toggles == [True]
    assert dialog._profiling_enabled is True


def test_developer_menu_outside_click_passthrough_and_close_callback() -> None:
    dialog = DeveloperMenuDialog(1200, 800)
    closed = []
    dialog.show(profiling_enabled=False, on_toggle_profiling=lambda desired: desired, on_close=lambda: closed.append(True))

    outside_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (0, 0)})
    assert dialog.handle_event(outside_event) is False
    assert dialog.visible is True

    assert dialog._handle_button_click("close") is True
    assert dialog.visible is False
    assert closed == [True]
