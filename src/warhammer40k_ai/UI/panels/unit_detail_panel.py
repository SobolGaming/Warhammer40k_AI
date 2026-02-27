import pygame
from typing import List, Tuple
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id
from ..ui_utils import draw_aspect_shrine_token_icon

# Font sizes
FONT_LARGE = 20
FONT_MEDIUM = 16
FONT_SMALL = 14
FONT_TINY = 12

# Enhanced Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_ACCENT = (100, 149, 237)  # Accent text
DARK_GREY = (40, 40, 40)


class UnitDetailPanel(pygame.sprite.Sprite):
    """Detailed unit information panel that appears when hovering over units"""

    def __init__(self, width=500, height=600):
        super().__init__()
        self.width = width
        self.height = height
        self.visible = True  # Add visible attribute
        try:
            self.font_large = pygame.font.SysFont("Arial", FONT_LARGE, bold=True)
            self.font_medium = pygame.font.SysFont("Arial", FONT_MEDIUM, bold=True)
            self.font_small = pygame.font.SysFont("Arial", FONT_SMALL, bold=False)
            self.font_tiny = pygame.font.SysFont("Arial", FONT_TINY, bold=False)
        except Exception:
            self.font_large = pygame.font.Font(None, FONT_LARGE)
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
            self.font_tiny = pygame.font.Font(None, FONT_TINY)
        self.background_color = PANEL_BG
        self.border_color = PANEL_BORDER
        self.scroll_offset = 0
        self.max_scroll = 0
        self.rect = None

        # Cached content surface for responsive scrolling.
        self._cached_unit = None
        self._cached_root = None
        self._cached_content_width = 0
        self._cached_content_surface = None
        self._cached_content_height = 0
        self._cache_built_ms = -1
        self._cache_refresh_ms = 500

    def invalidate_cache(self):
        self._cached_unit = None
        self._cached_root = None
        self._cached_content_width = 0
        self._cached_content_surface = None
        self._cached_content_height = 0
        self._cache_built_ms = -1

    def scroll(self, delta):
        """Handle scrolling in the unit detail panel"""
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + int(delta)))

    def _should_rebuild_cache(self, unit: Unit, root: Unit, content_width: int) -> bool:
        if self._cached_content_surface is None:
            return True
        if self._cached_content_width != int(content_width):
            return True
        if self._cached_unit is not unit or self._cached_root is not root:
            return True
        now_ms = pygame.time.get_ticks()
        if self._cache_built_ms < 0:
            return True
        return int(now_ms - self._cache_built_ms) >= int(self._cache_refresh_ms)

    def _ensure_content_cache(self, unit: Unit, root: Unit, content_width: int) -> None:
        if not self._should_rebuild_cache(unit, root, content_width):
            return
        surface, height = self._build_content_surface(unit, root, int(content_width))
        self._cached_content_surface = surface
        self._cached_content_height = int(height)
        self._cached_content_width = int(content_width)
        self._cached_unit = unit
        self._cached_root = root
        self._cache_built_ms = pygame.time.get_ticks()

    def draw(self, surface: pygame.Surface, unit: Unit, x: int, y: int):
        """Draw detailed unit information at the specified position"""
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit

        screen_width, screen_height = surface.get_size()
        if x + self.width > screen_width:
            x = screen_width - self.width - 10
        if y + self.height > screen_height:
            y = screen_height - self.height - 10

        self.rect = pygame.Rect(x, y, self.width, self.height)

        shadow_rect = pygame.Rect(x + 3, y + 3, self.width, self.height)
        pygame.draw.rect(surface, (0, 0, 0, 100), shadow_rect, border_radius=8)
        pygame.draw.rect(surface, self.background_color, self.rect, border_radius=8)
        pygame.draw.rect(surface, self.border_color, self.rect, 2, border_radius=8)

        content_rect = pygame.Rect(x + 10, y + 10, self.width - 20, self.height - 20)
        self._ensure_content_cache(unit, root, content_rect.width)

        self.max_scroll = max(0, int(self._cached_content_height) - content_rect.height)
        self.scroll_offset = max(0, min(self.max_scroll, int(self.scroll_offset)))

        if self._cached_content_surface is not None:
            available = int(self._cached_content_height) - int(self.scroll_offset)
            blit_h = max(0, min(content_rect.height, available))
            if blit_h > 0:
                source_rect = pygame.Rect(0, int(self.scroll_offset), content_rect.width, blit_h)
                surface.blit(self._cached_content_surface, content_rect.topleft, source_rect)

        if self.max_scroll > 0:
            self.draw_scroll_indicator(surface, x, y)

    def _append_wargear_profile_ops(self, text_ops, profile, profile_name: str, x_pos: int, y_pos: int) -> int:
        """Append detailed wargear profile draw operations and return new y position."""
        line_tiny = max(1, self.font_tiny.get_linesize())
        if profile_name != "default":
            profile_header = self.font_tiny.render(f"      {profile_name}:", True, TEXT_ACCENT)
            text_ops.append((profile_header, int(x_pos), int(y_pos)))
            y_pos += line_tiny + 2

        is_melee = False
        if hasattr(profile, "range"):
            if hasattr(profile.range, "max") and profile.range.max == 0:
                is_melee = True
            elif (
                hasattr(profile.range, "min")
                and hasattr(profile.range, "max")
                and profile.range.min == 0
                and profile.range.max == 0
            ):
                is_melee = True

        stats_parts = []
        if hasattr(profile, "range"):
            if is_melee:
                stats_parts.append("Melee")
            elif hasattr(profile.range, "max"):
                stats_parts.append(f"Ranged {profile.range.max}\"")
            else:
                stats_parts.append(f"Ranged {profile.range}")

        if hasattr(profile, "attacks"):
            if hasattr(profile.attacks, "value"):
                stats_parts.append(f"A: {profile.attacks.value}")
            else:
                stats_parts.append(f"A: {profile.attacks}")

        if hasattr(profile, "skill"):
            if is_melee:
                stats_parts.append(f"WS: {profile.skill}+")
            else:
                stats_parts.append(f"BS: {profile.skill}+")

        if hasattr(profile, "strength"):
            stats_parts.append(f"S: {profile.strength}")

        if hasattr(profile, "ap"):
            ap_val = profile.ap
            if ap_val == 0:
                stats_parts.append("AP: -")
            else:
                stats_parts.append(f"AP: {ap_val}")

        if hasattr(profile, "damage"):
            if hasattr(profile.damage, "value"):
                stats_parts.append(f"D: {profile.damage.value}")
            else:
                stats_parts.append(f"D: {profile.damage}")

        stats_text = " | ".join(stats_parts)
        stats_surface = self.font_tiny.render(f"      {stats_text}", True, TEXT_SECONDARY)
        text_ops.append((stats_surface, int(x_pos), int(y_pos)))
        y_pos += line_tiny + 2

        keywords = []
        if hasattr(profile, "get_keywords"):
            try:
                keywords = list(profile.get_keywords() or [])
            except Exception:
                keywords = []
        if keywords:
            keywords_text = f"      Keywords: {', '.join(keywords)}"
            keywords_surface = self.font_tiny.render(keywords_text, True, TEXT_ACCENT)
            text_ops.append((keywords_surface, int(x_pos), int(y_pos)))
            y_pos += line_tiny + 2

        abilities = list(getattr(profile, "abilities", []) or [])
        if abilities:
            abilities_text = f"      {', '.join(abilities)}"
            abilities_surface = self.font_tiny.render(abilities_text, True, TEXT_ACCENT)
            text_ops.append((abilities_surface, int(x_pos), int(y_pos)))
            y_pos += line_tiny + 2

        return y_pos + 3

    def _build_content_surface(self, unit: Unit, root: Unit, content_width: int) -> Tuple[pygame.Surface, int]:
        text_ops = []
        token_ops = []

        y_pos = 5
        x_left = 5
        x_right = max(5, content_width - 5)
        line_large = max(1, self.font_large.get_linesize())
        line_medium = max(1, self.font_medium.get_linesize())
        line_small = max(1, self.font_small.get_linesize())
        line_tiny = max(1, self.font_tiny.get_linesize())
        pad_sm = 4
        pad_md = 6
        pad_lg = 8
        wrap_width = max(10, content_width - 20)

        def _add_text(font: pygame.font.Font, text: str, color, tx: int, ty: int):
            surf = font.render(str(text), True, color)
            text_ops.append((surf, int(tx), int(ty)))
            return surf

        _add_text(self.font_large, root.name, TEXT_PRIMARY, x_left, y_pos)

        cost_val = 0
        try:
            cost_val += int(root.get_unit_cost())
        except Exception:
            pass
        try:
            for l in list(getattr(root, "attached_leaders", []) or []):
                cost_val += int(l.get_unit_cost())
        except Exception:
            pass
        try:
            for s in list(getattr(root, "attached_support_units", []) or []):
                cost_val += int(s.get_unit_cost())
        except Exception:
            pass
        cost_text = self.font_medium.render(f"{cost_val} points", True, TEXT_ACCENT)
        text_ops.append((cost_text, int(x_right - cost_text.get_rect().width), int(y_pos)))
        y_pos += line_large + pad_lg

        try:
            if getattr(unit.round_state, "performing_action_name", None):
                action_name = unit.round_state.performing_action_name
                _add_text(self.font_small, f"Performing Action: {action_name}", TEXT_ACCENT, x_left, y_pos)
                y_pos += line_small + pad_sm
        except Exception:
            pass

        _add_text(self.font_small, f"Faction: {root.faction}", TEXT_SECONDARY, x_left, y_pos)
        y_pos += line_small + pad_sm

        try:
            keywords = list(root.get_effective_keywords())
        except Exception:
            keywords = list(getattr(root, "keywords", []) or [])
        if keywords:
            _add_text(self.font_tiny, "Keywords: " + ", ".join(keywords), TEXT_SECONDARY, x_left, y_pos)
            y_pos += line_tiny + 2

        try:
            leaders = list(getattr(root, "attached_leaders", []) or [])
        except Exception:
            leaders = []
        if leaders:
            names = [getattr(l, "name", "Leader") for l in leaders]
            _add_text(self.font_tiny, "Leaders: " + ", ".join(names), TEXT_SECONDARY, x_left, y_pos)
            y_pos += line_tiny + 2

        try:
            supports = list(getattr(root, "attached_support_units", []) or [])
        except Exception:
            supports = []
        if supports:
            names = [getattr(s, "name", "Support") for s in supports]
            _add_text(self.font_tiny, "Support: " + ", ".join(names), TEXT_SECONDARY, x_left, y_pos)
            y_pos += line_tiny + 2

        try:
            total_tokens = int(root.get_aspect_shrine_token_total() or 0)
        except Exception:
            total_tokens = 0
        if total_tokens > 0:
            try:
                remaining_tokens = int(root.get_aspect_shrine_token_remaining() or 0)
            except Exception:
                remaining_tokens = 0
            header = _add_text(self.font_small, "Aspect Shrine Tokens:", TEXT_ACCENT, x_left, y_pos)
            token_size = 12
            gap = 4
            ix = x_left + header.get_width() + 8
            iy = y_pos + 2
            max_x = max(0, content_width - 15)
            for i in range(total_tokens):
                if ix + token_size > max_x:
                    ix = x_left
                    iy += token_size + 4
                token_ops.append((int(ix), int(iy), int(token_size), bool(i < remaining_tokens)))
                ix += token_size + gap
            y_pos = iy + token_size + pad_md

        try:
            footer_items = []
            candidates = []
            try:
                candidates.append(unit)
            except Exception:
                pass
            candidates.extend(leaders or [])
            seen_ids = set()
            uniq = []
            for c in candidates:
                if c is None:
                    continue
                cid = get_entity_id(c)
                if cid in seen_ids:
                    continue
                seen_ids.add(cid)
                uniq.append(c)

            for u in uniq:
                ds = getattr(u, "_datasheet", None)
                footer = None
                if ds is not None:
                    footer = getattr(ds, "leader_footer", None)
                if footer is None:
                    footer = getattr(u, "leader_footer", None)
                footer = (footer or "").strip()
                if footer:
                    footer_items.append((getattr(u, "name", "Leader"), footer))
        except Exception:
            footer_items = []

        if footer_items:
            y_pos += 6
            _add_text(self.font_medium, "Leader constraints:", TEXT_PRIMARY, x_left, y_pos)
            y_pos += line_medium + pad_sm
            for who, footer in footer_items:
                _add_text(self.font_small, f"- {who}", TEXT_ACCENT, x_left + 5, y_pos)
                y_pos += line_small + 2
                wrapped = self.wrap_text(footer, self.font_tiny, wrap_width)
                for line in wrapped:
                    _add_text(self.font_tiny, line, TEXT_SECONDARY, x_left + 10, y_pos)
                    y_pos += line_tiny + 2
                y_pos += pad_sm

        y_pos += pad_md
        _add_text(self.font_medium, "Unit Composition:", TEXT_PRIMARY, x_left, y_pos)
        y_pos += line_medium + pad_md

        model_groups = {}
        try:
            models_to_show = list(root.get_models_for_rendering())
        except Exception:
            models_to_show = list(getattr(root, "models", []) or [])
        for model in models_to_show:
            model_groups.setdefault(model.name, []).append(model)

        for model_name, models in model_groups.items():
            count = len(models)
            model_info = f"- {count}x {model_name}"
            if models:
                m = models[0]
                model_info += (
                    f" (M:{m.movement}\" T:{m.toughness} Sv:{m.save}+ "
                    f"W:{m.wounds} Ld:{m.leadership}+ OC:{m.objective_control})"
                )

            _add_text(self.font_small, model_info, TEXT_SECONDARY, x_left + 5, y_pos)
            y_pos += line_small + pad_sm

            if models and models[0].wargear:
                _add_text(self.font_tiny, "  Wargear:", TEXT_ACCENT, x_left + 10, y_pos)
                y_pos += line_tiny + 2

                wargear_counts = {}
                for model in models:
                    for wargear in model.wargear:
                        if wargear:
                            key = wargear.name
                            if key not in wargear_counts:
                                wargear_counts[key] = {"wargear": wargear, "count": 0}
                            wargear_counts[key]["count"] += 1

                for wargear_info in wargear_counts.values():
                    wargear = wargear_info["wargear"]
                    count = wargear_info["count"]
                    if count > 1:
                        wargear_text = f"    - {wargear.name} (x{count})"
                    else:
                        wargear_text = f"    - {wargear.name}"
                    _add_text(self.font_tiny, wargear_text, TEXT_SECONDARY, x_left + 15, y_pos)
                    y_pos += line_tiny + 2

                    if hasattr(wargear, "profiles") and wargear.profiles:
                        for profile_name, profile in wargear.profiles.items():
                            y_pos = self._append_wargear_profile_ops(
                                text_ops,
                                profile,
                                profile_name,
                                x_left + 25,
                                y_pos,
                            )
                    y_pos += pad_sm

        y_pos += pad_md

        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [root]
        abilities = []
        try:
            seen = set()
            for u in members:
                for ab in (getattr(u, "possible_abilities", []) or []):
                    key = (getattr(ab, "name", ""), getattr(ab, "parameter", ""), getattr(ab, "description", ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    abilities.append(ab)
        except Exception:
            abilities = list(getattr(root, "possible_abilities", []) or [])

        if abilities:
            _add_text(self.font_medium, "Abilities:", TEXT_PRIMARY, x_left, y_pos)
            y_pos += line_medium + pad_md

            for ability in abilities:
                ability_display_name = ability.name
                if hasattr(ability, "parameter") and ability.parameter:
                    ability_display_name = f"{ability.name} {ability.parameter}"

                _add_text(self.font_small, f"- {ability_display_name}", TEXT_ACCENT, x_left + 5, y_pos)
                y_pos += line_small + pad_sm

                if ability.description:
                    description = ability.description.rstrip(";")
                    desc_wrapped = self.wrap_text(description, self.font_tiny, wrap_width)
                    for line in desc_wrapped:
                        _add_text(self.font_tiny, line, TEXT_SECONDARY, x_left + 10, y_pos)
                        y_pos += line_tiny + 2
                y_pos += pad_sm

        try:
            active_leaders = list(root._disciple_of_khorne_active_leaders() or [])
        except Exception:
            active_leaders = []
        if active_leaders:
            y_pos += pad_md
            _add_text(self.font_medium, "Active Effects:", TEXT_PRIMARY, x_left, y_pos)
            y_pos += line_medium + pad_sm
            leader_names = ", ".join(str(getattr(l, "name", "Leader")) for l in active_leaders if l is not None)
            if leader_names:
                _add_text(self.font_small, f"- Disciple of Khorne ({leader_names})", TEXT_ACCENT, x_left + 5, y_pos)
                y_pos += line_small + pad_sm
            lines = [
                "Deep Strike (bearer only; while leading).",
                "Faction keyword: WORLD EATERS -> BLOOD LEGIONS (bearer only; while leading).",
                "Blessings of Khorne applies to the Attached unit (FAQ).",
            ]
            for line in lines:
                wrapped = self.wrap_text(line, self.font_tiny, wrap_width)
                for part in wrapped:
                    _add_text(self.font_tiny, part, TEXT_SECONDARY, x_left + 10, y_pos)
                    y_pos += line_tiny + 2
            y_pos += pad_sm

        if root.enhancement:
            y_pos += pad_md
            _add_text(self.font_medium, "Enhancement:", TEXT_PRIMARY, x_left, y_pos)
            y_pos += line_medium + pad_sm

            _add_text(
                self.font_small,
                f"- {root.enhancement.name} ({root.enhancement.points}pts)",
                TEXT_ACCENT,
                x_left + 5,
                y_pos,
            )
            y_pos += line_small + pad_sm

            if hasattr(root.enhancement, "description") and root.enhancement.description:
                desc_wrapped = self.wrap_text(root.enhancement.description, self.font_tiny, wrap_width)
                for line in desc_wrapped:
                    _add_text(self.font_tiny, line, TEXT_SECONDARY, x_left + 10, y_pos)
                    y_pos += line_tiny + 2
                y_pos += pad_sm

        content_height = max(1, int(y_pos + 5))
        content_surface = pygame.Surface((content_width, content_height), pygame.SRCALPHA)
        for text_surf, tx, ty in text_ops:
            content_surface.blit(text_surf, (tx, ty))
        for tx, ty, size, filled in token_ops:
            draw_aspect_shrine_token_icon(
                content_surface,
                tx + size // 2,
                ty + size // 2,
                size,
                filled=filled,
            )

        return content_surface, content_height

    def draw_scroll_indicator(self, surface: pygame.Surface, x: int, y: int):
        """Draw scroll indicator on the right side of the panel"""
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

    def draw_wargear_profile(self, surface: pygame.Surface, profile, profile_name: str, x_pos: int, y_pos: int) -> int:
        """Draw detailed wargear profile information and return new y position"""
        ops = []
        next_y = self._append_wargear_profile_ops(ops, profile, profile_name, x_pos, y_pos)
        for text_surf, tx, ty in ops:
            surface.blit(text_surf, (tx, ty))
        return next_y

    def wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> List[str]:
        """Wrap text to fit within the specified width"""
        lines = []
        for raw_line in text.splitlines():
            line_text = raw_line.strip()
            if not line_text:
                lines.append("")
                continue
            words = line_text.split(" ")
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

    def handle_event(self, event):
        """Handle events for the unit detail panel."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return True  # Signal that we want to close the panel
        return False
