from __future__ import annotations

import colorsys
import math
from typing import Callable, Dict, List, Optional, Tuple

import pygame

from .base_dialog import (
    BaseDialog,
    PANEL_BG,
    PANEL_BORDER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ..decision_ui_utils import option_entries


class PlayerColorPickerDialog(BaseDialog):
    """Modal color-wheel dialog for CHOOSE_PLAYER_COLOR setup decisions."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=560, height=520, draggable=True, center=True)
        self.title = "Select Player Color"
        self.player_name = "Player"
        self.decision_request = None
        self._on_confirm: Optional[Callable[[str], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None
        self._entries_by_hue: Dict[int, dict] = {}
        self._hue_options: List[int] = []
        self._selected_hue: Optional[int] = None

        self._wheel_radius = 120
        self._wheel_thickness = 32
        self._wheel_surface: Optional[pygame.Surface] = None

        self.add_button("confirm", 12, self.height - 50, 180, 35)
        self.add_button("cancel", self.width - 152, self.height - 50, 140, 35)

    def show(
        self,
        *,
        player_name: str,
        on_confirm: Callable[[str], None],
        on_cancel: Optional[Callable[[], None]] = None,
        decision_request=None,
        initial_hue_degrees: int | None = None,
        initial_rgb: Tuple[int, int, int] | None = None,
    ) -> None:
        super().show()
        self.player_name = str(player_name or "Player")
        self.decision_request = decision_request
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._entries_by_hue = {}
        self._hue_options = []
        self._selected_hue = None

        for entry in option_entries(self.decision_request):
            payload = dict(entry.get("payload", {}) or {})
            raw_hue = payload.get("hue_degrees", None)
            if raw_hue is None:
                continue
            hue = int(raw_hue) % 360
            self._entries_by_hue[hue] = entry

        self._hue_options = sorted(self._entries_by_hue.keys())
        if self._hue_options:
            if initial_hue_degrees is not None:
                self._selected_hue = self._nearest_hue(float(initial_hue_degrees))
            elif initial_rgb is not None:
                self._selected_hue = self._nearest_hue_for_rgb(initial_rgb)
            if self._selected_hue is None:
                self._selected_hue = self._hue_options[0]

    def hide(self):
        super().hide()
        self.decision_request = None
        self._on_confirm = None
        self._on_cancel = None
        self._entries_by_hue = {}
        self._hue_options = []
        self._selected_hue = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._cancel()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.get_dialog_rect().collidepoint(event.pos):
                self._cancel()
                return True
        return super().handle_event(event)

    def _selected_entry(self) -> Optional[dict]:
        if self._selected_hue is None:
            return None
        return self._entries_by_hue.get(int(self._selected_hue) % 360)

    def _selected_option_id(self) -> str:
        entry = self._selected_entry()
        if entry is None:
            return ""
        return str(entry.get("option_id", "") or "")

    def _selected_rgb(self) -> tuple[int, int, int]:
        entry = self._selected_entry()
        if entry is None:
            return (128, 128, 128)
        payload = dict(entry.get("payload", {}) or {})
        rgb = list(payload.get("rgb", []) or [])
        if len(rgb) != 3:
            return (128, 128, 128)
        return (int(rgb[0]), int(rgb[1]), int(rgb[2]))

    def _cancel(self) -> None:
        callback = self._on_cancel
        self.hide()
        if callback is not None:
            callback()

    def _confirm(self) -> None:
        option_id = self._selected_option_id()
        if not option_id:
            return
        callback = self._on_confirm
        self.hide()
        if callback is not None:
            callback(option_id)

    def _hue_distance(self, left: float, right: int) -> float:
        diff = abs(float(left) - float(right)) % 360.0
        return min(diff, 360.0 - diff)

    def _nearest_hue(self, hue_degrees: float) -> Optional[int]:
        if not self._hue_options:
            return None
        return min(self._hue_options, key=lambda value: self._hue_distance(hue_degrees, value))

    def _nearest_hue_for_rgb(self, rgb: Tuple[int, int, int]) -> Optional[int]:
        if not self._hue_options:
            return None
        target = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
        best_hue: Optional[int] = None
        best_dist: Optional[int] = None
        for hue in self._hue_options:
            entry = self._entries_by_hue.get(int(hue) % 360)
            if entry is None:
                continue
            payload = dict(entry.get("payload", {}) or {})
            option_rgb = list(payload.get("rgb", []) or [])
            if len(option_rgb) != 3:
                continue
            dr = int(option_rgb[0]) - target[0]
            dg = int(option_rgb[1]) - target[1]
            db = int(option_rgb[2]) - target[2]
            dist = dr * dr + dg * dg + db * db
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_hue = int(hue) % 360
        return best_hue

    def _step_selection(self, offset: int) -> None:
        if not self._hue_options:
            return
        if self._selected_hue is None:
            self._selected_hue = self._hue_options[0]
            return
        current = int(self._selected_hue) % 360
        try:
            idx = self._hue_options.index(current)
        except ValueError:
            idx = 0
        self._selected_hue = self._hue_options[(idx + int(offset)) % len(self._hue_options)]

    def _wheel_center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.title_bar_height + 185)

    def _wheel_inner_radius(self) -> int:
        return max(10, int(self._wheel_radius - self._wheel_thickness))

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "confirm":
            self._confirm()
            return True
        if button_name == "cancel":
            self._cancel()
            return True
        return False

    def _handle_dialog_click(self, mouse_pos) -> bool:
        if not self._hue_options:
            return False
        cx, cy = self._wheel_center()
        dx = float(mouse_pos[0] - cx)
        dy = float(mouse_pos[1] - cy)
        dist = math.hypot(dx, dy)
        inner = float(self._wheel_inner_radius())
        outer = float(self._wheel_radius + 4)
        if dist < inner or dist > outer:
            return False
        angle = (math.degrees(math.atan2(-dy, dx)) + 360.0) % 360.0
        nearest = self._nearest_hue(angle)
        if nearest is None:
            return False
        self._selected_hue = nearest
        return True

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_RETURN:
            self._confirm()
            return True
        if event.key in (pygame.K_LEFT, pygame.K_DOWN):
            self._step_selection(-1)
            return True
        if event.key in (pygame.K_RIGHT, pygame.K_UP):
            self._step_selection(1)
            return True
        return False

    def _build_wheel_surface(self) -> pygame.Surface:
        diameter = int(self._wheel_radius * 2 + 4)
        center = diameter // 2
        inner = self._wheel_inner_radius()
        outer = int(self._wheel_radius)
        surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)

        for angle in range(360):
            hue = float(angle) / 360.0
            red, green, blue = colorsys.hsv_to_rgb(hue, 0.85, 0.95)
            rgb = (int(round(red * 255.0)), int(round(green * 255.0)), int(round(blue * 255.0)))
            radians = math.radians(float(angle))
            x1 = center + int(math.cos(radians) * inner)
            y1 = center - int(math.sin(radians) * inner)
            x2 = center + int(math.cos(radians) * outer)
            y2 = center - int(math.sin(radians) * outer)
            pygame.draw.line(surface, rgb, (x1, y1), (x2, y2), 2)

        pygame.draw.circle(surface, PANEL_BORDER, (center, center), outer + 1, 1)
        pygame.draw.circle(surface, PANEL_BORDER, (center, center), inner, 1)
        return surface

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return

        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        panel = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        panel.fill((*PANEL_BG, 235) if len(PANEL_BG) == 3 else PANEL_BG)
        screen.blit(panel, (self.x, self.y))
        pygame.draw.rect(screen, PANEL_BORDER, dialog_rect, 2, border_radius=10)

        self.draw_title_bar(screen, self.title)
        self.draw_text_wrapped(
            screen,
            f"{self.player_name}: pick a color from the wheel.",
            self.x + 14,
            self.y + self.title_bar_height + 10,
            self.width - 28,
            self.font_small,
            TEXT_SECONDARY,
            line_height=18,
        )

        if self._wheel_surface is None:
            self._wheel_surface = self._build_wheel_surface()

        cx, cy = self._wheel_center()
        wheel_rect = self._wheel_surface.get_rect(center=(cx, cy))
        screen.blit(self._wheel_surface, wheel_rect.topleft)

        selected_rgb = self._selected_rgb()
        selected_hue = self._selected_hue
        if selected_hue is not None:
            marker_radius = self._wheel_inner_radius() + (self._wheel_radius - self._wheel_inner_radius()) // 2
            radians = math.radians(float(selected_hue))
            mx = cx + int(math.cos(radians) * marker_radius)
            my = cy - int(math.sin(radians) * marker_radius)
            pygame.draw.circle(screen, (255, 255, 255), (mx, my), 7, 2)
            pygame.draw.circle(screen, (20, 20, 20), (mx, my), 5, 1)

        preview_rect = pygame.Rect(self.x + 190, self.y + self.title_bar_height + 335, 180, 56)
        pygame.draw.rect(screen, selected_rgb, preview_rect, border_radius=8)
        pygame.draw.rect(screen, PANEL_BORDER, preview_rect, 1, border_radius=8)

        hue_text = "--"
        if selected_hue is not None:
            hue_text = f"{int(selected_hue) % 360:03d}"
        info = f"Hue {hue_text}  RGB {selected_rgb[0]}, {selected_rgb[1]}, {selected_rgb[2]}"
        label = self.font_small.render(info, True, TEXT_PRIMARY)
        screen.blit(label, (self.x + (self.width - label.get_width()) // 2, preview_rect.y + 18))

        self.draw_button(screen, "confirm", "Confirm Color", text_color=TEXT_PRIMARY)
        self.draw_button(screen, "cancel", "Cancel", text_color=TEXT_PRIMARY)
