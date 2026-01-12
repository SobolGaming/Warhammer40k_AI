from __future__ import annotations

from typing import Callable, Optional, Tuple

import pygame

from .base_dialog import BaseDialog, TEXT_PRIMARY, TEXT_SECONDARY, PANEL_BORDER


class AspectShrinePromptDialog(BaseDialog):
    """
    Blocking prompt: allow spending an Aspect Shrine token on a hit/wound roll.

    Callback returns one of: "use", "skip", "suppress".
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=600, height=320, draggable=True, center=True)
        self.title = "Aspect Shrine Token"
        self.message = ""
        self._roll_text = ""

    def show(
        self,
        *,
        title: str,
        message: str,
        roll_text: str = "",
        callback: Callable[[str], None],
    ):
        self.title = title or "Aspect Shrine Token"
        self.message = message or ""
        self._roll_text = roll_text or ""
        super().show(callback=callback)
        self._create_buttons()

    def _create_buttons(self):
        self.buttons.clear()
        self.button_states.clear()
        bw, bh = 160, 44
        gap = 16
        total_w = 3 * bw + 2 * gap
        start_x = (self.width - total_w) // 2
        y = self.height - 75
        self.add_button("use", start_x, y, bw, bh, enabled=True)
        self.add_button("skip", start_x + bw + gap, y, bw, bh, enabled=True)
        self.add_button("suppress", start_x + 2 * (bw + gap), y, bw, bh, enabled=True)

    def _handle_button_click(self, button_name: str) -> bool:
        cb = self.callback
        if button_name == "use":
            self.hide()
            if cb:
                cb("use")
            return True
        if button_name == "skip":
            self.hide()
            if cb:
                cb("skip")
            return True
        if button_name == "suppress":
            self.hide()
            if cb:
                cb("suppress")
            return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_u):
                return self._handle_button_click("use")
            if event.key in (pygame.K_n, pygame.K_d):
                return self._handle_button_click("skip")
            if event.key in (pygame.K_s, pygame.K_f):
                return self._handle_button_click("suppress")
        return False

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, self.title)

        # Roll card
        if self._roll_text:
            card_x = self.x + 20
            card_y = self.y + self.title_bar_height + 18
            card_w = self.width - 40
            card_h = 56
            r = pygame.Rect(card_x, card_y, card_w, card_h)
            pygame.draw.rect(screen, (30, 30, 35), r, border_radius=10)
            pygame.draw.rect(screen, PANEL_BORDER, r, width=2, border_radius=10)
            txt = self.font_medium.render(self._roll_text, True, TEXT_PRIMARY)
            screen.blit(txt, (r.x + 12, r.y + (r.height - txt.get_height()) // 2))
            msg_y = card_y + card_h + 12
        else:
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
        self.draw_button(screen, "use", "Use", text_color=TEXT_PRIMARY)
        self.draw_button(screen, "skip", "Don't Use", text_color=TEXT_PRIMARY)
        self.draw_button(screen, "suppress", "Don't Use for this Unit", text_color=TEXT_PRIMARY)
