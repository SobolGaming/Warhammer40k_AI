import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.panels.roster_pane import RosterPane


class _ModelStub:
    def __init__(self, name: str) -> None:
        self.name = name
        self.is_alive = True
        self.wounds = 1
        self._base_wounds = 1


class _LeaderStub:
    def __init__(self, name: str) -> None:
        self.name = name
        self.models = [_ModelStub(name)]

    def get_unit_cost(self) -> int:
        return 90


class _UnitStub:
    def __init__(self) -> None:
        self.name = "Howling Banshees"
        self.parent_army = None
        self.models = (
            [_ModelStub("Howling Banshee") for _ in range(4)]
            + [_ModelStub("Howling Banshee Exarch")]
        )
        self.attached_leaders = [_LeaderStub("Jain Zar")]
        self.attached_support_units = []
        self.possible_abilities = []
        self.enhancement = None
        self.deployed = True
        self.reserve_status = "deployed"

    def get_unit_cost(self) -> int:
        return 85

    def get_attached_unit_root(self):
        return self

    def get_aspect_shrine_token_total(self) -> int:
        return 2

    def get_aspect_shrine_token_remaining(self) -> int:
        return 1


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def test_ellipsize_to_width_never_exceeds_requested_width():
    pane = RosterPane(0, 0, 320, 240, [], "Player One")
    text = "4x Howling Banshee | 1x Howling Banshee Exarch | +1 types"
    max_width = 150

    clipped = pane._ellipsize_to_width(pane.font_small, text, max_width)

    assert pane.font_small.size(clipped)[0] <= max_width
    assert clipped.endswith("...")


def test_draw_unit_info_reserves_token_space_for_composition_line():
    unit = _UnitStub()
    pane = RosterPane(0, 0, 360, 260, [unit], "Player One")
    pane.all_units = [unit]
    canvas = pygame.Surface((500, 300), pygame.SRCALPHA)
    button_rect = pygame.Rect(10, 40, 320, 80)

    captured = {}

    def _capture(font, text, max_width):
        captured["text"] = text
        captured["max_width"] = int(max_width)
        return text

    pane._ellipsize_to_width = _capture
    pane.draw_unit_info(canvas, unit, button_rect)

    x_left = button_rect.left + 8
    x_right = button_rect.right - 8
    icon_size = 16
    details_x = x_left + icon_size + 8
    token_total = int(unit.get_aspect_shrine_token_total())
    token_size = 8
    gap = 3
    total_w = token_total * token_size + max(0, token_total - 1) * gap
    token_start_x = x_right - total_w
    expected_max_width = max(0, (token_start_x - 6) - details_x)

    assert "+1 types" in str(captured.get("text", ""))
    assert captured.get("max_width") == expected_max_width
