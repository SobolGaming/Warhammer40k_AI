from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.panels.rule_detail_panel import RuleDetailPanel


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def test_rule_detail_panel_draw_uses_cached_content_surface() -> None:
    panel = RuleDetailPanel(width=520, height=520)
    panel._cache_refresh_ms = 100000
    long_description = " ".join(["Rule details text"] * 600)

    panel.set_content(
        title="Army Rule",
        rule_name="Core Mechanic",
        legend="Legend text",
        description=long_description,
        supported=True,
        highlight_words=["Rule"],
    )

    calls: list[int] = []
    original_builder = panel._build_content_surface

    def _tracked_builder(content_width: int):
        calls.append(1)
        return original_builder(content_width)

    panel._build_content_surface = _tracked_builder

    canvas = pygame.Surface((1920, 1080), pygame.SRCALPHA)
    panel.draw(canvas, 100, 100)
    panel.draw(canvas, 100, 100)
    panel.scroll(120)
    panel.draw(canvas, 100, 100)
    assert len(calls) == 1

    panel.set_content(
        title="Army Rule",
        rule_name="Core Mechanic",
        legend="Legend text",
        description=long_description + " updated",
        supported=True,
        highlight_words=["Rule"],
    )
    panel.draw(canvas, 100, 100)
    assert len(calls) == 2
