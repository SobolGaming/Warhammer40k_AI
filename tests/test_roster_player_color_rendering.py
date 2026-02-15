import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.panels.roster_pane import DARK_GREY as ROSTER_DARK_GREY
from warhammer40k_ai.UI.panels.roster_pane import RosterPane
from warhammer40k_ai.UI.player_colors import get_active_roster_header_rgb, get_player_color_rgb
from warhammer40k_ai.UI.ui_constants import PLAYER_SWATCH_SIZE
from warhammer40k_ai.roster.player import Player


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


class _GameStub:
    def __init__(self, players, waiting_player_id):
        self.players = list(players or [])
        self.attacker_index = None
        self.defender_index = None
        self._waiting_player_id = str(waiting_player_id or "")

    def get_waiting_player_id(self):
        return self._waiting_player_id


class _GameViewStub:
    def __init__(self, required_input_player_id=None):
        self._last_highlighted_player_id = None
        self._required_input_player_id = (
            str(required_input_player_id) if required_input_player_id else None
        )

    def get_required_input_player_id(self):
        return self._required_input_player_id


def _build_pane(player: Player, *, required_input_player_id=None) -> RosterPane:
    pane = RosterPane(0, 0, 320, 240, [], "Player One")
    pane.player = player
    pane.game_view = _GameViewStub(required_input_player_id=required_input_player_id)
    return pane


def _swatch_center(pane: RosterPane) -> tuple[int, int]:
    player_control_str = ""
    if pane.player and hasattr(pane.player, "control"):
        player_control_str = f" ({pane.player.control.name})"
    player_display_name = f"{pane.player_name}{player_control_str}"
    player_text = pane.font_medium.render(player_display_name, True, (255, 255, 255))
    player_text_x = pane.rect.left + 10
    swatch_size = int(PLAYER_SWATCH_SIZE)
    swatch_x_max = pane.rect.right - 90 - swatch_size
    swatch_x = min(player_text_x + player_text.get_width() + 8, swatch_x_max)
    swatch_x = max(pane.rect.left + 10, swatch_x)
    swatch_y = pane.rect.top + (35 - swatch_size) // 2
    return (swatch_x + swatch_size // 2, swatch_y + swatch_size // 2)


def _header_sample_point(pane: RosterPane) -> tuple[int, int]:
    return (pane.rect.right - 24, pane.rect.top + 12)


def test_active_roster_header_uses_player_color_and_draws_swatch():
    player = Player("Player One")
    player.set_ui_color([24, 150, 90], hue_degrees=135, selected=True, source="selected")
    pane = _build_pane(player)
    game = _GameStub([player], waiting_player_id=player.id)
    surface = pygame.Surface((360, 280), pygame.SRCALPHA)

    pane.draw(surface, game)

    expected_header_rgb = get_active_roster_header_rgb(player, base_header_rgb=ROSTER_DARK_GREY)
    header_sample = tuple(surface.get_at(_header_sample_point(pane))[:3])
    assert header_sample == expected_header_rgb

    swatch_sample = tuple(surface.get_at(_swatch_center(pane))[:3])
    assert swatch_sample == get_player_color_rgb(player)


def test_inactive_roster_keeps_persistent_swatch():
    player = Player("Player One")
    other_player = Player("Player Two")
    player.set_ui_color([210, 70, 45], hue_degrees=5, selected=True, source="selected")
    pane = _build_pane(player)
    game = _GameStub([player, other_player], waiting_player_id=other_player.id)
    surface = pygame.Surface((360, 280), pygame.SRCALPHA)

    pane.draw(surface, game)

    inactive_header_rgb = tuple(surface.get_at(_header_sample_point(pane))[:3])
    assert inactive_header_rgb == ROSTER_DARK_GREY

    swatch_sample = tuple(surface.get_at(_swatch_center(pane))[:3])
    assert swatch_sample == get_player_color_rgb(player)


def test_roster_highlight_prefers_required_input_owner_from_game_view():
    player = Player("Player One")
    other_player = Player("Player Two")
    other_player.set_ui_color([20, 110, 210], hue_degrees=210, selected=True, source="selected")
    pane = _build_pane(other_player, required_input_player_id=other_player.id)
    game = _GameStub([player, other_player], waiting_player_id=player.id)
    surface = pygame.Surface((360, 280), pygame.SRCALPHA)

    pane.draw(surface, game)

    expected_header_rgb = get_active_roster_header_rgb(other_player, base_header_rgb=ROSTER_DARK_GREY)
    header_sample = tuple(surface.get_at(_header_sample_point(pane))[:3])
    assert header_sample == expected_header_rgb
