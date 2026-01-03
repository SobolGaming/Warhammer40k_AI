"""
StratagemPane component for displaying phase-available stratagems.
"""

from typing import Dict, List, Any, Optional
import pygame

# Font sizes
FONT_TITLE = 18
FONT_MAIN = 14
FONT_SMALL = 12

# UI Colors
PANEL_BG = (45, 45, 48)
PANEL_BORDER = (63, 63, 70)
BUTTON_BG = (60, 60, 67)
BUTTON_DISABLED = (40, 40, 40)
TEXT_PRIMARY = (255, 255, 255)
TEXT_SECONDARY = (200, 200, 200)
TEXT_DISABLED = (120, 120, 120)

COLOR_YOUR_TURN = (0, 122, 204)     # Blue
COLOR_OPPONENT = (200, 70, 70)      # Red
COLOR_EITHER = (60, 160, 90)        # Green


class StratagemPane(pygame.sprite.Sprite):
    def __init__(self, left: int, top: int, width: int, height: int, player_name: str):
        super().__init__()
        self.rect = pygame.Rect(left, top, width, height)
        self.player_name = player_name
        self.player = None
        self.items: List[Dict[str, Any]] = []
        self.scroll_offset = 0
        self.max_scroll = 0
        self.header_height = 52
        self.row_height = 66

        try:
            self.font_title = pygame.font.SysFont("Arial", FONT_TITLE, bold=True)
            self.font_main = pygame.font.SysFont("Arial", FONT_MAIN, bold=False)
            self.font_small = pygame.font.SysFont("Arial", FONT_SMALL, bold=False)
        except Exception:
            self.font_title = pygame.font.Font(None, FONT_TITLE)
            self.font_main = pygame.font.Font(None, FONT_MAIN)
            self.font_small = pygame.font.Font(None, FONT_SMALL)

    def update_rect(self, left: int, top: int, width: int, height: int) -> None:
        self.rect.update(left, top, width, height)
        self._recompute_scroll()

    def set_items(self, items: List[Dict[str, Any]]) -> None:
        self.items = list(items or [])
        self._recompute_scroll()

    def scroll(self, delta: int) -> None:
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + int(delta)))

    def _recompute_scroll(self) -> None:
        content_height = self.header_height + (len(self.items) * self.row_height) + 12
        self.max_scroll = max(0, content_height - self.rect.height)
        if self.scroll_offset > self.max_scroll:
            self.scroll_offset = self.max_scroll

    def _truncate(self, text: str, font: pygame.font.Font, max_width: int) -> str:
        if not text:
            return ""
        try:
            if font.size(text)[0] <= max_width:
                return text
            ell = "..."
            lo, hi = 0, len(text)
            best = ell
            while lo <= hi:
                mid = (lo + hi) // 2
                candidate = text[:mid].rstrip() + ell
                if font.size(candidate)[0] <= max_width:
                    best = candidate
                    lo = mid + 1
                else:
                    hi = mid - 1
            return best
        except Exception:
            return text

    def _border_color(self, category: str) -> tuple:
        if category == "opponent":
            return COLOR_OPPONENT
        if category == "either":
            return COLOR_EITHER
        return COLOR_YOUR_TURN

    def draw(self, surface: pygame.Surface, hitboxes: Optional[Dict[str, Any]] = None, key_prefix: str = "") -> None:
        pygame.draw.rect(surface, PANEL_BG, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 2)

        title = "Stratagems"
        subtitle = self.player_name or "Player"
        title_surf = self.font_title.render(title, True, TEXT_PRIMARY)
        subtitle_surf = self.font_small.render(subtitle, True, TEXT_SECONDARY)

        title_rect = title_surf.get_rect(centerx=self.rect.centerx)
        title_rect.y = self.rect.y + 8
        subtitle_rect = subtitle_surf.get_rect(centerx=self.rect.centerx)
        subtitle_rect.y = title_rect.bottom + 2
        surface.blit(title_surf, title_rect)
        surface.blit(subtitle_surf, subtitle_rect)

        list_top = self.rect.y + self.header_height
        list_rect = pygame.Rect(self.rect.x + 6, list_top, self.rect.width - 12, self.rect.height - self.header_height - 8)
        pygame.draw.rect(surface, (50, 50, 55), list_rect)
        pygame.draw.rect(surface, (90, 90, 100), list_rect, 1)

        clip_prev = surface.get_clip()
        surface.set_clip(list_rect)

        y_cursor = list_rect.y + 6 - self.scroll_offset
        for idx, item in enumerate(self.items):
            row_rect = pygame.Rect(list_rect.x + 6, y_cursor, list_rect.width - 12, self.row_height)
            y_cursor += self.row_height + 6
            if row_rect.bottom < list_rect.top or row_rect.top > list_rect.bottom:
                continue

            available = bool(item.get("available", False))
            category = str(item.get("turn_category", "your"))
            border = self._border_color(category)
            fill = BUTTON_BG if not available else (min(border[0] + 40, 255), min(border[1] + 40, 255), min(border[2] + 40, 255))
            if not available:
                fill = BUTTON_DISABLED

            pygame.draw.rect(surface, fill, row_rect)
            pygame.draw.rect(surface, border, row_rect, 2)

            name = str(item.get("name", "Stratagem"))
            cp_cost = int(item.get("cp_cost", 0) or 0)
            time_left = item.get("time_left", None)
            reason = str(item.get("reason") or "")
            target_label = str(item.get("target_label") or "")
            trigger_label = str(item.get("trigger_label") or "")

            top_y = row_rect.y + 6
            left_x = row_rect.x + 8
            right_x = row_rect.right - 8

            name_text = self._truncate(name, self.font_main, row_rect.width - 80)
            name_surf = self.font_main.render(name_text, True, TEXT_PRIMARY if available else TEXT_DISABLED)
            surface.blit(name_surf, (left_x, top_y))

            cp_text = f"{cp_cost}CP"
            cp_surf = self.font_small.render(cp_text, True, TEXT_SECONDARY)
            cp_rect = cp_surf.get_rect()
            cp_rect.topright = (right_x, top_y + 2)
            surface.blit(cp_surf, cp_rect)

            if time_left is not None:
                timer_text = f"{time_left:.1f}s"
                timer_surf = self.font_small.render(timer_text, True, TEXT_SECONDARY)
                timer_rect = timer_surf.get_rect()
                timer_rect.topright = (right_x, top_y + 20)
                surface.blit(timer_surf, timer_rect)

            if available:
                detail = target_label or trigger_label
            else:
                detail = reason

            detail = self._truncate(detail, self.font_small, row_rect.width - 16)
            detail_surf = self.font_small.render(detail, True, TEXT_SECONDARY if available else TEXT_DISABLED)
            surface.blit(detail_surf, (left_x, top_y + 24))

            if target_label and trigger_label and available:
                extra = self._truncate(trigger_label, self.font_small, row_rect.width - 16)
                extra_surf = self.font_small.render(extra, True, TEXT_SECONDARY)
                surface.blit(extra_surf, (left_x, top_y + 40))

            if available and hitboxes is not None:
                hitboxes[f"strat_item_{key_prefix}_{idx}"] = (pygame.Rect(row_rect), item)

        surface.set_clip(clip_prev)
