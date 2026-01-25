import pygame
from typing import List, Optional, Callable, Dict

from .base_dialog import BaseDialog, BUTTON_BG, BUTTON_SELECTED, TEXT_PRIMARY, TEXT_SECONDARY
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.utility.entity_ids import get_entity_id


class ExplodingHorrorsModelSelectionDialog(BaseDialog):
    """Dialog for selecting one or more Brimstone Horror models to explode."""

    def __init__(self, screen_width: int, screen_height: int) -> None:
        super().__init__(screen_width, screen_height, width=560, height=420, draggable=True, center=True)
        self.unit: Optional[Unit] = None
        self.models: List[Model] = []
        self.selected_ids: set[str] = set()
        self.on_confirm: Optional[Callable[[str, dict], None]] = None
        self.decision_request = None
        self._option_entries: List[dict] = []
        self._button_to_model: Dict[str, Model] = {}

    def show(
        self,
        unit: Unit,
        models: List[Model],
        on_confirm: Callable[[str, dict], None],
        *,
        decision_request=None,
    ) -> None:
        self.unit = unit
        self.models = list(models or [])
        self.on_confirm = on_confirm
        self.decision_request = decision_request
        self.selected_ids = set()
        self._option_entries = []
        if self.decision_request is not None:
            from ..decision_ui_utils import option_entries

            self._option_entries = option_entries(self.decision_request)
        super().show()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.unit = None
        self.models = []
        self.selected_ids = set()
        self.on_confirm = None
        self.decision_request = None
        self._option_entries = []
        self._button_to_model.clear()

    def _create_buttons(self) -> None:
        self.buttons.clear()
        self.button_states.clear()
        self._button_to_model.clear()

        button_width = self.width - 40
        button_height = 60
        button_spacing = 8
        start_y = self.title_bar_height + 70

        for i, model in enumerate(self.models):
            rel_x = 20
            rel_y = start_y + i * (button_height + button_spacing)
            name = f"model_{i}"
            self.add_button(name, rel_x, rel_y, button_width, button_height, enabled=True)
            self._button_to_model[name] = model

        confirm_width, confirm_height = 140, 40
        rel_x = self.width - confirm_width - 20
        rel_y = self.height - confirm_height - 20
        can_confirm = bool(self.selected_ids)
        self.add_button("confirm", rel_x, rel_y, confirm_width, confirm_height, enabled=can_confirm)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "confirm":
            if not self.selected_ids:
                return True
            option_id = self._option_entries[0]["option_id"] if self._option_entries else ""
            payload = {"model_ids": list(self.selected_ids)}
            if callable(self.on_confirm):
                self.on_confirm(option_id, payload)
            self.hide()
            return True

        if button_name in self._button_to_model:
            model = self._button_to_model[button_name]
            mid = str(get_entity_id(model))
            if mid in self.selected_ids:
                self.selected_ids.remove(mid)
            else:
                self.selected_ids.add(mid)
            # Update confirm button enabled state
            if "confirm" in self.button_states:
                self.button_states["confirm"] = bool(self.selected_ids)
            return True

        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        # Overlay behind the dialog
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        self.draw_dialog_background(screen)
        title = "Exploding Horrors - Select Brimstones"
        self.draw_title_bar(screen, title)

        instruction = "Select one or more Brimstone Horrors to explode."
        self.draw_instructions(screen, instruction)

        for name, rect in self.buttons.items():
            if name == "confirm":
                continue
            model = self._button_to_model.get(name)
            if model is None:
                continue
            label = getattr(model, "name", "Model")
            mid = str(get_entity_id(model))
            color = BUTTON_SELECTED if mid in self.selected_ids else BUTTON_BG
            self.draw_button(screen, name, label, color=color)

        if "confirm" in self.buttons:
            self.draw_button(screen, "confirm", "Confirm")
