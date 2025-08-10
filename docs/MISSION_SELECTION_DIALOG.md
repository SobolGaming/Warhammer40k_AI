# Mission Selection Dialog - Chapter Approved 2025/2026

This document describes the implementation of the Mission Selection Dialog for the SELECT_MISSION_OBJECTIVES setup phase, displaying all approved mission combinations from Chapter Approved 2025/2026.

## Overview

The Mission Selection Dialog provides a comprehensive interface for selecting official tournament-approved mission combinations including:
- **Primary Mission types** (Take and Hold, Supply Drop, etc.)
- **Deployment patterns** (Crucible of Battle, Hammer and Anvil, etc.)
- **Terrain Layouts** (Layout 1-8 as approved combinations)

## Features

### 📋 **Complete Mission Database**
All 20 approved combinations (A-T) from Chapter Approved 2025/2026:
- **A-D**: Tipping Point missions (6 terrain layouts each)
- **E-H**: Hammer and Anvil missions (3 terrain layouts each)
- **I-L**: Search and Destroy missions (5 terrain layouts each)
- **M-P**: Crucible of Battle missions (5 terrain layouts each)
- **Q-R**: Sweeping Engagement missions (2 terrain layouts each)
- **S-T**: Dawn of War missions (1 terrain layout each)

### 🎨 **User Interface**
- **Scrollable table** with mission combinations
- **Interactive terrain layout buttons** for each combination
- **"Pick Random" button** for instant random selection from all A-T combinations
- **Visual selection feedback** with color coding
- **Mouse and keyboard navigation** support
- **Real-time selection status** display

### ⌨️ **Controls**
- **Mouse**: Click combinations and terrain layouts
- **Keyboard**: Arrow keys to scroll, Enter to confirm, Escape to cancel, **R for random**
- **Mouse wheel**: Scroll through mission list
- **Buttons**: Cancel/**Pick Random**/Confirm with visual feedback

## Technical Implementation

### Class Structure

```python
class MissionSelectionDialog(BaseDialog):
    # Official Chapter Approved 2025/2026 combinations
    APPROVED_COMBINATIONS = [...]  # 20 mission combinations A-T
    
    def __init__(self, screen_width, screen_height)
    def handle_event(self, event) -> Optional[Dict]
    def pick_random_mission(self)  # Randomly select combination and layout
    def draw(self, screen: pygame.Surface)
```

### Random Selection Feature

The "Pick Random" functionality provides:
- **Random combination**: Selects from all 20 approved combinations (A-T)
- **Random terrain layout**: Chooses from available layouts for the selected combination
- **Instant feedback**: Immediately highlights the selected combination and layout
- **Equal probability**: Each combination has equal chance of selection
- **Layout distribution**: Respects the approved terrain layouts for each combination

**Usage:**
- Click the purple "Pick Random" button
- Press 'R' key for keyboard shortcut
- Combination and layout are instantly selected and highlighted

### Mission Data Format

Each mission combination contains:
```python
{
    "id": "A",                           # Letter ID (A-T)
    "primary": "Take and Hold",          # Primary mission name
    "deployment": "Tipping Point",       # Deployment pattern
    "layouts": [1, 2, 4, 6, 7, 8]      # Approved terrain layouts
}
```

### Return Values

When confirmed, the dialog returns:
```python
{
    "action": "confirm",
    "combination": {
        "id": "A",
        "primary": "Take and Hold", 
        "deployment": "Tipping Point",
        "layouts": [1, 2, 4, 6, 7, 8]
    },
    "layout": 1  # Selected terrain layout number
}
```

## Integration with Game Setup

### Setup Phase Integration

The dialog integrates with the `SELECT_MISSION_OBJECTIVES` phase:

```python
# In game.py
def execute_select_mission_objectives_phase(self):
    # Dialog sets self.selected_mission_info with:
    # {"combination_id": "M", "primary": "...", "deployment": "...", "layout": N}
    
def execute_create_battlefield_phase(self):
    # Uses selected_mission_info to configure:
    # - Deployment zones via DeploymentManager
    # - Terrain layout via _create_terrain_layout()
    # - Mission objectives
```

### UI Integration

**Automatic Dialog Display**: When pressing Space during SELECT_MISSION_OBJECTIVES phase, the dialog automatically appears

**Visual Feedback**: Selected mission information is displayed in the info panel showing:
- Mission ID (A-T)
- Primary mission name  
- Deployment pattern
- Terrain layout number

**User Flow**:
1. Press Space during SELECT_MISSION_OBJECTIVES phase
2. Mission Selection Dialog opens
3. Choose combination and terrain layout (or use "Pick Random")
4. Confirm selection
5. Dialog closes and phase advances
6. Mission info visible in info panel throughout game

### Mission Application

Selected mission affects:
1. **Deployment zones**: Uses correct deployment pattern
2. **Terrain layout**: Applies approved terrain configuration
3. **Objectives**: Places mission-appropriate objective markers
4. **Primary mission**: Sets scoring and victory conditions

## Visual Design

### Color Scheme
- **Background**: Dark theme (30, 30, 40)
- **Selected combination**: Blue highlight (50, 120, 200)
- **Selected layout**: Green highlight (100, 200, 100)
- **Hover effects**: Subtle gray (60, 60, 80)
- **Text**: High contrast white/gray

### Layout Elements
- **Header**: Column titles for ID, Primary, Deployment, Layouts
- **Scrollable content**: Mission combinations with layout buttons
- **Status bar**: Shows current selection
- **Action buttons**: Cancel (red) / Confirm (green)

## Usage Example

```python
# Create dialog
mission_dialog = MissionSelectionDialog(screen_width, screen_height)

# Handle events in main loop
result = mission_dialog.handle_event(event)

if result and result["action"] == "confirm":
    # Apply selection to game
    game.selected_mission_info = {
        "primary": result["combination"]["primary"],
        "deployment": result["combination"]["deployment"], 
        "layout": result["layout"]
    }
```

## Mission Combinations Reference

| ID | Primary Mission | Deployment | Terrain Layouts |
|----|----------------|------------|-----------------|
| A | Take and Hold | Tipping Point | 1, 2, 4, 6, 7, 8 |
| B | Supply Drop | Tipping Point | 1, 2, 4, 6, 7, 8 |
| C | Linchpin | Tipping Point | 1, 2, 4, 6, 7, 8 |
| D | Scorched Earth | Tipping Point | 1, 2, 4, 6, 7, 8 |
| E | Take and Hold | Hammer and Anvil | 1, 7, 8 |
| F | Hidden Supplies | Hammer and Anvil | 1, 7, 8 |
| G | Purge the Foe | Hammer and Anvil | 1, 7, 8 |
| H | Supply Drop | Hammer and Anvil | 1, 7, 8 |
| I | Hidden Supplies | Search and Destroy | 1, 2, 3, 4, 6 |
| J | Linchpin | Search and Destroy | 1, 2, 3, 4, 6 |
| K | Scorched Earth | Search and Destroy | 1, 2, 3, 4, 6 |
| L | Take and Hold | Search and Destroy | 1, 2, 3, 4, 6 |
| M | Purge the Foe | Crucible of Battle | 1, 2, 3, 4, 6 |
| N | Hidden Supplies | Crucible of Battle | 1, 2, 3, 4, 6 |
| O | Terraform | Crucible of Battle | 1, 2, 3, 4, 6 |
| P | Scorched Earth | Crucible of Battle | 1, 2, 3, 4, 6 |
| Q | Supply Drop | Sweeping Engagement | 3, 5 |
| R | Terraform | Sweeping Engagement | 3, 5 |
| S | Linchpin | Dawn of War | 5 |
| T | Purge the Foe | Dawn of War | 5 |

## Future Enhancements

Planned improvements:
- **Mission preview**: Show deployment zone visualization
- **Terrain preview**: Display terrain layout images
- **Mission details**: Hover tooltips with mission descriptions
- **Favorites system**: Save preferred mission combinations
- **Random selection**: Quick random mission generator
- **Search/filter**: Find missions by type or deployment

## Files Created/Modified

- `src/warhammer40k_ai/UI/dialogs/mission_selection_dialog.py` - Main dialog implementation
- `src/warhammer40k_ai/UI/dialogs/__init__.py` - Added dialog import
- `src/warhammer40k_ai/classes/game.py` - Updated setup phases
- `src/warhammer40k_ai/classes/missions.py` - Added placeholder missions
- `examples/mission_selection_example.py` - Usage demonstration

The Mission Selection Dialog provides a complete, tournament-legal interface for selecting Chapter Approved 2025/2026 mission combinations with proper integration into the game setup sequence.
