import pygame
import sys
import math
import random
from typing import Dict, Tuple, List
from warhammer40k_ai.gym_env.warhammer40k_env import WarhammerEnv
from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.map import Map
from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.waha_helper import WahaHelper
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.classes.player import Player, PlayerType
from warhammer40k_ai.classes.army import Army, parse_army_list
import textwrap

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

# Helper
waha_helper = WahaHelper()

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
        
        # Create RosterPane instances
        self.player1_roster = RosterPane(0, 0, ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT, player1.get_army().units)
        self.player2_roster = RosterPane(BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH, 0, ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT, player2.get_army().units)

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
            elif self.selected_unit and ROSTER_PANE_WIDTH < x < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH:
                # Calculate the battlefield coordinates
                battlefield_x = (x - ROSTER_PANE_WIDTH) / TILE_SIZE
                battlefield_y = y / TILE_SIZE
                
                # Create a new unit using the datasheet of the selected unit
                new_unit = self.selected_unit #Unit(waha_helper.get_full_datasheet_info_by_name(self.selected_unit.name))
                
                # Calculate positions for all models in the unit
                model_positions = calculate_model_positions(battlefield_x, battlefield_y, len(new_unit.models), new_unit.models[0].model_base.getRadius())
                
                if len(model_positions) > 0:
                    # Set the position of each model in the unit
                    for model, (model_x, model_y) in zip(new_unit.models, model_positions):
                        model.set_location(model_x, model_y, 0, 0)
                    
                    # Set the unit's position to the centroid of all model positions
                    unit_x = sum(pos[0] for pos in model_positions) / len(model_positions)
                    unit_y = sum(pos[1] for pos in model_positions) / len(model_positions)
                    new_unit.set_position(unit_x, unit_y)
                    
                    # Attempt to place the unit on the game map
                    if self.game_map.place_unit(new_unit):
                        print(f"Unit placed with centroid at ({unit_x}, {unit_y})")
                    else:
                        print("Failed to place unit")
                
                # Reset selection
                self.selected_unit = None
                self.player1_roster.selected_unit = None
                self.player2_roster.selected_unit = None

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

    def draw(self):
        self.screen.fill(WHITE)
        
        # Draw debug rectangles for roster panes
        pygame.draw.rect(self.screen, (255, 0, 0), self.player1_roster.rect, 2)
        pygame.draw.rect(self.screen, (0, 0, 255), self.player2_roster.rect, 2)
        
        # Draw roster panes first
        self.player1_roster.draw(self.screen)
        self.player2_roster.draw(self.screen)
        
        # Draw the battlefield
        battlefield_surface = pygame.Surface((BATTLEFIELD_WIDTH, BATTLEFIELD_HEIGHT))
        draw_battlefield(battlefield_surface, self.zoom_level, self.offset_x, self.offset_y)
        
        # Draw units on the battlefield
        for unit in self.game_map.units:
            place_unit(battlefield_surface, unit, self.zoom_level, self.offset_x, self.offset_y, pygame.mouse.get_pos(), self.player1, self.player2)
        
        self.screen.blit(battlefield_surface, (ROSTER_PANE_WIDTH, 0))

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

def initialize_game() -> Tuple[pygame.Surface, WarhammerEnv, Game, Map, float, int, int, Player, Player]:
    pygame.init()
    screen = pygame.display.set_mode((BATTLEFIELD_WIDTH + 2 * ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT))
    pygame.display.set_caption('Warhammer 40,000 Battlefield')

    env = WarhammerEnv()
    game = env.game
    game_map = Map(*game.get_battlefield_size())

    zoom_level = 1.0
    offset_x, offset_y = ROSTER_PANE_WIDTH, 0  # Adjust initial offset to account for left pane

    # Create players with armies
    player1 = Player("Player 1", PlayerType.HUMAN, parse_army_list("army_lists/warhammer_app_dump.txt", waha_helper))
    player2 = Player("Player 2", PlayerType.HUMAN, parse_army_list("army_lists/chaos_daemons_GT2023.txt", waha_helper))

    print(f"Player 1 army created with {len(player1.get_army().units)} units")
    print(f"Player 2 army created with {len(player2.get_army().units)} units")

    return screen, env, game, game_map, zoom_level, offset_x, offset_y, player1, player2

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
    pygame.draw.rect(screen, (255, 0, 0), (0, 0, visible_width, visible_height), 2)

def place_unit(screen: pygame.Surface, unit: Unit, zoom_level: float, offset_x: int, offset_y: int, mouse_pos: Tuple[int, int], player1: Player, player2: Player) -> None:
    # Determine the color based on which player the unit belongs to
    color = GREEN if unit in player1.get_army().units else RED if unit in player2.get_army().units else BLUE

    for model in unit.models:
        x, y = model.get_location()[:2]
        screen_x = int((x * TILE_SIZE) * zoom_level + offset_x)
        screen_y = int((y * TILE_SIZE) * zoom_level + offset_y)
        base = model.model_base
        
        draw_base(screen, base, screen_x, screen_y, zoom_level, color)
    
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
    ellipse_rect = pygame.Rect(screen_x - width // 2, screen_y - height // 2, width, height)
    pygame.draw.ellipse(screen, color, ellipse_rect)
    inner_width, inner_height = max(1, int(width * 0.8)), max(1, int(height * 0.8))
    inner_rect = pygame.Rect(screen_x - inner_width // 2, screen_y - inner_height // 2, inner_width, inner_height)
    pygame.draw.ellipse(screen, (255, 255, 255), inner_rect)

def draw_hull_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int]) -> None:
    width = int(base.radius[0] * 2 * TILE_SIZE * zoom_level)
    height = int(base.radius[1] * 2 * TILE_SIZE * zoom_level)
    rect = pygame.Rect(screen_x - width // 2, screen_y - height // 2, width, height)
    pygame.draw.rect(screen, color, rect)
    inner_width, inner_height = max(1, int(width * 0.8)), max(1, int(height * 0.8))
    inner_rect = pygame.Rect(screen_x - inner_width // 2, screen_y - inner_height // 2, inner_width, inner_height)
    pygame.draw.rect(screen, (255, 255, 255), inner_rect)

def draw_unit_bounding_box(screen: pygame.Surface, unit: Unit, zoom_level: float, offset_x: int, offset_y: int, mouse_pos: Tuple[int, int]) -> None:
    min_x = min(model.get_location()[0] for model in unit.models)
    max_x = max(model.get_location()[0] for model in unit.models)
    min_y = min(model.get_location()[1] for model in unit.models)
    max_y = max(model.get_location()[1] for model in unit.models)
    
    unit_rect = pygame.Rect(
        int((min_x * TILE_SIZE + offset_x) * zoom_level),
        int((min_y * TILE_SIZE + offset_y) * zoom_level),
        int((max_x - min_x) * TILE_SIZE * zoom_level),
        int((max_y - min_y) * TILE_SIZE * zoom_level)
    )
    if unit_rect.collidepoint(mouse_pos):
        pygame.draw.rect(screen, (255, 255, 0), unit_rect, 2)  # Yellow highlight

def calculate_model_positions(start_x: float, start_y: float, num_models: int, base_radius: float) -> List[Tuple[float, float]]:
    """
    Calculate model positions starting from the clicked location.
    
    Parameters:
    start_x (float): X-coordinate of the first model (clicked position)
    start_y (float): Y-coordinate of the first model (clicked position)
    num_models (int): Number of models in the unit
    base_radius (float): Radius of each model's base in inches
    
    Returns:
    List of tuple coordinates for model positions.
    """
    coherency_distance = 2.0 + 2 * base_radius  # Max distance between model edges for coherency in inches
    total_spacing = base_radius * 2 + coherency_distance

    positions = [(start_x, start_y)]  # First model at clicked position

    for _ in range(1, num_models):
        valid_position = False
        attempts = 0
        max_attempts = 100

        while not valid_position and attempts < max_attempts:
            # Generate a random position within the coherency distance of the last placed model
            last_x, last_y = positions[-1]
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(base_radius * 2, coherency_distance)
            new_x = last_x + distance * math.cos(angle)
            new_y = last_y + distance * math.sin(angle)

            # Check if the new position is valid (not colliding with other models)
            valid_position = all(
                math.hypot(new_x - x, new_y - y) >= base_radius * 2
                for x, y in positions
            )

            attempts += 1

        if valid_position:
            positions.append((new_x, new_y))
        else:
            print(f"Warning: Could not place model {len(positions) + 1} after {max_attempts} attempts")
            return []

    return positions

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

def main_game_loop() -> None:
    screen, env, game, game_map, _, _, _, player1, player2 = initialize_game()
    game_view = GameView(screen, env, game, game_map, player1, player2)
    game_state = GameState.SETUP

    print("Starting main game loop")

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                game_view.on_mouse_press(*event.pos, event.button)
            elif event.type == pygame.MOUSEWHEEL:
                game_view.zoom_level = handle_zoom(game_view.zoom_level, event)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and game_state == GameState.SETUP:
                    game_state = GameState.PLAYING
                    print("Game started!")

        keys_pressed = pygame.key.get_pressed()
        game_view.offset_x, game_view.offset_y = handle_pan(keys_pressed, game_view.offset_x, game_view.offset_y, game_view.zoom_level)

        game_view.draw()
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main_game_loop()