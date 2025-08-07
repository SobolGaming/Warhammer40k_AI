# Player Configuration System

The Warhammer 40k AI game supports flexible player configurations, allowing you to set up games with different combinations of AI and human players, along with advanced debugging and demonstration features.

## Command Line Arguments

### Player Types
- `--player1 {ai|human}` - Set Player 1 as AI or Human (default: ai)
- `--player2 {ai|human}` - Set Player 2 as AI or Human (default: ai)

### Army Lists
- `--player1-army <file>` - Army list file for Player 1 (default: army_lists/warhammer_app_dump.txt)
- `--player2-army <file>` - Army list file for Player 2 (default: army_lists/chaos_daemons_GT2023.txt)

### Game Modes
- `--mode {train|play}` - Run mode: train for AI training, play for gameplay (default: train)
- `--episodes N` - Number of training episodes (default: 1000)
- `--checkpoint-interval N` - Save checkpoints every N episodes (default: 10)

### Advanced Options
- `--manual-phases` - Require SPACE key to advance phases, including individual deployment actions
- `--clear-checkpoints` - Clear existing checkpoints and start fresh training

## Usage Examples

### AI Training (AI vs AI)
```bash
# Default AI training
python scripts/main.py --mode train --episodes 1000

# Training with custom army lists
python scripts/main.py --mode train --episodes 500 --player1-army my_space_marines.txt --player2-army my_chaos.txt

# Training with manual phase control for observation
python scripts/main.py --mode train --episodes 10 --manual-phases
```

### Human vs AI Gameplay
```bash
# Human Player 1 vs AI Player 2
python scripts/main.py --mode play --player1 human --player2 ai

# AI Player 1 vs Human Player 2  
python scripts/main.py --mode play --player1 ai --player2 human

# Human vs AI with step-by-step deployment
python scripts/main.py --mode play --player1 human --player2 ai --manual-phases
```

### AI vs AI Gameplay
```bash
# Watch AI vs AI battle
python scripts/main.py --mode play --player1 ai --player2 ai

# AI vs AI with manual phase control (great for learning/debugging)
python scripts/main.py --mode play --player1 ai --player2 ai --manual-phases
```

### Human vs Human Gameplay
```bash
# Two human players
python scripts/main.py --mode play --player1 human --player2 human

# Human vs Human with step-by-step phases
python scripts/main.py --mode play --player1 human --player2 human --manual-phases
```

## Game Behavior by Player Type

### AI Players
- Use trained neural networks for strategic, tactical, and operational decision making
- Automatically handle all game phases (command, movement, shooting, charge, fight)
- Load from checkpoint files if available, or start with random initialization
- Support intelligent deployment with zone selection, reserves decisions, and unit positioning
- Learn and improve through reinforcement learning during training

### Human Players
- Use interactive UI for all game interactions
- Manual deployment through clicking units in roster panes and battlefield positioning
- Phase progression controlled by player input (SPACE key)
- Full access to unit details, battlefield zoom/pan, and game state information
- Deployment choice dialogs for reserves vs battlefield placement decisions

### Mixed AI/Human Games
- AI players act automatically during their turns (unless manual phases mode is enabled)
- Human players get manual control during their turns
- Deployment respects player types with proper turn alternation
- Game state properly transitions between AI and human control
- UI shows whose turn it is and what actions are available

## Manual Phases Mode (`--manual-phases`)

This advanced feature provides step-by-step control over game progression:

### Setup Phases
- Requires SPACE key to advance through each of the 7 setup phases
- Shows detailed progress and phase descriptions
- Allows observation of attacker/defender determination and deployment zone setup

### Deployment Phase
- **Individual Deployment Actions**: Each unit deployment requires a separate SPACE key press
- Shows deployment action tracking: "Be'lakor deployed at (15.3, 22.7)" or "Unit placed in Reserves"
- Displays whose turn it is: "DEPLOY ARMIES: Defender's Turn" / "DEPLOY ARMIES: Attacker's Turn"
- Perfect for learning official Warhammer 40k deployment rules

### Battle Rounds
- SPACE key required to advance between each phase
- AI players wait for manual trigger during their phases
- Human players maintain normal control during their phases

### Use Cases
- **Learning**: Understand official Warhammer 40k 10th Edition rules
- **Debugging**: Step through AI decision making
- **Demonstration**: Show game mechanics to others
- **Training Observation**: Watch AI learning deployment strategies

## User Interface Features

### Roster Panes
- **Player Names**: Show "Player 1 (Attacker) (AI)" instead of redundant names after setup
- **Unit Health**: Color-coded health indicators (green/yellow/red)
- **Deployment Status**: Shows "Not Deployed", "Reserves", "Strategic Reserves"
- **Interactive Selection**: Click units to select for deployment or view details

### Info Panel
- **Game Phase**: Current setup phase or battle round phase with clear labeling
- **Deployment Tracking**: Shows last deployment action for each player on appropriate side
- **Turn Indicator**: Clear indication of whose turn it is during deployment
- **Progress Tracking**: Phase progression with manual mode indicators

### Battlefield View
- **Zoom and Pan**: Mouse wheel zoom, middle-click pan, keyboard controls
- **Deployment Zones**: Colored zones with clear labels and boundaries
- **Unit Visualization**: Different icons for unit types with health indicators
- **Objective Markers**: Mission objectives with control indicators

## Technical Implementation

The system works through:

1. **Player Type Detection**: Each `Player` object has a `PlayerType.AI` or `PlayerType.HUMAN` attribute

2. **Conditional Agent Creation**: AI agents (HighLevelAgent, TacticalAgent, LowLevelAgent) are only created for AI players

3. **Setup Phase System**: Seven official setup phases with proper progression and rule implementation

4. **Deployment System**: Official alternating deployment with proper zones, reserves, and manual phase support

5. **Game Loop Management**: Handles different player types, manual phases, and proper turn progression

## Army List Files

Army list files should follow the supported format. Default files included:
- `army_lists/warhammer_app_dump.txt` - Space Marines army
- `army_lists/chaos_daemons_GT2023.txt` - Chaos Daemons army

You can specify custom army files using the `--player1-army` and `--player2-army` arguments.

## Training Mode Restrictions

When using training mode (`--mode train`), the system automatically sets both players to AI regardless of command line arguments, as training requires consistent AI behavior for learning algorithms. However, `--manual-phases` can still be used to observe training progression.

## Troubleshooting

**Deployment Issues**: If deployment fails, check that army lists are valid and deployment zones are properly loaded.

**Manual Phases Not Working**: Ensure you're using `--mode play` for interactive manual phases functionality.

**UI Performance**: For better performance, avoid excessive zooming during large battles or consider reducing visual effects.

**Checkpoint Loading**: If AI checkpoint loading fails, use `--clear-checkpoints` to start fresh training. 