"""
Fight Unit Selection Dialog for Warhammer 40k AI

This dialog allows human players to select which unit should fight next
during the Fight Phase, in both Fight First and Remaining Combatants stages.
"""

import pygame
from typing import List, Optional, Callable
from ...classes.unit import Unit
from ...classes.player import Player

# Colors
DIALOG_BG = (45, 45, 48)
DIALOG_BORDER = (63, 63, 70)
BUTTON_BG = (60, 60, 67)
BUTTON_HOVER = (75, 75, 82)
BUTTON_SELECTED = (0, 122, 204)
TEXT_PRIMARY = (255, 255, 255)
TEXT_SECONDARY = (200, 200, 200)
TEXT_ACCENT = (100, 149, 237)
DANGER_COLOR = (220, 53, 69)
SUCCESS_COLOR = (40, 167, 69)

# Font sizes
TITLE_FONT_SIZE = 24
HEADER_FONT_SIZE = 18
BUTTON_FONT_SIZE = 16
UNIT_INFO_FONT_SIZE = 14

class FightUnitSelectionDialog:
    """Dialog for selecting which unit should fight next in the Fight Phase."""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.visible = False
        
        # Dialog dimensions
        self.width = 600
        self.height = 500
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
        
        # Dialog state
        self.stage_name = ""  # "Fight First" or "Remaining Combatants"
        self.eligible_units = []
        self.selected_unit = None
        self.on_unit_selected_callback = None
        self.on_cancel_callback = None
        
        # UI elements
        self.unit_buttons = []
        self.cancel_button = None
        self.scroll_offset = 0
        self.max_scroll = 0
        
        # Initialize fonts
        try:
            self.title_font = pygame.font.SysFont('Arial', TITLE_FONT_SIZE, bold=True)
            self.header_font = pygame.font.SysFont('Arial', HEADER_FONT_SIZE, bold=True)
            self.button_font = pygame.font.SysFont('Arial', BUTTON_FONT_SIZE)
            self.unit_info_font = pygame.font.SysFont('Arial', UNIT_INFO_FONT_SIZE)
        except:
            # Fallback to default fonts
            self.title_font = pygame.font.Font(None, TITLE_FONT_SIZE)
            self.header_font = pygame.font.Font(None, HEADER_FONT_SIZE)
            self.button_font = pygame.font.Font(None, BUTTON_FONT_SIZE)
            self.unit_info_font = pygame.font.Font(None, UNIT_INFO_FONT_SIZE)
    
    def show(self, stage_name: str, eligible_units: List[Unit], 
             on_unit_selected: Callable[[Unit], None], 
             on_cancel: Callable[[], None] = None) -> None:
        """Show the fight unit selection dialog."""
        self.stage_name = stage_name
        self.eligible_units = eligible_units
        self.selected_unit = None
        self.on_unit_selected_callback = on_unit_selected
        self.on_cancel_callback = on_cancel
        self.visible = True
        self.scroll_offset = 0
        
        # Create unit buttons
        self._create_unit_buttons()
        
        # Create cancel button
        cancel_button_width = 120
        cancel_button_height = 40
        self.cancel_button = pygame.Rect(
            self.x + self.width - cancel_button_width - 20,
            self.y + self.height - cancel_button_height - 20,
            cancel_button_width,
            cancel_button_height
        )
    
    def hide(self) -> None:
        """Hide the dialog."""
        self.visible = False
        self.unit_buttons = []
        self.cancel_button = None
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events. Returns True if event was handled."""
        if not self.visible:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                return self._handle_mouse_click(event.pos)
            elif event.button == 4:  # Mouse wheel up
                self.scroll_offset = max(0, self.scroll_offset - 20)
                return True
            elif event.button == 5:  # Mouse wheel down
                self.scroll_offset = min(self.max_scroll, self.scroll_offset + 20)
                return True
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.on_cancel_callback:
                    self.on_cancel_callback()
                self.hide()
                return True
        
        return False
    
    def _handle_mouse_click(self, pos: tuple) -> bool:
        """Handle mouse click events."""
        # Check cancel button
        if self.cancel_button and self.cancel_button.collidepoint(pos):
            if self.on_cancel_callback:
                self.on_cancel_callback()
            self.hide()
            return True
        
        # Check unit buttons
        for button_rect, unit in self.unit_buttons:
            if button_rect.collidepoint(pos):
                self.selected_unit = unit
                if self.on_unit_selected_callback:
                    self.on_unit_selected_callback(unit)
                self.hide()
                return True
        
        return False
    
    def _create_unit_buttons(self) -> None:
        """Create buttons for each eligible unit."""
        self.unit_buttons = []
        
        button_width = self.width - 40
        button_height = 80
        button_spacing = 10
        start_y = self.y + 120  # Leave space for title and description
        
        for i, unit in enumerate(self.eligible_units):
            button_y = start_y + i * (button_height + button_spacing) - self.scroll_offset
            button_rect = pygame.Rect(self.x + 20, button_y, button_width, button_height)
            self.unit_buttons.append((button_rect, unit))
        
        # Calculate max scroll
        total_height = len(self.eligible_units) * (button_height + button_spacing)
        available_height = self.height - 140  # Account for title and margins
        self.max_scroll = max(0, total_height - available_height)
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the dialog."""
        if not self.visible:
            return
        
        # Draw background overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        # Draw dialog background
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, DIALOG_BG, dialog_rect)
        pygame.draw.rect(screen, DIALOG_BORDER, dialog_rect, 3)
        
        # Draw title
        title_text = f"⚔️ {self.stage_name} Stage"
        title_surface = self.title_font.render(title_text, True, TEXT_ACCENT)
        title_rect = title_surface.get_rect(center=(self.x + self.width // 2, self.y + 30))
        screen.blit(title_surface, title_rect)
        
        # Draw description
        description_text = f"Select which unit should fight next ({len(self.eligible_units)} eligible units)"
        description_surface = self.header_font.render(description_text, True, TEXT_SECONDARY)
        description_rect = description_surface.get_rect(center=(self.x + self.width // 2, self.y + 60))
        screen.blit(description_surface, description_rect)
        
        # Draw unit buttons
        for button_rect, unit in self.unit_buttons:
            # Only draw buttons that are visible
            if button_rect.bottom < self.y + 100 or button_rect.top > self.y + self.height - 60:
                continue
            
            # Draw button background
            pygame.draw.rect(screen, BUTTON_BG, button_rect)
            pygame.draw.rect(screen, DIALOG_BORDER, button_rect, 2)
            
            # Draw unit name
            unit_name_text = unit.name
            unit_name_surface = self.button_font.render(unit_name_text, True, TEXT_PRIMARY)
            screen.blit(unit_name_surface, (button_rect.x + 10, button_rect.y + 10))
            
            # Draw unit status info
            status_lines = []
            
            # Health status
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
            
            status_lines.append(f"Health: {health_percent:.0f}% ({health_text})")
            
            # Fight First status
            if unit.should_fight_first():
                if unit.round_state.declared_charge_this_round:
                    status_lines.append("🏃 Charged this turn")
                if unit.has_fight_first():
                    status_lines.append("⚡ Has Fight First ability")
            
            # Draw status lines
            for i, status_line in enumerate(status_lines):
                status_surface = self.unit_info_font.render(status_line, True, health_color if i == 0 else TEXT_SECONDARY)
                screen.blit(status_surface, (button_rect.x + 10, button_rect.y + 35 + i * 15))
        
        # Draw cancel button
        if self.cancel_button:
            pygame.draw.rect(screen, BUTTON_BG, self.cancel_button)
            pygame.draw.rect(screen, DIALOG_BORDER, self.cancel_button, 2)
            
            cancel_text = "Cancel"
            cancel_surface = self.button_font.render(cancel_text, True, TEXT_PRIMARY)
            cancel_rect = cancel_surface.get_rect(center=self.cancel_button.center)
            screen.blit(cancel_surface, cancel_rect)
        
        # Draw scroll indicator if needed
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
        pygame.draw.rect(screen, DIALOG_BORDER, indicator_rect, 1) 