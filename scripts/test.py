import asyncio
import platform
import pygame
import numpy as np
from shapely.geometry import Polygon, box
from shapely.affinity import rotate, translate

# Constants
INCH_TO_MM = 25.4
MAP_WIDTH = 60 * INCH_TO_MM
MAP_HEIGHT = 44 * INCH_TO_MM
MODEL_SIZE = (60, 35)  # Ellipse size
ENEMY_DISTANCE = 25.4
ORIENTATIONS = [0, 90, 45, 15, 30, 60, 75]

class Model:
    def __init__(self, center, shape_type="ellipse", size=MODEL_SIZE, orientation=0):
        self.shape_type = shape_type
        self.size = size
        self.orientation = orientation
        self.shape = self._create_shape(center)

    def _create_shape(self, center):
        if self.shape_type == "ellipse":
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

class Unit:
    def __init__(self, models):
        self.models = models

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

def heuristic(a, b):
    ax, ay = a
    bx, by = b
    return np.hypot(bx - ax, by - ay)

# Pre-cache rotated ellipse shapes at origin
ELLIPSE_SHAPES = {
    angle: rotate(Polygon([(MODEL_SIZE[0] / 2 * np.cos(t), MODEL_SIZE[1] / 2 * np.sin(t))
                           for t in np.linspace(0, 2 * np.pi, 30)]), angle, origin=(0, 0))
    for angle in ORIENTATIONS
}

def a_star(start, goal, environment, unit):
    from heapq import heappush, heappop
    open_set = []
    came_from = {}
    cost_so_far = {}
    heappush(open_set, (0, 0, start, None, 0))
    cost_so_far[start] = 0

    while open_set:
        _, cost, current, parent, rotation = heappop(open_set)
        if heuristic(current, goal) < 10:  # early exit threshold
            path = [(current, rotation)]
            while parent:
                path.append(parent)
                parent = came_from.get(parent[0])
            path.reverse()
            return path

        for dx, dy in [(-10, 0), (10, 0), (0, -10), (0, 10), (-10, -10), (10, -10), (-10, 10), (10, 10)]:
            neighbor = (current[0] + dx, current[1] + dy)

            # Try 0° first
            rotated = translate(ELLIPSE_SHAPES[0], xoff=neighbor[0], yoff=neighbor[1])
            model = Model(neighbor, orientation=0)
            model.shape = rotated
            if environment.is_valid_position(model, unit):
                new_cost = cost + heuristic(current, neighbor)
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + heuristic(goal, neighbor)
                    heappush(open_set, (priority, new_cost, neighbor, (current, rotation), 0))
                    came_from[neighbor] = (current, rotation)
                continue

            # Try 90° second
            rotated = translate(ELLIPSE_SHAPES[90], xoff=neighbor[0], yoff=neighbor[1])
            model = Model(neighbor, orientation=90)
            model.shape = rotated
            if environment.is_valid_position(model, unit):
                new_cost = cost + heuristic(current, neighbor)
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + heuristic(goal, neighbor)
                    heappush(open_set, (priority, new_cost, neighbor, (current, rotation), 90))
                    came_from[neighbor] = (current, rotation)
                continue

            # Try remaining orientations only if 0° fails
            for angle in ORIENTATIONS[2:]:
                rotated = translate(ELLIPSE_SHAPES[angle], xoff=neighbor[0], yoff=neighbor[1])
                model = Model(neighbor, orientation=angle)
                model.shape = rotated
                if not environment.is_valid_position(model, unit):
                    continue
                new_cost = cost + heuristic(current, neighbor)
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + heuristic(goal, neighbor)
                    heappush(open_set, (priority, new_cost, neighbor, (current, rotation), angle))
                    came_from[neighbor] = (current, rotation)
                break

    return None

def a_star_pathfinding(unit, goal, environment, max_distance):
    start = unit.models[0].shape.centroid.coords[0]
    raw_path = a_star(start, goal, environment, unit)
    if not raw_path:
        return None

    steps = []
    distance_used = 0
    turn = 0
    previous = raw_path[0][0]

    for i in range(1, len(raw_path)):
        pos, rot = raw_path[i]
        step_distance = heuristic(previous, pos)
        if distance_used + step_distance > max_distance:
            turn += 1
            distance_used = 0
        steps.append(([pos], [rot], distance_used, turn))
        distance_used += step_distance
        previous = pos

    return steps

# Pygame setup
async def main():
    pygame.init()
    screen = pygame.display.set_mode((MAP_WIDTH, MAP_HEIGHT))
    clock = pygame.time.Clock()

    map_bounds = box(0, 0, MAP_WIDTH, MAP_HEIGHT)
    obstacles = [
        Polygon([(400, 400), (800, 400), (550, 1600)]),  # Triangle
        box(800, 200, 1100, 400),
        box(1140, 200, 1400, 400),
        Polygon([(1000, 700), (1400, 700), (1050, 900), (1200, 700)]),  # Irregular
    ]
    friendly_unit = Unit([Model((100, 100))])
    enemy_units = [Unit([Model((800, 800))]), Unit([Model((1000, 200))]), Unit([Model((1450, 700))])]
    environment = Environment(map_bounds, obstacles, [friendly_unit], enemy_units)

    target = (1200, 900)
    max_distance = 12 * INCH_TO_MM

    path = a_star_pathfinding(friendly_unit, target, environment, max_distance)
    if not path:
        print("No path found.")
        return

    path_index = 0
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((255, 255, 255))
        for obstacle in obstacles:
            points = [(x, y) for x, y in obstacle.exterior.coords]
            pygame.draw.polygon(screen, (100, 100, 100), points)

        for unit in enemy_units:
            for model in unit.models:
                points = [(x, y) for x, y in model.shape.exterior.coords]
                pygame.draw.polygon(screen, (255, 0, 0), points)

        if path_index < len(path):
            pos_list, rot_list, _, _ = path[path_index]
            for pos, rot in zip(pos_list, rot_list):
                model = Model(pos, orientation=rot)
                points = [(x, y) for x, y in model.shape.exterior.coords]
                pygame.draw.polygon(screen, (0, 255, 0), points)
            path_index += 1

        pygame.display.flip()
        clock.tick(30)
        await asyncio.sleep(1.0 / 30)

    pygame.quit()

if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        asyncio.run(main())