import random
import math
from shapely.geometry import Point, box
from shapely.affinity import scale, rotate, translate
from shapely.strtree import STRtree

def arrange_ellipses(ellipses, center_x, center_y, target_x, target_y, coherency_distance, required_neighbors, tightness, obstacles=None):
    """
    Arrange ellipses around the specified center, satisfying the constraints and avoiding obstacles.
    Each ellipse faces towards the target location.

    Parameters:
    - ellipses: list of tuples [(a1, b1), (a2, b2), ..., (aN, bN)], major and minor radii
    - center_x, center_y: center coordinates
    - target_x, target_y: target location coordinates that ellipses should face
    - coherency_distance: the maximum allowed edge-to-edge distance for coherency
    - required_neighbors: the number of neighbors each ellipse must be within coherency distance
    - tightness: parameter controlling the overall spread of the formation (0 < tightness <= 1)
    - obstacles: list of Shapely polygons that the ellipses must avoid

    Returns:
    - positions: list of (x_i, y_i)
    - orientations: list of theta_i (in degrees)
    """
    if obstacles is None:
        obstacles = []

    N = len(ellipses)

    # Compute average sizes
    avg_a = sum(a for a, b in ellipses) / N
    avg_b = sum(b for a, b in ellipses) / N

    # Determine initial spacing based on tightness
    default_spacing = (avg_a + avg_b) * 2
    spacing = default_spacing * tightness

    # Initialize positions in a grid around the center
    grid_cols = grid_rows = int(math.ceil(math.sqrt(N)))

    # Compute starting point of the grid to center it at (center_x, center_y)
    grid_width = (grid_cols - 1) * spacing
    grid_height = (grid_rows - 1) * spacing

    start_x = center_x - grid_width / 2.0
    start_y = center_y - grid_height / 2.0

    positions = []
    orientations = []

    # Place ellipses in grid
    idx = 0
    for i in range(grid_rows):
        for j in range(grid_cols):
            if idx >= N:
                break
            x = start_x + j * spacing + random.uniform(-spacing * 0.1, spacing * 0.1)
            y = start_y + i * spacing + random.uniform(-spacing * 0.1, spacing * 0.1)
            positions.append([x, y])
            # Orientation towards the target location
            dx = target_x - x
            dy = target_y - y
            theta = math.degrees(math.atan2(dy, dx))  # Angle in degrees
            orientations.append(theta)
            idx += 1

    # Precompute static obstacle STRtree
    obstacle_geoms = obstacles
    obstacle_tree = STRtree(obstacle_geoms) if obstacle_geoms else None

    # Now, adjust positions and orientations iteratively
    max_iterations = 200
    for iteration in range(max_iterations):
        # Create shapely polygons for ellipses
        ellipses_polygons = []
        for idx in range(N):
            a, b = ellipses[idx]
            x, y = positions[idx]
            theta = orientations[idx]
            # Create ellipse
            ellipse = Point(0, 0).buffer(1.0, resolution=32)  # unit circle
            ellipse = scale(ellipse, a, b)
            ellipse = rotate(ellipse, theta, use_radians=False)
            ellipse = translate(ellipse, x, y)
            ellipses_polygons.append(ellipse)

        # Build spatial index for ellipses
        ellipse_tree = STRtree(ellipses_polygons)

        overlaps = False

        # Check overlaps with obstacles and adjust positions
        for idx, ellipse in enumerate(ellipses_polygons):
            x, y = positions[idx]

            # Check for overlap with obstacles
            if obstacle_tree:
                possible_obstacle_indices = obstacle_tree.query(ellipse)
                for obstacle_idx in possible_obstacle_indices:
                    obstacle = obstacle_geoms[obstacle_idx]
                    if ellipse.intersects(obstacle):
                        overlaps = True
                        # Move the ellipse away from the obstacle
                        dx = x - obstacle.centroid.x
                        dy = y - obstacle.centroid.y
                        distance = math.hypot(dx, dy)
                        if distance == 0:
                            dx = random.uniform(-1, 1)
                            dy = random.uniform(-1, 1)
                            distance = math.hypot(dx, dy)
                        dx /= distance
                        dy /= distance
                        move_distance = (avg_a + avg_b) * 0.2
                        positions[idx][0] += dx * move_distance
                        positions[idx][1] += dy * move_distance
                        # Update orientation to face target
                        dx_to_target = target_x - positions[idx][0]
                        dy_to_target = target_y - positions[idx][1]
                        orientations[idx] = math.degrees(math.atan2(dy_to_target, dx_to_target))
                        # Update ellipse polygon
                        a_i, b_i = ellipses[idx]
                        theta_i = orientations[idx]
                        ellipse = Point(0, 0).buffer(1.0, resolution=32)
                        ellipse = scale(ellipse, a_i, b_i)
                        ellipse = rotate(ellipse, theta_i, use_radians=False)
                        ellipse = translate(ellipse, positions[idx][0], positions[idx][1])
                        ellipses_polygons[idx] = ellipse

        # Check overlaps between ellipses and adjust positions
        for idx, ellipse in enumerate(ellipses_polygons):
            x, y = positions[idx]
            # Query potential overlaps
            possible_overlap_indices = ellipse_tree.query(ellipse)
            for other_idx in possible_overlap_indices:
                if other_idx == idx:
                    continue
                other_ellipse = ellipses_polygons[other_idx]
                if ellipse.intersects(other_ellipse):
                    overlaps = True
                    # Adjust positions to eliminate overlap
                    x1, y1 = positions[idx]
                    x2, y2 = positions[other_idx]
                    dx = x2 - x1
                    dy = y2 - y1
                    distance = math.hypot(dx, dy)
                    if distance == 0:
                        dx = random.uniform(-1, 1)
                        dy = random.uniform(-1, 1)
                        distance = math.hypot(dx, dy)
                    dx /= distance
                    dy /= distance
                    move_distance = (avg_a + avg_b) * 0.1
                    positions[idx][0] -= dx * move_distance / 2
                    positions[idx][1] -= dy * move_distance / 2
                    positions[other_idx][0] += dx * move_distance / 2
                    positions[other_idx][1] += dy * move_distance / 2
                    # Update orientations to face target
                    for i in [idx, other_idx]:
                        dx_to_target = target_x - positions[i][0]
                        dy_to_target = target_y - positions[i][1]
                        orientations[i] = math.degrees(math.atan2(dy_to_target, dx_to_target))
                        # Update ellipse polygons
                        a_i, b_i = ellipses[i]
                        theta_i = orientations[i]
                        ellipse_i = Point(0, 0).buffer(1.0, resolution=32)
                        ellipse_i = scale(ellipse_i, a_i, b_i)
                        ellipse_i = rotate(ellipse_i, theta_i, use_radians=False)
                        ellipse_i = translate(ellipse_i, positions[i][0], positions[i][1])
                        ellipses_polygons[i] = ellipse_i

        # Rebuild spatial index after adjustments
        ellipse_tree = STRtree(ellipses_polygons)

        # Check for coherency
        all_coherent = True
        for idx, ellipse in enumerate(ellipses_polygons):
            x, y = positions[idx]
            # Query ellipses within coherency distance
            search_area = ellipse.buffer(coherency_distance)
            possible_neighbor_indices = ellipse_tree.query(search_area)
            neighbors = 0
            for neighbor_idx in possible_neighbor_indices:
                if neighbor_idx == idx:
                    continue
                neighbor_ellipse = ellipses_polygons[neighbor_idx]
                if ellipse.distance(neighbor_ellipse) <= coherency_distance:
                    neighbors += 1
            if neighbors < required_neighbors:
                all_coherent = False
                # Adjust position towards center
                dx = center_x - x
                dy = center_y - y
                distance_to_center = math.hypot(dx, dy)
                if distance_to_center > 0:
                    move_distance = (avg_a + avg_b) * 0.1
                    dx /= distance_to_center
                    dy /= distance_to_center
                    positions[idx][0] += dx * move_distance
                    positions[idx][1] += dy * move_distance
                    # Update orientation to face target
                    dx_to_target = target_x - positions[idx][0]
                    dy_to_target = target_y - positions[idx][1]
                    orientations[idx] = math.degrees(math.atan2(dy_to_target, dx_to_target))
                    # Update ellipse polygon
                    a_i, b_i = ellipses[idx]
                    theta_i = orientations[idx]
                    ellipse = Point(0, 0).buffer(1.0, resolution=32)
                    ellipse = scale(ellipse, a_i, b_i)
                    ellipse = rotate(ellipse, theta_i, use_radians=False)
                    ellipse = translate(ellipse, positions[idx][0], positions[idx][1])
                    ellipses_polygons[idx] = ellipse
                    # Check overlap with obstacles after moving
                    if obstacle_tree:
                        possible_obstacle_indices = obstacle_tree.query(ellipse)
                        for obstacle_idx in possible_obstacle_indices:
                            obstacle = obstacle_geoms[obstacle_idx]
                            if ellipse.intersects(obstacle):
                                # Move away from obstacle
                                dx = positions[idx][0] - obstacle.centroid.x
                                dy = positions[idx][1] - obstacle.centroid.y
                                distance = math.hypot(dx, dy)
                                if distance == 0:
                                    dx = random.uniform(-1, 1)
                                    dy = random.uniform(-1, 1)
                                    distance = math.hypot(dx, dy)
                                dx /= distance
                                dy /= distance
                                move_distance = (avg_a + avg_b) * 0.2
                                positions[idx][0] += dx * move_distance
                                positions[idx][1] += dy * move_distance
                                # Update orientation to face target
                                dx_to_target = target_x - positions[idx][0]
                                dy_to_target = target_y - positions[idx][1]
                                orientations[idx] = math.degrees(math.atan2(dy_to_target, dx_to_target))
                                # Update ellipse polygon
                                a_i, b_i = ellipses[idx]
                                theta_i = orientations[idx]
                                ellipse = Point(0, 0).buffer(1.0, resolution=32)
                                ellipse = scale(ellipse, a_i, b_i)
                                ellipse = rotate(ellipse, theta_i, use_radians=False)
                                ellipse = translate(ellipse, positions[idx][0], positions[idx][1])
                                ellipses_polygons[idx] = ellipse

        # Rebuild spatial index after adjustments
        ellipse_tree = STRtree(ellipses_polygons)

        # If no overlaps and all coherent, break
        if not overlaps and all_coherent:
            break

    else:
        print("Warning: Maximum iterations reached without satisfying all constraints.")

    return positions, orientations

# Example usage:
def test_with_target_orientation():
    import matplotlib.pyplot as plt

    # Define ellipses with major and minor radii
    ellipses = [(1.7717, 1.0236)] * 6

    # Define obstacles (e.g., two rectangles)
    obstacle1 = box(-10, -10, -8, 10)
    obstacle2 = box(8, -10, 10, 10)
    obstacles = [obstacle1, obstacle2]

    center_x, center_y = 10, 10
    target_x, target_y = 20, 20  # Target location that ellipses should face
    coherency_distance = 2.0
    required_neighbors = 2
    tightness = 1.5

    positions, orientations = arrange_ellipses(
        ellipses,
        center_x,
        center_y,
        target_x,
        target_y,
        coherency_distance,
        required_neighbors,
        tightness,
        obstacles=obstacles
    )

    # Plotting the ellipses and obstacles
    fig, ax = plt.subplots(figsize=(10, 10))

    # Plot obstacles
    for obstacle in obstacles:
        x, y = obstacle.exterior.xy
        ax.fill(x, y, fc='grey', ec='black', alpha=0.5)

    # Plot ellipses
    for idx, (pos, orient) in enumerate(zip(positions, orientations)):
        a, b = ellipses[idx]
        ellipse = Point(0, 0).buffer(1.0, resolution=32)
        ellipse = scale(ellipse, a, b)
        ellipse = rotate(ellipse, orient, use_radians=False)
        ellipse = translate(ellipse, pos[0], pos[1])
        x, y = ellipse.exterior.xy
        ax.fill(x, y, fc='blue', ec='black', alpha=0.7)
        # Draw a line from ellipse center to target to show orientation
        ax.arrow(pos[0], pos[1],
                 math.cos(math.radians(orient)) * a,
                 math.sin(math.radians(orient)) * a,
                 head_width=0.2, head_length=0.4, fc='red', ec='red')
        # Annotate ellipse number
        ax.text(pos[0], pos[1], str(idx+1), ha='center', va='center', fontsize=12, color='white')

    ax.plot(target_x, target_y, 'ro', markersize=8, label='Target')
    ax.legend()
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 30)
    ax.set_aspect('equal')
    plt.title('Ellipses Facing Target Location with Obstacles')
    plt.show()

if __name__ == "__main__":
    test_with_target_orientation()