# Mission Selection Dialog - Chapter Approved 2025/2026

This document describes the implementation of the Mission Selection Dialog for the SELECT_MISSION_OBJECTIVES setup phase, displaying all approved mission combinations from Chapter Approved 2025/2026, and how it integrates with the new mission card scoring system.

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
4. **Primary mission**: Sets scoring and victory conditions via Mission Cards

## Mission Cards and Scoring

The game uses a Chapter Approved 2025/26 mission card system:

- **Primary Mission Card**: Selected via the Mission Selection Dialog; applies to both players for the battle. Each Primary defines its scoring windows (Command phase, end of turn, end of battle round) and optional mission Actions.
- **Secondary Mission Deck**: At the start of each of your Command phases, you draw until you have two active secondary cards. When you score any VP from a secondary, it is discarded. You may discard an active secondary at end of your turn to gain 1CP. If the deck runs out you cannot generate more secondaries.
- **Per-turn caps**: Some primaries have per-turn VP caps that are enforced automatically.
- **Objective control**: Objectives removed by missions (e.g., Scorched Earth, Supply Drop) are excluded from control and scoring automatically.

### Implemented Primary Missions

- **Take and Hold**
  - BR2+: End of your Command phase (or end of your turn if BR5 and you are going second): 5VP per objective you control, up to 15VP/turn.

- **Terraform**
  - Action: Terraform in your Shooting phase. Completes end of your turn if still in range and you control the same objective; marks that objective as terraformed by you.
  - BR2+: End of your Command phase: 4VP per objective you control, up to 12VP/turn.
  - Any BR: End of each turn: +1VP per terraformed objective you own.

- **Linchpin**
  - BR2+: End of your Command phase: If you do not control your home objective, score 3VP per objective you control; otherwise score 3VP for home objective and 5VP per other objective (cap 15VP/turn). Home objective is auto-detected as any objective in your deployment zone.

- **Purge the Foe**
  - End of battle round: 4VP if one or more enemy units were destroyed this battle round; BR2+: +4VP if more enemy units than friendly were destroyed.
  - BR2+: End of your Command phase: 4VP if you control 1+ objectives; +4VP if you control more than your opponent.

- **Scorched Earth**
  - Action: Burn Objective (BR2+) in your Shooting phase while within range of a No Man’s Land or opponent DZ objective you control. Completes end of opponent’s next turn if still in range and you control it; removes that objective and awards 5VP (No Man’s Land) or 10VP (opponent DZ) immediately.
  - BR2+: End of your Command phase: 5VP per objective you control (cap 10VP/turn).

- **Hidden Supplies**
  - Setup: Moves center objective 6" toward a corner and spawns a new No Man’s Land objective opposite (handled in deployment/objective placement logic).
  - BR2+: End of your Command phase (cumulative): +5VP if you control one objective not in your DZ; +5VP if you control two not in your DZ; +5VP if you control more than your opponent.

- **Supply Drop**
  - Setup: Selects two No Man’s Land objectives (not center) as Alpha and Omega.
  - BR4 start: Alpha is removed. BR5 start: Omega is removed. (Handled automatically at the start of those rounds.)
  - BR2+: End of your Command phase: Score per No Man's Land objective you control: 5VP in BR2-3, 8VP in BR4, 15VP in BR5.

### Actions UI

During your Shooting phase, units can start mission Actions from the Shooting dialog:

- Buttons: "Start Terraform", "Start Sabotage", and (if Scorched Earth is active) "Start Burn Objective".
- Eligibility is enforced per rules: not Aircraft, not Battle-shocked, OC > 0, not within Engagement Range (unless TITANIC CHARACTER), did not Advance or Fall Back, and not already selected to shoot this phase.
- While performing an Action, the unit cannot shoot or declare a charge until completion or end of turn; moving (Advance/Move/Fall Back) cancels the Action.

The unit detail panel shows "Performing Action: <Action>" when a unit is acting.

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

The Mission Selection Dialog provides a complete, tournament-legal interface for selecting Chapter Approved 2025/2026 mission combinations with proper integration into the game setup sequence.
