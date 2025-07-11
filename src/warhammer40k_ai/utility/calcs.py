from math import sqrt, atan2, pi, cos, sin
from typing import Tuple, List, Optional, Union
import heapq
import numpy as np
from ..utility.constants import MM_TO_INCHES, FREELY_CLIMBABLE_RANGE, ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
from shapely.geometry import LineString, Point, Polygon
from shapely.affinity import translate
from shapely.ops import unary_union
from shapely import STRtree

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..classes.map import Obstacle, ObstacleType
    from ..classes.unit import Unit, MovementAction
    from ..classes.model import Model
    from ..classes.map import Map

import logging
logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

# Convert mm (as in base size of models) to inches
def convert_mm_to_inches(value: float) -> float:
    return round(value / MM_TO_INCHES, 4)

# Determine the distance of a 3D position delta
def get_dist(x_delta: float, y_delta: float, z_delta: float = 0) -> float:
    return sqrt(x_delta**2 + y_delta**2 + z_delta**2)

# Determine the angle between to X,Y points
def get_angle(x_delta: float, y_delta: float) -> float:
    return atan2(x_delta, y_delta)

def angle_difference(angle1: float, angle2: float) -> float:
    """
    Calculate the smallest difference between two angles in radians.
    The result is in the range [-π, π].
    """
    diff = (angle2 - angle1 + pi) % (2 * pi) - pi
    return diff

def can_traverse_freely(unit: 'Unit', obstacle: 'Obstacle') -> bool:
    """Check if a unit can freely traverse over an obstacle.
    
    This function combines both general movement rules and specific terrain type rules.
    """
    # Flying units can traverse any obstacle
    if unit.is_flying:
        return True

    # Check height-based traversal
    if obstacle.height <= FREELY_CLIMBABLE_RANGE:
        return True

    # Import at runtime to avoid circular import
    from ..classes.map import ObstacleType
    
    # Check terrain type specific rules
    terrain = obstacle.terrain_type
    if terrain in [ObstacleType.CRATER_AND_RUBBLE, ObstacleType.DEBRIS_AND_STATUARY]:
        return True  # These are always traversable
    elif terrain == ObstacleType.HILLS_AND_SEALED_BUILDINGS:
        return False  # Cannot traverse through buildings
    elif terrain == ObstacleType.WOODS:
        return True  # Can traverse through woods
    elif terrain == ObstacleType.RUINS:
        # Special characters and infantry/beasts can traverse ruins
        return (unit.is_infantry or unit.is_beast or 
                unit.is_belisarius_cawl or unit.is_imperium_primarch)
    
    # Default to not traversable for unknown terrain types
    return False

def get_pivot_cost(unit: 'Unit') -> float:
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

def get_movement_cost(model: 'Model', point_a: Tuple[float, float], point_b: Tuple[float, float], obstacles: List['Obstacle']) -> float:
    dx = point_b[0] - point_a[0]
    dy = point_b[1] - point_a[1]
    dz = 0  # Initialize vertical distance

    # Create a line representing the movement path
    #print(f"A: {point_a}, B: {point_b}")
    movement_line = LineString([point_a, point_b])

    # Find obstacles that intersect the movement path
    intersecting_obstacles = []
    for obstacle in obstacles:
        if movement_line.intersects(obstacle.polygon):
            intersecting_obstacles.append(obstacle)

    # Determine the maximum obstacle height along the path
    max_obstacle_height = 0
    for obstacle in intersecting_obstacles:
        if not can_traverse_freely(model.parent_unit, obstacle):
            if obstacle.height > max_obstacle_height:
                max_obstacle_height = obstacle.height

    # Set vertical distance based on the highest obstacle if it's greater than the freely climbable range
    dz = max_obstacle_height if max_obstacle_height > FREELY_CLIMBABLE_RANGE else 0

    # For units with 'Fly', they pay vertical movement cost but can traverse over obstacles
    if model.parent_unit.is_flying:
        pass  # They can fly over obstacles but must pay vertical cost
    else:
        # For non-flying units, check if they can climb over the obstacle
        if dz > model.movement:
            return float('inf')  # Cannot traverse over the obstacle

    # Calculate total movement cost including vertical distance
    total_distance = get_dist(dx, dy, dz)
    return total_distance

def heuristic(a, b):
    """Calculate the heuristic (estimated distance) between two points."""
    return get_dist(a[0] - b[0], a[1] - b[1], a[2] - b[2])

def distance_to_nearest_obstacle(point, obstacles):
    if not obstacles:
        return float('inf')  # Return infinity if there are no obstacles
    return min(obstacle.polygon.distance(Point(point)) for obstacle in obstacles)

def adaptive_step_size(point, obstacles, target, min_step=0.1, max_step=6.0, safety_factor=0.5):
    dist = distance_to_nearest_obstacle(point, obstacles)
    return max(min_step, min(max_step, dist * safety_factor))

def move_object(obj, obstacles, dx, dy, step):
    """Moves an object by (dx, dy), attempting to path around obstacles."""
    new_obj = translate(obj, dx, dy)

    # Check for collisions
    for obstacle in obstacles:
        if new_obj.intersects(obstacle.polygon):
            # Attempt to path around the obstacle
            alternative_directions = [
                (cos(angle) * dx - sin(angle) * dy, sin(angle) * dx + cos(angle) * dy)
                for angle in [
                    pi/6,  # 30 degrees clockwise
                    -pi/6,  # 30 degrees counterclockwise
                    pi/3,  # 60 degrees clockwise
                    -pi/3,  # 60 degrees counterclockwise
                    pi/2,  # 90 degrees clockwise
                    -pi/2,  # 90 degrees counterclockwise
                    2*pi/3,  # 120 degrees clockwise
                    -2*pi/3,  # 120 degrees counterclockwise
                    pi,  # 180 degrees (reverse)
                ]
            ]
            
            for alt_dx, alt_dy in alternative_directions:
                alt_obj = translate(obj, alt_dx, alt_dy)
                if not any(alt_obj.intersects(obs.polygon) for obs in obstacles):
                    logger.debug(f"Collision avoided at step {step}")
                    return alt_obj, False  # Return the alternative movement

            # If no alternative direction works, stay in place
            logger.debug(f"Collision at step {step}, no alternative path found")
            return obj, True  # Return the original object and collision flag

    return new_obj, False

def get_neighbors(current, obstacles, ellipse, goal):
    """Get valid neighboring points with adaptive step size and direct path to goal."""
    x, y, z = current
    step_size = adaptive_step_size(current, obstacles, ellipse)
    
    # Add direct path to goal
    goal_direction = (goal[0] - x, goal[1] - y)
    goal_distance = get_dist(goal_direction[0], goal_direction[1])
    if goal_distance <= step_size:
        neighbors = [goal]
    else:
        goal_step = (goal_direction[0] / goal_distance * step_size,
                     goal_direction[1] / goal_distance * step_size)
        neighbors = [
            (x + goal_step[0], y + goal_step[1]),
            (x + step_size, y),
            (x - step_size, y),
            (x, y + step_size),
            (x, y - step_size),
            (x + step_size * 0.707, y + step_size * 0.707),
            (x - step_size * 0.707, y - step_size * 0.707),
            (x + step_size * 0.707, y - step_size * 0.707),
            (x - step_size * 0.707, y + step_size * 0.707),
        ]
    
    valid_neighbors = []
    for n in neighbors:
        moved_ellipse = translate(ellipse, n[0] - ellipse.centroid.x, n[1] - ellipse.centroid.y)
        if not any(moved_ellipse.intersects(obs.polygon) for obs in obstacles):
            valid_neighbors.append((n[0], n[1], z))
    return valid_neighbors

def check_engagement_range_violation(model: 'Model', position: Tuple[float, float, float], game_map: 'Map', 
                                   movement_action: 'MovementAction' = None, is_ending_position: bool = False) -> bool:
    """
    Check if a position would put the model within engagement range of any enemy unit.
    
    Args:
        model: The model to check
        position: The position to test (x, y, z)
        game_map: The game map containing enemy units
        movement_action: MovementAction enum value (MOVE, ADVANCE, FALL_BACK)
        is_ending_position: Whether this is the final destination
        
    Returns:
        bool: True if position violates engagement range rules for the given movement action
    """
    # Import here to avoid circular imports
    from ..classes.unit import MovementAction
    
    # Create a temporary base at the test position
    temp_base = model.model_base.__class__(model.model_base.base_type, model.model_base.radius)
    temp_base.set_position(position[0], position[1], position[2])
    temp_base.set_facing(model.model_base.facing)
    
    # Check against all enemy units
    enemy_units = game_map.get_enemy_units(model.parent_unit)
    for enemy_unit in enemy_units:
        if not enemy_unit.is_alive() or not enemy_unit.deployed:
            continue
            
        for enemy_model in enemy_unit.models:
            if not enemy_model.is_alive:
                continue
                
            # Calculate horizontal and vertical distances
            horizontal_distance = temp_base.edge_to_edge_distance(enemy_model.model_base)
            vertical_distance = temp_base.vertical_distance(enemy_model.model_base)
            
            # Check if within engagement range
            if (horizontal_distance <= ENGAGEMENT_RANGE_HORIZONTAL and 
                vertical_distance <= ENGAGEMENT_RANGE_VERTICAL):
                
                # Fall Back rules: Can move within engagement range but cannot end within it
                if movement_action == MovementAction.FALL_BACK:
                    return is_ending_position  # Only violation if ending position
                
                # Normal/Advance rules: Cannot move within engagement range at all
                return True
                
    return False

def check_enemy_model_collision(model: 'Model', start_pos: Tuple[float, float, float], 
                               end_pos: Tuple[float, float, float], game_map: 'Map', 
                               movement_action: 'MovementAction' = None) -> Tuple[bool, List['Model']]:
    """
    Check if the movement path would collide with enemy models.
    
    Args:
        model: The model moving
        start_pos: Starting position (x, y, z)
        end_pos: Ending position (x, y, z) 
        game_map: The game map containing enemy units
        movement_action: MovementAction enum value (MOVE, ADVANCE, FALL_BACK)
        
    Returns:
        Tuple[bool, List[Model]]: (collision_detected, list_of_enemy_models_moved_over)
    """
    # Import here to avoid circular imports
    from ..classes.unit import MovementAction
    from shapely.geometry import LineString
    
    # Create movement line
    movement_line = LineString([(start_pos[0], start_pos[1]), (end_pos[0], end_pos[1])])
    
    enemy_units = game_map.get_enemy_units(model.parent_unit)
    enemy_models_moved_over = []
    
    for enemy_unit in enemy_units:
        if not enemy_unit.is_alive() or not enemy_unit.deployed:
            continue
            
        for enemy_model in enemy_unit.models:
            if not enemy_model.is_alive:
                continue
                
            # Check if model has FLY keyword - can move over enemy models freely
            if model.parent_unit.is_flying:
                continue
                
            # Get enemy model's base shape
            enemy_base_shape = enemy_model.model_base.get_base_shape()
            
            # Check if movement line intersects with enemy base
            if movement_line.intersects(enemy_base_shape):
                # For Fall Back moves, allow moving over enemies but track them
                if movement_action == MovementAction.FALL_BACK:
                    enemy_models_moved_over.append(enemy_model)
                    continue
                else:
                    # Normal/Advance moves: collision blocks movement
                    return True, []
            
            # Also check if our model's base would intersect at any point along the path
            # Sample points along the path for more thorough checking
            num_samples = max(10, int(sqrt((end_pos[0] - start_pos[0])**2 + (end_pos[1] - start_pos[1])**2) * 10))
            for i in range(num_samples + 1):
                t = i / num_samples
                sample_x = start_pos[0] + t * (end_pos[0] - start_pos[0])
                sample_y = start_pos[1] + t * (end_pos[1] - start_pos[1])
                sample_z = start_pos[2] + t * (end_pos[2] - start_pos[2])
                
                # Create temporary base at sample position
                temp_base = model.model_base.__class__(model.model_base.base_type, model.model_base.radius)
                temp_base.set_position(sample_x, sample_y, sample_z)
                temp_base.set_facing(model.model_base.facing)
                
                # Check collision with enemy model
                if temp_base.collides_with(enemy_model.model_base):
                    if movement_action == MovementAction.FALL_BACK:
                        # Track enemy models being moved over
                        if enemy_model not in enemy_models_moved_over:
                            enemy_models_moved_over.append(enemy_model)
                    else:
                        # Normal/Advance moves: collision blocks movement
                        return True, []
    
    # Return collision status and list of enemy models moved over
    return len(enemy_models_moved_over) > 0 and movement_action != MovementAction.FALL_BACK, enemy_models_moved_over

def check_vehicle_monster_restrictions(model: 'Model', start_pos: Tuple[float, float, float], 
                                     end_pos: Tuple[float, float, float], game_map: 'Map') -> bool:
    """
    Check vehicle/monster movement restrictions against other vehicles/monsters.
    
    Args:
        model: The model moving
        start_pos: Starting position (x, y, z)
        end_pos: Ending position (x, y, z)
        game_map: The game map containing other units
        
    Returns:
        bool: True if movement violates vehicle/monster restrictions
    """
    # Only apply to vehicles and monsters
    if not (model.parent_unit.is_vehicle or model.parent_unit.is_monster):
        return False
        
    # Check against both friendly and enemy vehicles/monsters
    all_units = game_map.get_friendly_units(model.parent_unit) + game_map.get_enemy_units(model.parent_unit)
    
    for unit in all_units:
        if unit == model.parent_unit or not unit.is_alive() or not unit.deployed:
            continue
            
        # Only check against other vehicles/monsters
        if not (unit.is_vehicle or unit.is_monster):
            continue
            
        for other_model in unit.models:
            if not other_model.is_alive:
                continue
                
            # Check if path would intersect with this vehicle/monster
            if check_model_path_intersection(model, start_pos, end_pos, other_model):
                return True
                
    return False

def check_model_path_intersection(moving_model: 'Model', start_pos: Tuple[float, float, float], 
                                 end_pos: Tuple[float, float, float], stationary_model: 'Model') -> bool:
    """
    Check if a model's movement path would intersect with another model.
    
    Args:
        moving_model: The model that is moving
        start_pos: Starting position
        end_pos: Ending position
        stationary_model: The model to check intersection against
        
    Returns:
        bool: True if paths intersect
    """
    # Sample points along the movement path
    num_samples = max(20, int(sqrt((end_pos[0] - start_pos[0])**2 + (end_pos[1] - start_pos[1])**2) * 15))
    
    for i in range(num_samples + 1):
        t = i / num_samples
        sample_x = start_pos[0] + t * (end_pos[0] - start_pos[0])
        sample_y = start_pos[1] + t * (end_pos[1] - start_pos[1])
        sample_z = start_pos[2] + t * (end_pos[2] - start_pos[2])
        
        # Create temporary base at sample position
        temp_base = moving_model.model_base.__class__(moving_model.model_base.base_type, moving_model.model_base.radius)
        temp_base.set_position(sample_x, sample_y, sample_z)
        temp_base.set_facing(moving_model.model_base.facing)
        
        # Check collision
        if temp_base.collides_with(stationary_model.model_base):
            return True
            
    return False

def check_friendly_ending_collision(model: 'Model', end_pos: Tuple[float, float, float], game_map: 'Map') -> bool:
    """
    Check if ending position would collide with friendly models.
    
    Args:
        model: The model to check
        end_pos: The ending position (x, y, z)
        game_map: The game map
        
    Returns:
        bool: True if ending position collides with friendly models
    """
    # Create temporary base at ending position
    temp_base = model.model_base.__class__(model.model_base.base_type, model.model_base.radius)
    temp_base.set_position(end_pos[0], end_pos[1], end_pos[2])
    temp_base.set_facing(model.model_base.facing)
    
    # Check against friendly units (excluding own unit)
    friendly_units = game_map.get_friendly_units(model.parent_unit)
    for friendly_unit in friendly_units:
        if friendly_unit == model.parent_unit or not friendly_unit.is_alive() or not friendly_unit.deployed:
            continue
            
        for friendly_model in friendly_unit.models:
            if not friendly_model.is_alive:
                continue
                
            if temp_base.collides_with(friendly_model.model_base):
                return True
                
    return False

def is_position_valid_for_movement(model: 'Model', position: Tuple[float, float, float], 
                                  start_pos: Tuple[float, float, float], game_map: 'Map', 
                                  is_ending_position: bool = False, movement_action: 'MovementAction' = None) -> Tuple[bool, List['Model']]:
    """
    Comprehensive validation of a position for movement according to Warhammer 40k rules.
    
    Args:
        model: The model to check
        position: The position to validate (x, y, z)
        start_pos: The starting position for path checking
        game_map: The game map
        is_ending_position: Whether this is the final destination
        movement_action: MovementAction enum value (MOVE, ADVANCE, FALL_BACK)
        
    Returns:
        Tuple[bool, List[Model]]: (is_valid, list_of_enemy_models_moved_over)
    """
    # 1. Check battlefield boundaries
    if not game_map.is_within_boundary(model, position[:2]):
        return False, []
        
    # 2. Check obstacle collisions
    if game_map.check_collision_with_obstacles(model, position[:2]):
        return False, []
        
    # 3. Check engagement range violations (modified for Fall Back rules)
    if check_engagement_range_violation(model, position, game_map, movement_action, is_ending_position):
        return False, []
        
    # 4. Check enemy model base collisions along path (modified for Fall Back rules)
    collision_detected, enemy_models_moved_over = check_enemy_model_collision(model, start_pos, position, game_map, movement_action)
    if collision_detected:
        return False, []
        
    # 5. Check vehicle/monster restrictions
    if check_vehicle_monster_restrictions(model, start_pos, position, game_map):
        return False, []
        
    # 6. Check friendly model collisions (only for ending position)
    if is_ending_position and check_friendly_ending_collision(model, position, game_map):
        return False, []
    
    # 7. Special FLY keyword rules
    if model.parent_unit.is_flying and is_ending_position:
        # FLY models cannot end on top of any other model (friendly or enemy)
        if check_model_overlap_at_position(model, position, game_map):
            return False, []
        
    return True, enemy_models_moved_over

def check_model_overlap_at_position(model: 'Model', position: Tuple[float, float, float], game_map: 'Map') -> bool:
    """
    Check if a model would overlap with any other model (friendly or enemy) at the given position.
    Used for FLY keyword validation.
    """
    # Create temporary base at test position
    temp_base = model.model_base.__class__(model.model_base.base_type, model.model_base.radius)
    temp_base.set_position(position[0], position[1], position[2])
    temp_base.set_facing(model.model_base.facing)
    
    # Check against all other units on the map
    for unit in game_map.units:
        if not unit.is_alive() or not unit.deployed or unit == model.parent_unit:
            continue
            
        for other_model in unit.models:
            if not other_model.is_alive:
                continue
                
            # Check if bases would overlap
            if temp_base.collides_with(other_model.model_base):
                return True
                
    return False

def get_enhanced_neighbors(current: Tuple[float, float, float], model: 'Model', obstacles: List['Obstacle'], 
                          game_map: 'Map', goal: Tuple[float, float, float], 
                          movement_action: 'MovementAction' = None) -> List[Tuple[Tuple[float, float, float], List['Model']]]:
    """
    Get valid neighboring points with comprehensive Warhammer 40k movement validation.
    
    Args:
        current: Current position (x, y, z)
        model: The model moving
        obstacles: List of terrain obstacles
        game_map: The game map
        goal: The target destination
        movement_action: MovementAction enum value (MOVE, ADVANCE, FALL_BACK)
        
    Returns:
        List of tuples containing (valid_neighboring_position, enemy_models_moved_over)
    """
    x, y, z = current
    step_size = adaptive_step_size(current, obstacles, goal)
    
    # Generate potential neighbors with adaptive step size
    potential_neighbors = []
    
    # Add direct path to goal if close enough
    goal_direction = (goal[0] - x, goal[1] - y)
    goal_distance = sqrt(goal_direction[0]**2 + goal_direction[1]**2)
    
    if goal_distance <= step_size:
        potential_neighbors.append(goal)
    else:
        # Normalized direction to goal
        goal_step = (goal_direction[0] / goal_distance * step_size,
                     goal_direction[1] / goal_distance * step_size)
        potential_neighbors.append((x + goal_step[0], y + goal_step[1], z))
    
    # Add standard directional neighbors
    directions = [
        (step_size, 0),           # East
        (-step_size, 0),          # West  
        (0, step_size),           # North
        (0, -step_size),          # South
        (step_size * 0.707, step_size * 0.707),    # Northeast
        (-step_size * 0.707, -step_size * 0.707),  # Southwest
        (step_size * 0.707, -step_size * 0.707),   # Southeast
        (-step_size * 0.707, step_size * 0.707),   # Northwest
    ]
    
    for dx, dy in directions:
        neighbor_pos = (x + dx, y + dy, z)
        potential_neighbors.append(neighbor_pos)
    
    # Validate each neighbor according to Warhammer 40k rules
    valid_neighbors = []
    for neighbor in potential_neighbors:
        is_valid, enemy_models_moved_over = is_position_valid_for_movement(
            model, neighbor, current, game_map, 
            is_ending_position=(neighbor == goal), movement_action=movement_action
        )
        if is_valid:
            valid_neighbors.append((neighbor, enemy_models_moved_over))
    
    return valid_neighbors

def a_star_enhanced(model: 'Model', game_map: 'Map', target: Tuple[float, float, float], 
                   max_iterations: int = 15000, movement_action: 'MovementAction' = None) -> Optional[Tuple[List[Tuple[float, float, float]], List['Model']]]:
    """
    Enhanced A* pathfinding algorithm that accounts for all Warhammer 40k movement rules.
    
    This implementation handles:
    - Normal/Advance movement: Cannot move within engagement range or through enemy models
    - Fall Back movement: Can move within engagement range and over enemy models, but cannot end within engagement range
    - FLY keyword: Can move over models but cannot end on them or within engagement range
    
    Args:
        model: The model to pathfind for
        game_map: The game map containing all units and obstacles
        target: Target position (x, y, z, facing)
        max_iterations: Maximum iterations to prevent infinite loops
        movement_action: MovementAction enum value (MOVE, ADVANCE, FALL_BACK)
        
    Returns:
        Tuple containing (path, enemy_models_moved_over) or None if no path exists
    """
    start = (model.model_base.x, model.model_base.y, model.model_base.z)
    goal = target[:3]
    
    # Early validation - check if goal is reachable at all
    goal_valid, _ = is_position_valid_for_movement(model, goal, start, game_map, 
                                                  is_ending_position=True, movement_action=movement_action)
    if not goal_valid:
        logger.debug(f"Goal position {goal} is invalid for {model.name} (movement action: {movement_action})")
        return None
    
    # Initialize A* data structures
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}
    closed_set = set()
    
    # Track enemy models moved over for each path
    path_enemy_models = {start: []}
    
    iterations = 0
    logger.debug(f"Starting enhanced A* pathfinding for {model.name} from {start} to {goal} (movement action: {movement_action})")
    
    while open_set and iterations < max_iterations:
        current = heapq.heappop(open_set)[1]
        
        # Skip if already processed
        if current in closed_set:
            continue
            
        closed_set.add(current)
        
        # Check if we've reached the goal
        if heuristic(current, goal) < 0.1:  # Close enough to goal
            # Reconstruct path and enemy models moved over
            path = []
            all_enemy_models_moved_over = []
            
            # Trace back through the path
            path_node = current
            while path_node in came_from:
                path.append(path_node)
                all_enemy_models_moved_over.extend(path_enemy_models.get(path_node, []))
                path_node = came_from[path_node]
                
            path.append(start)
            path.reverse()
            path.append(goal)  # Ensure we end exactly at goal
            
            # Remove duplicates from enemy models moved over
            unique_enemy_models = []
            for enemy_model in all_enemy_models_moved_over:
                if enemy_model not in unique_enemy_models:
                    unique_enemy_models.append(enemy_model)
            
            logger.debug(f"Enhanced path found after {iterations} iterations, length: {len(path)}, enemy models moved over: {len(unique_enemy_models)}")
            return path, unique_enemy_models
        
        # Get valid neighbors according to Warhammer 40k rules
        neighbors_with_enemies = get_enhanced_neighbors(current, model, game_map.obstacles, game_map, goal, movement_action)
        
        for neighbor, enemy_models_moved_over in neighbors_with_enemies:
            if neighbor in closed_set:
                continue
                
            # Calculate movement cost (including vertical movement)
            movement_cost = heuristic(current, neighbor)
            tentative_g_score = g_score[current] + movement_cost
            
            # If we've found a better path to this neighbor
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = g_score[neighbor] + heuristic(neighbor, goal)
                
                # Track enemy models moved over for this path
                current_enemy_models = path_enemy_models.get(current, [])
                path_enemy_models[neighbor] = current_enemy_models + enemy_models_moved_over
                
                # Add to open set if not already there with worse score
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        iterations += 1
        
        # Progress logging for long pathfinding
        if iterations % 1000 == 0:
            logger.debug(f"Enhanced A* iteration {iterations}, open set size: {len(open_set)} (movement action: {movement_action})")
    
    logger.debug(f"No enhanced path found after {iterations} iterations for {model.name} (movement action: {movement_action})")
    return None

# Keep the original a_star function for backwards compatibility
def a_star(model: 'Model', obstacles, target, max_iterations=10000):
    """A* pathfinding algorithm with adaptive step size and iteration limit."""
    start = (model.model_base.x, model.model_base.y, model.model_base.z)
    goal = target[:3]
    ellipse = model.model_base.get_base_shape()
    
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}
    
    iterations = 0
    while open_set and iterations < max_iterations:
        current = heapq.heappop(open_set)[1]
        
        current_ellipse = translate(ellipse, current[0] - ellipse.centroid.x, current[1] - ellipse.centroid.y)
        if current_ellipse.intersects(Point(target[:2])) or heuristic(current, goal) < 0.1:  # Changed goal condition
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            logging.debug(f"Path found after {iterations} iterations")
            return path[::-1] + [goal]  # Add the exact goal point to the end of the path
        
        for neighbor in get_neighbors(current, obstacles, current_ellipse, goal):
            tentative_g_score = g_score[current] + heuristic(current, neighbor)
            
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = g_score[neighbor] + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        iterations += 1
    
    logger.debug(f"No path found after {iterations} iterations")
    return None  # No path found

def simplify_path(path, obstacles, ellipse, tolerance=0.1):
    """Simplify the path using the Ramer-Douglas-Peucker algorithm and additional collision checks."""
    line = LineString(path)
    simplified = list(line.simplify(tolerance).coords)
    
    i = 0
    while i < len(simplified) - 2:
        start = simplified[i]
        end = simplified[i + 2]
        
        # Check if the direct path between start and end collides with any obstacles
        test_line = LineString([start, end])
        collision = any(test_line.intersects(obs.polygon) for obs in obstacles)
        
        if not collision:
            # Check if the ellipse moving along this path collides with any obstacles
            test_ellipse = translate(ellipse, start[0] - ellipse.centroid.x, start[1] - ellipse.centroid.y)
            dx, dy = end[0] - start[0], end[1] - start[1]
            moved_ellipse, collision = move_object(test_ellipse, obstacles, dx, dy, i)
            
            if not collision:
                # If no collision, remove the intermediate point
                simplified.pop(i + 1)
            else:
                i += 1
        else:
            i += 1
    return simplified

def can_end_move_on_terrain(model: 'Model', obstacle: 'Obstacle') -> bool:
    from ..classes.map import ObstacleType
    terrain = obstacle.terrain_type
    base_overhang = base_overhangs_obstacle(model, obstacle)
    if terrain in [ObstacleType.CRATER_AND_RUBBLE, ObstacleType.DEBRIS_AND_STATUARY]:
        return False  # Cannot end move on this terrain
    elif terrain == ObstacleType.HILLS_AND_SEALED_BUILDINGS:
        return not base_overhang  # Can end move if base does not overhang
    elif terrain == ObstacleType.WOODS:
        return True  # Can end move on this terrain
    elif terrain == ObstacleType.RUINS:
        unit = model.parent_unit
        # TODO - not accurate, need to account for floors. All units can end move on ruins base floor
        if unit.is_infantry or unit.is_beast or unit.is_belisarius_cawl or unit.is_imperium_primarch:
            return not base_overhang
        else:
            return False  # Other units cannot end move on RUINS
    else:
        # Default behavior
        return True

def base_overhangs_obstacle(model: 'Model', obstacle: 'Obstacle') -> bool:
    base_shape = model.model_base.get_base_shape_at(model.model_base.x, model.model_base.y, model.model_base.facing)
    return not obstacle.polygon.contains(base_shape) and obstacle.polygon.intersects(base_shape)

def build_formation_templates(N, spacing):
    """
    Returns dict of {formation_name: np.ndarray[N×2]} offsets.
    """
    templates = {}
    # BLOCK: fill rows of width = ceil(sqrt(N))
    w = int(np.ceil(np.sqrt(N)))
    coords = [(i % w, i // w) for i in range(N)]
    block = np.array(coords, dtype=float) * spacing
    # center
    block -= block.mean(axis=0)
    templates['block'] = block

    # WEDGE: triangular stacks
    wedge = []
    row = 0
    placed = 0
    while placed < N:
        for i in range(row+1):
            if placed >= N: break
            x = (i - row/2)*spacing
            y = -row*spacing
            wedge.append((x,y))
            placed += 1
        row += 1
    wedge = np.array(wedge)[:N]
    wedge -= wedge.mean(axis=0)
    templates['wedge'] = wedge

    # CIRCLE: petals around a circle
    angles = np.linspace(0, 2*np.pi, N, endpoint=False)
    circle = np.stack([np.cos(angles), np.sin(angles)], axis=1) * spacing
    templates['circle'] = circle

    # COLUMN: single file along +Y
    col = np.stack([np.zeros(N), np.arange(N)*spacing], axis=1)
    col -= col.mean(axis=0)
    templates['column'] = col

    return templates

def footprint_from_offsets(offsets, unit):
    """
    Given an (N×2) offsets array and unit, reconstruct
    the convex-hull-buffer footprint Polygon.
    """
    polys = []
    cx, cy = unit.get_position()[:2]
    for (dx,dy), m in zip(offsets, unit.models):
        base = m.model_base.get_base_shape()
        polys.append(translate(base, cx+dx - m.model_base.x,
                                cy+dy - m.model_base.y))
    hull = unary_union(polys).convex_hull
    # For deployment, use no buffer - just check actual model base collisions
    # Adding any buffer makes small units appear much larger than they are
    return hull

def build_spatial_index(obstacles, enemies):
    """
    Build an STRtree index of blocking polygons from terrain obstacles and enemy models.

    Parameters:
        obstacles: iterable of objects with a `.polygon` attribute (Shapely Polygon) or Shapely Polygon objects directly
        enemies: iterable of model objects with `.model_base.get_base_shape()` and `.is_alive()`.

    Returns:
        STRtree instance containing all blocker polygons.
    """
    blocker_polys = []
    # Add terrain obstacle polygons
    for obs in obstacles:
        # Handle both Obstacle objects (with .polygon attribute) and direct Polygon objects
        if hasattr(obs, 'polygon'):
            blocker_polys.append(obs.polygon)
        else:
            # Assume it's already a Shapely Polygon (e.g., boundary repulsors)
            blocker_polys.append(obs)

    # Add live enemy base shapes
    for enemy in enemies:
        if enemy.is_alive:
            blocker_polys.append(enemy.model_base.get_base_shape())

    # Build and return the spatial index
    return STRtree(blocker_polys)

def query_spatial_index(tree: STRtree, query_geom) -> List:
    """Query spatial index and return geometry objects (not indices).
    
    In Shapely 2.0+, STRtree.query() returns indices instead of geometry objects.
    This helper function handles both the old and new API for compatibility.
    
    Args:
        tree: STRtree spatial index
        query_geom: Geometry to query with
        
    Returns:
        List of geometry objects that intersect with query_geom
    """
    indices = tree.query(query_geom)
    
    # In Shapely 2.0+, query() returns indices (numpy arrays of integers)
    # We need to use tree.geometries[index] to get the actual geometry objects
    if hasattr(tree, 'geometries') and len(indices) > 0:
        # Check if indices are actually indices (integers) rather than geometry objects
        if hasattr(indices, '__iter__') and len(indices) > 0:
            first_result = indices[0] if hasattr(indices, '__getitem__') else next(iter(indices))
            # If it's an integer type, we need to convert indices to geometries
            if isinstance(first_result, (int, np.integer)):
                return [tree.geometries[i] for i in indices]
    
    # Fallback: if indices are actually geometry objects (old API), return as-is
    return list(indices) if hasattr(indices, '__iter__') else [indices]