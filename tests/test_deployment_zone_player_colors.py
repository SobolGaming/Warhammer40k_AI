import os
from dataclasses import dataclass, field

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.player_colors import get_zone_fill_rgba
from warhammer40k_ai.UI.rendering.board_renderer import draw_deployment_zones
from warhammer40k_ai.UI.ui_constants import TILE_SIZE
from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player


@dataclass
class _MissionZone:
    vertices: list[tuple[float, float]]
    cutouts: list[object] = field(default_factory=list)


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def test_deployment_zones_tint_from_owner_player_colors():
    player_one = Player("Player One")
    player_two = Player("Player Two")
    player_one.set_ui_color([20, 130, 220], hue_degrees=210, selected=True, source="selected")
    player_two.set_ui_color([200, 70, 30], hue_degrees=15, selected=True, source="selected")
    game = Game(Battlefield(width=60, height=44), players=[player_one, player_two])

    left_zone = _MissionZone(vertices=[(1.0, 1.0), (6.0, 1.0), (6.0, 6.0), (1.0, 6.0)])
    right_zone = _MissionZone(vertices=[(8.0, 1.0), (13.0, 1.0), (13.0, 6.0), (8.0, 6.0)])
    deployment_zones = {
        str(player_one.id): {"zone_type": "attacker", "name": "Left", "mission_zones": [left_zone]},
        str(player_two.id): {"zone_type": "defender", "name": "Right", "mission_zones": [right_zone]},
    }

    screen = pygame.Surface((320, 180), pygame.SRCALPHA)
    draw_deployment_zones(screen, deployment_zones, game, 1.0, 0, 0)

    left_sample = tuple(screen.get_at((int(2 * TILE_SIZE), int(2 * TILE_SIZE))))
    right_sample = tuple(screen.get_at((int(9 * TILE_SIZE), int(2 * TILE_SIZE))))

    assert left_sample == get_zone_fill_rgba(player_one)
    assert right_sample == get_zone_fill_rgba(player_two)
