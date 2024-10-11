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

# Constants
TILE_SIZE = 20  # 20 pixels per inch
BATTLEFIELD_WIDTH_INCHES = 60
BATTLEFIELD_HEIGHT_INCHES = 44
BATTLEFIELD_WIDTH = BATTLEFIELD_WIDTH_INCHES * TILE_SIZE
BATTLEFIELD_HEIGHT = BATTLEFIELD_HEIGHT_INCHES * TILE_SIZE

# Colors
WHITE = (255, 255, 255)
GREY = (50, 50, 50)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)

# Helper
waha_helper = WahaHelper()

# Game states
class GameState:
    SETUP = 0
    PLAYING = 1
    GAME_OVER = 2

# Add these new constants
MIN_ZOOM = 0.5
MAX_ZOOM = 2.0
ZOOM_SPEED = 0.1

def initialize_game() -> Tuple[pygame.Surface, WarhammerEnv, Game, Map, float]:
    pygame.init()
    screen = pygame.display.set_mode((BATTLEFIELD_WIDTH, BATTLEFIELD_HEIGHT))
    pygame.display.set_caption('Warhammer 40,000 Battlefield')

    env = WarhammerEnv()
    game = env.game
    game_map = Map(BATTLEFIELD_WIDTH_INCHES, BATTLEFIELD_HEIGHT_INCHES)

    zoom_level = 1.0
    return screen, env, game, game_map, zoom_level

def draw_battlefield(screen: pygame.Surface, zoom_level: float) -> None:
    screen.fill(WHITE)
    tile_size = int(TILE_SIZE * zoom_level)
    for x in range(0, BATTLEFIELD_WIDTH, tile_size):
        for y in range(0, BATTLEFIELD_HEIGHT, tile_size):
            rect = pygame.Rect(x, y, tile_size, tile_size)
            pygame.draw.rect(screen, GREY, rect, 1)

def place_unit(screen: pygame.Surface, unit: Unit, color: Tuple[int, int, int], zoom_level: float) -> None:
    for model in unit.models:
        x, y = model.get_location()[:2]
        screen_x = int(x * TILE_SIZE * zoom_level)
        screen_y = int(y * TILE_SIZE * zoom_level)
        radius = int(model.model_base.getRadius() * TILE_SIZE * zoom_level)
        pygame.draw.circle(screen, color, (screen_x, screen_y), radius)

def handle_unit_placement(game_map: Map, army_units: Dict[str, Unit], mouse_pos: Tuple[int, int], zoom_level: float) -> bool:
    # Convert mouse position to grid position
    grid_x = mouse_pos[0] / (TILE_SIZE * zoom_level)
    grid_y = mouse_pos[1] / (TILE_SIZE * zoom_level)
    print(f"Attempting to place unit at grid position: ({grid_x}, {grid_y})")

    new_unit = Unit(waha_helper.get_full_datasheet_info_by_name("Bloodletters"))
    print(f"Created new unit with {len(new_unit.models)} models")
    new_unit.set_position(grid_x, grid_y)

    base_radius = new_unit.models[0].model_base.getRadius()
    model_positions = calculate_model_positions(grid_x, grid_y, len(new_unit.models), base_radius)
    print(f"Calculated model positions: {model_positions}")

    # Check if all model positions are within the map boundaries
    if all(0 <= pos[0] < BATTLEFIELD_WIDTH_INCHES and 0 <= pos[1] < BATTLEFIELD_HEIGHT_INCHES for pos in model_positions):
        for model, (model_x, model_y) in zip(new_unit.models, model_positions):
            model.set_location(model_x, model_y, 0, 0)
        
        print(f"Attempting to place unit on game map at position: ({grid_x}, {grid_y})")
        if game_map.place_unit(new_unit):
            unit_key = f"unit_{len(army_units)}"
            army_units[unit_key] = new_unit
            print(f"Unit placed successfully with key: {unit_key}")
            print(f"Unit location: {new_unit.position}")
            return True
        else:
            print(f"Failed to place unit on game map. Current map state:")
            print(game_map.debug_print_map())
    else:
        print("Invalid position for unit placement: Some models would be outside the map boundaries")

    return False

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
    coherency_distance = 2.0  # Max distance between models for coherency in inches
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
            break  # Stop placing models if we can't find a valid position

    return positions

def handle_zoom(zoom_level: float, mouse_pos: Tuple[int, int], button: int) -> float:
    zoom_direction = 1 if button == 4 else -1  # 4 is scroll up, 5 is scroll down
    new_zoom = zoom_level + (ZOOM_SPEED * zoom_direction)
    new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, new_zoom))
    return new_zoom

def main_game_loop() -> None:
    screen, env, game, game_map, zoom_level = initialize_game()
    army_units: Dict[str, Unit] = {}
    game_state = GameState.SETUP

    running = True
    while running:
        draw_battlefield(screen, zoom_level)

        for unit in army_units.values():
            place_unit(screen, unit, GREEN, zoom_level)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    if game_state == GameState.SETUP:
                        mouse_pos = pygame.mouse.get_pos()
                        if handle_unit_placement(game_map, army_units, mouse_pos, zoom_level):
                            print(f"Unit placed successfully. Total units: {len(army_units)}")
                        else:
                            print("Failed to place unit")
                elif event.button == 4 or event.button == 5:  # Mouse wheel
                    mouse_pos = pygame.mouse.get_pos()
                    zoom_level = handle_zoom(zoom_level, mouse_pos, event.button)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and game_state == GameState.SETUP:
                    game_state = GameState.PLAYING
                    print("Game started!")

        pygame.display.update()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main_game_loop()