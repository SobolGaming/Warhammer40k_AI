#!/usr/bin/env python3
"""
Example for generating and visualizing preset RUINS pieces (including low rubble variants).
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from warhammer40k_ai.classes.map import TerrainFactory
from warhammer40k_ai.classes.terrain_layouts import instantiate_layout
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
    # Display with (0,0) at upper-left: invert Y axis direction
    ax.set_ylim(bymax + 1, bymin - 1)
    # Z limit: use ruins bounding box
    ax.set_zlim(0, ruin.bounding_box["max"][2] + 1)
    ax.set_xlabel('X (inches)')
    ax.set_ylabel('Y (inches)')
    ax.set_zlabel('Z (inches)')
    ax.set_title(title)

    # Enforce 1:1:1 scaling in data units (1 inch looks the same in X/Y/Z)
    x_range = (bxmax - bxmin) + 2.0
    y_range = (bymax - bymin) + 2.0
    z_range = float(ruin.bounding_box["max"][2]) + 1.0
    try:
        ax.set_box_aspect((x_range, y_range, z_range))
    except Exception:
        # Older matplotlib: best-effort fallback (XY equal only via limits)
        max_range = max(x_range, y_range)
        x_mid = (bxmax + bxmin) / 2.0
        y_mid = (bymax + bymin) / 2.0
        ax.set_xlim(x_mid - max_range/2, x_mid + max_range/2)
        # Preserve inverted Y while equalizing span
        ax.set_ylim(y_mid + max_range/2, y_mid - max_range/2)
    plt.tight_layout()
    plt.show()


def visualize_battlefield_layout_3d(layout_id: int, title: str | None = None, show_grid: bool = True):
    """Visualize a full 60\"x44\" battlefield layout in 3D with a 1\" grid."""
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from shapely.geometry import Polygon, MultiPolygon
    from shapely.ops import unary_union

    features = instantiate_layout(layout_id)

    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')

    def draw_prism(poly, z0: float, z1: float, color: str, alpha: float = 0.5):
        if isinstance(poly, MultiPolygon):
            for sub in poly.geoms:
                draw_prism(sub, z0, z1, color, alpha)
            return
        if not isinstance(poly, Polygon):
            return
        x, y = poly.exterior.xy
        verts = list(zip(x, y))
        faces = []
        for i in range(len(verts) - 1):
            x0, y0 = verts[i]
            x1, y1 = verts[i + 1]
            faces.append([(x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1)])
        top = [(vx, vy, z1) for vx, vy in verts]
        bottom = [(vx, vy, z0) for vx, vy in verts]
        faces.append(top)
        faces.append(bottom)
        pc = Poly3DCollection(faces, facecolors=color, linewidths=0.3, edgecolors='k', alpha=alpha)
        ax.add_collection3d(pc)

    # Battlefield base plane at z=0
    board_poly = Polygon([(0.0, 0.0), (60.0, 0.0), (60.0, 44.0), (0.0, 44.0)])
    draw_prism(board_poly, 0.0, 0.02, color="#f0f0f0", alpha=0.25)

    # 1" grid lines (drawn slightly above the plane)
    if show_grid:
        z = 0.03
        grid_color = "#aaaaaa"
        for x in range(0, 61):
            ax.plot([x, x], [0, 44], [z, z], color=grid_color, linewidth=0.4, alpha=0.35)
        for y in range(0, 45):
            ax.plot([0, 60], [y, y], [z, z], color=grid_color, linewidth=0.4, alpha=0.35)

        # Mid-lines (thicker/darker): x=30 and y=22
        mid_z = z + 0.005
        ax.plot([30, 30], [0, 44], [mid_z, mid_z], color="#111111", linewidth=2.0, alpha=0.85)
        ax.plot([0, 60], [22, 22], [mid_z, mid_z], color="#111111", linewidth=2.0, alpha=0.85)

    # Draw terrain features (RUINS get walls/floors; others get a footprint prism)
    for feat in features:
        if getattr(feat, "terrain_type", None) and str(getattr(feat, "terrain_type")).endswith("RUINS"):
            ruin = feat
            # Floors
            for floor in getattr(ruin, "floors", []) or []:
                draw_prism(
                    floor["polygon"],
                    float(floor.get("elevation", 0.0)),
                    float(floor.get("elevation", 0.0) + floor.get("thickness", 0.5)),
                    color="#8da0cb",
                    alpha=0.30,
                )

            # Walls (with opening cutouts)
            for wall in getattr(ruin, "walls", []) or []:
                wall_poly = wall["polygon"]
                z0, z1 = float(wall["z_bottom"]), float(wall["z_top"])

                relevant = []
                z_cuts = {z0, z1}
                for op in getattr(ruin, "openings", []) or []:
                    if (float(op["z_top"]) > z0 and float(op["z_bottom"]) < z1) and wall_poly.buffer(1e-6).intersects(op["polygon"]):
                        relevant.append(op)
                        z_cuts.add(max(z0, float(op["z_bottom"])))
                        z_cuts.add(min(z1, float(op["z_top"])))
                z_slices = sorted(z_cuts)

                for a, b in zip(z_slices[:-1], z_slices[1:]):
                    if b - a <= 1e-6:
                        continue
                    slice_poly = wall_poly
                    active = [op["polygon"] for op in relevant if not (float(op["z_top"]) <= a or float(op["z_bottom"]) >= b)]
                    if active:
                        slice_poly = slice_poly.difference(unary_union(active))
                    draw_prism(slice_poly, a, b, color="#fc8d62", alpha=0.55)
        else:
            # Fallback: just extrude the footprint slightly so it's visible
            draw_prism(getattr(feat, "footprint", board_poly), 0.0, 0.5, color="#bdbdbd", alpha=0.35)

    ax.set_xlim(0, 60)
    # Display with (0,0) at upper-left: invert Y axis direction
    ax.set_ylim(44, 0)
    # Z limit: infer from features
    max_z = 0.0
    for feat in features:
        try:
            max_z = max(max_z, float(feat.bounding_box["max"][2]))
        except Exception:
            pass
    z_lim = max(6.0, max_z + 1.0)
    ax.set_zlim(0, z_lim)
    ax.set_xlabel("X (inches)")
    ax.set_ylabel("Y (inches)")
    ax.set_zlabel("Z (inches)")
    ax.set_title(title or f"Battlefield Layout {layout_id} (60x44)")

    # Enforce 1:1:1 scaling in data units (1 inch looks the same in X/Y/Z)
    try:
        ax.set_box_aspect((60.0, 44.0, float(z_lim)))
    except Exception:
        pass

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
    # Some presets (e.g. low rubble) only have ground floor; clamp gracefully.
    target_elev = float(floor_level) * 4.0
    floor = None
    for fl in ruin.floors:
        if abs(float(fl.get("elevation", 0.0)) - target_elev) < 1e-6:
            floor = fl
            break
    if floor is None:
        # Fall back to the lowest floor (usually elevation 0)
        if not ruin.floors:
            return []
        floor = sorted(ruin.floors, key=lambda f: float(f.get("elevation", 0.0)))[0]
        floor_level = int(round(float(floor.get("elevation", 0.0)) / 4.0))
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
    parser = argparse.ArgumentParser(description='Visualize preset RUINS variants or full battlefield layouts')
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        '--preset',
        choices=['variant1', 'variant2', 'variant3', 'variant4', 'variant5', 'rubble6x4', 'ruin10x5'],
        default=None,
        help='Visualize a single preset ruin'
    )
    group.add_argument(
        '--layout',
        type=int,
        choices=list(range(1, 9)),
        default=None,
        help='Visualize a full 60x44 battlefield using a preset terrain layout id (1-8)'
    )
    parser.add_argument('--floor', type=int, default=1, help='Floor level to place example models (0,1,2). For rubble6x4, this is clamped to ground.')
    parser.add_argument('--models', type=int, default=5, help='Number of example models to place (preset mode only)')
    parser.add_argument('--no-grid', action='store_true', help='Disable 1" grid in layout mode')
    args = parser.parse_args()

    # Layout mode
    if args.layout is not None:
        visualize_battlefield_layout_3d(args.layout, show_grid=(not args.no_grid))
        return

    # Default to preset mode if nothing specified
    preset = args.preset or 'variant1'

    # Create selected preset ruin
    if preset == 'rubble6x4':
        ruin = TerrainFactory.create_preset_ruin_rect_6x4_variant1()
    elif preset == 'ruin10x5':
        ruin = TerrainFactory.create_preset_ruin_rect_10x5_variant1()
    elif preset == 'variant4':
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant4()
    elif preset == 'variant5':
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant5()
    elif preset == 'variant3':
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant3()
    elif preset == 'variant2':
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant2()
    else:
        ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant1()

    # Place example models on requested floor
    models = place_unit_in_ruin(ruin, num_models=args.models, base_mm=32, floor_level=args.floor, model_height_in=2.0)

    # Visualize with dynamic title
    bxmin, bymin, bxmax, bymax = ruin.footprint.bounds
    size_lbl = f'{(bxmax-bxmin):.0f}"x{(bymax-bymin):.0f}"'
    visualize_ruin_3d(ruin, models=models, title=f'Preset RUINS {size_lbl} ({preset})')


if __name__ == "__main__":
    main()
