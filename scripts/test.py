import asyncio
import platform
import numpy as np
import pygame
import numpy as np
from shapely.strtree import STRtree
from shapely.geometry import Polygon, box, Point
from shapely.affinity import rotate, translate
from shapely.ops import unary_union
from heapq import heappush, heappop

# Constants
INCH_TO_MM = 25.4
MAP_WIDTH = 60 * INCH_TO_MM  # 60 inches
MAP_HEIGHT = 44 * INCH_TO_MM  # 44 inches
COHERENCY_DISTANCE = 2 * INCH_TO_MM  # 2 inches
ENEMY_DISTANCE = 1 * INCH_TO_MM  # 1 inch
ROTATION_PENALTY = 1 * INCH_TO_MM  # 1 inch
MODEL_SIZE = (60, 35)  # Ellipse: 60mm x 35mm

# Removed global variable - using parameter passing instead

class Model:
    def __init__(self, center, shape_type="ellipse", size=MODEL_SIZE, orientation=0):
        self.shape_type = shape_type
        self.size = size
        self.orientation = orientation  # degrees
        self.shape = self._create_shape(center)

    def _create_shape(self, center):
        if self.shape_type == "ellipse":
            # Approximate ellipse with a polygon
            # Convert from diameter to radius
            radius_x = self.size[0] / 2
            radius_y = self.size[1] / 2
            points = [(center[0] + radius_x * np.cos(t), center[1] + radius_y * np.sin(t))
                     for t in np.linspace(0, 2 * np.pi, 20)]
            shape = Polygon(points)
        else:  # hull
            w, h = self.size
            shape = box(center[0] - w/2, center[1] - h/2, center[0] + w/2, center[1] + h/2)
        if self.orientation != 0:
            shape = rotate(shape, self.orientation, origin=center)
        return shape

    def move(self, new_center):
        self.shape = translate(self._create_shape(new_center), xoff=-self.shape.centroid.x + new_center[0],
                              yoff=-self.shape.centroid.y + new_center[1])

    def rotate(self, angle):
        self.orientation += angle
        center = (self.shape.centroid.x, self.shape.centroid.y)
        self.shape = rotate(self._create_shape(center), angle, origin=center)

class Unit:
    def __init__(self, models, can_move_through_obstacles=False):
        self.models = models
        self.can_move_through_obstacles = can_move_through_obstacles

    def is_coherent(self):
        if len(self.models) == 1:
            return True
        for i, model in enumerate(self.models):
            neighbors = 0
            for j, other in enumerate(self.models):
                if i != j and model.shape.distance(other.shape) <= COHERENCY_DISTANCE:
                    neighbors += 1
            required_neighbors = 2 if len(self.models) >= 6 else 1
            if neighbors < required_neighbors:
                return False
        return True

class Environment:
    def __init__(self, map_bounds, obstacles, friendly_units, enemy_units):
        self.map = map_bounds
        self.obstacles = obstacles
        self.friendly_units = friendly_units
        self.enemy_units = enemy_units

    def is_valid_position(self, model, unit, is_charge=False):
        # Check map bounds
        if not self.map.contains(model.shape):
            return False
        # Check overlaps with other models
        for f_unit in self.friendly_units:
            if f_unit != unit:
                for f_model in f_unit.models:
                    if model.shape.intersects(f_model.shape):
                        return False
        # Check enemy distance
        for e_unit in self.enemy_units:
            for e_model in e_unit.models:
                dist = model.shape.distance(e_model.shape)
                if is_charge and dist >= ENEMY_DISTANCE:
                    return False
                elif not is_charge and dist < ENEMY_DISTANCE:
                    return False
        # Check obstacles
        if not unit.can_move_through_obstacles:
            for obstacle in self.obstacles:
                if model.shape.intersects(obstacle):
                    return False
        return True

# Constants for the pathfinding
GRID_STEP = 10  # grid step in mm for pathfinding resolution
ORIENTATIONS = [0, 5, 15, 30, 45]  # degrees for rotational clearance consideration

# Preprocessing for obstacles

def create_model_shape(center, size, orientation):
    radius_x = size[0] / 2
    radius_y = size[1] / 2
    points = [(center[0] + radius_x * np.cos(t), center[1] + radius_y * np.sin(t))
              for t in np.linspace(0, 2 * np.pi, 20)]
    shape = Polygon(points)
    if orientation != 0:
        shape = rotate(shape, orientation, origin=center)
    return shape

def minkowski_sum(obstacle: Polygon, model_shape: Polygon):
    translated = [translate(obstacle, xoff=pt[0], yoff=pt[1]) for pt in model_shape.exterior.coords]
    return unary_union(translated)

def create_expanded_obstacles(obstacles, model_size):
    all_rotated_sums = []
    for angle in ORIENTATIONS:
        model_shape = create_model_shape((0, 0), model_size, angle)
        for obstacle in obstacles:
            expanded = minkowski_sum(obstacle, model_shape)
            all_rotated_sums.append(expanded)
    return all_rotated_sums

# Spatial indexing with STRtree

def create_spatial_index(expanded_obstacles):
    return STRtree(expanded_obstacles), expanded_obstacles

# Efficient collision check using spatial indexing

def is_collision(point, spatial_index, geometry_list):
    candidate_indices = spatial_index.query(point)
    candidate_polygons = [geometry_list[idx] for idx in candidate_indices]
    return any(poly.contains(point) for poly in candidate_polygons)

# A* Pathfinding

def heuristic(a, b):
    return np.hypot(b[0] - a[0], b[1] - a[1])

def a_star(start, goal, spatial_index, geometry_list, map_bounds):
    open_set = []
    heappush(open_set, (heuristic(start, goal), 0, start, None))

    came_from = {}
    cost_so_far = {start: 0}

    directions = [(-GRID_STEP, 0), (GRID_STEP, 0), (0, -GRID_STEP), (0, GRID_STEP),
                  (-GRID_STEP, -GRID_STEP), (-GRID_STEP, GRID_STEP), (GRID_STEP, -GRID_STEP), (GRID_STEP, GRID_STEP)]

    while open_set:
        _, cost, current, _ = heappop(open_set)

        if heuristic(current, goal) < GRID_STEP:
            path = [goal]
            while current:
                path.append(current)
                current = came_from.get(current)
            return path[::-1]

        for dx, dy in directions:
            neighbor = (current[0] + dx, current[1] + dy)
            point = Point(neighbor)

            if not map_bounds.contains(point):
                continue

            if is_collision(point, spatial_index, geometry_list):
                continue

            new_cost = cost + heuristic(current, neighbor)

            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                priority = new_cost + heuristic(goal, neighbor)
                heappush(open_set, (priority, new_cost, neighbor, current))
                came_from[neighbor] = current

    return None  # no path found

# Example usage within provided Environment setup

def a_star_pathfinding(unit, target_pos, environment, max_distance):
    start_pos = (unit.models[0].shape.centroid.x, unit.models[0].shape.centroid.y)

    expanded_obstacles = create_expanded_obstacles(environment.obstacles, unit.models[0].size)
    spatial_index, geometry_list = create_spatial_index(expanded_obstacles)

    raw_path = a_star(start_pos, target_pos, spatial_index, geometry_list, environment.map)

    if raw_path is None:
        print("No valid path found.")
        return None

    # Segment path according to max_distance allowed
    path = []
    distance_used = 0
    segment = []
    previous = start_pos
    turn_number = 1

    for point in raw_path:
        step_distance = heuristic(previous, point)
        if distance_used + step_distance > max_distance:
            path.append((segment, [0]*len(segment), distance_used, turn_number))
            segment = [point]
            distance_used = step_distance
            turn_number += 1
        else:
            segment.append(point)
            distance_used += step_distance
        previous = point

    if segment:
        path.append((segment, [0]*len(segment), distance_used, turn_number))

    return path

# Pygame Visualization
FPS = 60
async def main():
    pygame.init()
    scale = 0.5  # Scale for visualization
    screen = pygame.display.set_mode((int(MAP_WIDTH * scale), int(MAP_HEIGHT * scale)))
    clock = pygame.time.Clock()

    # Create test environment
    map_bounds = box(0, 0, MAP_WIDTH, MAP_HEIGHT)
    obstacles = [
        Polygon([(400, 400), (800, 400), (550, 1600)]),  # Triangle
        box(800, 200, 900, 400),  # Rectangle
        Polygon([(1000, 700), (1400, 700), (1050, 900), (1200, 700)]),  # Irregular
    ]

    # single model
    friendly_unit = Unit([
        Model((100, 100), "ellipse", MODEL_SIZE),
    ])
    enemy_units = [
        Unit([Model((800, 800), "ellipse", MODEL_SIZE)]),
        Unit([Model((1000, 200), "ellipse", MODEL_SIZE)]),
    ]
    environment = Environment(map_bounds, obstacles, [friendly_unit], enemy_units)

    # Calculate path
    target_pos = (1200, 900)  # Original far target - multi-turn pathfinding should handle this
    start_pos = (friendly_unit.models[0].shape.centroid.x, friendly_unit.models[0].shape.centroid.y)
    distance_to_target = ((target_pos[0] - start_pos[0])**2 + (target_pos[1] - start_pos[1])**2)**0.5
    max_distance = 1200 * INCH_TO_MM
    
    print(f"Starting pathfinding")
    print(f"Start position: {start_pos}")
    print(f"Target position: {target_pos}")
    print(f"Distance to target: {distance_to_target:.1f}mm")
    print(f"Max movement distance: {max_distance:.1f}mm")
    print(f"Target reachable in one move: {distance_to_target <= max_distance}")
    print(f"Enemy unit positions:")
    for i, e_unit in enumerate(enemy_units):
        for j, e_model in enumerate(e_unit.models):
            enemy_pos = (e_model.shape.centroid.x, e_model.shape.centroid.y)
            print(f"  Enemy {i+1}-{j+1}: {enemy_pos}")
    print(f"Enemy distance constraint: {ENEMY_DISTANCE:.1f}mm")
    
    # Check if starting position is valid
    start_valid = all(environment.is_valid_position(model, friendly_unit) for model in friendly_unit.models)
    print(f"Starting position valid: {start_valid}")
    
    # Check if target area is clear (create a test model at target)
    test_model = Model(target_pos, "ellipse", MODEL_SIZE)
    target_valid = environment.is_valid_position(test_model, friendly_unit)
    print(f"Target position valid: {target_valid}")
    
    path = a_star_pathfinding(friendly_unit, target_pos, environment, max_distance)
    print("Pathfinding complete")
    print(f"Path found: {path is not None}")
    if path:
        print(f"Path length: {len(path)}")
    else:
        print("No path found!")

    running = True
    path_index = 0
    animation_counter = 0
    animation_delay = 30  # frames before moving to next path step
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((255, 255, 255))  # White background

        # Draw map
        pygame.draw.rect(screen, (0, 0, 0), (0, 0, MAP_WIDTH * scale, MAP_HEIGHT * scale), 2)

        # Draw obstacles
        for obstacle in obstacles:
            points = [(x * scale, y * scale) for x, y in obstacle.exterior.coords]
            pygame.draw.polygon(screen, (100, 100, 100), points)

        # Draw enemy units
        for unit in enemy_units:
            for model in unit.models:
                points = [(x * scale, y * scale) for x, y in model.shape.exterior.coords]
                pygame.draw.polygon(screen, (255, 0, 0), points)

        # Draw path trace
        if path:
            for step_idx, (positions, rotations, distance_used, turn_number) in enumerate(path):
                for i, pos in enumerate(positions):
                    # Use different colors for different turns
                    colors = [(200, 200, 200), (150, 150, 255), (255, 150, 150), (150, 255, 150), (255, 255, 150)]
                    color = colors[turn_number % len(colors)]
                    # Draw small circles to show path
                    pygame.draw.circle(screen, color, (int(pos[0] * scale), int(pos[1] * scale)), 3)
                    if step_idx < len(path) - 1:
                        # Draw line to next position
                        next_pos = path[step_idx + 1][0][i]
                        pygame.draw.line(screen, color, 
                                       (int(pos[0] * scale), int(pos[1] * scale)),
                                       (int(next_pos[0] * scale), int(next_pos[1] * scale)), 2)

        # Draw path
        if path and path_index < len(path):
            positions, rotations, distance_used, turn_number = path[path_index]
            for i, (pos, rot) in enumerate(zip(positions, rotations)):
                ref_model = friendly_unit.models[0]
                model = Model(pos, ref_model.shape_type, ref_model.size, rot)
                points = [(x * scale, y * scale) for x, y in model.shape.exterior.coords]
                pygame.draw.polygon(screen, (0, 255, 0), points)
            
            # Update animation
            animation_counter += 1
            if animation_counter >= animation_delay:
                animation_counter = 0
                if path_index < len(path) - 1:
                    path_index += 1
                    print(f"Path step {path_index}/{len(path)}, Turn {turn_number}, Distance used: {distance_used:.1f}mm")
        else:
            for model in friendly_unit.models:
                points = [(x * scale, y * scale) for x, y in model.shape.exterior.coords]
                pygame.draw.polygon(screen, (0, 255, 0), points)

        # Draw target
        pygame.draw.circle(screen, (0, 0, 255), (target_pos[0] * scale, target_pos[1] * scale), 5)

        pygame.display.flip()
        clock.tick(FPS)
        await asyncio.sleep(1.0 / FPS)

    pygame.quit()

if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        asyncio.run(main())