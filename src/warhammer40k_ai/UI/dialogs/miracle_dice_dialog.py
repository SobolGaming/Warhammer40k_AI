from __future__ import annotations

from typing import Callable, Optional

import pygame

from .base_dialog import BaseDialog, TEXT_PRIMARY, TEXT_SECONDARY


class MiracleDiceDialog(BaseDialog):
    """
    Dialog for selecting a Miracle die to substitute for a roll.

    Callback returns:
    - int value => chosen Miracle die value
    - None => skip
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=560, height=330, draggable=True, center=True)
        self.title = "Acts of Faith"
        self.message = ""
        self.dice_values: list[int] = []
        self.skip_label = "Skip"
        self._button_values: dict[str, int] = {}

    def show(
        self,
        *,
        title: str,
        message: str,
        dice_values: list[int],
        callback: Callable[[Optional[int]], None],
        skip_label: str = "Skip",
    ):
        self.title = title or "Acts of Faith"
        self.message = message or ""
        self.dice_values = list(dice_values or [])
        self.skip_label = skip_label or "Skip"
        super().show(callback=callback)
        self._create_buttons()

    def _create_buttons(self):
        self.buttons.clear()
        self.button_states.clear()
        self._button_values = {}

        values = list(self.dice_values or [])
        if not values:
            self.add_button("skip", (self.width - 160) // 2, self.height - 70, 160, 40, enabled=True)
            return

        bw, bh = 64, 38
        gap = 10
        cols = min(6, max(1, len(values)))
        rows = (len(values) + cols - 1) // cols

        grid_w = cols * bw + (cols - 1) * gap
        start_x = (self.width - grid_w) // 2
        start_y = self.title_bar_height + 90

        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx >= len(values):
                    break
                x = start_x + c * (bw + gap)
                y = start_y + r * (bh + gap)
                name = f"die_{idx}"
                self.add_button(name, x, y, bw, bh, enabled=True)
                self._button_values[name] = int(values[idx])
                idx += 1

        self.add_button("skip", (self.width - 160) // 2, self.height - 70, 160, 40, enabled=True)

    def _handle_button_click(self, button_name: str) -> bool:
        cb = self.callback
        if button_name == "skip":
            self.hide()
            if cb:
                cb(None)
            return True
        if button_name in self._button_values:
            self.hide()
            if cb:
                cb(int(self._button_values[button_name]))
            return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return self._handle_button_click("skip")
        return False

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, self.title)

        msg_y = self.y + self.title_bar_height + 20
        try:
            self.draw_text_wrapped(
                screen,
                self.message,
                self.x + 20,
                msg_y,
                self.width - 40,
                self.font_small,
                TEXT_SECONDARY,
            )
        except Exception:
            msg = self.font_small.render(self.message, True, TEXT_SECONDARY)
            screen.blit(msg, (self.x + 20, msg_y))

        self._create_buttons()
        for name, val in self._button_values.items():
            self.draw_button(screen, name, str(val), text_color=TEXT_PRIMARY)
        self.draw_button(screen, "skip", self.skip_label, text_color=TEXT_PRIMARY)
