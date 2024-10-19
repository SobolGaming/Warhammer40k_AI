from math import sqrt, atan2, pi, cos, sin
from typing import Tuple, List
import heapq
from ..utility.constants import MM_TO_INCHES, FREELY_CLIMBABLE_RANGE
from shapely.geometry import LineString, Point
from shapely.affinity import translate

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..classes.map import Obstacle, ObstacleType
    from ..classes.unit import Unit
    from ..classes.model import Model
    from ..classes.map import Map


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
    # Check if the unit can ignore the obstacle based on abilities
    if unit.is_fly:
        return True  # Units with Fly can move over obstacles
    # Additional checks based on terrain type and unit abilities
    if obstacle.height <= FREELY_CLIMBABLE_RANGE:
        return True
    if obstacle.terrain_type.name == 'RUINS' and (unit.is_infantry or unit.is_beast or unit.is_belisarius_cawl or unit.is_imperium_primarch):
        return True  # Infantry, beasts, Belisarius Cawl and Imperium Primarch can traverse into ruins
    # Add more rules as needed
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
    print(f"A: {point_a}, B: {point_b}")
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
    if model.parent_unit.is_fly:
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
    return get_dist(a[0] - b[0], a[1] - b[1])

def distance_to_nearest_obstacle(point, obstacles, target):
    return min(obstacle.polygon.distance(Point(point)) for obstacle in obstacles)

def adaptive_step_size(point, obstacles, target, min_step=0.1, max_step=6.0, safety_factor=0.5):
    dist = distance_to_nearest_obstacle(point, obstacles, target)
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
                    print(f"Collision avoided at step {step}")
                    return alt_obj, False  # Return the alternative movement

            # If no alternative direction works, stay in place
            print(f"Collision at step {step}, no alternative path found")
            return obj, True  # Return the original object and collision flag

    return new_obj, False

def get_neighbors(current, obstacles, ellipse, goal):
    """Get valid neighboring points with adaptive step size and direct path to goal."""
    x, y = current
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
            valid_neighbors.append(n)
    return valid_neighbors

def a_star(model: 'Model', obstacles, target, max_iterations=50000):
    """A* pathfinding algorithm with adaptive step size and iteration limit."""
    start = (model.model_base.x, model.model_base.y)
    goal = target[:2]
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
            print(f"Path found after {iterations} iterations")
            return path[::-1] + [goal]  # Add the exact goal point to the end of the path
        
        for neighbor in get_neighbors(current, obstacles, current_ellipse, goal):
            tentative_g_score = g_score[current] + heuristic(current, neighbor)
            
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = g_score[neighbor] + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        iterations += 1
    
    print(f"No path found after {iterations} iterations")
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
    return not obstacle.polygon.contains(base_shape)