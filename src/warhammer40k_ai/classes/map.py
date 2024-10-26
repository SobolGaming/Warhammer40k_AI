from typing import List, Optional, Tuple
from enum import Enum, auto
from .unit import Unit
from .model import Model
from ..utility.calcs import get_dist, convert_mm_to_inches
from ..utility.constants import ENGAGEMENT_RANGE
from shapely.geometry import Polygon, Point   
from shapely.affinity import scale, translate

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
        ]
        return Polygon(vertices)

    def add_obstacle(self, obstacle: 'Obstacle') -> None:
        self.obstacles.append(obstacle)

    def add_obstacles(self, obstacles: List['Obstacle']) -> None:
        self.obstacles.extend(obstacles)

    def add_objective(self, objective: 'Objective') -> None:
        self.objectives.append(objective)

    def add_objectives(self, objectives: List['Objective']) -> None:
        self.objectives.extend(objectives)

    def get_objectives(self, is_secret: bool = False) -> List['Objective']:
        return [objective for objective in self.objectives if objective.category == ObjectiveCategory.SECRET]

    def place_unit(self, unit: Unit) -> bool:
        for model in unit.models:
            if not self.is_within_boundary(model):
                return False
            if self.check_collision_with_obstacles(model):
                return False
            if self.check_collision_with_other_friendly_units(model):
                return False
            if self.check_collision_with_other_enemy_units(model):
                return False
        self.units.append(unit)
        return True

    def get_all_models(self, units: Optional[List[Unit]] = None) -> List[Model] :
        if units is None:
            units = self.units
        all_models = []
        for unit in units:
            all_models.extend(unit.models)
        return all_models

    def get_enemy_units(self, unit: Unit) -> List[Unit]:
        enemy_units = []
        for test_unit in self.units:
            if unit.get_parent_army() != test_unit.get_parent_army():
                enemy_units.append(test_unit)
        return enemy_units

    def get_enemy_models(self, unit: Unit) -> List[Model]:
        enemy_models = []
        for test_unit in self.get_enemy_units(unit):
            enemy_models.extend(test_unit.models)
        return enemy_models

    def get_friendly_units(self, unit: Unit) -> List[Unit]:
        friendly_units = []
        for test_unit in self.units:
            if unit.get_parent_army() == test_unit.get_parent_army():
                friendly_units.append(test_unit)
        return friendly_units

    def get_friendly_models(self, unit: Unit) -> List[Model]:
        friendly_models = []
        for test_unit in self.get_friendly_units(unit):
            friendly_models.extend(test_unit.models)
        return friendly_models

    def is_within_boundary(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        """
        Checks if a given Shapely geometry is fully contained within the battlefield boundary.
        """
        test_shape = model.model_base.get_base_shape()
        if destination:
            test_shape = translate(test_shape, destination[0] - model.model_base.x, destination[1] - model.model_base.y)
        return self.boundary.contains(test_shape)

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

    def check_collision_with_obstacles(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        shape = model.model_base.get_base_shape()
        if destination:
            shape = translate(shape, destination[0] - model.model_base.x, destination[1] - model.model_base.y)
        for obstacle in self.obstacles:
            #print(f"{model.parent_unit.name} checking collision with obstacles :: {obstacle.polygon}")
            if shape.intersects(obstacle.polygon):
                return True
        return False

    def check_collision_with_other_friendly_units(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        test_base = model.model_base
        if destination:
            test_base = model.parent_unit._create_potential_base(destination[0], destination[1], test_base.z, test_base.facing)
        for unit in self.get_friendly_units(model.parent_unit):
            if unit != model.parent_unit:  #  inter-unit collisions check done elsewhere
                for other_model in unit.models:
                    print(f"Friendly Unit Check :: {model.parent_unit.name} checking collision with friendly units :: {other_model.parent_unit.name}")
                    if test_base.collides_with(other_model.model_base):
                        return True
        return False

    def check_collision_with_other_enemy_units(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        test_base = model.model_base
        if destination:
            test_base = model.parent_unit._create_potential_base(destination[0], destination[1], test_base.z, test_base.facing)
        
        for unit in self.get_enemy_units(model.parent_unit):
            for other_model in unit.models:
                print(f"Enemy Unit Check :: {model.parent_unit.name} checking collision with enemy units :: {other_model.parent_unit.name}")
                if test_base.collides_with(other_model.model_base):
                    return True
        return False

    def get_height_at_point(self, x: float, y: float) -> float:
        """
        Check if a given X,Y coordinate has an obstacle and return its height (Z coordinate).
        If multiple obstacles overlap, return the maximum height.

        Args:
            x (float): X coordinate to check
            y (float): Y coordinate to check

        Returns:
            float: Maximum height of obstacles at the given point, or 0 if no obstacles are present
        """
        point = Point(x, y)
        max_height = 0.0

        for obstacle in self.obstacles:
            if obstacle.polygon.contains(point):
                max_height = max(max_height, obstacle.height)

        return max_height



class ObstacleType(Enum):
    CRATER_AND_RUBBLE = auto()
    DEBRIS_AND_STATUARY = auto()
    HILLS_AND_SEALED_BUILDINGS = auto()
    WOODS = auto()
    RUINS = auto()


class Obstacle:
    def __init__(self, vertices: List[Tuple[float, float]], terrain_type: ObstacleType, height: float) -> None:
        self.vertices = vertices
        self.terrain_type = terrain_type
        self.height = height
        if len(vertices) == 2:
            self.polygon = Point(vertices[0]).buffer(1, resolution=64)
            self.polygon = scale(self.polygon, vertices[1][0], vertices[1][1])
        else:
            self.polygon = Polygon(vertices)
        self.center = (self.polygon.centroid.x, self.polygon.centroid.y)
        self.color = 'red'


class ObjectivePoint:
    def __init__(self, x: float, y: float, z: float = 0.0, control_radius: float = 3.0) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.control_radius = control_radius
        self.controlling_player = None

    def update_control(self, game_state: 'Game') -> None:
        # Determine which player controls the objective based on nearby units
        player_oc = {player: 0 for player in game_state.players}  # Initialize all players with 0 OC
        for player in game_state.players:
            for unit in player.army.units:
                for model in unit.models:
                    if get_dist(self.x - model.model_base.x, self.y - model.model_base.y) <= self.control_radius:
                        player_oc[player] += model.objective_control

        if any(oc > 0 for oc in player_oc.values()):
            max_oc = max(player_oc.values())
            max_players = [player for player, oc in player_oc.items() if oc == max_oc]
            self.controlling_player = max_players[0] if len(max_players) == 1 else None
        else:
            self.controlling_player = None
        
        print(f"ObjectivePoint {self.x}, {self.y} controlled by {self.controlling_player}")
        #print(f"Player OC values: {player_oc}")  # Debug print


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
