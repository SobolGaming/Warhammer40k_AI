from __future__ import annotations

from typing import Callable, List, Optional

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


class QuarrySelectionDialog(BaseDialog):
    """
    Modal dialog to select an enemy unit as "quarry" (Monarch of the Hunt).

    Notes:
    - Caller passes already-filtered eligible units (e.g., excludes embarked units).
    - Attached units should be provided as their root unit (bodyguard), not individual attached leaders.
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=640, height=420, draggable=True, center=True)
        self.title = "Select Quarry"
        self.subtitle = ""
        self.header = ""
        self.choices = []
        self.selected_idx: Optional[int] = None
        self._on_confirm: Optional[Callable[[object], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None

        self.add_button("confirm", 10, self.height - 50, 160, 35)
        self.add_button("cancel", self.width - 160, self.height - 50, 140, 35)

    def show(
        self,
        *,
        title: str = "Select Quarry",
        header: str = "",
        subtitle: str = "",
        choices: List[object],
        on_confirm: Callable[[object], None],
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        super().show()
        self.visible = True
        self.title = title or "Select Quarry"
        self.header = header or ""
        self.subtitle = subtitle or ""
        self.choices = list(choices or [])
        self.selected_idx = 0 if self.choices else None
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel

    def hide(self):
        super().hide()
        self.subtitle = ""
        self.header = ""
        self.choices = []
        self.selected_idx = None
        self._on_confirm = None
        self._on_cancel = None

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if self._on_cancel is not None:
                self._on_cancel()
            self.hide()
            return True
        if button_name == "confirm":
            if self.selected_idx is None:
                return True
            if not (0 <= self.selected_idx < len(self.choices)):
                return True
            if self._on_confirm is not None:
                self._on_confirm(self.choices[self.selected_idx])
            self.hide()
            return True
        return False

    def _handle_dialog_click(self, mouse_pos) -> bool:
        # list area click -> change selection
        mx, my = mouse_pos
        rel_x = mx - self.x
        rel_y = my - self.y - (self.title_bar_height if self.draggable else 0)
        list_top = 95
        list_left = 15
        list_w = self.width - 30
        row_h = 40
        if list_left <= rel_x <= list_left + list_w and list_top <= rel_y <= list_top + row_h * max(1, len(self.choices)):
            idx = int((rel_y - list_top) // row_h)
            if 0 <= idx < len(self.choices):
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
                    self.selected_idx = min(len(self.choices) - 1, self.selected_idx + 1)
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

        header = self.header or "Choose an enemy unit to be this model's quarry."
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

        # List
        row_h = 40
        list_x = self.x + 15
        list_y = self.y + self.title_bar_height + 70
        list_w = self.width - 30
        for i, u in enumerate(self.choices):
            r = pygame.Rect(list_x, list_y + i * row_h, list_w, row_h - 6)
            hovered = r.collidepoint(pygame.mouse.get_pos())
            selected = (self.selected_idx == i)
            bg = BUTTON_SELECTED if selected else (BUTTON_HOVER if hovered else BUTTON_BG)
            pygame.draw.rect(screen, bg, r, border_radius=8)
            pygame.draw.rect(screen, PANEL_BORDER, r, width=1, border_radius=8)

            name = getattr(u, "name", "Unit")
            status_bits = []
            try:
                rs = str(getattr(u, "reserve_status", "deployed") or "deployed").strip().lower()
                if rs != "deployed":
                    status_bits.append(rs.upper())
            except Exception:
                pass
            try:
                if getattr(u, "is_embarked", None) is not None and callable(getattr(u, "is_embarked")):
                    if bool(u.is_embarked()):
                        status_bits.append("EMBARKED")
            except Exception:
                pass
            suffix = f" [{' / '.join(status_bits)}]" if status_bits else ""
            label = f"{name}{suffix}"
            txt = self.font_small.render(label, True, TEXT_PRIMARY)
            screen.blit(txt, (r.x + 10, r.y + (r.height - txt.get_height()) // 2))

        self.draw_button(screen, "confirm", "Confirm")
        self.draw_button(screen, "cancel", "Cancel")

