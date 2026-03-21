"""Dialog for resolving post-casualty coherency cleanup."""

from typing import Callable, List
import logging

import pygame

from .base_dialog import BUTTON_BG, BUTTON_SELECTED, BaseDialog, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_WARNING
from ..ui_fonts import get_ui_font
from warhammer40k_ai.units.unit import Unit

logger = logging.getLogger(__name__)


class CoherencyViolationDialog(BaseDialog):
    """Dialog for choosing a single additional casualty for coherency."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=600, height=500, draggable=True)
        self.unit = None
        self.non_coherent_models = []
        self.callback = None
        self.decision_request = None
        self._option_entries: List[dict] = []
        self.model_buttons = []
        self.font_large = get_ui_font(28, bold=True)
        self.font_medium = get_ui_font(24, bold=True)
        self.font_small = get_ui_font(20, bold=False)

    def show(
        self,
        unit: Unit,
        non_coherent_models: List[str],
        callback: Callable[[str, List[str]], None],
        existing_dialogs: List | None = None,
        *,
        decision_request=None,
    ):
        if existing_dialogs:
            self.x, self.y = self.find_non_overlapping_position(existing_dialogs)

        super().show(callback)
        self.unit = unit
        self.non_coherent_models = list(non_coherent_models or [])
        self.callback = callback
        self.decision_request = decision_request
        self._option_entries = []
        if self.decision_request is not None:
            from ..decision_ui_utils import option_entries

            self._option_entries = option_entries(self.decision_request)
        self._create_model_buttons()
        self._create_dialog_buttons()
        self._update_model_buttons()
        logger.info("Coherency violation dialog opened for %s", getattr(unit, "name", "Unit"))

    def hide(self):
        super().hide()
        self.unit = None
        self.non_coherent_models = []
        self.callback = None
        self.decision_request = None
        self._option_entries = []
        self.model_buttons = []

    def _create_model_buttons(self):
        self.model_buttons = []
        if self.unit is None:
            return
        button_width = 400
        button_height = 40
        top_y = self.title_bar_height + 90
        for index, entry in enumerate(self._option_entries):
            payload = dict(entry.get("payload", {}) or {})
            model_id = str(payload.get("model_id", "") or "")
            label = str(entry.get("label", "") or "Model").strip() or "Model"
            relative_x = 20
            relative_y = top_y + index * (button_height + 10)
            button_rect = pygame.Rect(
                self.x + relative_x,
                self.y + relative_y,
                button_width,
                button_height,
            )
            self.model_buttons.append(
                {
                    "rect": button_rect,
                    "relative_x": relative_x,
                    "relative_y": relative_y,
                    "width": button_width,
                    "height": button_height,
                    "option_id": entry.get("option_id", ""),
                    "model_id": model_id,
                    "label": label,
                    "selected": False,
                    "is_non_coherent": model_id in self.non_coherent_models,
                }
            )

    def _update_model_buttons(self):
        for button in self.model_buttons:
            button["rect"] = pygame.Rect(
                self.x + button["relative_x"],
                self.y + button["relative_y"],
                button["width"],
                button["height"],
            )

    def _create_dialog_buttons(self):
        button_y = self.y + self.height - 70
        self.buttons = {
            "remove_selected": pygame.Rect(self.x + 300, button_y, 180, 40),
        }
        self.button_states = {
            "remove_selected": {
                "hovered": False,
                "pressed": False,
                "enabled": True,
                "state": "normal",
                "relative_x": 300,
                "relative_y": self.height - 70,
                "width": 180,
                "height": 40,
            }
        }

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            for button in self.model_buttons:
                if button["rect"].collidepoint(mouse_pos):
                    for other in self.model_buttons:
                        other["selected"] = False
                    button["selected"] = True
                    return True
            if self.buttons["remove_selected"].collidepoint(mouse_pos):
                self._submit_selected_model()
                return True
        result = super().handle_event(event)
        if event.type == pygame.MOUSEMOTION and self.dragging:
            self._update_model_buttons()
        return result

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "remove_selected":
            self._submit_selected_model()
            return True
        return False

    def _submit_selected_model(self):
        selected = next((button for button in self.model_buttons if button["selected"]), None)
        if selected is None:
            logger.error("No coherency-removal model selected.")
            return
        option_id = str(selected.get("option_id", "") or "")
        model_id = str(selected.get("model_id", "") or "")
        if not option_id or not model_id:
            logger.error("Selected coherency-removal option is incomplete.")
            return
        if self.callback:
            self.callback(option_id, [model_id])
        self.hide()

    def draw(self, screen: pygame.Surface):
        if not self.visible or self.unit is None:
            return
        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, f"Coherency Violation - {self.unit.name}")
        explanation_lines = [
            "Casualties left this unit out of coherency.",
            "Select one additional model to destroy, then the engine will re-check coherency.",
        ]
        content_start_y = self.y + self.title_bar_height + 20
        for index, line in enumerate(explanation_lines):
            text_surface = self.font_medium.render(line, True, TEXT_WARNING)
            screen.blit(text_surface, (self.x + 20, content_start_y + index * 25))
        for button in self.model_buttons:
            rect = button["rect"]
            selected = bool(button["selected"])
            color = BUTTON_SELECTED if selected else BUTTON_BG
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, TEXT_PRIMARY, rect, 2)
            label = str(button["label"] or "Model")
            if button["is_non_coherent"]:
                label = f"{label} [currently out of coherency]"
            text_surface = self.font_small.render(label, True, TEXT_PRIMARY)
            text_rect = text_surface.get_rect(midleft=(rect.left + 12, rect.centery))
            screen.blit(text_surface, text_rect)
        self.draw_button(screen, "remove_selected", "Remove Selected")
        instruction_text = "This choice resolves one casualty at a time; another request appears only if still required."
        instruction_surface = self.font_small.render(instruction_text, True, TEXT_SECONDARY)
        screen.blit(instruction_surface, (self.x + 20, self.y + self.height - 30))
