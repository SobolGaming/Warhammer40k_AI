# Player Configuration System

The game supports local player control for interactive gameplay and a remote-control flag for future external controllers.

## Command Line Arguments

### Army Lists
- `--player1-army <file>` - Army list file for Player 1 (default: army_lists/chaos_test.txt)
- `--player2-army <file>` - Army list file for Player 2 (default: army_lists/aeldari_test.txt)

### Advanced Options
- `--manual-phases` - Require SPACE key to advance phases, including individual deployment actions

## Usage Examples

### Local vs Local
```bash
python scripts/main.py --player1-army army_lists/chaos_test.txt --player2-army army_lists/aeldari_test.txt
```

### Manual Phases
```bash
python scripts/main.py --manual-phases
```

## Manual Phases Mode (`--manual-phases`)

This mode provides step-by-step control over game progression:

### Setup Phases
- Requires SPACE key to advance through each setup phase
- Shows detailed progress and phase descriptions
- Allows observation of attacker/defender determination and deployment zone setup

### Deployment Phase
- Each unit deployment requires a separate SPACE key press
- Shows deployment action tracking: "Unit deployed at (x, y)" or "Unit placed in Reserves"
- Displays whose turn it is during alternating deployment

### Battle Rounds
- SPACE key required to advance between each phase

## Player Control Model

Each `Player` instance includes a `control` value:

- `PlayerControl.LOCAL`: Controlled by the local UI
- `PlayerControl.REMOTE`: Intended for external controllers (no local input)

The UI checks `player.has_control()` before enabling interactions, which allows future networked or automation control to be added without changing core game flow.

## User Interface Highlights

### Roster Panes
- Player names update with attacker/defender roles after setup
- Unit health indicators and deployment status
- Interactive selection for deployment and details

### Info Panel
- Game phase and turn indicators
- Deployment action tracking
- Manual mode indicators

### Battlefield View
- Zoom and pan controls
- Deployment zones with labels and boundaries
- Objective markers and unit visualization
