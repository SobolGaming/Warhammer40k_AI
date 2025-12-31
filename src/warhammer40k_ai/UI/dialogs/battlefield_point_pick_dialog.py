from __future__ import annotations

from typing import Callable, Optional, Tuple

import pygame

from .base_dialog import BaseDialog, PANEL_BG, PANEL_BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_ERROR, BUTTON_BG, BUTTON_HOVER


class BattlefieldPointPickDialog(BaseDialog):
    """
    Full-screen modal overlay that lets the user click the battlefield to choose a point in game inches.

    - Left click: select point
    - Enter: confirm (if selection valid)
    - Esc / Cancel: cancel
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=screen_width, height=screen_height, draggable=False, center=False)
        self.title = "Select Point"
        self.instructions: str = "Click the battlefield to select a point."
        self.game_view = None

        self._validate_cb: Optional[Callable[[float, float], dict]] = None
        self._on_confirm: Optional[Callable[[Tuple[float, float]], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None

        self.selected_point: Optional[Tuple[float, float]] = None
        self._last_validation: dict = {"valid": False, "reason": "No point selected"}

        # Small info panel
        self.panel_w = 520
        self.panel_h = 170
        self.panel_x = 20
        self.panel_y = 20

        # Buttons
        self.buttons.clear()
        self.add_button("confirm", self.panel_x + 20, self.panel_y + self.panel_h - 50, 160, 35)
        self.add_button("cancel", self.panel_x + 200, self.panel_y + self.panel_h - 50, 140, 35)

    def show(
        self,
        *,
        game_view,
        title: str,
        instructions: str,
        validate_cb: Callable[[float, float], dict],
        on_confirm: Callable[[Tuple[float, float]], None],
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        super().show()
        self.visible = True
        self.game_view = game_view
        self.title = title
        self.instructions = instructions
        self._validate_cb = validate_cb
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self.selected_point = None
        self._last_validation = {"valid": False, "reason": "No point selected"}

    def hide(self):
        super().hide()
        self.game_view = None
        self._validate_cb = None
        self._on_confirm = None
        self._on_cancel = None
        self.selected_point = None
        self._last_validation = {"valid": False, "reason": "No point selected"}

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
            if not self.selected_point:
                return True
            if not bool(self._last_validation.get("valid", False)):
                return True
            if self._on_confirm:
                try:
                    self._on_confirm(self.selected_point)
                except Exception:
                    pass
            self.hide()
            return True
        return False

    def _handle_dialog_click(self, mouse_pos) -> bool:
        # Any click anywhere in the full-screen dialog should be treated as a selection attempt,
        # except clicks inside the small info panel (so buttons still work).
        mx, my = mouse_pos
        panel_rect = pygame.Rect(self.panel_x, self.panel_y, self.panel_w, self.panel_h)
        if panel_rect.collidepoint((mx, my)):
            return False

        if not self.game_view:
            return True
        try:
            gx, gy = self.game_view.screen_to_game_coords(mx, my)
        except Exception:
            self._last_validation = {"valid": False, "reason": "Could not convert click to battlefield coordinates"}
            return True

        # Basic bounds check
        try:
            w = float(getattr(self.game_view.game.map, "width", 60))
            h = float(getattr(self.game_view.game.map, "height", 44))
        except Exception:
            w, h = 60.0, 44.0

        if gx < 0 or gy < 0 or gx > w or gy > h:
            self.selected_point = None
            self._last_validation = {"valid": False, "reason": "Click must be on the battlefield"}
            return True

        self.selected_point = (float(gx), float(gy))

        # Validate via callback
        if self._validate_cb:
            try:
                self._last_validation = dict(self._validate_cb(self.selected_point[0], self.selected_point[1]) or {})
            except Exception:
                self._last_validation = {"valid": False, "reason": "Validation failed"}
        else:
            self._last_validation = {"valid": True, "reason": "OK"}

        return True

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            # Confirm if valid
            if self.selected_point and bool(self._last_validation.get("valid", False)):
                return self._handle_button_click("confirm")
            return True
        return True

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return

        # Dim overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(140)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        # Draw selected marker on battlefield
        if self.selected_point and self.game_view:
            try:
                sx, sy = self.game_view.game_to_screen_coords(self.selected_point[0], self.selected_point[1])
                pygame.draw.circle(screen, (255, 215, 0), (sx, sy), 10, 2)  # gold ring
                pygame.draw.line(screen, (255, 215, 0), (sx - 12, sy), (sx + 12, sy), 2)
                pygame.draw.line(screen, (255, 215, 0), (sx, sy - 12), (sx, sy + 12), 2)
            except Exception:
                pass

        # Info panel
        panel_rect = pygame.Rect(self.panel_x, self.panel_y, self.panel_w, self.panel_h)
        pygame.draw.rect(screen, PANEL_BG, panel_rect, border_radius=10)
        pygame.draw.rect(screen, PANEL_BORDER, panel_rect, width=2, border_radius=10)

        # Title
        title_surf = self.font_medium.render(self.title, True, TEXT_PRIMARY)
        screen.blit(title_surf, (self.panel_x + 20, self.panel_y + 15))

        # Instructions
        instr_lines = []
        for raw in (self.instructions or "").split("\n"):
            raw = raw.strip()
            if raw:
                instr_lines.append(raw)
        y = self.panel_y + 45
        for line in instr_lines[:3]:
            s = self.font_small.render(line, True, TEXT_SECONDARY)
            screen.blit(s, (self.panel_x + 20, y))
            y += 18

        # Selected point + validation
        if self.selected_point:
            pt = self.font_small.render(f"Selected: ({self.selected_point[0]:.1f}\", {self.selected_point[1]:.1f}\")", True, TEXT_PRIMARY)
            screen.blit(pt, (self.panel_x + 20, self.panel_y + 105))
        reason = str(self._last_validation.get("reason", "") or "")
        ok = bool(self._last_validation.get("valid", False))
        reason_color = (100, 255, 100) if ok else TEXT_ERROR
        reason_surf = self.font_tiny.render(("OK" if ok else "Invalid") + (f": {reason}" if reason else ""), True, reason_color)
        screen.blit(reason_surf, (self.panel_x + 20, self.panel_y + 125))

        # Buttons (override BaseDialog drawing since our dialog is fullscreen)
        self._update_buttons()
        for name, rect in self.buttons.items():
            hovered = rect.collidepoint(pygame.mouse.get_pos())
            bg = BUTTON_HOVER if hovered else BUTTON_BG
            pygame.draw.rect(screen, bg, rect, border_radius=8)
            pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=8)
            label = "Confirm" if name == "confirm" else "Cancel"
            txt = self.font_small.render(label, True, TEXT_PRIMARY)
            screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))


