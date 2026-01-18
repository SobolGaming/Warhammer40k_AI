import re
from pathlib import Path
from typing import Optional

import pygame


class PopupOverlayRenderer:
    def __init__(self):
        self.screen = None
        self._vp_history_scroll = 0
        self._vp_history_max_scroll = 0
        self._cp_history_scroll = 0
        self._cp_history_max_scroll = 0
        self._mission_image_surface_cache: dict[str, pygame.Surface] = {}
        self._mission_image_path_cache: dict[str, Optional[str]] = {}

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen

    def reset_vp_scroll(self) -> None:
        self._vp_history_scroll = 0

    def reset_cp_scroll(self) -> None:
        self._cp_history_scroll = 0

    def adjust_vp_scroll(self, delta: int) -> None:
        try:
            self._vp_history_scroll = max(
                0,
                min(
                    self._vp_history_max_scroll,
                    int(self._vp_history_scroll) - int(delta * 24),
                ),
            )
        except Exception:
            self._vp_history_scroll = 0

    def adjust_cp_scroll(self, delta: int) -> None:
        try:
            self._cp_history_scroll = max(
                0,
                min(
                    self._cp_history_max_scroll,
                    int(self._cp_history_scroll) - int(delta * 24),
                ),
            )
        except Exception:
            self._cp_history_scroll = 0

    def find_mission_card_image_path(self, card, is_primary: bool) -> Optional[str]:
        return self._find_mission_card_image_path(card, is_primary)

    def draw_mission_popup(self, title: str, body: str, image_path: Optional[str] = None) -> None:
        if self.screen is None:
            return
        self._draw_mission_popup_overlay(title, body, image_path=image_path)

    def draw_vp_history_popup(self, player) -> None:
        if self.screen is None:
            return
        self._draw_vp_history_popup_overlay(player)

    def draw_cp_history_popup(self, player) -> None:
        if self.screen is None:
            return
        self._draw_cp_history_popup_overlay(player)

    def _slugify_mission_card_name(self, name: str) -> str:
        """
        Convert a mission card name into the expected PNG suffix used under RuleSets mission_cards.
        Examples:
          "Take and Hold" -> "take_and_hold"
          "Purge the Foe" -> "purge_the_foe"
        """
        s = (name or "").strip().lower()
        # Replace common separators with underscores, drop other punctuation.
        s = re.sub(r"[\s\-]+", "_", s)
        s = re.sub(r"[^a-z0-9_]+", "", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s

    def _get_mission_cards_dir(self) -> Path:
        """
        Locate the repo's Chapter Approved 2025/2026 mission card images directory.
        Prefer repo-relative to this source file, but fall back to CWD if needed.
        """
        # src/warhammer40k_ai/UI/game_ui.py -> repo root is parents[3]
        try:
            repo_root = Path(__file__).resolve().parents[3]
        except Exception:
            repo_root = Path.cwd()
        p = repo_root / "RuleSets" / "ChapterApproved_2025_2026" / "mission_cards"
        if p.exists():
            return p
        # Fallback: when running from a different CWD
        p2 = Path.cwd() / "RuleSets" / "ChapterApproved_2025_2026" / "mission_cards"
        return p2

    def _find_mission_card_image_path(self, card, is_primary: bool) -> Optional[str]:
        """
        Returns a filesystem path to a PNG image for the given card if present, else None.
        File naming convention:
          primary_<slug>.png
          secondary_<slug>.png
        """
        if card is None:
            return None
        name = getattr(card, "name", None) or "mission"
        slug = self._slugify_mission_card_name(str(name))
        prefix = "primary" if is_primary else "secondary"
        cache_key = f"{prefix}:{slug}"
        if cache_key in self._mission_image_path_cache:
            return self._mission_image_path_cache[cache_key]

        cards_dir = self._get_mission_cards_dir()
        candidate = cards_dir / f"{prefix}_{slug}.png"
        path_str = str(candidate) if candidate.exists() else None
        self._mission_image_path_cache[cache_key] = path_str
        return path_str

    def _load_image_surface_cached(self, image_path: str) -> Optional[pygame.Surface]:
        if not image_path:
            return None
        if image_path in self._mission_image_surface_cache:
            return self._mission_image_surface_cache[image_path]
        # pygame.image.load can raise if file is missing/corrupt; let caller handle it.
        surf = pygame.image.load(image_path).convert_alpha()
        self._mission_image_surface_cache[image_path] = surf
        return surf

    def _draw_mission_popup_overlay(self, title: str, body: str, image_path: Optional[str] = None) -> None:
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        # Slightly larger to fit mission card images comfortably.
        width = int(screen_w * 0.62)
        height = int(screen_h * 0.78)
        img = None
        scaled_img = None
        image_size = None
        if image_path:
            try:
                img = self._load_image_surface_cached(image_path)
            except Exception:
                img = None
        if img is not None:
            iw, ih = img.get_width(), img.get_height()
            if iw > 0 and ih > 0:
                # Keep the popup tight to the image for mission card art.
                outer_margin = 24
                inner_pad = 16
                header_h = 56
                hint_h = 36
                max_img_w = max(1, screen_w - (outer_margin * 2) - (inner_pad * 2))
                max_img_h = max(1, screen_h - (outer_margin * 2) - header_h - hint_h)
                scale = min(1.0, max_img_w / iw, max_img_h / ih)
                new_w = max(1, int(iw * scale))
                new_h = max(1, int(ih * scale))
                width = new_w + (inner_pad * 2)
                height = new_h + header_h + hint_h
                image_size = (new_w, new_h)
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (screen_w // 2, screen_h // 2)
        pygame.draw.rect(self.screen, (35,35,38), rect)
        pygame.draw.rect(self.screen, (90,90,100), rect, 2)
        try:
            title_font = pygame.font.SysFont('Arial', 18, bold=True)
            body_font = pygame.font.SysFont('Arial', 16)
            hint_font = pygame.font.SysFont('Arial', 14)
        except Exception:
            title_font = pygame.font.Font(None, 18)
            body_font = pygame.font.Font(None, 16)
            hint_font = pygame.font.Font(None, 14)
        ts = title_font.render(title, True, (255,255,255))
        tr = ts.get_rect(center=(rect.centerx, rect.y + 28))
        self.screen.blit(ts, tr)

        # Content area (below title; above hint)
        content_rect = pygame.Rect(rect.x + 16, rect.y + 56, rect.width - 32, rect.height - 56 - 36)

        # If an image is available, show it instead of text.
        if image_path:
            try:
                if img is not None:
                    iw, ih = img.get_width(), img.get_height()
                    if iw > 0 and ih > 0:
                        if image_size:
                            new_w, new_h = image_size
                        else:
                            scale = min(content_rect.width / iw, content_rect.height / ih)
                            new_w = max(1, int(iw * scale))
                            new_h = max(1, int(ih * scale))
                        if (new_w, new_h) != (iw, ih):
                            scaled_img = pygame.transform.smoothscale(img, (new_w, new_h))
                        else:
                            scaled_img = img
                        dest = scaled_img.get_rect(center=content_rect.center)
                        self.screen.blit(scaled_img, dest)
                        hint = hint_font.render("Click anywhere to close", True, (180, 180, 180))
                        self.screen.blit(hint, (rect.x + 16, rect.bottom - 28))
                        return
            except Exception:
                # Fall back to text rendering below.
                pass

        # Fallback: simple wrapped text
        x = content_rect.x
        y = content_rect.y
        max_w = content_rect.width
        line = ''
        for word in (body or '').split(' '):
            test = (line + ' ' + word).strip()
            surf = body_font.render(test, True, (220,220,220))
            if surf.get_width() > max_w and line:
                ls = body_font.render(line, True, (220,220,220))
                self.screen.blit(ls, (x, y))
                y += ls.get_height() + 4
                line = word
            else:
                line = test
        if line:
            ls = body_font.render(line, True, (220,220,220))
            self.screen.blit(ls, (x, y))
        hint = hint_font.render("Click anywhere to close", True, (180, 180, 180))
        self.screen.blit(hint, (rect.x + 16, rect.bottom - 28))

    def _wrap_text_lines(
        self,
        text: str,
        font: pygame.font.Font,
        max_width: int,
        *,
        first_prefix: str = "",
        next_prefix: str = "",
    ) -> list[str]:
        words = str(text or "").split()
        if not words:
            return [first_prefix.rstrip()]
        lines: list[str] = []
        prefix = first_prefix
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if font.size(f"{prefix}{test}")[0] <= max_width:
                line = test
                continue
            if line:
                lines.append(f"{prefix}{line}")
            else:
                lines.append(f"{prefix}{test}")
                test = ""
            prefix = next_prefix
            line = word if test != "" else ""
        if line:
            lines.append(f"{prefix}{line}")
        return lines

    def _draw_vp_history_popup_overlay(self, player) -> None:
        if player is None:
            return
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        width = int(screen_w * 0.64)
        height = int(screen_h * 0.72)
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (screen_w // 2, screen_h // 2)
        pygame.draw.rect(self.screen, (35,35,38), rect)
        pygame.draw.rect(self.screen, (90,90,100), rect, 2)

        try:
            title_font = pygame.font.SysFont('Arial', 18, bold=True)
            body_font = pygame.font.SysFont('Arial', 14)
            hint_font = pygame.font.SysFont('Arial', 12)
        except Exception:
            title_font = pygame.font.Font(None, 18)
            body_font = pygame.font.Font(None, 14)
            hint_font = pygame.font.Font(None, 12)

        title = f"VP History - {getattr(player, 'name', 'Player')}"
        ts = title_font.render(title, True, (255,255,255))
        tr = ts.get_rect(center=(rect.centerx, rect.y + 26))
        self.screen.blit(ts, tr)

        content_rect = pygame.Rect(rect.x + 16, rect.y + 48, rect.width - 32, rect.height - 48 - 28)

        entries = list(reversed(getattr(player, "vp_history", []) or []))
        lines: list[str] = []
        if not entries:
            lines.append("No VP scored yet.")
        else:
            for entry in entries:
                round_val = entry.get("round") or 0
                phase = entry.get("phase") or "Unknown Phase"
                timing = entry.get("timing")
                when = f"Round {round_val} - {phase}"
                if timing:
                    when = f"{when} ({timing})"
                lines.extend(self._wrap_text_lines(when, body_font, content_rect.width, first_prefix="When: ", next_prefix="      "))

                source = str(entry.get("source") or "").lower()
                card_name = entry.get("card_name")
                if source == "primary":
                    label = "Primary"
                elif source == "secondary":
                    label = "Secondary"
                elif source in ("battle_ready", "battleready", "battle-ready"):
                    label = "Battle Ready"
                else:
                    label = source.title() if source else "VP"
                if card_name:
                    if label in ("Primary", "Secondary"):
                        label = f"{label}: {card_name}"
                    else:
                        label = f"{label} ({card_name})"
                what = f"{entry.get('awarded', 0)} VP - {label}"
                lines.extend(self._wrap_text_lines(what, body_font, content_rect.width, first_prefix="What: ", next_prefix="      "))

                detail_lines = []
                details = entry.get("details")
                if details:
                    if isinstance(details, list):
                        detail_lines = [str(d).strip() for d in details if str(d).strip()]
                    else:
                        detail_lines = [d.strip() for d in str(details).splitlines() if d.strip()]
                else:
                    scoring_text = entry.get("card_scoring_text")
                    if scoring_text:
                        detail_lines = [d.strip() for d in str(scoring_text).splitlines() if d.strip()]
                if detail_lines:
                    for i, detail in enumerate(detail_lines):
                        if i == 0:
                            lines.extend(self._wrap_text_lines(detail, body_font, content_rect.width, first_prefix="Why: ", next_prefix="     "))
                        else:
                            lines.extend(self._wrap_text_lines(detail, body_font, content_rect.width, first_prefix="     ", next_prefix="     "))
                lines.append("")

        line_height = body_font.get_height() + 4
        total_height = len(lines) * line_height
        self._vp_history_max_scroll = max(0, total_height - content_rect.height)
        self._vp_history_scroll = max(0, min(self._vp_history_scroll, self._vp_history_max_scroll))
        y = content_rect.y - self._vp_history_scroll
        for line in lines:
            if y + line_height < content_rect.y:
                y += line_height
                continue
            if y > content_rect.bottom:
                break
            if line:
                surf = body_font.render(line, True, (220,220,220))
                self.screen.blit(surf, (content_rect.x, y))
            y += line_height

        hint = hint_font.render("Mouse wheel to scroll, click to close", True, (180, 180, 180))
        self.screen.blit(hint, (rect.x + 16, rect.bottom - 22))

    def _draw_cp_history_popup_overlay(self, player) -> None:
        if player is None:
            return
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        width = int(screen_w * 0.64)
        height = int(screen_h * 0.72)
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (screen_w // 2, screen_h // 2)
        pygame.draw.rect(self.screen, (35,35,38), rect)
        pygame.draw.rect(self.screen, (90,90,100), rect, 2)

        try:
            title_font = pygame.font.SysFont('Arial', 18, bold=True)
            body_font = pygame.font.SysFont('Arial', 14)
            hint_font = pygame.font.SysFont('Arial', 12)
        except Exception:
            title_font = pygame.font.Font(None, 18)
            body_font = pygame.font.Font(None, 14)
            hint_font = pygame.font.Font(None, 12)

        title = f"CP History - {getattr(player, 'name', 'Player')} (Current: {int(getattr(player, 'command_points', 0) or 0)})"
        ts = title_font.render(title, True, (255,255,255))
        tr = ts.get_rect(center=(rect.centerx, rect.y + 26))
        self.screen.blit(ts, tr)

        content_rect = pygame.Rect(rect.x + 16, rect.y + 48, rect.width - 32, rect.height - 48 - 28)

        entries = list(reversed(getattr(player, "cp_history", []) or []))
        lines: list[str] = []
        if not entries:
            lines.append("No CP changes yet.")
        else:
            for entry in entries:
                round_val = entry.get("round") or 0
                phase = entry.get("phase") or "Unknown Phase"
                when = f"Round {round_val} - {phase}"
                lines.extend(self._wrap_text_lines(when, body_font, content_rect.width, first_prefix="When: ", next_prefix="      "))

                delta = int(entry.get("delta") or 0)
                sign = "+" if delta >= 0 else "-"
                current = entry.get("current")
                if current is None:
                    current = int(getattr(player, "command_points", 0) or 0)
                what = f"{sign}{abs(delta)} CP (Current: {current})"
                lines.extend(self._wrap_text_lines(what, body_font, content_rect.width, first_prefix="What: ", next_prefix="      "))

                reason = entry.get("reason")
                if not reason:
                    src = entry.get("source")
                    if src and str(src).lower() not in ("gain", "spend"):
                        reason = str(src)
                if reason:
                    lines.extend(self._wrap_text_lines(str(reason), body_font, content_rect.width, first_prefix="Why: ", next_prefix="     "))
                else:
                    lines.append("Why: (unspecified)")
                lines.append("")

        line_height = body_font.get_height() + 4
        total_height = len(lines) * line_height
        self._cp_history_max_scroll = max(0, total_height - content_rect.height)
        self._cp_history_scroll = max(0, min(self._cp_history_scroll, self._cp_history_max_scroll))
        y = content_rect.y - self._cp_history_scroll
        for line in lines:
            if y + line_height < content_rect.y:
                y += line_height
                continue
            if y > content_rect.bottom:
                break
            if line:
                surf = body_font.render(line, True, (220,220,220))
                self.screen.blit(surf, (content_rect.x, y))
            y += line_height

        hint = hint_font.render("Mouse wheel to scroll, click to close", True, (180, 180, 180))
        self.screen.blit(hint, (rect.x + 16, rect.bottom - 22))
