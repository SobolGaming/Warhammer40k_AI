# Warhammer 40k AI

A comprehensive AI system for playing Warhammer 40k 10th Edition, featuring hierarchical reinforcement learning agents, interactive gameplay, and official rule implementation.

## Features

- **Hierarchical AI System**: Three-layer reinforcement learning with strategic, tactical, and operational decision making
- **Multiple Player Types**: Support for AI vs AI, Human vs AI, Human vs Human, and mixed gameplay
- **Official Rules Implementation**: Complete setup phases, deployment system, and battle round mechanics
- **Interactive UI**: Rich graphical interface with unit details, deployment controls, and battlefield visualization
- **Manual Phase Control**: Step-through debugging and demonstration mode with `--manual-phases`
- **Persistent Learning**: AI agents save progress and improve over multiple training sessions

## Quick Start

### Initial Setup

1. **Install dependencies and the package**:
```bash
pip3 install -r requirements.txt
pip3 install -e .
```

2. **Download Warhammer 40k data** (first time only):
```bash
mkdir wahapedia_data
cd scripts
python3 -m get_datasheets -f -c -o ../wahapedia_data -s ../wahapedia_data
cd ..
```

### Usage Examples

#### AI Training (Default)
```bash
# Train AI agents with 1000 episodes
python3 scripts/main.py --mode train --episodes 1000

# Shorter training with custom armies
python3 scripts/main.py --mode train --episodes 100 --player1-army army_lists/my_army.txt
```

#### Interactive Gameplay
```bash
# Human vs AI
python3 scripts/main.py --mode play --player1 human --player2 ai

# AI vs AI with manual phase control (for learning/debugging)
python3 scripts/main.py --mode play --player1 ai --player2 ai --manual-phases

# Human vs Human with manual phase control
python3 scripts/main.py --mode play --player1 human --player2 human --manual-phases
```

#### Data Exploration
```bash
# Browse Wahapedia data
python3 -m warhammer40k_ai.UI.wahapedia_ui
```

## Command Line Options

### Game Modes
- `--mode {train|play}`: Training mode for AI development or play mode for interactive games
- `--episodes N`: Number of training episodes (default: 1000)
- `--checkpoint-interval N`: Save AI progress every N episodes (default: 10)

### Player Configuration
- `--player1 {ai|human}`: Set Player 1 type (default: ai)
- `--player2 {ai|human}`: Set Player 2 type (default: ai)
- `--player1-army <file>`: Army list for Player 1 (default: army_lists/warhammer_app_dump.txt)
- `--player2-army <file>`: Army list for Player 2 (default: army_lists/chaos_daemons_GT2023.txt)

### Advanced Options
- `--manual-phases`: Require SPACE key between each phase (useful for learning/debugging)
- `--clear-checkpoints`: Start fresh training (clears existing AI progress)

## Architecture

### AI System (Hierarchical Reinforcement Learning)
- **High-Level Agent**: Strategic objective selection and command decisions
- **Tactical Agent**: Phase-specific actions (movement, shooting, fighting)
- **Low-Level Agent**: Precise unit positioning and movement execution

### Game System
- **Complete Setup Phases**: Army loading, battlefield creation, attacker/defender determination, deployment, and first turn order
- **Official Deployment**: Alternating deployment with proper zones, reserves, and strategic reserves
- **Battle Round System**: Command, Movement, Shooting, Charge, and Fight phases with official rules

### User Interface
- **Battlefield View**: Zoomable map with units, terrain, objectives, and deployment zones
- **Roster Panes**: Interactive unit lists showing health, equipment, and deployment status
- **Info Panel**: Game state, turn information, and deployment action tracking
- **Unit Details**: Comprehensive stat sheets with weapons, abilities, and rules

## Files and Documentation

- `README.md`: This file
- `PLAYER_CONFIGURATION.md`: Detailed player type configuration guide
- `DEPLOYMENT_ARCHITECTURE.md`: Deployment system implementation details
- `CHECKPOINT_MIGRATION.md`: AI checkpoint management and migration
- `README_training.md`: In-depth training system documentation

## Project Structure

```
Warhammer40k_AI/
├── scripts/main.py              # Main entry point
├── src/warhammer40k_ai/
│   ├── classes/                 # Core game classes
│   ├── agents/                  # AI agents and learning
│   ├── UI/                      # User interface components
│   └── utility/                 # Helper functions
├── army_lists/                  # Army configuration files
├── checkpoints/                 # AI training checkpoints
└── wahapedia_data/              # Game data from Wahapedia
```

## Contributing

This project has been developed primarily through AI-assisted programming using CursorAI and prompt engineering. The codebase implements official Warhammer 40k 10th Edition rules and provides a solid foundation for both AI research and interactive gameplay.

## License

This project is licensed under the MIT License.