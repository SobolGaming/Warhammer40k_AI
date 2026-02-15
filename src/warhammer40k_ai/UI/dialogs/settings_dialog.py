from __future__ import annotations

from typing import Callable, Optional

import pygame

from .base_dialog import (
    BaseDialog,
    BUTTON_SELECTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SettingsDialog(BaseDialog):
    """Global UI settings dialog."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=560, height=300, draggable=True, center=True)
        self.title = "Settings"
        self._enable_developer_controls = False
        self._on_apply: Optional[Callable[[bool], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None

        self.add_button("toggle_dev_controls", 20, 128, self.width - 40, 44)
        self.add_button("apply", 20, self.height - 56, 160, 36)
        self.add_button("cancel", self.width - 180, self.height - 56, 160, 36)

    def show(
        self,
        *,
        enable_developer_controls: bool,
        on_apply: Callable[[bool], None],
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        super().show()
        self._enable_developer_controls = bool(enable_developer_controls)
        self._on_apply = on_apply
        self._on_cancel = on_cancel
        self._sync_button_state()

    def hide(self) -> None:
        super().hide()
        self._on_apply = None
        self._on_cancel = None

    def _sync_button_state(self) -> None:
        state = self.button_states.get("toggle_dev_controls")
        if state is None:
            return
        state["state"] = "selected" if self._enable_developer_controls else "normal"

    def _cancel(self) -> None:
        callback = self._on_cancel
        self.hide()
        if callback is not None:
            callback()

    def _confirm(self) -> None:
        callback = self._on_apply
        enabled = bool(self._enable_developer_controls)
        self.hide()
        if callback is not None:
            callback(enabled)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "toggle_dev_controls":
            self._enable_developer_controls = not self._enable_developer_controls
            self._sync_button_state()
            return True
        if button_name == "apply":
            self._confirm()
            return True
        if button_name == "cancel":
            self._cancel()
            return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_RETURN:
            self._confirm()
            return True
        if event.key == pygame.K_SPACE:
            self._enable_developer_controls = not self._enable_developer_controls
            self._sync_button_state()
            return True
        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, self.title)

        body_top = self.y + self.title_bar_height + 14
        self.draw_text_wrapped(
            screen,
            "Configure global UI settings.",
            self.x + 20,
            body_top,
            self.width - 40,
            self.font_small,
            TEXT_SECONDARY,
            line_height=18,
        )
        self.draw_text_wrapped(
            screen,
            "Enable developer controls to show the floating developer menu.",
            self.x + 20,
            body_top + 24,
            self.width - 40,
            self.font_small,
            TEXT_SECONDARY,
            line_height=18,
        )

        status = "ON" if self._enable_developer_controls else "OFF"
        toggle_text = f"Enable developer controls: {status}"
        toggle_color = BUTTON_SELECTED if self._enable_developer_controls else None
        self.draw_button(screen, "toggle_dev_controls", toggle_text, color=toggle_color, text_color=TEXT_PRIMARY)
        self.draw_button(screen, "apply", "Apply", text_color=TEXT_PRIMARY)
        self.draw_button(screen, "cancel", "Cancel", text_color=TEXT_PRIMARY)
