from typing import List, Optional, Tuple
from enum import Enum, auto
from .unit import Unit
from .model import Model
from ..utility.calcs import get_dist, convert_mm_to_inches, can_traverse_freely
from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
from shapely.geometry import Polygon, Point, LineString
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
        """
        Check if any model in the target unit is within engagement range.
        
        Engagement Range in 10th Edition:
        - Within 1″ horizontally (measured base-to-base)  
        - Within 5″ vertically
        
        Args:
            position: The position to check from (x, y, z)
            target: The target unit to check against
            
        Returns:
            bool: True if any model in target is within engagement range
        """
        # Create a temporary model at the given position for distance calculations
        from .model import Model
        from ..utility.model_base import Base, BaseType
        
        # Create a temporary base for the position we're checking from
        temp_base = Base(BaseType.CIRCULAR, 0.1)  # Small radius for point-like calculation
        temp_base.set_position(position[0], position[1], position[2])
        
        for target_model in target.models:
            # Calculate horizontal distance (base-to-base)
            horizontal_distance = temp_base.edge_to_edge_distance(target_model.model_base)
            
            # Calculate vertical distance  
            vertical_distance = temp_base.vertical_distance(target_model.model_base)
            
            # Check if within engagement range
            if (horizontal_distance <= ENGAGEMENT_RANGE_HORIZONTAL and 
                vertical_distance <= ENGAGEMENT_RANGE_VERTICAL):
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
                    #print(f"Friendly Unit Check :: {model.parent_unit.name} checking collision with friendly units :: {other_model.parent_unit.name}")
                    if test_base.collides_with(other_model.model_base):
                        return True
        return False

    def check_collision_with_other_enemy_units(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        test_base = model.model_base
        if destination:
            test_base = model.parent_unit._create_potential_base(destination[0], destination[1], test_base.z, test_base.facing)
        
        for unit in self.get_enemy_units(model.parent_unit):
            for other_model in unit.models:
                #print(f"Enemy Unit Check :: {model.parent_unit.name} checking collision with enemy units :: {other_model.parent_unit.name}")
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

    def get_distance_between_units(self, unit1: Unit, unit2: Unit) -> float:
        """Calculate the shortest distance between two units.
        
        Args:
            unit1 (Unit): First unit
            unit2 (Unit): Second unit
            
        Returns:
            float: The shortest distance between any models in the two units
        """
        shortest_distance = float('inf')
        
        # Check distance between each model pair
        for model1 in unit1.models:
            for model2 in unit2.models:
                distance = model1.edge_to_edge_distance(model2)
                shortest_distance = min(shortest_distance, distance)
                
        return shortest_distance

    def is_path_blocked(self, unit: Unit, target: Unit) -> bool:
        """Check if there's a clear path between two units considering terrain and obstacles.
        
        Args:
            unit (Unit): The unit checking the path
            target (Unit): The target unit
            
        Returns:
            bool: True if path is blocked, False if clear
        """
        # Get the positions of both units
        unit_pos = unit.get_position()
        target_pos = target.get_position()
        
        # Create a line representing the path
        path = LineString([(unit_pos[0], unit_pos[1]), (target_pos[0], target_pos[1])])
        
        # Check for intersections with obstacles
        for obstacle in self.obstacles:
            if path.intersects(obstacle.polygon):
                if not can_traverse_freely(unit, obstacle):
                    return True  # Path is blocked
        
        return False  # Path is clear



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
        # Determine which player controls the objective based on base overlap
        player_oc = {player: 0 for player in game_state.players}  # Initialize all players with 0 OC
        
        from shapely.geometry import Point
        # Create objective area as a circle
        objective_area = Point(self.x, self.y).buffer(self.control_radius)
        
        for player in game_state.players:
            if not player.army:
                continue
            for unit in player.army.units:
                if not unit.deployed or not unit.is_alive():
                    continue
                for model in unit.models:
                    if not model.is_alive:
                        continue
                    
                    # Get model's base shape and check for overlap with objective area
                    try:
                        model_base_shape = model.model_base.get_base_shape()
                        if model_base_shape.intersects(objective_area):
                            player_oc[player] += model.objective_control
                            print(f"🎯 {model.name} (OC: {model.objective_control}) overlaps objective at ({self.x:.1f}, {self.y:.1f})")
                    except Exception as e:
                        # Fallback to distance check if base shape fails
                        distance = get_dist(self.x - model.model_base.x, self.y - model.model_base.y)
                        model_base_radius = getattr(model.model_base, 'get_radius', lambda: 1.0)()
                        if distance <= (self.control_radius + model_base_radius):
                            player_oc[player] += model.objective_control
                            print(f"🎯 {model.name} (OC: {model.objective_control}) near objective (fallback calculation)")

        # Determine controlling player based on OC values
        if any(oc > 0 for oc in player_oc.values()):
            max_oc = max(player_oc.values())
            max_players = [player for player, oc in player_oc.items() if oc == max_oc]
            if len(max_players) == 1:
                self.controlling_player = max_players[0]
            else:
                # Tie - no one controls the objective
                self.controlling_player = None
        else:
            self.controlling_player = None
        
        # Debug output
        oc_summary = {player.name: oc for player, oc in player_oc.items() if oc > 0}
        if oc_summary:
            print(f"ObjectivePoint ({self.x:.1f}, {self.y:.1f}) OC values: {oc_summary} -> controlled by {self.controlling_player.name if self.controlling_player else 'None'}")
        else:
            print(f"ObjectivePoint ({self.x:.1f}, {self.y:.1f}) controlled by None (no models in range)")


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
