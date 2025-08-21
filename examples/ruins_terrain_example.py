#!/usr/bin/env python3
"""
Example for generating and visualizing a preset 12"x6" RUINS piece with specific walls/windows.
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from warhammer40k_ai.classes.map import TerrainFactory
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.utility.calcs import convert_mm_to_inches
from shapely.geometry import Polygon

def visualize_ruin_3d(ruin, models=None, title: str = 'Preset 12"x6" RUINS'):
    """Visualize a RuinsTerrain in 3D using matplotlib (simple prism rendering)."""
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')

    def draw_prism(ax, poly, z0: float, z1: float, color: str, alpha: float = 0.5):
        from shapely.geometry import Polygon, MultiPolygon
        if isinstance(poly, MultiPolygon):
            for sub in poly.geoms:
                draw_prism(ax, sub, z0, z1, color, alpha)
            return
        if not isinstance(poly, Polygon):
            return
        x, y = poly.exterior.xy
        verts = list(zip(x, y))
        faces = []
        # Side faces around exterior ring
        for i in range(len(verts) - 1):
            x0, y0 = verts[i]
            x1, y1 = verts[i + 1]
            faces.append([(x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1)])
        # Top and bottom faces (exterior only)
        top = [(vx, vy, z1) for vx, vy in verts]
        bottom = [(vx, vy, z0) for vx, vy in verts]
        faces.append(top)
        faces.append(bottom)
        pc = Poly3DCollection(faces, facecolors=color, linewidths=0.5, edgecolors='k', alpha=alpha)
        ax.add_collection3d(pc)

    # Draw footprint floor slabs (upper floors clipped to interior)
    for floor in ruin.floors:
        draw_prism(ax, floor["polygon"], floor["elevation"], floor["elevation"] + floor.get("thickness", 0.5), color='#8da0cb', alpha=0.4)

    # Draw walls with window cutouts, preserving wall above and below windows by slicing vertically
    from shapely.ops import unary_union
    for wall in ruin.walls:
        wall_poly = wall["polygon"]
        z0, z1 = wall["z_bottom"], wall["z_top"]

        # Gather relevant openings (overlap vertically and intersect in 2D)
        relevant = []
        z_cuts = {z0, z1}
        for op in ruin.openings:
            if (op["z_top"] > z0 and op["z_bottom"] < z1) and (wall_poly.buffer(1e-6).intersects(op["polygon"])):
                relevant.append(op)
                z_cuts.add(max(z0, op["z_bottom"]))
                z_cuts.add(min(z1, op["z_top"]))
        z_slices = sorted(z_cuts)

        # Render each vertical slice, subtracting openings only within that slice
        for a, b in zip(z_slices[:-1], z_slices[1:]):
            if b - a <= 1e-6:
                continue
            slice_poly = wall_poly
            # Openings active in this slice
            active = [op["polygon"] for op in relevant if not (op["z_top"] <= a or op["z_bottom"] >= b)]
            if active:
                slice_poly = slice_poly.difference(unary_union(active))
            draw_prism(ax, slice_poly, a, b, color='#fc8d62', alpha=0.7)

    # Do not draw openings; they are holes in walls, not glass

    # Draw models (extruded bases)
    if models:
        for base in models:
            poly = base.get_base_shape()
            draw_prism(ax, poly, base.z, base.z + base.model_height, color='#1b9e77', alpha=0.8)

    # Axes limits and labels
    bxmin, bymin, bxmax, bymax = ruin.footprint.bounds
    ax.set_xlim(bxmin - 1, bxmax + 1)
    ax.set_ylim(bymin - 1, bymax + 1)
    # Z limit: use ruins bounding box
    ax.set_zlim(0, ruin.bounding_box["max"][2] + 1)
    ax.set_xlabel('X (inches)')
    ax.set_ylabel('Y (inches)')
    ax.set_zlabel('Z (inches)')
    ax.set_title(title)

    # Enforce equal XY scale so inches look equal in both axes
    # Matplotlib 3D doesn't have set_aspect('equal') directly; emulate via limits
    x_range = (bxmax - bxmin) + 2
    y_range = (bymax - bymin) + 2
    max_range = max(x_range, y_range)
    x_mid = (bxmax + bxmin) / 2.0
    y_mid = (bymax + bymin) / 2.0
    ax.set_xlim(x_mid - max_range/2, x_mid + max_range/2)
    ax.set_ylim(y_mid - max_range/2, y_mid + max_range/2)
    plt.tight_layout()
    plt.show()


def place_unit_in_ruin(ruin, num_models=5, base_mm=32, floor_level=0, model_height_in=2.0):
    """Place models legally inside the ruin interior on a given floor.
    Ensures: inside interior, no overlap, 2" coherency chain.
    """
    from shapely.ops import unary_union
    from shapely.affinity import translate

    # Base radius in inches (circular 32mm base)
    radius_in = convert_mm_to_inches(base_mm / 2.0)
    spacing_gap = 0.01  # edge-to-edge gap between bases
    center_step = 2*radius_in + spacing_gap

    # Interior polygon (footprint minus walls)
    walls_union = unary_union([w["polygon"] for w in ruin.walls])
    interior = ruin.footprint.difference(walls_union)

    # Floor elevation and platform area (upper floors are smaller than footprint)
    floor = next(fl for fl in ruin.floors if abs(fl["elevation"] - floor_level*4.0) < 1e-6)
    z_base = floor["elevation"] + floor.get("thickness", 0.5)
    # If a higher floor exists, ensure model height fits fully between floors; otherwise, disallow placement
    higher_floors = sorted([fl for fl in ruin.floors if fl["elevation"] > floor["elevation"]], key=lambda f: f["elevation"])
    if higher_floors:
        next_floor = higher_floors[0]
        clearance = (next_floor["elevation"]) - (floor["elevation"] + floor.get("thickness", 0.5))
        if model_height_in >= clearance - 1e-3:
            return []
    placement_area = interior.intersection(floor["polygon"])  # constrain to floor platform
    # Shrink to safe area so a circular base fits fully inside without boundary tolerance issues
    # Safe area: floor platform minus walls with a tiny inward epsilon only
    safe_area = placement_area.buffer(-1e-6)

    placed = []
    bxmin, bymin, bxmax, bymax = safe_area.bounds
    row_idx = 0
    y = bymin
    while y <= bymax and len(placed) < num_models:
        # Zig-zag: offset every other row by one radius
        x = bxmin + (radius_in if (row_idx % 2 == 1) else 0.0)
        while x <= bxmax and len(placed) < num_models:
            b = Base(BaseType.CIRCULAR, radius_in)
            b.set_position(x, y, z_base)
            b.set_model_height(model_height_in)
            shape = b.get_base_shape()
            if not safe_area.contains(shape):
                x += center_step
                continue
            # Check overlap with already placed
            overlap = False
            for other in placed:
                # Disallow intersections; allow tiny numerical tolerance
                if shape.buffer(-1e-6).intersects(other.get_base_shape().buffer(-1e-6)):
                    overlap = True
                    break
            if overlap:
                x += center_step
                continue
            placed.append(b)
            x += center_step
        y += center_step
        row_idx += 1

    return placed


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Visualize preset 12x6 RUINS variants')
    parser.add_argument('--preset', choices=['variant1', 'variant2', 'variant3'], default='variant1', help='Which preset to visualize')
    parser.add_argument('--floor', type=int, default=1, help='Floor level to place example models (0,1,2)')
    parser.add_argument('--models', type=int, default=5, help='Number of example models to place')
    args = parser.parse_args()

    # Create selected preset ruin
    if args.preset == 'variant3':
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant3()
    elif args.preset == 'variant2':
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant2()
    else:
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant1()

    # Place example models on requested floor
    models = place_unit_in_ruin(ruin, num_models=args.models, base_mm=32, floor_level=args.floor, model_height_in=2.0)

    # Visualize with dynamic title
    visualize_ruin_3d(ruin, models=models, title=f'Preset 12"x6" RUINS ({args.preset})')


if __name__ == "__main__":
    main()
