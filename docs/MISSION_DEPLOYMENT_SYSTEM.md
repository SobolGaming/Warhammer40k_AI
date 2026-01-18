# Mission Deployment System

## Overview
Missions are defined as polygonal deployment zones with objective marker placements. The system
uses mission data to build deployment zones, create objectives, and validate deployment placement.

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
- `Game.execute_create_battlefield_phase` reads `game.selected_mission_info` and chooses:
  - deployment mission name
  - terrain layout
  - primary mission name
- `DeploymentManager.create_deployment_zones` returns compound zone dicts with
  `mission_zones` (polygon zones + cutouts).
- `DeploymentManager.setup_mission_objectives` uses `create_objectives_from_mission` to add
  objectives to the map.
- `Game._apply_primary_mission_setup_rules` applies primary-specific objective edits (e.g.,
  Hidden Supplies, Supply Drop).
- `Game.is_position_in_deployment_zone` and related helpers only support mission polygon zones;
  rectangular zones are not supported.

## Files
- `src/warhammer40k_ai/engine/missions.py`
- `src/warhammer40k_ai/engine/deployment.py`
- `src/warhammer40k_ai/engine/game.py`
- `src/warhammer40k_ai/battlefield/terrain_layouts.py`
