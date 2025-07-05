"""
Melee Weapon Declaration Dialog for Warhammer 40k AI

This dialog allows players to declare melee weapons and targets during the Fight Phase,
following the official rules for melee combat resolution.
"""

import pygame
from typing import List, Dict, Optional, Callable
from ...classes.unit import Unit
from ...classes.model import Model
from ...classes.wargear import Wargear, WargearProfile

# Enhanced Colors
PANEL_BG = (50, 50, 50)
PANEL_BORDER = (100, 100, 100)
BUTTON_BG = (70, 70, 70)
BUTTON_HOVER = (100, 100, 100)
BUTTON_SELECTED = (120, 120, 120)
TEXT_PRIMARY = (255, 255, 255)
TEXT_SECONDARY = (200, 200, 200)
TEXT_ACCENT = (255, 100, 100)  # Red accent color for melee combat
MELEE_COLOR = (255, 100, 100)  # Red for melee weapons
EXTRA_ATTACKS_COLOR = (255, 200, 100)  # Orange for extra attacks

class MeleeWeaponDeclarationDialog:
    """
    Melee weapon declaration dialog that allows players to declare melee weapons
    and targets before executing all melee attacks simultaneously.
    """
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 600
        self.height = 500
        self.x = 50
        self.y = 50
        self.visible = False
        
        # Unit and callback
        self.unit = None
        self.callback = None
        self.game_map = None
        
        # Weapon declarations storage
        self.weapon_declarations = {}
        
        # Colors
        self.bg_color = (50, 50, 50, 230)
        self.border_color = (100, 100, 100)
        self.text_color = (255, 255, 255)
        self.button_color = (80, 80, 80)
        self.button_hover_color = (120, 120, 120)
    
    def show(self, unit: Unit, callback: Callable, game_map=None):
        """Show the melee weapon declaration dialog."""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        self.visible = True
        
        # Center dialog
        self.x = (self.screen_width - self.width) // 2
        self.y = (self.screen_height - self.height) // 2
        
        print(f"⚔️ MeleeWeaponDeclarationDialog shown for {unit.name}")
    
    def hide(self):
        """Hide the dialog."""
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.weapon_declarations = {}
    
    def handle_event(self, event):
        """Handle pygame events."""
        if not self.visible:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                mouse_pos = pygame.mouse.get_pos()
                if self._is_click_in_dialog(mouse_pos):
                    self._handle_click(mouse_pos)
                    return True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
        
        return False
    
    def _handle_click(self, mouse_pos):
        """Handle mouse clicks."""
        x, y = mouse_pos
        dialog_x = x - self.x
        dialog_y = y - self.y
        
        # Check if click is in button area
        if 10 <= dialog_x <= 590 and 450 <= dialog_y <= 490:
            self._execute_attacks()
    
    def _execute_attacks(self):
        """Execute the declared melee attacks."""
        if self.callback:
            self.callback(self.weapon_declarations)
        self.hide()
    
    def _is_click_in_dialog(self, mouse_pos):
        """Check if click is within dialog bounds."""
        x, y = mouse_pos
        return (self.x <= x <= self.x + self.width and 
                self.y <= y <= self.y + self.height)
    
    def draw(self, screen):
        """Draw the dialog."""
        if not self.visible:
            return
        
        # Create surface
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        
        # Draw background
        pygame.draw.rect(surface, self.bg_color, (0, 0, self.width, self.height))
        pygame.draw.rect(surface, self.border_color, (0, 0, self.width, self.height), 2)
        
        # Draw title
        font = pygame.font.Font(None, 24)
        title_text = f"Melee Weapon Declaration - {self.unit.name}"
        title_surface = font.render(title_text, True, self.text_color)
        surface.blit(title_surface, (10, 10))
        
        # Draw content placeholder
        content_text = "Melee weapon declaration functionality"
        content_surface = font.render(content_text, True, self.text_color)
        surface.blit(content_surface, (10, 50))
        
        # Draw execute button
        button_rect = pygame.Rect(10, 450, 580, 40)
        pygame.draw.rect(surface, self.button_color, button_rect)
        pygame.draw.rect(surface, self.border_color, button_rect, 1)
        
        button_text = "Execute Melee Attacks"
        button_surface = font.render(button_text, True, self.text_color)
        text_rect = button_surface.get_rect(center=button_rect.center)
        surface.blit(button_surface, text_rect)
        
        # Draw to screen
        screen.blit(surface, (self.x, self.y)) 