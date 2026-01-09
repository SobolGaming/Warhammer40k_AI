from __future__ import annotations

from typing import Callable, Optional

import pygame

from .base_dialog import (
    BaseDialog,
    PANEL_BG,
    PANEL_BORDER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    BUTTON_BG,
    BUTTON_HOVER,
    BUTTON_SELECTED,
)


class PledgeSelectionDialog(BaseDialog):
    """Modal dialog to select a Pledge target value (integer)."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=520, height=300, draggable=True, center=True)
        self.title = "Pledge to Slaanesh"
        self.subtitle = ""
        self.min_value = 1
        self.max_value = 1
        self.value = 1
        self._input_text = "1"
        self._on_confirm: Optional[Callable[[int], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None

        self._input_w = 120
        self._input_h = 44
        self._input_x = (self.width - self._input_w) // 2
        self._input_y = 150

        btn_size = 36
        self.add_button("minus", self._input_x - (btn_size + 12), self._input_y + 4, btn_size, btn_size)
        self.add_button("plus", self._input_x + self._input_w + 12, self._input_y + 4, btn_size, btn_size)
        self.add_button("confirm", 10, self.height - 50, 160, 35)
        self.add_button("cancel", self.width - 160, self.height - 50, 140, 35)

    def show(
        self,
        *,
        max_value: int,
        default_value: int = 1,
        on_confirm: Callable[[int], None],
        on_cancel: Optional[Callable[[], None]] = None,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
    ):
        super().show()
        self.visible = True
        self.title = title or "Pledge to Slaanesh"
        self.subtitle = subtitle or ""
        try:
            self.max_value = max(1, int(max_value))
        except Exception:
            self.max_value = 1
        try:
            default = int(default_value)
        except Exception:
            default = 1
        self._set_value(default)
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel

    def hide(self):
        super().hide()
        self.subtitle = ""
        self._on_confirm = None
        self._on_cancel = None

    def _set_value(self, value: int) -> None:
        try:
            val = int(value)
        except Exception:
            val = self.min_value
        val = max(self.min_value, min(val, self.max_value))
        self.value = val
        self._input_text = str(val)

    def _apply_text_value(self) -> None:
        try:
            val = int(self._input_text or 0)
        except Exception:
            val = self.min_value
        self._set_value(val)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if self._on_cancel:
                try:
                    self._on_cancel()
                except Exception:
                    pass
            self.hide()
            return True
        if button_name == "confirm":
            if self._on_confirm:
                try:
                    self._on_confirm(int(self.value))
                except Exception:
                    pass
            self.hide()
            return True
        if button_name == "minus":
            self._set_value(self.value - 1)
            return True
        if button_name == "plus":
            self._set_value(self.value + 1)
            return True
        return False

    def _handle_dialog_click(self, mouse_pos) -> bool:
        mx, my = mouse_pos
        rel_x = mx - self.x
        rel_y = my - self.y - (self.title_bar_height if self.draggable else 0)
        input_rect = pygame.Rect(self._input_x, self._input_y, self._input_w, self._input_h)
        if input_rect.collidepoint(rel_x, rel_y):
            return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                return self._handle_button_click("confirm")
            if event.key in (pygame.K_UP, pygame.K_KP_PLUS):
                self._set_value(self.value + 1)
                return True
            if event.key in (pygame.K_DOWN, pygame.K_KP_MINUS):
                self._set_value(self.value - 1)
                return True
            if event.key == pygame.K_BACKSPACE:
                if len(self._input_text) > 1:
                    self._input_text = self._input_text[:-1]
                else:
                    self._input_text = str(self.min_value)
                self._apply_text_value()
                return True
            try:
                if event.unicode and event.unicode.isdigit():
                    digit = event.unicode
                    if self._input_text == "0":
                        self._input_text = digit
                    else:
                        self._input_text += digit
                    self._apply_text_value()
                    return True
            except Exception:
                pass
        return True

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return

        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        panel = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        panel.fill((*PANEL_BG, 235) if len(PANEL_BG) == 3 else PANEL_BG)
        screen.blit(panel, (self.x, self.y))
        pygame.draw.rect(screen, PANEL_BORDER, dialog_rect, 2, border_radius=10)

        self.draw_title_bar(screen, self.title)

        header = "Enter how many enemy units will be destroyed this battle round."
        if self.subtitle:
            header = f"{header}\n{self.subtitle}"
        try:
            self.draw_text_wrapped(
                screen,
                header,
                self.x + 15,
                self.y + self.title_bar_height + 10,
                self.width - 30,
                self.font_small,
                TEXT_SECONDARY,
            )
        except Exception:
            txt = self.font_small.render(header, True, TEXT_SECONDARY)
            screen.blit(txt, (self.x + 15, self.y + self.title_bar_height + 10))

        # Input box
        input_rect = pygame.Rect(self.x + self._input_x, self.y + self._input_y, self._input_w, self._input_h)
        pygame.draw.rect(screen, BUTTON_SELECTED, input_rect, border_radius=6)
        pygame.draw.rect(screen, PANEL_BORDER, input_rect, 2, border_radius=6)
        value_text = str(self.value)
        value_surf = self.font_medium.render(value_text, True, TEXT_PRIMARY)
        screen.blit(
            value_surf,
            (input_rect.centerx - value_surf.get_width() // 2, input_rect.centery - value_surf.get_height() // 2),
        )

        # +/- buttons
        self.draw_button(screen, "minus", "-", text_color=TEXT_PRIMARY)
        self.draw_button(screen, "plus", "+", text_color=TEXT_PRIMARY)

        # Min/Max hint
        hint = f"Min: {self.min_value}  Max: {self.max_value}"
        hint_surf = self.font_tiny.render(hint, True, TEXT_SECONDARY)
        screen.blit(hint_surf, (self.x + 15, input_rect.bottom + 8))

        self.draw_button(screen, "confirm", "Confirm")
        self.draw_button(screen, "cancel", "Cancel")
