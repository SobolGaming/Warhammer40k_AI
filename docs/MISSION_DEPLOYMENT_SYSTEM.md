# Official Mission Deployment System

This document describes the implementation of the official Warhammer 40k 10th Edition mission deployment zones and objectives based on Chapter Approved 2025/2026.

## Overview

The new mission system provides:
- **Precise deployment zones** matching official tournament missions
- **Official objective placement** with accurate coordinates  
- **Polygon-based zone detection** for complex deployment shapes
- **Enhanced visualization** with proper colors and zone markings
- **Extensible mission registry** for adding new missions

## Architecture

### Mission Classes

#### `OfficialMission` (Base Class)
- Defines battlefield dimensions (60" × 44" for Strike Force)
- Contains deployment zones and objective markers
- Provides zone checking methods

#### `DeploymentZone`
- Represents polygonal deployment areas
- Uses ray-casting algorithm for point-in-polygon detection
- Supports complex shapes like triangular corners

#### `MissionObjectiveMarker`
- Precise objective placement with coordinates
- Control radius and metadata
- Converted to game objectives during setup

### Mission Registry

The `MissionRegistry` class manages available missions:

```python
# Get available missions
missions = MissionRegistry.get_available_missions()
# ['Crucible of Battle', 'Dawn of War']

# Load a specific mission
mission = MissionRegistry.get_mission("Crucible of Battle")
```

## Implemented Missions

### Crucible of Battle

Based on the official Chapter Approved 2025/2026 layout:

#### Deployment Zones
- **Defender (Green)**: Two triangular corners
  - Bottom-left: (0,0) → (24,0) → (0,18)
  - Top-right: (36,44) → (60,44) → (60,26)
- **Attacker (Red)**: Two triangular corners  
  - Top-left: (0,26) → (0,44) → (24,44)
  - Bottom-right: (36,0) → (60,0) → (60,18)

#### Objectives
- **Center**: (30", 22") - Center of battlefield
- **Southwest**: (12", 12") - Defender area
- **Northeast**: (48", 32") - Defender area
- **Northwest**: (12", 32") - Attacker area
- **Southeast**: (48", 12") - Attacker area

### Dawn of War

Standard opposed deployment:

#### Deployment Zones
- **Defender**: Left 18" zone (0-18" from left edge)
- **Attacker**: Right 18" zone (42-60" from right edge)

#### Objectives
- **West**: (15", 22")
- **Center**: (30", 22") 
- **East**: (45", 22")

## Integration

### Game Setup

The mission system integrates with the existing game setup:

```python
# During battlefield creation
def execute_create_battlefield_phase(self, mission_name: str = "Crucible of Battle"):
    deployment_manager = DeploymentManager(self, mission_name)
    deployment_manager.setup_mission_objectives()
```

### Deployment Manager

Enhanced to use mission-based zones:

```python
deployment_manager = DeploymentManager(game, "Crucible of Battle")
zones = deployment_manager.create_deployment_zones()
```

### Position Checking

Updated game methods support mission zones:

```python
# Check if position is in deployment zone
game.is_position_in_deployment_zone(x, y, player_name)

# Check if model is wholly within zone
game.is_model_wholly_in_deployment_zone(model, player_name)
```

## Visualization

Enhanced UI rendering for mission zones:

- **Polygon rendering** for complex deployment shapes
- **Color coding**: Green (Defender), Red (Attacker)
- **Zone labels** with role identification
- **Objective markers** at precise locations

## Adding New Missions

To add a new mission:

1. **Create mission class** inheriting from `OfficialMission`
2. **Define deployment zones** with vertex coordinates
3. **Set objective markers** with precise positions
4. **Register mission** in `MissionRegistry`

```python
class NewMission(OfficialMission):
    def __init__(self):
        super().__init__("New Mission Name")
        self._setup_deployment_zones()
        self._setup_objectives()
    
    def _setup_deployment_zones(self):
        # Define zones with vertex coordinates
        pass
    
    def _setup_objectives(self):
        # Place objective markers
        pass

# Register the mission
MissionRegistry.register_mission("New Mission", NewMission)
```

## Coordinate System

- **Origin**: Bottom-left corner (0, 0)
- **X-axis**: Horizontal, left to right (0" to 60")
- **Y-axis**: Vertical, bottom to top (0" to 44")
- **Units**: Inches (matching tabletop measurements)

## Testing

The system includes comprehensive tests covering:
- Mission creation and zone definition
- Point-in-polygon detection accuracy
- Game integration and deployment
- Objective placement verification
- Mission registry functionality

## Future Enhancements

Planned improvements:
- Additional Chapter Approved missions
- Dynamic mission selection in UI
- Mission-specific special rules
- Terrain layout integration
- Tournament scenario support

## Files Modified

- `src/warhammer40k_ai/classes/missions.py` - New mission system
- `src/warhammer40k_ai/classes/deployment.py` - Enhanced deployment manager
- `src/warhammer40k_ai/classes/game.py` - Updated position checking
- `src/warhammer40k_ai/UI/game_ui.py` - Enhanced zone visualization

The mission system provides accurate, tournament-legal deployment zones that match the official Warhammer 40k Chapter Approved layouts.
