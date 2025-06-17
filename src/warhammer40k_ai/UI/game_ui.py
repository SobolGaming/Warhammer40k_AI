import pygame
import textwrap
import math
from typing import Optional, Tuple, Dict, List
from warhammer40k_ai.classes.unit import Unit
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
PAN_SPEED = 5

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
        
        # Unit name (truncated if too long)
        unit_name = unit.name
        if len(unit_name) > 20:
            unit_name = unit_name[:17] + "..."
        name_text = self.font_medium.render(unit_name, True, TEXT_PRIMARY)
        surface.blit(name_text, (x_left, y_offset))
        
        # Unit cost
        cost_text = self.font_small.render(f"{unit.get_unit_cost()}pts", True, TEXT_ACCENT)
        cost_rect = cost_text.get_rect()
        surface.blit(cost_text, (x_right - cost_rect.width, y_offset))
        
        y_offset += 20
        
        # Model count and composition
        model_count_text = f"{len(unit.models)} models"
        if unit.is_character:
            model_count_text += " (Character)"
        elif unit.is_leader:
            model_count_text += " (Leader)"
        
        models_text = self.font_small.render(model_count_text, True, TEXT_SECONDARY)
        surface.blit(models_text, (x_left, y_offset))
        
        y_offset += 16
        
        # Health status
        health_percent = unit.health_percent
        if health_percent == 100:
            health_color = HEALTH_GOOD
            health_text = "Full Health"
        elif health_percent > 50:
            health_color = HEALTH_DAMAGED
            health_text = f"{health_percent:.0f}% Health"
        else:
            health_color = HEALTH_CRITICAL
            health_text = f"{health_percent:.0f}% Health"
        
        health_surface = self.font_tiny.render(health_text, True, health_color)
        surface.blit(health_surface, (x_left, y_offset))
        
        # Deployment status
        if unit.deployed:
            status_text = "Deployed"
            status_color = HEALTH_GOOD
        else:
            status_text = "Not Deployed"
            status_color = TEXT_SECONDARY
        
        status_surface = self.font_tiny.render(status_text, True, status_color)
        status_rect = status_surface.get_rect()
        surface.blit(status_surface, (x_right - status_rect.width, y_offset))
        
        y_offset += 14
        
        # Primary weapons summary (if space allows)
        if unit.models and unit.models[0].wargear and y_offset < button_rect.bottom - 10:
            weapons = []
            for wargear in unit.models[0].wargear[:2]:  # Show first 2 weapons
                if wargear and hasattr(wargear, 'profiles'):
                    weapons.append(wargear.name)
            
            if weapons:
                weapons_text = "Weapons: " + ", ".join(weapons)
                if len(weapons_text) > 25:
                    weapons_text = weapons_text[:22] + "..."
                weapons_surface = self.font_tiny.render(weapons_text, True, TEXT_SECONDARY)
                surface.blit(weapons_surface, (x_left, y_offset))

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
                ability_name = self.font_small.render(f"• {ability.name}", True, TEXT_ACCENT)
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
        
        # Keywords on next line
        if hasattr(profile, 'keywords') and profile.keywords:
            keywords_str = ", ".join(profile.keywords)
            if keywords_str:
                # Wrap keywords if too long
                max_keyword_width = self.width - x_pos - 40
                keywords_wrapped = self.wrap_text(f"Keywords: {keywords_str}", self.font_tiny, max_keyword_width)
                for line in keywords_wrapped:
                    keyword_text = self.font_tiny.render(f"        {line}", True, TEXT_ACCENT)
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
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.selected_unit = None
        
        # Create enhanced RosterPane instances
        self.player1_roster = RosterPane(0, 0, ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT, 
                                       player1.get_army().units, player1.name)
        self.player2_roster = RosterPane(BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH, 0, ROSTER_PANE_WIDTH, 
                                       BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT, player2.get_army().units, player2.name)
        self.player1_roster.game_map = game_map
        self.player2_roster.game_map = game_map

        # Create enhanced InfoPane
        self.info_pane = InfoPane(ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT, BATTLEFIELD_WIDTH, INFO_PANE_HEIGHT, self.selected_unit)
        
        # Create unit detail panel
        self.unit_detail_panel = UnitDetailPanel()
        self.show_unit_details = None
        self.detail_panel_pos = (0, 0)

    def on_mouse_press(self, x, y, button):
        # PRIORITY 1: Check if click is on unit detail panel first (highest priority)
        if self.show_unit_details and button == 1:  # Left click
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
            if self.player1_roster.rect.collidepoint(x, y):
                self.player1_roster.on_mouse_press(x, y, button)
                self.selected_unit = self.player1_roster.selected_unit
            # Check if click is in player2's roster pane
            elif self.player2_roster.rect.collidepoint(x, y):
                self.player2_roster.on_mouse_press(x, y, button)
                self.selected_unit = self.player2_roster.selected_unit
            # Check if click is on the battlefield and a unit is selected
            elif self.selected_unit and not self.selected_unit.deployed and ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH:
                battlefield_x = (x - ROSTER_PANE_WIDTH) / TILE_SIZE
                battlefield_y = y / TILE_SIZE
                
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
                self.player1_roster.selected_unit = None
                self.player2_roster.selected_unit = None
            else:
                # Click outside of everything - close unit details if open
                if self.show_unit_details:
                    self.close_unit_details()
        
        elif button == 3:  # Right mouse button - show unit details
            hovered_unit, _ = self.get_hovered_unit(x, y)
            if hovered_unit:
                self.show_unit_details = hovered_unit
                self.detail_panel_pos = (x, y)

    def on_mouse_scroll(self, x, y, scroll_y):
        """Handle mouse scroll events"""
        # PRIORITY 1: Check if scrolling in unit detail panel first (highest priority)
        if self.show_unit_details:
            # Use the rect that was set during drawing (if it exists)
            if hasattr(self.unit_detail_panel, 'rect') and self.unit_detail_panel.rect:
                # Check if mouse is over the unit detail panel using the actual rect
                if self.unit_detail_panel.rect.collidepoint(x, y):
                    self.unit_detail_panel.scroll(-scroll_y * 30)  # Scroll speed
                    return  # CRITICAL: Exit early to prevent other panels from handling the event
        
        # PRIORITY 2: Only check roster panes if unit detail panel didn't handle the event
        if self.player1_roster.rect.collidepoint(x, y):
            self.player1_roster.scroll(-scroll_y * 30)  # Scroll speed
        elif self.player2_roster.rect.collidepoint(x, y):
            self.player2_roster.scroll(-scroll_y * 30)

    def reset_unit_position(self, unit, original_unit_position, original_model_positions):
        if original_unit_position:
            unit.set_position(original_unit_position[0], original_unit_position[1], original_unit_position[2])
            for model, original_position in zip(unit.models, original_model_positions):
                model.set_location(*original_position)
        else:
            unit.position = None

    def get_hovered_unit(self, x, y):
        # Check if hovering over a unit in the roster panes
        hovered_unit = self.player1_roster.get_hovered_unit(x, y)
        if hovered_unit:
            return hovered_unit, self.player1_roster
        
        hovered_unit = self.player2_roster.get_hovered_unit(x, y)
        if hovered_unit:
            return hovered_unit, self.player2_roster
        
        # Check if hovering over a unit on the battlefield
        if ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH:
            battlefield_x = (x - ROSTER_PANE_WIDTH) / TILE_SIZE / self.zoom_level - self.offset_x / TILE_SIZE
            battlefield_y = y / TILE_SIZE / self.zoom_level - self.offset_y / TILE_SIZE
            
            for unit in self.game_map.units:
                if unit.is_point_inside(battlefield_x, battlefield_y):
                    # Determine which roster the unit belongs to
                    if unit in self.player1.get_army().units:
                        return unit, self.player1_roster
                    elif unit in self.player2.get_army().units:
                        return unit, self.player2_roster
        
        return None, None

    def get_unit_at_position(self, x: float, y: float) -> Optional[Unit]:
        # Convert screen coordinates to game coordinates
        game_x = (x - ROSTER_PANE_WIDTH - self.offset_x) / (TILE_SIZE * self.zoom_level)
        game_y = (y - self.offset_y) / (TILE_SIZE * self.zoom_level)
        
        print(f"Checking for unit at game coordinates: ({game_x}, {game_y})")

        for player in [self.player1, self.player2]:
            for unit in [unit for unit in player.get_army().units if unit.deployed]:
                print(f"Checking unit: {unit.name}")
                print(f"Unit position: {unit.get_position()}")
                if unit.is_point_inside(game_x, game_y):
                    return unit
        
        print("No unit found at position")
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
        self.player1_roster.draw(self.screen, self.game)
        self.player2_roster.draw(self.screen, self.game)

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
        if self.show_unit_details:
            self.unit_detail_panel.draw(self.screen, self.show_unit_details, 
                                      self.detail_panel_pos[0], self.detail_panel_pos[1])

        # Draw move paths for all units
        for unit in self.game.get_current_player().get_army().units:
            self.draw_move_path(unit)

        pygame.display.update()

    def on_key_press(self, key):
        """Handle keyboard events"""
        if key == pygame.K_ESCAPE:
            # Close unit details panel if open
            if self.show_unit_details:
                self.close_unit_details()
        elif self.show_unit_details:
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
        self.show_unit_details = None
        # Reset scroll position when closing
        self.unit_detail_panel.scroll_offset = 0


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

    for model in unit.models:
        x, y = model.get_location()[:2]
        screen_x = int((x * TILE_SIZE) * zoom_level + offset_x)
        screen_y = int((y * TILE_SIZE) * zoom_level + offset_y)
        base = model.model_base
        
        draw_base(screen, base, screen_x, screen_y, zoom_level, color)
        
        # Draw facing direction
        if base.base_type == BaseType.CIRCULAR:
            radius = int(base.get_radius() * TILE_SIZE * zoom_level)
            end_x = screen_x + int(radius * math.cos(base.facing))
            end_y = screen_y + int(radius * math.sin(base.facing))
        elif base.base_type in [BaseType.ELLIPTICAL, BaseType.HULL]:
            width = int(base.get_longest_radius() * TILE_SIZE * zoom_level)
            height = int(base.get_longest_radius() * TILE_SIZE * zoom_level)
            end_x = screen_x + int(width * math.cos(base.facing))
            end_y = screen_y + int(height * math.sin(base.facing))
        else:
            continue  # Skip if base type is unknown
        
        pygame.draw.line(screen, BLACK, (screen_x, screen_y), (end_x, end_y), 2)
    
    # Calculate and draw unit bounding box
    draw_unit_bounding_box(screen, unit, zoom_level, offset_x, offset_y, mouse_pos)

def draw_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int]) -> None:
    if base.base_type == BaseType.CIRCULAR:
        draw_circular_base(screen, base, screen_x, screen_y, zoom_level, color)
    elif base.base_type == BaseType.ELLIPTICAL:
        draw_elliptical_base(screen, base, screen_x, screen_y, zoom_level, color)
    elif base.base_type == BaseType.HULL:
        draw_hull_base(screen, base, screen_x, screen_y, zoom_level, color)

def draw_circular_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int]) -> None:
    radius = int(base.get_radius() * TILE_SIZE * zoom_level)
    pygame.draw.circle(screen, color, (screen_x, screen_y), radius)
    inner_radius = max(1, int(radius * 0.8))
    pygame.draw.circle(screen, (255, 255, 255), (screen_x, screen_y), inner_radius)

def draw_elliptical_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int]) -> None:
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
    
    # Draw the facing line on the screen after rotation
    facing_line_length = max(width, height) // 2
    end_x = screen_x + int(facing_line_length * math.cos(base.facing))
    end_y = screen_y + int(facing_line_length * math.sin(base.facing))
    pygame.draw.line(screen, (0, 0, 0), (screen_x, screen_y), (end_x, end_y), 2)

def draw_hull_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int]) -> None:
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
    
    # Draw the facing line on the screen after rotation
    facing_line_length = max(width, height) // 2
    end_x = screen_x + int(facing_line_length * math.cos(base.facing))
    end_y = screen_y + int(facing_line_length * math.sin(base.facing))
    pygame.draw.line(screen, (0, 0, 0), (screen_x, screen_y), (end_x, end_y), 2)

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
    pan_speed = int(PAN_SPEED / zoom_level)
    new_offset_x, new_offset_y = offset_x, offset_y
    if keys_pressed[pygame.K_LEFT]:
        new_offset_x += pan_speed
    if keys_pressed[pygame.K_RIGHT]:
        new_offset_x -= pan_speed
    if keys_pressed[pygame.K_UP]:
        new_offset_y += pan_speed
    if keys_pressed[pygame.K_DOWN]:
        new_offset_y -= pan_speed
    
    # Limit panning to prevent moving outside the grid
    max_offset_x = max(0, int(BATTLEFIELD_WIDTH * zoom_level) - BATTLEFIELD_WIDTH)
    max_offset_y = max(0, int(BATTLEFIELD_HEIGHT * zoom_level) - BATTLEFIELD_HEIGHT)
    new_offset_x = max(-max_offset_x, min(0, new_offset_x))
    new_offset_y = max(-max_offset_y, min(0, new_offset_y))
    
    return new_offset_x, new_offset_y
