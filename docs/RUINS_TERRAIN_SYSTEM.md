# RUINS Terrain System

## Overview
RUINS are modeled as explicit 3D terrain with walls, floors, and openings. The engine uses these
components for movement validation, collision, and line-of-sight checks.

## Data model (`RuinsTerrain`)
Defined in `src/warhammer40k_ai/battlefield/map.py`.

- `footprint`: Shapely polygon for the ground outline
- `walls`: list of dicts with:
  - `polygon` (Shapely polygon)
  - `z_bottom`, `z_top`
  - `thickness`
- `openings`: list of dicts with:
  - `polygon`
  - `z_bottom`, `z_top`
  - `allows_movement`, `allows_los`
- `floors`: list of dicts with:
  - `polygon`
  - `elevation`
  - `thickness`

Constants live in `src/warhammer40k_ai/utility/constants.py`:
- `RUINS_FLOOR_HEIGHT`
- `RUINS_FLOOR_THICKNESS`
- `RUINS_WALL_THICKNESS`

## Creation helpers
`TerrainFactory` builds RUINS in `src/warhammer40k_ai/battlefield/map.py`:

- `create_ruins(footprint_vertices, wall_height, num_floors, has_windows, has_doors)`
  - Builds perimeter walls, floors for each level, and optional windows/doors.
- `create_preset_ruin_rect_*` presets for common tournament-sized ruins (12x6, 6x4, 10x5).

Example:
```python
from warhammer40k_ai.battlefield.map import TerrainFactory

ruins = TerrainFactory.create_ruins(
    footprint_vertices=[(0, 0), (12, 0), (12, 6), (0, 6)],
    wall_height=3.0,
    num_floors=2,
    has_windows=True,
    has_doors=True,
)
```

## Movement and placement
- Collision and blocking polygons are computed via
  `warhammer40k_ai.utility.calcs.get_terrain_blocking_polygons`.
- `RuinsTerrain.can_unit_move_through` enforces wall traversal rules, using
  `RuinsTerrain.traversal_rules` (infantry/beast pass; vehicle/monster/titanic/flying blocked
  unless an opening allows movement).
- Floor legality and wall overlap are validated in:
  - `Map.validate_ruins_position`
  - `utility.calcs.can_end_move_on_terrain`

Key rules applied:
- Ground floor: base must not overhang the footprint and must not overlap walls.
- Upper floors:
  - require `unit.can_access_upper_floors()`
  - base must be within the floor polygon unless `unit.can_overhang_floor()`
  - wall overlap is disallowed at the model's Z
- Floor level is resolved via `_resolve_ruins_floor_level` using the model Z.

## Line of sight
`Map.can_model_see_model` applies ruins-aware LOS:
- The footprint blocks outside-to-outside visibility unless aircraft are involved.
- Models partially inside the footprint cannot see out unless they are towering.
- Walls block LOS unless an opening with `allows_los` intersects the line segment at the
  relevant height.

## Files
- `src/warhammer40k_ai/battlefield/map.py`
- `src/warhammer40k_ai/utility/calcs.py`
- `src/warhammer40k_ai/utility/constants.py`
