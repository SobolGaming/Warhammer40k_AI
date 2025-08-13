"""
Melee Weapon Declaration Dialog for Warhammer 40k AI

This dialog allows players to declare melee weapons and targets during the Fight Phase,
following the official rules for melee combat resolution.
"""

import pygame
from typing import List, Dict, Optional, Callable
from ...classes.unit import Unit

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
        
        # Weapon group expansion state
        self.expanded_weapon_groups = set()  # Set of weapon profile IDs that are expanded
        self.available_weapons = []  # Grouped weapons list
        
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
        self.expanded_weapon_groups.clear()  # Clear expansion state
        self.available_weapons = []
    
    def _initialize_weapon_selection(self):
        """Initialize the weapon selection interface."""
        self.weapon_buttons = []
        self.selected_weapons = []
        
        if not self.unit:
            return
        
        print(f"🔍 DEBUG: Initializing weapon selection for {self.unit.name}")
        print(f"🔍 DEBUG: Unit has {len(self.unit.models)} models")
        
        # Get grouped weapons using the same system as shooting declarations
        self.available_weapons = self._get_available_melee_weapons()
        
        # Create buttons for each weapon (or weapon group)
        y_offset = 80
        button_height = 60  # Increased height for more weapon info
        
        for i, weapon_info in enumerate(self.available_weapons):
            button_rect = pygame.Rect(20, y_offset + i * button_height, self.width - 40, button_height - 5)
            
            profile = weapon_info['profile']
            has_extra_attacks = profile.is_extra_attacks()
            is_group = weapon_info.get('is_group', False)
            
            # Select first primary weapon by default, and all extra attack weapons
            is_selected = False
            if has_extra_attacks:
                is_selected = True  # Always select extra attack weapons
            elif not has_extra_attacks and not any(btn.get('selected', False) and not btn['weapon_info']['profile'].is_extra_attacks() for btn in self.weapon_buttons):
                is_selected = True  # Select first primary weapon if none selected yet
            
            self.weapon_buttons.append({
                'rect': button_rect,
                'weapon_info': weapon_info,
                'selected': is_selected,
                'has_extra_attacks': has_extra_attacks,
                'is_group': is_group
            })
            
            if is_selected:
                self.selected_weapons.append(weapon_info)
        
        # Calculate scroll limits
        total_height = len(self.weapon_buttons) * button_height
        content_height = self.height - 160  # Leave space for title and buttons
        self.max_scroll = max(0, total_height - content_height)
    
    def _get_available_melee_weapons(self):
        """Get all available melee weapon profiles for the unit, grouped by type."""
        # First, collect all individual weapons
        individual_weapons = []
        
        for model in self.unit.models:
            if not model.is_alive:
                continue
            
            for wargear in model.wargear:
                if wargear.is_melee():
                    for profile_name, profile in wargear.profiles.items():
                        individual_weapons.append({
                            'profile': profile,
                            'wargear': wargear,
                            'profile_name': profile_name,
                            'model': model,
                            'weapon_instance': len([w for w in individual_weapons if w['profile'] == profile]) + 1
                        })
        
        # Group weapons by profile
        weapon_groups = {}
        for weapon in individual_weapons:
            profile_id = id(weapon['profile'])
            if profile_id not in weapon_groups:
                weapon_groups[profile_id] = {
                    'profile': weapon['profile'],
                    'wargear': weapon['wargear'],
                    'profile_name': weapon['profile_name'],
                    'individual_weapons': [],
                    'is_group': True
                }
            weapon_groups[profile_id]['individual_weapons'].append(weapon)
        
        # Build the final weapons list
        weapons = []
        for profile_id, group in weapon_groups.items():
            if len(group['individual_weapons']) == 1:
                # Single weapon - add as individual entry
                weapon = group['individual_weapons'][0]
                weapons.append({
                    'profile': weapon['profile'],
                    'wargear': weapon['wargear'],
                    'profile_name': weapon['profile_name'],
                    'models': [weapon['model']],
                    'weapon_instance': weapon['weapon_instance'],
                    'is_group': False,
                    'group_id': None
                })
            else:
                # Multiple weapons - add as group
                if profile_id in self.expanded_weapon_groups:
                    # Group is expanded - add individual weapons
                    for weapon in group['individual_weapons']:
                        weapons.append({
                            'profile': weapon['profile'],
                            'wargear': weapon['wargear'],
                            'profile_name': weapon['profile_name'],
                            'models': [weapon['model']],
                            'weapon_instance': weapon['weapon_instance'],
                            'is_group': False,
                            'group_id': profile_id
                        })
                else:
                    # Group is collapsed - add as single group entry
                    all_models = [w['model'] for w in group['individual_weapons']]
                    weapons.append({
                        'profile': group['profile'],
                        'wargear': group['wargear'],
                        'profile_name': group['profile_name'],
                        'models': all_models,
                        'count': len(group['individual_weapons']),
                        'is_group': True,
                        'group_id': profile_id,
                        'individual_weapons': group['individual_weapons']
                    })
        
        return weapons
    
    def _toggle_weapon_group_expansion(self, group_id):
        """Toggle the expansion state of a weapon group"""
        if group_id in self.expanded_weapon_groups:
            self.expanded_weapon_groups.remove(group_id)
        else:
            self.expanded_weapon_groups.add(group_id)
        
        # Refresh the weapon selection after expanding/collapsing
        self._initialize_weapon_selection()
    
    def _is_weapon_group_expanded(self, group_id):
        """Check if a weapon group is expanded"""
        return group_id in self.expanded_weapon_groups
    
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
                weapon_info = button['weapon_info']
                has_extra_attacks = button.get('has_extra_attacks', False)
                is_group = button.get('is_group', False)
                
                # Check if this is a click on the expand/collapse button for groups
                if is_group:
                    # Check if click is on the expand/collapse button area (right side)
                    button_x = self.width - 35  # 35 pixels from right edge
                    button_y = adjusted_rect.y + 5  # 5 pixels from top of weapon row
                    button_size = 20  # 20x20 pixel button
                    
                    # Check if click is within the button bounds
                    if (button_x <= dialog_x <= button_x + button_size and 
                        button_y <= dialog_y <= button_y + button_size):
                        group_id = weapon_info['group_id']
                        self._toggle_weapon_group_expansion(group_id)
                        print(f"🔄 Toggled weapon group expansion for {weapon_info['wargear'].name}")
                        return True
                
                # Handle weapon selection with melee combat rules
                if button['selected']:
                    # Deselecting a weapon
                    if has_extra_attacks:
                        # Can always deselect extra attack weapons
                        button['selected'] = False
                        if weapon_info in self.selected_weapons:
                            self.selected_weapons.remove(weapon_info)
                    else:
                        # Deselecting primary weapon - only allowed if another primary is selected
                        other_primary_selected = any(
                            btn['selected'] and not btn.get('has_extra_attacks', False) and btn != button 
                            for btn in self.weapon_buttons
                        )
                        if other_primary_selected:
                            button['selected'] = False
                            if weapon_info in self.selected_weapons:
                                self.selected_weapons.remove(weapon_info)
                        # If no other primary selected, don't allow deselection
                else:
                    # Selecting a weapon
                    if has_extra_attacks:
                        # Can always select extra attack weapons
                        button['selected'] = True
                        if weapon_info not in self.selected_weapons:
                            self.selected_weapons.append(weapon_info)
                    else:
                        # Selecting primary weapon - deselect other primary weapons first
                        for other_btn in self.weapon_buttons:
                            if other_btn != button and other_btn['selected'] and not other_btn.get('has_extra_attacks', False):
                                other_btn['selected'] = False
                                if other_btn['weapon_info'] in self.selected_weapons:
                                    self.selected_weapons.remove(other_btn['weapon_info'])
                        
                        button['selected'] = True
                        if weapon_info not in self.selected_weapons:
                            self.selected_weapons.append(weapon_info)
                return True
        
        # Check execute button
        execute_button_rect = pygame.Rect(20, self.height - 60, self.width - 40, 40)
        if execute_button_rect.collidepoint(dialog_x, dialog_y):
            self._execute_attacks()
    
    def _execute_attacks(self):
        """Execute the declared melee attacks."""
        if self.callback:
            # Convert selected weapons to weapon declarations format
            # This should match what the fight sequence expects for weapon selection
            weapon_declarations = []
            for weapon_info in self.selected_weapons:
                is_group = weapon_info.get('is_group', False)
                
                if is_group:
                    # For groups, create individual declarations for each model
                    for individual_weapon in weapon_info.get('individual_weapons', []):
                        weapon_declarations.append({
                            'model': individual_weapon['model'],
                            'weapon_profile': individual_weapon['profile'],
                            'wargear': individual_weapon['wargear'],
                            'profile_name': individual_weapon['profile_name']
                        })
                else:
                    # For individual weapons, create declarations for each model
                    models = weapon_info.get('models', [])
                    for model in models:
                        weapon_declarations.append({
                            'model': model,
                            'weapon_profile': weapon_info['profile'],
                            'wargear': weapon_info['wargear'],
                            'profile_name': weapon_info.get('profile_name', 'default')
                        })
            
            print(f"⚔️ Weapon selection completed with {len(weapon_declarations)} weapon declarations")
            self.callback(weapon_declarations)
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
            has_extra_attacks = button.get('has_extra_attacks', False)
            if button['selected']:
                button_color = EXTRA_ATTACKS_COLOR if has_extra_attacks else MELEE_COLOR
            else:
                button_color = self.button_color
            
            pygame.draw.rect(surface, button_color, button_rect)
            pygame.draw.rect(surface, self.border_color, button_rect, 1)
            
            # Draw weapon info
            weapon_info = button['weapon_info']
            wargear = weapon_info['wargear']
            profile = weapon_info['profile']
            profile_name = weapon_info.get('profile_name', 'default')
            is_group = button.get('is_group', False)
            
            # Line 1: Weapon name (use wargear name, not "default")
            weapon_name = wargear.name
            if profile_name != 'default':
                weapon_name += f" - {profile_name}"
            
            # Add count for groups or instance number for individuals
            if is_group:
                weapon_name += f" (x{weapon_info.get('count', 1)})"
            else:
                weapon_instance = weapon_info.get('weapon_instance', 1)
                if weapon_instance > 1 or any(w.get('weapon_instance', 1) > 1 for w in self.available_weapons if w['profile'] == profile):
                    weapon_name += f" #{weapon_instance}"
            
            # Add indicator for extra attacks weapons
            if has_extra_attacks:
                weapon_name += " [EXTRA ATTACKS]"
            
            name_surface = self.font_medium.render(weapon_name, True, self.text_color)
            surface.blit(name_surface, (button_rect.x + 10, button_rect.y + 5))
            
            # Draw expand/collapse button for groups
            if is_group:
                button_x = self.width - 35
                button_y = button_rect.y + 5
                button_size = 20
                
                # Draw button background
                pygame.draw.rect(surface, (80, 80, 80), (button_x, button_y, button_size, button_size))
                pygame.draw.rect(surface, self.border_color, (button_x, button_y, button_size, button_size), 1)
                
                # Draw + or - symbol
                symbol = "-" if self._is_weapon_group_expanded(weapon_info.get('group_id')) else "+"
                symbol_surface = self.font_medium.render(symbol, True, self.text_color)
                symbol_rect = symbol_surface.get_rect(center=(button_x + button_size//2, button_y + button_size//2))
                surface.blit(symbol_surface, symbol_rect)
            
            # Line 2: Weapon stats (melee format: A/WS/S/AP/D)
            stats_parts = []
            if hasattr(profile, 'attacks'):
                stats_parts.append(f"A: {profile.attacks}")
            if hasattr(profile, 'skill'):
                stats_parts.append(f"WS: {profile.skill}+")
            if hasattr(profile, 'strength'):
                stats_parts.append(f"S: {profile.strength}")
            if hasattr(profile, 'ap'):
                stats_parts.append(f"AP: {profile.ap}")
            if hasattr(profile, 'damage'):
                stats_parts.append(f"D: {profile.damage}")
            
            if stats_parts:
                stats_text = " | ".join(stats_parts)
                stats_surface = self.font_small.render(stats_text, True, TEXT_SECONDARY)
                surface.blit(stats_surface, (button_rect.x + 10, button_rect.y + 25))
            
            # Line 3: Keywords (if any)
            keywords = profile.get_keywords() if hasattr(profile, 'get_keywords') else []
            if keywords:
                keywords_text = ", ".join(keywords)
                keywords_surface = self.font_small.render(keywords_text, True, (100, 149, 237))  # Blue accent
                surface.blit(keywords_surface, (button_rect.x + 10, button_rect.y + 42))
            
            # Selection indicator
            if button['selected']:
                check_surface = self.font_medium.render("✓", True, TEXT_PRIMARY)
                surface.blit(check_surface, (button_rect.right - 30, button_rect.y + 10)) 