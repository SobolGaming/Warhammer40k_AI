from typing import List, Optional
from enum import Enum, auto
from .unit import Unit
from .model import Model
class Map:
    def __init__(self, width: int, height: int, terrain_grid: Optional[List[List[str]]] = None):
        self.width = width
        self.height = height
        self.grid = self.initialize_grid(terrain_grid)
        self.objectives = []
        self.deployment_zones = {}
        self.units = []
        self.occupied_positions = set()

    def initialize_grid(self, terrain_grid: Optional[List[List[str]]] = None):
        # Initialize the grid with default or provided terrain
        # TODO - implement terrain grid
        return [[None for _ in range(self.width)] for _ in range(self.height)]

    def place_unit(self, unit: Unit) -> bool:
        position = unit.get_position()
        if position and self.is_position_valid(position[0], position[1]):
            self.occupied_positions.add((int(position[0]), int(position[1])))
            self.units.append(unit)
            return True
        return False

    def is_position_valid(self, x: float, y: float, moving_unit: Optional[Unit] = None) -> bool:
        int_x, int_y = int(x), int(y)
        is_valid = (0 <= int_x < self.width and 0 <= int_y < self.height)
        
        if is_valid:
            if moving_unit:
                is_valid = self.is_position_unoccupied(int_x, int_y, moving_unit)
            else:
                is_valid = (int_x, int_y) not in self.occupied_positions
        
        print(f"Checking position validity: ({x}, {y}) -> {is_valid}")  # Debug print
        return is_valid

    def is_position_unoccupied(self, x: int, y: int, moving_unit: Unit) -> bool:
        for unit in self.units:
            if unit != moving_unit:
                unit_pos = unit.get_position()
                if unit_pos and (int(unit_pos[0]), int(unit_pos[1])) == (x, y):
                    return False
        return True

    def debug_print_map(self) -> str:
        """
        Returns a string representation of the map for debugging purposes.
        """
        map_str = ""
        for y in range(self.height):
            for x in range(self.width):
                if self.grid[y][x]:
                    map_str += "X"
                else:
                    map_str += "."
            map_str += "\n"
        return map_str

    def get_all_models(self, units: Optional[List[Unit]] = None) -> List[Model] :
        if units is None:
            units = self.units
        all_models = []
        for unit in units:
            all_models.extend(unit.models)
        return all_models

    def is_path_clear(self, start: tuple, end: tuple, moving_unit: Unit) -> bool:
        """
        Check if there's a clear path between two points on the map using Bresenham's line algorithm.
        
        Args:
            start (tuple): The starting position (x, y).
            end (tuple): The ending position (x, y).
            moving_unit (Unit): The unit that is being moved.
        
        Returns:
            bool: True if the path is clear, False otherwise.
        """
        x0, y0 = int(start[0]), int(start[1])
        x1, y1 = int(end[0]), int(end[1])
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        x, y = x0, y0
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        print(f"Checking path from ({x0}, {y0}) to ({x1}, {y1})")  # Debug print

        while True:
            if not self.is_position_valid(x, y, moving_unit):
                print(f"Path blocked at ({x}, {y})")  # Debug print
                return False
            if x == x1 and y == y1:
                print(f"Path is clear from ({x0}, {y0}) to ({x1}, {y1})")  # Debug print
                return True
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

            print(f"Checking position ({x}, {y})")  # Debug print

class TerrainType(Enum):
    OPEN = auto()
    FOREST = auto()
    BUILDING = auto()
    WATER = auto()
    HILL = auto()
    OBSTACLE = auto()


class Tile:
    def __init__(self, x: int, y: int, terrain_type: TerrainType):
        self.x = x
        self.y = y
        self.terrain_type = terrain_type
        self.is_occupied = False
        self.unit = None

    def get_movement_cost(self) -> int:
        # Return movement cost based on terrain_type
        pass

    def provides_cover(self) -> bool:
        # Return True if terrain provides cover
        pass

class ObjectivePoint:
    def __init__(self, x: int, y: int, control_radius: int = 3):
        self.x = x
        self.y = y
        self.control_radius = control_radius
        self.controlling_player = None

    def update_control(self, units: List[Unit]):
        # Determine which player controls the objective based on nearby units
        pass

