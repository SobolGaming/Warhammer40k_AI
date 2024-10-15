from typing import List, Optional, Tuple
from enum import Enum, auto
from .unit import Unit
from .model import Model
from ..utility.calcs import getDist, getAngle, VIEWING_ANGLE, convert_mm_to_inches
from .game import ENGAGEMENT_RANGE


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

    def get_enemy_units(self, faction: str) -> List[Unit]:
        enemy_units = []
        for unit in self.units:
            if unit.faction != faction:
                enemy_units.append(unit)
        return enemy_units

    def is_within_engagement_range(self, position: Tuple[float, float, float], target: Unit) -> bool:
        for model in target.models:
            target_position = model.get_location()
            distance = getDist(position[0] - target_position[0], position[1] - target_position[1])
            if distance <= ENGAGEMENT_RANGE:
                return True
        return False

    def is_path_clear(self, unit: Unit, start: Tuple[float, float, float], end: Tuple[float, float, float]) -> bool:
        """
        Check if there's a clear path for a unit to move from start to end.
        
        Args:
            unit (Unit): The unit that is being moved.
            start (Tuple[float, float, float]): Starting position (x, y, z).
            end (Tuple[float, float, float]): Ending position (x, y, z).
        
        Returns:
            bool: True if the path is clear, False otherwise.
        """
        print(f"Checking path for unit {unit.name} from {start} to {end}")  # Debug print

        remaining_move = unit.movement
        
        # Check if pivot is needed
        current_facing = unit.models[0].model_base.facing
        target_facing = getAngle(end[1] - start[1], end[0] - start[0])
        pivot_needed = abs(current_facing - target_facing) > VIEWING_ANGLE
        if pivot_needed:
            pivot_cost = self.calculate_pivot_cost(unit)
            remaining_move -= pivot_cost
        
        if remaining_move < 0:
            print(f"Insufficient movement for unit {unit.name}")
            return False
        
        if not self.is_straight_path_clear(unit, start, end):
            return False
        
        distance = self.calculate_distance(start, end)
        remaining_move -= distance

        return remaining_move >= 0

    def is_straight_path_clear(self, unit: Unit, start: Tuple[float, float, float], 
                               end: Tuple[float, float, float]) -> bool:
        """
        Check if there's a clear straight path between two points for a unit.
        """
        x0, y0, _ = start
        x1, y1, _ = end
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        x, y = x0, y0
        increment = 0.2
        sx = increment if x0 < x1 else -increment
        sy = increment if y0 < y1 else -increment
        err = dx - dy

        print(f"Checking straight path from ({x0}, {y0}) to ({x1}, {y1})")  # Debug print

        while True:
            #print(f"Checking position ({x}, {y})")
            if not self.is_position_valid_for_unit(x, y, unit):
                print(f"Path blocked at ({x}, {y})")  # Debug print
                return False
            if abs(x - x1) < increment and abs(y - y1) < increment:
                print(f"Path is clear from ({x0}, {y0}) to ({x1}, {y1})")  # Debug print
                return True
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def is_position_valid_for_unit(self, x: float, y: float, moving_unit: Unit) -> bool:
        """
        Check if a position is valid for a unit to move through or end on.
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False

        for other_unit in self.units:
            if other_unit == moving_unit:
                continue
            
            if self.units_collide(moving_unit, (x, y), other_unit):
                if other_unit.faction != moving_unit.faction:
                    return False
                if (moving_unit.is_monster or moving_unit.is_vehicle) and \
                   (other_unit.is_monster or other_unit.is_vehicle):
                    return False
        
        return True

    def units_collide(self, unit1: Unit, position: Tuple[float, float], unit2: Unit) -> bool:
        """
        Check if two units' bases collide.
        """
        # Implement collision detection based on unit base sizes and shapes
        pass

    def calculate_pivot_cost(self, unit: Unit) -> float:
        """
        Calculate the pivot cost for a unit based on its characteristics.
        """
        if unit.is_aircraft:
            return 0
        if unit.is_monster or unit.is_vehicle:
            if not unit.has_circular_base or unit.base_size > convert_mm_to_inches(32 / 2):
                return 2
        if not unit.has_circular_base:
            return 1
        return 0

    def calculate_distance(self, point1: Tuple[float, float, float], 
                           point2: Tuple[float, float, float]) -> float:
        """
        Calculate the Euclidean distance between two points.
        """
        return getDist(point2[0] - point1[0], point2[1] - point1[1])


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
    def __init__(self, x: float, y: float, z: float = 0.0, control_radius: float = 3.0) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.control_radius = control_radius
        self.controlling_player = None

    def update_control(self, units: List[Unit]):
        # Determine which player controls the objective based on nearby units
        pass

