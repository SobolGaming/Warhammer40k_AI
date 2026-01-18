import pygame
from typing import List

from ..ui_fonts import get_ui_font

# Font sizes
FONT_MEDIUM = 16
FONT_SMALL = 14
FONT_TINY = 12

# Enhanced Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
BUTTON_BG = (60, 60, 67)  # Button background
BUTTON_HOVER = (75, 75, 82)  # Button hover
BUTTON_SELECTED = (100, 149, 237)  # Selected button
BUTTON_DISABLED = (40, 40, 40)  # Disabled button
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_DISABLED = (100, 100, 100)  # Disabled text


class WeaponChoiceDialog:
    """Dialog for choosing weapon and profile for a unit during shooting phase"""
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 600
        self.height = 400
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.available_weapons = []
        self.scroll_offset = 0
        self.max_scroll = 0
        
        # Calculate position (center of screen)
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
        
        # Fonts
        self.font_medium = get_ui_font(FONT_MEDIUM, bold=True)
        self.font_small = get_ui_font(FONT_SMALL, bold=False)
        self.font_tiny = get_ui_font(FONT_TINY, bold=False)
        
        self.hovered_weapon = None
        self.weapon_buttons = []
    
    def show(self, unit, callback, game_map=None):
        """Show the dialog for the given unit"""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        self.visible = True
        self.scroll_offset = 0
        
        # Collect all available weapons and profiles
        self.available_weapons = []
        for model in unit.models:
            if not model.is_alive:
                continue
            
            for wargear in model.wargear:
                if wargear.is_ranged():
                    if wargear.is_bubblechukka():
                        profile = None
                        for candidate in wargear.profiles.values():
                            if getattr(candidate, "is_bubblechukka", lambda: False)():
                                profile = candidate
                                break
                        if profile is None:
                            profile = next(iter(wargear.profiles.values()), None)
                        if profile is None:
                            continue
                        # Check if unit can shoot this weapon
                        can_shoot = True
                        if unit.round_state.advanced_this_round:
                            # Unit method already checks both weapon-specific and unit-specific abilities
                            if not unit.can_shoot_after_advance(profile):
                                can_shoot = False
                        if unit.round_state.fell_back_this_round:
                            if not unit.can_shoot_after_fall_back(profile):
                                can_shoot = False

                        weapon_info = {
                            'wargear': wargear,
                            'profile': profile,
                            'profile_name': "random profile",
                            'model': model,
                            'can_shoot': can_shoot,
                            'models_with_weapon': self._count_models_with_weapon(unit, wargear)
                        }

                        # Avoid duplicates (same weapon/profile combo)
                        if not any(w['wargear'] == wargear and w['profile'] == profile
                                 for w in self.available_weapons):
                            self.available_weapons.append(weapon_info)
                        continue
                    for profile_name, profile in wargear.profiles.items():
                        # Check if unit can shoot this weapon
                        can_shoot = True
                        if unit.round_state.advanced_this_round:
                            # Unit method already checks both weapon-specific and unit-specific abilities
                            if not unit.can_shoot_after_advance(profile):
                                can_shoot = False
                        if unit.round_state.fell_back_this_round:
                            if not unit.can_shoot_after_fall_back(profile):
                                can_shoot = False
                        
                        weapon_info = {
                            'wargear': wargear,
                            'profile': profile,
                            'profile_name': profile_name,
                            'model': model,
                            'can_shoot': can_shoot,
                            'models_with_weapon': self._count_models_with_weapon(unit, wargear)
                        }
                        
                        # Avoid duplicates (same weapon/profile combo)
                        if not any(w['wargear'] == wargear and w['profile_name'] == profile_name 
                                 for w in self.available_weapons):
                            self.available_weapons.append(weapon_info)
        
        # Create button rectangles
        self._create_weapon_buttons()
    
    def _count_models_with_weapon(self, unit, wargear):
        """Count how many models in the unit have this weapon"""
        count = 0
        for model in unit.models:
            if model.is_alive and wargear in model.wargear:
                count += 1
        return count
    
    def _create_weapon_buttons(self):
        """Create button rectangles for weapon selection"""
        self.weapon_buttons = []
        button_height = 60  # Increased from 45 to 60 to prevent text overflow
        button_spacing = 5
        start_y = self.y + 60
        
        for i, weapon in enumerate(self.available_weapons):
            button_rect = pygame.Rect(
                self.x + 20, 
                start_y + i * (button_height + button_spacing) - self.scroll_offset,
                self.width - 40, 
                button_height
            )
            self.weapon_buttons.append(button_rect)
        
        # Calculate scroll limits
        total_height = len(self.available_weapons) * (button_height + button_spacing)
        visible_height = self.height - 100  # Account for title and padding
        self.max_scroll = max(0, total_height - visible_height)
    
    def hide(self):
        """Hide the dialog"""
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.available_weapons = []
        self.weapon_buttons = []
        self.scroll_offset = 0
    
    def handle_event(self, event):
        """Handle pygame events"""
        if not self.visible:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                return self.handle_click(event.pos)
            elif event.button == 4:  # Scroll up
                self.scroll(-30)
                return True
            elif event.button == 5:  # Scroll down
                self.scroll(30)
                return True
        elif event.type == pygame.MOUSEMOTION:
            self.update_hover(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
        
        return True  # Consume all events when visible
    
    def handle_click(self, mouse_pos):
        """Handle mouse clicks"""
        # Check weapon button clicks
        for i, button_rect in enumerate(self.weapon_buttons):
            if button_rect.collidepoint(mouse_pos) and i < len(self.available_weapons):
                weapon_info = self.available_weapons[i]
                if weapon_info['can_shoot']:
                    if self.callback:
                        self.callback(weapon_info['profile'])
                    self.hide()
                    return True
        
        # Click outside dialog - close it
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not dialog_rect.collidepoint(mouse_pos):
            self.hide()
            return True
        
        return True
    
    def scroll(self, delta):
        """Scroll the weapon list"""
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + delta))
        self._create_weapon_buttons()  # Recreate buttons with new scroll position
    
    def update_hover(self, mouse_pos):
        """Update hover state"""
        self.hovered_weapon = None
        for i, button_rect in enumerate(self.weapon_buttons):
            if button_rect.collidepoint(mouse_pos) and i < len(self.available_weapons):
                self.hovered_weapon = i
                break
    
    def draw(self, screen):
        """Draw the dialog"""
        if not self.visible or not self.unit or not self.available_weapons:
            return
        
        # Draw semi-transparent overlay only around the dialog area
        overlay = pygame.Surface((self.width + 40, self.height + 40))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (self.x - 20, self.y - 20))
        
        # Draw dialog background
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, PANEL_BG, dialog_rect)
        pygame.draw.rect(screen, PANEL_BORDER, dialog_rect, 3)
        
        # Draw title
        title_text = self.font_medium.render(f"Select Weapon - {self.unit.name}", True, TEXT_PRIMARY)
        title_rect = title_text.get_rect(center=(self.x + self.width // 2, self.y + 25))
        screen.blit(title_text, title_rect)
        
        # Create clipping rect for scrollable content
        content_rect = pygame.Rect(self.x + 10, self.y + 50, self.width - 20, self.height - 70)
        screen.set_clip(content_rect)
        
        # Draw weapon buttons
        for i, (weapon_info, button_rect) in enumerate(zip(self.available_weapons, self.weapon_buttons)):
            if button_rect.bottom < self.y + 50 or button_rect.top > self.y + self.height - 20:
                continue  # Skip buttons outside visible area
            
            self.draw_weapon_button(screen, button_rect, weapon_info, i)
        
        # Remove clipping
        screen.set_clip(None)
        
        # Draw scroll indicator if needed
        if self.max_scroll > 0:
            self.draw_scroll_indicator(screen)
    
    def draw_weapon_button(self, screen, rect, weapon_info, index):
        """Draw a weapon selection button"""
        wargear = weapon_info['wargear']
        profile = weapon_info['profile']
        can_shoot = weapon_info['can_shoot']
        model_count = weapon_info['models_with_weapon']
        
        # Choose colors based on state
        if not can_shoot:
            bg_color = BUTTON_DISABLED
            text_color = TEXT_DISABLED
            border_color = PANEL_BORDER
        elif self.hovered_weapon == index:
            bg_color = BUTTON_HOVER
            text_color = TEXT_PRIMARY
            border_color = BUTTON_SELECTED
        else:
            bg_color = BUTTON_BG
            text_color = TEXT_PRIMARY
            border_color = PANEL_BORDER
        
        # Draw button background
        pygame.draw.rect(screen, bg_color, rect)
        pygame.draw.rect(screen, border_color, rect, 2)
        
        # Draw weapon name and profile
        weapon_name = f"{wargear.name}"
        if wargear.is_bubblechukka():
            weapon_name += " (random profile)"
        elif len(wargear.profiles) > 1:
            weapon_name += f" ({weapon_info['profile_name']})"
        
        name_text = self.font_small.render(weapon_name, True, text_color)
        name_rect = pygame.Rect(rect.x + 10, rect.y + 6, rect.width - 20, 16)
        screen.blit(name_text, name_rect)
        
        # Draw weapon stats
        stats_text = f"Range {profile.range.max}\" | A {profile.attacks} | BS {profile.skill}+ | S {profile.strength} | AP {profile.ap} | D {profile.damage}"
        stats_surface = self.font_tiny.render(stats_text, True, text_color)
        stats_rect = pygame.Rect(rect.x + 10, rect.y + 26, rect.width - 20, 14)
        screen.blit(stats_surface, stats_rect)
        
        # Draw model count and availability
        if can_shoot:
            count_text = f"{model_count} model(s)"
            count_color = TEXT_SECONDARY
        else:
            count_text = "Cannot shoot"  
            count_color = TEXT_DISABLED
        
        count_surface = self.font_tiny.render(count_text, True, count_color)
        count_rect = pygame.Rect(rect.x + 10, rect.y + 44, rect.width - 20, 12)
        screen.blit(count_surface, count_rect)
    
    def draw_scroll_indicator(self, screen):
        """Draw scroll indicator"""
        if self.max_scroll <= 0:
            return
        
        # Calculate scroll bar dimensions
        scroll_bar_height = 100
        scroll_bar_width = 8
        scroll_bar_x = self.x + self.width - scroll_bar_width - 5
        scroll_bar_y = self.y + 60
        
        # Draw scroll track
        track_rect = pygame.Rect(scroll_bar_x, scroll_bar_y, scroll_bar_width, scroll_bar_height)
        pygame.draw.rect(screen, (100, 100, 100), track_rect)
        
        # Draw scroll thumb
        thumb_ratio = (self.height - 100) / (self.max_scroll + self.height - 100)
        thumb_height = max(20, int(scroll_bar_height * thumb_ratio))
        thumb_y = scroll_bar_y + int((scroll_bar_height - thumb_height) * (self.scroll_offset / self.max_scroll))
        
        thumb_rect = pygame.Rect(scroll_bar_x, thumb_y, scroll_bar_width, thumb_height)
        pygame.draw.rect(screen, (200, 200, 200), thumb_rect) 
