from math import sqrt, atan2
from typing import Tuple, List
import heapq

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..classes.map import Map


MM_TO_INCHES = 25.4
VIEWING_ANGLE = 1.57 / 3 # 30 degrees

# Convert mm (as in base size of models) to inches
def convert_mm_to_inches(value: float) -> float:
    return round(value / MM_TO_INCHES, 4)

# Determine the distance of a 3D position delta
def get_dist(x_delta: float, y_delta: float, z_delta: float = 0) -> float:
    return sqrt(x_delta**2 + y_delta**2 + z_delta**2)

# Determine the angle between to X,Y points
def get_angle(x_delta: float, y_delta: float) -> float:
    return atan2(x_delta, y_delta)

'''
Opton 1: Algorithmic Pathfinding (Recommended)

Pros:

Efficiency: Algorithms like A* can find optimal paths quickly.
Rule Compliance: Easier to incorporate game-specific movement rules.
Determinism: Predictable paths make debugging and strategy analysis simpler.

Cons:

Limited Adaptability: Doesn't learn from experience unless explicitly programmed.


Option 2: Learned Pathfinding

Pros:

Adaptability: Can learn to navigate complex scenarios over time.
Strategic Depth: May discover unconventional paths that an algorithm might miss.

Cons:

Complexity: Requires significant training data and computational resources.
Unpredictability: May produce non-optimal paths during learning phases.
Recommendation:

RECOMMENDATION: 

Use algorithmic pathfinding for movement and let the learning components focus on 
higher-level strategic decisions. This approach ensures compliance with movement 
rules and efficient path calculation while allowing the AI to learn when and where 
to move strategically.
'''
def astar(start_tile: Tuple[float, float], goal_tile: Tuple[float, float], game_map: 'Map'):
    open_set = []
    heapq.heappush(open_set, (0, start_tile))
    came_from = {}
    cost_so_far = {start_tile: 0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal_tile:
            # Reconstruct path
            path = []
            while current != start_tile:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path  # List of tiles from start to goal

        for neighbor in game_map.get_neighbors(current):
            new_cost = cost_so_far[current] + game_map.get_movement_cost(current, neighbor)
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                priority = new_cost + get_dist(neighbor[0] - goal_tile[0], neighbor[1] - goal_tile[1])
                heapq.heappush(open_set, (priority, neighbor))
                came_from[neighbor] = current
    return None  # No path found