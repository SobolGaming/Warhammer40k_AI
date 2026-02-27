from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.dialogs.mission_selection_dialog import MissionSelectionDialog


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def _make_combinations(count: int) -> list[dict]:
    combos = []
    for i in range(count):
        combos.append(
            {
                "id": f"{chr(65 + (i % 26))}{i}",
                "primary": f"Primary Mission {i}",
                "deployment": f"Deployment Type {i}",
                "layouts": [1, 2, 3],
            }
        )
    return combos


def test_mission_selection_dialog_reuses_cached_content_surface() -> None:
    dialog = MissionSelectionDialog(1600, 900, combinations=_make_combinations(40))
    dialog.show()

    calls: list[int] = []
    original_builder = dialog._build_content_surface

    def _tracked_builder(content_width: int, content_height: int):
        calls.append(1)
        return original_builder(content_width, content_height)

    dialog._build_content_surface = _tracked_builder

    canvas = pygame.Surface((1600, 900), pygame.SRCALPHA)
    dialog.draw(canvas)
    dialog.draw(canvas)
    dialog._scroll(2)
    dialog.draw(canvas)
    assert len(calls) == 1

    dialog.selected_combination = 0
    dialog.selected_layout = 2
    dialog.draw(canvas)
    assert len(calls) == 2
