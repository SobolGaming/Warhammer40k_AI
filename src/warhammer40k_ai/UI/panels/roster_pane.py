"""
RosterPane component for displaying army rosters and unit selection.
"""

import pygame
from typing import List, Optional, Tuple, Dict

from ...classes.unit import Unit
from ...classes.player import Player
from ...classes.game import Game

# Import icon drawing functions from ui_utils to avoid circular imports
from ..ui_utils import (
    get_unit_color_variation,
    draw_character_icon,
    draw_vehicle_icon,
    draw_monster_icon,
    draw_battleline_icon,
    draw_aircraft_icon,
    draw_beast_icon,
    draw_psyker_icon,
    draw_generic_icon
)

# Font sizes
FONT_LARGE = 20
FONT_MEDIUM = 16
FONT_SMALL = 14
FONT_TINY = 12

# Modern UI Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
BUTTON_BG = (60, 60, 67)  # Button background
BUTTON_HOVER = (75, 75, 82)  # Button hover
BUTTON_SELECTED = (0, 122, 204)  # Selected button
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_ACCENT = (100, 149, 237)  # Accent text
DARK_GREY = (30, 30, 30)  # Dark grey for headers

# Button dimensions
ROSTER_PANE_BUTTON_HEIGHT = 60

class RosterPane(pygame.sprite.Sprite):
    """UI Panel for displaying army rosters and handling unit selection."""
    
    def __init__(self, left, bottom, width, height, roster, player_name):
        super().__init__()
        self.rect = pygame.Rect(left, bottom, width, height)
        self.roster = roster
        self.player_name = player_name
        self.selected_unit = None
        self.hovered_unit = None
        self.background_color = PANEL_BG
        # Use system fonts for better clarity
        try:
            self.font_large = pygame.font.SysFont('Arial', FONT_LARGE, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=False)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
            self.font_tiny = pygame.font.SysFont('Arial', FONT_TINY, bold=False)
        except:
            # Use default fonts if system fonts fail
            self.font_large = pygame.font.Font(None, FONT_LARGE)
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
            self.font_tiny = pygame.font.Font(None, FONT_TINY)
        self.button_height = ROSTER_PANE_BUTTON_HEIGHT
        self.button_width = width - 20  # 10px padding on each side
        self.buttons = []
        self.scroll_offset = 0
        self.max_scroll = 0
        self.create_buttons()
        self.game_map = None
        self.game_view = None  # Reference to GameView for deployment dialog
        
        # Find the player object from the units
        self.player = None
        if roster:  # Only try to find player if roster has units
            for unit in roster:
                if unit.parent_army and unit.parent_army.player:
                    self.player = unit.parent_army.player
                    break

    def create_buttons(self):
        """Create button rectangles for each unit in the roster."""
        self.buttons = []
        for i, unit in enumerate(self.roster):
            button_rect = pygame.Rect(
                self.rect.left + 10,
                self.rect.top + 40 + i * (self.button_height + 5) - self.scroll_offset,  # Account for header
                self.button_width,
                self.button_height
            )
            self.buttons.append((button_rect, unit))
        
        # Calculate max scroll based on content height
        total_content_height = len(self.roster) * (self.button_height + 5) + 40  # +40 for header
        visible_height = self.rect.height
        self.max_scroll = max(0, total_content_height - visible_height)

    def scroll(self, delta):
        """Handle scrolling in the roster pane"""
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + delta))
        self.create_buttons()  # Recreate buttons with new scroll offset

    def on_mouse_press(self, x, y, button):
        """Handle mouse press events in the roster pane."""
        print(f"🔍 DEBUG: RosterPane.on_mouse_press called at ({x}, {y}) button={button} for {self.player_name}")

        if button == 1:  # Left mouse button
            for button_rect, unit in self.buttons:
                if button_rect.collidepoint(x, y):
                    print(f"🔍 DEBUG: Clicked on unit {unit.name}")
                    print(f"🔍 DEBUG: unit.deployed = {unit.deployed}")
                    print(f"🔍 DEBUG: game_view exists = {self.game_view is not None}")
                    print(f"🔍 DEBUG: ui_interface exists = {self.game_view.ui_interface is not None if self.game_view else False}")

                    # Check if this is during deployment phase and unit is not deployed
                    if not unit.deployed and self.game_view and self.game_view.ui_interface:
                        # Check if deployment zones are loaded (deployment has officially started)
                        has_deployment_zones = hasattr(self.game_view.game, 'deployment_zones')
                        zones_exist = self.game_view.game.deployment_zones if has_deployment_zones else None
                        print(f"🔍 DEBUG: has_deployment_zones = {has_deployment_zones}")
                        print(f"🔍 DEBUG: zones_exist = {zones_exist is not None if zones_exist else False}")

                        if not has_deployment_zones or not zones_exist:
                            print(f"📋 Press SPACE to begin deployment sequence first")
                            return
                        
                        # Check if it's this player's turn to deploy
                        can_deploy = self.game_view.game.can_player_deploy_unit(self.player)
                        print(f"🔍 DEBUG: can_player_deploy_unit = {can_deploy}")

                        if not can_deploy:
                            # Not this player's turn - show message
                            print(f"❌ Not {self.player_name}'s turn to deploy")
                            return
                        
                        # Show deployment choice dialog
                        print(f"🔍 DEBUG: About to show deployment choice dialog for {unit.name}")

                        def on_deployment_choice(choice):
                            if choice == 'deploy':
                                unit.set_reserve_status('deployed')
                                unit.deployed = False  # Mark as ready for deployment but not yet placed
                                self.selected_unit = unit  # Select for battlefield placement
                                self.game_view.selected_unit = unit  # Also update GameView's selection
                            elif choice == 'reserves':
                                unit.set_reserve_status('reserves')
                                unit.deployed = True  # Deployment decision made (but not on battlefield)
                                self.selected_unit = None
                                self.game_view.selected_unit = None  # Clear GameView's selection
                                # Record reserves action
                                current_deployment_player = self.game_view.game.get_current_deployment_player()
                                if current_deployment_player:
                                    self.game_view.game.record_deployment_action(current_deployment_player, unit, 'reserves')
                                # Advance to next player's deployment turn
                                self.game_view.game.advance_deployment_turn()
                            elif choice == 'strategic_reserves':
                                unit.set_reserve_status('strategic_reserves')
                                unit.deployed = True  # Deployment decision made (but not on battlefield)
                                self.selected_unit = None
                                self.game_view.selected_unit = None  # Clear GameView's selection
                                # Record strategic reserves action
                                current_deployment_player = self.game_view.game.get_current_deployment_player()
                                if current_deployment_player:
                                    self.game_view.game.record_deployment_action(current_deployment_player, unit, 'strategic_reserves')
                                # Advance to next player's deployment turn
                                self.game_view.game.advance_deployment_turn()
                        
                        self.game_view.ui_interface.deployment_choice_dialog.show(unit, on_deployment_choice, self.game_view)
                        return
                    else:
                        # Normal unit selection (for deployed units or non-deployment phases)
                        self.selected_unit = unit
                        return
            self.selected_unit = None

    def draw(self, surface, game):
        """Draw the roster pane and its contents."""
        # Draw main background
        pygame.draw.rect(surface, self.background_color, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 2)
        
        # Draw header
        header_rect = pygame.Rect(self.rect.left, self.rect.top, self.rect.width, 35)
        pygame.draw.rect(surface, DARK_GREY, header_rect)
        
        # Player name with AI/Human indicator
        player_type_str = ""
        if self.player and hasattr(self.player, 'type'):
            if self.player.type.name == 'AI':
                player_type_str = " (AI)"
            elif self.player.type.name == 'HUMAN':
                player_type_str = " (HUMAN)"
        
        player_display_name = f"{self.player_name}{player_type_str}"
        player_text = self.font_medium.render(player_display_name, True, TEXT_PRIMARY)
        surface.blit(player_text, (self.rect.left + 10, self.rect.top + 5))
        
        # Army points total
        if self.roster:
            total_points = sum(unit.get_unit_cost() for unit in self.roster)
            points_text = self.font_small.render(f"{total_points} pts", True, TEXT_SECONDARY)
            surface.blit(points_text, (self.rect.right - 80, self.rect.top + 8))
        
        # Create clipping rect for scrollable content
        content_rect = pygame.Rect(self.rect.left, self.rect.top + 40, self.rect.width, self.rect.height - 40)
        surface.set_clip(content_rect)
        
        # Draw unit buttons
        for button_rect, unit in self.buttons:
            if button_rect.bottom < self.rect.top + 40 or button_rect.top > self.rect.bottom:
                continue  # Skip buttons outside visible area
                
            # Determine button state and color
            if unit == self.selected_unit:
                button_color = BUTTON_SELECTED
                border_color = TEXT_ACCENT
            elif unit == self.hovered_unit:
                button_color = BUTTON_HOVER
                border_color = PANEL_BORDER
            else:
                button_color = BUTTON_BG
                border_color = PANEL_BORDER
            
            # Draw button background
            pygame.draw.rect(surface, button_color, button_rect, border_radius=5)
            pygame.draw.rect(surface, border_color, button_rect, 2, border_radius=5)
            
            # Draw unit information
            self.draw_unit_info(surface, unit, button_rect)

        # Reset clipping
        surface.set_clip(None)
        
        # Draw scroll indicator if needed
        if self.max_scroll > 0:
            self.draw_scroll_indicator(surface)

    def draw_unit_info(self, surface, unit, button_rect):
        """Draw detailed unit information in the button."""
        y_offset = button_rect.top + 5
        x_left = button_rect.left + 8
        x_right = button_rect.right - 8
        
        # Get unit color variation for visual correlation with battlefield
        all_units = getattr(self, 'all_units', self.roster)  # Use all_units if available, otherwise use roster
        unit_color_tint = get_unit_color_variation(unit, all_units)
        
        # Draw unit type icon in the button with color tint
        icon_size = 16
        icon_x = x_left + icon_size // 2
        icon_y = button_rect.top + 20
        self.draw_roster_unit_icon(surface, icon_x, icon_y, icon_size, unit, unit_color_tint)
        
        # Unit name (truncated if too long) - moved right to make room for icon
        unit_name = unit.name
        if len(unit_name) > 18:  # Reduced to make room for icon
            unit_name = unit_name[:15] + "..."
        name_text = self.font_medium.render(unit_name, True, TEXT_PRIMARY)
        surface.blit(name_text, (x_left + icon_size + 8, y_offset))
        
        # Unit cost
        cost_text = self.font_small.render(f"{unit.get_unit_cost()}pts", True, TEXT_ACCENT)
        surface.blit(cost_text, (x_right - cost_text.get_width(), y_offset))

    def draw_roster_unit_icon(self, surface: pygame.Surface, center_x: int, center_y: int, size: int, unit: Unit, tint_color: Tuple[int, int, int] = (255, 255, 255)) -> None:
        """Draw the unit's icon in the roster with appropriate tinting."""
        # Create a surface for the icon
        icon_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Draw the appropriate icon based on unit type
        if unit.is_character():
            draw_character_icon(icon_surface, size//2, size//2, size)
        elif unit.is_vehicle():
            draw_vehicle_icon(icon_surface, size//2, size//2, size)
        elif unit.is_monster():
            draw_monster_icon(icon_surface, size//2, size//2, size)
        elif unit.is_battleline():
            draw_battleline_icon(icon_surface, size//2, size//2, size)
        elif unit.is_aircraft():
            draw_aircraft_icon(icon_surface, size//2, size//2, size)
        elif unit.is_beast():
            draw_beast_icon(icon_surface, size//2, size//2, size)
        else:
            draw_generic_icon(icon_surface, size//2, size//2, size)
        
        # Apply tint color
        for x in range(size):
            for y in range(size):
                color = icon_surface.get_at((x, y))
                if color.a > 0:  # Only tint non-transparent pixels
                    tinted_color = (
                        min(255, int(color[0] * tint_color[0] / 255)),
                        min(255, int(color[1] * tint_color[1] / 255)),
                        min(255, int(color[2] * tint_color[2] / 255)),
                        color[3]
                    )
                    icon_surface.set_at((x, y), tinted_color)
        
        # Draw the tinted icon
        surface.blit(icon_surface, (center_x - size//2, center_y - size//2))

    def draw_scroll_indicator(self, surface):
        """Draw scroll indicator when content is scrollable."""
        # Calculate scroll percentage
        scroll_percent = self.scroll_offset / self.max_scroll
        
        # Draw scroll track
        track_width = 4
        track_rect = pygame.Rect(self.rect.right - track_width - 2, self.rect.top + 40, track_width, self.rect.height - 40)
        pygame.draw.rect(surface, PANEL_BORDER, track_rect)
        
        # Draw scroll handle
        handle_height = max(20, (self.rect.height - 40) * (self.rect.height - 40) / (self.rect.height - 40 + self.max_scroll))
        handle_y = self.rect.top + 40 + scroll_percent * (self.rect.height - 40 - handle_height)
        handle_rect = pygame.Rect(track_rect.left, handle_y, track_width, handle_height)
        pygame.draw.rect(surface, TEXT_SECONDARY, handle_rect)

    def get_hovered_unit(self, x, y):
        """Get the unit being hovered over, if any."""
        for button_rect, unit in self.buttons:
            if button_rect.collidepoint(x, y):
                return unit
        return None 