from __future__ import annotations

import os
from types import SimpleNamespace

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


def _make_model(*, x: float, y: float, z: float = 0.0):
    base = SimpleNamespace(x=float(x), y=float(y), z=float(z))
    return SimpleNamespace(is_alive=True, model_base=base)


def _make_dialog_with_shooter(shooter_model):
    dialog = ShootingDeclarationDialog(1200, 800)
    dialog.unit = SimpleNamespace(round_state=SimpleNamespace(advanced_this_round=False, fell_back_this_round=False))
    dialog.game_map = None
    dialog._get_models_with_weapon = lambda _weapon: [shooter_model]
    return dialog


def test_validate_click_target_in_range_does_not_crash():
    shooter = _make_model(x=0, y=0)
    target = _make_model(x=8, y=0)
    target_unit = SimpleNamespace(models=[target], name="Target Unit")
    weapon_profile = SimpleNamespace(range=SimpleNamespace(max=12))

    dialog = _make_dialog_with_shooter(shooter)
    valid, reason = dialog._validate_click_target_with_reason(weapon_profile, target_unit, target)

    assert valid is True
    assert reason == ""


def test_validate_click_target_out_of_range_has_reason():
    shooter = _make_model(x=0, y=0)
    target = _make_model(x=20, y=0)
    target_unit = SimpleNamespace(models=[target], name="Target Unit")
    weapon_profile = SimpleNamespace(range=SimpleNamespace(max=6))

    dialog = _make_dialog_with_shooter(shooter)
    valid, reason = dialog._validate_click_target_with_reason(weapon_profile, target_unit, target)

    assert valid is False
    assert "Out of range" in reason
