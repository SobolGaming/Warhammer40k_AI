from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.panels.unit_detail_panel import UnitDetailPanel


class _ModelStub:
    def __init__(self, name: str) -> None:
        self.name = name
        self.movement = 6
        self.toughness = 4
        self.save = 3
        self.wounds = 2
        self.leadership = 7
        self.objective_control = 1
        self.wargear = []


class _UnitStub:
    def __init__(self, name: str) -> None:
        self.name = name
        self.faction = "Imperium"
        self.round_state = SimpleNamespace(performing_action_name=None)
        self.models = [_ModelStub("Trooper"), _ModelStub("Trooper")]
        self.attached_leaders = []
        self.attached_support_units = []
        self.possible_abilities = []
        self.enhancement = None

    def get_attached_unit_root(self):
        return self

    def get_unit_cost(self) -> int:
        return 100

    def get_effective_keywords(self):
        return ["INFANTRY"]

    def get_models_for_rendering(self):
        return list(self.models)

    def get_attached_unit_members(self):
        return [self]

    def _disciple_of_khorne_active_leaders(self):
        return []

    def get_aspect_shrine_token_total(self) -> int:
        return 0


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def test_unit_detail_panel_draw_uses_cached_content_surface() -> None:
    panel = UnitDetailPanel(width=500, height=600)
    panel._cache_refresh_ms = 100000

    unit_a = _UnitStub("Alpha")
    unit_b = _UnitStub("Beta")

    calls: list[int] = []
    original_builder = panel._build_content_surface

    def _tracked_builder(unit, root, content_width):
        calls.append(1)
        return original_builder(unit, root, content_width)

    panel._build_content_surface = _tracked_builder

    canvas = pygame.Surface((1600, 900))

    panel.draw(canvas, unit_a, 100, 100)
    panel.draw(canvas, unit_a, 100, 100)
    panel.scroll(30)
    panel.draw(canvas, unit_a, 100, 100)

    assert len(calls) == 1

    panel.draw(canvas, unit_b, 100, 100)
    assert len(calls) == 2

    panel.invalidate_cache()
    panel.draw(canvas, unit_b, 100, 100)
    assert len(calls) == 3
