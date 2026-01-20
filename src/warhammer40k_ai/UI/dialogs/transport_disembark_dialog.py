import pygame
from typing import List, Optional, Callable, Set

from .base_dialog import BaseDialog, BUTTON_BG, PANEL_BORDER, TEXT_SECONDARY, BUTTON_SELECTED


class TransportDisembarkDialog(BaseDialog):
    """Dialog for selecting one or more embarked units to disembark from a transport."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=640, height=440, draggable=True, center=True)
        self.transport_unit = None
        self.passengers: List = []
        self.selected_indices: Set[int] = set()
        self.on_confirm: Optional[Callable[[List], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None
        self.confirm_label = "Disembark"
        self.cancel_label = "Cancel"
        self.show_cancel = True
        self.decision_request = None

        self.scroll_offset = 0
        self.max_scroll = 0

    def show(
        self,
        transport_unit,
        passengers: List,
        on_confirm: Callable[[List], None],
        on_cancel: Optional[Callable[[], None]] = None,
        *,
        confirm_label: str = "Disembark",
        cancel_label: str = "Cancel",
        show_cancel: bool = True,
        decision_request=None,
    ) -> None:
        self.transport_unit = transport_unit
        self.passengers = list(passengers or [])
        self.selected_indices = set()
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.confirm_label = str(confirm_label or "Disembark")
        self.cancel_label = str(cancel_label or "Cancel")
        self.show_cancel = bool(show_cancel)
        self.scroll_offset = 0
        self.decision_request = decision_request
        super().show()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.transport_unit = None
        self.passengers = []
        self.selected_indices = set()
        self.on_confirm = None
        self.on_cancel = None
        self.confirm_label = "Disembark"
        self.cancel_label = "Cancel"
        self.show_cancel = True
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
        self.buttons.clear()
        self.button_states.clear()

        button_width = self.width - 40
        button_height = 56
        button_spacing = 10
        start_y_rel = self.title_bar_height + 60

        for i, _u in enumerate(self.passengers):
            rel_y = start_y_rel + i * (button_height + button_spacing) - self.scroll_offset
            if rel_y + button_height < self.title_bar_height + 40 or rel_y > self.height - 70:
                continue
            self.add_button(f"unit_{i}", 20, rel_y, button_width, button_height, enabled=True)

        total_height = len(self.passengers) * (button_height + button_spacing)
        available_height = self.height - (self.title_bar_height + 120)
        self.max_scroll = max(0, total_height - available_height)

        if self.show_cancel:
            self.add_button("confirm", self.width - 280, self.height - 55, 120, 38, enabled=True)
            self.add_button("cancel", self.width - 150, self.height - 55, 120, 38, enabled=True)
        else:
            self.add_button("confirm", self.width - 150, self.height - 55, 120, 38, enabled=True)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True

        if button_name == "confirm":
            chosen = []
            for i in sorted(self.selected_indices):
                if 0 <= i < len(self.passengers):
                    chosen.append(self.passengers[i])
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
        subtitle = f"{len(self.passengers)} embarked units"
        self.draw_title_bar(screen, f"Disembark from {tname}", subtitle=subtitle)

        inst = "Select one or more units to disembark."
        inst_surface = self.font_small.render(inst, True, TEXT_SECONDARY)
        screen.blit(inst_surface, (self.x + 20, self.y + self.title_bar_height + 10))

        self._create_buttons()
        self._update_buttons()

        for i, unit in enumerate(self.passengers):
            btn_name = f"unit_{i}"
            if btn_name not in self.buttons:
                continue
            if btn_name in self.button_states:
                self.button_states[btn_name]['state'] = 'selected' if i in self.selected_indices else 'normal'
            rect = self.buttons[btn_name]
            label = getattr(unit, "name", f"unit_{i}")
            self.draw_button(screen, btn_name, label, color=BUTTON_BG)
            if i in self.selected_indices:
                pygame.draw.rect(screen, BUTTON_SELECTED, rect, 2)
            else:
                pygame.draw.rect(screen, PANEL_BORDER, rect, 1)

        self.draw_button(screen, "confirm", self.confirm_label or "Disembark")
        if self.show_cancel:
            self.draw_button(screen, "cancel", self.cancel_label or "Cancel")
