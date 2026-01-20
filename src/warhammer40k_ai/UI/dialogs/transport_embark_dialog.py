import pygame
from typing import List, Optional, Callable, Set

from .base_dialog import BaseDialog, BUTTON_BG, PANEL_BORDER, TEXT_PRIMARY, TEXT_SECONDARY, BUTTON_SELECTED


class TransportEmbarkDialog(BaseDialog):
    """Dialog for selecting one or more units to embark into a transport."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=640, height=460, draggable=True, center=True)
        self.transport_unit = None
        self.candidates: List = []
        self.selected_indices: Set[int] = set()
        self.on_confirm: Optional[Callable[[List], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None
        self.decision_request = None

        # Scrolling
        self.scroll_offset = 0
        self.max_scroll = 0

    def show(self, transport_unit, candidates: List, on_confirm: Callable[[List], None], on_cancel: Optional[Callable[[], None]] = None, decision_request=None) -> None:
        self.transport_unit = transport_unit
        self.candidates = list(candidates or [])
        self.selected_indices = set()
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.scroll_offset = 0
        self.decision_request = decision_request
        super().show()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.transport_unit = None
        self.candidates = []
        self.selected_indices = set()
        self.on_confirm = None
        self.on_cancel = None
        self.scroll_offset = 0
        self.max_scroll = 0
        self.decision_request = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if super().handle_event(event):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self.scroll_offset = max(0, self.scroll_offset - 20)
                return True
            if event.button == 5:
                self.scroll_offset = min(self.max_scroll, self.scroll_offset + 20)
                return True
        return False

    def _create_buttons(self) -> None:
        # Clear existing buttons
        self.buttons.clear()
        self.button_states.clear()

        # Candidate list buttons
        button_width = self.width - 40
        button_height = 52
        button_spacing = 10
        start_y_rel = self.title_bar_height + 70

        for i, _unit in enumerate(self.candidates):
            rel_y = start_y_rel + i * (button_height + button_spacing) - self.scroll_offset
            if rel_y + button_height < self.title_bar_height + 50 or rel_y > self.height - 70:
                continue
            self.add_button(f"unit_{i}", 20, rel_y, button_width, button_height, enabled=True)

        total_height = len(self.candidates) * (button_height + button_spacing)
        available_height = self.height - (self.title_bar_height + 130)
        self.max_scroll = max(0, total_height - available_height)

        # Action buttons
        self.add_button("confirm", self.width - 280, self.height - 55, 120, 38, enabled=True)
        self.add_button("cancel", self.width - 150, self.height - 55, 120, 38, enabled=True)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True

        if button_name == "confirm":
            chosen = []
            for i in sorted(self.selected_indices):
                if 0 <= i < len(self.candidates):
                    chosen.append(self.candidates[i])
            if self.on_confirm:
                self.on_confirm(chosen)
            self.hide()
            return True

        if button_name.startswith("unit_"):
            try:
                idx = int(button_name.split("_", 1)[1])
            except Exception:
                return False
            if idx in self.selected_indices:
                self.selected_indices.remove(idx)
            else:
                self.selected_indices.add(idx)
            return True

        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        self.draw_dialog_background(screen)
        tname = getattr(self.transport_unit, "name", "Transport")
        subtitle = f"{len(self.candidates)} valid units"
        self.draw_title_bar(screen, f"Embark into {tname}", subtitle=subtitle)

        # Instructions
        inst = "Select one or more units to embark."
        inst_surface = self.font_small.render(inst, True, TEXT_SECONDARY)
        screen.blit(inst_surface, (self.x + 20, self.y + self.title_bar_height + 10))

        # Update visible buttons (scroll-aware)
        self._create_buttons()
        self._update_buttons()

        # Draw unit rows
        for i, unit in enumerate(self.candidates):
            btn_name = f"unit_{i}"
            if btn_name not in self.buttons:
                continue
            # Mark selection state
            if btn_name in self.button_states:
                self.button_states[btn_name]['state'] = 'selected' if i in self.selected_indices else 'normal'
            rect = self.buttons[btn_name]
            label = getattr(unit, "name", f"unit_{i}")
            self.draw_button(screen, btn_name, label, color=BUTTON_BG)
            # Secondary line: slots
            try:
                slots = unit.get_transport_slots_required()
            except Exception:
                slots = 0
            info = f"Slots: {slots}"
            info_surface = self.font_tiny.render(info, True, TEXT_SECONDARY)
            screen.blit(info_surface, (rect.x + 12, rect.y + rect.height - 18))

            # Outline selected
            if i in self.selected_indices:
                pygame.draw.rect(screen, BUTTON_SELECTED, rect, 2)
            else:
                pygame.draw.rect(screen, PANEL_BORDER, rect, 1)

        # Buttons
        self.draw_button(screen, "confirm", "Embark")
        self.draw_button(screen, "cancel", "Cancel")
