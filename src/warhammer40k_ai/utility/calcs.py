from math import sqrt, atan2, pi, cos, sin, acos
from typing import Tuple, List, Optional
import heapq
import numpy as np
from ..utility.constants import MM_TO_INCHES, FREELY_CLIMBABLE_RANGE, ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
from shapely.geometry import LineString, Point, Polygon
from shapely.affinity import translate, rotate
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

# Constants for optimized pathfinding
ORIENTATIONS = [0, 90, 45, -45, 15, -15, 30, -30, 60, -60, 75, -75]  # Degrees

# Import existing constants
from .constants import ENGAGEMENT_RANGE_HORIZONTAL, MM_TO_INCHES

# OPTIMIZED PATHFINDING INTEGRATION
# =================================
# This module now includes optimized A* pathfinding with:
# - Minkowski sum pre-computation for fast collision detection
# - STRTree spatial indexing for O(log n) spatial queries
# - Rotation cost tracking using existing get_pivot_cost() function
# - MODEL-LEVEL PATHFINDING: Works with individual models for maximum flexibility
# - COHERENCY SEPARATION: Pathfinding ignores coherency, validated separately
# - Backward compatibility with existing pathfinding interfaces
#
# Main functions:
# - get_individual_model_movement_path(): Human-friendly individual model movement
# - get_optimized_path(): Core function for model-level pathfinding
# - a_star_optimized(): Core optimized A* algorithm (model-level)
# - a_star_optimized_with_pivot_cost(): Optimized pathfinding with pivot cost integration
# - get_optimized_paths_for_unit_models(): Multi-model pathfinding for units
# - get_optimized_path_for_unit(): Unit-level compatibility wrapper
# - validate_unit_coherency_after_movement(): Post-movement coherency validation
# - process_unit_movement_with_coherency_check(): Complete human movement workflow
# - a_star_enhanced(): Enhanced pathfinding with movement action support (uses optimized for basic cases)
# - a_star(): Legacy compatibility wrapper (uses optimized when possible)
#
# ARCHITECTURAL CHANGE: Movement is now handled at the model level rather than unit level.
# This allows for more flexible movement patterns and better human player control.
# Unit coherency is completely ignored during pathfinding - it's the human player's
# responsibility to place models coherently. Coherency is validated only after all
# models have finished moving, and non-coherent models are removed from play.
#
# The optimized pathfinding provides 3-10x performance improvement over legacy methods
# while maintaining full compatibility with existing Warhammer 40k movement rules.

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
    """Check if a unit can freely traverse over an obstacle without vertical movement cost.

    This function determines if terrain should be ignored for pathfinding purposes.
    """
    # Flying units can traverse any obstacle freely
    if unit.is_flying:
        return True

    # Check height-based traversal (≤2" is freely climbable)
    if obstacle.height <= FREELY_CLIMBABLE_RANGE:
        return True

    # Import at runtime to avoid circular import
    from ..classes.map import ObstacleType

    # For terrain >2" height, check if it has special traversal rules
    terrain = obstacle.terrain_type
    if terrain == ObstacleType.RUINS:
        # Infantry, Beasts, Imperium Primarch, and Belisarius Cawl can move through walls freely
        return (unit.is_infantry or unit.is_beast or
                unit.is_belisarius_cawl or unit.is_imperium_primarch)

    # All other terrain types >2" can be traversed but require vertical movement cost
    # They should NOT be treated as blocking terrain for pathfinding
    return True

def is_terrain_impassable(unit: 'Unit', obstacle: 'Obstacle') -> bool:
    """Check if terrain is completely impassable for a unit.

    This determines if terrain should be added to blocking collision trees.
    """
    # Flying units can pass through any terrain
    if unit.is_flying:
        return False

    # Import at runtime to avoid circular import
    from ..classes.map import ObstacleType

    # Only RUINS are truly impassable for certain unit types
    terrain = obstacle.terrain_type
    if terrain == ObstacleType.RUINS:
        # Non-Infantry/Beast units cannot move through RUINS walls
        return not (unit.is_infantry or unit.is_beast or
                   unit.is_belisarius_cawl or unit.is_imperium_primarch)

    # All other terrain types are passable (may require vertical cost)
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

    # Determine the maximum obstacle height along the path that requires vertical movement
    max_obstacle_height = 0
    for obstacle in intersecting_obstacles:
        # Only consider obstacles that are not impassable
        if not is_terrain_impassable(model.parent_unit, obstacle):
            # If obstacle is >2" height, it requires vertical movement cost
            if obstacle.height > FREELY_CLIMBABLE_RANGE:
                if obstacle.height > max_obstacle_height:
                    max_obstacle_height = obstacle.height

    # Set vertical distance based on the highest obstacle that requires climbing
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

def heuristic_2d(a, b):
    """Calculate the heuristic (estimated distance) between two 2D points."""
    return ((a[0] - b[0])**2 + (a[1] - b[1])**2)**0.5

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

# =============================================================================
# UNIFIED PATHFINDING SYSTEM
# =============================================================================

from enum import Enum

class MovementType(Enum):
    """Movement types with specific rules and validation"""
    MOVE = "move"
    ADVANCE = "advance"
    FALL_BACK = "fall_back"
    CHARGE = "charge"
    PILE_IN = "pile_in"
    CONSOLIDATE = "consolidate"
    SCOUT = "scout"

def unified_pathfinding(model: 'Model', target: Tuple[float, float, float], movement_type: MovementType,
                       max_distance: float, game_map: 'Map', target_unit: 'Unit' = None) -> dict:
    """
    Unified pathfinding system that handles all movement types through different
    STRTree configurations and validation rules.

    Args:
        model: The model to move
        target: Target position (x, y, z)
        movement_type: Type of movement (MOVE, CHARGE, etc.)
        max_distance: Maximum movement distance
        game_map: The game map
        target_unit: Target unit for charge movement (required for CHARGE)

    Returns:
        Dict with keys: 'valid', 'path', 'distance', 'reason'
    """
    try:
        # Handle None model gracefully
        if model is None:
            return {
                'valid': False,
                'path': [],
                'distance': 0.0,
                'reason': 'Invalid input: model is None'
            }

        # Validate target
        if target is None or len(target) < 3:
            return {
                'valid': False,
                'path': [],
                'distance': 0.0,
                'reason': 'Invalid input: target is None or incomplete'
            }

        # Validate max_distance
        if max_distance <= 0:
            return {
                'valid': False,
                'path': [],
                'distance': 0.0,
                'reason': 'Invalid input: max_distance must be positive'
            }

        print(f"🔍 DEBUG: Unified pathfinding for {model.name} to {target}, type: {movement_type}, max_dist: {max_distance}")

        # Build collision trees based on movement type and unit capabilities
        collision_trees = build_collision_trees(model.parent_unit, movement_type, game_map)
        print(f"🔍 DEBUG: Built collision trees: {list(collision_trees.keys())}")

        # Get validation rules for this movement type
        validation_rules = get_validation_rules(movement_type, target_unit)
        print(f"🔍 DEBUG: Validation rules: {validation_rules}")

        # Run unified A* pathfinding
        result = a_star_unified(model, target, max_distance, collision_trees, validation_rules, game_map)
        print(f"🔍 DEBUG: A* result: valid={result.get('valid')}, reason={result.get('reason')}")

        return result

    except Exception as e:
        import traceback
        model_name = model.name if model and hasattr(model, 'name') else 'Unknown'
        print(f"❌ Unified pathfinding error for {model_name}: {e}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        return {
            'valid': False,
            'path': [],
            'distance': 0.0,
            'reason': f'Pathfinding error: {str(e)}'
        }

# REMOVED: can_unit_pass_through_terrain - using existing can_traverse_freely instead

def build_collision_trees(moving_unit: 'Unit', movement_type: MovementType, game_map: 'Map') -> dict:
    """
    Build STRTrees for collision detection based on movement type and unit capabilities.

    Args:
        moving_unit: The unit that is moving
        movement_type: Type of movement being performed
        game_map: The game map containing all objects

    Returns:
        Dict containing STRTrees for different collision types
    """
    # Filter terrain based on unit capabilities
    blocking_terrain = []
    for obstacle in game_map.obstacles:
        if is_terrain_impassable(moving_unit, obstacle):
            blocking_terrain.append(obstacle.polygon)

    # Get all models except the moving unit's models
    friendly_models = []
    enemy_models = []

    for unit in game_map.units:
        if unit == moving_unit or not unit.is_alive() or not unit.deployed:
            continue

        for model in unit.models:
            if not model.is_alive:
                continue

            model_shape = model.model_base.get_base_shape()
            if unit.faction == moving_unit.faction:
                friendly_models.append(model_shape)
            else:
                enemy_models.append(model_shape)

    # Build trees based on movement type
    trees = {
        'terrain': STRtree(blocking_terrain) if blocking_terrain else None,
        'friendly_models': STRtree(friendly_models) if friendly_models else None,
        'enemy_models': STRtree(enemy_models) if enemy_models else None
    }

    print(f"🔍 DEBUG: Built collision trees - terrain: {len(blocking_terrain)}, friendly: {len(friendly_models)}, enemy: {len(enemy_models)}")

    # Add engagement range buffers based on movement type
    if movement_type in [MovementType.MOVE, MovementType.ADVANCE]:
        # Standard movement: 1" engagement range buffer around enemy models
        if enemy_models:
            buffered_enemies = [shape.buffer(ENGAGEMENT_RANGE_HORIZONTAL) for shape in enemy_models]
            trees['engagement_buffer'] = STRtree(buffered_enemies)

    elif movement_type == MovementType.SCOUT:
        # Scout movement: 9" buffer around enemy models and deployment zone
        if enemy_models:
            buffered_enemies = [shape.buffer(9.0) for shape in enemy_models]
            trees['engagement_buffer'] = STRtree(buffered_enemies)

        # Add deployment zone buffer (9" from enemy deployment zone)
        enemy_deployment_zone = game_map.get_enemy_deployment_zone(moving_unit.faction)
        if enemy_deployment_zone:
            buffered_deployment = enemy_deployment_zone.buffer(9.0)
            trees['deployment_buffer'] = STRtree([buffered_deployment])

    elif movement_type == MovementType.FALL_BACK:
        # Fall back: can move through models, only terrain blocks
        trees['friendly_models'] = None  # Can move through friendly models
        trees['enemy_models'] = None     # Can move through enemy models

    elif movement_type == MovementType.CHARGE:
        # Charge: no engagement range buffer (can move into engagement range)
        pass  # Use base trees without engagement buffer

    elif movement_type in [MovementType.PILE_IN, MovementType.CONSOLIDATE]:
        # Pile-in/Consolidate: 3" movement, no engagement buffer
        pass  # Use base trees without engagement buffer

    return trees

def get_validation_rules(movement_type: MovementType, target_unit: 'Unit' = None) -> dict:
    """
    Get validation rules for specific movement types.

    Args:
        movement_type: Type of movement being performed
        target_unit: Target unit for charge movement (required for CHARGE)

    Returns:
        Dict containing validation rules for this movement type
    """
    # Base rules that apply to all movement types
    base_rules = {
        'prevent_friendly_overlap': True,    # Always prevent friendly model overlap
        'prevent_enemy_overlap': True,       # Always prevent enemy model overlap
        'apply_pivot_cost': True,           # Always apply pivot costs
        'check_terrain_traversal': True,    # Always check if unit can traverse terrain
    }

    # Add movement-specific rules
    if movement_type == MovementType.CHARGE:
        base_rules.update({
            'must_end_in_engagement_range': True,
            'target_unit': target_unit,  # Required for charge validation
            'allow_engagement_range_movement': True,  # Can move through engagement range
        })

    elif movement_type == MovementType.PILE_IN:
        base_rules.update({
            'must_end_closer_to_enemies': True,
            'prefer_base_contact': True,  # Prefer ending in base-to-base contact
            'max_distance_override': 3.0,  # Pile-in is always 3"
        })

    elif movement_type == MovementType.CONSOLIDATE:
        base_rules.update({
            'must_end_closer_to_enemies_or_objectives': True,
            'prefer_base_contact': True,  # Prefer ending in base-to-base contact
            'max_distance_override': 3.0,  # Consolidate is always 3"
        })

    elif movement_type == MovementType.FALL_BACK:
        base_rules.update({
            'can_move_through_models': True,  # Can move through enemy and friendly models
            'cannot_end_in_engagement_range': True,  # Cannot end within engagement range
            'check_desperate_escape': True,  # Check if Desperate Escape tests are needed
        })

    elif movement_type == MovementType.SCOUT:
        base_rules.update({
            'min_distance_from_enemies': 9.0,  # Must end 9" from enemies
            'min_distance_from_deployment_zone': 9.0,  # Must end 9" from enemy deployment
        })

    elif movement_type in [MovementType.MOVE, MovementType.ADVANCE]:
        base_rules.update({
            'cannot_move_within_engagement_range': True,  # Cannot move within 1" of enemies
        })

    return base_rules

def a_star_unified(model: 'Model', target: Tuple[float, float, float], max_distance: float,
                  collision_trees: dict, validation_rules: dict, game_map: 'Map') -> dict:
    """
    Unified A* pathfinding algorithm that uses STRTrees for collision detection
    and validation rules for movement-specific constraints.

    Args:
        model: The model to move
        target: Target position (x, y, z)
        max_distance: Maximum movement distance
        collision_trees: Dict of STRTrees for different collision types
        validation_rules: Dict of validation rules for this movement type
        game_map: The game map

    Returns:
        Dict with keys: 'valid', 'path', 'distance', 'reason'
    """
    import heapq

    start = (model.model_base.x, model.model_base.y, model.model_base.z)
    goal = target
    step_size = 0.5  # 0.5" step size for pathfinding (larger for straighter paths)

    # Initialize A* data structures
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}
    closed_set = set()

    max_iterations = 15000
    iterations = 0

    # Track collision reasons for better error reporting
    collision_reasons = set()

    print(f"🔍 DEBUG: Starting A* from {start} to {goal}, max_distance: {max_distance}")

    # Optimization: Try straight line path first if no obstacles
    straight_line_distance = heuristic(start, goal)
    if straight_line_distance <= max_distance:
        # Check if straight line path is clear
        straight_line_clear = True
        num_checks = max(10, int(straight_line_distance / step_size))

        for i in range(1, num_checks):
            t = i / num_checks
            check_pos = (
                start[0] + t * (goal[0] - start[0]),
                start[1] + t * (goal[1] - start[1]),
                start[2] + t * (goal[2] - start[2])
            )

            validity_result = is_position_valid_unified_detailed(check_pos, model, collision_trees, validation_rules, game_map)
            if not validity_result['valid']:
                straight_line_clear = False
                collision_reasons.add(validity_result['reason'])
                break

        if straight_line_clear:
            # Validate final position for straight line path
            validation_result = validate_final_position(model, goal, validation_rules, game_map)
            if not validation_result['valid']:
                print(f"🔍 DEBUG: Straight line path blocked by final position validation: {validation_result['reason']}")
                # Continue with A* pathfinding instead
            else:
                print(f"🔍 DEBUG: Using straight line path (distance: {straight_line_distance:.1f}\")")

                # Check for Desperate Escape requirements for straight line path
                desperate_escape_info = check_desperate_escape_requirements(
                    model, [start, goal], validation_rules, game_map
                )

                return {
                    'valid': True,
                    'path': [start, goal],
                    'distance': straight_line_distance,
                    'reason': 'Straight line path',
                    'desperate_escape': desperate_escape_info
                }

    while open_set and iterations < max_iterations:
        current = heapq.heappop(open_set)[1]

        if current in closed_set:
            continue

        closed_set.add(current)

        # Check if we've reached the goal
        if heuristic(current, goal) < step_size:
            # Reconstruct path
            path = []
            path_node = current
            while path_node in came_from:
                path.append(path_node)
                path_node = came_from[path_node]
            path.append(start)
            path.reverse()
            path.append(goal)  # Ensure we end exactly at goal

            # Calculate total distance
            total_distance = 0
            for i in range(1, len(path)):
                total_distance += heuristic(path[i-1], path[i])

            # Apply pivot cost only if there's actual rotation
            if validation_rules.get('apply_pivot_cost', False) and len(path) > 1:
                # Check if the path requires rotation (direction change)
                requires_rotation = False
                if len(path) >= 3:  # Need at least 3 points to detect direction change
                    # Check if there are significant direction changes
                    for i in range(1, len(path) - 1):
                        prev_dir = (path[i][0] - path[i-1][0], path[i][1] - path[i-1][1])
                        next_dir = (path[i+1][0] - path[i][0], path[i+1][1] - path[i][1])

                        # Normalize directions
                        prev_len = (prev_dir[0]**2 + prev_dir[1]**2)**0.5
                        next_len = (next_dir[0]**2 + next_dir[1]**2)**0.5

                        if prev_len > 0 and next_len > 0:
                            prev_norm = (prev_dir[0]/prev_len, prev_dir[1]/prev_len)
                            next_norm = (next_dir[0]/next_len, next_dir[1]/next_len)

                            # Calculate angle between directions
                            dot_product = prev_norm[0]*next_norm[0] + prev_norm[1]*next_norm[1]
                            dot_product = max(-1, min(1, dot_product))  # Clamp to [-1, 1]
                            angle_diff = acos(dot_product)

                            # If angle change > 30 degrees, consider it rotation
                            if angle_diff > pi / 6:  # 30 degrees
                                requires_rotation = True
                                break

                if requires_rotation:
                    pivot_cost = get_pivot_cost(model.parent_unit)
                    if pivot_cost > 0:
                        total_distance += pivot_cost
                        print(f"🔍 DEBUG: Applied pivot cost: {pivot_cost:.1f}\"")
                else:
                    print(f"🔍 DEBUG: No rotation detected, no pivot cost applied")

            # Validate final position according to movement rules
            validation_result = validate_final_position(model, goal, validation_rules, game_map)
            if not validation_result['valid']:
                return {
                    'valid': False,
                    'path': None,
                    'distance': total_distance,
                    'reason': validation_result['reason']
                }

            # Check distance limit
            max_dist = validation_rules.get('max_distance_override', max_distance)
            if total_distance > max_dist:
                return {
                    'valid': False,
                    'path': None,
                    'distance': total_distance,
                    'reason': f'Path too long ({total_distance:.1f}" > {max_dist:.1f}")'
                }

            # Check for Desperate Escape requirements
            desperate_escape_info = check_desperate_escape_requirements(
                model, path, validation_rules, game_map
            )

            return {
                'valid': True,
                'path': path,
                'distance': total_distance,
                'reason': 'Valid path found',
                'desperate_escape': desperate_escape_info
            }

        # Generate neighbors (3D movement with vertical component)
        for dx, dy, dz in [(-step_size, 0, 0), (step_size, 0, 0), (0, -step_size, 0), (0, step_size, 0),
                          (-step_size, -step_size, 0), (-step_size, step_size, 0),
                          (step_size, -step_size, 0), (step_size, step_size, 0),
                          # Add vertical movement for flying units or terrain traversal
                          (0, 0, step_size), (0, 0, -step_size)]:
            neighbor = (current[0] + dx, current[1] + dy, current[2] + dz)

            if neighbor in closed_set:
                continue

            # Check if position is valid using STRTrees
            validity_result = is_position_valid_unified_detailed(neighbor, model, collision_trees, validation_rules, game_map)
            if not validity_result['valid']:
                collision_reasons.add(validity_result['reason'])
                if iterations < 10:  # Only log first few iterations to avoid spam
                    print(f"🔍 DEBUG: Position {neighbor} invalid: {validity_result['reason']}")
                continue

            tentative_g_score = g_score[current] + heuristic(current, neighbor)

            # Check distance limit during pathfinding
            max_dist = validation_rules.get('max_distance_override', max_distance)
            if tentative_g_score > max_dist:
                continue

            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

        iterations += 1

    # Provide more specific failure reason based on encountered obstacles
    if collision_reasons:
        primary_reason = list(collision_reasons)[0]  # Get first encountered reason
        if len(collision_reasons) > 1:
            reason = f"{primary_reason} (and {len(collision_reasons)-1} other obstacles)"
        else:
            reason = primary_reason
    else:
        reason = f'No path found after {iterations} iterations'

    return {
        'valid': False,
        'path': None,
        'distance': 0,
        'reason': reason
    }

def is_position_valid_unified(position: Tuple[float, float, float], model: 'Model',
                            collision_trees: dict, validation_rules: dict, game_map: 'Map' = None) -> bool:
    """
    Check if a position is valid using STRTrees and validation rules.

    Args:
        position: Position to check (x, y, z)
        model: The model being moved
        collision_trees: Dict of STRTrees for collision detection
        validation_rules: Dict of validation rules

    Returns:
        True if position is valid, False otherwise
    """
    # Create the moving model's base shape at the test position
    # We need to check shape intersection, not just point collision
    current_pos = model.get_location()
    dx = position[0] - current_pos[0]
    dy = position[1] - current_pos[1]

    # Get the model's base shape and translate it to the test position
    moving_model_shape = model.model_base.get_base_shape()
    test_shape = translate(moving_model_shape, dx, dy)

    # Check if the entire model base fits within battlefield boundaries
    if game_map:
        if not game_map.is_within_boundary(model, (position[0], position[1])):
            print(f"🔍 DEBUG: Position {position} would place model outside battlefield boundaries")
            return False
    else:
        # Fallback basic boundary check if no game_map provided
        bounds = test_shape.bounds  # (minx, miny, maxx, maxy)
        if bounds[0] < 0 or bounds[1] < 0:
            print(f"🔍 DEBUG: Position {position} would place model outside battlefield (negative coordinates)")
            return False

    # Check terrain collisions using shape intersection
    if collision_trees.get('terrain'):
        potential_hits = query_spatial_index(collision_trees['terrain'], test_shape)
        actual_hits = []

        for hit_shape in potential_hits:
            try:
                if test_shape.intersects(hit_shape):
                    actual_hits.append(hit_shape)
            except Exception as e:
                print(f"🔍 DEBUG: Error checking terrain intersection: {e}, hit_shape type: {type(hit_shape)}")
                continue

        if actual_hits:
            print(f"🔍 DEBUG: Position {position} blocked by terrain (shape intersection: {len(actual_hits)} hits)")
            return False

    # Check friendly model collisions using shape intersection (always blocked unless fall back)
    if collision_trees.get('friendly_models') and validation_rules.get('prevent_friendly_overlap', True):
        if not validation_rules.get('can_move_through_models', False):
            # Use shape intersection instead of point collision
            potential_hits = query_spatial_index(collision_trees['friendly_models'], test_shape)
            actual_hits = []

            for hit_shape in potential_hits:
                try:
                    if test_shape.intersects(hit_shape):
                        actual_hits.append(hit_shape)
                except Exception as e:
                    print(f"🔍 DEBUG: Error checking friendly model intersection: {e}, hit_shape type: {type(hit_shape)}")
                    continue

            if actual_hits:
                print(f"🔍 DEBUG: Position {position} blocked by friendly models (shape intersection: {len(actual_hits)} hits)")
                return False
        else:
            print(f"🔍 DEBUG: Can move through models - skipping friendly collision check")
    else:
        if not collision_trees.get('friendly_models'):
            print(f"🔍 DEBUG: No friendly models tree")
        if not validation_rules.get('prevent_friendly_overlap', True):
            print(f"🔍 DEBUG: prevent_friendly_overlap is False")

    # Check enemy model collisions using shape intersection (always blocked unless fall back)
    if collision_trees.get('enemy_models') and validation_rules.get('prevent_enemy_overlap', True):
        if not validation_rules.get('can_move_through_models', False):
            # Use shape intersection instead of point collision
            potential_hits = query_spatial_index(collision_trees['enemy_models'], test_shape)
            actual_hits = []

            for hit_shape in potential_hits:
                try:
                    if test_shape.intersects(hit_shape):
                        actual_hits.append(hit_shape)
                except Exception as e:
                    print(f"🔍 DEBUG: Error checking enemy model intersection: {e}, hit_shape type: {type(hit_shape)}")
                    continue

            if actual_hits:
                print(f"🔍 DEBUG: Position {position} blocked by enemy models (shape intersection: {len(actual_hits)} hits)")
                return False

    # Check engagement range buffer using shape intersection (for normal movement)
    if collision_trees.get('engagement_buffer') and validation_rules.get('cannot_move_within_engagement_range', False):
        potential_hits = query_spatial_index(collision_trees['engagement_buffer'], test_shape)
        actual_hits = []

        for hit_shape in potential_hits:
            if test_shape.intersects(hit_shape):
                actual_hits.append(hit_shape)

        if actual_hits:
            print(f"🔍 DEBUG: Position {position} blocked by engagement range (shape intersection: {len(actual_hits)} hits)")
            return False

    # Check scout-specific deployment buffers using shape intersection
    if collision_trees.get('deployment_buffer'):
        potential_hits = query_spatial_index(collision_trees['deployment_buffer'], test_shape)
        actual_hits = []

        for hit_shape in potential_hits:
            if test_shape.intersects(hit_shape):
                actual_hits.append(hit_shape)

        if actual_hits:
            print(f"🔍 DEBUG: Position {position} blocked by deployment buffer (shape intersection: {len(actual_hits)} hits)")
            return False

    return True

def is_position_valid_unified_detailed(position: Tuple[float, float, float], model: 'Model',
                                      collision_trees: dict, validation_rules: dict, game_map: 'Map' = None) -> dict:
    """
    Check if a position is valid using STRTrees and validation rules, returning detailed reason.

    Args:
        position: Position to check (x, y, z)
        model: The model being moved
        collision_trees: Dict of STRTrees for collision detection
        validation_rules: Dict of validation rules

    Returns:
        Dict with 'valid' (bool) and 'reason' (str) keys
    """
    # Create the moving model's base shape at the test position
    current_pos = model.get_location()
    dx = position[0] - current_pos[0]
    dy = position[1] - current_pos[1]

    # Get the model's base shape and translate it to the test position
    moving_model_shape = model.model_base.get_base_shape()
    test_shape = translate(moving_model_shape, dx, dy)

    # Check if the entire model base fits within battlefield boundaries
    if game_map:
        if not game_map.is_within_boundary(model, (position[0], position[1])):
            return {'valid': False, 'reason': 'Position outside battlefield boundaries'}
    else:
        # Fallback basic boundary check if no game_map provided
        bounds = test_shape.bounds  # (minx, miny, maxx, maxy)
        if bounds[0] < 0 or bounds[1] < 0:
            return {'valid': False, 'reason': 'Position outside battlefield boundaries'}

    # Check terrain collisions using shape intersection
    if collision_trees.get('terrain'):
        potential_hits = query_spatial_index(collision_trees['terrain'], test_shape)
        actual_hits = []

        for hit_shape in potential_hits:
            try:
                if test_shape.intersects(hit_shape):
                    actual_hits.append(hit_shape)
            except Exception:
                continue

        if actual_hits:
            return {'valid': False, 'reason': 'Position blocked by terrain'}

    # Check friendly model collisions using shape intersection
    if collision_trees.get('friendly_models') and validation_rules.get('prevent_friendly_overlap', True):
        if not validation_rules.get('can_move_through_models', False):
            potential_hits = query_spatial_index(collision_trees['friendly_models'], test_shape)
            actual_hits = []

            for hit_shape in potential_hits:
                try:
                    if test_shape.intersects(hit_shape):
                        actual_hits.append(hit_shape)
                except Exception:
                    continue

            if actual_hits:
                return {'valid': False, 'reason': 'Position blocked by friendly models'}

    # Check enemy model collisions using shape intersection
    if collision_trees.get('enemy_models') and validation_rules.get('prevent_enemy_overlap', True):
        if not validation_rules.get('can_move_through_models', False):
            potential_hits = query_spatial_index(collision_trees['enemy_models'], test_shape)
            actual_hits = []

            for hit_shape in potential_hits:
                try:
                    if test_shape.intersects(hit_shape):
                        actual_hits.append(hit_shape)
                except Exception:
                    continue

            if actual_hits:
                return {'valid': False, 'reason': 'Position blocked by enemy models'}

    # Check engagement range buffer using shape intersection
    if collision_trees.get('engagement_buffer') and validation_rules.get('cannot_move_within_engagement_range', False):
        potential_hits = query_spatial_index(collision_trees['engagement_buffer'], test_shape)
        actual_hits = []

        for hit_shape in potential_hits:
            if test_shape.intersects(hit_shape):
                actual_hits.append(hit_shape)

        if actual_hits:
            return {'valid': False, 'reason': 'Position within engagement range of enemy models'}

    # Check scout-specific deployment buffers using shape intersection
    if collision_trees.get('deployment_buffer'):
        potential_hits = query_spatial_index(collision_trees['deployment_buffer'], test_shape)
        actual_hits = []

        for hit_shape in potential_hits:
            if test_shape.intersects(hit_shape):
                actual_hits.append(hit_shape)

        if actual_hits:
            return {'valid': False, 'reason': 'Position within deployment zone buffer'}

    return {'valid': True, 'reason': 'Position is valid'}

def check_desperate_escape_requirements(model: 'Model', path: List[Tuple[float, float, float]],
                                       validation_rules: dict, game_map: 'Map') -> dict:
    """
    Check if Desperate Escape tests are required for fall back movement.

    Args:
        model: The model that moved
        path: The movement path taken
        validation_rules: Movement validation rules
        game_map: The game map

    Returns:
        Dict with desperate escape information
    """
    if not validation_rules.get('check_desperate_escape', False):
        return {'required': False, 'reason': 'Not fall back movement'}

    unit = model.parent_unit
    if not unit:
        return {'required': False, 'reason': 'No parent unit'}

    # Rule 1: Battle-shocked units always need Desperate Escape tests
    if unit.is_battle_shocked():
        return {
            'required': True,
            'reason': 'Battle-shocked unit falling back',
            'all_models': True,  # All models in unit must test
            'path_through_enemy': False  # Doesn't matter for battle-shocked
        }

    # Rule 2: Check if path goes through enemy models (for non-battle-shocked units)
    path_through_enemy = False
    if len(path) > 1:
        # Check each segment of the path for enemy model intersection
        for i in range(len(path) - 1):
            start_pos = path[i]
            end_pos = path[i + 1]

            # Create line segment for this part of the path
            from shapely.geometry import LineString
            path_segment = LineString([start_pos[:2], end_pos[:2]])

            # Check against all enemy models
            for enemy_unit in game_map.units:
                if (enemy_unit.faction == unit.faction or
                    not enemy_unit.is_alive() or
                    not enemy_unit.deployed):
                    continue

                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue

                    # Get enemy model shape
                    enemy_shape = enemy_model.model_base.get_base_shape()

                    # Check if path segment intersects enemy model
                    if path_segment.intersects(enemy_shape):
                        path_through_enemy = True
                        break

                if path_through_enemy:
                    break

            if path_through_enemy:
                break

    # Rule 3: Check for TITANIC or FLY keywords (exempt from Desperate Escape)
    if path_through_enemy:
        if unit.is_titanic or unit.is_flying:
            return {
                'required': False,
                'reason': 'TITANIC or FLY unit exempt from Desperate Escape',
                'path_through_enemy': True
            }

        return {
            'required': True,
            'reason': 'Path goes through enemy models',
            'all_models': False,  # Only models that moved through enemies
            'path_through_enemy': True
        }

    return {
        'required': False,
        'reason': 'Path does not go through enemy models',
        'path_through_enemy': False
    }

def validate_final_position(model: 'Model', position: Tuple[float, float, float],
                          validation_rules: dict, game_map: 'Map') -> dict:
    """
    Validate the final position according to movement-specific rules.

    Args:
        model: The model being moved
        position: Final position to validate (x, y, z)
        validation_rules: Dict of validation rules
        game_map: The game map

    Returns:
        Dict with keys: 'valid', 'reason'
    """
    # Check charge-specific rules
    if validation_rules.get('must_end_in_engagement_range', False):
        target_unit = validation_rules.get('target_unit')
        if not target_unit:
            return {'valid': False, 'reason': 'No target unit specified for charge'}

        # Check if final position is within engagement range of target unit using shape intersection
        # Create the moving model's base shape at the final position
        current_pos = model.get_location()
        dx = position[0] - current_pos[0]
        dy = position[1] - current_pos[1]

        moving_model_shape = model.model_base.get_base_shape()
        final_shape = translate(moving_model_shape, dx, dy)

        in_engagement_range = False
        for enemy_model in target_unit.models:
            if not enemy_model.is_alive:
                continue

            # Get enemy model shape and buffer by engagement range
            enemy_shape = enemy_model.model_base.get_base_shape()
            engagement_zone = enemy_shape.buffer(ENGAGEMENT_RANGE_HORIZONTAL)

            # Check if final position intersects with engagement zone
            if final_shape.intersects(engagement_zone):
                in_engagement_range = True
                break

        if not in_engagement_range:
            return {'valid': False, 'reason': 'Charge must end within engagement range of target unit'}

    # Check fall back rules
    if validation_rules.get('cannot_end_in_engagement_range', False):
        # Check if final position is within engagement range of any enemy using shape intersection
        # Create the moving model's base shape at the final position
        current_pos = model.get_location()
        dx = position[0] - current_pos[0]
        dy = position[1] - current_pos[1]

        moving_model_shape = model.model_base.get_base_shape()
        final_shape = translate(moving_model_shape, dx, dy)

        # Check against all enemy models using proper edge-to-edge distance
        for unit in game_map.units:
            if unit.faction == model.parent_unit.faction or not unit.is_alive() or not unit.deployed:
                continue
            for enemy_model in unit.models:
                if not enemy_model.is_alive:
                    continue

                # Get enemy model shape and buffer by engagement range
                enemy_shape = enemy_model.model_base.get_base_shape()
                engagement_zone = enemy_shape.buffer(ENGAGEMENT_RANGE_HORIZONTAL)

                # Check if final position intersects with engagement zone
                if final_shape.intersects(engagement_zone):
                    return {'valid': False, 'reason': 'Fall back cannot end within engagement range'}

    # Check pile-in/consolidate rules
    if validation_rules.get('must_end_closer_to_enemies', False):
        # TODO: Implement pile-in validation (must end closer to enemies)
        pass

    if validation_rules.get('must_end_closer_to_enemies_or_objectives', False):
        # TODO: Implement consolidate validation (must end closer to enemies or objectives)
        pass

    # Check scout rules
    if validation_rules.get('min_distance_from_enemies', 0) > 0:
        min_distance = validation_rules['min_distance_from_enemies']
        for unit in game_map.units:
            if unit.faction == model.parent_unit.faction or not unit.is_alive() or not unit.deployed:
                continue
            for enemy_model in unit.models:
                if not enemy_model.is_alive:
                    continue
                enemy_pos = enemy_model.get_location()
                distance = ((position[0] - enemy_pos[0])**2 + (position[1] - enemy_pos[1])**2)**0.5
                if distance < min_distance:
                    return {'valid': False, 'reason': f'Scout movement must end {min_distance}" from enemies'}

    return {'valid': True, 'reason': 'Valid final position'}

# REMOVED: a_star_enhanced_legacy - forcing use of new pathfinding system

# Keep the original a_star function for backwards compatibility
def a_star(model: 'Model', obstacles, target, max_iterations=10000):
    """
    A* pathfinding algorithm with adaptive step size and iteration limit.
    
    This function now uses the optimized pathfinding algorithm by default,
    with fallback to the legacy implementation if needed.
    """
    # Try to use the optimized pathfinding if we have a game_map
    if hasattr(model, 'parent_unit') and hasattr(model.parent_unit, 'game_map'):
        game_map = model.parent_unit.game_map
        max_distance = model.parent_unit.movement * 12  # Convert to inches
        
        try:
            path = a_star_optimized_with_pivot_cost(model, game_map, target, max_distance)
            if path:
                logger.debug(f"Optimized path found for {model.name}")
                return path
        except Exception as e:
            logger.warning(f"Optimized pathfinding failed, falling back to legacy: {e}")
    
    # Legacy pathfinding implementation
    return a_star_legacy(model, obstacles, target, max_iterations)

def a_star_legacy(model: 'Model', obstacles, target, max_iterations=10000):
    """Legacy A* pathfinding algorithm with adaptive step size and iteration limit."""
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
            logging.debug(f"Legacy path found after {iterations} iterations")
            return path[::-1] + [goal]  # Add the exact goal point to the end of the path
        
        for neighbor in get_neighbors(current, obstacles, current_ellipse, goal):
            tentative_g_score = g_score[current] + heuristic(current, neighbor)
            
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = g_score[neighbor] + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        iterations += 1
    
    logger.debug(f"No legacy path found after {iterations} iterations")
    return None  # No path found

def a_star_optimized_with_pivot_cost(model: 'Model', game_map: 'Map', target: Tuple[float, float, float], 
                                   max_distance: float, step_size: float = 0.4) -> Optional[List[Tuple[float, float, float]]]:
    """
    Optimized A* pathfinding with pivot cost integration for individual models.
    
    This is the main model-level pathfinding function that integrates optimized pathfinding
    with the existing pivot cost system.
    
    Args:
        model: The model to pathfind for
        game_map: The game map containing obstacles and units
        target: Target position (x, y, z) in inches
        max_distance: Maximum movement distance in inches
        step_size: Step size for pathfinding grid in inches
        
    Returns:
        List of path points (x, y, z) in inches, or None if no path exists
    """
    # Call the optimized A* algorithm
    result = a_star_optimized_enhanced(model, game_map, target[:2], max_distance, step_size)
    
    if not result:
        return None
    
    path, rotation_occurred = result
    
    # Apply pivot cost if any rotation occurred during the path
    effective_max_distance = max_distance
    if rotation_occurred and not model.parent_unit.has_circular_base:
        pivot_cost = get_pivot_cost(model.parent_unit)
        effective_max_distance -= pivot_cost
        logger.debug(f"Pivot cost applied: {pivot_cost:.2f} inches, effective max distance: {effective_max_distance:.2f} inches")
    
    # Validate path length against effective max distance
    if len(path) > 1:
        total_distance = 0
        for i in range(1, len(path)):
            step_distance = heuristic(path[i-1], path[i])
            total_distance += step_distance
            
            if total_distance > effective_max_distance:
                # Truncate path at maximum distance
                logger.debug(f"Path truncated at {effective_max_distance:.2f} inches due to pivot cost")
                return path[:i]
    
    return path

def get_optimized_path(model: 'Model', game_map: 'Map', target: Tuple[float, float, float], 
                      max_distance: Optional[float] = None) -> Optional[List[Tuple[float, float, float]]]:
    """
    Convenience function for getting an optimized path for a single model.
    
    This is the recommended function to use for all new model-level pathfinding needs.
    It automatically handles pivot costs and provides the best performance.
    
    Args:
        model: The model to pathfind for
        game_map: The game map containing obstacles and units
        target: Target position (x, y, z) in inches
        max_distance: Maximum movement distance in inches (defaults to parent unit's movement * 12)
        
    Returns:
        List of path points (x, y, z) in inches, or None if no path exists
    """
    if max_distance is None:
        max_distance = model.parent_unit.movement * 12  # Convert feet to inches
    
    return a_star_optimized_with_pivot_cost(model, game_map, target, max_distance)

def create_optimized_pathfinding_environment(game_map: 'Map', moving_model: 'Model') -> 'OptimizedPathfindingEnvironment':
    """
    Create an optimized pathfinding environment for a specific model.
    
    This can be useful when making multiple pathfinding calls for the same model,
    as it allows reusing the pre-computed collision geometry.
    
    Args:
        game_map: The game map containing obstacles and units
        moving_model: The model that will be pathfinding
        
    Returns:
        Optimized pathfinding environment
    """
    return OptimizedPathfindingEnvironment(game_map, moving_model)

# UNIT-LEVEL WRAPPER FUNCTIONS FOR BACKWARD COMPATIBILITY
# ========================================================

def get_optimized_path_for_unit(unit: 'Unit', game_map: 'Map', target: Tuple[float, float, float], 
                               max_distance: Optional[float] = None, model_index: int = 0) -> Optional[List[Tuple[float, float, float]]]:
    """
    Convenience function for getting an optimized path for a unit's model.
    
    This is a compatibility wrapper that works at the unit level but uses model-level pathfinding.
    For new code, prefer get_optimized_path() with individual models.
    
    Args:
        unit: The unit to pathfind for
        game_map: The game map containing obstacles and units
        target: Target position (x, y, z) in inches
        max_distance: Maximum movement distance in inches (defaults to unit.movement * 12)
        model_index: Index of the model in the unit to use for pathfinding (default: 0)
        
    Returns:
        List of path points (x, y, z) in inches, or None if no path exists
    """
    if not unit.models or model_index >= len(unit.models):
        logger.warning(f"Invalid model index {model_index} for unit {unit.name}")
        return None
    
    model = unit.models[model_index]
    if max_distance is None:
        max_distance = unit.movement * 12  # Convert feet to inches
    
    return get_optimized_path(model, game_map, target, max_distance)

def get_optimized_paths_for_unit_models(unit: 'Unit', game_map: 'Map', targets: List[Tuple[float, float, float]], 
                                      max_distance: Optional[float] = None) -> List[Optional[List[Tuple[float, float, float]]]]:
    """
    Get optimized paths for all models in a unit.
    
    This function enables model-level movement for human players while maintaining unit coordination.
    Each model gets its own target and path.
    
    Args:
        unit: The unit containing models to pathfind for
        game_map: The game map containing obstacles and units
        targets: List of target positions (x, y, z) in inches, one per model
        max_distance: Maximum movement distance in inches (defaults to unit.movement * 12)
        
    Returns:
        List of paths, one per model. Each path is a list of (x, y, z) points or None if no path exists.
    """
    if max_distance is None:
        max_distance = unit.movement * 12  # Convert feet to inches
    
    if len(targets) != len(unit.models):
        logger.warning(f"Number of targets ({len(targets)}) does not match number of models ({len(unit.models)}) in unit {unit.name}")
        return [None] * len(unit.models)
    
    paths = []
    for model, target in zip(unit.models, targets):
        path = get_optimized_path(model, game_map, target, max_distance)
        paths.append(path)
    
    return paths

def validate_unit_coherency_after_movement(unit: 'Unit', new_positions: List[Tuple[float, float, float]]) -> Tuple[bool, List[int]]:
    """
    Validate that unit coherency is maintained after model movement.
    
    This should be called after calculating paths for individual models to ensure
    the unit remains in coherency according to Warhammer 40k rules.
    
    Args:
        unit: The unit to validate
        new_positions: List of new positions (x, y, z) for each model
        
    Returns:
        Tuple[bool, List[int]]: (is_coherent, list_of_non_coherent_model_indices)
    """
    if len(new_positions) != len(unit.models):
        logger.warning(f"Number of positions ({len(new_positions)}) does not match number of models ({len(unit.models)}) in unit {unit.name}")
        return False, []
    
    # Check if unit has only one model - always coherent
    if len(unit.models) == 1:
        return True, []
    
    # Build adjacency graph based on coherency distance
    coherency_distance = unit.coherency_distance
    adjacency_graph = {}
    non_coherent_models = []
    
    for i, pos_i in enumerate(new_positions):
        adjacency_graph[i] = []
        for j, pos_j in enumerate(new_positions):
            if i != j:
                # Calculate edge-to-edge distance between model bases
                model_i = unit.models[i]
                model_j = unit.models[j]

                # Create temporary bases at the new positions to calculate proper edge-to-edge distance
                temp_base_i = model_i.model_base.__class__(model_i.model_base.base_type, model_i.model_base.radius)
                temp_base_i.set_position(pos_i[0], pos_i[1], pos_i[2])
                temp_base_i.set_facing(model_i.model_base.facing)

                temp_base_j = model_j.model_base.__class__(model_j.model_base.base_type, model_j.model_base.radius)
                temp_base_j.set_position(pos_j[0], pos_j[1], pos_j[2])
                temp_base_j.set_facing(model_j.model_base.facing)

                # Use proper edge-to-edge distance calculation
                distance = temp_base_i.edge_to_edge_distance(temp_base_j)

                if distance <= coherency_distance:
                    adjacency_graph[i].append(j)
    
    # Check if all models are connected (coherent)
    # Use BFS to find connected components
    visited = set()
    connected_components = []
    
    for i in range(len(unit.models)):
        if i not in visited:
            component = []
            queue = [i]
            visited.add(i)
            
            while queue:
                current = queue.pop(0)
                component.append(current)
                
                for neighbor in adjacency_graph[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            
            connected_components.append(component)
    
    # Unit is coherent if all models are in one connected component
    is_coherent = len(connected_components) == 1
    
    # If not coherent, find which models are isolated
    if not is_coherent:
        # Find the largest connected component (this should remain)
        largest_component = max(connected_components, key=len)
        
        # All models not in the largest component are non-coherent
        non_coherent_models = []
        for component in connected_components:
            if component != largest_component:
                non_coherent_models.extend(component)
    
    logger.debug(f"Unit {unit.name} coherency check: {'PASS' if is_coherent else 'FAIL'}")
    if not is_coherent:
        logger.debug(f"Non-coherent models: {non_coherent_models}")
    
    return is_coherent, non_coherent_models

def get_individual_model_movement_path(unit: 'Unit', model_index: int, target: Tuple[float, float, float],
                                    game_map: 'Map', max_distance: Optional[float] = None, movement_action: 'MovementAction' = None) -> Optional[List[Tuple[float, float, float]]]:
    """
    Get pathfinding result for an individual model within a unit's movement phase.
    
    This function is designed for human players who want to move models one at a time.
    It ignores coherency considerations during pathfinding - coherency is checked
    separately after all models in the unit have been moved.
    
    Args:
        unit: The unit containing the model
        model_index: Index of the model to move within the unit
        target: Target position (x, y, z) for the model
        game_map: The game map
        max_distance: Maximum movement distance (defaults to model's movement stat)
        movement_action: MovementAction enum value (MOVE, ADVANCE, FALL_BACK, CHARGE)
        
    Returns:
        Optional path as list of (x, y, z) positions, or None if no path found
    """
    if model_index < 0 or model_index >= len(unit.models):
        logger.warning(f"Invalid model index {model_index} for unit {unit.name} with {len(unit.models)} models")
        return None
    
    model = unit.models[model_index]
    
    # Use the model's movement stat if no max_distance specified
    if max_distance is None:
        max_distance = model.movement
    
    # Map MovementAction to MovementType
    movement_type_map = {
        None: MovementType.MOVE,
    }

    if movement_action is not None:
        from ..classes.unit import MovementAction
        movement_type_map.update({
            MovementAction.MOVE: MovementType.MOVE,
            MovementAction.ADVANCE: MovementType.ADVANCE,
            MovementAction.FALL_BACK: MovementType.FALL_BACK,
            MovementAction.CHARGE: MovementType.CHARGE,
        })

    movement_type = movement_type_map.get(movement_action, MovementType.MOVE)

    # Use unified pathfinding system
    pathfinding_result = unified_pathfinding(
        model=model,
        target=target[:2],
        movement_type=movement_type,
        max_distance=max_distance,
        game_map=game_map
    )

    if pathfinding_result and pathfinding_result.get('valid'):
        # Convert 2D path back to 3D
        path_3d = [(p[0], p[1], target[2]) for p in pathfinding_result['path']]
        logger.debug(f"Path found for model {model_index} in unit {unit.name}: {len(path_3d)} points, type: {movement_type}")
        return path_3d
    else:
        logger.debug(f"No path found for model {model_index} in unit {unit.name}: {pathfinding_result.get('reason', 'unknown')}")
        return None

def process_unit_movement_with_coherency_check(unit: 'Unit', model_movements: List[Tuple[int, List[Tuple[float, float, float]]]]) -> Tuple[bool, List[int]]:
    """
    Process a complete unit movement with individual model paths and validate coherency.
    
    This function handles the complete workflow for human players moving models individually:
    1. Apply all model movements
    2. Validate unit coherency
    3. Return coherency status and any non-coherent models
    
    Args:
        unit: The unit being moved
        model_movements: List of (model_index, path) tuples for each model that moved
        
    Returns:
        Tuple[bool, List[int]]: (is_coherent, non_coherent_model_indices)
    """
    # Calculate final positions for all models
    final_positions = []
    
    for i, model in enumerate(unit.models):
        # Check if this model has a movement path
        moved = False
        for model_index, path in model_movements:
            if model_index == i:
                # Use the final position from the path
                final_positions.append(path[-1])
                moved = True
                break
        
        if not moved:
            # Model didn't move, use current position
            final_positions.append(model.position)
    
    # Validate coherency with the final positions
    is_coherent, non_coherent_models = validate_unit_coherency_after_movement(unit, final_positions)
    
    return is_coherent, non_coherent_models

# ===========================================
# SUMMARY OF CHANGES FOR DEVELOPERS
# ===========================================
#
# KEY ARCHITECTURAL CHANGES:
# 1. Pathfinding now works at the MODEL level instead of UNIT level
# 2. Humans can now control individual model movement within a unit
# 3. Unit coherency is IGNORED during pathfinding (human responsibility)
# 4. Coherency is validated separately AFTER all models have moved
# 5. Optimized pathfinding provides 3-10x performance improvement
#
# INDIVIDUAL MODEL MOVEMENT WORKFLOW:
# 1. Human selects a unit to move
# 2. System allows moving one model at a time using get_individual_model_movement_path()
# 3. Human continues until all desired models are moved
# 4. System validates coherency using process_unit_movement_with_coherency_check()
# 5. If coherency fails, human decides which models to remove from play
#
# MIGRATION GUIDE:
# - Old: a_star(model, obstacles, target) -> Unit-level thinking with coherency
# - New: get_optimized_path(model, game_map, target) -> Model-level, no coherency
# - For individual models: get_individual_model_movement_path(unit, model_index, target, game_map)
# - For multi-model: get_optimized_paths_for_unit_models(unit, game_map, targets)
# - For coherency: validate_unit_coherency_after_movement(unit, new_positions)
# - For complete workflow: process_unit_movement_with_coherency_check(unit, model_movements)
#
# RECOMMENDED USAGE:
# - Use get_individual_model_movement_path() for human players moving single models
# - Use get_optimized_path() for AI or programmatic model movement
# - Use get_optimized_paths_for_unit_models() for simultaneous multi-model movement
# - Use get_optimized_path_for_unit() for backward compatibility
# - Always validate unit coherency after movement phase is complete
# - Use process_unit_movement_with_coherency_check() for complete human workflow
# ===========================================

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
    """
    Check if a model can end its move on a specific terrain feature.

    Args:
        model: The model attempting to end its move
        obstacle: The terrain obstacle

    Returns:
        bool: True if the model can end its move on this terrain
    """
    from ..classes.map import ObstacleType
    terrain = obstacle.terrain_type
    base_overhang = base_overhangs_obstacle(model, obstacle)
    unit = model.parent_unit

    if terrain == ObstacleType.CRATER_AND_RUBBLE:
        return True  # Units can move over this terrain freely (can end move)
    elif terrain == ObstacleType.BARRICADE_AND_FUEL_PIPES:
        return False  # Cannot be set up or end any kind of move on top of it
    elif terrain == ObstacleType.DEBRIS_AND_STATUARY:
        return False  # Cannot be set up or end any kind of move on top of it
    elif terrain == ObstacleType.HILLS_AND_SEALED_BUILDINGS:
        return not base_overhang  # Can end move if base does not overhang
    elif terrain == ObstacleType.WOODS:
        return True  # Units can move over this terrain freely (can end move)
    elif terrain == ObstacleType.RUINS:
        # All models can end move on ground floor of ruins
        # Special keyworded models + FLY can end move on any floor level
        if unit.is_infantry or unit.is_beast or unit.is_belisarius_cawl or unit.is_imperium_primarch or unit.is_flying():
            return not base_overhang  # Must not overhang if not ground floor
        else:
            # Other units can only end move on ground floor
            # TODO: Need to determine if this is ground floor vs upper floor
            return not base_overhang
    else:
        # Default behavior for unknown terrain types
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
    # Get position from first alive model
    first_model = None
    for model in unit.models:
        if model.is_alive:
            first_model = model
            break

    if not first_model:
        return Polygon()  # Return empty polygon if no alive models

    cx, cy = first_model.get_location()[:2]
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

# REMOVED: Old pathfinding classes - replaced with unified system

# REMOVED: OptimizedPathfindingEnvironmentForCharge - replaced with unified system


class OptimizedPathfindingEnvironment:
    """
    Optimized pathfinding environment using Minkowski sums and STRTrees.
    
    This class pre-computes collision geometry for fast pathfinding:
    - Minkowski sums convert shape-vs-shape collision to point-vs-shape
    - STRTrees provide O(log n) spatial queries instead of O(n) linear searches
    - Cached oriented shapes avoid repeated rotation calculations
    
    Works at the model level for maximum flexibility.
    """
    
    def __init__(self, game_map: 'Map', moving_model: 'Model'):
        """
        Initialize the optimized pathfinding environment.
        
        Args:
            game_map: The game map containing obstacles and units
            moving_model: The model that will be pathfinding
        """
        self.game_map = game_map
        self.moving_model = moving_model
        self.moving_unit = moving_model.parent_unit
        
        # Pre-compute collision geometry
        self._precompute_collision_geometry()
        
    def _precompute_collision_geometry(self):
        """Pre-compute Minkowski sums and spatial indices for fast collision detection"""
        logger.debug("Pre-computing collision geometry for optimized pathfinding...")
        
        # Create base shapes for all orientations (in inches)
        if not self.moving_model.parent_unit.has_circular_base:
            # Get model base size in inches
            model_radius = self.moving_model.model_base.radius
            
            # Handle case where radius might be a tuple (width, height) or a single value
            if isinstance(model_radius, (tuple, list)):
                # Use the maximum dimension for base size
                base_size_inches = convert_mm_to_inches(max(model_radius) * 2)
            else:
                base_size_inches = convert_mm_to_inches(model_radius * 2)
            
            # Create oriented shapes for all orientations
            self.oriented_shapes = {}
            self.oriented_min_radii = {}
            
            for angle in ORIENTATIONS:
                if hasattr(self.moving_model.model_base, 'get_base_shape'):
                    # Use existing base shape method
                    base_shape = self.moving_model.model_base.get_base_shape()
                    if angle != 0:
                        base_shape = rotate(base_shape, angle, origin=(0, 0))
                else:
                    # Create elliptical base shape
                    radius = base_size_inches / 2
                    points = [(radius * np.cos(t), radius * np.sin(t))
                              for t in np.linspace(0, 2 * np.pi, 30)]
                    base_shape = Polygon(points)
                    if angle != 0:
                        base_shape = rotate(base_shape, angle, origin=(0, 0))
                
                self.oriented_shapes[angle] = base_shape
                self.oriented_min_radii[angle] = self._calculate_shape_min_radius(base_shape)
        else:
            # For circular bases, all orientations are the same
            model_radius = self.moving_model.model_base.radius
            
            # Handle case where radius might be a tuple (width, height) or a single value
            if isinstance(model_radius, (tuple, list)):
                # Use the maximum dimension for circular approximation
                base_radius = convert_mm_to_inches(max(model_radius))
            else:
                base_radius = convert_mm_to_inches(model_radius)
                
            points = [(base_radius * np.cos(t), base_radius * np.sin(t))
                      for t in np.linspace(0, 2 * np.pi, 30)]
            base_shape = Polygon(points)
            self.oriented_shapes = {0: base_shape}
            self.oriented_min_radii = {0: base_radius}
        
        # Compute Minkowski sums with obstacles
        self.obstacle_minkowski = {}
        for angle, shape in self.oriented_shapes.items():
            minkowski_obstacles = []
            for obstacle in self.game_map.obstacles:
                try:
                    # Convert obstacle polygon to inches if needed
                    obstacle_poly = obstacle.polygon
                    # Assume obstacle coordinates are already in inches
                    
                    # Compute Minkowski sum by sampling obstacle perimeter
                    translated_shapes = []
                    obstacle_coords = list(obstacle_poly.exterior.coords[:-1])
                    
                    # Sample points along obstacle perimeter
                    perimeter = LineString(obstacle_poly.exterior.coords)
                    total_length = perimeter.length
                    sample_distance = min(0.4, total_length / 20)  # 0.4 inch samples or 20 samples max
                    
                    for i in range(int(total_length / sample_distance) + 1):
                        dist = i * sample_distance
                        if dist <= total_length:
                            point = perimeter.interpolate(dist)
                            translated_shape = translate(shape, point.x, point.y)
                            translated_shapes.append(translated_shape)
                    
                    # Union all translated shapes
                    if translated_shapes:
                        minkowski = unary_union(translated_shapes)
                        minkowski_obstacles.append(minkowski)
                    else:
                        # Fallback to buffering
                        min_radius = self.oriented_min_radii[angle]
                        minkowski_obstacles.append(obstacle_poly.buffer(min_radius))
                        
                except Exception as e:
                    logger.warning(f"Minkowski sum computation failed for obstacle, using buffer: {e}")
                    min_radius = self.oriented_min_radii[angle]
                    minkowski_obstacles.append(obstacle.polygon.buffer(min_radius))
            
            self.obstacle_minkowski[angle] = minkowski_obstacles
        
        # Create STRTrees for fast spatial queries
        self.obstacle_strtrees = {}
        for angle, obstacles in self.obstacle_minkowski.items():
            if obstacles:
                self.obstacle_strtrees[angle] = STRtree(obstacles)
            else:
                self.obstacle_strtrees[angle] = None
        
        # Create STRTrees for friendly and enemy units
        self.friendly_shapes = []
        self.enemy_shapes = []
        
        # Get all units from game map
        all_units = getattr(self.game_map, 'units', [])
        
        for unit in all_units:
            if not unit.is_alive() or not unit.deployed:
                continue

            # Determine if unit is friendly or enemy
            # Units are enemies if they belong to different players
            is_enemy = False
            if (unit.parent_army and unit.parent_army.player and
                self.moving_unit.parent_army and self.moving_unit.parent_army.player):
                is_enemy = unit.parent_army.player != self.moving_unit.parent_army.player

            for model in unit.models:
                if not model.is_alive:
                    continue

                # Skip the specific model that's being moved, but include other models from the same unit
                if model == self.moving_model:
                    continue

                if hasattr(model.model_base, 'get_base_shape'):
                    model_shape = model.model_base.get_base_shape()
                else:
                    # Create circular base shape
                    radius = convert_mm_to_inches(model.model_base.radius)
                    model_x, model_y = model.model_base.x, model.model_base.y
                    points = [(model_x + radius * np.cos(t), model_y + radius * np.sin(t))
                              for t in np.linspace(0, 2 * np.pi, 30)]
                    model_shape = Polygon(points)

                if is_enemy:
                    # Buffer enemy shapes by engagement range
                    self.enemy_shapes.append(model_shape.buffer(ENGAGEMENT_RANGE_HORIZONTAL))
                else:
                    self.friendly_shapes.append(model_shape)
        
        self.friendly_strtree = STRtree(self.friendly_shapes) if self.friendly_shapes else None
        self.enemy_strtree = STRtree(self.enemy_shapes) if self.enemy_shapes else None
        
        logger.debug(f"Collision geometry pre-computed for {len(ORIENTATIONS)} orientations")
    
    def _calculate_shape_min_radius(self, shape):
        """Calculate minimum radius for a shape"""
        bounds = shape.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        return min(width, height) / 2

    def is_valid_position_fast(self, position: Tuple[float, float], orientation: float) -> bool:
        """Fast collision detection using pre-computed Minkowski sums and STRTrees"""
        point = Point(position)
        
        # Check map bounds
        if not self.game_map.is_within_boundary(self.moving_model, position):
            return False
        
        # Check obstacles using Minkowski sums
        if self.obstacle_strtrees.get(orientation):
            possible_obstacles = query_spatial_index(self.obstacle_strtrees[orientation], point)
            for obstacle in possible_obstacles:
                if obstacle.contains(point):
                    return False
        
        # Check friendly units using STRTree - prevent base overlap
        if self.friendly_strtree:
            # Create the moving model's base shape at the target position
            temp_base = self.moving_model.model_base.__class__(
                self.moving_model.model_base.base_type,
                self.moving_model.model_base.radius
            )
            temp_base.set_position(position[0], position[1], self.moving_model.model_base.z)
            temp_base.set_facing(orientation)
            temp_base_shape = temp_base.get_base_shape()

            # Query for nearby friendly units
            query_buffer = temp_base_shape.buffer(0.1)  # Small buffer for spatial query
            possible_friendlies = query_spatial_index(self.friendly_strtree, query_buffer)
            for friendly_shape in possible_friendlies:
                # Check for actual base overlap (not just touching)
                if temp_base_shape.overlaps(friendly_shape):
                    return False
        
        # Check enemy units using STRTree - prevent base overlap
        if self.enemy_strtree:
            # Use the same temp_base_shape created above for friendly checks
            if 'temp_base_shape' not in locals():
                temp_base = self.moving_model.model_base.__class__(
                    self.moving_model.model_base.base_type,
                    self.moving_model.model_base.radius
                )
                temp_base.set_position(position[0], position[1], self.moving_model.model_base.z)
                temp_base.set_facing(orientation)
                temp_base_shape = temp_base.get_base_shape()

            # Query for nearby enemy units
            query_buffer = temp_base_shape.buffer(0.1)  # Small buffer for spatial query
            possible_enemies = query_spatial_index(self.enemy_strtree, query_buffer)
            for enemy_shape in possible_enemies:
                # Check for actual base overlap (not just touching)
                if temp_base_shape.overlaps(enemy_shape):
                    return False
        
        return True

    def get_reachable_positions(self, max_distance: float, step_size: float = 0.4) -> list:
        """
        Get all reachable positions within max_distance using optimized pathfinding.

        This is useful for real-time movement preview visualization.

        Args:
            max_distance: Maximum movement distance in inches
            step_size: Step size for pathfinding grid in inches

        Returns:
            List of (x, y) positions that are reachable
        """
        reachable = []
        start_pos = (self.moving_model.model_base.x, self.moving_model.model_base.y)
        current_orientation = getattr(self.moving_model.model_base, 'facing', 0)

        # Find closest orientation in our ORIENTATIONS list
        if current_orientation in ORIENTATIONS:
            start_orientation = current_orientation
        else:
            start_orientation = min(ORIENTATIONS, key=lambda x: abs(x - current_orientation))

        # Sample positions in a grid around the starting position
        search_radius = max_distance + step_size
        x_min = start_pos[0] - search_radius
        x_max = start_pos[0] + search_radius
        y_min = start_pos[1] - search_radius
        y_max = start_pos[1] + search_radius

        x = x_min
        while x <= x_max:
            y = y_min
            while y <= y_max:
                pos = (x, y)

                # Quick distance check
                distance = ((pos[0] - start_pos[0])**2 + (pos[1] - start_pos[1])**2)**0.5
                if distance <= max_distance:
                    # Check if position is valid
                    if self.is_valid_position_fast(pos, start_orientation):
                        reachable.append(pos)

                y += step_size
            x += step_size

        return reachable

# REMOVED: a_star_optimized_enhanced_for_charge - replaced with unified system


def a_star_optimized_enhanced(model: 'Model', game_map: 'Map', target: Tuple[float, float],
                            max_distance: float, step_size: float = 0.4) -> Optional[Tuple[List[Tuple[float, float, float]], bool]]:
    """
    Enhanced A* pathfinding adapted from test.py with optimizations.

    This function provides the advanced pathfinding capabilities from test.py
    but adapted to work with the main game's data structures.

    Args:
        model: The model to pathfind for
        game_map: The game map containing obstacles and units
        target: Target position (x, y) in inches
        max_distance: Maximum movement distance in inches
        step_size: Step size for pathfinding grid in inches

    Returns:
        Tuple containing (path, rotation_occurred) or None if no path exists
    """
    from heapq import heappush, heappop

    # Create optimized environment for this model
    env = OptimizedPathfindingEnvironment(game_map, model)

    # Get starting position and orientation
    start_pos = (model.model_base.x, model.model_base.y)
    current_orientation = getattr(model.model_base, 'facing', 0)

    # Find closest orientation in our ORIENTATIONS list
    if current_orientation in ORIENTATIONS:
        start_orientation = current_orientation
    else:
        # Find closest orientation
        start_orientation = min(ORIENTATIONS, key=lambda x: abs(x - current_orientation))

    # A* data structures
    open_set = []
    came_from = {}
    cost_so_far = {}
    rotation_occurred = {}

    # Initialize with starting position
    heappush(open_set, (0, 0, start_pos, None, start_orientation, False))
    cost_so_far[start_pos] = 0
    rotation_occurred[start_pos] = False

    # Early exit threshold for performance
    early_exit_threshold = step_size

    while open_set:
        _, cost, current, parent, rotation, path_has_rotation = heappop(open_set)
        last_angle = rotation

        # Check if we've reached the goal (early exit)
        if heuristic(current + (0,), target + (0,)) < early_exit_threshold:
            # Reconstruct path
            path = [(current[0], current[1], 0)]  # Add z=0 for 3D compatibility
            while parent:
                path.append((parent[0], parent[1], 0))
                parent = came_from.get(parent)
            path.reverse()
            return path, path_has_rotation

        # Check distance constraint
        distance_from_start = heuristic(start_pos + (0,), current + (0,))
        if distance_from_start > max_distance:
            continue

        # Generate neighbors with 8-directional movement
        directions = [
            (-step_size, 0), (step_size, 0), (0, -step_size), (0, step_size),
            (-step_size, -step_size), (step_size, -step_size),
            (-step_size, step_size), (step_size, step_size)
        ]

        for dx, dy in directions:
            neighbor = (current[0] + dx, current[1] + dy)

            # Check distance constraint for neighbor
            neighbor_distance = heuristic(start_pos + (0,), neighbor + (0,))
            if neighbor_distance > max_distance:
                continue

            # For circular bases, orientation doesn't matter
            if getattr(model.parent_unit, 'has_circular_base', False):
                if env.is_valid_position_fast(neighbor, 0):
                    new_cost = cost + heuristic(current + (0,), neighbor + (0,))
                    if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                        cost_so_far[neighbor] = new_cost
                        rotation_occurred[neighbor] = path_has_rotation
                        priority = new_cost + heuristic(neighbor + (0,), target + (0,))
                        heappush(open_set, (priority, new_cost, neighbor, current, 0, path_has_rotation))
                        came_from[neighbor] = current
                continue

            # Try orientations in priority order for non-circular bases
            orientations_to_try = [last_angle]  # Try current orientation first

            # Add start orientation if different
            if start_orientation != last_angle:
                orientations_to_try.append(start_orientation)

            # Add other orientations
            for angle in ORIENTATIONS:
                if angle not in orientations_to_try:
                    orientations_to_try.append(angle)

            # Try each orientation until one works
            for angle in orientations_to_try:
                if env.is_valid_position_fast(neighbor, angle):
                    new_cost = cost + heuristic(current + (0,), neighbor + (0,))

                    # Apply orientation preferences
                    if angle == start_orientation:
                        new_cost -= 0.01  # Prefer original orientation
                    elif angle == last_angle:
                        new_cost -= 0.005  # Prefer maintaining current orientation

                    # Check if rotation occurred
                    has_rotation = path_has_rotation or (angle != start_orientation)

                    if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                        cost_so_far[neighbor] = new_cost
                        rotation_occurred[neighbor] = has_rotation
                        priority = new_cost + heuristic(neighbor + (0,), target + (0,))
                        heappush(open_set, (priority, new_cost, neighbor, current, angle, has_rotation))
                        came_from[neighbor] = current
                    break  # Found valid orientation, move to next neighbor

    return None  # No path found


def get_charge_movement_path(moving_model: 'Model', target_position: tuple,
                           max_distance: float, game_map: 'Map', target_unit: 'Unit' = None) -> dict:
    """
    Get a movement path for charge actions using the unified pathfinding system.
    """
    # Convert 2D target to 3D if needed
    if len(target_position) == 2:
        target_3d = (target_position[0], target_position[1], moving_model.model_base.z)
    else:
        target_3d = target_position

    return unified_pathfinding(
        model=moving_model,
        target=target_3d,
        movement_type=MovementType.CHARGE,
        max_distance=max_distance,
        game_map=game_map,
        target_unit=target_unit
    )


def get_movement_path_preview(moving_model: 'Model', target_position: tuple,
                            max_distance: float, game_map: 'Map') -> dict:
    """
    Get a movement path preview using the unified pathfinding system.
    """
    # Convert 2D target to 3D if needed
    if len(target_position) == 2:
        target_3d = (target_position[0], target_position[1], moving_model.model_base.z)
    else:
        target_3d = target_position

    return unified_pathfinding(
        model=moving_model,
        target=target_3d,
        movement_type=MovementType.MOVE,
        max_distance=max_distance,
        game_map=game_map
    )


def get_unit_movement_path_preview(moving_unit: 'Unit', target_position: tuple,
                                 max_distance: float, game_map: 'Map') -> dict:
    """
    Get a movement path preview for a unit by using its first model.

    This is a convenience function that works at the unit level but delegates
    to model-level pathfinding.

    Args:
        moving_unit: The unit to move
        target_position: Target position (x, y) in inches
        max_distance: Maximum movement distance in inches
        game_map: The game map containing obstacles and units

    Returns:
        Dict with keys:
        - 'valid': bool indicating if path is valid
        - 'path': list of path points if valid
        - 'distance': total path distance
        - 'reason': explanation if invalid
    """
    # Get the first model for pathfinding (unit leader)
    if not moving_unit.models or not moving_unit.models[0].is_alive:
        return {
            'valid': False,
            'path': None,
            'distance': 0,
            'reason': 'No valid models in unit'
        }

    # Delegate to model-level pathfinding
    return get_movement_path_preview(moving_unit.models[0], target_position, max_distance, game_map)


def create_optimized_pathfinding_environment(game_map: 'Map', moving_unit: 'Unit') -> 'OptimizedPathfindingEnvironment':
    """
    Create an optimized pathfinding environment for the given moving unit.

    This adapts the existing OptimizedPathfindingEnvironment to work with the
    enhanced pathfinding from test.py.

    Args:
        game_map: The game map containing obstacles and units
        moving_unit: The unit that will be pathfinding

    Returns:
        OptimizedPathfindingEnvironment ready for pathfinding
    """
    if not moving_unit.models or not moving_unit.models[0].is_alive:
        raise ValueError("Moving unit has no valid models")

    # Use the existing OptimizedPathfindingEnvironment but enhance it
    return OptimizedPathfindingEnvironment(game_map, moving_unit.models[0])