# RUINS Terrain System

The RUINS terrain system has been enhanced to support complex multi-level structures with walls, floors, and windows for accurate Warhammer 40k gameplay.

## Overview

RUINS terrain now consists of individual **components** rather than simple obstacles:

- **Walls**: Vertical barriers that may block movement and line of sight
- **Floors**: Horizontal surfaces that models can stand on
- **Windows**: Openings in walls for line of sight calculations

## Components

### RuinsComponent

Each component of a ruins structure is defined by:

```python
class RuinsComponent:
    def __init__(self, vertices, component_type, height, floor_level=0, windows=None):
        self.vertices = vertices           # Polygon defining the component
        self.component_type = component_type  # WALL or FLOOR
        self.height = height              # Height/thickness of component
        self.floor_level = floor_level    # Which floor (0=ground, 1=first, etc.)
        self.windows = windows or []      # List of Window objects (walls only)
        self.z_bottom = ...              # Bottom Z coordinate
        self.z_top = ...                 # Top Z coordinate
```

### Component Types

- **`RuinsComponentType.WALL`**: Vertical barriers
- **`RuinsComponentType.FLOOR`**: Horizontal surfaces

### Windows

Windows are openings in walls defined by:

```python
class Window:
    def __init__(self, start_position, end_position, height_bottom, height_top):
        self.start_position = start_position  # 0.0 to 1.0 along wall
        self.end_position = end_position      # 0.0 to 1.0 along wall  
        self.height_bottom = height_bottom    # Bottom height (inches)
        self.height_top = height_top          # Top height (inches)
```

## Floor Levels

- **Ground Floor**: `floor_level = 0`, Z = 0.0"
- **First Floor**: `floor_level = 1`, Z = 4.0"
- **Second Floor**: `floor_level = 2`, Z = 8.0"
- **etc.**

Each floor level is 4" above the previous level.

## Movement Rules

### Wall Traversal

Only certain unit types can move through walls:

- ✅ **Infantry** units
- ✅ **Beast** units  
- ✅ **Imperium Primarch** units
- ✅ **Belisarius Cawl**
- ❌ **Vehicle** units
- ❌ **Monster** units
- ❌ Other unit types

### Floor Access

All units can move onto floors if they can reach them:

- Models can be positioned on any floor level
- Vertical movement cost applies when climbing between floors
- Flying units can access any floor level freely

## Creating RUINS Terrain

### Simple Method

Use the helper method for basic ruins:

```python
ruins = Obstacle.create_ruins(
    building_footprint=[(0,0), (10,0), (10,10), (0,10)],
    wall_height=4.0,      # Height per floor
    num_floors=1,         # Ground + 1 additional floor
    has_windows=True      # Include windows
)
```

### Custom Method

Create components manually for complex structures:

```python
components = []

# Add floor
floor = RuinsComponent(
    vertices=building_footprint,
    component_type=RuinsComponentType.FLOOR,
    height=0.5,           # Floor thickness
    floor_level=0         # Ground floor
)
components.append(floor)

# Add wall with window
wall = RuinsComponent(
    vertices=[(0,0), (10,0)],  # Wall segment
    component_type=RuinsComponentType.WALL,
    height=4.0,
    floor_level=0,
    windows=[Window(0.3, 0.7, 1.0, 3.0)]  # Window from 30%-70% of wall
)
components.append(wall)

# Create ruins obstacle
ruins = Obstacle(
    vertices=building_footprint,
    terrain_type=ObstacleType.RUINS,
    height=4.0,
    ruins_components=components
)
```

## Line of Sight Integration

Windows provide openings for line of sight calculations:

- **Solid walls**: Block line of sight completely
- **Windows**: Allow line of sight through the opening
- **Window dimensions**: Defined by position along wall and height range
- **Multi-level**: Each floor level can have different window configurations

## Pathfinding Integration

The pathfinding system now considers:

1. **Wall blocking**: Non-Infantry/Beast units cannot path through walls
2. **Floor accessibility**: Models can move onto floors they can reach
3. **Vertical movement**: Cost calculated for climbing between floor levels
4. **Component-level collision**: Each wall/floor component checked individually

## Usage Examples

See `examples/ruins_terrain_example.py` for complete examples of:

- Creating simple ruins buildings
- Creating custom ruins with specific wall/floor layouts
- Adding windows for line of sight
- Testing unit traversal rules
- Multi-level floor access

## Benefits

This enhanced RUINS system provides:

- ✅ **Accurate movement rules** for different unit types
- ✅ **Multi-level gameplay** with proper floor positioning
- ✅ **Line of sight calculations** through windows
- ✅ **Flexible building design** with custom components
- ✅ **Proper vertical movement** cost calculations
- ✅ **Warhammer 40k compliance** with official terrain rules

## 3D visualization and preset ruin example

This project includes a ready-to-use preset ruins piece and a simple 3D preview tool.

- Preset: `TerrainFactory.create_preset_ruin_rect_12x6_variant1()`
  - Footprint: 12" × 6"
  - Wall thickness: 0.5" (all walls fully within the footprint)
  - Walls layout:
    - Long wall along the long edge, inset so its centerline is at y = 0.25"
    - Two short walls at x = 2" and x = 10", each 4" long (y ∈ [0.25", 4.00"]) and joining the long wall at corners
  - Windows (first floor only):
    - Long wall: three 2" windows at x ∈ [3–5], [5–7], [7–9] (centered on y = 0.25")
    - Short walls: one 2" window per short wall at y ∈ [1–3]
  - Floors:
    - Ground (level 0): full 12" × 6" footprint
    - First and second floors: platform is exactly 8" × 4" at x ∈ [2, 10], y ∈ [0.25, 4.00]

### Preview in 3D

Install matplotlib (once):

```bash
pip install matplotlib
```

Run the example preview script:

```bash
python examples/ruins_terrain_example.py
```

You’ll see:

- The preset ruin rendered in 3D (matplotlib mplot3d) with equal X/Y scale so inches look correct
- Walls as solids; windows are cutouts (no glass)
- Floors as slabs; upper floors do not extend beyond the walls
- A unit of five 32 mm models placed on the selected floor (default: first floor), extruded to a simple height

### Programmatic use

```python
from warhammer40k_ai.classes.map import TerrainFactory

ruin = TerrainFactory.create_preset_ruin_rect_12x6_variant1()
# game_map.add_terrain_feature(ruin)
```

To place and visualize 32 mm models on the first floor, see `examples/ruins_terrain_example.py`. It:

- Computes interior as (footprint − walls)
- Constrains placement to the floor platform area
- Ensures no base overlap and uses a staggered (zig‑zag) pattern to fit five models