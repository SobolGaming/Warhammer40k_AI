import pygame
import textwrap
import math
import random
from typing import Optional, Tuple, Dict, List, Protocol
from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.classes.model import Model
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.classes.player import Player
from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.map import Obstacle, ObstacleType, Objective, ObjectivePoint

# Constants
TILE_SIZE = 20  # 20 pixels per inch
BATTLEFIELD_WIDTH_INCHES = 60
BATTLEFIELD_HEIGHT_INCHES = 44
BATTLEFIELD_WIDTH = BATTLEFIELD_WIDTH_INCHES * TILE_SIZE
BATTLEFIELD_HEIGHT = BATTLEFIELD_HEIGHT_INCHES * TILE_SIZE

# Enhanced Colors - Modern UI Palette
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (50, 50, 50)
LIGHT_GREY = (200, 200, 200)
DARK_GREY = (40, 40, 40)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
RED = (255, 0, 0)
PURPLE = (128, 0, 128)

# Modern UI Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
BUTTON_BG = (60, 60, 67)  # Button background
BUTTON_HOVER = (75, 75, 82)  # Button hover
BUTTON_SELECTED = (0, 122, 204)  # Selected button
BUTTON_DISABLED = (40, 40, 40)  # Disabled button
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_ACCENT = (100, 149, 237)  # Accent text
TEXT_DISABLED = (100, 100, 100)  # Disabled text
HEALTH_GOOD = (76, 175, 80)  # Green for good health
HEALTH_DAMAGED = (255, 193, 7)  # Yellow for damaged
HEALTH_CRITICAL = (244, 67, 54)  # Red for critical

# Reserves UI Colors
RESERVES_BUTTON_BG = (140, 80, 200)  # Brighter purple for reserves
RESERVES_BUTTON_HOVER = (160, 100, 220)  # Lighter purple
STRATEGIC_RESERVES_BG = (60, 120, 200)  # Brighter blue for strategic reserves
STRATEGIC_RESERVES_HOVER = (80, 140, 220)  # Lighter blue
STRATEGIC_BUTTON_BG = (60, 120, 200)  # Brighter blue for strategic button
DEPLOY_BUTTON_BG = (40, 160, 40)  # Brighter green for deploy
DEPLOY_BUTTON_HOVER = (60, 180, 60)  # Lighter green

# Game states
class GameState:
    SETUP = 0
    PLAYING = 1
    GAME_OVER = 2

# Add these new constants
MIN_ZOOM = 1.0
MAX_ZOOM = 2.0
ZOOM_SPEED = 0.1
PAN_SPEED = 15  # Increased from 5 for faster keyboard panning
MOUSE_PAN_SPEED = 1.0  # New constant for mouse panning sensitivity

# Enhanced constants for the roster panes
ROSTER_PANE_WIDTH = 350  # Wider for more information
ROSTER_PANE_BUTTON_HEIGHT = 80  # Taller for more details
ROSTER_FONT_SIZE = 16
ROSTER_LINE_HEIGHT = 18
INFO_PANE_HEIGHT = 120  # Taller for more game info

# Font sizes
FONT_LARGE = 20
FONT_MEDIUM = 16
FONT_SMALL = 14
FONT_TINY = 12

# Add new constants for icon drawing
ICON_SCALE_FACTOR = 0.8  # Larger icons that are more prominent
ICON_MIN_SIZE = 16  # Minimum icon size regardless of zoom
ICON_OVERLAY_ALPHA = 220  # Semi-transparent background for better visibility

# Color variations for multiple units of same type
UNIT_COLOR_VARIATIONS = [
    (255, 100, 100),  # Light red
    (100, 255, 100),  # Light green  
    (100, 100, 255),  # Light blue
    (255, 255, 100),  # Light yellow
    (255, 100, 255),  # Light magenta
    (100, 255, 255),  # Light cyan
    (255, 200, 100),  # Light orange
    (200, 100, 255),  # Light purple
]

def get_unit_color_variation(unit: Unit, all_units: List[Unit]) -> Tuple[int, int, int]:
    """Get a color variation for a unit to distinguish it from others of the same type."""
    # For Characters (especially Epic Heroes), assign different colors to different units
    if unit.is_character:
        character_units = [u for u in all_units if u.is_character]
        if len(character_units) > 1:
            try:
                unit_index = character_units.index(unit)
                return UNIT_COLOR_VARIATIONS[unit_index % len(UNIT_COLOR_VARIATIONS)]
            except (ValueError, IndexError):
                return (255, 255, 255)  # Default to white
    
    # For non-characters, use the original logic (same name units get different colors)
    same_type_units = [u for u in all_units if u.name == unit.name]
    if len(same_type_units) <= 1:
        return (255, 255, 255)  # Default white for single units
    
    try:
        unit_index = same_type_units.index(unit)
        return UNIT_COLOR_VARIATIONS[unit_index % len(UNIT_COLOR_VARIATIONS)]
    except (ValueError, IndexError):
        return (255, 255, 255)  # Default to white

class RosterPane(pygame.sprite.Sprite):
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
        if button == 1:  # Left mouse button
            for button_rect, unit in self.buttons:
                if button_rect.collidepoint(x, y):
                    # Check if this is during deployment phase and unit is not deployed
                    if not unit.deployed and self.game_view and self.game_view.ui_interface:
                        # Check if deployment zones are loaded (deployment has officially started)
                        if not hasattr(self.game_view.game, 'deployment_zones') or not self.game_view.game.deployment_zones:
                            print(f"📋 Press SPACE to begin deployment sequence first")
                            return
                        
                        # Check if it's this player's turn to deploy
                        if not self.game_view.game.can_player_deploy_unit(self.player):
                            # Not this player's turn - show message
                            print(f"❌ Not {self.player_name}'s turn to deploy")
                            return
                        
                        # Show deployment choice dialog
                        def on_deployment_choice(choice):
                            if choice == 'deploy':
                                unit.set_reserve_status('deployed')
                                unit.deployed = False  # Mark as ready for deployment but not yet placed
                                self.selected_unit = unit  # Select for battlefield placement
                                self.game_view.selected_unit = unit  # Also update GameView's selection
                            elif choice == 'reserves':
                                unit.set_reserve_status('reserves')
                                unit.deployed = True  # Deployed to reserves (deployment decision made)
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
                                unit.deployed = True  # Deployed to strategic reserves (deployment decision made)
                                self.selected_unit = None
                                self.game_view.selected_unit = None  # Clear GameView's selection
                                # Record strategic reserves action
                                current_deployment_player = self.game_view.game.get_current_deployment_player()
                                if current_deployment_player:
                                    self.game_view.game.record_deployment_action(current_deployment_player, unit, 'strategic_reserves')
                                # Advance to next player's deployment turn
                                self.game_view.game.advance_deployment_turn()
                        
                        self.game_view.ui_interface.deployment_choice_dialog.show(unit, on_deployment_choice)
                        return
                    else:
                        # Normal unit selection (for deployed units or non-deployment phases)
                        self.selected_unit = unit
                        return
            self.selected_unit = None

    def draw(self, surface, game):
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
        """Draw detailed unit information in the button"""
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
        cost_rect = cost_text.get_rect()
        surface.blit(cost_text, (x_right - cost_rect.width, y_offset))
        
        y_offset += 20
        
        # Model count and composition
        model_count_text = f"{len(unit.models)} models"
        if unit.is_character:
            model_count_text += " (Character)"
        elif unit.is_vehicle:
            model_count_text += " (Vehicle)"
        elif unit.is_monster:
            model_count_text += " (Monster)"
        elif unit.is_battleline:
            model_count_text += " (Battleline)"
        
        count_text = self.font_small.render(model_count_text, True, TEXT_SECONDARY)
        surface.blit(count_text, (x_left + icon_size + 8, y_offset))
        
        y_offset += 18
        
        # Health status for the unit
        total_wounds = sum(model._base_wounds for model in unit.models)
        current_wounds = sum(model.wounds for model in unit.models)
        health_percent = (current_wounds / total_wounds) * 100 if total_wounds > 0 else 100
        
        # Health color coding
        if health_percent >= 75:
            health_color = HEALTH_GOOD
        elif health_percent >= 50:
            health_color = HEALTH_DAMAGED
        else:
            health_color = HEALTH_CRITICAL
        
        health_text = f"Health: {current_wounds}/{total_wounds}"
        if unit.reserve_status == 'reserves':
            health_text += " (Reserves)"
            health_color = RESERVES_BUTTON_BG
        elif unit.reserve_status == 'strategic_reserves':
            health_text += " (Strategic Reserves)"
            health_color = STRATEGIC_BUTTON_BG
        elif not unit.deployed:
            health_text += " (Not Deployed)"
            health_color = TEXT_SECONDARY
        
        # Add movement and shooting status indicators
        status_indicators = []
        if (hasattr(unit, 'round_state') and hasattr(unit.round_state, 'moved_this_round') and 
            unit.round_state.moved_this_round):
            status_indicators.append("Moved")
            health_color = (0, 150, 200)  # Blue to indicate moved
        
        if (hasattr(unit, 'round_state') and hasattr(unit.round_state, 'shot_this_round') and 
            unit.round_state.shot_this_round):
            status_indicators.append("Shot")
            health_color = (200, 100, 0)  # Orange to indicate shot
        
        # If both moved and shot, use purple color and show both
        if len(status_indicators) == 2:
            health_color = (150, 0, 150)  # Purple for both actions
        
        # Add status indicators to health text
        if status_indicators:
            health_text += " • " + " • ".join(status_indicators)
        
        health_surface = self.font_small.render(health_text, True, health_color)
        surface.blit(health_surface, (x_left + icon_size + 8, y_offset))
        
        # Show first couple of weapons if space allows
        y_offset += 16
        if y_offset < button_rect.bottom - 5:
            weapons = []
            for model in unit.models[:1]:  # Just first model to avoid clutter
                for wargear in model.wargear[:2]:  # First 2 weapons
                    if hasattr(wargear, 'profiles') and wargear.profiles:
                        weapons.append(wargear.name)
            
            if weapons:
                weapon_text = ", ".join(weapons)
                if len(weapon_text) > 25:
                    weapon_text = weapon_text[:22] + "..."
                weapon_surface = self.font_tiny.render(weapon_text, True, TEXT_SECONDARY)
                surface.blit(weapon_surface, (x_left + icon_size + 8, y_offset))

    def draw_roster_unit_icon(self, surface: pygame.Surface, center_x: int, center_y: int, size: int, unit: Unit, tint_color: Tuple[int, int, int] = (255, 255, 255)) -> None:
        """Draw the same unit type icon used on the battlefield in the roster with color tinting"""
        # Create a surface for the icon with alpha for tinting
        icon_surface = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        icon_center = size  # Center of the icon surface
        
        # Draw the base icon on the surface - use same priority as battlefield icons
        # Priority order: Vehicle > Monster > Aircraft > Beast > Psyker > Battleline > Character > Generic
        if unit.is_vehicle:
            draw_vehicle_icon(icon_surface, icon_center, icon_center, size)
        elif unit.is_monster:
            draw_monster_icon(icon_surface, icon_center, icon_center, size)
        elif unit.is_aircraft:
            draw_aircraft_icon(icon_surface, icon_center, icon_center, size)
        elif unit.is_beast:
            draw_beast_icon(icon_surface, icon_center, icon_center, size)
        elif unit.is_psyker:
            draw_psyker_icon(icon_surface, icon_center, icon_center, size)
        elif unit.is_battleline:
            draw_battleline_icon(icon_surface, icon_center, icon_center, size)
        elif unit.is_character:
            draw_character_icon(icon_surface, icon_center, icon_center, size)
        else:
            draw_generic_icon(icon_surface, icon_center, icon_center, size)
        
        # Apply color tint if it's not the default white
        if tint_color != (255, 255, 255):
            # Create tint overlay
            tint_surface = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            tint_surface.fill((*tint_color, 120))  # Semi-transparent tint
            icon_surface.blit(tint_surface, (0, 0), special_flags=pygame.BLEND_MULT)
        
        # Blit the tinted icon to the surface
        surface.blit(icon_surface, (center_x - size, center_y - size))

    def draw_scroll_indicator(self, surface):
        """Draw a scroll indicator on the right side"""
        if self.max_scroll == 0:
            return
            
        indicator_width = 4
        indicator_x = self.rect.right - indicator_width - 2
        indicator_height = max(20, int((self.rect.height - 40) * (self.rect.height - 40) / (self.max_scroll + self.rect.height - 40)))
        indicator_y = self.rect.top + 40 + int(self.scroll_offset * (self.rect.height - 40 - indicator_height) / self.max_scroll)
        
        # Background track
        track_rect = pygame.Rect(indicator_x, self.rect.top + 40, indicator_width, self.rect.height - 40)
        pygame.draw.rect(surface, DARK_GREY, track_rect)
        
        # Scroll thumb
        thumb_rect = pygame.Rect(indicator_x, indicator_y, indicator_width, indicator_height)
        pygame.draw.rect(surface, TEXT_SECONDARY, thumb_rect, border_radius=2)

    def get_hovered_unit(self, x, y):
        for button_rect, unit in self.buttons:
            if button_rect.collidepoint(x, y):
                self.hovered_unit = unit
                return unit
        self.hovered_unit = None
        return None


class InfoPane(pygame.sprite.Sprite):
    def __init__(self, left: int, bottom: int, width: int, height: int, selected_unit: Unit):
        super().__init__()
        self.rect = pygame.Rect(left, bottom, width, height)
        self.selected_unit = selected_unit
        self.background_color = PANEL_BG
        
        # Fonts
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
        


    def handle_click(self, x: int, y: int, game_view) -> bool:
        """Handle mouse clicks on the info pane. Returns True if click was handled."""
        # No interactive elements in info pane anymore
        return False
    
    def update_hover(self, x: int, y: int):
        """Update hover state for interactive elements."""
        pass  # No interactive elements to hover over

    def draw(self, surface: pygame.Surface, game: Game, game_view=None):
        # Draw background
        pygame.draw.rect(surface, self.background_color, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 2)

        # Get game information
        current_player = game.get_current_player()
        opponent = game.get_opponent()
        
        y_offset = self.rect.top + 10
        x_left = self.rect.left + 15
        x_center = self.rect.centerx
        x_right = self.rect.right - 15

        # Game status line 1: Setup Phase, Deployment Phase, or Battle Round
        # Define deployment phase variables for later use
        in_deployment_phase = game.is_deployment_phase()
        deployment_zones_loaded = hasattr(game, 'deployment_zones') and game.deployment_zones
        
        if game.is_in_setup_phase():
            # Show current setup phase
            setup_phase_name = game.get_current_setup_phase().name.replace('_', ' ').title()
            game_status = f"SETUP: {setup_phase_name}"
            text_color = TEXT_ACCENT  # Use accent color to highlight setup phase
        elif in_deployment_phase:
            if deployment_zones_loaded:
                # Show whose turn it is to deploy with enhanced visibility
                deployment_player = game.get_current_deployment_player()
                deployable_units = game.get_deployable_units(deployment_player)
                game_status = f"🚢 DEPLOYMENT - {deployment_player.name}'s Turn ({len(deployable_units)} units left)"
                text_color = TEXT_ACCENT  # Use accent color to highlight deployment phase
            else:
                # Show battlefield creation phase before deployment zones are loaded
                game_status = "🗺️ CREATING BATTLEFIELD"
                text_color = TEXT_SECONDARY  # Different color to indicate pre-deployment state
        else:
            # Show battle round with current player
            current_player_name = current_player.name if current_player else "Unknown"
            game_status = f"Turn {game.turn} - {current_player_name} - {game.phase.name.replace('_', ' ').title()}"
            text_color = TEXT_PRIMARY
        
        game_text = self.font_medium.render(game_status, True, text_color)
        game_rect = game_text.get_rect(center=(x_center, y_offset + 10))
        surface.blit(game_text, game_rect)
        
        y_offset += 30
        
        # Setup phase, deployment, or player information
        if game.is_in_setup_phase():
            # Show setup phase information
            setup_phase = game.get_current_setup_phase()
            setup_descriptions = {
                'MUSTER_ARMIES': 'Loading army lists and preparing forces',
                'SELECT_MISSION_OBJECTIVES': 'Configuring mission objectives and commands',
                'CREATE_BATTLEFIELD': 'Creating battlefield, terrain, and objectives',
                'DETERMINE_ATTACKER_AND_DEFENDER': 'Rolling dice to determine attacker/defender roles',
                'DECLARE_BATTLE_FORMATIONS': 'Declaring battle formations and reserves',
                'DEPLOY_ARMIES': 'Deploying armies to the battlefield',
                'DETERMINE_FIRST_TURN_ORDER': 'Rolling dice to determine who goes first'
            }
            
            # Special handling for DEPLOY_ARMIES phase to show whose turn it is
            if setup_phase.name == 'DEPLOY_ARMIES' and game.is_deployment_phase():
                deployment_player = game.get_current_deployment_player()
                if deployment_player:
                    if deployment_player == game.get_attacker():
                        description = 'DEPLOY ARMIES: Attacker\'s Turn'
                    elif deployment_player == game.get_defender():
                        description = 'DEPLOY ARMIES: Defender\'s Turn'
                    else:
                        description = f'DEPLOY ARMIES: {deployment_player.name}\'s Turn'
                else:
                    description = setup_descriptions.get(setup_phase.name, f"Executing {setup_phase.name}")
            else:
                description = setup_descriptions.get(setup_phase.name, f"Executing {setup_phase.name}")
            
            setup_text = description
            setup_surface = self.font_small.render(setup_text, True, TEXT_ACCENT)
            setup_rect = setup_surface.get_rect(center=(x_center, y_offset))
            surface.blit(setup_surface, setup_rect)
            
            # Show progress indicator
            phase_number = setup_phase.value + 1
            # Import SetupPhase to get total count
            from ..classes.game import SetupPhase
            total_phases = len(SetupPhase.__members__)
            
            # Check if we're waiting for deployment input
            if getattr(game, 'waiting_for_deployment_input', False):
                progress_text = f"Phase {phase_number}/{total_phases} - Manual Deployment Mode: Press SPACE to continue each deployment"
            else:
                progress_text = f"Phase {phase_number}/{total_phases} - Press SPACE to continue"
            
            progress_surface = self.font_tiny.render(progress_text, True, TEXT_SECONDARY)
            progress_rect = progress_surface.get_rect(center=(x_center, y_offset + 20))
            surface.blit(progress_surface, progress_rect)
            y_offset += 20
        elif in_deployment_phase:
            if deployment_zones_loaded:
                # Show detailed deployment phase information
                deployment_player = game.get_current_deployment_player()
                deployable_units = game.get_deployable_units(deployment_player)
                
                # Show player role and deployment status
                player_role = "⚔️ Attacker" if deployment_player == game.get_attacker() else "🛡️ Defender"
                role_text = f"{deployment_player.name} ({player_role}) - {len(deployable_units)} units to deploy"
                role_surface = self.font_small.render(role_text, True, TEXT_ACCENT)
                role_rect = role_surface.get_rect(center=(x_center, y_offset))
                surface.blit(role_surface, role_rect)
                y_offset += 20
                
                # Show deployment zone info
                if hasattr(game, 'deployment_zones') and deployment_player.name in game.deployment_zones:
                    zone = game.deployment_zones[deployment_player.name]
                    zone_text = f"📍 Zone: X({zone['x_range'][0]:.0f}\"-{zone['x_range'][1]:.0f}\") Y({zone['y_range'][0]:.0f}\"-{zone['y_range'][1]:.0f}\")"
                    zone_surface = self.font_small.render(zone_text, True, TEXT_SECONDARY)
                    zone_rect = zone_surface.get_rect(center=(x_center, y_offset))
                    surface.blit(zone_surface, zone_rect)
                    y_offset += 20
                
                # Show deployment instructions
                if deployment_player.type.name == 'HUMAN':
                    instruction_text = "👆 Click units in roster to select, then click battlefield to deploy"
                    instruction_surface = self.font_tiny.render(instruction_text, True, TEXT_SECONDARY)
                    instruction_rect = instruction_surface.get_rect(center=(x_center, y_offset))
                    surface.blit(instruction_surface, instruction_rect)
                else:
                    instruction_text = "🤖 AI is deploying units automatically..."
                    instruction_surface = self.font_tiny.render(instruction_text, True, TEXT_SECONDARY)
                    instruction_rect = instruction_surface.get_rect(center=(x_center, y_offset))
                    surface.blit(instruction_surface, instruction_rect)
            else:
                # Show battlefield creation status
                setup_text = "🗺️ Preparing battlefield for deployment..."
                setup_surface = self.font_small.render(setup_text, True, TEXT_ACCENT)
                setup_rect = setup_surface.get_rect(center=(x_center, y_offset))
                surface.blit(setup_surface, setup_rect)
        elif game_view and hasattr(game_view, 'selected_unit') and game_view.selected_unit and not game_view.selected_unit.deployed:
            deployment_text = f"📍 Click battlefield to deploy: {game_view.selected_unit.name}"
            deployment_surface = self.font_small.render(deployment_text, True, DEPLOY_BUTTON_BG)
            deployment_rect = deployment_surface.get_rect(center=(x_center, y_offset))
            surface.blit(deployment_surface, deployment_rect)
        else:
            # Always display Player 1 on the left and Player 2 on the right
            player1 = game.players[0] if len(game.players) > 0 else None
            player2 = game.players[1] if len(game.players) > 1 else None
            
            if player1:
                # Highlight current player with accent color
                player1_color = TEXT_ACCENT if current_player == player1 else TEXT_SECONDARY
                player1_text = f"{player1.name}: {player1.command_points} CP | Score: {player1.score}"
                player1_surface = self.font_small.render(player1_text, True, player1_color)
                surface.blit(player1_surface, (x_left, y_offset))
            
            if player2:
                # Highlight current player with accent color
                player2_color = TEXT_ACCENT if current_player == player2 else TEXT_SECONDARY
                player2_text = f"{player2.name}: {player2.command_points} CP | Score: {player2.score}"
                player2_surface = self.font_small.render(player2_text, True, player2_color)
                player2_rect = player2_surface.get_rect()
                surface.blit(player2_surface, (x_right - player2_rect.width, y_offset))
        
        y_offset += 25
        
        # Deployment actions display during deployment phase
        if in_deployment_phase and hasattr(game, 'deployment_actions') and game.deployment_actions:
            # Display deployment actions on the appropriate side of the InfoPane
            # Left side for player 1, right side for player 2
            player1 = game.players[0] if len(game.players) > 0 else None
            player2 = game.players[1] if len(game.players) > 1 else None
            
            if player1 and player1.name in game.deployment_actions:
                action_text = f"📍 {game.deployment_actions[player1.name]}"
                action_surface = self.font_tiny.render(action_text, True, TEXT_ACCENT)
                # Place on left side
                surface.blit(action_surface, (x_left, y_offset))
            
            if player2 and player2.name in game.deployment_actions:
                action_text = f"📍 {game.deployment_actions[player2.name]}"
                action_surface = self.font_tiny.render(action_text, True, TEXT_ACCENT)
                action_rect = action_surface.get_rect()
                # Place on right side
                surface.blit(action_surface, (x_right - action_rect.width, y_offset))
            
            y_offset += 18
        
        # Army status or controls
        current_army = current_player.get_army()
        opponent_army = opponent.get_army()
        
        if current_army and opponent_army:
            current_units_alive = len([u for u in current_army.units if u.is_alive()])
            opponent_units_alive = len([u for u in opponent_army.units if u.is_alive()])
            
            army_status = f"Units: {current_units_alive} vs {opponent_units_alive}"
            army_text = self.font_small.render(army_status, True, TEXT_SECONDARY)
            army_rect = army_text.get_rect(center=(x_center, y_offset))
            surface.blit(army_text, army_rect)
            
            y_offset += 30
            
            # Show phase-specific controls and allowed actions
            if game_view and hasattr(game_view, 'phase_manager'):
                allowed_actions = game_view.phase_manager.get_current_allowed_actions()
                self._draw_allowed_actions(surface, allowed_actions, x_center, y_offset)
                
                # Show advance roll if active
                if (hasattr(game_view, 'selected_unit_for_movement') and game_view.selected_unit_for_movement):
                    unit = game_view.selected_unit_for_movement
                    advance_roll = unit.get_advance_roll()
                    if advance_roll is not None:
                        y_offset += 15
                        advance_info = f"🎲 Advance Roll: {advance_roll}\" (Total: {unit.movement + advance_roll}\")"
                        advance_surface = self.font_tiny.render(advance_info, True, TEXT_ACCENT)
                        advance_rect = advance_surface.get_rect(center=(x_center, y_offset))
                        surface.blit(advance_surface, advance_rect)
            else:
                # Fallback to old control display
                if in_deployment_phase and deployment_zones_loaded:
                    deployment_player = game.get_current_deployment_player()
                    if deployment_player.type.name == 'HUMAN':
                        controls_text = "⌨️ ENTER: Auto-deploy remaining | ESC: Cancel selection"
                    else:
                        controls_text = "⏳ Waiting for AI deployment to complete..."
                    controls_surface = self.font_tiny.render(controls_text, True, TEXT_SECONDARY)
                    controls_rect = controls_surface.get_rect(center=(x_center, y_offset))
                    surface.blit(controls_surface, controls_rect)
                elif in_deployment_phase and not deployment_zones_loaded:
                    controls_text = "⌨️ SPACE: Begin deployment sequence"
                    controls_surface = self.font_tiny.render(controls_text, True, TEXT_SECONDARY)
                    controls_rect = controls_surface.get_rect(center=(x_center, y_offset))
                    surface.blit(controls_surface, controls_rect)
        
        # No reserves button anymore - reserves selection happens in roster pane
    
    def _draw_allowed_actions(self, surface: pygame.Surface, allowed_actions: List[str], x_center: int, y_offset: int) -> None:
        """Draw phase-specific allowed actions"""
        if not allowed_actions:
            return
        
        # Action descriptions for user-friendly display (no emojis)
        action_descriptions = {
            "advance_setup_phase": "SPACE: Continue setup",
            "view_unit_details": "Right-click: Unit details",
            "select_unit": "Click: Select unit",
            "deploy_unit": "Click battlefield: Deploy",
            "choose_reserves": "Click unit: Deployment options",
            "complete_deployment": "ENTER: Auto-deploy remaining",
            "move_unit": "Click: Move unit",
            "advance_unit": "Double movement",
            "shoot_weapon": "Select weapon/target",
            "target_unit": "Click: Target enemy",
            "declare_charge": "Declare charge",
            "charge_move": "Move into combat",
            "pile_in": "Move closer",
            "fight": "Select target",
            "consolidate": "Move after combat"
        }
        
        # Show only 1 most relevant action to save space
        priority_actions = ["advance_setup_phase", "deploy_unit", "move_unit", "shoot_weapon", "fight"]
        displayed_actions = []
        
        # First, add priority actions that are available
        for action in priority_actions:
            if action in allowed_actions and len(displayed_actions) < 1:
                displayed_actions.append(action)
                break  # Only show one action
        
        # Draw action descriptions
        for i, action in enumerate(displayed_actions):
            if action in action_descriptions:
                action_text = action_descriptions[action]
                action_surface = self.font_tiny.render(action_text, True, TEXT_SECONDARY)
                action_rect = action_surface.get_rect(center=(x_center, y_offset + i * 12))
                surface.blit(action_surface, action_rect)


class UnitDetailPanel(pygame.sprite.Sprite):
    """Detailed unit information panel that appears when hovering over units"""
    def __init__(self, width=500, height=600):
        super().__init__()
        self.width = width
        self.height = height
        # Use system fonts for better clarity
        try:
            self.font_large = pygame.font.SysFont('Arial', FONT_LARGE, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=True)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
            self.font_tiny = pygame.font.SysFont('Arial', FONT_TINY, bold=False)
        except:
            # Use default fonts if system fonts fail
            self.font_large = pygame.font.Font(None, FONT_LARGE)
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
            self.font_tiny = pygame.font.Font(None, FONT_TINY)
        self.background_color = PANEL_BG
        self.border_color = PANEL_BORDER
        self.scroll_offset = 0
        self.max_scroll = 0

    def scroll(self, delta):
        """Handle scrolling in the unit detail panel"""
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + delta))

    def draw(self, surface: pygame.Surface, unit: Unit, x: int, y: int):
        """Draw detailed unit information at the specified position"""
        # Adjust position to keep panel on screen
        screen_width, screen_height = surface.get_size()
        if x + self.width > screen_width:
            x = screen_width - self.width - 10
        if y + self.height > screen_height:
            y = screen_height - self.height - 10
        
        self.rect = pygame.Rect(x, y, self.width, self.height)
        
        # Draw background with shadow effect
        shadow_rect = pygame.Rect(x + 3, y + 3, self.width, self.height)
        pygame.draw.rect(surface, (0, 0, 0, 100), shadow_rect, border_radius=8)
        pygame.draw.rect(surface, self.background_color, self.rect, border_radius=8)
        pygame.draw.rect(surface, self.border_color, self.rect, 2, border_radius=8)
        
        # Create clipping area for scrollable content
        content_rect = pygame.Rect(x + 10, y + 10, self.width - 20, self.height - 20)
        surface.set_clip(content_rect)
        
        y_pos = y + 15 - self.scroll_offset
        x_left = x + 15
        x_right = x + self.width - 15
        
        # Unit name and cost
        unit_name = self.font_large.render(unit.name, True, TEXT_PRIMARY)
        surface.blit(unit_name, (x_left, y_pos))
        
        cost_text = self.font_medium.render(f"{unit.get_unit_cost()} points", True, TEXT_ACCENT)
        cost_rect = cost_text.get_rect()
        surface.blit(cost_text, (x_right - cost_rect.width, y_pos))
        
        y_pos += 35
        
        # Faction and keywords
        faction_text = self.font_small.render(f"Faction: {unit.faction}", True, TEXT_SECONDARY)
        surface.blit(faction_text, (x_left, y_pos))
        y_pos += 20
        
        # Keywords (single line, no wrapping)
        if unit.keywords:
            keywords_str = "Keywords: " + ", ".join(unit.keywords)
            keyword_text = self.font_tiny.render(keywords_str, True, TEXT_SECONDARY)
            surface.blit(keyword_text, (x_left, y_pos))
            y_pos += 14
        
        y_pos += 10
        
        # Unit composition header
        comp_header = self.font_medium.render("Unit Composition:", True, TEXT_PRIMARY)
        surface.blit(comp_header, (x_left, y_pos))
        y_pos += 25
        
        # Model details
        model_groups = {}
        for model in unit.models:
            if model.name not in model_groups:
                model_groups[model.name] = []
            model_groups[model.name].append(model)
        
        for model_name, models in model_groups.items():
            count = len(models)
            model_info = f"• {count}x {model_name}"
            
            # Add stats
            if models:
                m = models[0]  # Use first model as reference
                stats = f" (M:{m.movement}\" T:{m.toughness} Sv:{m.save}+ W:{m.wounds} Ld:{m.leadership}+ OC:{m.objective_control})"
                model_info += stats
            
            model_text = self.font_small.render(model_info, True, TEXT_SECONDARY)
            surface.blit(model_text, (x_left + 5, y_pos))
            y_pos += 18
            
            # Show wargear for this model type
            if models and models[0].wargear:
                wargear_header = self.font_tiny.render("  Wargear:", True, TEXT_ACCENT)
                surface.blit(wargear_header, (x_left + 10, y_pos))
                y_pos += 14
                
                for wargear in models[0].wargear:
                    if wargear:
                        # Wargear name
                        wargear_text = f"    • {wargear.name}"
                        wargear_surface = self.font_tiny.render(wargear_text, True, TEXT_SECONDARY)
                        surface.blit(wargear_surface, (x_left + 15, y_pos))
                        y_pos += 12
                        
                        # Show wargear profiles
                        if hasattr(wargear, 'profiles') and wargear.profiles:
                            for profile_name, profile in wargear.profiles.items():
                                y_pos = self.draw_wargear_profile(surface, profile, profile_name, x_left + 25, y_pos)
                        y_pos += 5  # Extra spacing between wargear items
        
        y_pos += 15
        
        # Abilities
        if unit.possible_abilities:
            abilities_header = self.font_medium.render("Abilities:", True, TEXT_PRIMARY)
            surface.blit(abilities_header, (x_left, y_pos))
            y_pos += 25
            
            for ability in unit.possible_abilities[:5]:  # Show first 5 abilities
                # Include parameter in ability name if available (e.g., "Feel No Pain 5+")
                ability_display_name = ability.name
                if hasattr(ability, 'parameter') and ability.parameter:
                    ability_display_name = f"{ability.name} {ability.parameter}"
                
                ability_name = self.font_small.render(f"• {ability_display_name}", True, TEXT_ACCENT)
                surface.blit(ability_name, (x_left + 5, y_pos))
                y_pos += 18
                
                # Wrap ability description
                if ability.description:
                    desc_wrapped = self.wrap_text(ability.description, self.font_tiny, self.width - 40)
                    for line in desc_wrapped[:3]:  # Show first 3 lines
                        desc_text = self.font_tiny.render(line, True, TEXT_SECONDARY)
                        surface.blit(desc_text, (x_left + 10, y_pos))
                        y_pos += 12
                    y_pos += 5
        
        # Enhancement
        if unit.enhancement:
            y_pos += 10
            enh_header = self.font_medium.render("Enhancement:", True, TEXT_PRIMARY)
            surface.blit(enh_header, (x_left, y_pos))
            y_pos += 20
            
            enh_name = self.font_small.render(f"• {unit.enhancement.name} ({unit.enhancement.points}pts)", True, TEXT_ACCENT)
            surface.blit(enh_name, (x_left + 5, y_pos))
            y_pos += 18
            
            # Enhancement description
            if hasattr(unit.enhancement, 'description') and unit.enhancement.description:
                desc_wrapped = self.wrap_text(unit.enhancement.description, self.font_tiny, self.width - 40)
                for line in desc_wrapped:
                    desc_text = self.font_tiny.render(line, True, TEXT_SECONDARY)
                    surface.blit(desc_text, (x_left + 10, y_pos))
                    y_pos += 12
                y_pos += 5  # Extra spacing after description
        
        # Calculate max scroll
        total_content_height = y_pos - (y + 15) + self.scroll_offset
        self.max_scroll = max(0, total_content_height - (self.height - 30))
        
        # Reset clipping
        surface.set_clip(None)
        
        # Draw scroll indicator if needed
        if self.max_scroll > 0:
            self.draw_scroll_indicator(surface, x, y)

    def draw_scroll_indicator(self, surface: pygame.Surface, x: int, y: int):
        """Draw scroll indicator on the right side of the panel"""
        if self.max_scroll <= 0:
            return
        
        # Scroll bar background
        scrollbar_x = x + self.width - 15
        scrollbar_y = y + 10
        scrollbar_height = self.height - 20
        scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, 10, scrollbar_height)
        pygame.draw.rect(surface, DARK_GREY, scrollbar_rect, border_radius=5)
        
        # Scroll thumb
        thumb_height = max(20, int(scrollbar_height * (self.height - 30) / (self.max_scroll + self.height - 30)))
        thumb_y = scrollbar_y + int((scrollbar_height - thumb_height) * (self.scroll_offset / self.max_scroll))
        thumb_rect = pygame.Rect(scrollbar_x + 1, thumb_y, 8, thumb_height)
        pygame.draw.rect(surface, TEXT_SECONDARY, thumb_rect, border_radius=4)

    def draw_wargear_profile(self, surface: pygame.Surface, profile, profile_name: str, x_pos: int, y_pos: int) -> int:
        """Draw detailed wargear profile information and return new y position"""
        # Profile name (if not 'default')
        if profile_name != 'default':
            profile_header = self.font_tiny.render(f"      {profile_name}:", True, TEXT_ACCENT)
            surface.blit(profile_header, (x_pos, y_pos))
            y_pos += 12
        
        # Determine if weapon is melee or ranged
        is_melee = False
        if hasattr(profile, 'range'):
            if hasattr(profile.range, 'max') and profile.range.max == 0:
                is_melee = True
            elif hasattr(profile.range, 'min') and hasattr(profile.range, 'max') and profile.range.min == 0 and profile.range.max == 0:
                is_melee = True
        
        # Format profile stats - display all on one line
        stats_parts = []
        
        # Weapon type and range
        if hasattr(profile, 'range'):
            if is_melee:
                stats_parts.append("Melee")
            elif hasattr(profile.range, 'max'):
                stats_parts.append(f"Ranged {profile.range.max}\"")
            else:
                stats_parts.append(f"Ranged {profile.range}")
        
        # Attacks
        if hasattr(profile, 'attacks'):
            if hasattr(profile.attacks, 'value'):
                stats_parts.append(f"A: {profile.attacks.value}")
            else:
                stats_parts.append(f"A: {profile.attacks}")
        
        # Skill (BS for ranged, WS for melee)
        if hasattr(profile, 'skill'):
            if is_melee:
                stats_parts.append(f"WS: {profile.skill}+")
            else:
                stats_parts.append(f"BS: {profile.skill}+")
        
        # Strength
        if hasattr(profile, 'strength'):
            stats_parts.append(f"S: {profile.strength}")
        
        # AP
        if hasattr(profile, 'ap'):
            ap_val = profile.ap
            if ap_val == 0:
                stats_parts.append("AP: -")
            else:
                stats_parts.append(f"AP: {ap_val}")
        
        # Damage
        if hasattr(profile, 'damage'):
            if hasattr(profile.damage, 'value'):
                stats_parts.append(f"D: {profile.damage.value}")
            else:
                stats_parts.append(f"D: {profile.damage}")
        
        # Display all stats on one line
        if stats_parts:
            stats_line = " | ".join(stats_parts)
            stats_text = self.font_tiny.render(f"        {stats_line}", True, TEXT_SECONDARY)
            surface.blit(stats_text, (x_pos, y_pos))
            y_pos += 12
        
        # Keywords on next line (single line, no wrapping)
        if hasattr(profile, 'keywords') and profile.keywords:
            keywords_str = ", ".join(profile.keywords)
            if keywords_str:
                keyword_text = self.font_tiny.render(f"        Keywords: {keywords_str}", True, TEXT_ACCENT)
                surface.blit(keyword_text, (x_pos, y_pos))
                y_pos += 12
        
        return y_pos + 3  # Add small spacing after profile

    def wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> List[str]:
        """Wrap text to fit within max_width pixels."""
        lines = []
        words = text.split(' ')
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines


class MovementChoiceDialog:
    """Dialog for choosing movement option for a unit during movement phase"""
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 520
        self.height = 220
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.available_actions = []
        
        # Calculate position (center of screen)
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
        
        # Fonts
        try:
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=True)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
        except:
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
        
        # Button rectangles
        button_width = 95
        button_height = 32
        button_spacing = 12
        
        start_x = self.x + (self.width - (4 * button_width + 3 * button_spacing)) // 2
        button_y = self.y + self.height - 120
        
        self.move_button = pygame.Rect(start_x, button_y, button_width, button_height)
        self.advance_button = pygame.Rect(start_x + button_width + button_spacing, button_y, button_width, button_height)
        self.fall_back_button = pygame.Rect(start_x + 2 * (button_width + button_spacing), button_y, button_width, button_height)
        self.stationary_button = pygame.Rect(start_x + 3 * (button_width + button_spacing), button_y, button_width, button_height)
        
        self.hovered_button = None
    
    def show(self, unit, callback, game_map=None):
        """Show the dialog for the given unit"""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        self.visible = True
        
        # Get available actions based on engagement state
        if game_map:
            engagement_state = unit.get_engagement_state(game_map)
            self.available_actions = unit.get_available_move_actions(engagement_state.value)
        else:
            # Fallback - assume all actions available
            from warhammer40k_ai.classes.unit import MovementAction
            self.available_actions = [
                MovementAction.REMAIN_STATIONARY.value,
                MovementAction.MOVE.value,
                MovementAction.ADVANCE.value,
                MovementAction.FALL_BACK.value
            ]
    
    def hide(self):
        """Hide the dialog"""
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.available_actions = []
    
    def is_action_available(self, action_name: str) -> bool:
        """Check if a movement action is available for the current unit"""
        from warhammer40k_ai.classes.unit import MovementAction
        
        action_map = {
            'move': MovementAction.MOVE.value,
            'advance': MovementAction.ADVANCE.value,
            'fall_back': MovementAction.FALL_BACK.value,
            'stationary': MovementAction.REMAIN_STATIONARY.value
        }
        
        if action_name not in action_map:
            return False
            
        return action_map[action_name] in self.available_actions
    
    def handle_event(self, event):
        """Handle pygame events"""
        if not self.visible:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.handle_click(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            self.update_hover(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
        
        return True  # Consume all events when visible
    
    def handle_click(self, mouse_pos):
        """Handle mouse clicks"""
        if self.move_button.collidepoint(mouse_pos) and self.is_action_available('move'):
            if self.callback:
                self.callback('move')
            self.hide()
            return True
        elif self.advance_button.collidepoint(mouse_pos) and self.is_action_available('advance'):
            if self.callback:
                self.callback('advance')
            self.hide()
            return True
        elif self.fall_back_button.collidepoint(mouse_pos) and self.is_action_available('fall_back'):
            if self.callback:
                self.callback('fall_back')
            self.hide()
            return True
        elif self.stationary_button.collidepoint(mouse_pos) and self.is_action_available('stationary'):
            if self.callback:
                self.callback('stationary')
            self.hide()
            return True
        
        # Click outside dialog - close it
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not dialog_rect.collidepoint(mouse_pos):
            self.hide()
            return True
        
        return True
    
    def update_hover(self, mouse_pos):
        """Update hover state"""
        if self.move_button.collidepoint(mouse_pos):
            self.hovered_button = 'move'
        elif self.advance_button.collidepoint(mouse_pos):
            self.hovered_button = 'advance'
        elif self.fall_back_button.collidepoint(mouse_pos):
            self.hovered_button = 'fall_back'
        elif self.stationary_button.collidepoint(mouse_pos):
            self.hovered_button = 'stationary'
        else:
            self.hovered_button = None
    
    def draw(self, screen):
        """Draw the dialog"""
        if not self.visible or not self.unit:
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
        title_text = self.font_medium.render(f"Move {self.unit.name}", True, TEXT_PRIMARY)
        title_rect = title_text.get_rect(center=(self.x + self.width // 2, self.y + 30))
        screen.blit(title_text, title_rect)
        
        # Draw movement info
        movement_info = f"Movement: {self.unit.models[0].movement}\""
        info_text = self.font_small.render(movement_info, True, TEXT_SECONDARY)
        info_rect = info_text.get_rect(center=(self.x + self.width // 2, self.y + 55))
        screen.blit(info_text, info_rect)
        
        # Draw buttons - only enabled if action is available
        self.draw_button(screen, self.move_button, "Move", 'move', BUTTON_BG, enabled=self.is_action_available('move'))
        self.draw_button(screen, self.advance_button, "Advance", 'advance', BUTTON_BG, enabled=self.is_action_available('advance'))
        self.draw_button(screen, self.fall_back_button, "Fall Back", 'fall_back', BUTTON_BG, enabled=self.is_action_available('fall_back'))
        self.draw_button(screen, self.stationary_button, "Stationary", 'stationary', BUTTON_BG, enabled=self.is_action_available('stationary'))
        
        # Draw help text based on available actions
        help_parts = []
        if self.is_action_available('move'):
            help_parts.append("Move: Normal")
        if self.is_action_available('advance'):
            help_parts.append("Advance: +D6\" no shoot")
        if self.is_action_available('fall_back'):
            help_parts.append("Fall Back: Exit combat")
        
        if help_parts:
            help_text = " | ".join(help_parts)
        else:
            help_text = "Only Stationary available"
            
        help_surface = self.font_small.render(help_text, True, TEXT_SECONDARY)
        help_rect = help_surface.get_rect(center=(self.x + self.width // 2, self.y + self.height - 30))
        screen.blit(help_surface, help_rect)
    
    def draw_button(self, screen, rect, text, button_id, base_color, enabled=True):
        """Draw a button with hover effects"""
        if not enabled:
            color = BUTTON_DISABLED
            text_color = TEXT_DISABLED
        elif self.hovered_button == button_id:
            color = BUTTON_HOVER
            text_color = TEXT_PRIMARY
        else:
            color = base_color
            text_color = TEXT_PRIMARY
        
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, PANEL_BORDER, rect, 2)
        
        button_text = self.font_small.render(text, True, text_color)
        text_rect = button_text.get_rect(center=rect.center)
        screen.blit(button_text, text_rect)


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
        try:
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=True)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
            self.font_tiny = pygame.font.SysFont('Arial', FONT_TINY, bold=False)
        except:
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
            self.font_tiny = pygame.font.Font(None, FONT_TINY)
        
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
                    for profile_name, profile in wargear.profiles.items():
                        # Check if unit can shoot this weapon
                        can_shoot = True
                        if unit.round_state.advanced_this_round and not unit.can_shoot_after_advance(profile):
                            can_shoot = False
                        if unit.round_state.fell_back_this_round:
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
        if len(wargear.profiles) > 1:
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


class DeploymentChoiceDialog:
    """Simple dialog for choosing deployment option for a single unit"""
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 300
        self.height = 200
        self.visible = False
        self.unit = None
        self.callback = None
        
        # Calculate position (center of screen)
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
        
        # Fonts
        try:
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=True)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
        except:
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
        
        # Button rectangles
        button_width = 80
        button_height = 30
        button_spacing = 10
        
        start_x = self.x + (self.width - (3 * button_width + 2 * button_spacing)) // 2
        button_y = self.y + self.height - 110
        
        self.deploy_button = pygame.Rect(start_x, button_y, button_width, button_height)
        self.reserves_button = pygame.Rect(start_x + button_width + button_spacing, button_y, button_width, button_height)
        self.strategic_button = pygame.Rect(start_x + 2 * (button_width + button_spacing), button_y, button_width, button_height)
        
        self.hovered_button = None
    
    def show(self, unit, callback):
        """Show the dialog for the given unit"""
        self.unit = unit
        self.callback = callback
        self.visible = True
    
    def hide(self):
        """Hide the dialog"""
        self.visible = False
        self.unit = None
        self.callback = None
    
    def handle_event(self, event):
        """Handle pygame events"""
        if not self.visible:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.handle_click(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            self.update_hover(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
        
        return True  # Consume all events when visible
    
    def handle_click(self, mouse_pos):
        """Handle mouse clicks"""
        if self.deploy_button.collidepoint(mouse_pos):
            if self.callback:
                self.callback('deploy')
            self.hide()
            return True
        elif self.reserves_button.collidepoint(mouse_pos):
            # Only allow reserves if unit has Deep Strike
            if self.unit and self.unit.has_deep_strike():
                if self.callback:
                    self.callback('reserves')
                self.hide()
                return True
            # If unit doesn't have Deep Strike, don't do anything but still consume the click
            return True
        elif self.strategic_button.collidepoint(mouse_pos):
            if self.callback:
                self.callback('strategic_reserves')
            self.hide()
            return True
        
        # Click outside dialog - close it
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not dialog_rect.collidepoint(mouse_pos):
            self.hide()
            return True
        
        return True
    
    def update_hover(self, mouse_pos):
        """Update hover state"""
        if self.deploy_button.collidepoint(mouse_pos):
            self.hovered_button = 'deploy'
        elif self.reserves_button.collidepoint(mouse_pos):
            self.hovered_button = 'reserves'
        elif self.strategic_button.collidepoint(mouse_pos):
            self.hovered_button = 'strategic'
        else:
            self.hovered_button = None
    
    def draw(self, screen):
        """Draw the dialog"""
        if not self.visible or not self.unit:
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
        title_text = self.font_medium.render(f"Deploy {self.unit.name}", True, TEXT_PRIMARY)
        title_rect = title_text.get_rect(center=(self.x + self.width // 2, self.y + 30))
        screen.blit(title_text, title_rect)
        
        # Draw instruction
        instruction = "Choose deployment option:"
        instruction_text = self.font_small.render(instruction, True, TEXT_SECONDARY)
        instruction_rect = instruction_text.get_rect(center=(self.x + self.width // 2, self.y + 60))
        screen.blit(instruction_text, instruction_rect)
        
        # Draw buttons
        self.draw_button(screen, self.deploy_button, "Deploy", 'deploy', DEPLOY_BUTTON_BG)
        
        # Reserves button - only enabled if unit has Deep Strike
        if self.unit.has_deep_strike():
            self.draw_button(screen, self.reserves_button, "Reserves", 'reserves', RESERVES_BUTTON_BG)
        else:
            self.draw_button(screen, self.reserves_button, "Reserves", 'reserves', BUTTON_DISABLED, enabled=False)
        
        self.draw_button(screen, self.strategic_button, "Strategic", 'strategic', STRATEGIC_BUTTON_BG)
        
        # Draw help text
        if self.unit.has_deep_strike():
            help_text = "Reserves: Deep Strike ability required"
        else:
            help_text = "Reserves: Requires Deep Strike ability"
        
        help_surface = self.font_small.render(help_text, True, TEXT_SECONDARY)
        help_rect = help_surface.get_rect(center=(self.x + self.width // 2, self.y + self.height - 40))
        screen.blit(help_surface, help_rect)
    
    def draw_button(self, screen, rect, text, button_id, base_color, enabled=True):
        """Draw a button with hover effects"""
        if not enabled:
            color = BUTTON_DISABLED
            text_color = TEXT_DISABLED
        elif self.hovered_button == button_id:
            color = BUTTON_HOVER
            text_color = TEXT_PRIMARY
        else:
            color = base_color
            text_color = TEXT_PRIMARY
        
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, PANEL_BORDER, rect, 2)
        
        button_text = self.font_small.render(text, True, text_color)
        text_rect = button_text.get_rect(center=rect.center)
        screen.blit(button_text, text_rect)


class ReservesSelectionDialog:
    """UI Dialog for selecting which units to place in reserves during deployment."""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 800
        self.height = 600
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        
        # UI state
        self.visible = False
        self.player = None
        self.units = []
        self.reserves_decisions = {}  # unit_name -> 'deploy'/'reserves'/'strategic_reserves'
        self.selected_unit = None
        self.hovered_unit = None
        self.scroll_offset = 0
        self.max_scroll = 0
        
        # Fonts
        try:
            self.font_large = pygame.font.SysFont('Arial', 24, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', 18, bold=False)
            self.font_small = pygame.font.SysFont('Arial', 14, bold=False)
        except:
            self.font_large = pygame.font.Font(None, 24)
            self.font_medium = pygame.font.Font(None, 18)
            self.font_small = pygame.font.Font(None, 14)
            
        # Button dimensions
        self.unit_button_height = 100
        self.button_width = self.width - 40
        self.choice_button_width = 140
        self.choice_button_height = 30
        
        # Complete callback
        self.on_complete = None
        
    def show(self, player, on_complete_callback):
        """Show the reserves selection dialog."""
        self.visible = True
        self.player = player
        self.units = player.get_army().units
        self.on_complete = on_complete_callback
        
        # Initialize all units to deploy by default
        self.reserves_decisions = {unit.name: 'deploy' for unit in self.units}
        
        # Calculate scroll limits
        total_height = len(self.units) * (self.unit_button_height + 10) + 100  # +100 for header/footer
        visible_height = self.height - 100  # Account for header/footer
        self.max_scroll = max(0, total_height - visible_height)
        
    def hide(self):
        """Hide the reserves selection dialog."""
        self.visible = False
        self.player = None
        self.units = []
        self.reserves_decisions = {}
        
    def handle_event(self, event):
        """Handle pygame events for the reserves dialog."""
        if not self.visible:
            return False
            
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                return self.handle_click(event.pos)
            elif event.button == 4:  # Mouse wheel up
                self.scroll_offset = max(0, self.scroll_offset - 30)
                return True
            elif event.button == 5:  # Mouse wheel down
                self.scroll_offset = min(self.max_scroll, self.scroll_offset + 30)
                return True
                
        elif event.type == pygame.MOUSEMOTION:
            self.update_hover(event.pos)
            return True
            
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
            elif event.key == pygame.K_RETURN:
                self.complete_selection()
                return True
                
        return True  # Consume all events while visible
        
    def handle_click(self, mouse_pos):
        """Handle mouse clicks in the reserves dialog."""
        x, y = mouse_pos
        
        # Check if click is outside dialog
        if not self.rect.collidepoint(x, y):
            return True
            
        # Check complete button
        complete_rect = pygame.Rect(self.x + self.width - 120, self.y + self.height - 50, 100, 30)
        if complete_rect.collidepoint(x, y):
            self.complete_selection()
            return True
            
        # Check unit buttons and choice buttons
        for i, unit in enumerate(self.units):
            unit_y = self.y + 80 + i * (self.unit_button_height + 10) - self.scroll_offset
            unit_rect = pygame.Rect(self.x + 20, unit_y, self.button_width, self.unit_button_height)
            
            if unit_rect.collidepoint(x, y):
                # Check which choice button was clicked
                choice_y = unit_y + 60
                deploy_rect = pygame.Rect(self.x + 30, choice_y, self.choice_button_width, self.choice_button_height)
                reserves_rect = pygame.Rect(self.x + 30 + self.choice_button_width + 10, choice_y, self.choice_button_width, self.choice_button_height)
                strategic_rect = pygame.Rect(self.x + 30 + 2 * (self.choice_button_width + 10), choice_y, self.choice_button_width, self.choice_button_height)
                
                if deploy_rect.collidepoint(x, y):
                    self.reserves_decisions[unit.name] = 'deploy'
                elif reserves_rect.collidepoint(x, y) and self.can_use_reserves(unit):
                    self.reserves_decisions[unit.name] = 'reserves'
                elif strategic_rect.collidepoint(x, y):
                    self.reserves_decisions[unit.name] = 'strategic_reserves'
                
                return True
                
        return True
        
    def update_hover(self, mouse_pos):
        """Update hover state based on mouse position."""
        x, y = mouse_pos
        self.hovered_unit = None
        
        for i, unit in enumerate(self.units):
            unit_y = self.y + 80 + i * (self.unit_button_height + 10) - self.scroll_offset
            unit_rect = pygame.Rect(self.x + 20, unit_y, self.button_width, self.unit_button_height)
            
            if unit_rect.collidepoint(x, y):
                self.hovered_unit = unit
                break
                
    def can_use_reserves(self, unit):
        """Check if a unit can use standard reserves (Deep Strike, etc.)."""
        # Units with Deep Strike or similar abilities can use reserves
        return unit.has_deep_strike() or "Deep Strike" in unit.keywords
        
    def complete_selection(self):
        """Complete the reserves selection and call the callback."""
        if self.on_complete:
            self.on_complete(self.reserves_decisions)
        self.hide()
        
    def draw(self, screen):
        """Draw the reserves selection dialog."""
        if not self.visible:
            return
            
        # Draw backdrop
        backdrop = pygame.Surface((self.screen_width, self.screen_height))
        backdrop.set_alpha(128)
        backdrop.fill(BLACK)
        screen.blit(backdrop, (0, 0))
        
        # Draw main dialog
        pygame.draw.rect(screen, PANEL_BG, self.rect)
        pygame.draw.rect(screen, PANEL_BORDER, self.rect, 3)
        
        # Draw header
        header_text = self.font_large.render(f"Reserves Selection - {self.player.name}", True, TEXT_PRIMARY)
        screen.blit(header_text, (self.x + 20, self.y + 20))
        
        # Draw instructions
        instructions = "Choose deployment options for each unit. Units with Deep Strike can use Reserves."
        instr_text = self.font_small.render(instructions, True, TEXT_SECONDARY)
        screen.blit(instr_text, (self.x + 20, self.y + 50))
        
        # Create clipping rect for scrollable content
        content_rect = pygame.Rect(self.x + 10, self.y + 70, self.width - 20, self.height - 120)
        screen.set_clip(content_rect)
        
        # Draw units
        for i, unit in enumerate(self.units):
            unit_y = self.y + 80 + i * (self.unit_button_height + 10) - self.scroll_offset
            
            # Skip units outside visible area
            if unit_y + self.unit_button_height < self.y + 70 or unit_y > self.y + self.height - 50:
                continue
                
            self.draw_unit_selection(screen, unit, unit_y)
            
        # Remove clipping
        screen.set_clip(None)
        
        # Draw complete button
        complete_rect = pygame.Rect(self.x + self.width - 120, self.y + self.height - 50, 100, 30)
        pygame.draw.rect(screen, BUTTON_BG, complete_rect)
        pygame.draw.rect(screen, PANEL_BORDER, complete_rect, 2)
        
        complete_text = self.font_medium.render("Complete", True, TEXT_PRIMARY)
        text_rect = complete_text.get_rect(center=complete_rect.center)
        screen.blit(complete_text, text_rect)
        
        # Draw scroll indicator if needed
        if self.max_scroll > 0:
            self.draw_scroll_indicator(screen)
            
    def draw_unit_selection(self, screen, unit, y):
        """Draw an individual unit's selection options."""
        unit_rect = pygame.Rect(self.x + 20, y, self.button_width, self.unit_button_height)
        
        # Background color based on hover
        bg_color = BUTTON_HOVER if unit == self.hovered_unit else BUTTON_BG
        pygame.draw.rect(screen, bg_color, unit_rect)
        pygame.draw.rect(screen, PANEL_BORDER, unit_rect, 2)
        
        # Unit name and info
        name_text = self.font_medium.render(unit.name, True, TEXT_PRIMARY)
        screen.blit(name_text, (self.x + 30, y + 10))
        
        # Unit details
        details = f"{len(unit.models)} models • {unit.get_unit_cost()} pts"
        details_text = self.font_small.render(details, True, TEXT_SECONDARY)
        screen.blit(details_text, (self.x + 30, y + 35))
        
        # Choice buttons
        choice_y = y + 60
        current_choice = self.reserves_decisions.get(unit.name, 'deploy')
        
        # Deploy button
        deploy_rect = pygame.Rect(self.x + 30, choice_y, self.choice_button_width, self.choice_button_height)
        deploy_color = DEPLOY_BUTTON_BG if current_choice == 'deploy' else BUTTON_BG
        pygame.draw.rect(screen, deploy_color, deploy_rect)
        pygame.draw.rect(screen, PANEL_BORDER, deploy_rect, 1)
        
        deploy_text = self.font_small.render("Deploy", True, TEXT_PRIMARY)
        text_rect = deploy_text.get_rect(center=deploy_rect.center)
        screen.blit(deploy_text, text_rect)
        
        # Reserves button
        reserves_rect = pygame.Rect(self.x + 30 + self.choice_button_width + 10, choice_y, self.choice_button_width, self.choice_button_height)
        can_reserves = self.can_use_reserves(unit)
        reserves_color = RESERVES_BUTTON_BG if current_choice == 'reserves' else (BUTTON_BG if can_reserves else DARK_GREY)
        pygame.draw.rect(screen, reserves_color, reserves_rect)
        pygame.draw.rect(screen, PANEL_BORDER, reserves_rect, 1)
        
        reserves_text = self.font_small.render("Reserves", True, TEXT_PRIMARY if can_reserves else TEXT_SECONDARY)
        text_rect = reserves_text.get_rect(center=reserves_rect.center)
        screen.blit(reserves_text, text_rect)
        
        # Strategic reserves button
        strategic_rect = pygame.Rect(self.x + 30 + 2 * (self.choice_button_width + 10), choice_y, self.choice_button_width, self.choice_button_height)
        strategic_color = STRATEGIC_RESERVES_BG if current_choice == 'strategic_reserves' else BUTTON_BG
        pygame.draw.rect(screen, strategic_color, strategic_rect)
        pygame.draw.rect(screen, PANEL_BORDER, strategic_rect, 1)
        
        strategic_text = self.font_small.render("Strategic Reserves", True, TEXT_PRIMARY)
        text_rect = strategic_text.get_rect(center=strategic_rect.center)
        screen.blit(strategic_text, text_rect)
        
    def draw_scroll_indicator(self, screen):
        """Draw scroll indicator."""
        if self.max_scroll <= 0:
            return
            
        # Scroll bar background
        scroll_rect = pygame.Rect(self.x + self.width - 15, self.y + 70, 10, self.height - 120)
        pygame.draw.rect(screen, DARK_GREY, scroll_rect)
        
        # Scroll thumb
        thumb_height = max(20, int((self.height - 120) * (self.height - 120) / (self.max_scroll + self.height - 120)))
        thumb_y = self.y + 70 + int(self.scroll_offset * (self.height - 120 - thumb_height) / self.max_scroll)
        thumb_rect = pygame.Rect(self.x + self.width - 15, thumb_y, 10, thumb_height)
        pygame.draw.rect(screen, LIGHT_GREY, thumb_rect)


class ReservesArrivalPanel:
    """UI Panel for bringing units in from reserves during the game."""
    
    def __init__(self, width: int = 400, height: int = 500):
        self.width = width
        self.height = height
        self.visible = False
        self.player = None
        self.game = None
        self.available_units = []
        self.selected_unit = None
        self.placement_mode = False
        self.placement_position = None
        
        # Fonts
        try:
            self.font_large = pygame.font.SysFont('Arial', 20, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', 16, bold=False)
            self.font_small = pygame.font.SysFont('Arial', 14, bold=False)
        except:
            self.font_large = pygame.font.Font(None, 20)
            self.font_medium = pygame.font.Font(None, 16)
            self.font_small = pygame.font.Font(None, 14)
            
        # Button dimensions
        self.unit_button_height = 60
        self.button_width = self.width - 40
        
        # Callbacks
        self.on_unit_placed = None
        self.on_cancel = None
        
    def show(self, player, game, on_unit_placed_callback, on_cancel_callback):
        """Show the reserves arrival panel."""
        self.visible = True
        self.player = player
        self.game = game
        self.on_unit_placed = on_unit_placed_callback
        self.on_cancel = on_cancel_callback
        
        # Get units that can arrive from reserves
        self.available_units = [unit for unit in player.get_army().units if unit.can_arrive_from_reserves(game.turn)]
        
    def hide(self):
        """Hide the reserves arrival panel."""
        self.visible = False
        self.placement_mode = False
        self.selected_unit = None
        self.placement_position = None
        
    def handle_event(self, event):
        """Handle pygame events for the reserves arrival panel."""
        if not self.visible:
            return False
            
        if self.placement_mode:
            return self.handle_placement_event(event)
        else:
            return self.handle_selection_event(event)
            
    def handle_selection_event(self, event):
        """Handle events during unit selection."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.handle_selection_click(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True
                
        return True
        
    def handle_placement_event(self, event):
        """Handle events during unit placement."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click to place
                if self.placement_position and self.is_valid_placement(self.placement_position):
                    if self.on_unit_placed:
                        self.on_unit_placed(self.selected_unit, self.placement_position)
                    self.hide()
                    return True
            elif event.button == 3:  # Right click to cancel
                self.placement_mode = False
                self.selected_unit = None
                return True
                
        elif event.type == pygame.MOUSEMOTION:
            # Update placement position
            game_x, game_y = self.screen_to_game_coords(event.pos)
            self.placement_position = (game_x, game_y, 0.0)
            return True
            
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.placement_mode = False
                self.selected_unit = None
                return True
                
        return True
        
    def handle_selection_click(self, mouse_pos):
        """Handle mouse clicks during unit selection."""
        x, y = mouse_pos
        
        # Check unit buttons
        panel_x = 10  # Assume panel is positioned at left edge
        panel_y = 100  # Assume panel is positioned below other UI elements
        
        for i, unit in enumerate(self.available_units):
            unit_y = panel_y + 60 + i * (self.unit_button_height + 10)  # +60 for header
            unit_rect = pygame.Rect(panel_x + 20, unit_y, self.button_width, self.unit_button_height)
            
            if unit_rect.collidepoint(x, y):
                self.selected_unit = unit
                self.placement_mode = True
                return True
                
        # Check cancel button
        cancel_rect = pygame.Rect(panel_x + 20, panel_y + self.height - 50, 100, 30)
        if cancel_rect.collidepoint(x, y):
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True
            
        return True
        
    def screen_to_game_coords(self, screen_pos):
        """Convert screen coordinates to game coordinates."""
        # This would need to be implemented based on the game's coordinate system
        # For now, return the screen position as-is
        return screen_pos[0], screen_pos[1]
        
    def is_valid_placement(self, position):
        """Check if the placement position is valid for the selected unit."""
        if not self.selected_unit or not position:
            return False
            
        # Check reserves arrival rules
        if self.selected_unit.is_in_strategic_reserves():
            # Strategic reserves rules for board edge placement
            return self.is_valid_strategic_reserves_position(position)
        else:
            # Standard reserves (Deep Strike) rules
            return self.is_valid_deep_strike_position(position)
            
    def is_valid_strategic_reserves_position(self, position):
        """Check if position is valid for strategic reserves arrival."""
        # Must be within 6" of battlefield edge and more than 9" from enemies
        # This is a simplified check - full implementation would need game map
        return True
        
    def is_valid_deep_strike_position(self, position):
        """Check if position is valid for deep strike arrival."""
        # Must be more than 9" from enemy models
        # This is a simplified check - full implementation would need game map
        return True
        
    def draw(self, screen):
        """Draw the reserves arrival panel."""
        if not self.visible:
            return
            
        if self.placement_mode:
            self.draw_placement_mode(screen)
        else:
            self.draw_selection_mode(screen)
            
    def draw_selection_mode(self, screen):
        """Draw the unit selection interface."""
        panel_x = 10
        panel_y = 100
        panel_rect = pygame.Rect(panel_x, panel_y, self.width, self.height)
        
        # Draw panel background
        pygame.draw.rect(screen, PANEL_BG, panel_rect)
        pygame.draw.rect(screen, PANEL_BORDER, panel_rect, 2)
        
        # Draw header
        header_text = self.font_large.render("Reserves Arrival", True, TEXT_PRIMARY)
        screen.blit(header_text, (panel_x + 20, panel_y + 20))
        
        # Draw turn info
        turn_info = f"Turn {self.game.turn} - {self.player.name}"
        turn_text = self.font_medium.render(turn_info, True, TEXT_SECONDARY)
        screen.blit(turn_text, (panel_x + 20, panel_y + 45))
        
        # Draw units
        if not self.available_units:
            no_units_text = self.font_medium.render("No units available", True, TEXT_SECONDARY)
            screen.blit(no_units_text, (panel_x + 20, panel_y + 80))
        else:
            for i, unit in enumerate(self.available_units):
                unit_y = panel_y + 60 + i * (self.unit_button_height + 10)
                self.draw_reserves_unit_button(screen, unit, panel_x + 20, unit_y)
                
        # Draw cancel button
        cancel_rect = pygame.Rect(panel_x + 20, panel_y + self.height - 50, 100, 30)
        pygame.draw.rect(screen, BUTTON_BG, cancel_rect)
        pygame.draw.rect(screen, PANEL_BORDER, cancel_rect, 1)
        
        cancel_text = self.font_medium.render("Cancel", True, TEXT_PRIMARY)
        text_rect = cancel_text.get_rect(center=cancel_rect.center)
        screen.blit(cancel_text, text_rect)
        
    def draw_placement_mode(self, screen):
        """Draw the placement interface."""
        # Draw placement instructions
        instructions = [
            f"Placing {self.selected_unit.name}",
            "Left click to place unit",
            "Right click to cancel",
            "Must be >9\" from enemies"
        ]
        
        for i, instruction in enumerate(instructions):
            text = self.font_medium.render(instruction, True, TEXT_PRIMARY)
            screen.blit(text, (10, 10 + i * 25))
            
        # Draw placement preview if position is available
        if self.placement_position:
            self.draw_placement_preview(screen)
            
    def draw_placement_preview(self, screen):
        """Draw a preview of where the unit will be placed."""
        if not self.placement_position:
            return
            
        # Convert game coordinates to screen coordinates
        screen_x, screen_y = self.placement_position[0], self.placement_position[1]
        
        # Draw placement circle
        color = GREEN if self.is_valid_placement(self.placement_position) else RED
        pygame.draw.circle(screen, color, (int(screen_x), int(screen_y)), 30, 3)
        
        # Draw unit name
        name_text = self.font_medium.render(self.selected_unit.name, True, color)
        screen.blit(name_text, (int(screen_x) - 50, int(screen_y) - 50))
        
    def draw_reserves_unit_button(self, screen, unit, x, y):
        """Draw a button for a unit available from reserves."""
        unit_rect = pygame.Rect(x, y, self.button_width, self.unit_button_height)
        
        # Background color based on reserve type
        if unit.is_in_strategic_reserves():
            bg_color = STRATEGIC_RESERVES_BG
        else:
            bg_color = RESERVES_BUTTON_BG
            
        pygame.draw.rect(screen, bg_color, unit_rect)
        pygame.draw.rect(screen, PANEL_BORDER, unit_rect, 2)
        
        # Unit name
        name_text = self.font_medium.render(unit.name, True, TEXT_PRIMARY)
        screen.blit(name_text, (x + 10, y + 10))
        
        # Unit details
        reserve_type = "Strategic Reserves" if unit.is_in_strategic_reserves() else "Reserves"
        details = f"{reserve_type} • {len(unit.models)} models • {unit.get_unit_cost()} pts"
        details_text = self.font_small.render(details, True, TEXT_SECONDARY)
        screen.blit(details_text, (x + 10, y + 35))


class HumanUIInterface:
    """Interface class that bridges human UI components with the deployment system."""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # UI components
        self.deployment_choice_dialog = DeploymentChoiceDialog(screen_width, screen_height)
        self.reserves_dialog = ReservesSelectionDialog(screen_width, screen_height)
        self.reserves_arrival_panel = ReservesArrivalPanel()
        
        # State for handling UI interactions
        self.pending_reserves_callback = None
        self.pending_position_callback = None
        self.current_unit_for_placement = None
        self.current_deployment_zone = None
        self.placement_mode = False
        
    def choose_deployment_zone(self, available_zones: List[dict]) -> dict:
        """Human chooses deployment zone via UI."""
        # For now, return the first available zone
        # In a full implementation, this would show a zone selection dialog
        return available_zones[0]
    
    def declare_reserves(self, player) -> dict:
        """Human declares reserves via UI dialog."""
        
        # Set up the reserves selection dialog
        reserves_decisions = {}
        dialog_complete = False
        
        def on_reserves_complete(decisions):
            nonlocal reserves_decisions, dialog_complete
            reserves_decisions = decisions
            dialog_complete = True
        
        # Show the reserves dialog
        self.reserves_dialog.show(player, on_reserves_complete)
        
        # Wait for user input
        clock = pygame.time.Clock()
        while not dialog_complete and self.reserves_dialog.visible:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return {unit.name: 'deploy' for unit in player.get_army().units}
                
                # Let the dialog handle the event
                if self.reserves_dialog.handle_event(event):
                    continue
            
            # Draw the current screen (this would be called by the main game loop)
            # For now, we'll assume the screen is being drawn elsewhere
            
            clock.tick(60)
        
        return reserves_decisions if reserves_decisions else {unit.name: 'deploy' for unit in player.get_army().units}
    
    def choose_unit_deployment_position(self, unit: 'Unit', deployment_zone: dict, 
                                       already_deployed: List['Unit']) -> Tuple[float, float]:
        """Human chooses unit position via UI clicking."""
        
        # Set up for position selection
        self.current_unit_for_placement = unit
        self.current_deployment_zone = deployment_zone
        self.placement_mode = True
        
        selected_position = None
        position_selected = False
        
        print(f"Click on the battlefield to place {unit.name}")
        print(f"Deployment zone: X({deployment_zone['x_range'][0]:.1f} - {deployment_zone['x_range'][1]:.1f}), Y({deployment_zone['y_range'][0]:.1f} - {deployment_zone['y_range'][1]:.1f})")
        
        # Wait for position selection
        clock = pygame.time.Clock()
        while not position_selected and self.placement_mode:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    # Return center of deployment zone as default
                    x_center = (deployment_zone['x_range'][0] + deployment_zone['x_range'][1]) / 2
                    y_center = (deployment_zone['y_range'][0] + deployment_zone['y_range'][1]) / 2
                    return x_center, y_center
                
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # Convert screen coordinates to game coordinates
                    game_x, game_y = self.screen_to_game_coords(event.pos)
                    
                    # Check if position is within deployment zone
                    if self.is_position_in_zone(game_x, game_y, deployment_zone):
                        selected_position = (game_x, game_y)
                        position_selected = True
                        print(f"Unit {unit.name} will be placed at ({game_x:.1f}, {game_y:.1f})")
                    else:
                        print(f"Invalid position ({game_x:.1f}, {game_y:.1f}) - must be within deployment zone")
                
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    # Cancel and use center of deployment zone
                    x_center = (deployment_zone['x_range'][0] + deployment_zone['x_range'][1]) / 2
                    y_center = (deployment_zone['y_range'][0] + deployment_zone['y_range'][1]) / 2
                    selected_position = (x_center, y_center)
                    position_selected = True
                    print(f"Position selection cancelled, using center of deployment zone")
            
            clock.tick(60)
        
        self.placement_mode = False
        self.current_unit_for_placement = None
        self.current_deployment_zone = None
        
        return selected_position if selected_position else (
            (deployment_zone['x_range'][0] + deployment_zone['x_range'][1]) / 2,
            (deployment_zone['y_range'][0] + deployment_zone['y_range'][1]) / 2
        )
    
    def screen_to_game_coords(self, screen_pos: Tuple[int, int]) -> Tuple[float, float]:
        """Convert screen coordinates to game coordinates."""
        # This would need to account for zoom, pan, and coordinate system
        # For now, simplified conversion assuming 1:1 mapping
        x, y = screen_pos
        # Convert from screen pixels to game inches
        game_x = x / TILE_SIZE
        game_y = y / TILE_SIZE
        return game_x, game_y
    
    def is_position_in_zone(self, x: float, y: float, zone: dict) -> bool:
        """Check if a position is within the deployment zone."""
        x_min, x_max = zone['x_range']
        y_min, y_max = zone['y_range']
        return x_min <= x <= x_max and y_min <= y <= y_max
    
    def update(self, screen):
        """Update and draw UI components."""
        # Draw deployment choice dialog if visible (highest priority)
        if self.deployment_choice_dialog.visible:
            self.deployment_choice_dialog.draw(screen)
        
        if self.reserves_dialog.visible:
            self.reserves_dialog.draw(screen)
        
        if self.reserves_arrival_panel.visible:
            self.reserves_arrival_panel.draw(screen)
        
        # Draw placement indicator if in placement mode
        if self.placement_mode and self.current_unit_for_placement:
            self.draw_placement_indicator(screen)
    
    def draw_placement_indicator(self, screen):
        """Draw visual indicator for unit placement."""
        if not self.current_unit_for_placement or not self.current_deployment_zone:
            return
        
        # Draw deployment zone outline
        zone = self.current_deployment_zone
        x_min, x_max = zone['x_range']
        y_min, y_max = zone['y_range']
        
        # Convert to screen coordinates
        screen_x_min = int(x_min * TILE_SIZE)
        screen_y_min = int(y_min * TILE_SIZE)
        screen_width = int((x_max - x_min) * TILE_SIZE)
        screen_height = int((y_max - y_min) * TILE_SIZE)
        
        zone_rect = pygame.Rect(screen_x_min, screen_y_min, screen_width, screen_height)
        pygame.draw.rect(screen, TEXT_ACCENT, zone_rect, 3)
        
        # Draw unit name
        font = pygame.font.SysFont('Arial', 16, bold=True)
        text = font.render(f"Place {self.current_unit_for_placement.name}", True, TEXT_PRIMARY)
        screen.blit(text, (10, 10))
        
        # Draw instructions
        instr_font = pygame.font.SysFont('Arial', 14)
        instructions = [
            "Left click to place unit",
            "ESC to use center position",
            f"Must be in highlighted zone"
        ]
        
        for i, instruction in enumerate(instructions):
            instr_text = instr_font.render(instruction, True, TEXT_SECONDARY)
            screen.blit(instr_text, (10, 40 + i * 20))
    
    def handle_event(self, event):
        """Handle pygame events for all UI components."""
        handled = False
        
        # Let deployment choice dialog handle events first (highest priority)
        if self.deployment_choice_dialog.visible:
            handled = self.deployment_choice_dialog.handle_event(event)
        
        # Let reserves dialog handle events
        if not handled and self.reserves_dialog.visible:
            handled = self.reserves_dialog.handle_event(event)
        
        # Let reserves arrival panel handle events
        if not handled and self.reserves_arrival_panel.visible:
            handled = self.reserves_arrival_panel.handle_event(event)
        
        return handled


class GameView:
    def __init__(self, screen, env, game, game_map, player1, player2, ui_interface=None):
        self.screen = screen
        self.env = env
        self.game = game
        self.game_map = game_map
        self.player1 = player1
        self.player2 = player2
        self.selected_unit = None
        self.dragging_unit = None
        self.dragging = False
        self.drag_offset = (0, 0)
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.detailed_unit = None
        self.detail_panel_pos = (0, 0)
        self.unit_detail_panel = UnitDetailPanel()
        
        # UI interface for human player interaction
        self.ui_interface = ui_interface
        
        # Phase-based event handling system
        self.phase_manager = PhaseManager(self)
        
        # Mouse panning support
        self.panning = False
        self.pan_start_pos = (0, 0)
        self.pan_start_offset = (0, 0)
        
        # Create roster panes with reference to all units for color correlation
        # Roster panes now extend to full battlefield height + info pane height
        # Handle case where armies haven't been loaded yet (during setup phases)
        roster_pane_height = BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT
        player1_units = player1.get_army().units if player1.get_army() else []
        player2_units = player2.get_army().units if player2.get_army() else []
        
        self.left_roster_pane = RosterPane(0, 0, ROSTER_PANE_WIDTH, roster_pane_height, 
                                         player1_units, f"Player 1 ({player1.name})")
        self.right_roster_pane = RosterPane(BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH, 0, ROSTER_PANE_WIDTH, 
                                          roster_pane_height, player2_units, 
                                          f"Player 2 ({player2.name})")
        
        # Pass all units to roster panes for color correlation
        all_units = player1_units + player2_units
        self.left_roster_pane.all_units = all_units
        self.right_roster_pane.all_units = all_units
        
        # Set game_view reference in roster panes for deployment dialog
        self.left_roster_pane.game_view = self
        self.right_roster_pane.game_view = self
        
        # Position InfoPane between roster panes and below battlefield
        self.info_pane = InfoPane(ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT, 
                                BATTLEFIELD_WIDTH, INFO_PANE_HEIGHT, self.selected_unit)
    
    def refresh_roster_panes(self):
        """Refresh roster panes when armies are loaded during setup phases."""
        if self.player1 and self.player2:
            player1_units = self.player1.get_army().units if self.player1.get_army() else []
            player2_units = self.player2.get_army().units if self.player2.get_army() else []
            
            print(f"🔄 Refreshing roster panes: Player1 has {len(player1_units)} units, Player2 has {len(player2_units)} units")
            
            # Update roster units
            self.left_roster_pane.roster = player1_units
            self.right_roster_pane.roster = player2_units
            
            # Update player references
            self.left_roster_pane.player = self.player1
            self.right_roster_pane.player = self.player2
            
            # Update all_units for color correlation
            all_units = player1_units + player2_units
            self.left_roster_pane.all_units = all_units
            self.right_roster_pane.all_units = all_units
            
            # Reset scroll positions
            self.left_roster_pane.scroll_offset = 0
            self.right_roster_pane.scroll_offset = 0
            
            # Recreate buttons with new roster data
            self.left_roster_pane.create_buttons()
            self.right_roster_pane.create_buttons()
            
            print(f"✅ Roster panes refreshed successfully")
    
    def update_roster_pane_titles(self):
        """Update roster pane titles to show Attacker/Defender after roles are determined."""
        if self.game and hasattr(self.game, 'attacker_index') and self.game.attacker_index is not None:
            # Update player names to include role
            if self.game.attacker_index == 0:  # Player 1 is attacker
                self.left_roster_pane.player_name = f"{self.player1.name} (Attacker)"
                self.right_roster_pane.player_name = f"{self.player2.name} (Defender)"
            else:  # Player 2 is attacker
                self.left_roster_pane.player_name = f"{self.player1.name} (Defender)"
                self.right_roster_pane.player_name = f"{self.player2.name} (Attacker)"

    def handle_pygame_event(self, event):
        """Handle pygame events using phase-based routing."""
        # PRIORITY 1: Let phase manager handle phase-specific events first
        if self.phase_manager.handle_event(event):
            return True
        
        # PRIORITY 2: Handle universal UI events that apply to all phases
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Check for unit detail panel clicks (highest priority)
            if self.detailed_unit and event.button == 1:  # Left click
                if hasattr(self.unit_detail_panel, 'rect') and self.unit_detail_panel.rect:
                    if self.unit_detail_panel.rect.collidepoint(event.pos):
                        return True  # Consume the click on detail panel
                    else:
                        self.close_unit_details()
                        return True
            # Check for middle mouse button panning
            elif event.button == 2:  # Middle mouse button - start panning
                x, y = event.pos
                if ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH:
                    self.panning = True
                    self.pan_start_pos = (x, y)
                    self.pan_start_offset = (self.offset_x, self.offset_y)
                    return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.on_mouse_release(event.pos[0], event.pos[1], event.button)
        elif event.type == pygame.MOUSEMOTION:
            self.on_mouse_motion(event.pos[0], event.pos[1])
        elif event.type == pygame.MOUSEWHEEL:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            self.on_mouse_scroll(mouse_x, mouse_y, event.y)
        elif event.type == pygame.KEYDOWN:
            # Handle universal keyboard shortcuts
            if event.key == pygame.K_ESCAPE:
                # Close unit details panel if open
                if self.detailed_unit:
                    self.close_unit_details()
                    return True
            # Handle unit detail panel scrolling
            elif self.detailed_unit:
                if event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.unit_detail_panel.scroll(-30)  # Scroll up
                    return True
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    self.unit_detail_panel.scroll(30)   # Scroll down
                    return True
                elif event.key == pygame.K_PAGEUP:
                    self.unit_detail_panel.scroll(-150)  # Page up
                    return True
                elif event.key == pygame.K_PAGEDOWN:
                    self.unit_detail_panel.scroll(150)   # Page down
                    return True
                elif event.key == pygame.K_HOME:
                    self.unit_detail_panel.scroll_offset = 0  # Go to top
                    return True
                elif event.key == pygame.K_END:
                    self.unit_detail_panel.scroll_offset = self.unit_detail_panel.max_scroll  # Go to bottom
                    return True
        
        return False

    # Note: on_mouse_press is now handled by phase-specific handlers in PhaseManager

    def on_mouse_release(self, x, y, button):
        """Handle mouse button release events"""
        if button == 2:  # Middle mouse button - stop panning
            self.panning = False

    def on_mouse_motion(self, x, y):
        """Handle mouse motion events"""
        if self.panning:
            # Calculate pan delta
            dx = x - self.pan_start_pos[0]
            dy = y - self.pan_start_pos[1]
            
            # Apply panning with sensitivity adjustment
            self.offset_x = self.pan_start_offset[0] + dx * MOUSE_PAN_SPEED
            self.offset_y = self.pan_start_offset[1] + dy * MOUSE_PAN_SPEED
            
            # Apply panning limits
            self.offset_x, self.offset_y = self._apply_pan_limits(self.offset_x, self.offset_y)
        
        # Update hover state for info pane
        self.info_pane.update_hover(x, y)

    def on_mouse_scroll(self, x, y, scroll_y):
        """Handle mouse scroll events"""
        # PRIORITY 1: Check if scrolling in unit detail panel first (highest priority)
        if self.detailed_unit:
            # Use the rect that was set during drawing (if it exists)
            if hasattr(self.unit_detail_panel, 'rect') and self.unit_detail_panel.rect:
                # Check if mouse is over the unit detail panel using the actual rect
                if self.unit_detail_panel.rect.collidepoint(x, y):
                    self.unit_detail_panel.scroll(-scroll_y * 30)  # Scroll speed
                    return  # CRITICAL: Exit early to prevent other panels from handling the event
        
        # PRIORITY 2: Only check roster panes if unit detail panel didn't handle the event
        if self.left_roster_pane.rect.collidepoint(x, y):
            self.left_roster_pane.scroll(-scroll_y * 30)  # Scroll speed
        elif self.right_roster_pane.rect.collidepoint(x, y):
            self.right_roster_pane.scroll(-scroll_y * 30)
        
        # PRIORITY 3: Handle battlefield panning with Shift+Scroll (alternative to middle mouse)
        elif ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
                # Horizontal panning with Shift+Scroll
                pan_delta = scroll_y * 20 * MOUSE_PAN_SPEED
                self.offset_x += pan_delta
                self.offset_x, self.offset_y = self._apply_pan_limits(self.offset_x, self.offset_y)
            elif keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
                # Vertical panning with Ctrl+Scroll
                pan_delta = scroll_y * 20 * MOUSE_PAN_SPEED
                self.offset_y += pan_delta
                self.offset_x, self.offset_y = self._apply_pan_limits(self.offset_x, self.offset_y)

    def reset_unit_position(self, unit, original_unit_position, original_model_positions):
        if original_unit_position:
            unit.set_position(original_unit_position[0], original_unit_position[1], original_unit_position[2])
            for model, original_position in zip(unit.models, original_model_positions):
                model.set_location(*original_position)
        else:
            unit.position = None

    def get_hovered_unit(self, x, y):
        # Check if hovering over a unit in the roster panes
        hovered_unit = self.left_roster_pane.get_hovered_unit(x, y)
        if hovered_unit:
            return hovered_unit, self.left_roster_pane
        
        hovered_unit = self.right_roster_pane.get_hovered_unit(x, y)
        if hovered_unit:
            return hovered_unit, self.right_roster_pane
        
        # Check if hovering over a model on the battlefield
        if ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH:
            battlefield_x = (x - ROSTER_PANE_WIDTH) / TILE_SIZE / self.zoom_level - self.offset_x / TILE_SIZE
            battlefield_y = y / TILE_SIZE / self.zoom_level - self.offset_y / TILE_SIZE
            
            # Create a point for the mouse position
            from shapely.geometry import Point
            mouse_point = Point(battlefield_x, battlefield_y)
            
            # Check all models in all units
            for unit in self.game_map.units:
                for model in unit.models:
                    if not model.is_alive:
                        continue
                    # Get the model's base shape and check if mouse point is inside
                    model_shape = model.model_base.get_base_shape()
                    if model_shape.contains(mouse_point):
                        # Use the model's parent_unit to get the unit reference
                        parent_unit = model.parent_unit
                        # Determine which roster the unit belongs to (only if armies are loaded)
                        if (self.player1.get_army() and self.player1.get_army().units and 
                            parent_unit in self.player1.get_army().units):
                            return parent_unit, self.left_roster_pane
                        elif (self.player2.get_army() and self.player2.get_army().units and 
                              parent_unit in self.player2.get_army().units):
                            return parent_unit, self.right_roster_pane
        
        return None, None

    def get_unit_at_position(self, x: float, y: float) -> Optional[Unit]:
        # Convert screen coordinates to game coordinates
        game_x = (x - ROSTER_PANE_WIDTH - self.offset_x) / (TILE_SIZE * self.zoom_level)
        game_y = (y - self.offset_y) / (TILE_SIZE * self.zoom_level)
        
        print(f"Checking for model at game coordinates: ({game_x}, {game_y})")

        # Create a point for the game position
        from shapely.geometry import Point
        game_point = Point(game_x, game_y)

        for player in [self.player1, self.player2]:
            if player.get_army() and player.get_army().units:
                for unit in [unit for unit in player.get_army().units if unit.deployed]:
                    for model in unit.models:
                        if not model.is_alive:
                            continue
                        # Get the model's base shape and check if game point is inside
                        model_shape = model.model_base.get_base_shape()
                        if model_shape.contains(game_point):
                            # Use the model's parent_unit to get the unit reference
                            print(f"Found model {model.name} from unit {model.parent_unit.name}")
                            return model.parent_unit
        
        print("No model found at position")
        return None
    
    def get_model_at_position(self, x: float, y: float) -> Optional['Model']:
        """Get the specific model at the given position"""
        # Convert screen coordinates to game coordinates
        game_x = (x - ROSTER_PANE_WIDTH - self.offset_x) / (TILE_SIZE * self.zoom_level)
        game_y = (y - self.offset_y) / (TILE_SIZE * self.zoom_level)
        
        print(f"Checking for model at game coordinates: ({game_x}, {game_y})")

        # Create a point for the game position
        from shapely.geometry import Point
        game_point = Point(game_x, game_y)

        for player in [self.player1, self.player2]:
            if player.get_army() and player.get_army().units:
                for unit in [unit for unit in player.get_army().units if unit.deployed]:
                    for model in unit.models:
                        if not model.is_alive:
                            continue
                        # Get the model's base shape and check if game point is inside
                        model_shape = model.model_base.get_base_shape()
                        if model_shape.contains(game_point):
                            print(f"Found model {model.name} from unit {model.parent_unit.name}")
                            return model
        
        print("No model found at position")
        return None

    def draw_move_path(self, unit: Unit):
        for model in unit.models:
            if not model.last_move_path:
                return

            # Convert game coordinates to screen coordinates
            screen_path = [self.game_to_screen_coords(*point[:2]) for point in model.last_move_path]

            # Draw the path
            pygame.draw.lines(self.screen, (0, 0, 255), False, screen_path, 2)

            # Draw start and end points
            start_point = screen_path[0]
            end_point = screen_path[-1]
            pygame.draw.circle(self.screen, (0, 255, 0), start_point, 5)  # Start point in green
            pygame.draw.circle(self.screen, (255, 0, 0), end_point, 5)  # End point in red

            # Draw direction arrows
            for i in range(len(screen_path) - 1):
                mid_point = ((screen_path[i][0] + screen_path[i+1][0]) // 2,
                            (screen_path[i][1] + screen_path[i+1][1]) // 2)
                pygame.draw.circle(self.screen, (255, 0, 0), mid_point, 3)  # Small red dot for direction

    def game_to_screen_coords(self, x: float, y: float) -> Tuple[int, int]:
        # Convert game coordinates to screen coordinates
        screen_x = int(ROSTER_PANE_WIDTH + (x * TILE_SIZE * self.zoom_level) + self.offset_x)
        screen_y = int(y * TILE_SIZE * self.zoom_level + self.offset_y)
        return (screen_x, screen_y)
    
    def screen_to_game_coords(self, screen_pos: Tuple[int, int]) -> Tuple[float, float]:
        """Convert screen coordinates to game coordinates"""
        x, y = screen_pos
        # Convert from screen coordinates to game coordinates
        # Account for roster pane width, zoom level, and pan offset
        game_x = (x - ROSTER_PANE_WIDTH - self.offset_x) / (TILE_SIZE * self.zoom_level)
        game_y = (y - self.offset_y) / (TILE_SIZE * self.zoom_level)
        return game_x, game_y

    def draw(self):
        self.screen.fill(DARK_GREY)
    
        # Draw roster panes with enhanced styling
        self.left_roster_pane.draw(self.screen, self.game)
        self.right_roster_pane.draw(self.screen, self.game)

        # Draw the battlefield
        battlefield_surface = pygame.Surface((BATTLEFIELD_WIDTH, BATTLEFIELD_HEIGHT))
        draw_battlefield(battlefield_surface, self.zoom_level, self.offset_x, self.offset_y)

        # Draw obstacles on the battlefield
        for obstacle in self.game_map.obstacles:
            draw_obstacle(battlefield_surface, obstacle, self.zoom_level, self.offset_x, self.offset_y)

        # Draw deployment zones (with transparency)
        if hasattr(self.game, 'deployment_zones') and self.game.deployment_zones:
            draw_deployment_zones(battlefield_surface, self.game.deployment_zones, self.player1, self.player2, 
                                self.zoom_level, self.offset_x, self.offset_y)

        # Draw objectives on the battlefield
        for objective in self.game_map.objectives:
            draw_objective(battlefield_surface, objective, self.zoom_level, self.offset_x, self.offset_y)

        # Draw units on the battlefield
        for unit in self.game_map.units:
            draw_units(battlefield_surface, unit, self.zoom_level, self.offset_x, self.offset_y, pygame.mouse.get_pos(), self.player1, self.player2)
        
        # Draw movement range indicator if a unit is selected for movement
        if (hasattr(self, 'selected_unit_for_movement') and 
            self.selected_unit_for_movement and 
            hasattr(self, 'movement_action') and 
            self.movement_action):
            advance_roll = getattr(self, 'advance_roll', None)
            selected_model = getattr(self, 'selected_model_for_movement', None)
            draw_movement_range(battlefield_surface, self.selected_unit_for_movement, 
                              self.movement_action, self.zoom_level, self.offset_x, self.offset_y, advance_roll, selected_model)
        
        # Draw weapon range indicator if a unit is selected for shooting
        if (hasattr(self, 'selected_unit') and self.selected_unit and 
            hasattr(self, 'selected_weapon_profile') and self.selected_weapon_profile):
            draw_weapon_ranges(battlefield_surface, self.selected_unit, 
                             self.selected_weapon_profile, self.zoom_level, self.offset_x, self.offset_y)
        
        # Draw weapon range for shooting declaration dialog if in targeting mode
        if (hasattr(self, 'shooting_declaration_dialog') and 
            self.shooting_declaration_dialog.is_targeting_mode and
            self.shooting_declaration_dialog.current_weapon_for_targeting):
            draw_weapon_ranges(battlefield_surface, self.shooting_declaration_dialog.unit, 
                             self.shooting_declaration_dialog.current_weapon_for_targeting, 
                             self.zoom_level, self.offset_x, self.offset_y)
        
        self.screen.blit(battlefield_surface, (ROSTER_PANE_WIDTH, 0))

        # Draw enhanced InfoPane
        self.info_pane.draw(self.screen, self.game, self)

        # Draw unit details panel if requested
        if self.detailed_unit:
            self.unit_detail_panel.draw(self.screen, self.detailed_unit, 
                                      self.detail_panel_pos[0], self.detail_panel_pos[1])

        # Draw move paths for all units (only if armies are loaded)
        current_player = self.game.get_current_player()
        if current_player and current_player.get_army() and current_player.get_army().units:
            for unit in current_player.get_army().units:
                self.draw_move_path(unit)

        # Draw UI interface components (reserves dialogs, etc.)
        if self.ui_interface:
            self.ui_interface.update(self.screen)
        
        # Draw movement choice dialog if visible
        if hasattr(self, 'movement_choice_dialog') and self.movement_choice_dialog.visible:
            self.movement_choice_dialog.draw(self.screen)
        
        # Draw weapon choice dialog if visible
        if hasattr(self, 'weapon_choice_dialog') and self.weapon_choice_dialog.visible:
            self.weapon_choice_dialog.draw(self.screen)
        
        # Draw shooting declaration dialog
        if hasattr(self, 'shooting_declaration_dialog') and self.shooting_declaration_dialog.visible:
            self.shooting_declaration_dialog.draw(self.screen)

        pygame.display.update()

    # Note: on_key_press is now handled by phase-specific handlers in PhaseManager
    # Detail panel scrolling is still handled in handle_pygame_event for universal access
    
    def force_complete_deployment(self):
        """Force complete the deployment phase by auto-deploying remaining units"""
        self.game.complete_deployment_phase()
        
        # Clear any selected units
        self.selected_unit = None
        self.left_roster_pane.selected_unit = None
        self.right_roster_pane.selected_unit = None
        
        print("Deployment phase completed! Press SPACE to start the game.")

    def close_unit_details(self):
        """Close the unit details panel"""
        self.detailed_unit = None
        # Reset scroll position when closing
        self.unit_detail_panel.scroll_offset = 0

    def _apply_pan_limits(self, offset_x: int, offset_y: int) -> Tuple[int, int]:
        """Apply panning limits to prevent moving outside the battlefield"""
        # Limit panning to prevent moving outside the grid
        max_offset_x = max(0, int(BATTLEFIELD_WIDTH * self.zoom_level) - BATTLEFIELD_WIDTH)
        max_offset_y = max(0, int(BATTLEFIELD_HEIGHT * self.zoom_level) - BATTLEFIELD_HEIGHT)
        limited_offset_x = max(-max_offset_x, min(0, offset_x))
        limited_offset_y = max(-max_offset_y, min(0, offset_y))
        return limited_offset_x, limited_offset_y

    def get_phase_status(self) -> dict:
        """Get current phase status and allowed actions for debugging/testing"""
        if hasattr(self, 'phase_manager'):
            current_handler = self.phase_manager.get_current_handler()
            return {
                'current_phase': type(current_handler).__name__,
                'game_phase': self.game.phase.name if hasattr(self.game.phase, 'name') else str(self.game.phase),
                'setup_phase': self.game.get_current_setup_phase().name if self.game.is_in_setup_phase() else None,
                'is_deployment': self.game.is_deployment_phase(),
                'allowed_actions': self.phase_manager.get_current_allowed_actions()
            }
        else:
            return {'error': 'Phase manager not initialized'}


### Battlefield drawing functions
def draw_battlefield(screen: pygame.Surface, zoom_level: float, offset_x: int, offset_y: int) -> None:
    screen.fill(WHITE)
    tile_size = int(TILE_SIZE * zoom_level)
    
    # Calculate the visible area
    visible_width = BATTLEFIELD_WIDTH
    visible_height = BATTLEFIELD_HEIGHT
    
    # Calculate the range of tiles to draw
    start_x = max(0, int(-offset_x / tile_size))
    end_x = min(BATTLEFIELD_WIDTH_INCHES, int((visible_width - offset_x) / tile_size) + 1)
    start_y = max(0, int(-offset_y / tile_size))
    end_y = min(BATTLEFIELD_HEIGHT_INCHES, int((visible_height - offset_y) / tile_size) + 1)
    
    # Draw vertical lines
    for x in range(start_x, end_x + 1):
        screen_x = int(x * tile_size + offset_x)
        if 0 <= screen_x < visible_width:
            pygame.draw.line(screen, GREY, (screen_x, 0), (screen_x, visible_height))
    
    # Draw horizontal lines
    for y in range(start_y, end_y + 1):
        screen_y = int(y * tile_size + offset_y)
        if 0 <= screen_y < visible_height:
            pygame.draw.line(screen, GREY, (0, screen_y), (visible_width, screen_y))
    
    # Draw battlefield border
    pygame.draw.rect(screen, RED, (0, 0, visible_width, visible_height), 2)

def draw_obstacle(screen: pygame.Surface, obstacle: Obstacle, zoom_level: float, offset_x: int, offset_y: int) -> None:
    # Determine the color based on the obstacle type
    if obstacle.terrain_type == ObstacleType.CRATER_AND_RUBBLE:
        color = (128, 0, 0, 180)  # Dark red for craters
    elif obstacle.terrain_type == ObstacleType.DEBRIS_AND_STATUARY:
        color = (192, 192, 192, 180)  # Gray for debris and statuary
    elif obstacle.terrain_type == ObstacleType.HILLS_AND_SEALED_BUILDINGS:
        color = (128, 64, 0, 180)  # Brown for hills and sealed buildings
    elif obstacle.terrain_type == ObstacleType.WOODS:
        color = (0, 128, 0, 180)  # Green for woods
    elif obstacle.terrain_type == ObstacleType.RUINS:
        color = (128, 128, 128, 180)  # Gray for ruins
    else:
        color = (255, 255, 255, 180)  # Default white

    # Convert vertices to screen coordinates
    screen_vertices = [
        (int((vertex[0] * TILE_SIZE) * zoom_level + offset_x),
         int((vertex[1] * TILE_SIZE) * zoom_level + offset_y))
        for vertex in obstacle.vertices
    ]

    # Draw the filled polygon
    pygame.draw.polygon(screen, color, screen_vertices)

    # Draw the outline of the polygon
    pygame.draw.polygon(screen, (0, 0, 0), screen_vertices, 2)  # Black outline with 2px width

def draw_deployment_zones(screen: pygame.Surface, deployment_zones: dict, player1: Player, player2: Player, 
                         zoom_level: float, offset_x: int, offset_y: int) -> None:
    """Draw deployment zones with transparency and appropriate colors for each player."""
    for player_name, zone in deployment_zones.items():
        # Determine player color with more vibrant colors during deployment
        if player_name == player1.name:
            color = (0, 255, 0, 160)  # More visible green for player 1
            border_color = (0, 200, 0)
        elif player_name == player2.name:
            color = (255, 0, 0, 160)  # More visible red for player 2
            border_color = (200, 0, 0)
        else:
            color = (128, 128, 128, 160)  # Semi-transparent gray for unknown players
            border_color = (100, 100, 100)
        
        # Extract zone coordinates
        x_start, x_end = zone['x_range']
        y_start, y_end = zone['y_range']
        
        # Convert to screen coordinates
        screen_x_start = int(x_start * TILE_SIZE * zoom_level + offset_x)
        screen_y_start = int(y_start * TILE_SIZE * zoom_level + offset_y)
        screen_x_end = int(x_end * TILE_SIZE * zoom_level + offset_x)
        screen_y_end = int(y_end * TILE_SIZE * zoom_level + offset_y)
        
        # Calculate width and height
        zone_width = screen_x_end - screen_x_start
        zone_height = screen_y_end - screen_y_start
        
        # Skip drawing if zone is off-screen or invalid
        if zone_width <= 0 or zone_height <= 0:
            continue
        
        # Create a surface with per-pixel alpha for transparency
        zone_surface = pygame.Surface((zone_width, zone_height), pygame.SRCALPHA)
        zone_surface.fill(color)
        
        # Blit the transparent zone onto the battlefield
        screen.blit(zone_surface, (screen_x_start, screen_y_start))
        
        # Draw a thicker border around the deployment zone for better visibility
        pygame.draw.rect(screen, border_color, 
                        (screen_x_start, screen_y_start, zone_width, zone_height), 4)
        
        # Draw corner markers for extra visibility
        corner_size = max(8, int(8 * zoom_level))
        corners = [
            (screen_x_start, screen_y_start),  # Top-left
            (screen_x_end - corner_size, screen_y_start),  # Top-right
            (screen_x_start, screen_y_end - corner_size),  # Bottom-left
            (screen_x_end - corner_size, screen_y_end - corner_size)  # Bottom-right
        ]
        
        for corner_x, corner_y in corners:
            pygame.draw.rect(screen, border_color, 
                           (corner_x, corner_y, corner_size, corner_size))
        
        # Add zone label with better positioning
        font = pygame.font.SysFont('Arial', max(14, int(16 * zoom_level)), bold=True)
        label_text = f"{player_name} Deployment Zone"
        text_surface = font.render(label_text, True, border_color)
        
        # Position label at the center-top of the zone for better visibility
        label_x = screen_x_start + (zone_width - text_surface.get_width()) // 2
        label_y = screen_y_start + 15
        
        # Draw a more prominent background for the text
        text_bg = pygame.Surface((text_surface.get_width() + 12, text_surface.get_height() + 6), pygame.SRCALPHA)
        text_bg.fill((255, 255, 255, 220))  # More opaque white background
        screen.blit(text_bg, (label_x - 6, label_y - 3))
        
        # Draw black outline for better text visibility
        outline_positions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        for dx, dy in outline_positions:
            outline_surface = font.render(label_text, True, (0, 0, 0))
            screen.blit(outline_surface, (label_x + dx, label_y + dy))
        
        # Draw the main text
        screen.blit(text_surface, (label_x, label_y))

def draw_objective(screen: pygame.Surface, objective: Objective, zoom_level: float, offset_x: int, offset_y: int) -> None:
    if isinstance(objective.location, ObjectivePoint):
        pygame.draw.circle(screen, PURPLE, (int(objective.location.x * TILE_SIZE * zoom_level + offset_x), int(objective.location.y * TILE_SIZE * zoom_level + offset_y)), int(objective.location.control_radius * TILE_SIZE * zoom_level))

def draw_units(screen: pygame.Surface, unit: Unit, zoom_level: float, offset_x: int, offset_y: int, mouse_pos: Tuple[int, int], player1: Player, player2: Player) -> None:
    # Determine the color based on which player the unit belongs to (only if armies are loaded)
    color = BLUE  # Default color
    if (player1.get_army() and player1.get_army().units and unit in player1.get_army().units):
        color = GREEN
    elif (player2.get_army() and player2.get_army().units and unit in player2.get_army().units):
        color = RED
    
    # Get all units for color variation calculation (only if armies are loaded)
    all_units = []
    if player1.get_army() and player1.get_army().units:
        all_units.extend(player1.get_army().units)
    if player2.get_army() and player2.get_army().units:
        all_units.extend(player2.get_army().units)

    for model_index, model in enumerate(unit.models):
        x, y = model.get_location()[:2]
        screen_x = int((x * TILE_SIZE) * zoom_level + offset_x)
        screen_y = int((y * TILE_SIZE) * zoom_level + offset_y)
        base = model.model_base
        
        draw_enhanced_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model)
        
        # Draw facing direction with enhanced styling
        draw_facing_direction(screen, base, screen_x, screen_y, zoom_level)
        
        # Draw large prominent icon that overlays the facing arrow
        draw_prominent_unit_icon(screen, screen_x, screen_y, base, zoom_level, unit, model, model_index, all_units)
    
    # Calculate and draw unit bounding box
    draw_unit_bounding_box(screen, unit, zoom_level, offset_x, offset_y, mouse_pos)

def draw_prominent_unit_icon(screen: pygame.Surface, center_x: int, center_y: int, base: Base, zoom_level: float, unit: Unit, model: Model, model_index: int, all_units: List[Unit]) -> None:
    """Draw a large, prominent icon that overlays the facing direction"""
    # Calculate icon size - larger and with minimum size
    base_radius = int(base.get_radius() * TILE_SIZE * zoom_level)
    icon_size = max(ICON_MIN_SIZE, int(base_radius * ICON_SCALE_FACTOR))
    
    # Get unit-specific color variation
    icon_tint = get_unit_color_variation(unit, all_units)
    
    # Draw semi-transparent background circle for better visibility
    bg_radius = icon_size // 2 + 4
    bg_surface = pygame.Surface((bg_radius * 2, bg_radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(bg_surface, (0, 0, 0, 100), (bg_radius, bg_radius), bg_radius)
    screen.blit(bg_surface, (center_x - bg_radius, center_y - bg_radius))
    
    # Draw the unit type icon with color tinting and rotation
    draw_rotated_tinted_unit_icon(screen, center_x, center_y, icon_size, unit, icon_tint, base.facing)
    
    # For multi-model units, draw individual model identifier
    if len(unit.models) > 1:
        draw_model_identifier(screen, center_x, center_y, icon_size, model_index, unit)
    
    # Draw wound indicator if model is damaged
    if not model.is_max_health:
        draw_prominent_wound_indicator(screen, center_x, center_y, icon_size, model)

def draw_rotated_tinted_unit_icon(screen: pygame.Surface, center_x: int, center_y: int, size: int, unit: Unit, tint_color: Tuple[int, int, int], angle: float) -> None:
    """Draw unit icon with color tinting and rotation based on facing direction"""
    # Create a surface for the icon with alpha - make it larger for rotation
    icon_surface = pygame.Surface((size * 3, size * 3), pygame.SRCALPHA)
    icon_center = size * 3 // 2  # Center of the larger icon surface
    
    # Draw the base icon on the surface - prioritize more distinctive unit types
    # Priority order: Vehicle > Monster > Aircraft > Beast > Psyker > Battleline > Character > Generic
    if unit.is_vehicle:
        draw_vehicle_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_monster:
        draw_monster_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_aircraft:
        draw_aircraft_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_beast:
        draw_beast_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_psyker:
        draw_psyker_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_battleline:
        draw_battleline_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_character:
        draw_character_icon(icon_surface, icon_center, icon_center, size)
    else:
        draw_generic_icon(icon_surface, icon_center, icon_center, size)
    
    # Apply color tint if it's not the default white
    if tint_color != (255, 255, 255):
        # Create tint overlay
        tint_surface = pygame.Surface((size * 3, size * 3), pygame.SRCALPHA)
        tint_surface.fill((*tint_color, 120))  # Semi-transparent tint
        icon_surface.blit(tint_surface, (0, 0), special_flags=pygame.BLEND_MULT)
    
    # Rotate the icon surface based on the model's facing direction
    angle_degrees = math.degrees(angle)
    rotated_surface = pygame.transform.rotate(icon_surface, -angle_degrees)  # Negative for correct rotation
    
    # Calculate the position to blit the rotated surface (centered)
    blit_x = center_x - rotated_surface.get_width() // 2
    blit_y = center_y - rotated_surface.get_height() // 2
    
    # Blit the rotated icon to the screen
    screen.blit(rotated_surface, (blit_x, blit_y))

def draw_tinted_unit_icon(screen: pygame.Surface, center_x: int, center_y: int, size: int, unit: Unit, tint_color: Tuple[int, int, int]) -> None:
    """Draw unit icon with color tinting (backward compatibility function for roster)"""
    # Just call the rotated version with 0 rotation for backward compatibility
    draw_rotated_tinted_unit_icon(screen, center_x, center_y, size, unit, tint_color, 0.0)

def draw_model_identifier(screen: pygame.Surface, center_x: int, center_y: int, icon_size: int, model_index: int, unit: Unit) -> None:
    """Draw individual model identifier for multi-model units"""
    # Position the identifier at the top-right of the icon with more offset
    identifier_size = max(12, icon_size // 3)
    identifier_x = center_x + icon_size // 2 - identifier_size // 4  # More to the right
    identifier_y = center_y - icon_size // 2 + identifier_size // 4  # More up
    
    # Draw background circle
    pygame.draw.circle(screen, (255, 255, 255), (identifier_x, identifier_y), identifier_size // 2 + 2)
    pygame.draw.circle(screen, (0, 0, 0), (identifier_x, identifier_y), identifier_size // 2 + 2, 2)
    
    # Draw model number (1-indexed for user friendliness)
    font_size = max(10, identifier_size)
    font = pygame.font.Font(None, font_size)
    model_number = str(model_index + 1)
    text_surface = font.render(model_number, True, (0, 0, 0))
    text_rect = text_surface.get_rect(center=(identifier_x, identifier_y))
    screen.blit(text_surface, text_rect)

def draw_prominent_wound_indicator(screen: pygame.Surface, center_x: int, center_y: int, icon_size: int, model: Model) -> None:
    """Draw a prominent wound indicator for damaged models"""
    if model.is_max_health:
        return
    
    # Position at bottom of icon
    indicator_y = center_y + icon_size // 2 + 8
    
    # Larger background for better visibility
    bg_width = max(30, icon_size // 2)
    bg_height = 14
    bg_rect = pygame.Rect(center_x - bg_width // 2, indicator_y - bg_height // 2, bg_width, bg_height)
    
    # Background with strong contrast
    pygame.draw.rect(screen, (0, 0, 0), bg_rect, border_radius=4)
    pygame.draw.rect(screen, (255, 255, 255), bg_rect, 2, border_radius=4)
    
    # Wound text with larger font
    font_size = max(12, int(14))
    font = pygame.font.Font(None, font_size)
    wound_text = f"{model.wounds}/{model._base_wounds}"
    
    # Color based on health level
    health_percent = model.health_percent
    if health_percent < 25:
        text_color = (255, 100, 100)  # Light red
    elif health_percent < 50:
        text_color = (255, 200, 100)  # Light orange
    elif health_percent < 75:
        text_color = (255, 255, 100)  # Light yellow
    else:
        text_color = (100, 255, 100)  # Light green
    
    text_surface = font.render(wound_text, True, text_color)
    text_rect = text_surface.get_rect(center=(center_x, indicator_y))
    screen.blit(text_surface, text_rect)

def draw_unit_identification(screen: pygame.Surface, screen_x: int, screen_y: int, radius: int, unit: Unit, model: Model, zoom_level: float) -> None:
    """Draw unit identification elements for circular bases - now simplified since we have prominent icons"""
    # This function is now mainly for the health indicator ring
    draw_health_indicator(screen, screen_x, screen_y, radius, model)

def draw_unit_identification_on_surface(surface: pygame.Surface, center_x: int, center_y: int, radius: int, unit: Unit, model: Model, zoom_level: float) -> None:
    """Draw unit identification elements on a surface - now simplified since we have prominent icons"""
    # This function is now mainly for the health indicator ring
    # Note: Health indicator is drawn separately for surface-based rendering
    pass

def draw_model_count_indicator(surface: pygame.Surface, center_x: int, center_y: int, radius: int, unit: Unit) -> None:
    """Draw a small indicator showing model count for multi-model units - now unused since we show individual model numbers"""
    # This function is now unused but kept for compatibility
    pass

def draw_enhanced_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model) -> None:
    """Enhanced base drawing with unit identification features"""
    if base.base_type == BaseType.CIRCULAR:
        draw_enhanced_circular_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model)
    elif base.base_type == BaseType.ELLIPTICAL:
        draw_enhanced_elliptical_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model)
    elif base.base_type == BaseType.HULL:
        draw_enhanced_hull_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model)

def draw_enhanced_circular_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model) -> None:
    """Enhanced circular base with unit identification"""
    radius = int(base.get_radius() * TILE_SIZE * zoom_level)
    
    # Draw outer ring with gradient effect
    pygame.draw.circle(screen, color, (screen_x, screen_y), radius)
    
    # Draw inner area with unit-specific styling - scale properly with zoom
    inner_radius = max(1, int(radius * 0.85))
    inner_color = get_unit_inner_color(unit, model)
    pygame.draw.circle(screen, inner_color, (screen_x, screen_y), inner_radius)
    
    # Add unit identification elements
    draw_unit_identification(screen, screen_x, screen_y, radius, unit, model, zoom_level)

def draw_enhanced_elliptical_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model) -> None:
    """Enhanced elliptical base with unit identification"""
    width = int(base.radius[0] * 2 * TILE_SIZE * zoom_level)
    height = int(base.radius[1] * 2 * TILE_SIZE * zoom_level)
    
    # Ensure minimum size for visibility
    width = max(4, width)
    height = max(4, height)
    
    # Create a surface for the ellipse
    ellipse_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    ellipse_surface.fill((0, 0, 0, 0))  # Transparent background
    
    # Draw the outer ellipse
    pygame.draw.ellipse(ellipse_surface, color, (0, 0, width, height))
    
    # Draw the inner ellipse with unit-specific styling - scale properly with zoom
    inner_width, inner_height = max(1, int(width * 0.85)), max(1, int(height * 0.85))
    inner_rect = pygame.Rect((width - inner_width) // 2, (height - inner_height) // 2, inner_width, inner_height)
    inner_color = get_unit_inner_color(unit, model)
    pygame.draw.ellipse(ellipse_surface, inner_color, inner_rect)
    
    # Add unit identification on the surface before rotation
    draw_unit_identification_on_surface(ellipse_surface, width//2, height//2, min(width, height)//2, unit, model, zoom_level)
    
    # Rotate the surface
    angle_degrees = math.degrees(base.facing)
    rotated_surface = pygame.transform.rotate(ellipse_surface, -angle_degrees)
    
    # Calculate the position to blit the rotated surface
    blit_pos = (screen_x - rotated_surface.get_width() // 2, 
                screen_y - rotated_surface.get_height() // 2)
    
    # Blit the rotated surface onto the screen
    screen.blit(rotated_surface, blit_pos)

def draw_enhanced_hull_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model) -> None:
    """Enhanced hull base with unit identification"""
    width = int(base.radius[0] * 2 * TILE_SIZE * zoom_level)
    height = int(base.radius[1] * 2 * TILE_SIZE * zoom_level)
    
    # Ensure minimum size for visibility
    width = max(4, width)
    height = max(4, height)
    
    # Create a surface for the hull
    hull_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    hull_surface.fill((0, 0, 0, 0))  # Transparent background
    
    # Draw the outer hull
    pygame.draw.rect(hull_surface, color, (0, 0, width, height))
    
    # Draw the inner hull with unit-specific styling - scale properly with zoom
    inner_width, inner_height = max(1, int(width * 0.85)), max(1, int(height * 0.85))
    inner_rect = pygame.Rect((width - inner_width) // 2, (height - inner_height) // 2, inner_width, inner_height)
    inner_color = get_unit_inner_color(unit, model)
    pygame.draw.rect(hull_surface, inner_color, inner_rect)
    
    # Add unit identification on the surface before rotation
    draw_unit_identification_on_surface(hull_surface, width//2, height//2, min(width, height)//2, unit, model, zoom_level)
    
    # Rotate the surface
    angle_degrees = math.degrees(base.facing)
    rotated_surface = pygame.transform.rotate(hull_surface, -angle_degrees)
    
    # Calculate the position to blit the rotated surface
    blit_pos = (screen_x - rotated_surface.get_width() // 2, 
                screen_y - rotated_surface.get_height() // 2)
    
    # Blit the rotated surface onto the screen
    screen.blit(rotated_surface, blit_pos)

def get_unit_inner_color(unit: Unit, model: Model) -> Tuple[int, int, int]:
    """Get the inner color based on unit type and health"""
    # Base inner color based on unit type
    if unit.is_character:
        base_color = (255, 215, 0)  # Gold for characters
    elif unit.is_vehicle:
        base_color = (169, 169, 169)  # Silver for vehicles
    elif unit.is_monster:
        base_color = (139, 69, 19)  # Brown for monsters
    elif unit.is_psyker:
        base_color = (138, 43, 226)  # Blue violet for psykers
    elif unit.is_battleline:
        base_color = (255, 255, 255)  # White for battleline
    else:
        base_color = (220, 220, 220)  # Light gray for others
    
    # Modify color based on health
    health_percent = model.health_percent
    if health_percent < 25:
        # Heavily damaged - add red tint
        return (min(255, base_color[0] + 50), max(0, base_color[1] - 50), max(0, base_color[2] - 50))
    elif health_percent < 50:
        # Moderately damaged - add yellow tint
        return (min(255, base_color[0] + 30), min(255, base_color[1] + 30), max(0, base_color[2] - 30))
    else:
        return base_color

def draw_health_indicator(screen: pygame.Surface, screen_x: int, screen_y: int, radius: int, model: Model) -> None:
    """Draw a health indicator ring around the base"""
    if radius < 8:  # Too small for health indicator
        return
    
    health_percent = model.health_percent
    if health_percent >= 100:
        return  # No indicator needed for full health
    
    # Calculate the arc angle based on health percentage
    arc_angle = int(360 * (health_percent / 100))
    
    # Choose color based on health level
    if health_percent < 25:
        health_color = (255, 0, 0)  # Red
    elif health_percent < 50:
        health_color = (255, 165, 0)  # Orange
    elif health_percent < 75:
        health_color = (255, 255, 0)  # Yellow
    else:
        health_color = (0, 255, 0)  # Green
    
    # Draw health arc (simplified approach using lines)
    health_radius = radius + 2
    for angle in range(0, arc_angle, 5):
        angle_rad = math.radians(angle - 90)  # Start from top
        x1 = screen_x + int(health_radius * math.cos(angle_rad))
        y1 = screen_y + int(health_radius * math.sin(angle_rad))
        x2 = screen_x + int((health_radius + 3) * math.cos(angle_rad))
        y2 = screen_y + int((health_radius + 3) * math.sin(angle_rad))
        pygame.draw.line(screen, health_color, (x1, y1), (x2, y2), 2)

def draw_facing_direction(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float) -> None:
    """Draw enhanced facing direction indicator"""
    # Calculate the facing line end point
    if base.base_type == BaseType.CIRCULAR:
        radius = int(base.get_radius() * TILE_SIZE * zoom_level)
        line_length = radius
    elif base.base_type in [BaseType.ELLIPTICAL, BaseType.HULL]:
        radius = int(base.get_longest_radius() * TILE_SIZE * zoom_level)
        line_length = radius
    else:
        return  # Skip if base type is unknown
    
    end_x = screen_x + int(line_length * math.cos(base.facing))
    end_y = screen_y + int(line_length * math.sin(base.facing))
    
    # Draw the main facing line with enhanced styling
    pygame.draw.line(screen, (0, 0, 0), (screen_x, screen_y), (end_x, end_y), 3)
    
    # Draw arrowhead
    if line_length > 10:  # Only draw arrowhead if line is long enough
        arrow_length = min(8, line_length // 3)
        arrow_angle = 0.5  # radians
        
        # Calculate arrowhead points
        left_x = end_x - int(arrow_length * math.cos(base.facing - arrow_angle))
        left_y = end_y - int(arrow_length * math.sin(base.facing - arrow_angle))
        right_x = end_x - int(arrow_length * math.cos(base.facing + arrow_angle))
        right_y = end_y - int(arrow_length * math.sin(base.facing + arrow_angle))
        
        # Draw arrowhead
        pygame.draw.polygon(screen, (0, 0, 0), [(end_x, end_y), (left_x, left_y), (right_x, right_y)])

# Legacy draw_base function removed - use draw_enhanced_base instead

# Legacy draw_circular_base function removed - use draw_enhanced_circular_base instead

# Legacy draw_elliptical_base function removed - use draw_enhanced_elliptical_base instead

# Legacy draw_hull_base function removed - use draw_enhanced_hull_base instead

def draw_unit_bounding_box(screen: pygame.Surface, unit: Unit, zoom_level: float, offset_x: int, offset_y: int, mouse_pos: Tuple[int, int]) -> None:
    position = unit.get_position()
    if position is None:
        return

    center_x, center_y, _ = position
    radius = unit.coherency_distance  # Assuming this is defined in the Unit class

    bounding_box_rect = pygame.Rect(
        int((center_x - radius) * TILE_SIZE * zoom_level + offset_x),
        int((center_y - radius) * TILE_SIZE * zoom_level + offset_y),
        int(2 * radius * TILE_SIZE * zoom_level),
        int(2 * radius * TILE_SIZE * zoom_level)
    )

    if bounding_box_rect.collidepoint(mouse_pos):
        pygame.draw.rect(screen, (255, 255, 0), bounding_box_rect, 2)  # Yellow highlight

def handle_zoom(zoom_level: float, event: pygame.event.Event) -> float:
    zoom_direction = event.y  # Positive for scroll up, negative for scroll down
    new_zoom = zoom_level + (ZOOM_SPEED * zoom_direction)
    return max(MIN_ZOOM, min(MAX_ZOOM, new_zoom))

def handle_pan(keys_pressed: Dict[int, bool], offset_x: int, offset_y: int, zoom_level: float) -> Tuple[int, int]:
    # Improved pan speed that doesn't get slower when zoomed in (but can be faster when zoomed out)
    pan_speed = max(PAN_SPEED, int(PAN_SPEED * zoom_level))
    new_offset_x, new_offset_y = offset_x, offset_y
    
    # Support both arrow keys and WASD
    if keys_pressed[pygame.K_LEFT] or keys_pressed[pygame.K_a]:
        new_offset_x += pan_speed
    if keys_pressed[pygame.K_RIGHT] or keys_pressed[pygame.K_d]:
        new_offset_x -= pan_speed
    if keys_pressed[pygame.K_UP] or keys_pressed[pygame.K_w]:
        new_offset_y += pan_speed
    if keys_pressed[pygame.K_DOWN] or keys_pressed[pygame.K_s]:
        new_offset_y -= pan_speed
    
    # Limit panning to prevent moving outside the grid
    max_offset_x = max(0, int(BATTLEFIELD_WIDTH * zoom_level) - BATTLEFIELD_WIDTH)
    max_offset_y = max(0, int(BATTLEFIELD_HEIGHT * zoom_level) - BATTLEFIELD_HEIGHT)
    new_offset_x = max(-max_offset_x, min(0, new_offset_x))
    new_offset_y = max(-max_offset_y, min(0, new_offset_y))
    
    return new_offset_x, new_offset_y

def draw_character_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a crown icon for characters"""
    crown_color = (255, 215, 0)  # Gold
    outline_color = (0, 0, 0)
    
    # Crown base
    base_rect = pygame.Rect(center_x - size//2, center_y + size//4, size, size//4)
    pygame.draw.rect(surface, crown_color, base_rect)
    pygame.draw.rect(surface, outline_color, base_rect, 1)
    
    # Crown peaks
    peaks = [
        (center_x - size//2, center_y + size//4),
        (center_x - size//4, center_y - size//4),
        (center_x, center_y + size//8),
        (center_x + size//4, center_y - size//4),
        (center_x + size//2, center_y + size//4)
    ]
    pygame.draw.polygon(surface, crown_color, peaks)
    pygame.draw.polygon(surface, outline_color, peaks, 2)
    
    # Crown jewel
    pygame.draw.circle(surface, (255, 0, 0), (center_x, center_y - size//8), size//8)

def draw_vehicle_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a tank/vehicle icon"""
    vehicle_color = (128, 128, 128)  # Gray
    outline_color = (0, 0, 0)
    
    # Tank body
    body_rect = pygame.Rect(center_x - size//2, center_y - size//4, size, size//2)
    pygame.draw.rect(surface, vehicle_color, body_rect)
    pygame.draw.rect(surface, outline_color, body_rect, 1)
    
    # Tank turret
    turret_rect = pygame.Rect(center_x - size//3, center_y - size//3, size//1.5, size//3)
    pygame.draw.rect(surface, vehicle_color, turret_rect)
    pygame.draw.rect(surface, outline_color, turret_rect, 1)
    
    # Tank barrel
    barrel_rect = pygame.Rect(center_x + size//4, center_y - size//8, size//3, size//8)
    pygame.draw.rect(surface, vehicle_color, barrel_rect)
    pygame.draw.rect(surface, outline_color, barrel_rect, 1)
    
    # Tracks
    pygame.draw.rect(surface, outline_color, (center_x - size//2, center_y + size//8, size, size//8), 1)

def draw_monster_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a monster/creature icon with claws and fangs"""
    monster_color = (139, 69, 19)  # Brown
    claw_color = (160, 82, 45)  # Lighter brown
    outline_color = (0, 0, 0)
    
    # Monster body (oval)
    body_rect = pygame.Rect(center_x - size//3, center_y - size//4, size//1.5, size//2)
    pygame.draw.ellipse(surface, monster_color, body_rect)
    pygame.draw.ellipse(surface, outline_color, body_rect, 2)
    
    # Claws
    claw_points_left = [
        (center_x - size//2, center_y),
        (center_x - size//4, center_y - size//6),
        (center_x - size//3, center_y + size//6)
    ]
    claw_points_right = [
        (center_x + size//2, center_y),
        (center_x + size//4, center_y - size//6),
        (center_x + size//3, center_y + size//6)
    ]
    
    pygame.draw.polygon(surface, claw_color, claw_points_left)
    pygame.draw.polygon(surface, claw_color, claw_points_right)
    pygame.draw.polygon(surface, outline_color, claw_points_left, 2)
    pygame.draw.polygon(surface, outline_color, claw_points_right, 2)
    
    # Eyes
    pygame.draw.circle(surface, (255, 0, 0), (center_x - size//8, center_y - size//8), size//12)
    pygame.draw.circle(surface, (255, 0, 0), (center_x + size//8, center_y - size//8), size//12)

def draw_psyker_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a mystical psyker icon"""
    psyker_color = (138, 43, 226)  # Blue violet
    outline_color = (0, 0, 0)
    
    # Central circle
    pygame.draw.circle(surface, psyker_color, (center_x, center_y), size//4, 2)
    
    # Mystical rays
    ray_length = size//2
    for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
        angle_rad = math.radians(angle)
        end_x = center_x + int(ray_length * math.cos(angle_rad))
        end_y = center_y + int(ray_length * math.sin(angle_rad))
        pygame.draw.line(surface, psyker_color, (center_x, center_y), (end_x, end_y), 2)
    
    # Central eye
    pygame.draw.circle(surface, (255, 255, 255), (center_x, center_y), size//8)
    pygame.draw.circle(surface, psyker_color, (center_x, center_y), size//12)
    pygame.draw.circle(surface, outline_color, (center_x, center_y), size//8, 1)

def draw_battleline_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a battleline infantry icon"""
    infantry_color = (100, 100, 100)  # Gray
    outline_color = (0, 0, 0)
    
    # Helmet
    helmet_rect = pygame.Rect(center_x - size//4, center_y - size//3, size//2, size//3)
    pygame.draw.ellipse(surface, infantry_color, helmet_rect)
    pygame.draw.ellipse(surface, outline_color, helmet_rect, 1)
    
    # Body
    body_rect = pygame.Rect(center_x - size//3, center_y - size//8, size//1.5, size//2)
    pygame.draw.rect(surface, infantry_color, body_rect)
    pygame.draw.rect(surface, outline_color, body_rect, 1)
    
    # Weapon
    weapon_rect = pygame.Rect(center_x + size//6, center_y - size//4, size//4, size//12)
    pygame.draw.rect(surface, outline_color, weapon_rect)
    
    # Visor
    pygame.draw.rect(surface, (255, 0, 0), (center_x - size//8, center_y - size//4, size//4, size//12))

def draw_aircraft_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw an aircraft icon"""
    aircraft_color = (70, 130, 180)  # Steel blue
    outline_color = (0, 0, 0)
    
    # Main body
    body_points = [
        (center_x - size//2, center_y),
        (center_x + size//3, center_y - size//8),
        (center_x + size//2, center_y),
        (center_x + size//3, center_y + size//8)
    ]
    pygame.draw.polygon(surface, aircraft_color, body_points)
    pygame.draw.polygon(surface, outline_color, body_points, 2)
    
    # Wings
    wing_points_top = [
        (center_x - size//4, center_y - size//8),
        (center_x - size//8, center_y - size//3),
        (center_x + size//8, center_y - size//4)
    ]
    wing_points_bottom = [
        (center_x - size//4, center_y + size//8),
        (center_x - size//8, center_y + size//3),
        (center_x + size//8, center_y + size//4)
    ]
    
    pygame.draw.polygon(surface, aircraft_color, wing_points_top)
    pygame.draw.polygon(surface, aircraft_color, wing_points_bottom)
    pygame.draw.polygon(surface, outline_color, wing_points_top, 1)
    pygame.draw.polygon(surface, outline_color, wing_points_bottom, 1)

def draw_beast_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a beast icon"""
    beast_color = (160, 82, 45)  # Saddle brown
    outline_color = (0, 0, 0)
    
    # Beast body (elongated oval)
    body_rect = pygame.Rect(center_x - size//2, center_y - size//4, size, size//2)
    pygame.draw.ellipse(surface, beast_color, body_rect)
    pygame.draw.ellipse(surface, outline_color, body_rect, 2)
    
    # Legs
    for x_offset in [-size//3, -size//6, size//6, size//3]:
        leg_start = (center_x + x_offset, center_y + size//4)
        leg_end = (center_x + x_offset, center_y + size//2)
        pygame.draw.line(surface, outline_color, leg_start, leg_end, 2)
    
    # Head
    head_center = (center_x + size//3, center_y - size//8)
    pygame.draw.circle(surface, beast_color, head_center, size//6)
    pygame.draw.circle(surface, outline_color, head_center, size//6, 1)
    
    # Eyes
    pygame.draw.circle(surface, (255, 0, 0), (center_x + size//4, center_y - size//6), size//16)

def draw_generic_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a generic unit icon"""
    generic_color = (128, 128, 128)  # Gray
    outline_color = (0, 0, 0)
    
    # Simple diamond shape
    diamond_points = [
        (center_x, center_y - size//2),
        (center_x + size//2, center_y),
        (center_x, center_y + size//2),
        (center_x - size//2, center_y)
    ]
    pygame.draw.polygon(surface, generic_color, diamond_points)
    pygame.draw.polygon(surface, outline_color, diamond_points, 2)

# Add these new classes and imports after the existing imports
from abc import ABC, abstractmethod

# Phase-specific event handler protocol
class PhaseEventHandler(Protocol):
    """Protocol for phase-specific event handlers"""
    def handle_event(self, event: pygame.event.Event, game_view: 'GameView') -> bool:
        """Handle pygame event for this phase. Returns True if event was consumed."""
        ...
    
    def get_allowed_actions(self) -> List[str]:
        """Get list of allowed actions for this phase"""
        ...

class BasePhaseHandler(ABC):
    """Base class for phase-specific event handlers"""
    
    def __init__(self, game_view: 'GameView'):
        self.game_view = game_view
        self.game = game_view.game
    
    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame event for this phase. Returns True if event was consumed."""
        pass
    
    @abstractmethod
    def get_allowed_actions(self) -> List[str]:
        """Get list of allowed actions for this phase"""
        pass
    
    def is_valid_action(self, action: str) -> bool:
        """Check if an action is valid for this phase"""
        return action in self.get_allowed_actions()

class SetupPhaseHandler(BasePhaseHandler):
    """Handles events during setup phases"""
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                # Handle setup phase advancement
                current_phase = self.game.get_current_setup_phase()
                
                # Check if we're in deployment phase and waiting for deployment input
                if (current_phase.name == 'DEPLOY_ARMIES' and 
                    hasattr(self.game, 'waiting_for_deployment_input') and 
                    self.game.waiting_for_deployment_input):
                    # Continue deployment
                    self.game.waiting_for_deployment_input = False
                    return True
                
                # Execute the current setup phase
                setup_kwargs = {
                    'player1_army_file': None,  # These would come from game config
                    'player2_army_file': None,
                    'manual_phases': True
                }
                
                # For DEPLOY_ARMIES phase, handle based on player types
                if current_phase.name == 'DEPLOY_ARMIES':
                    has_human_players = any(player.type.name == 'HUMAN' for player in self.game.players)
                    if has_human_players:
                        setup_kwargs['manual_phases'] = True
                
                # Store which phase we're executing to know when to refresh UI
                current_phase_before = self.game.get_current_setup_phase()
                
                self.game.execute_current_setup_phase(**setup_kwargs)
                setup_complete = self.game.advance_setup_phase()
                
                # Update UI after specific phases that change game state
                if current_phase_before.name == 'MUSTER_ARMIES':
                    # Armies were just loaded - refresh roster panes
                    self.game_view.refresh_roster_panes()
                    print("📋 UI updated after armies loaded")
                elif current_phase_before.name == 'DETERMINE_ATTACKER_AND_DEFENDER':
                    # Attacker/Defender roles determined - update titles
                    self.game_view.update_roster_pane_titles()
                    print("📋 UI updated after attacker/defender determined")
                
                if setup_complete:
                    # Final update after all setup phases complete
                    self.game_view.refresh_roster_panes()
                    self.game_view.update_roster_pane_titles()
                    print("📋 UI updated after setup completion")
                
                return True
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:  # Right click - show unit details
            hovered_unit, _ = self.game_view.get_hovered_unit(event.pos[0], event.pos[1])
            if hovered_unit:
                self.game_view.detailed_unit = hovered_unit
                self.game_view.detail_panel_pos = event.pos
                return True
        
        return False
    
    def get_allowed_actions(self) -> List[str]:
        return ["advance_setup_phase", "view_unit_details"]

class DeploymentPhaseHandler(BasePhaseHandler):
    """Handles events during deployment phase"""
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        # Handle deployment choice dialog first (highest priority)
        if (self.game_view.ui_interface and 
            hasattr(self.game_view.ui_interface, 'deployment_choice_dialog') and 
            self.game_view.ui_interface.deployment_choice_dialog.visible):
            return self.game_view.ui_interface.deployment_choice_dialog.handle_event(event)
        
        # Handle UI interface events
        if self.game_view.ui_interface and self.game_view.ui_interface.handle_event(event):
            return True
        
        # Handle deployment-specific mouse events
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_deployment_click(event.pos)
        
        # Handle deployment-specific keyboard events
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                # Force complete deployment phase
                self.game_view.force_complete_deployment()
                return True
            elif event.key == pygame.K_ESCAPE:
                # Cancel current unit selection
                self.game_view.selected_unit = None
                self.game_view.left_roster_pane.selected_unit = None
                self.game_view.right_roster_pane.selected_unit = None
                return True
        
        # Handle right-click for unit details (works in all phases)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:  # Right click - show unit details
            hovered_unit, _ = self.game_view.get_hovered_unit(event.pos[0], event.pos[1])
            if hovered_unit:
                self.game_view.detailed_unit = hovered_unit
                self.game_view.detail_panel_pos = event.pos
                return True
        
        return False
    
    def _handle_deployment_click(self, mouse_pos) -> bool:
        """Handle mouse clicks during deployment phase"""
        x, y = mouse_pos
        
        # Check roster pane clicks first
        if self.game_view.left_roster_pane.rect.collidepoint(x, y):
            self.game_view.left_roster_pane.on_mouse_press(x, y, 1)
            self.game_view.selected_unit = self.game_view.left_roster_pane.selected_unit
            return True
        elif self.game_view.right_roster_pane.rect.collidepoint(x, y):
            self.game_view.right_roster_pane.on_mouse_press(x, y, 1)
            self.game_view.selected_unit = self.game_view.right_roster_pane.selected_unit
            return True
        
        # Handle battlefield deployment clicks
        elif (self.game_view.selected_unit and not self.game_view.selected_unit.deployed and 
              ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH):
            return self._handle_battlefield_deployment(x, y)
        
        return False
    
    def _handle_battlefield_deployment(self, x: int, y: int) -> bool:
        """Handle unit deployment on battlefield"""
        # Check if deployment zones are loaded
        if not hasattr(self.game, 'deployment_zones') or not self.game.deployment_zones:
            print(f"📋 Press SPACE to begin deployment sequence first")
            return True
        
        # Convert screen coordinates to game coordinates
        battlefield_x = (x - ROSTER_PANE_WIDTH - self.game_view.offset_x) / (TILE_SIZE * self.game_view.zoom_level)
        battlefield_y = (y - self.game_view.offset_y) / (TILE_SIZE * self.game_view.zoom_level)
        
        # Attempt to deploy the unit
        original_unit_position = self.game_view.selected_unit.get_position() if self.game_view.selected_unit.position else None
        original_model_positions = [model.get_location() for model in self.game_view.selected_unit.models]
        
        model_positions = self.game_view.selected_unit.calculate_model_positions(
            battlefield_x, battlefield_y, self.game_view.game_map, 0.0, self.game_view.zoom_level)
        
        if model_positions:
            # Set model positions
            for model, position in zip(self.game_view.selected_unit.models, model_positions):
                model_x, model_y, model_z, model_facing = position
                model.set_location(model_x, model_y, model_z, model_facing)
            
            unit_x = sum(pos[0] for pos in model_positions) / len(model_positions)
            unit_y = sum(pos[1] for pos in model_positions) / len(model_positions)
            
            # Validate deployment position
            current_deployment_player = self.game.get_current_deployment_player()
            player_name = current_deployment_player.name if current_deployment_player else None
            
            if player_name and not self.game.is_valid_deployment_position(
                self.game_view.selected_unit, unit_x, unit_y, player_name):
                # Invalid position - reset and show error
                if self.game_view.selected_unit.has_infiltrate():
                    print(f"❌ Invalid deployment position for {self.game_view.selected_unit.name} (Infiltrate)")
                else:
                    print(f"❌ Invalid deployment position for {self.game_view.selected_unit.name}")
                self.game_view.reset_unit_position(self.game_view.selected_unit, 
                                                 original_unit_position, original_model_positions)
                return True
            
            # Valid deployment
            self.game_view.selected_unit.set_position(unit_x, unit_y)
            
            if self.game_view.game_map.place_unit(self.game_view.selected_unit):
                print(f"Unit {self.game_view.selected_unit.name} deployed at ({unit_x:.1f}, {unit_y:.1f})")
                self.game_view.selected_unit.deployed = True
                
                # Record deployment action
                if current_deployment_player and self.game_view.selected_unit.position:
                    self.game.record_deployment_action(current_deployment_player, 
                                                     self.game_view.selected_unit, 'deployed', 
                                                     self.game_view.selected_unit.position)
                
                # Advance to next player's deployment turn
                self.game.advance_deployment_turn()
                
                # Clear selection
                self.game_view.selected_unit = None
                self.game_view.left_roster_pane.selected_unit = None
                self.game_view.right_roster_pane.selected_unit = None
            else:
                print("Failed to place unit")
                self.game_view.reset_unit_position(self.game_view.selected_unit, 
                                                 original_unit_position, original_model_positions)
        
        return True
    
    def get_allowed_actions(self) -> List[str]:
        return ["select_unit", "deploy_unit", "choose_reserves", "view_unit_details", "complete_deployment"]

class BattlePhaseHandler(BasePhaseHandler):
    """Handles events during battle phases (movement, shooting, etc.)"""
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events during battle phases"""
        # Handle weapon choice dialog first (highest priority)
        if (hasattr(self.game_view, 'weapon_choice_dialog') and
            self.game_view.weapon_choice_dialog.visible):
            return self.game_view.weapon_choice_dialog.handle_event(event)
        
        # Handle shooting declaration dialog
        if (hasattr(self.game_view, 'shooting_declaration_dialog') and
            (self.game_view.shooting_declaration_dialog.visible or 
             self.game_view.shooting_declaration_dialog.is_targeting_mode)):
            return self.game_view.shooting_declaration_dialog.handle_event(event)
        
        # Handle movement choice dialog
        if (hasattr(self.game_view, 'movement_choice_dialog') and
            self.game_view.movement_choice_dialog.visible):
            return self.game_view.movement_choice_dialog.handle_event(event)
        
        # Handle mouse events
        if event.type == pygame.MOUSEBUTTONDOWN:
            return self._handle_battle_click(event.pos, event.button)
        elif event.type == pygame.MOUSEMOTION:
            return self._handle_battle_motion(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            return self._handle_battle_release(event.pos, event.button)
        
        return False
    
    def _handle_battle_click(self, mouse_pos, button) -> bool:
        """Handle battlefield clicks during battle phases"""
        x, y = mouse_pos
        print(f"🔍 _handle_battle_click called at ({x}, {y}) with button {button}")
        
        # Check if shooting declaration dialog is in targeting mode
        if (hasattr(self.game_view, 'shooting_declaration_dialog') and
            self.game_view.shooting_declaration_dialog.is_targeting_mode):
            
            print(f"🎯 BattlePhaseHandler: Dialog in targeting mode, routing click to targeting handler")
            # Handle battlefield targeting for shooting declaration
            handled = self.game_view.shooting_declaration_dialog.handle_battlefield_targeting(x, y)
            if handled:
                print(f"🎯 BattlePhaseHandler: Targeting handled successfully")
                return True
            else:
                print(f"🎯 BattlePhaseHandler: Targeting not handled, continuing with normal battlefield handling")
        else:
            if hasattr(self.game_view, 'shooting_declaration_dialog'):
                print(f"🔍 BattlePhaseHandler: Dialog exists but not in targeting mode (is_targeting_mode={self.game_view.shooting_declaration_dialog.is_targeting_mode})")
            else:
                print(f"🔍 BattlePhaseHandler: No shooting declaration dialog found")
        
        # Handle unit selection and actions based on current phase
        if button == 1:  # Left click
            # Check roster pane clicks
            if self.game_view.left_roster_pane.rect.collidepoint(x, y):
                self.game_view.left_roster_pane.on_mouse_press(x, y, button)
                selected_unit = self.game_view.left_roster_pane.selected_unit
                if selected_unit:
                    self._handle_unit_selection(selected_unit)
                return True
            elif self.game_view.right_roster_pane.rect.collidepoint(x, y):
                self.game_view.right_roster_pane.on_mouse_press(x, y, button)
                selected_unit = self.game_view.right_roster_pane.selected_unit
                if selected_unit:
                    self._handle_unit_selection(selected_unit)
                return True
            
            # Handle battlefield clicks based on current phase
            elif ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH:
                return self._handle_battlefield_action(x, y)
        
        elif button == 3:  # Right click - show unit details
            hovered_unit, _ = self.game_view.get_hovered_unit(x, y)
            if hovered_unit:
                self.game_view.detailed_unit = hovered_unit
                self.game_view.detail_panel_pos = (x, y)
                return True
        
        return False
    
    def _synchronize_unit_selection(self, unit) -> None:
        """Synchronize unit selection between RosterPane and battlefield"""
        # Update the main selected unit
        self.game_view.selected_unit = unit
        
        # Update roster pane selections to match
        # Find which roster pane this unit belongs to and update its selection
        if unit.parent_army:
            if unit.parent_army.player == self.game_view.player1:
                self.game_view.left_roster_pane.selected_unit = unit
                self.game_view.right_roster_pane.selected_unit = None
            elif unit.parent_army.player == self.game_view.player2:
                self.game_view.right_roster_pane.selected_unit = unit
                self.game_view.left_roster_pane.selected_unit = None
    
    def _handle_unit_selection(self, unit) -> None:
        """Handle unit selection based on current phase"""
        current_phase = self.game.phase
        current_player = self.game.get_current_player()
        
        # Check if this unit belongs to the current player
        if not (unit.parent_army and unit.parent_army.player == current_player):
            print(f"❌ {unit.name} does not belong to current player {current_player.name}")
            return
        
        # Only allow human players to interact with units during their turn
        if current_player.type.name != 'HUMAN':
            print(f"❌ Current player {current_player.name} is AI - no unit interaction allowed")
            return
        
        # Synchronize selection across UI components
        self._synchronize_unit_selection(unit)
        
        # Handle phase-specific unit selection
        if current_phase.name == 'MOVEMENT_PHASE':
            self._handle_movement_phase_selection(unit)
        elif current_phase.name == 'SHOOTING_PHASE':
            self._handle_shooting_phase_selection(unit)
        elif current_phase.name == 'CHARGE_PHASE':
            self._handle_charge_phase_selection(unit)
        elif current_phase.name == 'FIGHT_PHASE':
            self._handle_fight_phase_selection(unit)
        else:
            print(f"❌ Unit selection not available in {current_phase.name}")
    
    def _handle_movement_phase_selection(self, unit) -> None:
        """Handle unit selection during movement phase"""
        # Check if unit has already moved this round
        if hasattr(unit.round_state, 'moved_this_round') and unit.round_state.moved_this_round:
            print(f"❌ {unit.name} has already moved this round")
            return
        
        def on_movement_choice(choice):
            self._handle_movement_choice(unit, choice)
        
        self.game_view.movement_choice_dialog.show(unit, on_movement_choice, self.game.map)
    
    def _handle_shooting_phase_selection(self, unit) -> None:
        """Handle unit selection during shooting phase"""
        if not unit or not unit.is_alive():
            return
        
        # Check if unit can shoot
        if unit.round_state.shot_this_round:
            print(f"❌ {unit.name} has already shot this round")
            return
        
        if unit.round_state.fell_back_this_round:
            print(f"❌ {unit.name} cannot shoot after falling back")
            return
        
        # Check if unit is engaged and can't shoot
        is_engaged = any(self.game.map.is_within_engagement_range(unit.get_position(), enemy)
                        for enemy in self.game.map.get_enemy_units(unit) if enemy.is_alive())
        
        if is_engaged:
            # Check if unit has any weapons that can shoot while engaged
            has_eligible_weapons = False
            for model in unit.models:
                if not model.is_alive:
                    continue
                for wargear in model.wargear:
                    if wargear.is_ranged():
                        for profile in wargear.profiles.values():
                            if unit.can_shoot_in_engagement_range(profile):
                                has_eligible_weapons = True
                                break
                        if has_eligible_weapons:
                            break
                if has_eligible_weapons:
                    break
            
            if not has_eligible_weapons:
                print(f"❌ {unit.name} is engaged and has no weapons that can shoot in engagement range")
                return
        
        # Show shooting declaration dialog
        def on_shooting_complete(declarations):
            # Handle shooting declarations
            self._clear_shooting_selection()
        
        self.game_view.shooting_declaration_dialog.show(unit, on_shooting_complete, self.game.map, self.game_view)
    
    def _handle_charge_phase_selection(self, unit) -> None:
        """Handle unit selection during charge phase"""
        # Check if unit has already charged this round
        if hasattr(unit.round_state, 'declared_charge_this_round') and unit.round_state.declared_charge_this_round:
            print(f"❌ {unit.name} has already declared a charge this round")
            return
        
        # Check if unit can charge (not advanced unless allowed, not fell back, etc.)
        if unit.round_state.fell_back_this_round:
            print(f"❌ {unit.name} fell back and cannot charge")
            return
        
        # TODO: Add more charge validation logic
        print(f"⚔️ Click on enemy unit to charge with {unit.name}")
    
    def _handle_fight_phase_selection(self, unit) -> None:
        """Handle unit selection during fight phase"""
        # Check if unit is in engagement range
        is_engaged = any(self.game.map.is_within_engagement_range(unit.get_position(), enemy)
                        for enemy in self.game.map.get_enemy_units(unit) if enemy.is_alive())
        
        if not is_engaged:
            print(f"❌ {unit.name} is not in engagement range")
            return
        
        # TODO: Add fight phase logic
        print(f"👊 Click on engaged enemy to fight with {unit.name}")
    
    def _handle_movement_choice(self, unit, choice: str) -> None:
        """Handle movement choice selection using Unit's movement system"""
        from warhammer40k_ai.classes.unit import MovementAction
        
        # Map UI choices to Unit's MovementAction enum
        choice_mapping = {
            'move': MovementAction.MOVE,
            'advance': MovementAction.ADVANCE,
            'fall_back': MovementAction.FALL_BACK,
            'stationary': MovementAction.REMAIN_STATIONARY
        }
        
        if choice not in choice_mapping:
            print(f"❌ Invalid movement choice: {choice}")
            return
        
        # Get the unit's current engagement state
        engagement_state = unit.get_engagement_state(self.game.map)
        available_actions = unit.get_available_move_actions(engagement_state.value)
        
        # Check if the chosen action is available
        chosen_action = choice_mapping[choice]
        if chosen_action.value not in available_actions:
            print(f"❌ {choice.title()} action not available for {unit.name}")
            return
        
        # Store the chosen action for battlefield click handling
        self.game_view.selected_unit_for_movement = unit
        self.game_view.movement_action = chosen_action
        # Keep the selected model if one was previously selected
        if not hasattr(self.game_view, 'selected_model_for_movement'):
            self.game_view.selected_model_for_movement = None
        
        # Roll advance dice immediately if advancing
        if choice == 'advance':
            advance_roll = unit.prepare_advance()
        
        if choice == 'stationary':
            # Execute stationary action immediately (no destination needed)
            success = unit._execute_action(chosen_action.value, (0, 0, 0), self.game.map)
            if success:
                print(f"🛑 {unit.name} remains stationary")
            # Clear selection since action is complete
            self.game_view.selected_unit_for_movement = None
            self.game_view.movement_action = None
            self.game_view.selected_model_for_movement = None
        else:
            print(f"📍 Click on the battlefield to {choice} {unit.name}")
            # Action will be executed when user clicks battlefield
    
    def _handle_battlefield_action(self, x: int, y: int) -> bool:
        """Handle battlefield actions based on current battle phase"""
        current_phase = self.game.phase
        
        # Phase-specific actions
        if current_phase.name == 'MOVEMENT_PHASE':
            return self._handle_movement_action(x, y)
        elif current_phase.name == 'SHOOTING_PHASE':
            return self._handle_shooting_action(x, y)
        elif current_phase.name == 'CHARGE_PHASE':
            return self._handle_charge_action(x, y)
        elif current_phase.name == 'FIGHT_PHASE':
            return self._handle_fight_action(x, y)
        
        return False
    
    def _handle_movement_action(self, x: int, y: int) -> bool:
        """Handle movement phase actions using Unit's movement system"""
        # Check if we clicked on a model first for selection
        clicked_model = self.game_view.get_model_at_position(x, y)
        if clicked_model:
            # Try to select this unit for movement and track the specific model
            clicked_unit = clicked_model.parent_unit
            self.game_view.selected_unit = clicked_unit
            self.game_view.selected_model_for_movement = clicked_model  # Track the specific model
            self._handle_unit_selection(clicked_unit)
            return True
        
        # Only process movement destination if we have a unit selected for movement
        if (hasattr(self.game_view, 'selected_unit_for_movement') and 
            self.game_view.selected_unit_for_movement and 
            hasattr(self.game_view, 'movement_action') and 
            self.game_view.movement_action):
            
            unit = self.game_view.selected_unit_for_movement
            action = self.game_view.movement_action
            
            # Convert to game coordinates
            battlefield_x = (x - ROSTER_PANE_WIDTH - self.game_view.offset_x) / (TILE_SIZE * self.game_view.zoom_level)
            battlefield_y = (y - self.game_view.offset_y) / (TILE_SIZE * self.game_view.zoom_level)
            battlefield_z = self.game.map.get_height_at_point(battlefield_x, battlefield_y)
            
            destination = (battlefield_x, battlefield_y, battlefield_z)
            
            # Pre-validate the movement destination
            validation_result = self._validate_movement_destination(unit, action, destination)
            
            if not validation_result["valid"]:
                # Invalid move - show feedback and keep selection active for retry
                print(f"❌ Invalid {action.name.lower().replace('_', ' ')}: {validation_result['reason']}")
                print(f"📍 Click on the battlefield to {action.name.lower().replace('_', ' ')} {unit.name} (try a closer location)")
                return True  # Keep the movement selection active
            
            # Destination is valid, attempt the movement
            success = unit._execute_action(action.value, destination, self.game.map)
            
            if success:
                # Unit movement system now provides its own detailed feedback
                # Clear movement selection only on successful move
                self.game_view.selected_unit_for_movement = None
                self.game_view.movement_action = None
                self.game_view.selected_model_for_movement = None
            else:
                # Move execution failed for some other reason - allow retry
                print(f"📍 Click on the battlefield to {action.name.lower().replace('_', ' ')} {unit.name} (try a different location)")
            
            return True
        
        return False
    
    def _validate_movement_destination(self, unit, action, destination: Tuple[float, float, float]) -> dict:
        """Validate if a movement destination is reachable and provide feedback"""
        from warhammer40k_ai.classes.unit import MovementAction
        from warhammer40k_ai.utility.calcs import get_dist
        
        current_position = unit.get_position()
        if current_position is None:
            return {"valid": False, "reason": "Unit has no current position"}
        
        # Calculate straight-line distance to destination
        distance_to_destination = get_dist(
            destination[0] - current_position[0],
            destination[1] - current_position[1],
            destination[2] - current_position[2] if len(current_position) > 2 else 0
        )
        
        # Get movement range based on action type
        base_movement = unit.movement
        if action == MovementAction.REMAIN_STATIONARY:
            max_distance = 0
        elif action == MovementAction.MOVE:
            max_distance = base_movement
        elif action == MovementAction.ADVANCE:
            # Use the unit's advance roll if available
            advance_roll = unit.get_advance_roll()
            if advance_roll is not None:
                max_distance = base_movement + advance_roll
            else:
                raise RuntimeError(f"Unit {unit.name} has no advance roll")
        elif action == MovementAction.FALL_BACK:
            max_distance = base_movement
        else:
            return {"valid": False, "reason": "Unknown movement action"}
        
        # Check if destination is within maximum possible range
        if distance_to_destination > max_distance:
            if action == MovementAction.ADVANCE:
                return {
                    "valid": False, 
                    "reason": f"Destination is {distance_to_destination:.1f}\" away, max advance is {base_movement}\" + D6 (up to {max_distance}\")"
                }
            else:
                return {
                    "valid": False, 
                    "reason": f"Destination is {distance_to_destination:.1f}\" away, max {action.name.lower().replace('_', ' ')} is {max_distance}\""
                }
        
        # Additional validation could be added here for:
        # - Terrain obstacles blocking the path
        # - Enemy units blocking the destination
        # - Unit coherency issues
        # - Engagement range restrictions
        
        return {"valid": True, "reason": "Destination is reachable"}
    
    def _handle_shooting_action(self, x: int, y: int) -> bool:
        """Handle shooting phase actions - allow clicking on units to select them for shooting"""
        # Check if we clicked on a unit first for selection
        clicked_unit = self.game_view.get_unit_at_position(x, y)
        if clicked_unit:
            # Try to select this unit for shooting
            self.game_view.selected_unit = clicked_unit
            self._handle_unit_selection(clicked_unit)
            return True
        
        return False
    
    def _show_weapon_choice_dialog(self, unit):
        """Show weapon selection dialog for the unit"""
        if not hasattr(self.game_view, 'weapon_choice_dialog'):
            self.game_view.weapon_choice_dialog = WeaponChoiceDialog(
                self.game_view.screen.get_width(), 
                self.game_view.screen.get_height()
            )
        
        def on_weapon_choice(weapon_profile):
            self.game_view.selected_weapon_profile = weapon_profile
            # Clear any previous shooting selection state
            if hasattr(self.game_view, 'selected_shooting_models'):
                self.game_view.selected_shooting_models = []
        
        self.game_view.weapon_choice_dialog.show(unit, on_weapon_choice, self.game.map)
    
    def _clear_shooting_selection(self):
        """Clear shooting selection state"""
        if hasattr(self.game_view, 'selected_weapon_profile'):
            self.game_view.selected_weapon_profile = None
        if hasattr(self.game_view, 'selected_shooting_models'):
            self.game_view.selected_shooting_models = []
    
    def _execute_shooting_attack(self, shooting_unit, target_unit, weapon_profile):
        """Shooting execution is now handled by unit.execute_shooting_declarations()"""
        # This method is deprecated - shooting execution moved to unit.py
        pass
    
    def _validate_shooting_target(self, shooting_unit, target_unit, weapon_profile) -> dict:
        """Validate if shooting unit can target the enemy unit with the selected weapon"""
        # Check if target is an enemy unit
        if target_unit.get_parent_army() == shooting_unit.get_parent_army():
            return {"valid": False, "reason": "Cannot target friendly units"}
        
        # Check if target is alive
        if not target_unit.is_alive():
            return {"valid": False, "reason": "Target unit is destroyed"}
        
        # Check if unit can shoot (not advanced unless allowed, not fell back, etc.)
        if shooting_unit.round_state.advanced_this_round and not shooting_unit.can_shoot_after_advance(weapon_profile):
            return {"valid": False, "reason": "Unit advanced and cannot shoot with this weapon"}
        
        if shooting_unit.round_state.fell_back_this_round:
            return {"valid": False, "reason": "Unit fell back and cannot shoot"}
        
        # Check if any models in the unit can shoot this weapon at the target
        models_in_range = []
        for model in shooting_unit.models:
            if not model.is_alive:
                continue
                
            # Check if this model has the weapon
            has_weapon = False
            for wargear in model.wargear:
                if weapon_profile.parent_wargear == wargear:
                    has_weapon = True
                    break
            
            if not has_weapon:
                continue
            
            # Check range to target
            closest_target_model, distance = model.return_closest_model_in_unit(target_unit)
            if distance <= weapon_profile.range.max:
                # Check line of sight (placeholder)
                if self._has_line_of_sight(model, closest_target_model):
                    models_in_range.append(model)
        
        if not models_in_range:
            return {"valid": False, "reason": "No models in range with line of sight"}
        
        # Check engagement range restrictions
        is_engaged = any(self.game.map.is_within_engagement_range(shooting_unit.get_position(), enemy)
                        for enemy in self.game.map.get_enemy_units(shooting_unit) if enemy.is_alive())
        
        if is_engaged and not shooting_unit.can_shoot_in_engagement_range(weapon_profile):
            return {"valid": False, "reason": "Unit is engaged and weapon cannot shoot in engagement range"}
        
        return {"valid": True, "reason": f"{len(models_in_range)} models can shoot"}
    
    def _has_line_of_sight(self, shooting_model, target_model) -> bool:
        """Placeholder line of sight check - always returns True for now"""
        # TODO: Implement proper line of sight calculations considering:
        # - Terrain blocking
        # - Other units blocking  
        # - Model height and visibility
        # - Special rules (e.g., Indirect Fire)
        return True
    
    def _handle_charge_action(self, x: int, y: int) -> bool:
        """Handle charge phase actions"""
        if self.game_view.selected_unit:
            # Get target unit at click position
            target_unit = self.game_view.get_unit_at_position(x, y)
            if target_unit:
                # TODO: Implement charge validation and execution
                print(f"Charge action: {self.game_view.selected_unit.name} charges {target_unit.name}")
                return True
        
        return False
    
    def _handle_fight_action(self, x: int, y: int) -> bool:
        """Handle fight phase actions"""
        if self.game_view.selected_unit:
            # Get target unit at click position
            target_unit = self.game_view.get_unit_at_position(x, y)
            if target_unit:
                # TODO: Implement fight validation and execution
                print(f"Fight action: {self.game_view.selected_unit.name} fights {target_unit.name}")
                return True
        
        return False
    
    def get_allowed_actions(self) -> List[str]:
        current_phase = self.game.phase
        current_player = self.game.get_current_player()
        
        # Base actions available in all phases
        base_actions = ["view_unit_details", "advance_phase"]
        
        # Only allow unit selection for human players
        if current_player.type.name == 'HUMAN':
            base_actions.append("select_unit")
        
        # Phase-specific actions
        if current_phase.name == 'MOVEMENT_PHASE':
            if current_player.type.name == 'HUMAN':
                return base_actions + ["move_unit", "advance_unit", "remain_stationary", "fall_back"]
            else:
                return base_actions + ["ai_movement_phase"]
        elif current_phase.name == 'SHOOTING_PHASE':
            if current_player.type.name == 'HUMAN':
                return base_actions + ["select_weapon", "target_unit", "cancel_shooting"]
            else:
                return base_actions + ["ai_shooting_phase"]
        elif current_phase.name == 'CHARGE_PHASE':
            if current_player.type.name == 'HUMAN':
                return base_actions + ["declare_charge", "charge_move"]
            else:
                return base_actions + ["ai_charge_phase"]
        elif current_phase.name == 'FIGHT_PHASE':
            if current_player.type.name == 'HUMAN':
                return base_actions + ["pile_in", "fight", "consolidate"]
            else:
                return base_actions + ["ai_fight_phase"]
        else:
            return base_actions
    
    def _handle_battle_motion(self, mouse_pos) -> bool:
        """Handle mouse motion during battle phases"""
        x, y = mouse_pos
        
        # Update hover states for UI components
        if hasattr(self.game_view, 'shooting_declaration_dialog') and self.game_view.shooting_declaration_dialog.visible:
            self.game_view.shooting_declaration_dialog.update_hover((x, y))
            return True
        
        if hasattr(self.game_view, 'movement_choice_dialog') and self.game_view.movement_choice_dialog.visible:
            self.game_view.movement_choice_dialog.update_hover((x, y))
            return True
        
        # Update roster pane hovers
        if self.game_view.left_roster_pane.rect.collidepoint(x, y):
            return True
        elif self.game_view.right_roster_pane.rect.collidepoint(x, y):
            return True
        
        return False
    
    def _handle_battle_release(self, mouse_pos, button) -> bool:
        """Handle mouse button release during battle phases"""
        # Currently no specific handling needed for mouse release
        return False

class PhaseManager:
    """Manages phase-specific event handling"""
    
    def __init__(self, game_view: 'GameView'):
        self.game_view = game_view
        self.game = game_view.game
        
        # Initialize phase handlers
        self.setup_handler = SetupPhaseHandler(game_view)
        self.deployment_handler = DeploymentPhaseHandler(game_view)
        self.battle_handler = BattlePhaseHandler(game_view)
        
        # Movement system state
        self.game_view.movement_choice_dialog = MovementChoiceDialog(game_view.screen.get_width(), game_view.screen.get_height())
        self.game_view.selected_unit_for_movement = None
        self.game_view.movement_action = None  # MovementAction enum value
        
        # Shooting system state
        self.game_view.shooting_declaration_dialog = ShootingDeclarationDialog(game_view.screen.get_width(), game_view.screen.get_height())
    
    def get_current_handler(self) -> BasePhaseHandler:
        """Get the appropriate handler for the current game phase"""
        if self.game.is_in_setup_phase():
            # Check if we're in the DEPLOY_ARMIES setup phase specifically
            current_setup_phase = self.game.get_current_setup_phase()
            if current_setup_phase.name == 'DEPLOY_ARMIES':
                return self.deployment_handler
            else:
                return self.setup_handler
        elif self.game.is_deployment_phase():
            return self.deployment_handler
        else:
            return self.battle_handler
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Route event to appropriate phase handler"""
        handler = self.get_current_handler()

        return handler.handle_event(event)
    
    def get_current_allowed_actions(self) -> List[str]:
        """Get allowed actions for current phase"""
        handler = self.get_current_handler()
        return handler.get_allowed_actions()
    
    def is_action_allowed(self, action: str) -> bool:
        """Check if an action is allowed in the current phase"""
        return action in self.get_current_allowed_actions()


def draw_movement_range(screen: pygame.Surface, unit, movement_action, zoom_level: float, offset_x: int, offset_y: int, advance_roll=None, selected_model=None) -> None:
    """Draw a visual indicator showing the movement range for a selected unit or specific model"""
    from warhammer40k_ai.classes.unit import MovementAction
    # TILE_SIZE is defined at the top of this file
    
    # Use selected model's position if available, otherwise use unit's position
    if selected_model:
        model_location = selected_model.get_location()
        current_position = (model_location[0], model_location[1], model_location[2])
    else:
        current_position = unit.get_position()
    
    if not current_position:
        return
    
    # Get movement range based on action type
    base_movement = unit.movement
    if movement_action == MovementAction.REMAIN_STATIONARY:
        max_distance = 0
    elif movement_action == MovementAction.MOVE:
        max_distance = base_movement
    elif movement_action == MovementAction.ADVANCE:
        # Use the unit's stored advance roll
        unit_advance_roll = unit.get_advance_roll()
        if unit_advance_roll is not None:
            max_distance = base_movement + unit_advance_roll
        else:
            raise RuntimeError(f"Unit {unit.name} has no advance roll")
    elif movement_action == MovementAction.FALL_BACK:
        max_distance = base_movement
    else:
        return
    
    if max_distance <= 0:
        return
    
    # Convert unit position to screen coordinates
    center_x = int(current_position[0] * TILE_SIZE * zoom_level + offset_x)
    center_y = int(current_position[1] * TILE_SIZE * zoom_level + offset_y)
    
    # Calculate radius in screen pixels
    radius = int(max_distance * TILE_SIZE * zoom_level)
    
    # Choose color based on movement type
    if movement_action == MovementAction.MOVE:
        color = (0, 255, 0, 64)  # Green for normal move
        border_color = (0, 200, 0)
    elif movement_action == MovementAction.ADVANCE:
        color = (255, 255, 0, 64)  # Yellow for advance
        border_color = (200, 200, 0)
    elif movement_action == MovementAction.FALL_BACK:
        color = (255, 128, 0, 64)  # Orange for fall back
        border_color = (200, 100, 0)
    else:
        color = (128, 128, 128, 64)  # Gray for other actions
        border_color = (100, 100, 100)
    
    # Create a surface with per-pixel alpha for the range circle
    if radius > 0:
        range_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(range_surface, color, (radius, radius), radius)
        
        # Blit the transparent range circle onto the battlefield
        screen.blit(range_surface, (center_x - radius, center_y - radius))
        
        # Draw the border circle
        pygame.draw.circle(screen, border_color, (center_x, center_y), radius, 3)
        
        # Draw action text at the bottom of the circle
        try:
            font = pygame.font.SysFont('Arial', max(16, int(20 * zoom_level)), bold=True)
            action_text = movement_action.name.replace('_', ' ').title()
            if movement_action == MovementAction.ADVANCE:
                unit_advance_roll = unit.get_advance_roll()
                if unit_advance_roll is not None:
                    action_text += f" ({unit.movement}\" + {unit_advance_roll}\" = {max_distance}\")"
                else:
                    action_text += f" (up to {max_distance}\")"
            else:
                action_text += f" ({max_distance}\")"
            
            # Add model identifier if a specific model is selected
            if selected_model and len(unit.models) > 1:
                model_index = unit.models.index(selected_model) + 1
                action_text += f" [Model {model_index}]"
            
            text_surface = font.render(action_text, True, border_color)
            text_rect = text_surface.get_rect()
            text_rect.center = (center_x, center_y + radius + text_rect.height // 2 + 5)
            screen.blit(text_surface, text_rect)
        except:
            # Fallback if font creation fails
            pass


def draw_weapon_ranges(screen: pygame.Surface, unit, selected_weapon_profile, zoom_level: float, offset_x: int, offset_y: int) -> None:
    """Draw visual indicators showing the weapon range for each model that has the selected weapon"""
    if not selected_weapon_profile or not unit or not unit.models:
        return
    
    # TILE_SIZE is defined at the top of this file
    weapon_range = selected_weapon_profile.range.max
    if weapon_range <= 0:
        return  # Skip melee weapons
    
    # Choose color based on weapon type and special rules
    if selected_weapon_profile.is_pistol():
        range_color = (255, 100, 255, 64)  # Magenta for pistols
        border_color = (200, 50, 200)
    elif selected_weapon_profile.is_assault():
        range_color = (255, 255, 0, 64)  # Yellow for assault
        border_color = (200, 200, 0)  
    elif selected_weapon_profile.is_heavy():
        range_color = (255, 128, 0, 64)  # Orange for heavy
        border_color = (200, 100, 0)
    elif selected_weapon_profile.is_rapid_fire():
        range_color = (0, 255, 255, 64)  # Cyan for rapid fire
        border_color = (0, 200, 200)
    else:
        range_color = (0, 255, 0, 64)  # Green for other ranged weapons
        border_color = (0, 200, 0)
    
    # Draw range circle for each model that has this weapon
    models_with_weapon = []
    for model in unit.models:
        if not model.is_alive:
            continue
        
        # Check if this model has the selected weapon
        has_weapon = False
        for wargear in model.wargear:
            if wargear == selected_weapon_profile.parent_wargear:
                has_weapon = True
                break
        
        if has_weapon:
            models_with_weapon.append(model)
            
            # Get model position
            model_pos = model.get_location()
            
            # Convert model position to screen coordinates
            center_x = int(model_pos[0] * TILE_SIZE * zoom_level + offset_x)
            center_y = int(model_pos[1] * TILE_SIZE * zoom_level + offset_y)
            
            # Calculate radius in screen pixels
            radius = int(weapon_range * TILE_SIZE * zoom_level)
            
            if radius > 0:
                # Create a surface with per-pixel alpha for the range circle
                range_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(range_surface, range_color, (radius, radius), radius)
                
                # Blit the transparent range circle onto the battlefield
                screen.blit(range_surface, (center_x - radius, center_y - radius))
                
                # Draw the border circle with thinner line for individual models
                pygame.draw.circle(screen, border_color, (center_x, center_y), radius, 1)
    
    # Draw weapon information text
    if models_with_weapon:
        try:
            font = pygame.font.SysFont('Arial', max(14, int(16 * zoom_level)), bold=True)
            weapon_name = selected_weapon_profile.parent_wargear.name
            if len(selected_weapon_profile.parent_wargear.profiles) > 1:
                weapon_name += f" ({selected_weapon_profile.name})"
            
            info_text = f"{weapon_name} - Range {weapon_range}\" ({len(models_with_weapon)} models)"
            text_surface = font.render(info_text, True, border_color)
            
            # Position text at top of screen
            text_rect = text_surface.get_rect()
            text_rect.center = (screen.get_width() // 2, 30)
            
            # Draw background for text
            bg_rect = text_rect.inflate(20, 10)
            pygame.draw.rect(screen, (0, 0, 0, 128), bg_rect)
            pygame.draw.rect(screen, border_color, bg_rect, 2)
            
            screen.blit(text_surface, text_rect)
        except:
            # Fallback if font creation fails
            pass


class ShootingDeclarationDialog:
    """Dialog for declaring shooting attacks"""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 500
        self.height = 600
        self.x = 50
        self.y = 50
        self.visible = False
        
        # Unit and callback
        self.unit = None
        self.callback = None
        self.game_map = None
        self.game_view = None
        
        # Weapon selection state
        self.selected_weapon_profile = None
        self.weapon_selected_for_targeting = None  # Legacy - will be removed
        
        # Declarations storage
        self.weapon_declarations = []
        
        # Available weapons and targets
        self.available_weapons = []
        self.available_targets = []
        
        # UI state
        self.scroll_offset = 0
        self.hovered_weapon_index = -1
        self.hovered_declaration_index = -1
        self.hovered_button = None
        self.hovered_weapon = -1  # Add this for consistency
        
        # Targeting state
        self.is_targeting_mode = False
        self.current_weapon_for_targeting = None
        
        # Colors
        self.text_color = (255, 255, 255)
        self.bg_color = (50, 50, 50, 230)
        self.border_color = (100, 100, 100)
        self.button_color = (80, 80, 80)
        self.button_hover_color = (120, 120, 120)
        self.selected_color = (0, 150, 255)
        self.valid_target_color = (0, 200, 0)
        self.invalid_target_color = (200, 0, 0)
    
    def show(self, unit, callback, game_map=None, game_view=None):
        """Show the shooting declaration dialog"""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        self.game_view = game_view
        self.visible = True
        
        # Hide weapon choice dialog if it's visible
        if game_view and hasattr(game_view, 'weapon_choice_dialog'):
            game_view.weapon_choice_dialog.hide()
            print("🔧 ShootingDeclarationDialog: Hiding weapon_choice_dialog")
        
        # Reset state
        self.weapon_declarations = []
        self.selected_weapon_profile = None
        self.is_targeting_mode = False
        self.current_weapon_for_targeting = None
        
        # Populate available weapons and targets
        self._get_available_weapons()
        self._get_available_targets()
        
        # Position dialog based on player (left for Player 1, right for Player 2)
        if unit.get_parent_army() and unit.get_parent_army().player:
            player_name = unit.get_parent_army().player.name
            if "Player 1" in player_name or "1" in player_name:
                # Player 1 - position on left side of battlefield
                self.x = 50  # Small margin from left edge
            else:
                # Player 2 - position on right side of battlefield
                self.x = self.screen_width - self.width - 50  # Small margin from right edge
        else:
            # Default to center
            self.x = (self.screen_width - self.width) // 2
        
        self.y = 50  # Small margin from top
    
    def hide(self):
        """Hide the dialog"""
        print("🔍 hide() called - clearing targeting mode")
        # Debug: Print stack trace to see what's calling this
        import traceback
        print("🔍 Hide called from:")
        traceback.print_stack()
        
        self.visible = False
        self.is_targeting_mode = False
        self.current_weapon_for_targeting = None
    
    def _get_available_weapons(self):
        """Get all ranged weapons the unit can use"""
        self.available_weapons = []
        
        for model in self.unit.models:
            if not model.is_alive:
                continue
                
            for wargear in model.wargear:
                if wargear.is_ranged():
                    # Skip this weapon if any profile has already been declared
                    if self._is_weapon_already_declared(wargear):
                        continue
                        
                    for profile_name, profile in wargear.profiles.items():
                        # Check if this weapon can be used (not advanced unless allowed, etc.)
                        if self._can_use_weapon(profile):
                            # Check if we already have this weapon profile
                            existing = next((w for w in self.available_weapons 
                                           if w['profile'] == profile), None)
                            if existing:
                                existing['models'].append(model)
                            else:
                                self.available_weapons.append({
                                    'profile': profile,
                                    'models': [model],
                                    'wargear': wargear
                                })
        
        return self.available_weapons
    
    def _get_available_targets(self):
        """Get all valid target units"""
        self.available_targets = []
        
        if not self.game_map:
            return
            
        for enemy_unit in self.game_map.get_enemy_units(self.unit):
            if enemy_unit.is_alive():
                self.available_targets.append(enemy_unit)
    
    def _can_use_weapon(self, weapon_profile):
        """Check if a weapon can be used by the unit"""
        # Check if unit advanced and weapon can't shoot after advance
        if (self.unit.round_state.advanced_this_round and 
            not self.unit.can_shoot_after_advance(weapon_profile)):
            return False
        
        # Check if unit fell back
        if self.unit.round_state.fell_back_this_round:
            return False
        
        # Check if unit already shot this round
        if self.unit.round_state.shot_this_round:
            return False
        
        return True
    
    def _can_target_unit(self, weapon_profile, target_unit):
        """Check if a weapon can target a specific unit"""
        # Check if any model with this weapon can see and reach the target
        for weapon_info in self.available_weapons:
            if weapon_info['profile'] == weapon_profile:
                for model in weapon_info['models']:
                    closest_target_model, distance = model.return_closest_model_in_unit(target_unit)
                    if (distance <= weapon_profile.range.max and 
                        self._has_line_of_sight(model, closest_target_model)):
                        return True
        return False
    
    def _has_line_of_sight(self, shooting_model, target_model):
        """Check if there's line of sight between models"""
        # Simple line of sight check - can be enhanced later
        return True
    
    def _get_models_with_weapon(self, weapon_profile):
        """Get models that have this weapon"""
        models_with_weapon = []
        for model in self.unit.models:
            if model.is_alive:
                for wargear in model.wargear:
                    if wargear == weapon_profile.parent_wargear:
                        models_with_weapon.append(model)
                        break
        return models_with_weapon
    
    def handle_event(self, event):
        """Handle pygame events"""
        if not self.visible and not self.is_targeting_mode:
            return False
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.is_targeting_mode:
                    self.clear_targeting_mode()
                    return True
                else:
                    self.hide()
                    return True
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.visible:
                # Handle dialog clicks when visible
                return self.handle_click(event.pos)
            elif self.is_targeting_mode:
                # Handle battlefield targeting when in targeting mode
                print(f"🎯 ShootingDeclarationDialog: Mouse click during targeting mode at {event.pos}")
                return self.handle_battlefield_targeting(event.pos[0], event.pos[1])
        
        if event.type == pygame.MOUSEMOTION:
            if self.visible:
                self.update_hover(event.pos)
                return True
        
        if event.type == pygame.MOUSEWHEEL:
            if self.visible:
                self.scroll(event.y)
                return True
        
        return False
    
    def handle_click(self, mouse_pos):
        """Handle mouse clicks"""
        x, y = mouse_pos
        
        # Check if clicking on weapons list
        weapon_clicked = self._handle_weapon_click(x, y)
        if weapon_clicked:
            return True
        
        # Check if clicking on declarations list
        declaration_clicked = self._handle_declaration_click(x, y)
        if declaration_clicked:
            return True
        
        # Check if clicking on buttons
        button_clicked = self._handle_button_click(x, y)
        if button_clicked:
            return True
        
        return False
    
    def _handle_weapon_click(self, x, y):
        """Handle clicks on the weapons list"""
        if not (self.x + 10 <= x <= self.x + self.width - 10):
            return False
        
        # Calculate weapon list area
        weapon_list_y = self.y + 80  # Below title
        weapon_list_height = self.height - 200  # Leave space for declarations and buttons
        
        if not (weapon_list_y <= y <= weapon_list_y + weapon_list_height):
            return False
        
        # Calculate which weapon was clicked
        relative_y = y - weapon_list_y + self.scroll_offset
        weapon_index = relative_y // 50  # 50 pixels per weapon
        
        available_weapons = self._get_available_weapons()
        if 0 <= weapon_index < len(available_weapons):
            weapon_info = available_weapons[weapon_index]
            weapon_profile = weapon_info['profile']
            wargear = weapon_info['wargear']
            
            # Check if weapon can be used and hasn't been declared already
            if self._can_use_weapon(weapon_profile) and not self._is_weapon_already_declared(wargear):
                print(f"🎯 Selected weapon: {weapon_profile.parent_wargear.name}")
                self.select_weapon_for_targeting(weapon_profile)
                return True
            else:
                print(f"❌ Cannot use {weapon_profile.parent_wargear.name} - already declared or unavailable")
        
        return False
    
    def _find_existing_declaration(self, weapon_profile):
        """Find if a weapon profile is already declared"""
        for declaration in self.weapon_declarations:
            if declaration['weapon_profile'] == weapon_profile:
                return declaration
        return None
    
    def _is_weapon_already_declared(self, wargear):
        """Check if any profile of this weapon has already been declared"""
        for declaration in self.weapon_declarations:
            if declaration['weapon_profile'].parent_wargear == wargear:
                return True
        return False
    
    def _has_split_fire(self, weapon_profile):
        """Check if a weapon has split fire ability"""
        return weapon_profile.is_split_fire()
    
    def _handle_declaration_click(self, x, y):
        """Handle clicks on the declarations list"""
        # Calculate declarations list area
        declarations_x = self.x + 10
        declarations_y = self.y + 350 + self.scroll_offset
        declarations_width = self.width - 20
        declarations_height = 150
        
        if (declarations_x <= x <= declarations_x + declarations_width and 
            declarations_y <= y <= declarations_y + declarations_height):
            
            # Calculate which declaration was clicked
            click_y = y - declarations_y
            declaration_index = click_y // 35  # 35 pixels per declaration
            
            if 0 <= declaration_index < len(self.weapon_declarations):
                # Remove this declaration
                del self.weapon_declarations[declaration_index]
                return True
        
        return False
    
    def _handle_button_click(self, x, y):
        """Handle clicks on buttons"""
        # Execute button
        execute_x = self.x + 10
        execute_y = self.y + self.height - 50
        execute_width = 200
        execute_height = 35
        
        if (execute_x <= x <= execute_x + execute_width and 
            execute_y <= y <= execute_y + execute_height):
            self.execute_shooting()
            return True
        
        # Cancel button
        cancel_x = self.x + self.width - 160
        cancel_y = self.y + self.height - 50
        cancel_width = 140
        cancel_height = 35
        
        if (cancel_x <= x <= cancel_x + cancel_width and 
            cancel_y <= y <= cancel_y + cancel_height):
            print("✅ Cancel button clicked")
            self.hide()
            return True
        
        print(f"❌ Button click not detected at ({x}, {y})")
        print(f"   Dialog bounds: ({self.x}, {self.y}) to ({self.x + self.width}, {self.y + self.height})")
        print(f"   Execute button: ({execute_x}, {execute_y}) to ({execute_x + execute_width}, {execute_y + execute_height})")
        print(f"   Cancel button: ({cancel_x}, {cancel_y}) to ({cancel_x + cancel_width}, {cancel_y + cancel_height})")
        return False
    
    def scroll(self, delta):
        """Scroll the dialog"""
        self.scroll_offset += delta * 20
        self.scroll_offset = max(-100, min(0, self.scroll_offset))
    
    def update_hover(self, mouse_pos):
        """Update hover states"""
        x, y = mouse_pos
        
        # Update weapon hover
        self.hovered_weapon = None
        weapons_x = self.x + 10
        weapons_y = self.y + 80  # Don't add scroll_offset here - it's for drawing only
        weapons_width = self.width - 20
        weapons_height = 200
        
        if (weapons_x <= x <= weapons_x + weapons_width and 
            weapons_y <= y <= weapons_y + weapons_height):
            # Account for scroll offset in the relative calculation
            relative_y = (y - weapons_y) - self.scroll_offset
            weapon_index = relative_y // 50
            if 0 <= weapon_index < len(self.available_weapons):
                self.hovered_weapon = weapon_index
    
    def execute_shooting(self):
        """Execute all shooting declarations"""
        if not self.weapon_declarations:
            print("❌ No shooting declarations to execute")
            return
        
        print(f"🎯 Executing {len(self.weapon_declarations)} shooting declarations...")
        
        # Execute shooting using the unit's new method
        success = self.unit.execute_shooting_declarations(self.weapon_declarations, self.game_map)
        
        if success:
            print(f"✅ {self.unit.name} completed shooting phase")
        else:
            print(f"❌ {self.unit.name} failed to execute shooting")
        
        # Call the callback with the results
        if self.callback:
            self.callback(self.weapon_declarations)
        
        # Hide the dialog
        self.hide()
    
    def draw(self, screen):
        """Draw the shooting declaration dialog"""
        if not self.visible:
            return
        
        # Create surface for dialog
        dialog_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        
        # Draw background
        pygame.draw.rect(dialog_surface, (50, 50, 50, 230), (0, 0, self.width, self.height))
        pygame.draw.rect(dialog_surface, (100, 100, 100), (0, 0, self.width, self.height), 2)
        
        # Draw title
        font_large = pygame.font.Font(None, 24)
        title_text = f"Shooting Declaration - {self.unit.name}"
        title_surface = font_large.render(title_text, True, (255, 255, 255))
        dialog_surface.blit(title_surface, (10, 10))
        
        # Draw instructions
        font_small = pygame.font.Font(None, 16)
        instructions = "Select a weapon to target, or click Execute to resolve shooting"
        instructions_surface = font_small.render(instructions, True, (200, 200, 200))
        dialog_surface.blit(instructions_surface, (10, 40))
        
        # Draw weapons list
        self._draw_weapons_list(dialog_surface, font_large, font_small)
        
        # Draw declarations list
        self._draw_declarations_list(dialog_surface, font_large, font_small)
        
        # Draw buttons
        self._draw_buttons(dialog_surface, font_large)
        
        # Draw dialog on screen
        screen.blit(dialog_surface, (self.x, self.y))
    
    def _draw_weapons_list(self, screen, font_large, font_small):
        """Draw the available weapons list"""
        x = 10  # Relative to dialog surface
        y = 80 + self.scroll_offset  # Relative to dialog surface
        
        # Draw section title
        title = "Available Weapons"
        title_surface = font_large.render(title, True, self.text_color)
        screen.blit(title_surface, (x, y - 20))
        
        # Get available weapons
        available_weapons = self._get_available_weapons()
        
        # Draw weapons
        for i, weapon_info in enumerate(available_weapons):
            weapon_y = y + i * 50  # Larger spacing
            
            # Handle both dictionary and WargearProfile formats
            if isinstance(weapon_info, dict):
                weapon_profile = weapon_info['profile']
                models_count = len(weapon_info['models'])
            else:
                # weapon_info is a WargearProfile object
                weapon_profile = weapon_info
                # Count models with this weapon
                models_count = 0
                for model in self.unit.models:
                    if model.is_alive:
                        for wargear in model.wargear:
                            if wargear == weapon_profile.parent_wargear:
                                models_count += 1
                                break
            
            # Check if this weapon is already declared
            existing_declaration = self._find_existing_declaration(weapon_profile)
            has_split_fire = weapon_profile.is_split_fire()
            
            # Background color
            bg_color = self.button_color
            if i == self.hovered_weapon:
                bg_color = self.button_hover_color
            if (self.selected_weapon_profile and 
                self.selected_weapon_profile == weapon_profile):
                bg_color = self.selected_color
            if self.weapon_selected_for_targeting == weapon_profile:
                bg_color = (100, 150, 255)  # Blue for selected weapon
            
            # If weapon is already declared and can't split fire, gray it out
            if existing_declaration and not has_split_fire:
                bg_color = (60, 60, 60)  # Darker gray for unavailable weapons
            
            # Draw weapon background
            pygame.draw.rect(screen, bg_color, (x, weapon_y, self.width - 20, 40))
            pygame.draw.rect(screen, self.border_color, (x, weapon_y, self.width - 20, 40), 1)
            
            # Draw weapon name
            weapon_name = weapon_profile.parent_wargear.name
            if weapon_profile.name != 'default':
                weapon_name += f" - {weapon_profile.name}"
            weapon_name += f" ({models_count} models)"
            
            if existing_declaration:
                weapon_name += f" → {existing_declaration['target_unit'].name[:15]}..."
                if has_split_fire:
                    weapon_name += " (Split)"
            weapon_surface = font_small.render(weapon_name, True, self.text_color)
            screen.blit(weapon_surface, (x + 5, weapon_y + 5))
            
            # Draw weapon stats
            stats = f"Range: {weapon_profile.range.max}\" | A: {weapon_profile.attacks}"
            if has_split_fire:
                stats += " | Split Fire"
            stats_surface = font_small.render(stats, True, self.text_color)
            screen.blit(stats_surface, (x + 5, weapon_y + 20))
    
    def _draw_declarations_list(self, screen, font_large, font_small):
        """Draw the shooting declarations list"""
        x = 10  # Relative to dialog surface
        y = 350 + self.scroll_offset  # Relative to dialog surface
        
        # Draw section title
        title = "Declarations Made"
        title_surface = font_large.render(title, True, self.text_color)
        screen.blit(title_surface, (x, y - 20))
        
        # Draw declarations
        for i, declaration in enumerate(self.weapon_declarations):
            declaration_y = y + i * 35  # Larger spacing
            
            # Background
            pygame.draw.rect(screen, self.selected_color, (x, declaration_y, self.width - 20, 30))
            pygame.draw.rect(screen, self.border_color, (x, declaration_y, self.width - 20, 30), 1)
            
            # Declaration text (shortened)
            weapon_name = declaration['weapon_profile'].parent_wargear.name
            if declaration['weapon_profile'].name != 'default':
                weapon_name += f" - {declaration['weapon_profile'].name}"
            target_name = declaration['target_unit'].name[:15] + "..." if len(declaration['target_unit'].name) > 15 else declaration['target_unit'].name
            declaration_text = f"{weapon_name} → {target_name}"
            text_surface = font_small.render(declaration_text, True, self.text_color)
            screen.blit(text_surface, (x + 5, declaration_y + 5))
    
    def _draw_buttons(self, screen, font_large):
        """Draw the dialog buttons"""
        # Execute button (relative to dialog surface, not screen)
        execute_x = 10
        execute_y = self.height - 50
        execute_width = 200
        execute_height = 35
        
        pygame.draw.rect(screen, self.button_color, (execute_x, execute_y, execute_width, execute_height))
        pygame.draw.rect(screen, self.border_color, (execute_x, execute_y, execute_width, execute_height), 2)
        
        execute_text = "Execute Shooting"
        execute_surface = font_large.render(execute_text, True, self.text_color)
        text_rect = execute_surface.get_rect(center=(execute_x + execute_width//2, execute_y + execute_height//2))
        screen.blit(execute_surface, text_rect)
        
        # Cancel button (relative to dialog surface, not screen)
        cancel_x = self.width - 160
        cancel_y = self.height - 50
        cancel_width = 140
        cancel_height = 35
    
        pygame.draw.rect(screen, self.button_color, (cancel_x, cancel_y, cancel_width, cancel_height))
        pygame.draw.rect(screen, self.border_color, (cancel_x, cancel_y, cancel_width, cancel_height), 2)
        
        cancel_text = "Cancel"
        cancel_surface = font_large.render(cancel_text, True, self.text_color)
        text_rect = cancel_surface.get_rect(center=(cancel_x + cancel_width//2, cancel_y + cancel_height//2))
        screen.blit(cancel_surface, text_rect)

    def _reposition_dialog_for_targeting(self, is_targeting):
        """Reposition dialog to avoid battlefield overlap when targeting"""
        if is_targeting:
            # When targeting, move dialog to top of screen to avoid battlefield overlap
            self.y = 20  # Small margin from top
        else:
            # When not targeting, restore original positioning based on player
            if self.unit.get_parent_army() and self.unit.get_parent_army().player:
                player_name = self.unit.get_parent_army().player.name
                if "Player 1" in player_name or "1" in player_name:
                    # Player 1 - position on left side of battlefield
                    self.x = 50  # Small margin from left edge
                else:
                    # Player 2 - position on right side of battlefield
                    self.x = self.screen_width - self.width - 50  # Small margin from right edge
            else:
                # Fallback to center if player info not available
                self.x = (self.screen_width - self.width) // 2
            
            # Center vertically when not targeting
            self.y = (self.screen_height - self.height) // 2

    def _handle_battle_motion(self, mouse_pos) -> bool:
        """Handle mouse motion during battle phases"""
        x, y = mouse_pos
        
        # Update hover states for UI components
        if hasattr(self.game_view, 'shooting_declaration_dialog') and self.game_view.shooting_declaration_dialog.visible:
            self.game_view.shooting_declaration_dialog.update_hover((x, y))
            return True
        
        if hasattr(self.game_view, 'movement_choice_dialog') and self.game_view.movement_choice_dialog.visible:
            self.game_view.movement_choice_dialog.update_hover((x, y))
            return True
        
        # Update roster pane hovers
        if self.game_view.left_roster_pane.rect.collidepoint(x, y):
            return True
        elif self.game_view.right_roster_pane.rect.collidepoint(x, y):
            return True
        
        return False
    
    def _handle_battle_release(self, mouse_pos, button) -> bool:
        """Handle mouse button release during battle phases"""
        # Currently no specific handling needed for mouse release
        return False

    def hide(self):
        """Hide the shooting declaration dialog"""
        self.visible = False
        self.is_targeting_mode = False
        self.current_weapon_for_targeting = None
    
    def select_weapon_for_targeting(self, weapon_profile):
        """Select a weapon and enter targeting mode"""
        print(f"🎯 select_weapon_for_targeting called with {weapon_profile.parent_wargear.name}")
        self.selected_weapon_profile = weapon_profile
        self.current_weapon_for_targeting = weapon_profile
        self.is_targeting_mode = True
        self.visible = False  # Close dialog
        print(f"🎯 Targeting mode set: is_targeting_mode={self.is_targeting_mode}, current_weapon_for_targeting={self.current_weapon_for_targeting}")
        print(f"🎯 Selected {weapon_profile.parent_wargear.name} for targeting - click on battlefield")
    
    def handle_battlefield_targeting(self, x: int, y: int) -> bool:
        """Handle battlefield clicks when in targeting mode"""
        if not self.is_targeting_mode or not self.current_weapon_for_targeting:
            print(f"🔍 Targeting check failed: is_targeting_mode={self.is_targeting_mode}, current_weapon_for_targeting={self.current_weapon_for_targeting}")
            return False
        
        print(f"🎯 Battlefield targeting called at ({x}, {y})")
        
        # Find unit at this position (get_unit_at_position expects screen coordinates)
        target_unit = self.game_view.get_unit_at_position(x, y)
        
        if not target_unit:
            # Convert to game coordinates for debug output
            game_x, game_y = self.game_view.screen_to_game_coords((x, y))
            print(f"❌ No unit found at screen ({x}, {y}) / game ({game_x}, {game_y})")
            return False
        
        print(f"🎯 Found target: {target_unit.name}")
        
        # Validate target
        if not self._can_target_unit(self.current_weapon_for_targeting, target_unit):
            print(f"❌ Cannot target {target_unit.name} with {self.current_weapon_for_targeting.parent_wargear.name}")
            return False
        
        # Create declaration
        declaration = {
            'weapon_profile': self.current_weapon_for_targeting,
            'target_unit': target_unit,
            'models': self._get_models_with_weapon(self.current_weapon_for_targeting)
        }
        
        # Add declaration to the list
        self.weapon_declarations.append(declaration)
        print(f"✅ Declared {self.current_weapon_for_targeting.parent_wargear.name} targeting {target_unit.name}")
        
        # Exit targeting mode and reopen dialog
        self.is_targeting_mode = False
        self.current_weapon_for_targeting = None
        self.visible = True
        
        return True
    
    def clear_targeting_mode(self):
        """Clear targeting mode (ESC key)"""
        if self.is_targeting_mode:
            self.is_targeting_mode = False
            self.current_weapon_for_targeting = None
            self.selected_weapon_profile = None
            self.visible = True  # Reopen dialog
            print("❌ Targeting mode cleared")

