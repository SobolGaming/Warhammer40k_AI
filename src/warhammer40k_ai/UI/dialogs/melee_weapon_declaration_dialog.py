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
        self.width = 800
        self.height = 600
        self.x = 50
        self.y = 50
        self.visible = False
        
        # Unit and callback
        self.unit = None
        self.callback = None
        self.game_map = None
        
        # Weapon declarations storage
        self.weapon_declarations = {}
        self.selected_weapons = []
        
        # UI state
        self.weapon_buttons = []
        self.scroll_offset = 0
        self.max_scroll = 0
        
        # Colors
        self.bg_color = (50, 50, 50, 230)
        self.border_color = (100, 100, 100)
        self.text_color = (255, 255, 255)
        self.button_color = (80, 80, 80)
        self.button_hover_color = (120, 120, 120)
        self.selected_color = (120, 120, 120)
        
        # Fonts
        try:
            self.font_large = pygame.font.SysFont('Arial', 20, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', 16, bold=False)
            self.font_small = pygame.font.SysFont('Arial', 14, bold=False)
        except:
            self.font_large = pygame.font.Font(None, 20)
            self.font_medium = pygame.font.Font(None, 16)
            self.font_small = pygame.font.Font(None, 14)
    
    def show(self, unit: Unit, callback: Callable, game_map=None):
        """Show the melee weapon declaration dialog."""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        self.visible = True
        
        # Center dialog
        self.x = (self.screen_width - self.width) // 2
        self.y = (self.screen_height - self.height) // 2
        
        # Initialize weapon selection
        self._initialize_weapon_selection()
        
        print(f"⚔️ MeleeWeaponDeclarationDialog shown for {unit.name}")
    
    def hide(self):
        """Hide the dialog."""
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.weapon_declarations = {}
        self.selected_weapons = []
        self.weapon_buttons = []
    
    def _initialize_weapon_selection(self):
        """Initialize the weapon selection interface."""
        self.weapon_buttons = []
        self.selected_weapons = []
        
        if not self.unit:
            return
        
        # Get all melee weapons from all models
        melee_weapons = []
        for model in self.unit.models:
            if not model.is_alive:
                continue
            
            for wargear in model.wargear:
                if hasattr(wargear, 'profiles'):
                    for profile_name, profile in wargear.profiles.items():
                        if hasattr(profile, 'is_melee_weapon') and profile.is_melee_weapon():
                            melee_weapons.append({
                                'model': model,
                                'wargear': wargear,
                                'profile': profile,
                                'name': profile_name
                            })
        
        # Create buttons for each weapon
        y_offset = 80
        for i, weapon_info in enumerate(melee_weapons):
            button_rect = pygame.Rect(20, y_offset + i * 50, self.width - 40, 45)
            self.weapon_buttons.append({
                'rect': button_rect,
                'weapon_info': weapon_info,
                'selected': True  # Default to all weapons selected
            })
            self.selected_weapons.append(weapon_info)
        
        # Calculate scroll limits
        total_height = len(self.weapon_buttons) * 50
        content_height = self.height - 160  # Leave space for title and buttons
        self.max_scroll = max(0, total_height - content_height)
    
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
            elif event.button == 4:  # Scroll up
                self.scroll_offset = max(0, self.scroll_offset - 20)
                return True
            elif event.button == 5:  # Scroll down
                self.scroll_offset = min(self.max_scroll, self.scroll_offset + 20)
                return True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
            elif event.key == pygame.K_RETURN:
                self._execute_attacks()
                return True
        
        return False
    
    def _handle_click(self, mouse_pos):
        """Handle mouse clicks."""
        x, y = mouse_pos
        dialog_x = x - self.x
        dialog_y = y - self.y
        
        # Check weapon button clicks
        for button in self.weapon_buttons:
            adjusted_rect = pygame.Rect(
                button['rect'].x,
                button['rect'].y - self.scroll_offset,
                button['rect'].width,
                button['rect'].height
            )
            if adjusted_rect.collidepoint(dialog_x, dialog_y):
                # Toggle weapon selection
                weapon_info = button['weapon_info']
                if button['selected']:
                    button['selected'] = False
                    if weapon_info in self.selected_weapons:
                        self.selected_weapons.remove(weapon_info)
                else:
                    button['selected'] = True
                    if weapon_info not in self.selected_weapons:
                        self.selected_weapons.append(weapon_info)
                return
        
        # Check execute button
        execute_button_rect = pygame.Rect(20, self.height - 60, self.width - 40, 40)
        if execute_button_rect.collidepoint(dialog_x, dialog_y):
            self._execute_attacks()
    
    def _execute_attacks(self):
        """Execute the declared melee attacks."""
        if self.callback:
            # Convert selected weapons to the format expected by the callback
            declarations = []
            for weapon_info in self.selected_weapons:
                declarations.append({
                    'model': weapon_info['model'],
                    'weapon_profile': weapon_info['profile'],
                    'wargear': weapon_info['wargear']
                })
            
            print(f"⚔️ Executing melee attacks with {len(declarations)} weapon declarations")
            self.callback(declarations)
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
        
        # Create surface with alpha
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        
        # Draw background
        pygame.draw.rect(surface, self.bg_color, (0, 0, self.width, self.height))
        pygame.draw.rect(surface, self.border_color, (0, 0, self.width, self.height), 2)
        
        # Draw title
        title_text = f"Melee Weapon Declaration - {self.unit.name if self.unit else 'Unknown'}"
        title_surface = self.font_large.render(title_text, True, self.text_color)
        surface.blit(title_surface, (20, 20))
        
        # Draw instructions
        instructions = "Select melee weapons to use in combat. Click weapons to toggle selection."
        instr_surface = self.font_small.render(instructions, True, TEXT_SECONDARY)
        surface.blit(instr_surface, (20, 50))
        
        # Draw weapon buttons
        self._draw_weapon_buttons(surface)
        
        # Draw execute button
        execute_button_rect = pygame.Rect(20, self.height - 60, self.width - 40, 40)
        button_color = self.button_color
        if self.selected_weapons:
            button_color = MELEE_COLOR
        
        pygame.draw.rect(surface, button_color, execute_button_rect)
        pygame.draw.rect(surface, self.border_color, execute_button_rect, 1)
        
        button_text = f"Execute Melee Attacks ({len(self.selected_weapons)} weapons)"
        button_surface = self.font_medium.render(button_text, True, self.text_color)
        text_rect = button_surface.get_rect(center=execute_button_rect.center)
        surface.blit(button_surface, text_rect)
        
        # Draw to screen
        screen.blit(surface, (self.x, self.y))
    
    def _draw_weapon_buttons(self, surface):
        """Draw the weapon selection buttons."""
        # Create clipping area for scrolling
        clip_rect = pygame.Rect(20, 80, self.width - 40, self.height - 160)
        
        for button in self.weapon_buttons:
            # Calculate position with scroll offset
            button_rect = pygame.Rect(
                button['rect'].x,
                button['rect'].y - self.scroll_offset,
                button['rect'].width,
                button['rect'].height
            )
            
            # Skip if button is outside visible area
            if (button_rect.bottom < clip_rect.top or 
                button_rect.top > clip_rect.bottom):
                continue
            
            # Draw button background
            button_color = self.selected_color if button['selected'] else self.button_color
            pygame.draw.rect(surface, button_color, button_rect)
            pygame.draw.rect(surface, self.border_color, button_rect, 1)
            
            # Draw weapon info
            weapon_info = button['weapon_info']
            weapon_name = weapon_info['name']
            model_name = weapon_info['model'].name if hasattr(weapon_info['model'], 'name') else f"Model {weapon_info['model']._id}"
            
            # Weapon name
            name_surface = self.font_medium.render(weapon_name, True, self.text_color)
            surface.blit(name_surface, (button_rect.x + 10, button_rect.y + 5))
            
            # Model name
            model_surface = self.font_small.render(f"Model: {model_name}", True, TEXT_SECONDARY)
            surface.blit(model_surface, (button_rect.x + 10, button_rect.y + 25))
            
            # Weapon stats (if available)
            profile = weapon_info['profile']
            if hasattr(profile, 'attacks') and hasattr(profile, 'strength'):
                stats_text = f"A:{profile.attacks} S:{profile.strength}"
                if hasattr(profile, 'ap'):
                    stats_text += f" AP:{profile.ap}"
                if hasattr(profile, 'damage'):
                    stats_text += f" D:{profile.damage}"
                
                stats_surface = self.font_small.render(stats_text, True, TEXT_SECONDARY)
                surface.blit(stats_surface, (button_rect.right - 200, button_rect.y + 5))
            
            # Selection indicator
            if button['selected']:
                check_surface = self.font_medium.render("✓", True, MELEE_COLOR)
                surface.blit(check_surface, (button_rect.right - 30, button_rect.y + 10)) 