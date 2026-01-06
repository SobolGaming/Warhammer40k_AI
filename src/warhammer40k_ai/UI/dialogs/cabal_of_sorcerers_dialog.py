from __future__ import annotations

from typing import Callable, List, Optional

import pygame

from .base_dialog import BaseDialog, PANEL_BG, PANEL_BORDER, TEXT_PRIMARY, TEXT_SECONDARY, BUTTON_BG, BUTTON_HOVER, BUTTON_SELECTED


class CabalOfSorcerersDialog(BaseDialog):
    """Modal dialog to select a Cabal of Sorcerers ritual."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=620, height=460, draggable=True)
        self.title = "Cabal of Sorcerers"
        self.subtitle = ""
        self.options: List[object] = []
        self.selected_idx: Optional[int] = None
        self._on_confirm: Optional[Callable[[object], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None

        self.add_button("confirm", 10, self.height - 50, 160, 35)
        self.add_button("cancel", self.width - 160, self.height - 50, 140, 35)

    def show(
        self,
        *,
        options: List[object],
        on_confirm: Callable[[object], None],
        on_cancel: Optional[Callable[[], None]] = None,
        subtitle: Optional[str] = None,
    ):
        super().show()
        self.visible = True
        self.options = list(options or [])
        self.selected_idx = 0 if self.options else None
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self.subtitle = subtitle or ""

    def hide(self):
        super().hide()
        self.options = []
        self.selected_idx = None
        self._on_confirm = None
        self._on_cancel = None
        self.subtitle = ""

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
            if self.selected_idx is None:
                return True
            if not (0 <= self.selected_idx < len(self.options)):
                return True
            if self._on_confirm:
                try:
                    self._on_confirm(self.options[self.selected_idx])
                except Exception:
                    pass
            self.hide()
            return True
        return False

    def _handle_dialog_click(self, mouse_pos) -> bool:
        mx, my = mouse_pos
        rel_x = mx - self.x
        rel_y = my - self.y - (self.title_bar_height if self.draggable else 0)
        list_top = 85
        list_left = 15
        list_w = self.width - 30
        row_h = 82
        if list_left <= rel_x <= list_left + list_w and list_top <= rel_y <= list_top + row_h * max(1, len(self.options)):
            idx = int((rel_y - list_top) // row_h)
            if 0 <= idx < len(self.options):
                self.selected_idx = idx
                return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                return self._handle_button_click("confirm")
            if event.key == pygame.K_UP:
                if self.selected_idx is not None:
                    self.selected_idx = max(0, self.selected_idx - 1)
                return True
            if event.key == pygame.K_DOWN:
                if self.selected_idx is not None:
                    self.selected_idx = min(len(self.options) - 1, self.selected_idx + 1)
                return True
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

        if self.subtitle:
            sub = self.font_small.render(self.subtitle, True, TEXT_SECONDARY)
            screen.blit(sub, (self.x + 15, self.y + self.title_bar_height + 10))

        row_h = 82
        list_x = self.x + 15
        list_y = self.y + self.title_bar_height + 40
        list_w = self.width - 30
        for i, option in enumerate(self.options):
            r = pygame.Rect(list_x, list_y + i * row_h, list_w, row_h - 8)
            hovered = r.collidepoint(pygame.mouse.get_pos())
            selected = (self.selected_idx == i)
            bg = BUTTON_SELECTED if selected else (BUTTON_HOVER if hovered else BUTTON_BG)
            pygame.draw.rect(screen, bg, r, border_radius=8)
            pygame.draw.rect(screen, PANEL_BORDER, r, width=1, border_radius=8)

            name = getattr(option, "name", str(option))
            warp = getattr(option, "warp_charge", None)
            summary = getattr(option, "summary", "")
            label = f"{name}"
            if warp is not None:
                label = f"{name} (Warp {warp})"
            name_surf = self.font_medium.render(str(label), True, TEXT_PRIMARY)
            screen.blit(name_surf, (r.x + 10, r.y + 8))
            if summary:
                self.draw_text_wrapped(
                    screen,
                    str(summary),
                    r.x + 10,
                    r.y + 34,
                    r.width - 20,
                    self.font_tiny,
                    TEXT_SECONDARY,
                    line_height=16,
                )

        self.draw_button(screen, "confirm", "Confirm")
        self.draw_button(screen, "cancel", "Cancel")
