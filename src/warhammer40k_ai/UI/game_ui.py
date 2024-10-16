import pygame
import textwrap
import math
from typing import Optional, Tuple, Dict
from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.classes.player import Player
from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.map import Obstacle, ObstacleType

# Constants
TILE_SIZE = 20  # 20 pixels per inch
BATTLEFIELD_WIDTH_INCHES = 60
BATTLEFIELD_HEIGHT_INCHES = 44
BATTLEFIELD_WIDTH = BATTLEFIELD_WIDTH_INCHES * TILE_SIZE
BATTLEFIELD_HEIGHT = BATTLEFIELD_HEIGHT_INCHES * TILE_SIZE

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (50, 50, 50)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
RED = (255, 0, 0)

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

# New constants for the roster panes
ROSTER_PANE_WIDTH = 300
ROSTER_PANE_BUTTON_HEIGHT = 30
ROSTER_FONT_SIZE = 18
ROSTER_LINE_HEIGHT = 20
INFO_PANE_HEIGHT = 100

# Add these new classes
class RosterPane(pygame.sprite.Sprite):
    def __init__(self, left, bottom, width, height, roster):
        super().__init__()
        self.rect = pygame.Rect(left, bottom, width, height)
        self.roster = roster
        self.selected_unit = None
        self.background_color = pygame.Color('lightgray')
        self.font = pygame.font.Font(None, 20)
        self.button_height = 50
        self.button_width = width - 20  # 10px padding on each side
        self.buttons = []
        self.create_buttons()
        self.game_map = None  # Add this line

    def create_buttons(self):
        for i, unit in enumerate(self.roster):
            button_rect = pygame.Rect(
                self.rect.left + 10,
                self.rect.top + 10 + i * (self.button_height + 5),
                self.button_width,
                self.button_height
            )
            self.buttons.append((button_rect, unit))

    def on_mouse_press(self, x, y, button):
        if button == 1:  # Left mouse button
            for button_rect, unit in self.buttons:
                if button_rect.collidepoint(x, y):
                    self.selected_unit = unit
                    return
            self.selected_unit = None
            
            # Remove the elif block here, as it's redundant with GameView.on_mouse_press

    def draw(self, surface):
        pygame.draw.rect(surface, self.background_color, self.rect)
        
        for button_rect, unit in self.buttons:
            # Draw button background
            pygame.draw.rect(surface, pygame.Color('white'), button_rect, border_radius=5)
            
            # Draw unit name (wrapped)
            wrapped_text = textwrap.wrap(unit.name, width=20)
            for i, line in enumerate(wrapped_text):
                text = self.font.render(line, True, pygame.Color('black'))
                text_rect = text.get_rect(center=(button_rect.centerx, button_rect.top + 15 + i * 20))
                surface.blit(text, text_rect)

        # Highlight the selected unit
        if self.selected_unit:
            for button_rect, unit in self.buttons:
                if unit == self.selected_unit:
                    pygame.draw.rect(surface, pygame.Color('yellow'), button_rect, 3, border_radius=5)
                    break

    def get_hovered_unit(self, x, y):
        for button_rect, unit in self.buttons:
            if button_rect.collidepoint(x, y):
                return unit
        return None


class InfoPane(pygame.sprite.Sprite):
    def __init__(self, left: int, bottom: int, width: int, height: int, selected_unit: Unit):
        super().__init__()
        self.rect = pygame.Rect(left, bottom, width, height)
        self.font = pygame.font.Font(None, 24)
        self.background_color = (200, 200, 200)
        self.text_color = pygame.Color('black')
        self.selected_unit = selected_unit

    def draw(self, surface: pygame.Surface, game: Game):
        # Draw background
        pygame.draw.rect(surface, self.background_color, self.rect)

        # Get game information
        current_player = game.get_current_player()

        # Render text
        player_text = self.font.render(f"Player: {current_player.name}, Turn: {game.turn}, Phase: {game.phase.name}", True, self.text_color)
        text_rect = player_text.get_rect(center=(self.rect.centerx, BATTLEFIELD_HEIGHT + 10))
        surface.blit(player_text, text_rect)

        if self.selected_unit:
            unit_text = self.font.render(f"{self.selected_unit.print_unit()}", True, self.text_color)
            unit_text_rect = unit_text.get_rect(center=(self.rect.centerx, BATTLEFIELD_HEIGHT + 40))
            surface.blit(unit_text, unit_text_rect)


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
        
        # Create RosterPane instances and set their game_map
        self.player1_roster = RosterPane(0, 0, ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT, player1.get_army().units)
        self.player2_roster = RosterPane(BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH, 0, ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT, player2.get_army().units)
        self.player1_roster.game_map = game_map
        self.player2_roster.game_map = game_map

        # Create InfoPane
        self.info_pane = InfoPane(ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT, BATTLEFIELD_WIDTH, INFO_PANE_HEIGHT, self.selected_unit)

    def on_mouse_press(self, x, y, button):
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
                
                all_models = self.game_map.get_all_models()
                model_positions = self.selected_unit.calculate_model_positions(battlefield_x, battlefield_y, (BATTLEFIELD_WIDTH_INCHES, BATTLEFIELD_HEIGHT_INCHES), all_models, self.zoom_level)
                
                if model_positions:
                    for model, position in zip(self.selected_unit.models, model_positions):
                        model_x, model_y = position[:2]
                        model_z = 0
                        model.set_location(model_x, model_y, model_z, 0)
                    
                    unit_x = sum(pos[0] for pos in model_positions) / len(model_positions)
                    unit_y = sum(pos[1] for pos in model_positions) / len(model_positions)
                    self.selected_unit.set_position(unit_x, unit_y)
                    
                    if self.game_map.place_unit(self.selected_unit):
                        print(f"Unit placed with centroid at ({unit_x}, {unit_y})")
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
            for unit in player.get_army().units:
                #print(f"Checking unit: {unit.name}")
                #print(f"Unit position: {unit.get_position()}")
                #print(f"Unit coherency distance: {unit.coherency_distance}")
                if unit.is_point_inside(game_x, game_y):
                    #print(f"Unit {unit.name} found at position")
                    return unit
        
        print("No unit found at position")
        return None

    def draw(self):
        self.screen.fill(WHITE)
    
        # Draw debug rectangles for roster panes
        pygame.draw.rect(self.screen, (255, 0, 0), self.player1_roster.rect, 2)
        pygame.draw.rect(self.screen, (0, 0, 255), self.player2_roster.rect, 2)
        
        # Draw roster panes
        self.player1_roster.draw(self.screen)
        self.player2_roster.draw(self.screen)

        # Draw the battlefield
        battlefield_surface = pygame.Surface((BATTLEFIELD_WIDTH, BATTLEFIELD_HEIGHT))
        draw_battlefield(battlefield_surface, self.zoom_level, self.offset_x, self.offset_y)

        # Draw obstacles on the battlefield
        for obstacle in self.game_map.obstacles:
            draw_obstacle(battlefield_surface, obstacle, self.zoom_level, self.offset_x, self.offset_y)

        # Draw units on the battlefield
        for unit in self.game_map.units:
            place_unit(battlefield_surface, unit, self.zoom_level, self.offset_x, self.offset_y, pygame.mouse.get_pos(), self.player1, self.player2)
        
        self.screen.blit(battlefield_surface, (ROSTER_PANE_WIDTH, 0))

        # Draw InfoPane
        pygame.draw.rect(self.screen, (200, 200, 200), self.info_pane.rect)

        # Draw actual InfoPane content
        self.info_pane.draw(self.screen, self.game)

        # Display unit info for hovered unit
        mouse_pos = pygame.mouse.get_pos()
        hovered_unit, roster_pane = self.get_hovered_unit(*mouse_pos)
        if hovered_unit:
            self.display_unit_info(hovered_unit, roster_pane)

        pygame.display.update()

    def display_unit_info(self, unit, roster_pane):
        font = pygame.font.SysFont(None, 24)
        info_text = f"{unit.name} - {len(unit.models)} models"
        text_surface = font.render(info_text, True, (255, 255, 255))  # White text
        text_rect = text_surface.get_rect()
        
        # Find the button for this unit in the roster pane
        for button_rect, roster_unit in roster_pane.buttons:
            if roster_unit == unit:
                # Position the info box above the button
                x = button_rect.left
                y = button_rect.top - text_rect.height - 10
                break
        else:
            # If not found (shouldn't happen), use default position
            x, y = pygame.mouse.get_pos()

        # Adjust position to keep the box within the screen
        padding = 10
        x = max(padding, min(x, self.screen.get_width() - text_rect.width - padding))
        y = max(padding, min(y, self.screen.get_height() - text_rect.height - padding))
        
        text_rect.topleft = (x, y)
        
        # Draw a semi-transparent background
        background_rect = text_rect.inflate(20, 10)
        background = pygame.Surface(background_rect.size, pygame.SRCALPHA)
        background.fill((0, 0, 0, 180))  # Semi-transparent black
        self.screen.blit(background, background_rect.topleft)
        
        # Draw the text
        self.screen.blit(text_surface, text_rect)


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

def place_unit(screen: pygame.Surface, unit: Unit, zoom_level: float, offset_x: int, offset_y: int, mouse_pos: Tuple[int, int], player1: Player, player2: Player) -> None:
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
            radius = int(base.getRadius() * TILE_SIZE * zoom_level)
            end_x = screen_x + int(radius * math.cos(base.facing))
            end_y = screen_y + int(radius * math.sin(base.facing))
        elif base.base_type in [BaseType.ELLIPTICAL, BaseType.HULL]:
            width = int(base.longestDistance() * TILE_SIZE * zoom_level)
            height = int(base.longestDistance() * TILE_SIZE * zoom_level)
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
    radius = int(base.getRadius() * TILE_SIZE * zoom_level)
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