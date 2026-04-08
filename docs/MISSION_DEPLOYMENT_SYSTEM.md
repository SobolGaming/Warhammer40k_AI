# Mission Deployment System

## Overview
Mission selection is now split into two layers:

- a mission-pack compiler that determines which mission entries are legal for the current armies
- deployment/runtime logic that turns the selected entry into zones, terrain layout, and objectives

This keeps Chapter Approved 2025-26 supported as the current matched-play default while also
allowing additional provisional mission packs to appear when the armies expose compatible
Force Dispositions.

The deployment layer still uses polygonal mission data to build deployment zones, create
objectives, and validate placement.

## Objective-site runtime model
Objective runtime is no longer treated as "marker circle only" at the engine boundary.

The battlefield layer now separates:

- `ObjectiveSite`: the site/anchor geometry
- `ControlRegion`: the space used for control checks
- `ScoreSource`: the scoring surface bound to that site

Current site styles:

- marker objective sites
- terrain-footprint objective sites
- keyed-feature objective sites
- terrain-bound objective identifiers via `terrain_area_id` and `layout_slot_id`

Default Chapter Approved missions still instantiate marker sites, but state blobs,
descriptors, and snapshots now preserve the richer site/control/scoring split so
terrain-footprint or keyed-feature missions can be added without reworking those schemas again.

PR-012 also introduces a separate runtime `terrain_areas` collection alongside `terrain_features`.
Explicit authored terrain areas are serialized directly, while feature-only battlefields can still
expose provisional adapter-backed terrain areas derived from existing terrain footprints for
descriptor/state compatibility work.

## Mission-pack compiler
Defined in `src/warhammer40k_ai/engine/mission_selection.py`:

- `ForceDisposition`
- `MissionPack`
- `MissionPairing`
- `MissionDefinition`
- `DeploymentDefinition`
- `TwistDefinition`
- `SecondaryRuleSet`

Current pack behavior:

- `chapter_approved_2025_2026`
  - default pack
  - used by server/local auto-random mission selection
  - preserves the current Chapter Approved A-T rotation
- `provisional_11e_preview`
  - optional preview-era pack
  - only appears when both armies expose matching force dispositions
  - now uses the April 3, 2026 five-Force-Disposition catalog
  - pairing-owned recommended terrain layouts override deployment-default layout lists
  - carries explicit preview visibility activation metadata for terrain Hidden/Obscuring scaffolding
  - remains explicitly provisional and twist-stubbed

## Mission model
Defined in `src/warhammer40k_ai/engine/missions.py`:
- `OfficialMission` base class
- `DeploymentZone` polygon with optional cutouts
- `ZoneCutout` (circle/rectangle/polygon)
- `MissionObjectiveMarker`
- `MissionRegistry` for lookup and registration

`DeploymentZone.contains_point` uses a ray-casting test, while `contains_circular_base` and
`contains_polygon_base` use Shapely to ensure bases are wholly within the zone and not overlapping
cutouts.

## Coordinate system
- Origin: top-left corner `(0, 0)`
- X axis: left to right (0" to 60")
- Y axis: top to bottom (0" to 44")

## Implemented missions
Current missions in `MissionRegistry`:
- Crucible of Battle
- Dawn of War
- Hammer and Anvil
- Tipping Point
- Search and Destroy (includes a 9" radius center cutout)
- Sweeping Engagement

Deployment zone vertices and objective marker coordinates are encoded directly in each mission
class (see `engine/missions.py`).

## Integration
- `Game.request_mission_selection` compiles the visible mission catalog from the current players'
  force dispositions.
- `Game.execute_select_mission_objectives_phase` defaults through the mission-pack compiler when
  no explicit choice has been made yet.
- `Game.execute_create_battlefield_phase` reads `game.selected_mission_info` and chooses:
  - deployment mission name
  - terrain layout
  - primary mission name
- `deployment_flow.selected_deployment_plan` converts `selected_mission_info` into a validated
  deployment plan with mission-pack and secondary/twist metadata.
- `battlefield/terrain_layouts.py` remains the stable façade for integer layout ids, but now
  delegates to:
  - `battlefield/terrain_area_templates.py`
  - `battlefield/terrain_layout_recipes.py`
  - `battlefield/terrain_feature_renderers.py`
- `DeploymentManager.create_deployment_zones` returns compound zone dicts with
  `mission_zones` (polygon zones + cutouts).
- `DeploymentManager.setup_mission_objectives` uses `create_objectives_from_mission` to add
  objectives to the map.
- Objective/control runtime now flows through:
  - `battlefield/objective_sites.py`
  - `battlefield/control_queries.py`
  - `battlefield/map_geometry.py`
  - `battlefield/terrain_runtime.py`
- `Game._apply_primary_mission_setup_rules` applies primary-specific objective edits (e.g.,
  Hidden Supplies, Supply Drop).
- `Game.is_position_in_deployment_zone` and related helpers only support mission polygon zones;
  rectangular zones are not supported.

## Files
- `src/warhammer40k_ai/engine/mission_selection.py`
- `src/warhammer40k_ai/engine/missions.py`
- `src/warhammer40k_ai/engine/deployment.py`
- `src/warhammer40k_ai/engine/deployment_flow.py`
- `src/warhammer40k_ai/engine/deployment_validation.py`
- `src/warhammer40k_ai/engine/deployment_types.py`
- `src/warhammer40k_ai/engine/deployment_candidates.py`
- `src/warhammer40k_ai/engine/deployment_heuristics.py`
- `src/warhammer40k_ai/engine/game.py`
- `src/warhammer40k_ai/battlefield/objective_sites.py`
- `src/warhammer40k_ai/battlefield/control_queries.py`
- `src/warhammer40k_ai/battlefield/map_geometry.py`
- `src/warhammer40k_ai/battlefield/terrain_runtime.py`
- `src/warhammer40k_ai/battlefield/terrain_area_templates.py`
- `src/warhammer40k_ai/battlefield/terrain_layout_recipes.py`
- `src/warhammer40k_ai/battlefield/terrain_feature_renderers.py`
- `src/warhammer40k_ai/battlefield/terrain_layouts.py`
