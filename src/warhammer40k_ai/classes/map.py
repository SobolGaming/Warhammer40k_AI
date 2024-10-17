from typing import List, Optional, Tuple
from enum import Enum, auto
from .unit import Unit
from .model import Model
from ..utility.calcs import get_dist, convert_mm_to_inches
from ..utility.constants import ENGAGEMENT_RANGE
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry    

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .game import Game


class Map:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.boundary = self.create_boundary_polygon()
        self.obstacles = []
        self.objectives = []
        self.deployment_zones = {}
        self.units = []
        self.occupied_positions = set()

    def create_boundary_polygon(self) -> Polygon:
        """
        Creates a Shapely Polygon representing the battlefield boundaries.
        """
        # Assuming the battlefield starts at (0, 0)
        vertices = [
            (0, 0),  # Bottom-left corner
            (self.width, 0),  # Bottom-right corner
            (self.width, self.height),  # Top-right corner
            (0, self.height),  # Top-left corner
            (0, 0)  # Closing the polygon
        ]
        return Polygon(vertices)

    def is_within_boundary(self, shape: BaseGeometry) -> bool:
        """
        Checks if a given Shapely geometry is fully contained within the battlefield boundary.
        """
        return self.boundary.contains(shape)

    def add_obstacles(self, obstacles: List['Obstacle']) -> None:
        self.obstacles.extend(obstacles)

    def add_obstacle(self, obstacle: 'Obstacle') -> None:
        self.obstacles.append(obstacle)

    def add_objective(self, objective: 'Objective') -> None:
        self.objectives.append(objective)

    def get_objectives(self, is_secret: bool = False) -> List['Objective']:
        return [objective for objective in self.objectives if objective.category == ObjectiveCategory.SECRET]

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


class ObstacleType(Enum):
    CRATER_AND_RUBBLE = auto()
    DEBRIS_AND_STATUARY = auto()
    HILLS_AND_SEALED_BUILDINGS = auto()
    WOODS = auto()
    RUINS = auto()


class Obstacle:
    def __init__(self, vertices: List[Tuple[float, float]], terrain_type: ObstacleType, height: float):
        self.vertices = vertices
        self.terrain_type = terrain_type
        self.height = height
        self.polygon = Polygon(vertices)
        self.center = (self.polygon.centroid.x, self.polygon.centroid.y)


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