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
  `RuinsTerrain.traversal_rules` and unit helpers:
  - Breachable set: `INFANTRY`, `BEAST`, `IMPERIUM PRIMARCH`, `BELISARIUS CAWL`
  - These units can move through walls/floors/ceilings as if not there, but can never
    end a move within a wall/floor/ceiling volume.
  - All other units require an opening to pass through wall volumes.
- Floor legality and wall overlap are validated in:
  - `Map.validate_ruins_position`
  - `utility.calcs.can_end_move_on_terrain`

Key rules applied:
- Ground floor: base/hull may be partially within the footprint ("toe-in" is legal) and must
  not overlap walls. Overhang is only restricted on upper floors.
- Upper floors:
  - require `unit.can_access_upper_floors()`
  - base/hull must be within the floor polygon (no overhang permitted)
  - wall overlap is disallowed at the model's Z
- Floor level is resolved via `_resolve_ruins_floor_level` using the model Z.
- "Within" vs "wholly within" uses the footprint polygon:
  - within: any part of base/hull intersects the footprint
  - wholly within: base/hull is fully covered by the footprint

### Low terrain + FLY + Super-Heavy Walker
- Terrain ≤2" is freely passable for all units (no blocking polygons added).
- `FLY` units do not gain the breach-through-walls permission, but may move over walls;
  movement is measured using the shortest path through the air (see `measure_path_distance`).
- Super-Heavy Walker and similar abilities are handled via:
  - `Unit.has_super_heavy_walker()` (raises freely climbable range to 4")
  - `special_rules.move_over_low_terrain_height_value` (per-unit override)
  These affect wall blocking and vertical movement costs.

## Line of sight
`Map.can_model_see_model` now delegates to `src/warhammer40k_ai/battlefield/terrain_visibility.py`, which keeps the stable map-facing API while moving the sampled LOS logic into a dedicated service.

Current ruins-aware LOS behavior remains:
- The footprint blocks outside-to-outside visibility regardless of openings or height
  (unless aircraft are involved).
- Models partially inside the footprint cannot see out unless they are towering.
- Models within the footprint can be seen normally.
- Models wholly within can see out normally; TOWERING models within can also see out.
- Walls block LOS unless an opening with `allows_los` intersects the line segment at the
  relevant height (applies only to valid "normal LOS" cases above).

PR-013 also adds provisional visibility context queries:
- Hidden / detection-range scaffolding
- terrain-area obscuring gating
- deterministic visibility reason traces

Those preview-only Hidden / detection / obscuring area semantics are now explicitly gated by
`Map.preview_visibility_semantics_enabled`. Chapter Approved and other non-preview setups leave
the gate off, while preview-pack battlefield creation can enable it through selected-mission
metadata.

## Benefit of Cover and Plunging Fire
- Benefit of Cover for RUINS and fortification-derived cover now route through
  `src/warhammer40k_ai/battlefield/terrain_cover.py`.
- The live engine still keeps current cover behavior in save-bonus compatibility mode until PR-015.
- Surface-height queries and Plunging Fire scaffolding now route through
  `src/warhammer40k_ai/battlefield/terrain_elevation.py`.
- `WargearProfile._plunging_fire_applies` now consumes the map/elevation query context instead of
  owning the geometry logic directly.


## Files
- `src/warhammer40k_ai/battlefield/map.py`
- `src/warhammer40k_ai/battlefield/terrain_presets.py`
- `src/warhammer40k_ai/battlefield/terrain_ruins_placement.py`
- `src/warhammer40k_ai/battlefield/terrain_visibility.py`
- `src/warhammer40k_ai/battlefield/terrain_cover.py`
- `src/warhammer40k_ai/battlefield/terrain_elevation.py`
- `src/warhammer40k_ai/utility/calcs.py`
- `src/warhammer40k_ai/utility/constants.py`
