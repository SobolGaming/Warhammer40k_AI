import pygame
from typing import List, Optional, Tuple, Dict, Any

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

        # Cached content surface for responsive scrolling.
        self._cached_content_surface: Optional[pygame.Surface] = None
        self._cached_content_width: int = 0
        self._cached_content_height: int = 0
        self._cached_signature: Optional[Tuple[Any, ...]] = None
        self._cache_built_ms: int = -1
        self._cache_refresh_ms: int = 350
        self._hud_button_rect_content: Optional[pygame.Rect] = None
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
        self._hud_button_rect_content = None
        self._invalidate_cache()

    def hide(self) -> None:
        self.visible = False
        self.scroll_offset = 0
        self.max_scroll = 0
        self.hud = None
        self.highlight_words = []
        self._hud_button_rect = None
        self._hud_on_use = None
        self._hud_enabled = False
        self._hud_button_rect_content = None
        self._invalidate_cache()

    def scroll(self, delta: int) -> None:
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + int(delta)))

    def _invalidate_cache(self) -> None:
        self._cached_content_surface = None
        self._cached_content_width = 0
        self._cached_content_height = 0
        self._cached_signature = None
        self._cache_built_ms = -1
        self._hud_button_rect_content = None

    def _content_signature(self) -> Tuple[Any, ...]:
        hud = self.hud or {}
        hint_val = hud.get("hint", "")
        if callable(hud.get("get_hint")):
            hint_val = "<dynamic>"
        tokens_val = hud.get("tokens", None)
        if callable(hud.get("get_tokens")):
            tokens_val = "<dynamic>"
        enabled_val = hud.get("enabled", None)
        if callable(hud.get("get_enabled")):
            enabled_val = "<dynamic>"
        return (
            self.title,
            self.rule_name,
            self.legend,
            self.description,
            bool(self.supported),
            tuple(self.highlight_words or []),
            bool(self.hud),
            str(hud.get("label", "Tokens")),
            str(hud.get("use_label", "Use Token")),
            bool(hud.get("show_button", True)),
            tuple(hud.get("highlight_words") or []),
            str(hint_val),
            tokens_val,
            enabled_val,
        )

    def _should_rebuild_cache(self, content_width: int) -> bool:
        if self._cached_content_surface is None:
            return True
        if self._cached_content_width != int(content_width):
            return True
        signature = self._content_signature()
        if self._cached_signature != signature:
            return True
        if self.hud:
            now_ms = pygame.time.get_ticks()
            if self._cache_built_ms < 0:
                return True
            return int(now_ms - self._cache_built_ms) >= int(self._cache_refresh_ms)
        return False

    def _ensure_content_cache(self, content_width: int) -> None:
        if not self._should_rebuild_cache(content_width):
            return
        surface, content_height = self._build_content_surface(int(content_width))
        self._cached_content_surface = surface
        self._cached_content_width = int(content_width)
        self._cached_content_height = int(content_height)
        self._cached_signature = self._content_signature()
        self._cache_built_ms = pygame.time.get_ticks()

    def _measure_wrapped_text_height(
        self,
        text: str,
        font: pygame.font.Font,
        max_width: int,
        *,
        paragraph_gap: int = 8,
    ) -> int:
        if not text:
            return 0
        line_height = font.get_linesize() + 2
        total = 0
        for para in str(text).split("\n"):
            if not para.strip():
                total += line_height // 2
                continue
            lines = self.wrap_text(para, font, max_width)
            total += len(lines) * line_height
            total += paragraph_gap
        return total

    def _resolve_hud_values(self, width: int) -> Dict[str, Any]:
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

        text_max_width = max(10, width - 140 if show_button else width - 20)
        on_use = hud.get("on_use") if callable(hud.get("on_use")) else None
        return {
            "tokens": tokens,
            "label": label,
            "use_label": use_label,
            "show_button": show_button,
            "highlight_words": highlight_words,
            "enabled": bool(enabled),
            "hint": hint,
            "text_max_width": text_max_width,
            "on_use": on_use,
        }

    def _measure_hud_height(self, width: int, hud_values: Dict[str, Any]) -> int:
        total = 44 + 6
        hint = str(hud_values.get("hint", "") or "")
        if hint:
            total += self._measure_wrapped_text_height(
                hint,
                self.font_small,
                width,
                paragraph_gap=6,
            )
        return total

    def _build_content_surface(self, content_width: int) -> Tuple[pygame.Surface, int]:
        x_left = 5
        draw_width = max(10, int(content_width) - 10)
        y_pos = 5

        if self.title:
            y_pos += self.font_title.get_linesize() + 6
        if self.rule_name:
            y_pos += self.font_heading.get_linesize() + 4
        if self.supported:
            y_pos += self.font_small.get_linesize() + 6

        hud_values: Optional[Dict[str, Any]] = None
        if self.hud:
            hud_values = self._resolve_hud_values(draw_width)
            y_pos += self._measure_hud_height(draw_width, hud_values)

        if self.legend:
            y_pos += self._measure_wrapped_text_height(
                self.legend,
                self.font_body,
                draw_width,
                paragraph_gap=10,
            )

        if self.description:
            y_pos += self._measure_wrapped_text_height(
                self.description,
                self.font_body,
                draw_width,
                paragraph_gap=10,
            )

        content_height = max(1, int(y_pos + 5))
        content_surface = pygame.Surface((int(content_width), content_height), pygame.SRCALPHA)

        y_draw = 5
        self._hud_button_rect_content = None
        if self.title:
            title_surf = self.font_title.render(self.title, True, TEXT_PRIMARY)
            content_surface.blit(title_surf, (x_left, y_draw))
            y_draw += self.font_title.get_linesize() + 6

        if self.rule_name:
            name_surf = self.font_heading.render(self.rule_name, True, TEXT_ACCENT)
            content_surface.blit(name_surf, (x_left, y_draw))
            y_draw += self.font_heading.get_linesize() + 4

        if self.supported:
            status_surf = self.font_small.render("Status: Supported", True, TEXT_ACCENT)
            content_surface.blit(status_surf, (x_left, y_draw))
            y_draw += self.font_small.get_linesize() + 6

        if self.hud and hud_values is not None:
            y_draw = self._draw_hud(
                content_surface,
                x_left,
                y_draw,
                draw_width,
                hud_values=hud_values,
            )

        if self.legend:
            y_draw = self._draw_wrapped_text(
                content_surface,
                self.legend,
                self.font_body,
                TEXT_SECONDARY,
                x_left,
                y_draw,
                draw_width,
                paragraph_gap=10,
            )

        if self.description:
            y_draw = self._draw_wrapped_text(
                content_surface,
                self.description,
                self.font_body,
                TEXT_SECONDARY,
                x_left,
                y_draw,
                draw_width,
                paragraph_gap=10,
                highlight_words=self.highlight_words,
            )

        return content_surface, content_height

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
        self._ensure_content_cache(content_rect.width)
        self.max_scroll = max(0, int(self._cached_content_height) - content_rect.height)
        self.scroll_offset = max(0, min(self.max_scroll, int(self.scroll_offset)))

        if self._cached_content_surface is not None:
            available = int(self._cached_content_height) - int(self.scroll_offset)
            blit_h = max(0, min(content_rect.height, available))
            if blit_h > 0:
                source_rect = pygame.Rect(0, int(self.scroll_offset), content_rect.width, blit_h)
                surface.blit(self._cached_content_surface, content_rect.topleft, source_rect)

        self._hud_button_rect = None
        if self._hud_button_rect_content is not None:
            mapped = self._hud_button_rect_content.move(content_rect.x, content_rect.y - int(self.scroll_offset))
            if mapped.bottom > content_rect.top and mapped.top < content_rect.bottom:
                self._hud_button_rect = mapped

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

    def _draw_hud(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        width: int,
        *,
        hud_values: Optional[Dict[str, Any]] = None,
    ) -> int:
        values = hud_values or self._resolve_hud_values(width)
        tokens = values.get("tokens")
        label = str(values.get("label", "Tokens"))
        use_label = str(values.get("use_label", "Use Token"))
        show_button = bool(values.get("show_button", True))
        highlight_words = list(values.get("highlight_words") or [])
        enabled = bool(values.get("enabled", False))
        hint = str(values.get("hint", "") or "")
        text_max_width = int(values.get("text_max_width", max(10, width - 20)))
        on_use = values.get("on_use")

        hud_rect = pygame.Rect(x, y, width, 44)
        pygame.draw.rect(surface, HUD_BG, hud_rect, border_radius=6)
        pygame.draw.rect(surface, HUD_BORDER, hud_rect, 1, border_radius=6)

        token_text = f"{label}: {tokens}" if tokens is not None else label
        token_color = TEXT_ACCENT if tokens and tokens > 0 else TEXT_SECONDARY
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
            self._hud_button_rect_content = pygame.Rect(btn_rect)
            self._hud_on_use = on_use if callable(on_use) else None
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
            self._hud_button_rect_content = None
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
