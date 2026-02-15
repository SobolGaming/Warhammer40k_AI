import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from warhammer40k_ai.UI.dialogs import floor_selection_dialog as floor_dialog_module
from warhammer40k_ai.UI.dialogs.individual_model_movement_dialog import IndividualModelMovementDialog


class _ModelStub:
    def __init__(self) -> None:
        self.name = "Howling Banshee"
        self._location = (56.0, 38.3, 0.0)

    def get_location(self):
        return self._location


class _UnitStub:
    def __init__(self) -> None:
        self.name = "Howling Banshees"
        self.models = [_ModelStub()]


class _FloorSelectionDialogStub:
    def __init__(self, available_floors, unit_name="Unit", disabled_floors=None):
        self.available_floors = list(available_floors or [])
        self.unit_name = unit_name
        self.disabled_floors = list(disabled_floors or [])
        self.visible = False
        self.on_confirm = None
        self.on_cancel = None
        self.decision_request = None

    def show(self, *, on_confirm, on_cancel=None, decision_request=None) -> None:
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.decision_request = decision_request
        self.visible = True

    def handle_event(self, _event) -> bool:
        return True

    def hide(self) -> None:
        self.visible = False


@pytest.fixture(scope="module", autouse=True)
def pygame_setup_teardown():
    pygame.init()
    pygame.font.init()
    yield
    pygame.font.quit()
    pygame.quit()


def _build_dialog(monkeypatch):
    dialog = IndividualModelMovementDialog(1024, 768)
    dialog.unit = _UnitStub()
    dialog.movement_type = "move"
    dialog.max_distance = 30.0
    dialog.selected_model_index = 0
    dialog.awaiting_battlefield_click = True
    monkeypatch.setattr(
        dialog,
        "_get_ruins_floor_options_for_model_at_xy",
        lambda *_args, **_kwargs: ([0, 1, 2], {0: 0.0, 1: 5.0, 2: 10.0}, [1, 2]),
    )
    return dialog


def test_ruins_floor_click_opens_dialog_with_callbacks(monkeypatch):
    monkeypatch.setattr(floor_dialog_module, "FloorSelectionDialog", _FloorSelectionDialogStub)
    dialog = _build_dialog(monkeypatch)

    handled = dialog.handle_battlefield_click(45.2, 27.4, 0.1)

    assert handled is True
    assert isinstance(dialog.floor_selection_dialog, _FloorSelectionDialogStub)
    assert dialog.floor_selection_dialog.visible is True
    assert callable(dialog.floor_selection_dialog.on_confirm)
    assert callable(dialog.floor_selection_dialog.on_cancel)
    assert dialog._pending_click_position == (45.2, 27.4)
    assert dialog._pending_floor_z_by_level == {0: 0.0, 1: 5.0, 2: 10.0}


def test_ruins_floor_confirm_uses_selected_level_z(monkeypatch):
    monkeypatch.setattr(floor_dialog_module, "FloorSelectionDialog", _FloorSelectionDialogStub)
    dialog = _build_dialog(monkeypatch)
    moved = []

    def _move_model(model_index: int, destination):
        moved.append((model_index, destination))
        return True

    monkeypatch.setattr(dialog, "_move_model", _move_model)

    dialog.handle_battlefield_click(45.2, 27.4, 0.1)
    dialog.floor_selection_dialog.on_confirm("", 2)

    assert moved == [(0, (45.2, 27.4, 10.0))]
    assert dialog._pending_click_position is None
    assert dialog._pending_floor_z_by_level is None
    assert dialog.selected_model_index is None
    assert dialog.awaiting_battlefield_click is False

