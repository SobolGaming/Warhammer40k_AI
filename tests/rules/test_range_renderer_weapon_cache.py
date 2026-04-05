from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.rendering.range_renderer import (
    _RANGE_CIRCLE_SURFACE_CACHE,
    _clear_range_render_caches,
    _get_cached_circle_surface,
    draw_weapon_ranges,
)


class _RangeStub:
    def __init__(self, max_value: float) -> None:
        self.max = max_value


class _WargearStub:
    def __init__(self, name: str) -> None:
        self.name = name
        self.profiles = {"default": object()}


class _WeaponProfileStub:
    def __init__(self, wargear: _WargearStub, *, max_range: float) -> None:
        self.range = _RangeStub(max_range)
        self.parent_wargear = wargear
        self.name = "default"

    def is_pistol(self) -> bool:
        return False

    def is_assault(self) -> bool:
        return False

    def is_heavy(self) -> bool:
        return False

    def is_rapid_fire(self) -> bool:
        return False


class _ModelStub:
    def __init__(self, x: float, y: float, wargear: _WargearStub) -> None:
        self.is_alive = True
        self.wargear = [wargear]
        self._pos = (x, y, 0.0)

    def get_location(self):
        return self._pos


class _UnitStub:
    def __init__(self, models):
        self.models = list(models)


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def test_cached_circle_surface_reuses_same_object() -> None:
    _clear_range_render_caches()

    s1 = _get_cached_circle_surface(
        radius=120,
        fill_color=(0, 255, 0, 64),
        border_color=(0, 200, 0),
        border_width=1,
    )
    s2 = _get_cached_circle_surface(
        radius=120,
        fill_color=(0, 255, 0, 64),
        border_color=(0, 200, 0),
        border_width=1,
    )

    assert s1 is not None
    assert s2 is not None
    assert s1 is s2
    assert len(_RANGE_CIRCLE_SURFACE_CACHE) == 1


def test_draw_weapon_ranges_reuses_cached_circle_surface_across_frames() -> None:
    _clear_range_render_caches()

    wargear = _WargearStub("Bolter")
    profile = _WeaponProfileStub(wargear, max_range=24.0)
    models = [_ModelStub(float(i), 2.0, wargear) for i in range(10)]
    unit = _UnitStub(models)
    surface = pygame.Surface((2200, 1400), pygame.SRCALPHA)

    draw_weapon_ranges(surface, unit, profile, zoom_level=1.0, offset_x=0, offset_y=0)
    first_count = len(_RANGE_CIRCLE_SURFACE_CACHE)

    draw_weapon_ranges(surface, unit, profile, zoom_level=1.0, offset_x=0, offset_y=0)
    second_count = len(_RANGE_CIRCLE_SURFACE_CACHE)

    assert first_count == 1
    assert second_count == 1
