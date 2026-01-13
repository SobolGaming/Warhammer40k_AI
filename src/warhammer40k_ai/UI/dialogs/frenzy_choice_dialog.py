import pygame

from .base_dialog import BaseDialog, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED


class FrenzyChoiceDialog(BaseDialog):
    """Dialog for choosing a Frenzy response (shoot, fight, or skip)."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=560, height=260, draggable=True, center=True)
        self.title = "Frenzy"
        self.message = ""
        self._options = {"shoot": True, "fight": True}

    def show(self, unit_name: str, attacker_name: str, options, callback):
        self.title = "Frenzy"
        unit_label = unit_name or "Unit"
        attacker_label = attacker_name or "Enemy unit"
        self.message = f"{unit_label} can react to {attacker_label}. Choose a response."
        opt = set(str(o or "").strip().lower() for o in (options or []))
        self._options = {
            "shoot": "shoot" in opt,
            "fight": "fight" in opt,
        }
        super().show(callback=callback)
        self._create_buttons()

    def _create_buttons(self):
        self.buttons.clear()
        self.button_states.clear()
        bw, bh = 140, 42
        gap = 14
        total = bw * 3 + gap * 2
        start_x = (self.width - total) // 2
        y = self.height - 70
        self.add_button("shoot", start_x, y, bw, bh, enabled=self._options.get("shoot", False))
        self.add_button("fight", start_x + bw + gap, y, bw, bh, enabled=self._options.get("fight", False))
        self.add_button("skip", start_x + (bw + gap) * 2, y, bw, bh, enabled=True)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name in ("shoot", "fight", "skip"):
            if button_name != "skip" and not self._options.get(button_name, False):
                return False
            cb = self.callback
            self.hide()
            if cb:
                cb(button_name)
            return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_n):
                return self._handle_button_click("skip")
            if event.key == pygame.K_s:
                return self._handle_button_click("shoot")
            if event.key == pygame.K_f:
                return self._handle_button_click("fight")
        return False

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, self.title)
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
            msg = self.font_small.render(self.message, True, TEXT_SECONDARY)
            screen.blit(msg, (self.x + 20, self.y + self.title_bar_height + 20))

        self._create_buttons()
        self.draw_button(screen, "shoot", "Shoot", text_color=TEXT_PRIMARY if self._options.get("shoot", False) else TEXT_DISABLED)
        self.draw_button(screen, "fight", "Fight", text_color=TEXT_PRIMARY if self._options.get("fight", False) else TEXT_DISABLED)
        self.draw_button(screen, "skip", "Skip", text_color=TEXT_PRIMARY)
