# Player Configuration System

The Warhammer 40k AI game now supports flexible player configurations, allowing you to set up games with different combinations of AI and human players.

## Command Line Arguments

### Player Types
- `--player1 {ai|human}` - Set Player 1 as AI or Human (default: ai)
- `--player2 {ai|human}` - Set Player 2 as AI or Human (default: ai)

### Army Lists
- `--player1-army <file>` - Army list file for Player 1 (default: army_lists/warhammer_app_dump.txt)
- `--player2-army <file>` - Army list file for Player 2 (default: army_lists/chaos_daemons_GT2023.txt)

### Game Modes
- `--mode {train|play}` - Run mode: train for AI training, play for gameplay (default: train)

## Usage Examples

### AI Training (AI vs AI)
```bash
# Default AI training
python scripts/main.py --mode train --episodes 1000

# Training with custom army lists
python scripts/main.py --mode train --episodes 500 --player1-army my_space_marines.txt --player2-army my_chaos.txt
```

### Human vs AI Gameplay
```bash
# Human Player 1 vs AI Player 2
python scripts/main.py --mode play --player1 human --player2 ai

# AI Player 1 vs Human Player 2  
python scripts/main.py --mode play --player1 ai --player2 human
```

### AI vs AI Gameplay
```bash
# Watch AI vs AI battle
python scripts/main.py --mode play --player1 ai --player2 ai
```

### Human vs Human Gameplay
```bash
# Two human players
python scripts/main.py --mode play --player1 human --player2 human
```

## Game Behavior by Player Type

### AI Players
- Use trained neural networks for decision making
- Automatically handle all game phases (movement, shooting, etc.)
- Load from checkpoint files if available
- Support auto-deployment with strategic decision making

### Human Players
- Use interactive UI for unit selection and movement
- Manual deployment through UI dialogs
- Phase progression controlled by player input
- Full access to unit details and battlefield view

### Mixed AI/Human Games
- AI players act automatically during their turns
- Human players get manual control during their turns
- Deployment respects player types (AI uses algorithms, humans use UI)
- Game state properly transitions between AI and human control

## Technical Implementation

The system works by:

1. **Player Type Detection**: Each `Player` object has a `player_type` attribute set to `PlayerType.AI` or `PlayerType.HUMAN`

2. **Conditional Agent Creation**: AI agents (HighLevelAgent, TacticalAgent, LowLevelAgent) are only created for AI players

3. **Deployment System**: The `execute_official_deployment` function uses appropriate decision makers:
   - `AIDeploymentDecisionMaker` for AI players
   - `HumanDeploymentDecisionMaker` for human players

4. **Game Loop Branching**: The main game loop checks player types and either:
   - Executes AI decision making for AI players
   - Waits for human input for human players

## Army List Files

Army list files should be in the supported format. Default files included:
- `army_lists/warhammer_app_dump.txt` - Space Marines army
- `army_lists/chaos_daemons_GT2023.txt` - Chaos Daemons army

You can specify custom army files using the `--player1-army` and `--player2-army` arguments.

## Training Mode Restrictions

When using training mode (`--mode train`), the system will automatically set both players to AI regardless of the command line arguments, as training requires consistent AI behavior for learning. 