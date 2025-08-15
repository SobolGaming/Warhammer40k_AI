"""
Fight Unit Selection Dialog for Warhammer 40k AI

This dialog allows human players to select which unit should fight next
during the Fight Phase, in both Fight First and Remaining Combatants stages.

Refactored to inherit from BaseDialog for consistent styling (title bar, dragging,
button handling) and to present richer unit information (melee weapons, abilities).
"""

import pygame
from typing import List, Optional, Callable
from ...classes.unit import Unit
from ...classes.player import Player
from .base_dialog import BaseDialog, PANEL_BG, PANEL_BORDER, BUTTON_BG, BUTTON_HOVER, BUTTON_SELECTED, TEXT_PRIMARY, TEXT_SECONDARY

# Accent colors
TEXT_ACCENT = (100, 149, 237)
DANGER_COLOR = (220, 53, 69)
SUCCESS_COLOR = (40, 167, 69)


class FightUnitSelectionDialog(BaseDialog):
    """Dialog for selecting which unit should fight next in the Fight Phase."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=640, height=520, draggable=True, center=True)

        # Dialog state
        self.stage_name = ""  # "Fight First" or "Remaining Combatants"
        self.eligible_units: List[Unit] = []
        self.selected_unit: Optional[Unit] = None
        self.on_unit_selected_callback: Optional[Callable[[Unit], None]] = None
        self.on_cancel_callback: Optional[Callable[[], None]] = None

        # UI state
        self.unit_button_infos = []  # [(button_name, unit)]
        self.scroll_offset = 0
        self.max_scroll = 0
    
    def show(self, stage_name: str, eligible_units: List[Unit],
             on_unit_selected: Callable[[Unit], None],
             on_cancel: Callable[[], None] = None) -> None:
        """Show the fight unit selection dialog."""
        self.stage_name = stage_name
        self.eligible_units = eligible_units
        self.selected_unit = None
        self.on_unit_selected_callback = on_unit_selected
        self.on_cancel_callback = on_cancel
        super().show()
        self.scroll_offset = 0
        self._create_unit_buttons()
        # Cancel button
        self.add_button("cancel", self.width - 140, self.height - 60, 120, 40, enabled=True)
    
    def hide(self) -> None:
        """Hide the dialog."""
        super().hide()
        self.unit_button_infos = []
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        # Use BaseDialog for core handling (drag/title/buttons)
        if super().handle_event(event):
            return True
        # Scroll wheel for the content list
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self.scroll_offset = max(0, self.scroll_offset - 20)
                return True
            if event.button == 5:
                self.scroll_offset = min(self.max_scroll, self.scroll_offset + 20)
                return True
        return False
    
    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if self.on_cancel_callback:
                self.on_cancel_callback()
            self.hide()
            return True
        if button_name.startswith("unit_"):
            try:
                idx = int(button_name.split("_")[1])
            except Exception:
                return False
            if 0 <= idx < len(self.eligible_units):
                unit = self.eligible_units[idx]
                self.selected_unit = unit
                if self.on_unit_selected_callback:
                    self.on_unit_selected_callback(unit)
                self.hide()
                return True
        return False
    
    def _create_unit_buttons(self) -> None:
        """Create buttons for each eligible unit (as BaseDialog buttons)."""
        # Clear existing
        names_to_remove = [k for k in self.buttons.keys() if k.startswith("unit_")]
        for k in names_to_remove:
            self.buttons.pop(k, None)
            self.button_states.pop(k, None)
        self.unit_button_infos = []

        button_width = self.width - 40
        button_height = 88
        button_spacing = 12
        start_y_rel = 100  # Relative to dialog top (below title/desc)

        for i, unit in enumerate(self.eligible_units):
            rel_y = start_y_rel + i * (button_height + button_spacing) - self.scroll_offset
            # Only add buttons that are potentially visible to keep rect count reasonable
            if rel_y + button_height < 80 or rel_y > self.height - 70:
                # Still register for scrolling but skip rect add if far off-screen
                self.unit_button_infos.append((f"unit_{i}", unit))
                continue
            self.add_button(f"unit_{i}", 20, rel_y, button_width, button_height, enabled=True)
            self.unit_button_infos.append((f"unit_{i}", unit))

        total_height = len(self.eligible_units) * (button_height + button_spacing)
        available_height = self.height - 160
        self.max_scroll = max(0, total_height - available_height)
    
    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return
        # Background + border
        self.draw_dialog_background(screen)
        # Title bar without emoji for font compatibility
        stage_title = f"{self.stage_name} Stage"
        self.draw_title_bar(screen, stage_title, subtitle=f"{len(self.eligible_units)} eligible units")

        # Section header
        header_surface = self.font_small.render("Select a unit to fight next:", True, TEXT_SECONDARY)
        screen.blit(header_surface, (self.x + 20, self.y + self.title_bar_height + 10))

        # Update unit buttons each frame to respect scrolling and dragging
        self._create_unit_buttons()
        self._update_buttons()

        # Render each visible unit entry
        for i, (button_name, unit) in enumerate(self.unit_button_infos):
            if button_name not in self.buttons:
                continue
            btn_rect = self.buttons[button_name]
            # Background
            pygame.draw.rect(screen, BUTTON_BG, btn_rect)
            pygame.draw.rect(screen, PANEL_BORDER, btn_rect, 2)
            # Unit name
            unit_name_surface = self.font_medium.render(unit.name, True, TEXT_PRIMARY)
            screen.blit(unit_name_surface, (btn_rect.x + 10, btn_rect.y + 8))

            # Status/health
            health_percent = unit.health_percent
            if health_percent > 75:
                health_color = SUCCESS_COLOR
                health_text = "Healthy"
            elif health_percent > 50:
                health_color = TEXT_SECONDARY
                health_text = "Wounded"
            else:
                health_color = DANGER_COLOR
                health_text = "Heavily Wounded"
            health_surface = self.font_small.render(f"Health: {health_percent:.0f}% ({health_text})", True, health_color)
            screen.blit(health_surface, (btn_rect.x + 10, btn_rect.y + 34))

            # Fight First / Charged
            ff_parts = []
            if hasattr(unit, 'round_state') and getattr(unit.round_state, 'charged_this_round', False):
                ff_parts.append("Charged this turn")
            if hasattr(unit, 'has_fight_first') and unit.has_fight_first():
                ff_parts.append("Has Fight First")
            if ff_parts:
                ff_surface = self.font_small.render(" | ".join(ff_parts), True, TEXT_SECONDARY)
                screen.blit(ff_surface, (btn_rect.x + 10, btn_rect.y + 52))

            # Melee summary (concise)
            melee_summary = self._get_unit_melee_summary(unit)
            if melee_summary:
                melee_surface = self.font_small.render(melee_summary, True, TEXT_SECONDARY)
                screen.blit(melee_surface, (btn_rect.x + 10, btn_rect.y + 70))

        # Cancel button
        self.draw_button(screen, "cancel", "Cancel")

        # Scroll indicator
        if self.max_scroll > 0:
            self._draw_scroll_indicator(screen)
    
    def _draw_scroll_indicator(self, screen: pygame.Surface) -> None:
        """Draw scroll indicator when there are more units than can fit."""
        indicator_width = 8
        indicator_height = 30
        indicator_x = self.x + self.width - 15
        indicator_y = self.y + 100
        
        # Calculate indicator position based on scroll
        scroll_ratio = self.scroll_offset / self.max_scroll if self.max_scroll > 0 else 0
        available_height = self.height - 160
        indicator_y += scroll_ratio * available_height
        
        # Draw scroll indicator
        indicator_rect = pygame.Rect(indicator_x, indicator_y, indicator_width, indicator_height)
        pygame.draw.rect(screen, TEXT_SECONDARY, indicator_rect)
        pygame.draw.rect(screen, PANEL_BORDER, indicator_rect, 1)

    def _get_unit_melee_summary(self, unit: Unit) -> str:
        """Return a concise summary of melee weapons for the unit."""
        try:
            profiles = []
            for model in unit.models:
                if not model.is_alive:
                    continue
                for wargear in model.wargear:
                    if wargear.is_melee():
                        for profile_name, profile in wargear.profiles.items():
                            # Compact stat line if available
                            parts = []
                            if hasattr(profile, 'attacks'):
                                parts.append(f"A{profile.attacks}")
                            if hasattr(profile, 'skill'):
                                parts.append(f"WS{profile.skill}+")
                            if hasattr(profile, 'strength'):
                                parts.append(f"S{profile.strength}")
                            if hasattr(profile, 'ap'):
                                parts.append(f"AP{profile.ap}")
                            if hasattr(profile, 'damage'):
                                parts.append(f"D{profile.damage}")
                            statline = "/".join(parts) if parts else ""
                            name = wargear.name if profile_name == 'default' else f"{wargear.name}:{profile_name}"
                            label = f"{name} ({statline})" if statline else name
                            profiles.append(label)
            # Deduplicate and truncate
            if not profiles:
                return ""
            seen = []
            for p in profiles:
                if p not in seen:
                    seen.append(p)
            joined = ", ".join(seen)
            if len(joined) > 80:
                joined = joined[:77] + "..."
            return f"Melee: {joined}"
        except Exception:
            return ""