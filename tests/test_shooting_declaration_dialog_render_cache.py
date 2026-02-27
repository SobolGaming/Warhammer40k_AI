from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.dialogs.shooting_declaration_dialog import ShootingDeclarationDialog


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def test_shooting_dialog_text_render_cache_reuses_surface() -> None:
    dialog = ShootingDeclarationDialog(1200, 800)
    s1 = dialog._render_text_cached(dialog.font_small, "Bolter", (255, 255, 255))
    s2 = dialog._render_text_cached(dialog.font_small, "Bolter", (255, 255, 255))
    assert s1 is s2
    assert len(dialog._text_surface_cache) == 1
