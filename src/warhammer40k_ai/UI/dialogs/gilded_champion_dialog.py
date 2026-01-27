from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import pygame

from .base_dialog import (
    BaseDialog,
    BUTTON_BG,
    BUTTON_HOVER,
    BUTTON_SELECTED,
    PANEL_BG,
    PANEL_BORDER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class GildedChampionDialog(BaseDialog):
    """Modal dialog for the Lions of the Emperor Gilded Champion stratagem."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=560, height=300, draggable=True)
        self.title = "Gilded Champion"
        self.selected_idx: Optional[int] = None
        self._on_select: Optional[Callable[[str], None]] = None
        self._options: List[Tuple[str, str, str]] = []
        self._model_name = ""
        self._ability_name = ""
        self._phase_name = ""
        self._cp_cost = 1

        self.add_button("confirm", (self.width - 160) // 2, self.height - 52, 160, 36)

    def show(
        self,
        *,
        model_name: str,
        ability_name: str,
        phase_name: str,
        cp_cost: int,
        on_select: Callable[[str], None],
    ) -> None:
        super().show()
        self.visible = True
        self._model_name = str(model_name or "Model")
        self._ability_name = str(ability_name or "ability")
        self._phase_name = str(phase_name or "")
        self._cp_cost = max(0, int(cp_cost or 0))
        self._on_select = on_select
        cp_label = f"Spend {self._cp_cost}CP" if self._cp_cost else "Spend CP"
        self._options = [
            (f"{cp_label} to use Gilded Champion", "use", "Grant one extra use (not this phase)."),
            ("None", "none", "Do not use this stratagem."),
        ]
        self.selected_idx = None

    def hide(self) -> None:
        super().hide()
        self.selected_idx = None
        self._on_select = None
        self._options = []

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name != "confirm":
            return False
        if self.selected_idx is None or not (0 <= self.selected_idx < len(self._options)):
            return True
        if self._on_select is not None:
            action = self._options[self.selected_idx][1]
            self._on_select(action)
        self.hide()
        return True

    def _handle_dialog_click(self, mouse_pos) -> bool:
        mx, my = mouse_pos
        rel_x = mx - self.x
        rel_y = my - self.y - (self.title_bar_height if self.draggable else 0)
        list_top = 140
        list_left = 15
        list_w = self.width - 30
        row_h = 64
        if list_left <= rel_x <= list_left + list_w and list_top <= rel_y <= list_top + row_h * max(1, len(self._options)):
            idx = int((rel_y - list_top) // row_h)
            if 0 <= idx < len(self._options):
                self.selected_idx = idx
                return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                return self._handle_button_click("confirm")
            if event.key == pygame.K_UP:
                if self.selected_idx is None:
                    self.selected_idx = 0
                else:
                    self.selected_idx = max(0, self.selected_idx - 1)
                return True
            if event.key == pygame.K_DOWN:
                if self.selected_idx is None:
                    self.selected_idx = 0
                else:
                    self.selected_idx = min(len(self._options) - 1, self.selected_idx + 1)
                return True
        return True

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        panel = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        panel.fill((*PANEL_BG, 235) if len(PANEL_BG) == 3 else PANEL_BG)
        screen.blit(panel, (self.x, self.y))
        pygame.draw.rect(screen, PANEL_BORDER, dialog_rect, 2, border_radius=10)

        self.draw_title_bar(screen, self.title)

        header = f"{self._model_name} used {self._ability_name}"
        header_surf = self.font_small.render(header, True, TEXT_PRIMARY)
        screen.blit(header_surf, (self.x + 15, self.y + self.title_bar_height + 10))

        phase_line = self._phase_name.strip()
        if phase_line:
            phase_surf = self.font_tiny.render(f"Phase: {phase_line}", True, TEXT_SECONDARY)
            screen.blit(phase_surf, (self.x + 15, self.y + self.title_bar_height + 34))

        description = (
            "Gilded Champion: you can use that once-per-battle ability one additional time "
            "(but not in the same phase)."
        )
        self.draw_text_wrapped(
            screen,
            description,
            self.x + 15,
            self.y + self.title_bar_height + 56,
            self.width - 30,
            self.font_tiny,
            TEXT_SECONDARY,
            line_height=16,
        )

        row_h = 64
        list_x = self.x + 15
        list_y = self.y + self.title_bar_height + 94
        list_w = self.width - 30
        for i, (label, _action, summary) in enumerate(self._options):
            r = pygame.Rect(list_x, list_y + i * row_h, list_w, row_h - 8)
            hovered = r.collidepoint(pygame.mouse.get_pos())
            selected = self.selected_idx == i
            bg = BUTTON_SELECTED if selected else (BUTTON_HOVER if hovered else BUTTON_BG)
            pygame.draw.rect(screen, bg, r, border_radius=8)
            pygame.draw.rect(screen, PANEL_BORDER, r, width=1, border_radius=8)

            label_surf = self.font_small.render(str(label), True, TEXT_PRIMARY)
            screen.blit(label_surf, (r.x + 10, r.y + 6))
            if summary:
                self.draw_text_wrapped(
                    screen,
                    str(summary),
                    r.x + 10,
                    r.y + 28,
                    r.width - 20,
                    self.font_tiny,
                    TEXT_SECONDARY,
                    line_height=15,
                )

        self.draw_button(screen, "confirm", "Confirm")

