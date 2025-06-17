import pygame
import textwrap
import math
from typing import Optional, Tuple, Dict, List
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
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_ACCENT = (100, 149, 237)  # Accent text
HEALTH_GOOD = (76, 175, 80)  # Green for good health
HEALTH_DAMAGED = (255, 193, 7)  # Yellow for damaged
HEALTH_CRITICAL = (244, 67, 54)  # Red for critical

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
    """Get a unique color variation for units of the same type or different character units"""
    # For Characters (especially Epic Heroes), assign different colors to different units
    if unit.is_character:
        character_units = [u for u in all_units if u.is_character]
        if len(character_units) > 1:
            try:
                unit_index = character_units.index(unit)
                return UNIT_COLOR_VARIATIONS[unit_index % len(UNIT_COLOR_VARIATIONS)]
            except (ValueError, IndexError):
                return (255, 255, 255)  # Fallback to white
    
    # For non-characters, use the original logic (same name units get different colors)
    same_type_units = [u for u in all_units if u.name == unit.name]
    if len(same_type_units) <= 1:
        return (255, 255, 255)  # Default white for single units
    
    try:
        unit_index = same_type_units.index(unit)
        return UNIT_COLOR_VARIATIONS[unit_index % len(UNIT_COLOR_VARIATIONS)]
    except (ValueError, IndexError):
        return (255, 255, 255)  # Fallback to white

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
            # Fallback to default fonts if system fonts fail
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
        
        # Player name and army info
        player_text = self.font_medium.render(f"{self.player_name}", True, TEXT_PRIMARY)
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
        all_units = getattr(self, 'all_units', self.roster)  # Use all_units if available, otherwise fallback to roster
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
        if not unit.deployed:
            health_text += " (Not Deployed)"
            health_color = TEXT_SECONDARY
        
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
        # Use system fonts for better clarity
        try:
            self.font_large = pygame.font.SysFont('Arial', FONT_LARGE, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=False)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
        except:
            # Fallback to default fonts if system fonts fail
            self.font_large = pygame.font.Font(None, FONT_LARGE)
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
        self.background_color = PANEL_BG
        self.text_color = TEXT_PRIMARY
        self.selected_unit = selected_unit

    def draw(self, surface: pygame.Surface, game: Game):
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

        # Game status line 1: Turn and Phase
        game_status = f"Turn {game.turn} - {game.phase.name.replace('_', ' ').title()}"
        game_text = self.font_medium.render(game_status, True, TEXT_PRIMARY)
        game_rect = game_text.get_rect(center=(x_center, y_offset + 10))
        surface.blit(game_text, game_rect)
        
        y_offset += 30
        
        # Player information
        current_player_text = f"{current_player.name}: {current_player.command_points} CP | Score: {current_player.score}"
        player_surface = self.font_small.render(current_player_text, True, TEXT_ACCENT)
        surface.blit(player_surface, (x_left, y_offset))
        
        opponent_text = f"{opponent.name}: {opponent.command_points} CP | Score: {opponent.score}"
        opponent_surface = self.font_small.render(opponent_text, True, TEXT_SECONDARY)
        opponent_rect = opponent_surface.get_rect()
        surface.blit(opponent_surface, (x_right - opponent_rect.width, y_offset))
        
        y_offset += 25
        
        # Army status
        current_army = current_player.get_army()
        opponent_army = opponent.get_army()
        
        if current_army and opponent_army:
            current_units_alive = len([u for u in current_army.units if u.is_alive()])
            opponent_units_alive = len([u for u in opponent_army.units if u.is_alive()])
            
            army_status = f"Units: {current_units_alive} vs {opponent_units_alive}"
            army_text = self.font_small.render(army_status, True, TEXT_SECONDARY)
            army_rect = army_text.get_rect(center=(x_center, y_offset))
            surface.blit(army_text, army_rect)


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
            # Fallback to default fonts if system fonts fail
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
        """Wrap text to fit within max_width"""
        words = text.split(' ')
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            if font.size(test_line)[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)  # Word is too long, add it anyway
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines


class GameView:
    def __init__(self, screen, env, game, game_map, player1, player2):
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
        
        # Mouse panning support
        self.panning = False
        self.pan_start_pos = (0, 0)
        self.pan_start_offset = (0, 0)
        
        # Create roster panes with reference to all units for color correlation
        # Roster panes now extend to full battlefield height + info pane height
        roster_pane_height = BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT
        self.left_roster_pane = RosterPane(0, 0, ROSTER_PANE_WIDTH, roster_pane_height, 
                                         player1.get_army().units, f"Player 1 ({player1.name})")
        self.right_roster_pane = RosterPane(BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH, 0, ROSTER_PANE_WIDTH, 
                                          roster_pane_height, player2.get_army().units, 
                                          f"Player 2 ({player2.name})")
        
        # Pass all units to roster panes for color correlation
        all_units = player1.get_army().units + player2.get_army().units
        self.left_roster_pane.all_units = all_units
        self.right_roster_pane.all_units = all_units
        
        # Position InfoPane between roster panes and below battlefield
        self.info_pane = InfoPane(ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT, 
                                BATTLEFIELD_WIDTH, INFO_PANE_HEIGHT, self.selected_unit)

    def on_mouse_press(self, x, y, button):
        # PRIORITY 1: Check if click is on unit detail panel first (highest priority)
        if self.detailed_unit and button == 1:  # Left click
            # Use the rect that was set during drawing (if it exists)
            if hasattr(self.unit_detail_panel, 'rect') and self.unit_detail_panel.rect:
                # Check if click is on the unit detail panel using the actual rect
                if self.unit_detail_panel.rect.collidepoint(x, y):
                    return  # CRITICAL: Exit early to prevent other actions
                else:
                    self.close_unit_details()
                    return  # Exit early since we handled the click
        
        if button == 1:  # Left mouse button
            # Check if click is in player1's roster pane
            if self.left_roster_pane.rect.collidepoint(x, y):
                self.left_roster_pane.on_mouse_press(x, y, button)
                self.selected_unit = self.left_roster_pane.selected_unit
            # Check if click is in player2's roster pane
            elif self.right_roster_pane.rect.collidepoint(x, y):
                self.right_roster_pane.on_mouse_press(x, y, button)
                self.selected_unit = self.right_roster_pane.selected_unit
            # Check if click is on the battlefield and a unit is selected
            elif self.selected_unit and not self.selected_unit.deployed and ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH:
                # Convert screen coordinates to game coordinates (accounting for zoom and pan)
                battlefield_x = (x - ROSTER_PANE_WIDTH - self.offset_x) / (TILE_SIZE * self.zoom_level)
                battlefield_y = (y - self.offset_y) / (TILE_SIZE * self.zoom_level)
                
                original_unit_position = self.selected_unit.get_position() if self.selected_unit.position else None
                original_model_positions = [model.get_location() for model in self.selected_unit.models] if self.selected_unit else []
                
                model_positions = self.selected_unit.calculate_model_positions(battlefield_x, battlefield_y, self.game_map, self.zoom_level)
                
                if model_positions:
                    for model, position in zip(self.selected_unit.models, model_positions):
                        model_x, model_y, model_z, model_facing = position
                        model.set_location(model_x, model_y, model_z, model_facing)
                    
                    unit_x = sum(pos[0] for pos in model_positions) / len(model_positions)
                    unit_y = sum(pos[1] for pos in model_positions) / len(model_positions)
                    self.selected_unit.set_position(unit_x, unit_y)
                    
                    if self.game_map.place_unit(self.selected_unit):
                        print(f"Unit {self.selected_unit.name} placed with centroid at ({unit_x}, {unit_y})")
                        self.selected_unit.deployed = True
                    else:
                        print("Failed to place unit")
                        self.reset_unit_position(self.selected_unit, original_unit_position, original_model_positions)
                else:
                    print("Unable to place all models in the unit")
                    self.reset_unit_position(self.selected_unit, original_unit_position, original_model_positions)
                
                self.selected_unit = None
                self.left_roster_pane.selected_unit = None
                self.right_roster_pane.selected_unit = None
            else:
                # Click outside of everything - close unit details if open
                if self.detailed_unit:
                    self.close_unit_details()
        
        elif button == 2:  # Middle mouse button - start panning
            # Only allow panning if mouse is over the battlefield
            if ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH:
                self.panning = True
                self.pan_start_pos = (x, y)
                self.pan_start_offset = (self.offset_x, self.offset_y)
        
        elif button == 3:  # Right mouse button - show unit details
            hovered_unit, _ = self.get_hovered_unit(x, y)
            if hovered_unit:
                self.detailed_unit = hovered_unit
                self.detail_panel_pos = (x, y)

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
        
        # Check if hovering over a unit on the battlefield
        if ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH:
            battlefield_x = (x - ROSTER_PANE_WIDTH) / TILE_SIZE / self.zoom_level - self.offset_x / TILE_SIZE
            battlefield_y = y / TILE_SIZE / self.zoom_level - self.offset_y / TILE_SIZE
            
            for unit in self.game_map.units:
                if unit.is_point_inside(battlefield_x, battlefield_y):
                    # Determine which roster the unit belongs to
                    if unit in self.player1.get_army().units:
                        return unit, self.left_roster_pane
                    elif unit in self.player2.get_army().units:
                        return unit, self.right_roster_pane
        
        return None, None

    def get_unit_at_position(self, x: float, y: float) -> Optional[Unit]:
        # Convert screen coordinates to game coordinates
        game_x = (x - ROSTER_PANE_WIDTH - self.offset_x) / (TILE_SIZE * self.zoom_level)
        game_y = (y - self.offset_y) / (TILE_SIZE * self.zoom_level)
        
        print(f"Checking for unit at game coordinates: ({game_x}, {game_y})")

        for player in [self.player1, self.player2]:
            for unit in [unit for unit in player.get_army().units if unit.deployed]:
                #print(f"Checking unit: {unit.name}")
                #print(f"Unit position: {unit.get_position()}")
                if unit.is_point_inside(game_x, game_y):
                    return unit
        
        #print("No unit found at position")
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

        # Draw objectives on the battlefield
        for objective in self.game_map.objectives:
            draw_objective(battlefield_surface, objective, self.zoom_level, self.offset_x, self.offset_y)

        # Draw units on the battlefield
        for unit in self.game_map.units:
            draw_units(battlefield_surface, unit, self.zoom_level, self.offset_x, self.offset_y, pygame.mouse.get_pos(), self.player1, self.player2)
        
        self.screen.blit(battlefield_surface, (ROSTER_PANE_WIDTH, 0))

        # Draw enhanced InfoPane
        self.info_pane.draw(self.screen, self.game)

        # Draw unit details panel if requested
        if self.detailed_unit:
            self.unit_detail_panel.draw(self.screen, self.detailed_unit, 
                                      self.detail_panel_pos[0], self.detail_panel_pos[1])

        # Draw move paths for all units
        for unit in self.game.get_current_player().get_army().units:
            self.draw_move_path(unit)

        pygame.display.update()

    def on_key_press(self, key):
        """Handle keyboard events"""
        if key == pygame.K_ESCAPE:
            # Close unit details panel if open
            if self.detailed_unit:
                self.close_unit_details()
        elif self.detailed_unit:
            # Keyboard scrolling in unit detail panel
            if key == pygame.K_UP or key == pygame.K_w:
                self.unit_detail_panel.scroll(-30)  # Scroll up
            elif key == pygame.K_DOWN or key == pygame.K_s:
                self.unit_detail_panel.scroll(30)   # Scroll down
            elif key == pygame.K_PAGEUP:
                self.unit_detail_panel.scroll(-150)  # Page up
            elif key == pygame.K_PAGEDOWN:
                self.unit_detail_panel.scroll(150)   # Page down
            elif key == pygame.K_HOME:
                self.unit_detail_panel.scroll_offset = 0  # Go to top
            elif key == pygame.K_END:
                self.unit_detail_panel.scroll_offset = self.unit_detail_panel.max_scroll  # Go to bottom

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

def draw_objective(screen: pygame.Surface, objective: Objective, zoom_level: float, offset_x: int, offset_y: int) -> None:
    if isinstance(objective.location, ObjectivePoint):
        pygame.draw.circle(screen, PURPLE, (int(objective.location.x * TILE_SIZE * zoom_level + offset_x), int(objective.location.y * TILE_SIZE * zoom_level + offset_y)), int(objective.location.control_radius * TILE_SIZE * zoom_level))

def draw_units(screen: pygame.Surface, unit: Unit, zoom_level: float, offset_x: int, offset_y: int, mouse_pos: Tuple[int, int], player1: Player, player2: Player) -> None:
    # Determine the color based on which player the unit belongs to
    color = GREEN if unit in player1.get_army().units else RED if unit in player2.get_army().units else BLUE
    
    # Get all units for color variation calculation
    all_units = player1.get_army().units + player2.get_army().units

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
    
    # Draw the unit type icon with color tinting
    draw_tinted_unit_icon(screen, center_x, center_y, icon_size, unit, icon_tint)
    
    # For multi-model units, draw individual model identifier
    if len(unit.models) > 1:
        draw_model_identifier(screen, center_x, center_y, icon_size, model_index, unit)
    
    # Draw wound indicator if model is damaged
    if not model.is_max_health:
        draw_prominent_wound_indicator(screen, center_x, center_y, icon_size, model)

def draw_tinted_unit_icon(screen: pygame.Surface, center_x: int, center_y: int, size: int, unit: Unit, tint_color: Tuple[int, int, int]) -> None:
    """Draw unit icon with color tinting for differentiation"""
    # Create a surface for the icon with alpha
    icon_surface = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
    icon_center = size  # Center of the icon surface
    
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
        tint_surface = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        tint_surface.fill((*tint_color, 120))  # Semi-transparent tint
        icon_surface.blit(tint_surface, (0, 0), special_flags=pygame.BLEND_MULT)
    
    # Blit the tinted icon to the screen
    screen.blit(icon_surface, (center_x - size, center_y - size))

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

def draw_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int]) -> None:
    # Legacy function kept for compatibility - redirects to enhanced version
    # This function is no longer used directly but kept in case other code references it
    if base.base_type == BaseType.CIRCULAR:
        draw_circular_base(screen, base, screen_x, screen_y, zoom_level, color)
    elif base.base_type == BaseType.ELLIPTICAL:
        draw_elliptical_base(screen, base, screen_x, screen_y, zoom_level, color)
    elif base.base_type == BaseType.HULL:
        draw_hull_base(screen, base, screen_x, screen_y, zoom_level, color)

def draw_circular_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int]) -> None:
    # Legacy function for backward compatibility
    radius = int(base.get_radius() * TILE_SIZE * zoom_level)
    pygame.draw.circle(screen, color, (screen_x, screen_y), radius)
    inner_radius = max(1, int(radius * 0.8))
    pygame.draw.circle(screen, (255, 255, 255), (screen_x, screen_y), inner_radius)

def draw_elliptical_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int]) -> None:
    # Legacy function for backward compatibility
    width = int(base.radius[0] * 2 * TILE_SIZE * zoom_level)
    height = int(base.radius[1] * 2 * TILE_SIZE * zoom_level)
    
    # Create a surface for the ellipse
    ellipse_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    ellipse_surface.fill((0, 0, 0, 0))  # Transparent background
    
    # Draw the outer ellipse
    pygame.draw.ellipse(ellipse_surface, color, (0, 0, width, height))
    
    # Draw the inner ellipse
    inner_width, inner_height = max(1, int(width * 0.8)), max(1, int(height * 0.8))
    inner_rect = pygame.Rect((width - inner_width) // 2, (height - inner_height) // 2, inner_width, inner_height)
    pygame.draw.ellipse(ellipse_surface, (255, 255, 255), inner_rect)
    
    # Rotate the surface
    angle_degrees = math.degrees(base.facing)
    rotated_surface = pygame.transform.rotate(ellipse_surface, -angle_degrees)
    
    # Calculate the position to blit the rotated surface
    blit_pos = (screen_x - rotated_surface.get_width() // 2, 
                screen_y - rotated_surface.get_height() // 2)
    
    # Blit the rotated surface onto the screen
    screen.blit(rotated_surface, blit_pos)

def draw_hull_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int]) -> None:
    # Legacy function for backward compatibility
    width = int(base.radius[0] * 2 * TILE_SIZE * zoom_level)
    height = int(base.radius[1] * 2 * TILE_SIZE * zoom_level)
    
    # Create a surface for the hull
    hull_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    hull_surface.fill((0, 0, 0, 0))  # Transparent background
    
    # Draw the outer hull
    pygame.draw.rect(hull_surface, color, (0, 0, width, height))
    
    # Draw the inner hull
    inner_width, inner_height = max(1, int(width * 0.8)), max(1, int(height * 0.8))
    inner_rect = pygame.Rect((width - inner_width) // 2, (height - inner_height) // 2, inner_width, inner_height)
    pygame.draw.rect(hull_surface, (255, 255, 255), inner_rect)
    
    # Rotate the surface
    angle_degrees = math.degrees(base.facing)
    rotated_surface = pygame.transform.rotate(hull_surface, -angle_degrees)
    
    # Calculate the position to blit the rotated surface
    blit_pos = (screen_x - rotated_surface.get_width() // 2, 
                screen_y - rotated_surface.get_height() // 2)
    
    # Blit the rotated surface onto the screen
    screen.blit(rotated_surface, blit_pos)

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
