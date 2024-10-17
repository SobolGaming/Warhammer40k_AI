from math import sqrt, atan2, pi, cos, sin
from typing import Tuple, List
import heapq
from ..utility.constants import MM_TO_INCHES, FREELY_CLIMBABLE_RANGE
from shapely.geometry import LineString, Point
import itertools

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..classes.map import Obstacle
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

def line_of_sight(model: 'Model', point_a: Tuple[float, float, float], point_b: Tuple[float, float, float], obstacles: List['Obstacle']) -> bool:
    base_radius = model.base_size
    movement_corridor = LineString([(point_a[0], point_a[1]), (point_b[0], point_b[1])]).buffer(base_radius)

    for obstacle in obstacles:
        if movement_corridor.intersects(obstacle.polygon):
            # Check if the unit can traverse over the obstacle
            if not can_traverse_freely(model.parent_unit, obstacle):
                return False  # Movement path is obstructed

    # Check for collisions with enemy models
    #for other_model in other_models:
    #    if movement_corridor.intersects(other_model.get_base_shape()):
    #        return False
    return True  # Path is clear

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

def build_visibility_graph(model: 'Model', start: Tuple[float, float, float], goal: Tuple[float, float, float], obstacles: List['Obstacle']):
    nodes = [start, goal]

    # List of obstacles the unit cannot traverse freely
    obstacles_to_consider = []
    for obstacle in obstacles:
        if not can_traverse_freely(model.parent_unit, obstacle):
            obstacles_to_consider.append(obstacle)

    # Add vertices of obstacles to nodes to improve pathfinding around obstacles
    for obstacle in obstacles_to_consider:
        nodes.extend(list(obstacle.polygon.exterior.coords)[:-1])  # Exclude duplicate starting point

    edges = []
    for i, node_a in enumerate(nodes):
        for node_b in nodes[i+1:]:
            if line_of_sight(model, node_a, node_b, obstacles_to_consider):
                distance = get_movement_cost(model, node_a, node_b, obstacles)
                edges.append((node_a, node_b, distance))
                edges.append((node_b, node_a, distance))
    return nodes, edges

# A* pathfinding algorithm
def astar_visibility_graph(start: Tuple[float, float, float], goal: Tuple[float, float, float], nodes: List[Tuple[float, float, float]], edges: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], float]], max_movement_range: float):
    graph = {node: [] for node in nodes}
    for edge in edges:
        node_a, node_b, cost = edge
        graph[node_a].append((node_b, cost))
    
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    cost_so_far = {start: 0}
    
    while open_set:
        _, current = heapq.heappop(open_set)
        
        if current == goal:
            # Reconstruct path
            path = []
            while current != start:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path
        
        for neighbor, cost in graph[current]:
            new_cost = cost_so_far[current] + cost
            if new_cost > max_movement_range:
                continue  # Skip paths that exceed movement range
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                priority = new_cost + get_dist(neighbor[0] - goal[0], neighbor[1] - goal[1])
                heapq.heappush(open_set, (priority, neighbor))
                came_from[neighbor] = current
    return None  # No path found within movement range

def generate_coherency_positions(model: 'Model', moved_positions: List[Tuple[float, float, float]], coherency_distance: float, game_map: 'Map', required_neighbors: int) -> List[Tuple[float, float, float]]:
    potential_positions = []
    # Generate positions around combinations of moved models
    if len(moved_positions) >= required_neighbors:
        # Generate positions that are within coherency distance of required_neighbors models
        for combination in itertools.combinations(moved_positions, required_neighbors):
            # Calculate average position
            avg_x = sum(pos[0] for pos in combination) / required_neighbors
            avg_y = sum(pos[1] for pos in combination) / required_neighbors
            avg_z = sum(pos[2] for pos in combination) / required_neighbors
            # Generate positions around the average point
            num_points = 8
            for i in range(num_points):
                angle = 2 * pi * i / num_points
                x = avg_x + coherency_distance * cos(angle)
                y = avg_y + coherency_distance * sin(angle)
                z = avg_z  # Adjust if necessary

                # Collision checking as before
                model_base = Point(x, y).buffer(model.base_size)
                collision = False

                # Check if position is within battlefield boundaries
                if not game_map.is_within_boundary(model_base):
                    continue  # Skip positions outside the battlefield

                for obstacle in game_map.obstacles:
                    if model_base.intersects(obstacle.polygon):
                        collision = True
                        break
                for other_model in game_map.get_all_models():
                    if other_model != model and model_base.intersects(other_model.model_base.get_base_shape()):
                        collision = True
                        break
                if collision:
                    continue  # Skip positions that collide

                potential_positions.append((x, y, z))
    else:
        # Not enough moved models to satisfy required_neighbors
        # Fallback to positions around existing models
        return generate_coherency_positions(model, moved_positions, coherency_distance, game_map, required_neighbors=1)

    # Sort positions by proximity to the destination
    potential_positions.sort(key=lambda p: get_dist(p[0] - model.model_base.x, p[1] - model.model_base.y))
    return potential_positions