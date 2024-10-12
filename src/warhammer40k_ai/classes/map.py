from typing import List, Optional
from enum import Enum, auto
from .unit import Unit

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

    def is_position_valid(self, x: float, y: float) -> bool:
        return (0 <= x < self.width and 0 <= y < self.height and
                (int(x), int(y)) not in self.occupied_positions)

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

    def get_all_models(self):
        all_models = []
        for unit in self.units:
            all_models.extend(unit.models)
        return all_models


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
