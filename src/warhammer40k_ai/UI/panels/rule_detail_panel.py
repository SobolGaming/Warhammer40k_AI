import pygame
from typing import List, Optional

# Font sizes
FONT_TITLE = 22
FONT_HEADING = 18
FONT_BODY = 16
FONT_SMALL = 14

# Colors (match unit detail styling)
PANEL_BG = (45, 45, 48)
PANEL_BORDER = (63, 63, 70)
TEXT_PRIMARY = (255, 255, 255)
TEXT_SECONDARY = (200, 200, 200)
TEXT_ACCENT = (100, 149, 237)
DARK_GREY = (40, 40, 40)


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
        self.scroll_offset = 0
        self.max_scroll = 0
        self.rect: Optional[pygame.Rect] = None
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

    def set_content(self, title: str, rule_name: str, legend: str, description: str, *, supported: bool = False) -> None:
        self.title = title or ""
        self.rule_name = rule_name or ""
        self.legend = legend or ""
        self.description = description or ""
        self.supported = bool(supported)
        self.scroll_offset = 0
        self.max_scroll = 0
        self.visible = True

    def hide(self) -> None:
        self.visible = False
        self.scroll_offset = 0
        self.max_scroll = 0

    def scroll(self, delta: int) -> None:
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + int(delta)))

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
    ) -> int:
        if not text:
            return y
        line_height = font.get_linesize() + 2
        for para in str(text).split("\n"):
            if not para.strip():
                y += line_height // 2
                continue
            for line in self.wrap_text(para, font, max_width):
                surf = font.render(line, True, color)
                surface.blit(surf, (x, y))
                y += line_height
            y += paragraph_gap
        return y
