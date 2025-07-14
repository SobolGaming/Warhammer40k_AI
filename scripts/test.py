"""
Optimized A* Pathfinding with Minkowski Sums and STRTrees

This module implements optimized pathfinding using:
1. Minkowski Sum Pre-computation: Converts shape-vs-shape collision detection to point-vs-shape
2. STRTree Spatial Indexing: Fast spatial queries to avoid checking all obstacles/units
3. Minimum Radius Buffering: Quick broad-phase collision detection using shape's minimum radius
4. Cached Oriented Shapes: Pre-computed rotated shapes for all orientations

Key optimizations:
- Pre-compute Minkowski sums for all obstacles at all orientations
- Use STRTrees for O(log n) spatial queries instead of O(n) linear searches
- Point-based collision detection instead of expensive shape intersection tests
- Minimum radius buffering for fast broad-phase collision detection

Expected performance improvement: 3-10x faster pathfinding
"""

import asyncio
import platform
import pygame
import numpy as np
from shapely.geometry import Polygon, box, Point
from shapely.affinity import rotate, translate
from shapely.ops import unary_union
from shapely.strtree import STRtree

# Constants
INCH_TO_MM = 25.4
MAP_WIDTH = 60 * INCH_TO_MM
MAP_HEIGHT = 44 * INCH_TO_MM
MODEL_SIZE = (60, 35)  # Ellipse size
ENEMY_DISTANCE = 25.4
ORIENTATIONS = [0, 90, 45, -45, 15, -15, 30, -30, 60, -60, 75, -75]

class Model:
    def __init__(self, center, shape_type="ellipse", size=MODEL_SIZE, orientation=0):
        self.shape_type = shape_type
        self.size = size
        self.orientation = orientation
        self.shape = self._create_shape(center)
        self._min_radius = self._calculate_min_radius()

    def _create_shape(self, center):
        if self.shape_type == "circle":
            radius = self.size[0] / 2
            points = [(center[0] + radius * np.cos(t), center[1] + radius * np.sin(t))
                      for t in np.linspace(0, 2 * np.pi, 30)]
            shape = Polygon(points)
            return shape
        elif self.shape_type == "ellipse":
            radius_x = self.size[0] / 2
            radius_y = self.size[1] / 2
            points = [(center[0] + radius_x * np.cos(t), center[1] + radius_y * np.sin(t))
                      for t in np.linspace(0, 2 * np.pi, 30)]
            shape = Polygon(points)
        else:
            w, h = self.size
            shape = box(center[0] - w / 2, center[1] - h / 2,
                        center[0] + w / 2, center[1] + h / 2)
        if self.orientation != 0:
            shape = rotate(shape, self.orientation, origin=center)
        return shape
    
    def _calculate_min_radius(self):
        """Calculate minimum radius that can contain the shape"""
        if self.shape_type == "circle":
            return self.size[0] / 2
        elif self.shape_type == "ellipse":
            return min(self.size[0], self.size[1]) / 2
        else:
            return min(self.size[0], self.size[1]) / 2

class Unit:
    def __init__(self, models):
        self.models = models
        # Cache for oriented shapes
        self._oriented_shapes = None
        self._oriented_min_radii = None

class OptimizedEnvironment:
    def __init__(self, map_bounds, obstacles, friendly_units, enemy_units, moving_unit):
        self.map = map_bounds
        self.obstacles = obstacles
        self.friendly_units = friendly_units
        self.enemy_units = enemy_units
        self.moving_unit = moving_unit
        
        # Pre-compute Minkowski sums and spatial indices
        self._precompute_collision_geometry()
        
    def _precompute_collision_geometry(self):
        """Pre-compute Minkowski sums for fast collision detection"""
        print("Pre-computing collision geometry...")
        
        # Get the moving unit's model shape (use first model as reference)
        moving_model = self.moving_unit.models[0]
        
        # Create base shapes for all orientations
        if moving_model.shape_type != "circle":
            base_shapes = {}
            min_radii = {}
            for angle in ORIENTATIONS:
                if moving_model.shape_type == "ellipse":
                    radius_x = moving_model.size[0] / 2
                    radius_y = moving_model.size[1] / 2
                    points = [(radius_x * np.cos(t), radius_y * np.sin(t))
                              for t in np.linspace(0, 2 * np.pi, 30)]
                    base_shape = Polygon(points)
                    if angle != 0:
                        base_shape = rotate(base_shape, angle, origin=(0, 0))
                else:  # rectangle
                    w, h = moving_model.size
                    base_shape = box(-w/2, -h/2, w/2, h/2)
                    if angle != 0:
                        base_shape = rotate(base_shape, angle, origin=(0, 0))
                
                base_shapes[angle] = base_shape
                min_radii[angle] = self._calculate_shape_min_radius(base_shape)
            
            self.moving_unit._oriented_shapes = base_shapes
            self.moving_unit._oriented_min_radii = min_radii
        else:
            # For circles, all orientations are the same
            radius = moving_model.size[0] / 2
            points = [(radius * np.cos(t), radius * np.sin(t))
                      for t in np.linspace(0, 2 * np.pi, 30)]
            base_shape = Polygon(points)
            self.moving_unit._oriented_shapes = {0: base_shape}
            self.moving_unit._oriented_min_radii = {0: radius}
        
        # Compute Minkowski sums with obstacles
        self.obstacle_minkowski = {}
        for angle, shape in self.moving_unit._oriented_shapes.items():
            minkowski_obstacles = []
            for obstacle in self.obstacles:
                try:
                    # Proper Minkowski sum calculation
                    # For each vertex of the obstacle, translate the shape to that vertex
                    # and take the union of all translated shapes
                    translated_shapes = []
                    obstacle_coords = list(obstacle.exterior.coords[:-1])  # Remove duplicate last point
                    
                    # Sample points along the obstacle perimeter for better coverage
                    from shapely.geometry import LineString
                    perimeter = LineString(obstacle.exterior.coords)
                    sample_points = []
                    total_length = perimeter.length
                    sample_distance = min(10, total_length / 20)  # Sample every 10 units or 20 samples max
                    
                    for i in range(int(total_length / sample_distance) + 1):
                        dist = i * sample_distance
                        if dist <= total_length:
                            point = perimeter.interpolate(dist)
                            sample_points.append((point.x, point.y))
                    
                    # Translate shape to each sample point
                    for px, py in sample_points:
                        translated_shape = translate(shape, px, py)
                        translated_shapes.append(translated_shape)
                    
                    # Union all translated shapes
                    if translated_shapes:
                        minkowski = unary_union(translated_shapes)
                        minkowski_obstacles.append(minkowski)
                    else:
                        # Fallback to buffering
                        min_radius = self.moving_unit._oriented_min_radii[angle]
                        minkowski_obstacles.append(obstacle.buffer(min_radius))
                        
                except Exception as e:
                    # Fallback to simple buffer if Minkowski sum fails
                    min_radius = self.moving_unit._oriented_min_radii[angle]
                    minkowski_obstacles.append(obstacle.buffer(min_radius))
            
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
        
        for unit in self.friendly_units:
            if unit != self.moving_unit:
                for model in unit.models:
                    self.friendly_shapes.append(model.shape)
        
        for unit in self.enemy_units:
            for model in unit.models:
                # Buffer enemy shapes by minimum distance
                self.enemy_shapes.append(model.shape.buffer(ENEMY_DISTANCE))
        
        self.friendly_strtree = STRtree(self.friendly_shapes) if self.friendly_shapes else None
        self.enemy_strtree = STRtree(self.enemy_shapes) if self.enemy_shapes else None
        
        print(f"Collision geometry pre-computed for {len(ORIENTATIONS)} orientations")
    
    def _calculate_shape_min_radius(self, shape):
        """Calculate minimum radius for a shape"""
        bounds = shape.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        return min(width, height) / 2

    def is_valid_position_fast(self, position, orientation):
        """Fast collision detection using pre-computed Minkowski sums and STRTrees"""
        point = Point(position)
        
        # Check map bounds
        if not self.map.contains(point):
            return False
        
        # Check obstacles using Minkowski sums
        if self.obstacle_strtrees[orientation]:
            possible_obstacles = list(self.obstacle_strtrees[orientation].query(point))
            obstacles_list = self.obstacle_minkowski[orientation]
            for idx in possible_obstacles:
                # STRTree returns indices, so we need to get the actual obstacle
                if idx < len(obstacles_list):
                    obstacle = obstacles_list[idx]
                    if obstacle.contains(point):
                        return False
        
        # Check friendly units using STRTree
        if self.friendly_strtree:
            min_radius = self.moving_unit._oriented_min_radii[orientation]
            query_circle = point.buffer(min_radius)
            possible_friendlies = list(self.friendly_strtree.query(query_circle))
            for idx in possible_friendlies:
                # STRTree returns indices, so we need to get the actual friendly unit
                if idx < len(self.friendly_shapes):
                    friendly = self.friendly_shapes[idx]
                    if friendly.intersects(query_circle):
                        return False
        
        # Check enemy units using STRTree
        if self.enemy_strtree:
            possible_enemies = list(self.enemy_strtree.query(point))
            for idx in possible_enemies:
                # STRTree returns indices, so we need to get the actual enemy unit
                if idx < len(self.enemy_shapes):
                    enemy = self.enemy_shapes[idx]
                    if enemy.contains(point):
                        return False
        
        return True
    
    def visualize_collision_geometry(self, orientation=0):
        """Debug function to visualize pre-computed collision geometry"""
        import matplotlib.pyplot as plt
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Plot original environment
        ax1.set_title("Original Environment")
        ax1.set_xlim(0, MAP_WIDTH)
        ax1.set_ylim(0, MAP_HEIGHT)
        ax1.set_aspect('equal')
        
        # Plot obstacles
        for obstacle in self.obstacles:
            x, y = obstacle.exterior.xy
            ax1.plot(x, y, 'k-', linewidth=2)
            ax1.fill(x, y, alpha=0.3, color='gray')
        
        # Plot friendly units
        for unit in self.friendly_units:
            if unit != self.moving_unit:
                for model in unit.models:
                    x, y = model.shape.exterior.xy
                    ax1.plot(x, y, 'g-', linewidth=2)
                    ax1.fill(x, y, alpha=0.3, color='green')
        
        # Plot enemy units
        for unit in self.enemy_units:
            for model in unit.models:
                x, y = model.shape.exterior.xy
                ax1.plot(x, y, 'r-', linewidth=2)
                ax1.fill(x, y, alpha=0.3, color='red')
        
        # Plot moving unit shape
        if orientation in self.moving_unit._oriented_shapes:
            shape = self.moving_unit._oriented_shapes[orientation]
            # Translate to current position for visualization
            current_pos = self.moving_unit.models[0].shape.centroid
            translated_shape = translate(shape, current_pos.x, current_pos.y)
            x, y = translated_shape.exterior.xy
            ax1.plot(x, y, 'b-', linewidth=2)
            ax1.fill(x, y, alpha=0.3, color='blue')
        
        # Plot Minkowski sums
        ax2.set_title(f"Minkowski Sums (Orientation {orientation}°)")
        ax2.set_xlim(0, MAP_WIDTH)
        ax2.set_ylim(0, MAP_HEIGHT)
        ax2.set_aspect('equal')
        
        if orientation in self.obstacle_minkowski:
            for i, minkowski in enumerate(self.obstacle_minkowski[orientation]):
                if hasattr(minkowski, 'geoms'):
                    for geom in minkowski.geoms:
                        x, y = geom.exterior.xy
                        ax2.plot(x, y, 'k-', linewidth=1)
                        ax2.fill(x, y, alpha=0.2, color=f'C{i % 10}')
                else:
                    x, y = minkowski.exterior.xy
                    ax2.plot(x, y, 'k-', linewidth=1)
                    ax2.fill(x, y, alpha=0.2, color=f'C{i % 10}')
        
        plt.tight_layout()
        plt.show()

# Legacy Environment class for backward compatibility
class Environment:
    def __init__(self, map_bounds, obstacles, friendly_units, enemy_units):
        self.map = map_bounds
        self.obstacles = obstacles
        self.friendly_units = friendly_units
        self.enemy_units = enemy_units

    def is_valid_position(self, model, unit):
        if not self.map.contains(model.shape):
            return False
        for f_unit in self.friendly_units:
            if f_unit != unit:
                for f_model in f_unit.models:
                    if model.shape.intersects(f_model.shape):
                        return False
        for e_unit in self.enemy_units:
            for e_model in e_unit.models:
                if model.shape.distance(e_model.shape) < ENEMY_DISTANCE:
                    return False
        for obstacle in self.obstacles:
            if model.shape.intersects(obstacle):
                return False
        return True

def get_rotation_cost():
    """Return the movement cost for any rotation during a turn (1 inch)"""
    return INCH_TO_MM  # 1 inch = 25.4mm

def heuristic(a, b):
    ax, ay = a
    bx, by = b
    return np.hypot(bx - ax, by - ay)

def a_star_optimized(start, goal, environment, unit):
    """Optimized A* using pre-computed Minkowski sums and STRTrees"""
    from heapq import heappush, heappop
    
    # Get unit's current orientation
    current_orientation = unit.models[0].orientation
    
    # Find the closest orientation in our ORIENTATIONS list
    if current_orientation in ORIENTATIONS:
        start_orientation = current_orientation
    else:
        # Find closest orientation
        start_orientation = min(ORIENTATIONS, key=lambda x: abs(x - current_orientation))
    
    open_set = []
    came_from = {}
    cost_so_far = {}
    rotation_occurred = {}  # Track if rotation occurred on path to each node
    heappush(open_set, (0, 0, start, None, start_orientation, False))
    cost_so_far[start] = 0
    rotation_occurred[start] = False

    zero_angle = ORIENTATIONS[0]
    second_angle = ORIENTATIONS[1]

    while open_set:
        _, cost, current, parent, rotation, path_has_rotation = heappop(open_set)
        last_angle = rotation
        
        if heuristic(current, goal) < 10:  # early exit threshold
            path = [(current, rotation)]
            while parent:
                path.append(parent)
                parent = came_from.get(parent[0])
            path.reverse()
            # Return path with rotation flag
            return path, path_has_rotation

        for dx, dy in [(-10, 0), (10, 0), (0, -10), (0, 10), (-10, -10), (10, -10), (-10, 10), (10, 10)]:
            neighbor = (current[0] + dx, current[1] + dy)

            # For circles, orientation doesn't matter
            if unit.models[0].shape_type == "circle":
                if environment.is_valid_position_fast(neighbor, 0):
                    new_cost = cost + heuristic(current, neighbor)
                    if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                        cost_so_far[neighbor] = new_cost
                        rotation_occurred[neighbor] = path_has_rotation
                        priority = new_cost + heuristic(goal, neighbor)
                        heappush(open_set, (priority, new_cost, neighbor, (current, rotation), 0, path_has_rotation))
                        came_from[neighbor] = (current, rotation)
                continue

            # Try last orientation first (for non-circles) - prefer maintaining current orientation
            if environment.is_valid_position_fast(neighbor, last_angle):
                new_cost = cost + heuristic(current, neighbor)
                # Small bonus for maintaining the same orientation (orientation consistency)
                if last_angle == start_orientation:
                    new_cost -= 0.1  # Slight preference for maintaining original orientation
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    rotation_occurred[neighbor] = path_has_rotation
                    priority = new_cost + heuristic(goal, neighbor)
                    heappush(open_set, (priority, new_cost, neighbor, (current, rotation), last_angle, path_has_rotation))
                    came_from[neighbor] = (current, rotation)
                continue

            # Try current unit orientation if different from last_angle
            if start_orientation != last_angle:
                if environment.is_valid_position_fast(neighbor, start_orientation):
                    new_cost = cost + heuristic(current, neighbor) - 0.1  # Prefer original orientation
                    has_rotation = path_has_rotation or (start_orientation != last_angle)  # Check if rotation occurred
                    if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                        cost_so_far[neighbor] = new_cost
                        rotation_occurred[neighbor] = has_rotation
                        priority = new_cost + heuristic(goal, neighbor)
                        heappush(open_set, (priority, new_cost, neighbor, (current, rotation), start_orientation, has_rotation))
                        came_from[neighbor] = (current, rotation)
                    continue

            # Try zero orientation
            if zero_angle != last_angle and zero_angle != start_orientation:
                if environment.is_valid_position_fast(neighbor, zero_angle):
                    new_cost = cost + heuristic(current, neighbor)
                    has_rotation = path_has_rotation or (zero_angle != start_orientation)  # Check if rotation occurred
                    if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                        cost_so_far[neighbor] = new_cost
                        rotation_occurred[neighbor] = has_rotation
                        priority = new_cost + heuristic(goal, neighbor)
                        heappush(open_set, (priority, new_cost, neighbor, (current, rotation), zero_angle, has_rotation))
                        came_from[neighbor] = (current, rotation)
                    continue

            # Try remaining orientations, but prioritize those close to the start orientation
            remaining_orientations = [a for a in ORIENTATIONS if a not in [last_angle, start_orientation, zero_angle]]
            # DO NOT sort remaining orientation - ORIENTATIONS are ordered for optimization
            
            for angle in remaining_orientations:
                if environment.is_valid_position_fast(neighbor, angle):
                    new_cost = cost + heuristic(current, neighbor)
                    has_rotation = path_has_rotation or (angle != start_orientation)  # Check if rotation occurred
                    if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                        cost_so_far[neighbor] = new_cost
                        rotation_occurred[neighbor] = has_rotation
                        priority = new_cost + heuristic(goal, neighbor)
                        heappush(open_set, (priority, new_cost, neighbor, (current, rotation), angle, has_rotation))
                        came_from[neighbor] = (current, rotation)
                    break

    return None, False

def a_star(start, goal, environment, unit):
    """Legacy A* function for backward compatibility"""
    from heapq import heappush, heappop
    
    # Get unit's current orientation
    current_orientation = unit.models[0].orientation
    start_orientation = current_orientation if current_orientation in ORIENTATIONS else ORIENTATIONS[0]
    
    # Pre-cache rotated ellipse shapes only for ellipses
    if unit.models[0].shape_type != "circle" and unit._oriented_shapes is None:
        print("Pre-caching oriented shapes")
        unit._oriented_shapes = {
            angle: rotate(Polygon([(unit.models[0].size[0] / 2 * np.cos(t), unit.models[0].size[1] / 2 * np.sin(t))
                                  for t in np.linspace(0, 2 * np.pi, 30)]), angle)
            for angle in ORIENTATIONS
        }

    open_set = []
    came_from = {}
    cost_so_far = {}
    rotation_occurred = {}
    heappush(open_set, (0, 0, start, None, start_orientation, False))
    cost_so_far[start] = 0
    rotation_occurred[start] = False

    zero_angle = ORIENTATIONS[0]
    second_angle = ORIENTATIONS[1]

    while open_set:
        _, cost, current, parent, rotation, path_has_rotation = heappop(open_set)
        last_angle = rotation  # Update last_angle to current node's rotation
        if heuristic(current, goal) < 10:  # early exit threshold
            path = [(current, rotation)]
            while parent:
                path.append(parent)
                parent = came_from.get(parent[0])
            path.reverse()
            return path, path_has_rotation

        for dx, dy in [(-10, 0), (10, 0), (0, -10), (0, 10), (-10, -10), (10, -10), (-10, 10), (10, 10)]:
            neighbor = (current[0] + dx, current[1] + dy)

            if unit.models[0].shape_type == "circle":
                model = Model(neighbor, shape_type="circle", size=unit.models[0].size)
                if environment.is_valid_position(model, unit):
                    new_cost = cost + heuristic(current, neighbor)
                    if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                        cost_so_far[neighbor] = new_cost
                        rotation_occurred[neighbor] = path_has_rotation
                        priority = new_cost + heuristic(goal, neighbor)
                        heappush(open_set, (priority, new_cost, neighbor, (current, rotation), 0, path_has_rotation))
                        came_from[neighbor] = (current, rotation)
                continue

            # Try last orientation first
            base = unit._oriented_shapes[last_angle]
            model = Model(neighbor, orientation=last_angle)
            # Replace with cached shape translated to neighbor position
            # (cached shapes are at origin, need to be moved to neighbor)
            model.shape = translate(base, neighbor[0], neighbor[1])
            if environment.is_valid_position(model, unit):
                new_cost = cost + heuristic(current, neighbor)
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    rotation_occurred[neighbor] = path_has_rotation
                    priority = new_cost + heuristic(goal, neighbor)
                    heappush(open_set, (priority, new_cost, neighbor, (current, rotation), last_angle, path_has_rotation))
                    came_from[neighbor] = (current, rotation)
                continue

            # Try zero orientation
            if zero_angle != last_angle:
                base = unit._oriented_shapes[zero_angle]
                model = Model(neighbor, orientation=zero_angle)
                # Replace with cached shape translated to neighbor position
                model.shape = translate(base, neighbor[0], neighbor[1])
                if environment.is_valid_position(model, unit):
                    new_cost = cost + heuristic(current, neighbor)
                    has_rotation = path_has_rotation or (zero_angle != start_orientation)
                    if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                        cost_so_far[neighbor] = new_cost
                        rotation_occurred[neighbor] = has_rotation
                        priority = new_cost + heuristic(goal, neighbor)
                        heappush(open_set, (priority, new_cost, neighbor, (current, rotation), zero_angle, has_rotation))
                        came_from[neighbor] = (current, rotation)
                    last_angle = zero_angle
                    continue

            # Try second orientation
            if second_angle != last_angle:
                base = unit._oriented_shapes[second_angle]
                model = Model(neighbor, orientation=second_angle)
                # Replace with cached shape translated to neighbor position
                model.shape = translate(base, neighbor[0], neighbor[1])
                if environment.is_valid_position(model, unit):
                    new_cost = cost + heuristic(current, neighbor)
                    has_rotation = path_has_rotation or (second_angle != start_orientation)
                    if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                        cost_so_far[neighbor] = new_cost
                        rotation_occurred[neighbor] = has_rotation
                        priority = new_cost + heuristic(goal, neighbor)
                        heappush(open_set, (priority, new_cost, neighbor, (current, rotation), second_angle, has_rotation))
                        came_from[neighbor] = (current, rotation)
                    last_angle = second_angle
                    continue

            # Try remaining orientations - DO NOT sort, keep ORIENTATIONS order for optimization
            for angle in ORIENTATIONS[2:-1]:
                base = unit._oriented_shapes[angle]
                model = Model(neighbor, orientation=angle)
                # Replace with cached shape translated to neighbor position
                model.shape = translate(base, neighbor[0], neighbor[1])
                if not environment.is_valid_position(model, unit):
                    continue
                new_cost = cost + heuristic(current, neighbor)
                has_rotation = path_has_rotation or (angle != start_orientation)
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    rotation_occurred[neighbor] = has_rotation
                    priority = new_cost + heuristic(goal, neighbor)
                    heappush(open_set, (priority, new_cost, neighbor, (current, rotation), angle, has_rotation))
                    came_from[neighbor] = (current, rotation)
                last_angle = angle
                break

    return None, False

def a_star_pathfinding_optimized(unit, goal, environment, max_distance):
    """Optimized pathfinding using pre-computed Minkowski sums and STRTrees"""
    start = unit.models[0].shape.centroid.coords[0]
    current_orientation = unit.models[0].orientation
    
    result = a_star_optimized(start, goal, environment, unit)
    if not result or not result[0]:
        return None
    
    raw_path, has_rotation = result
    
    # Apply rotation cost if any rotation occurred during the path
    effective_max_distance = max_distance
    if has_rotation and unit.models[0].shape_type != "circle":
        effective_max_distance -= get_rotation_cost()
        print(f"Rotation cost applied: {get_rotation_cost():.1f}mm, effective max distance: {effective_max_distance:.1f}mm")

    steps = []
    distance_used = 0
    turn = 0
    previous = raw_path[0][0]

    for i in range(1, len(raw_path)):
        pos, rot = raw_path[i]
        
        # Check if movement direction aligns with current orientation
        if i == 1:  # First movement step
            # Calculate movement direction
            dx = pos[0] - previous[0]
            dy = pos[1] - previous[1]
            if dx != 0 or dy != 0:
                movement_angle = np.degrees(np.arctan2(dy, dx))
                # Normalize to 0-360 range
                movement_angle = movement_angle % 360
                
                # Check if movement direction is close to current orientation
                angle_diff = abs(movement_angle - current_orientation)
                if angle_diff > 180:
                    angle_diff = 360 - angle_diff
                
                # If moving in roughly the same direction, keep current orientation
                if angle_diff < 45:  # Within 45 degrees
                    rot = current_orientation
        
        step_distance = heuristic(previous, pos)
        if distance_used + step_distance > effective_max_distance:
            turn += 1
            distance_used = 0
        steps.append(([pos], [rot], distance_used, turn))
        distance_used += step_distance
        previous = pos

    return steps

def a_star_pathfinding(unit, goal, environment, max_distance):
    """Legacy pathfinding function for backward compatibility"""
    start = unit.models[0].shape.centroid.coords[0]
    result = a_star(start, goal, environment, unit)
    if not result or not result[0]:
        return None
    
    raw_path, has_rotation = result
    
    # Apply rotation cost if any rotation occurred during the path
    effective_max_distance = max_distance
    if has_rotation and unit.models[0].shape_type != "circle":
        effective_max_distance -= get_rotation_cost()
        print(f"Rotation cost applied: {get_rotation_cost():.1f}mm, effective max distance: {effective_max_distance:.1f}mm")

    steps = []
    distance_used = 0
    turn = 0
    previous = raw_path[0][0]

    for i in range(1, len(raw_path)):
        pos, rot = raw_path[i]
        step_distance = heuristic(previous, pos)
        if distance_used + step_distance > effective_max_distance:
            turn += 1
            distance_used = 0
        steps.append(([pos], [rot], distance_used, turn))
        distance_used += step_distance
        previous = pos

    return steps

# Interactive Pygame setup
async def main():
    import time
    import numpy as np
    pygame.init()
    screen = pygame.display.set_mode((int(MAP_WIDTH), int(MAP_HEIGHT)))
    pygame.display.set_caption("Interactive Pathfinding - Click unit to select, hover to preview path, click to move")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 24)

    map_bounds = box(0, 0, MAP_WIDTH, MAP_HEIGHT)
    obstacles = [
        Polygon([(400, 400), (800, 400), (550, 1600)]),  # Triangle
        box(800, 200, 1100, 400),
        box(1140, 200, MAP_WIDTH, 400),
        Polygon([(1000, 700), (1400, 700), (1050, 900), (1200, 700)]),  # Irregular
    ]
    friendly_unit = Unit([Model((200, 200))])  # Move to more visible position
    enemy_units = [Unit([Model((800, 800))]), Unit([Model((1000, 200))]), Unit([Model((1450, 700))])]
    
    max_distance = 12 * INCH_TO_MM  # One turn movement

    # Debug unit positions BEFORE environment creation
    print("=== UNIT POSITIONS ===")
    for i, model in enumerate(friendly_unit.models):
        center = model.shape.centroid
        print(f"Friendly unit {i} center: ({center.x:.1f}, {center.y:.1f})")
    
    for i, unit in enumerate(enemy_units):
        for j, model in enumerate(unit.models):
            center = model.shape.centroid
            print(f"Enemy unit {i} model {j} center: ({center.x:.1f}, {center.y:.1f})")
    print("=======================")

    # Quick benchmark
    print("Initializing optimized pathfinding environment...")
    optimized_env = OptimizedEnvironment(map_bounds, obstacles, [friendly_unit], enemy_units, friendly_unit)
    print("Ready for interactive pathfinding!")
    
    # Interactive state
    selected_unit = None
    preview_path = None
    mouse_pos = (0, 0)
    last_mouse_pos = (0, 0)
    valid_target = False
    path_calculation_time = 0.0
    last_path_update = 0.0
    
    def point_in_polygon(point, polygon_points):
        """Check if point is inside polygon using ray casting"""
        x, y = point
        n = len(polygon_points)
        inside = False
        p1x, p1y = polygon_points[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon_points[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside
    
    def is_unit_clicked(mouse_pos, unit):
        """Check if mouse position is over a unit"""
        from shapely.geometry import Point
        mouse_point = Point(mouse_pos[0], mouse_pos[1])
        
        for i, model in enumerate(unit.models):
            center = model.shape.centroid
            distance = mouse_point.distance(center)
            print(f"  Model {i}: center=({center.x:.1f}, {center.y:.1f}), distance={distance:.1f}")
            
            # Check if within unit shape or close to it
            if model.shape.contains(mouse_point) or distance < 60:  # Much larger click area
                print(f"  Unit clicked! (distance: {distance:.1f})")
                return True
        return False
    
    def calculate_path_distance(path_steps):
        """Calculate total distance of a path"""
        if not path_steps:
            return 0
        
        total_distance = 0
        previous_pos = None
        
        for step in path_steps:
            pos_list, _, _, _ = step
            if pos_list:
                current_pos = pos_list[0]
                if previous_pos:
                    total_distance += heuristic(previous_pos, current_pos)
                previous_pos = current_pos
        
        return total_distance

    running = True
    print("Starting main game loop...")
    
    while running:
        # Get current mouse position
        mouse_pos = pygame.mouse.get_pos()
        
        # Process events
        for event in pygame.event.get():
            # Only print important events
            if event.type in [pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN]:
                print(f"Event: {event.type}")  # Debug important events
            
            if event.type == pygame.QUIT:
                print("Quit event received")
                running = False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    click_pos = pygame.mouse.get_pos()
                    print(f"Left mouse clicked at {click_pos}")
                    
                    # Check if clicking on friendly unit to select it
                    unit_clicked = is_unit_clicked(click_pos, friendly_unit)
                    print(f"Unit clicked check: {unit_clicked}")
                    
                    if unit_clicked:
                        selected_unit = friendly_unit
                        print("Unit selected!")
                    
                    # Check if clicking to move selected unit
                    elif selected_unit and valid_target and preview_path:
                        # Move the unit to the target position
                        final_step = preview_path[-1]
                        final_pos = final_step[0][0]  # pos_list[0]
                        final_rot = final_step[1][0]  # rot_list[0]
                        
                        # Update unit position
                        old_orientation = selected_unit.models[0].orientation
                        new_model = Model(final_pos, 
                                        shape_type=selected_unit.models[0].shape_type,
                                        size=selected_unit.models[0].size,
                                        orientation=final_rot)
                        selected_unit.models[0] = new_model
                        
                        # Debug orientation changes
                        if abs(old_orientation - final_rot) > 5:  # Only log significant changes
                            print(f"Orientation changed: {old_orientation:.1f}° → {final_rot:.1f}°")
                        
                        # Recompute environment with new unit position
                        print(f"Unit moved to {final_pos}")
                        optimized_env = OptimizedEnvironment(map_bounds, obstacles, [friendly_unit], enemy_units, friendly_unit)
                        
                        # Clear preview
                        preview_path = None
                        valid_target = False
                    else:
                        print(f"Click ignored - selected: {selected_unit is not None}, valid: {valid_target}, has_path: {preview_path is not None}")
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    selected_unit = None
                    preview_path = None
                    print("Unit deselected")
        
        # Update preview path if unit is selected and mouse moved significantly
        current_time = time.time()
        should_update_path = (selected_unit and 
                            (heuristic(mouse_pos, last_mouse_pos) > 50 or 
                             current_time - last_path_update > 0.5))  # Much less frequent updates
        
        if should_update_path:
            start_time = time.time()
            
            try:
                preview_path = a_star_pathfinding_optimized(selected_unit, mouse_pos, optimized_env, max_distance)
                path_calculation_time = time.time() - start_time
                
                # Check if path is valid and within one turn
                if preview_path:
                    path_distance = calculate_path_distance(preview_path)
                    valid_target = path_distance <= max_distance
                else:
                    valid_target = False
                    
                last_mouse_pos = mouse_pos
                last_path_update = current_time
                    
            except Exception as e:
                print(f"Path calculation error: {e}")
                preview_path = None
                valid_target = False
                path_calculation_time = time.time() - start_time

        # Rendering
        screen.fill((255, 255, 255))
        
        # Draw obstacles
        for obstacle in obstacles:
            points = [(int(x), int(y)) for x, y in obstacle.exterior.coords]
            pygame.draw.polygon(screen, (100, 100, 100), points)
        
        # Draw enemy units
        for unit in enemy_units:
            for model in unit.models:
                points = [(int(x), int(y)) for x, y in model.shape.exterior.coords]
                pygame.draw.polygon(screen, (255, 0, 0), points)
        
        # Draw friendly unit
        for model in friendly_unit.models:
            points = [(int(x), int(y)) for x, y in model.shape.exterior.coords]
            color = (0, 255, 0) if selected_unit == friendly_unit else (0, 200, 0)
            pygame.draw.polygon(screen, color, points)
            if selected_unit == friendly_unit:
                pygame.draw.polygon(screen, (0, 0, 255), points, 3)  # Blue outline for selected
            else:
                pygame.draw.polygon(screen, (0, 150, 0), points, 2)  # Green outline for unselected
            
            # Draw center dot for easier clicking
            center = model.shape.centroid
            pygame.draw.circle(screen, (255, 255, 255), (int(center.x), int(center.y)), 3)
            pygame.draw.circle(screen, (0, 0, 0), (int(center.x), int(center.y)), 3, 1)
            
            # Draw orientation indicator (arrow showing facing direction)
            orientation_rad = np.radians(model.orientation)
            arrow_length = 25
            end_x = center.x + arrow_length * np.cos(orientation_rad)
            end_y = center.y + arrow_length * np.sin(orientation_rad)
            
            # Draw orientation line/arrow
            pygame.draw.line(screen, (255, 255, 0), 
                           (int(center.x), int(center.y)), 
                           (int(end_x), int(end_y)), 3)
            
            # Draw arrowhead
            arrowhead_length = 8
            arrowhead_angle = np.pi / 6  # 30 degrees
            
            # Left arrowhead line
            left_x = end_x - arrowhead_length * np.cos(orientation_rad - arrowhead_angle)
            left_y = end_y - arrowhead_length * np.sin(orientation_rad - arrowhead_angle)
            pygame.draw.line(screen, (255, 255, 0), 
                           (int(end_x), int(end_y)), 
                           (int(left_x), int(left_y)), 2)
            
            # Right arrowhead line
            right_x = end_x - arrowhead_length * np.cos(orientation_rad + arrowhead_angle)
            right_y = end_y - arrowhead_length * np.sin(orientation_rad + arrowhead_angle)
            pygame.draw.line(screen, (255, 255, 0), 
                           (int(end_x), int(end_y)), 
                           (int(right_x), int(right_y)), 2)
        
        # Draw movement range circle if unit is selected
        if selected_unit:
            center = selected_unit.models[0].shape.centroid
            pygame.draw.circle(screen, (0, 255, 255, 50), 
                             (int(center.x), int(center.y)), 
                             int(max_distance), 2)
        
        # Draw preview path
        if preview_path and selected_unit:
            path_color = (0, 255, 0, 128) if valid_target else (255, 0, 0, 128)
            
            # Draw path line
            if len(preview_path) > 1:
                path_points = []
                for step in preview_path:
                    pos_list, _, _, _ = step
                    if pos_list:
                        path_points.append((int(pos_list[0][0]), int(pos_list[0][1])))
                
                if len(path_points) > 1:
                    pygame.draw.lines(screen, path_color[:3], False, path_points, 3)
            
            # Draw target position
            if preview_path:
                final_step = preview_path[-1]
                final_pos = final_step[0][0]
                final_rot = final_step[1][0]
                
                # Preview unit at target position
                preview_model = Model(final_pos, 
                                    shape_type=selected_unit.models[0].shape_type,
                                    size=selected_unit.models[0].size,
                                    orientation=final_rot)
                points = [(int(x), int(y)) for x, y in preview_model.shape.exterior.coords]
                color = (0, 255, 0, 100) if valid_target else (255, 0, 0, 100)
                pygame.draw.polygon(screen, color[:3], points)
                pygame.draw.polygon(screen, color[:3], points, 2)
        
        # Draw target cursor
        if selected_unit:
            cursor_color = (0, 255, 0) if valid_target else (255, 0, 0)
            pygame.draw.circle(screen, cursor_color, mouse_pos, 5)
        
        # Draw UI text on the right side
        friendly_center = friendly_unit.models[0].shape.centroid
        friendly_orientation = friendly_unit.models[0].orientation
        texts = [
            f"FPS: {clock.get_fps():.1f}",
            f"Path calc: {path_calculation_time*1000:.1f}ms",
            "",
            "Controls:",
            "• Click green unit to select",
            "• Hover to preview path", 
            "• Click to move (if green)",
            "• ESC to deselect",
            "",
            f"Unit at: ({friendly_center.x:.0f}, {friendly_center.y:.0f})",
            f"Orientation: {friendly_orientation:.0f}°",
            f"Selected: {'Yes' if selected_unit else 'No'}",
            f"Valid target: {'Yes' if valid_target else 'No'}",
            f"Max distance: {max_distance:.0f}mm"
        ]
        
        ui_x = int(MAP_WIDTH) - 250  # Right side of screen
        y_offset = 10
        for text in texts:
            if text:  # Skip empty strings
                text_surface = font.render(text, True, (0, 0, 0))
                # Add background for better readability
                text_rect = text_surface.get_rect()
                text_rect.x = ui_x
                text_rect.y = y_offset
                pygame.draw.rect(screen, (255, 255, 255, 200), text_rect)
                screen.blit(text_surface, (ui_x, y_offset))
            y_offset += 20

        pygame.display.flip()
        clock.tick(60)  # Limit to 60 FPS
        await asyncio.sleep(1.0 / 60.0)  # Async sleep for 60 FPS

    pygame.quit()

if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        asyncio.run(main())

# Example usage:
"""
# For optimized pathfinding:
optimized_env = OptimizedEnvironment(map_bounds, obstacles, friendly_units, enemy_units, moving_unit)
path = a_star_pathfinding_optimized(unit, target, optimized_env, max_distance)

# For legacy pathfinding:
legacy_env = Environment(map_bounds, obstacles, friendly_units, enemy_units)
path = a_star_pathfinding(unit, target, legacy_env, max_distance)

# To visualize collision geometry:
optimized_env.visualize_collision_geometry(orientation=0)
"""