from __future__ import annotations

from typing import Callable, Optional, Tuple

import pygame

from .base_dialog import BaseDialog, TEXT_PRIMARY, TEXT_SECONDARY, PANEL_BORDER, TEXT_WARNING, TEXT_SUCCESS


class RollRerollDialog(BaseDialog):
    """
    Blocking prompt: show a roll (Advance/Charge) and allow the user to re-roll it.

    Callback returns:
    - True  => re-roll
    - False => keep
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=560, height=300, draggable=True, center=True)
        self.title = "Re-roll?"
        self.message = ""
        self._roll_text = ""
        self._roll_border_color: Optional[Tuple[int, int, int]] = None
        self.keep_label = "Keep"
        self.reroll_label = "Re-roll"

    def show(
        self,
        *,
        title: str,
        message: str,
        roll_text: str = "",
        roll_border: Optional[str] = None,  # "fail" | "success" | None
        callback: Callable[[bool], None],
        keep_label: str = "Keep",
        reroll_label: str = "Re-roll",
    ):
        self.title = title or "Re-roll?"
        self.message = message or ""
        self._roll_text = roll_text or ""
        rb = (roll_border or "").strip().lower()
        if rb == "fail":
            self._roll_border_color = TEXT_WARNING  # red-ish
        elif rb == "success":
            self._roll_border_color = TEXT_SUCCESS  # green-ish
        else:
            self._roll_border_color = None
        self.keep_label = keep_label or "Keep"
        self.reroll_label = reroll_label or "Re-roll"
        super().show(callback=callback)
        self._create_buttons()

    def _create_buttons(self):
        self.buttons.clear()
        self.button_states.clear()
        bw, bh = 170, 44
        gap = 16
        start_x = (self.width - (2 * bw + gap)) // 2
        y = self.height - 75
        self.add_button("keep", start_x, y, bw, bh, enabled=True)
        self.add_button("reroll", start_x + bw + gap, y, bw, bh, enabled=True)

    def _handle_button_click(self, button_name: str) -> bool:
        cb = self.callback
        if button_name == "keep":
            self.hide()
            if cb:
                cb(False)
            return True
        if button_name == "reroll":
            self.hide()
            if cb:
                cb(True)
            return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_k):
                return self._handle_button_click("keep")
            if event.key in (pygame.K_r,):
                return self._handle_button_click("reroll")
        return False

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, self.title)

        # Optional highlighted roll card (border color indicates fail/success eligibility)
        if self._roll_text:
            card_x = self.x + 20
            card_y = self.y + self.title_bar_height + 18
            card_w = self.width - 40
            card_h = 56
            r = pygame.Rect(card_x, card_y, card_w, card_h)
            pygame.draw.rect(screen, (30, 30, 35), r, border_radius=10)
            pygame.draw.rect(
                screen,
                (self._roll_border_color or PANEL_BORDER),
                r,
                width=3 if self._roll_border_color else 2,
                border_radius=10,
            )
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
        self.draw_button(screen, "keep", self.keep_label, text_color=TEXT_PRIMARY)
        self.draw_button(screen, "reroll", self.reroll_label, text_color=TEXT_PRIMARY)


