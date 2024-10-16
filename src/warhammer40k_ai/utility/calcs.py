from math import sqrt, atan2
from typing import Tuple, List
import heapq
from ..utility.constants import MM_TO_INCHES, ENGAGEMENT_RANGE, FREELY_CLIMBABLE_RANGE

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..classes.map import Obstacle
    from ..classes.unit import Unit


# Convert mm (as in base size of models) to inches
def convert_mm_to_inches(value: float) -> float:
    return round(value / MM_TO_INCHES, 4)

# Determine the distance of a 3D position delta
def get_dist(x_delta: float, y_delta: float, z_delta: float = 0) -> float:
    return sqrt(x_delta**2 + y_delta**2 + z_delta**2)

# Determine the angle between to X,Y points
def get_angle(x_delta: float, y_delta: float) -> float:
    return atan2(x_delta, y_delta)

def lines_intersect(a1: Tuple[float, float], a2: Tuple[float, float], b1: Tuple[float, float], b2: Tuple[float, float]) -> bool:
    def ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> bool:
        return (C[1] - A[1]) * (B[0] - A[0]) - (B[1] - A[1]) * (C[0] - A[0])

    def on_segment(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> bool:
        return min(A[0], B[0]) <= C[0] <= max(A[0], B[0]) and \
               min(A[1], B[1]) <= C[1] <= max(A[1], B[1])

    ccw1 = ccw(a1, a2, b1)
    ccw2 = ccw(a1, a2, b2)
    ccw3 = ccw(b1, b2, a1)
    ccw4 = ccw(b1, b2, a2)

    if ccw1 == ccw2 == ccw3 == ccw4 == 0:
        # Lines are colinear
        return on_segment(a1, a2, b1) or on_segment(a1, a2, b2) or \
               on_segment(b1, b2, a1) or on_segment(b1, b2, a2)
    else:
        return (ccw1 * ccw2 <= 0) and (ccw3 * ccw4 <= 0)

def line_intersects_polygon(line_start: Tuple[float, float], line_end: Tuple[float, float], polygon_vertices: List[Tuple[float, float]]) -> bool:
    """
    Determines if a line segment intersects with any edge of a polygon.

    Parameters:
    - line_start: Tuple (x, y) representing the starting point of the line segment.
    - line_end: Tuple (x, y) representing the ending point of the line segment.
    - polygon_vertices: List of tuples [(x1, y1), (x2, y2), ...] representing the vertices of the polygon in order.

    Returns:
    - True if the line intersects any edge of the polygon.
    - False if the line does not intersect the polygon.
    """
    num_vertices = len(polygon_vertices)
    for i in range(num_vertices):
        # Get the current edge of the polygon
        vertex_a = polygon_vertices[i]
        vertex_b = polygon_vertices[(i + 1) % num_vertices]  # Wrap around to the first vertex

        # Check if the line segment intersects with the edge
        if lines_intersect(line_start, line_end, vertex_a, vertex_b):
            return True  # Intersection found
    return False  # No intersection with any edge

def can_traverse_freely(unit: 'Unit', obstacle: 'Obstacle') -> bool:
    # Check if the unit can ignore the obstacle based on abilities
    if 'Fly' in unit.abilities:
        return True  # Units with Fly can move over obstacles
    # Additional checks based on terrain type and unit abilities
    if obstacle.height > FREELY_CLIMBABLE_RANGE:
        return False
    if obstacle.terrain_type.name == 'RUINS' and (unit.is_infantry or unit.is_beast or unit.is_belisarius_cawl or unit.is_imperium_primarch):
        return True  # Infantry, beasts, Belisarius Cawl and Imperium Primarch can traverse into ruins
    # Add more rules as needed
    return False

def line_of_sight(unit: 'Unit', point_a: Tuple[float, float], point_b: Tuple[float, float], obstacles: List[Tuple[float, float]]) -> bool:
    for obstacle in obstacles:
        if not can_traverse_freely(unit, obstacle):
            if line_intersects_polygon(point_a, point_b, obstacle.vertices):
                return False  # Line is obstructed
    return True  # Line is clear

def get_movement_cost(unit: 'Unit', point_a: Tuple[float, float], point_b: Tuple[float, float], obstacles: List[Tuple[float, float]]) -> float:
    # Base cost is the Euclidean distance
    base_cost = get_dist(point_a[0] - point_b[0], point_a[1] - point_b[1])
    
    # Check for terrain effects
    for obstacle in obstacles:
        if line_intersects_polygon(point_a, point_b, obstacle.vertices):
            if not can_traverse_freely(unit, obstacle):
                # Increase movement cost
                base_cost += obstacle.height
                if obstacle.height > (unit.movement + 6.0):  # Best movement is "advance with 6 roll on die"
                    return float('inf')  # Cannot traverse
    return base_cost

def build_visibility_graph(unit: 'Unit', start: Tuple[float, float], goal: Tuple[float, float], obstacles: List[Tuple[float, float]]):
    nodes = [start, goal]
    for obstacle in obstacles:
        nodes.extend(obstacle.vertices)
    
    edges = []
    for i, node_a in enumerate(nodes):
        for node_b in nodes[i+1:]:
            if line_of_sight(unit, node_a, node_b, obstacles):
                distance = get_movement_cost(unit, node_a, node_b, obstacles)
                if distance != float('inf'):
                    edges.append((node_a, node_b, distance))
                    edges.append((node_b, node_a, distance))
    return nodes, edges

# A* pathfinding algorithm
def astar_visibility_graph(start: Tuple[float, float], goal: Tuple[float, float], nodes: List[Tuple[float, float]], edges: List[Tuple[Tuple[float, float], Tuple[float, float], float]]):
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
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                priority = new_cost + get_dist(neighbor[0] - goal[0], neighbor[1] - goal[1])
                heapq.heappush(open_set, (priority, neighbor))
                came_from[neighbor] = current
    return None  # No path found