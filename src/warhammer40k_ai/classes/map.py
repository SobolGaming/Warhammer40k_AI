from typing import List, Optional, Tuple
from enum import Enum, auto
from .unit import Unit
from .model import Model
from ..utility.calcs import get_dist, get_angle, convert_mm_to_inches
from ..utility.constants import VIEWING_ANGLE, ENGAGEMENT_RANGE

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .game import Game


class Map:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.obstacles = []
        self.objectives = []
        self.deployment_zones = {}
        self.units = []
        self.occupied_positions = set()

    def add_obstacle(self, obstacle: 'Obstacle') -> None:
        self.obstacles.append(obstacle)

    def add_objective(self, objective: 'Objective') -> None:
        self.objectives.append(objective)

    def get_objectives(self, is_secret: bool = False) -> List['Objective']:
        return [objective for objective in self.objectives if objective.category == ObjectiveCategory.SECRET]

    def get_movement_cost(self, current_tile, neighbor_tile):
        # Movement cost from current_tile to neighbor_tile
        return neighbor_tile.get_movement_cost()

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
            distance = get_dist(position[0] - target_position[0], position[1] - target_position[1])
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
        target_facing = get_angle(end[1] - start[1], end[0] - start[0])
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
        return get_dist(point2[0] - point1[0], point2[1] - point1[1])


class ObstacleType(Enum):
    CRATER_AND_RUBBLE = auto()
    DEBRIS_AND_STATUARY = auto()
    HILLS_AND_SEALED_BUILDINGS = auto()
    WOODS = auto()
    RUINS = auto()


class Obstacle:
    def __init__(self, vertices: List[Tuple[float, float]], terrain_type: ObstacleType, height: float):
        """
        vertices: List of (x, y) tuples defining the obstacle's shape.
        terrain_type: ObstacleType indicating the type (e.g., 'obstacle', 'building', 'area terrain').
        height: Numeric value indicating the obstacle's height.
        """
        self.vertices = vertices
        self.terrain_type = terrain_type
        self.height = height


class ObjectivePoint:
    def __init__(self, x: float, y: float, z: float = 0.0, control_radius: float = 3.0) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.control_radius = control_radius
        self.controlling_player = None

    def update_control(self, game_state: 'Game') -> None:
        # Determine which player controls the objective based on nearby units
        player_oc = {}
        for player in game_state.players:
            for unit in player.army.units:
                player_oc[player] = sum([model.objective_control for model in unit.models if get_dist(self.x - model.x, self.y - model.y) <= self.control_radius])
        if player_oc:
            max_oc = max(player_oc.values())
            max_players = [player for player, oc in player_oc.items() if oc == max_oc]
            self.controlling_player = max_players[0] if len(max_players) == 1 else None
        else:
            self.controlling_player = None


class ObjectiveCategory(Enum):
    PRIMARY = auto()
    SECONDARY = auto()
    SECRET = auto()


class Objective:
    def __init__(self, name: str, category: ObjectiveCategory, points: int, description: str, conditions: callable, location: Optional[Tuple[float, float]] = None) -> None:
        """
        Represents an objective in Warhammer 40,000.
        
        Parameters:
        - name (str): Name of the objective.
        - category (ObjectiveCategory): Primary, Secondary, or Secret.
        - points (int): Points rewarded upon completion.
        - description (str): Explanation of the objective's goal.
        - conditions (callable): A function or lambda to check if the objective is achieved.
        - location (tuple): (x, y) coordinates for objectives on the map (optional).
        """
        self.name = name
        self.category = category
        self.points = points
        self.description = description
        self.conditions = conditions
        self.location = location
        self.completed = False

    def check_completion(self, game_state: 'Game') -> bool:
        """Evaluate if the objective is completed based on game state."""
        self.completed = self.conditions(game_state)
        return self.completed

    def __repr__(self):
        status = "Completed" if self.completed else "Incomplete"
        return f"{self.name} ({self.category.name}): {status} - {self.points} points"


########################################################
### EXAMPLE OBJECTIVES
########################################################
# Primary Objective: Terraform (perform an action on objectives)
terraform_condition = lambda game_state: (
    game_state.unit_performed_action_on_objective("Terraform")
)

terraform_objective = Objective(
    name="Terraform Objective",
    category=ObjectiveCategory.PRIMARY,
    points=10,
    description="Perform a Terraform action on an objective to score points.",
    conditions=terraform_condition,
    location=(12, 8)  # Example objective location on the map
)

# Primary Objective: Take and Hold
take_and_hold_condition = lambda game_state: (
    game_state.player_controls_more_objectives()
)

take_and_hold = Objective(
    name="Take and Hold",
    category=ObjectiveCategory.PRIMARY,
    points=5,
    description="Control more objectives than your opponent at the end of the turn.",
    conditions=take_and_hold_condition
)

# Secondary Objective: Sabotage Terrain
sabotage_condition = lambda game_state: (
    game_state.unit_sabotaged_terrain("Enemy Terrain")
)

sabotage_objective = Objective(
    name="Sabotage Terrain",
    category=ObjectiveCategory.SECONDARY,
    points=5,
    description="Sabotage a terrain feature controlled by the opponent.",
    conditions=sabotage_condition
)

# Secondary Objective: Containment (units near battlefield edges)
containment_condition = lambda game_state: (
    game_state.has_units_near_edges()
)

containment_objective = Objective(
    name="Containment",
    category=ObjectiveCategory.SECONDARY,
    points=5,
    description="Maintain units within 9 inches of a battlefield edge.",
    conditions=containment_condition
)

# Secret Mission: Command Insertion (Warlord in enemy deployment)
command_insertion_condition = lambda game_state: (
    game_state.warlord_in_enemy_deployment_zone()
)

command_insertion = Objective(
    name="Command Insertion",
    category=ObjectiveCategory.SECRET,
    points=20,
    description="Move your Warlord into the enemy deployment zone.",
    conditions=command_insertion_condition
)

# Secret Mission: War of Attrition (weaken enemy forces)
war_of_attrition_condition = lambda game_state: (
    game_state.enemy_units_reduced_to_half_strength()
)

war_of_attrition = Objective(
    name="War of Attrition",
    category=ObjectiveCategory.SECRET,
    points=20,
    description="Reduce most of the enemy units to below half strength.",
    conditions=war_of_attrition_condition
)