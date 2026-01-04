import pygame
from typing import List, Optional

# Font sizes
FONT_TITLE = 22
FONT_HEADING = 20
FONT_BODY = 18
FONT_SMALL = 14

# Colors (match unit detail styling)
PANEL_BG = (45, 45, 48)
PANEL_BORDER = (63, 63, 70)
TEXT_PRIMARY = (255, 255, 255)
TEXT_SECONDARY = (200, 200, 200)
TEXT_ACCENT = (100, 149, 237)
DARK_GREY = (40, 40, 40)
GOLD = (212, 175, 55)
HUD_BG = (35, 35, 40)
HUD_BORDER = (80, 80, 90)
HUD_BUTTON_BG = (70, 120, 200)
HUD_BUTTON_BG_DISABLED = (55, 55, 60)


class RuleDetailPanel(pygame.sprite.Sprite):
    """Scrollable panel to display Army/Detachment rules."""

    def __init__(self, width: int = 520, height: int = 520):
        super().__init__()
        self.width = width
        self.height = height
        self.visible = False
        self.title: str = ""
        self.rule_name: str = ""
        self.legend: str = ""
        self.description: str = ""
        self.supported = False
        self.hud: Optional[dict] = None
        self.highlight_words: List[str] = []
        self.scroll_offset = 0
        self.max_scroll = 0
        self.rect: Optional[pygame.Rect] = None
        self._hud_button_rect: Optional[pygame.Rect] = None
        self._hud_on_use = None
        self._hud_enabled = False
        self._init_fonts()

    def _init_fonts(self) -> None:
        try:
            candidates = [
                "Segoe UI Variable",
                "Segoe UI",
                "Inter",
                "Roboto",
                "Helvetica Neue",
                "Helvetica",
                "Arial",
            ]

            def _font(size: int, bold: bool) -> pygame.font.Font:
                try:
                    path = pygame.font.match_font(candidates, bold=bold)
                    if path:
                        return pygame.font.Font(path, size)
                except Exception:
                    pass
                try:
                    return pygame.font.SysFont(candidates, size, bold=bold)
                except Exception:
                    return pygame.font.Font(None, size)

            self.font_title = _font(FONT_TITLE, bold=True)
            self.font_heading = _font(FONT_HEADING, bold=True)
            self.font_body = _font(FONT_BODY, bold=False)
            self.font_small = _font(FONT_SMALL, bold=False)
        except Exception:
            self.font_title = pygame.font.Font(None, FONT_TITLE)
            self.font_heading = pygame.font.Font(None, FONT_HEADING)
            self.font_body = pygame.font.Font(None, FONT_BODY)
            self.font_small = pygame.font.Font(None, FONT_SMALL)

    def set_content(
        self,
        title: str,
        rule_name: str,
        legend: str,
        description: str,
        *,
        supported: bool = False,
        hud: Optional[dict] = None,
        highlight_words: Optional[List[str]] = None,
    ) -> None:
        self.title = title or ""
        self.rule_name = rule_name or ""
        self.legend = legend or ""
        self.description = description or ""
        self.supported = bool(supported)
        self.hud = hud
        self.highlight_words = list(highlight_words or [])
        self.scroll_offset = 0
        self.max_scroll = 0
        self.visible = True
        self._hud_button_rect = None
        self._hud_on_use = None
        self._hud_enabled = False

    def hide(self) -> None:
        self.visible = False
        self.scroll_offset = 0
        self.max_scroll = 0
        self.hud = None
        self.highlight_words = []
        self._hud_button_rect = None
        self._hud_on_use = None
        self._hud_enabled = False

    def scroll(self, delta: int) -> None:
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + int(delta)))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hud_button_rect and self._hud_button_rect.collidepoint(event.pos):
                if self._hud_enabled and callable(self._hud_on_use):
                    self._hud_on_use()
                return True
        return False

    def draw(self, surface: pygame.Surface, x: int, y: int) -> None:
        if not self.visible:
            return

        screen_width, screen_height = surface.get_size()
        if x + self.width > screen_width:
            x = max(10, screen_width - self.width - 10)
        if y + self.height > screen_height:
            y = max(10, screen_height - self.height - 10)

        self.rect = pygame.Rect(x, y, self.width, self.height)
        shadow_rect = pygame.Rect(x + 3, y + 3, self.width, self.height)
        pygame.draw.rect(surface, (0, 0, 0), shadow_rect, border_radius=8)
        pygame.draw.rect(surface, PANEL_BG, self.rect, border_radius=8)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 2, border_radius=8)

        content_rect = pygame.Rect(x + 10, y + 10, self.width - 20, self.height - 20)
        surface.set_clip(content_rect)

        y_pos = y + 15 - self.scroll_offset
        x_left = x + 15

        if self.title:
            title_surf = self.font_title.render(self.title, True, TEXT_PRIMARY)
            surface.blit(title_surf, (x_left, y_pos))
            y_pos += self.font_title.get_linesize() + 6

        if self.rule_name:
            name_surf = self.font_heading.render(self.rule_name, True, TEXT_ACCENT)
            surface.blit(name_surf, (x_left, y_pos))
            y_pos += self.font_heading.get_linesize() + 4

        if self.supported:
            status_surf = self.font_small.render("Status: Supported", True, TEXT_ACCENT)
            surface.blit(status_surf, (x_left, y_pos))
            y_pos += self.font_small.get_linesize() + 6

        if self.hud:
            y_pos = self._draw_hud(surface, x_left, y_pos, self.width - 40)

        if self.legend:
            y_pos = self._draw_wrapped_text(
                surface,
                self.legend,
                self.font_body,
                TEXT_SECONDARY,
                x_left,
                y_pos,
                self.width - 40,
                paragraph_gap=10,
            )

        if self.description:
            y_pos = self._draw_wrapped_text(
                surface,
                self.description,
                self.font_body,
                TEXT_SECONDARY,
                x_left,
                y_pos,
                self.width - 40,
                paragraph_gap=10,
                highlight_words=self.highlight_words,
            )

        total_content_height = y_pos - (y + 15) + self.scroll_offset
        self.max_scroll = max(0, total_content_height - (self.height - 30))

        surface.set_clip(None)
        if self.max_scroll > 0:
            self.draw_scroll_indicator(surface, x, y)

    def draw_scroll_indicator(self, surface: pygame.Surface, x: int, y: int) -> None:
        if self.max_scroll <= 0:
            return
        scrollbar_x = x + self.width - 15
        scrollbar_y = y + 10
        scrollbar_height = self.height - 20
        scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, 10, scrollbar_height)
        pygame.draw.rect(surface, DARK_GREY, scrollbar_rect, border_radius=5)

        thumb_height = max(20, int(scrollbar_height * (self.height - 30) / (self.max_scroll + self.height - 30)))
        thumb_y = scrollbar_y + int((scrollbar_height - thumb_height) * (self.scroll_offset / self.max_scroll))
        thumb_rect = pygame.Rect(scrollbar_x + 1, thumb_y, 8, thumb_height)
        pygame.draw.rect(surface, TEXT_SECONDARY, thumb_rect, border_radius=4)

    def _draw_hud(self, surface: pygame.Surface, x: int, y: int, width: int) -> int:
        hud = self.hud or {}
        get_tokens = hud.get("get_tokens")
        tokens = None
        if callable(get_tokens):
            try:
                tokens = int(get_tokens() or 0)
            except Exception:
                tokens = None
        label = str(hud.get("label", "Tokens"))
        use_label = str(hud.get("use_label", "Use Token"))
        show_button = bool(hud.get("show_button", True))
        highlight_words = list(hud.get("highlight_words") or [])

        enabled = True
        get_enabled = hud.get("get_enabled")
        if callable(get_enabled):
            try:
                enabled = bool(get_enabled())
            except Exception:
                enabled = False

        hint = ""
        get_hint = hud.get("get_hint")
        if callable(get_hint):
            try:
                hint = str(get_hint() or "")
            except Exception:
                hint = ""
        else:
            hint = str(hud.get("hint", "") or "")

        hud_rect = pygame.Rect(x, y, width, 44)
        pygame.draw.rect(surface, HUD_BG, hud_rect, border_radius=6)
        pygame.draw.rect(surface, HUD_BORDER, hud_rect, 1, border_radius=6)

        token_text = f"{label}: {tokens}" if tokens is not None else label
        token_color = TEXT_ACCENT if tokens and tokens > 0 else TEXT_SECONDARY
        text_max_width = max(10, width - 140 if show_button else width - 20)
        token_lines = self.wrap_text(token_text, self.font_body, text_max_width)
        token_line = token_lines[0] if token_lines else token_text
        token_surf = self.font_body.render(token_line, True, token_color)
        surface.blit(
            token_surf,
            (hud_rect.x + 10, hud_rect.y + (hud_rect.height - token_surf.get_height()) // 2),
        )

        if show_button:
            btn_w = max(90, min(140, width // 3))
            btn_rect = pygame.Rect(hud_rect.right - btn_w - 10, hud_rect.y + 6, btn_w, hud_rect.height - 12)
            self._hud_button_rect = btn_rect
            self._hud_on_use = hud.get("on_use") if callable(hud.get("on_use")) else None
            self._hud_enabled = bool(enabled)
            btn_bg = HUD_BUTTON_BG if enabled else HUD_BUTTON_BG_DISABLED
            pygame.draw.rect(surface, btn_bg, btn_rect, border_radius=5)
            pygame.draw.rect(surface, HUD_BORDER, btn_rect, 1, border_radius=5)
            btn_color = TEXT_PRIMARY if enabled else TEXT_SECONDARY
            btn_surf = self.font_small.render(use_label, True, btn_color)
            surface.blit(
                btn_surf,
                (btn_rect.centerx - btn_surf.get_width() // 2, btn_rect.centery - btn_surf.get_height() // 2),
            )
        else:
            self._hud_button_rect = None
            self._hud_on_use = None
            self._hud_enabled = False

        y_next = hud_rect.bottom + 6
        if hint:
            y_next = self._draw_wrapped_text(
                surface,
                hint,
                self.font_small,
                TEXT_SECONDARY,
                x,
                y_next,
                width,
                paragraph_gap=6,
                highlight_words=highlight_words,
            )
        return y_next

    def wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> List[str]:
        words = text.split(' ')
        lines: List[str] = []
        current_line = ""
        for word in words:
            test_line = current_line + word + " "
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line.strip())
                    current_line = word + " "
                else:
                    lines.append(word)
                    current_line = ""
        if current_line:
            lines.append(current_line.strip())
        return lines

    def _draw_wrapped_text(
        self,
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: tuple,
        x: int,
        y: int,
        max_width: int,
        *,
        paragraph_gap: int = 8,
        highlight_words: Optional[List[str]] = None,
    ) -> int:
        if not text:
            return y
        line_height = font.get_linesize() + 2
        highlights = [w for w in (highlight_words or []) if str(w or "").strip()]
        highlight_tokens = [str(w).strip() for w in highlights]
        for para in str(text).split("\n"):
            if not para.strip():
                y += line_height // 2
                continue
            for line in self.wrap_text(para, font, max_width):
                if highlight_tokens and self._line_has_highlight(line, highlight_tokens):
                    y = self._draw_highlighted_line(
                        surface,
                        line,
                        font,
                        color,
                        highlight_tokens,
                        GOLD,
                        x,
                        y,
                        line_height,
                    )
                else:
                    surf = font.render(line, True, color)
                    surface.blit(surf, (x, y))
                    y += line_height
            y += paragraph_gap
        return y

    def _line_has_highlight(self, line: str, highlights: List[str]) -> bool:
        line_l = str(line or "").lower()
        for word in highlights:
            if str(word or "").lower() in line_l:
                return True
        return False

    def _draw_highlighted_line(
        self,
        surface: pygame.Surface,
        line: str,
        font: pygame.font.Font,
        base_color: tuple,
        highlights: List[str],
        highlight_color: tuple,
        x: int,
        y: int,
        line_height: int,
    ) -> int:
        line_str = str(line or "")
        line_lower = line_str.lower()
        tokens = [str(w).lower() for w in highlights]

        idx = 0
        x_cursor = x
        while idx < len(line_str):
            best_pos = None
            best_token = None
            for token in tokens:
                if not token:
                    continue
                pos = line_lower.find(token, idx)
                if pos == -1:
                    continue
                if best_pos is None or pos < best_pos or (pos == best_pos and len(token) > len(best_token or "")):
                    best_pos = pos
                    best_token = token

            if best_pos is None or best_token is None:
                seg = line_str[idx:]
                if seg:
                    surf = font.render(seg, True, base_color)
                    surface.blit(surf, (x_cursor, y))
                    x_cursor += surf.get_width()
                break

            if best_pos > idx:
                seg = line_str[idx:best_pos]
                surf = font.render(seg, True, base_color)
                surface.blit(surf, (x_cursor, y))
                x_cursor += surf.get_width()

            seg = line_str[best_pos:best_pos + len(best_token)]
            surf = font.render(seg, True, highlight_color)
            surface.blit(surf, (x_cursor, y))
            x_cursor += surf.get_width()
            idx = best_pos + len(best_token)

        return y + line_height
