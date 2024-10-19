from enum import Enum, auto
from typing import List, Tuple
import matplotlib.pyplot as plt
from shapely.affinity import translate, scale
from shapely.geometry import Point, Polygon, LineString
from math import atan2, cos, sin, pi, sqrt
import heapq


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

# Determine the distance of a 3D position delta
def get_dist(x_delta: float, y_delta: float, z_delta: float = 0) -> float:
    return sqrt(x_delta**2 + y_delta**2 + z_delta**2)

# Determine the angle between two X,Y points
def get_angle(x_delta: float, y_delta: float) -> float:
    return atan2(x_delta, y_delta)

def plot_geometry(ax, geom, **kwargs):
    """Helper function to plot Shapely geometries."""
    if isinstance(geom, Obstacle):
        # For custom Obstacle objects
        x, y = geom.polygon.exterior.xy
    elif isinstance(geom, (Polygon, Point)):
        # For Polygon and Point objects
        x, y = geom.exterior.xy
    else:
        # For other geometries
        x, y = geom.xy
    ax.fill(x, y, **kwargs)

def heuristic(a, b):
    """Calculate the heuristic (estimated distance) between two points."""
    return get_dist(a[0] - b[0], a[1] - b[1])

def distance_to_nearest_obstacle(point, obstacles, target):
    return min(obstacle.polygon.distance(Point(point)) for obstacle in obstacles)

def adaptive_step_size(point, obstacles, target, min_step=0.1, max_step=6.0, safety_factor=0.5):
    dist = distance_to_nearest_obstacle(point, obstacles, target)
    return max(min_step, min(max_step, dist * safety_factor))

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

def a_star(start, obstacles, ellipse, target, max_iterations=50000):
    """A* pathfinding algorithm with adaptive step size and iteration limit."""
    start = (start.x, start.y)
    goal = (target.centroid.x, target.centroid.y)
    
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}
    
    iterations = 0
    while open_set and iterations < max_iterations:
        current = heapq.heappop(open_set)[1]
        
        current_ellipse = translate(ellipse, current[0] - ellipse.centroid.x, current[1] - ellipse.centroid.y)
        if current_ellipse.intersects(target) or heuristic(current, goal) < 0.1:  # Changed goal condition
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

if __name__ == "__main__":
    # Define the agent's shape as an ellipse
    unit_circle = Point(0, 0).buffer(1, resolution=64)
    a, b = 0.5, 0.4  # semi-major and semi-minor axis lengths
    ellipse = scale(unit_circle, a, b)
    starting_ellipse = ellipse

    # Define the target
    target = Point(10, 10).buffer(1, resolution=64)

    # Define obstacles
    obstacles_1 = Obstacle([(5, 5), (1, 1)], ObstacleType.CRATER_AND_RUBBLE, 0.5)
    obstacles_2 = Obstacle([(6, 4), (7, 4), (7, 3), (6, 3)], ObstacleType.RUINS, 0.5)
    obstacles_3 = Obstacle([(2, 7), (3, 8), (4, 7), (3, 6)], ObstacleType.WOODS, 0.5)
    obstacles = [obstacles_1, obstacles_2, obstacles_3]

    # Visualization setup
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_aspect('equal')
    ax.set_xlim(-2, 12)
    ax.set_ylim(-2, 12)
    ax.set_title('Object Path Visualization')

    # Plot obstacles
    for obstacle in obstacles:
        plot_geometry(ax, obstacle, color=obstacle.color, alpha=0.5, label='Obstacle')

    # Plot target
    plot_geometry(ax, target, color='green', alpha=0.5, label='Target')

    # Find the shortest path using A* with adaptive step size
    start_point = Point(starting_ellipse.centroid.x, starting_ellipse.centroid.y)
    goal_point = Point(target.centroid.x, target.centroid.y)
    print("Starting A* pathfinding...")
    shortest_path = a_star(start_point, obstacles, starting_ellipse, target)

    if shortest_path:
        # Simplify the path with the new collision-aware function
        simplified_path = simplify_path(shortest_path, obstacles, starting_ellipse)
        
        # Plot the original shortest path
        path_x, path_y = zip(*shortest_path)
        ax.plot(path_x, path_y, color='green', linewidth=2, alpha=0.5, label='Original A* Path')

        # Calculate the distance of the original path
        path_distance = sum(get_dist(shortest_path[i][0] - shortest_path[i-1][0], shortest_path[i][1] - shortest_path[i-1][1]) for i in range(1, len(shortest_path)))

        # Plot the simplified path
        simplified_x, simplified_y = zip(*simplified_path)
        ax.plot(simplified_x, simplified_y, color='blue', linewidth=2, label='Simplified Path')

        # Calculate and print the distance of the simplified path
        simplified_distance = sum(get_dist(simplified_path[i][0] - simplified_path[i-1][0], simplified_path[i][1] - simplified_path[i-1][1]) for i in range(1, len(simplified_path)))
        print(f"Original path: {len(shortest_path)} points, distance: {path_distance:.2f}")
        print(f"Simplified path: {len(simplified_path)} points, distance: {simplified_distance:.2f}")

        # Move the ellipse along the simplified path
        path_ellipses = []
        total_distance = 0
        collision_steps = []

        for i, point in enumerate(simplified_path):
            new_ellipse = translate(starting_ellipse, point[0] - starting_ellipse.centroid.x, point[1] - starting_ellipse.centroid.y)
            
            # Check for collisions
            collision = any(new_ellipse.intersects(obs.polygon) for obs in obstacles)
            if collision:
                collision_steps.append(i)
                print(f"Collision detected at step {i}")
                break

            path_ellipses.append(new_ellipse)

            if i > 0:
                distance_moved = get_dist(point[0] - simplified_path[i-1][0], point[1] - simplified_path[i-1][1])
                total_distance += distance_moved

            if new_ellipse.intersects(target):
                print(f"Reached target at step {i}")
                break

        # Plot the ellipse path
        for step, ellipse in enumerate(path_ellipses):
            alpha = 0.1 if step < len(path_ellipses) - 1 else 0.7
            plot_geometry(ax, ellipse, color='blue', alpha=alpha, edgecolor='none')

        # Connect centroids with a line to show the ellipse path
        ellipse_path_x = [e.centroid.x for e in path_ellipses]
        ellipse_path_y = [e.centroid.y for e in path_ellipses]
        ax.plot(ellipse_path_x, ellipse_path_y, color='blue', linewidth=2, linestyle='--', label='Ellipse Path')

        # Mark collision points, if any
        for step in collision_steps:
            ax.plot(ellipse_path_x[step], ellipse_path_y[step], marker='x', color='black', markersize=10, label='Collision')

        print(f"Total distance of the ellipse path: {total_distance:.2f}")
        print(f"Final ellipse position: ({path_ellipses[-1].centroid.x:.2f}, {path_ellipses[-1].centroid.y:.2f})")

    else:
        print("No path found")

    plt.legend()
    plt.grid(True)
    plt.show()
