from __future__ import annotations

from typing import Callable, Optional

import pygame

from .base_dialog import BaseDialog, BUTTON_SELECTED, TEXT_PRIMARY, TEXT_SECONDARY


class DeveloperMenuDialog(BaseDialog):
    """Floating non-modal developer controls dialog."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=340, height=200, draggable=True, center=False)
        self.title = "Developer Menu"
        self.allow_battlefield_input = True
        self.x = max(20, screen_width - self.width - 20)
        self.y = 20
        self._update_title_bar()
        self._update_buttons()

        self._profiling_enabled = False
        self._on_toggle_profiling: Optional[Callable[[bool], Optional[bool]]] = None
        self._on_close: Optional[Callable[[], None]] = None

        self.add_button("toggle_profiling", 20, 98, self.width - 40, 44)
        self.add_button("close", self.width - 120, self.height - 44, 100, 30)

    def show(
        self,
        *,
        profiling_enabled: bool,
        on_toggle_profiling: Callable[[bool], Optional[bool]],
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        super().show()
        self._profiling_enabled = bool(profiling_enabled)
        self._on_toggle_profiling = on_toggle_profiling
        self._on_close = on_close

    def hide(self) -> None:
        super().hide()
        self._on_toggle_profiling = None
        self._on_close = None

    def set_profiling_enabled(self, enabled: bool) -> None:
        self._profiling_enabled = bool(enabled)

    def handle_event(self, event: pygame.event.Event) -> bool:
        # Preserve global ESC behavior (GameView opens Settings) while this menu is visible.
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return False
        return super().handle_event(event)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "toggle_profiling":
            desired_enabled = not self._profiling_enabled
            if self._on_toggle_profiling is not None:
                result = self._on_toggle_profiling(desired_enabled)
                if isinstance(result, bool):
                    self._profiling_enabled = bool(result)
                else:
                    self._profiling_enabled = desired_enabled
            else:
                self._profiling_enabled = desired_enabled
            return True
        if button_name == "close":
            callback = self._on_close
            self.hide()
            if callback is not None:
                callback()
            return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_RETURN:
            return self._handle_button_click("toggle_profiling")
        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, self.title)

        status = "ON" if self._profiling_enabled else "OFF"
        status_color = (100, 220, 120) if self._profiling_enabled else TEXT_SECONDARY
        self.draw_text_wrapped(
            screen,
            f"cProfile status: {status}",
            self.x + 20,
            self.y + self.title_bar_height + 16,
            self.width - 40,
            self.font_medium,
            status_color,
            line_height=20,
        )
        self.draw_text_wrapped(
            screen,
            "Enable to start sampling current thread.\nDisable to save profiling report files.",
            self.x + 20,
            self.y + self.title_bar_height + 42,
            self.width - 40,
            self.font_small,
            TEXT_SECONDARY,
            line_height=18,
        )

        toggle_label = "Disable Profiling" if self._profiling_enabled else "Enable Profiling"
        toggle_color = BUTTON_SELECTED if self._profiling_enabled else None
        self.draw_button(screen, "toggle_profiling", toggle_label, color=toggle_color, text_color=TEXT_PRIMARY)
        self.draw_button(screen, "close", "Close", text_color=TEXT_PRIMARY)
