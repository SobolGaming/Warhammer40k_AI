import pygame
from .base_dialog import BaseDialog, TEXT_SECONDARY, TEXT_PRIMARY


class YesNoDialog(BaseDialog):
    """
    Generic modal Yes/No prompt dialog.

    Callback receives a boolean:
    - True => Yes/Confirm
    - False => No/Cancel
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=520, height=260, draggable=True, center=True)
        self.title = "Confirm"
        self.message = ""
        self.yes_label = "Yes"
        self.no_label = "No"

    def show(self, title: str, message: str, callback, yes_label: str = "Yes", no_label: str = "No"):
        self.title = title or "Confirm"
        self.message = message or ""
        self.yes_label = yes_label or "Yes"
        self.no_label = no_label or "No"
        super().show(callback=callback)
        self._create_buttons()

    def _create_buttons(self):
        self.buttons.clear()
        self.button_states.clear()
        # Two buttons centered at bottom
        bw, bh = 160, 44
        gap = 18
        start_x = (self.width - (2 * bw + gap)) // 2
        y = self.height - 70
        self.add_button("yes", start_x, y, bw, bh, enabled=True)
        self.add_button("no", start_x + bw + gap, y, bw, bh, enabled=True)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "yes":
            cb = self.callback
            self.hide()
            if cb:
                cb(True)
            return True
        if button_name == "no":
            cb = self.callback
            self.hide()
            if cb:
                cb(False)
            return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_y, pygame.K_RETURN):
                return self._handle_button_click("yes")
            if event.key in (pygame.K_n, pygame.K_ESCAPE):
                return self._handle_button_click("no")
        return False

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, self.title)

        # Message text
        # Use BaseDialog helper: centered multi-line
        try:
            self.draw_text_wrapped(
                screen,
                self.message,
                self.x + 20,
                self.y + self.title_bar_height + 20,
                self.width - 40,
                self.font_small,
                TEXT_SECONDARY,
            )
        except Exception:
            # Fallback: single-line
            msg = self.font_small.render(self.message, True, TEXT_SECONDARY)
            screen.blit(msg, (self.x + 20, self.y + self.title_bar_height + 20))

        self._create_buttons()
        self.draw_button(screen, "yes", self.yes_label, text_color=TEXT_PRIMARY)
        self.draw_button(screen, "no", self.no_label, text_color=TEXT_PRIMARY)


