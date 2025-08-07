# Warhammer 40k AI Training System

This system implements a hierarchical reinforcement learning (HRL) approach for training AI agents to play Warhammer 40k. The AI consists of three specialized layers that work together to create strategic, tactical, and operational gameplay decisions.

## AI Architecture

### 1. **High-Level Agent (Strategic)**
- **Objectives**: Chooses mission objectives and high-level strategic commands
- **Deployment**: Zone selection, reserves decisions, and unit positioning strategies
- **Learning**: Long-term strategic reward optimization

### 2. **Tactical Agent (Phase-Specific)**
- **Movement Phase**: Unit movement and positioning decisions
- **Shooting Phase**: Target selection and weapon profile choices
- **Fight Phase**: Melee target selection and combat optimization
- **Learning**: Phase-specific tactical improvement

### 3. **Low-Level Agent (Operational)**
- **Movement Execution**: Precise unit pathfinding and positioning
- **Combat Calculations**: Damage resolution and dice roll optimization
- **Learning**: Action execution efficiency

## Key Features

### Training Capabilities
- **Persistent Learning**: AI agents save and load checkpoints to improve over multiple sessions
- **Deployment Learning**: Official Warhammer 40k deployment strategies integrated into AI learning
- **Multi-Phase Training**: Separate learning for each game phase (setup, command, movement, shooting, etc.)
- **Reward Tracking**: Comprehensive reward system for strategic, tactical, and operational decisions

### Observation and Debugging
- **Manual Phases Mode**: Step through AI decision making with `--manual-phases`
- **Training Statistics**: Win rates, average game length, reward progression tracking
- **Deployment Visualization**: Watch AI learn deployment strategies in real-time
- **Action Logging**: Detailed logs of AI decisions for analysis

### Official Rule Implementation
- **Complete Setup Phases**: Seven official setup phases including deployment
- **Deployment System**: Official alternating deployment with zones, reserves, and strategic reserves
- **Battle Rounds**: Command, Movement, Shooting, Charge, Fight phases with proper rule implementation

## Usage

### Standard AI Training
```bash
# Default AI vs AI training for 1000 episodes
python scripts/main.py --mode train --episodes 1000

# Shorter training session with more frequent checkpoints
python scripts/main.py --mode train --episodes 100 --checkpoint-interval 5

# Training with custom army compositions
python scripts/main.py --mode train --episodes 500 \
  --player1-army army_lists/space_marines.txt \
  --player2-army army_lists/chaos_daemons.txt
```

### Training with Manual Observation
```bash
# Watch AI training step-by-step (great for learning)
python scripts/main.py --mode train --episodes 10 --manual-phases

# Observe deployment learning specifically
python scripts/main.py --mode train --episodes 5 --manual-phases
```

### Fresh Training (Clear Existing Progress)
```bash
# Start completely fresh training
python scripts/main.py --mode train --clear-checkpoints --episodes 1000

# Useful after major code changes or to test new strategies
python scripts/main.py --mode train --clear-checkpoints --episodes 100 --manual-phases
```

## Training Modes and Options

### Command Line Arguments
- `--mode train`: Enables AI training mode (both players become AI)
- `--episodes N`: Number of training episodes (default: 1000)
- `--checkpoint-interval N`: Save checkpoints every N episodes (default: 10)
- `--manual-phases`: Step through each phase with SPACE key (great for observation)
- `--clear-checkpoints`: Remove existing checkpoints and start fresh

### Training Behavior
- **AI vs AI Only**: Training mode automatically sets both players to AI
- **Deployment Learning**: AI learns strategic deployment decisions as part of training
- **Phase-by-Phase Learning**: Each agent learns specific skills for their responsibility level
- **Persistent Progress**: Training resumes from last checkpoint automatically

## Checkpoint System

### Automatic Checkpoint Management
- Checkpoints saved automatically in `checkpoints/` directory
- Separate checkpoints for each agent type and player
- Training resumes from last checkpoint if available
- Final checkpoints saved with `_final.pth` suffix

### Checkpoint Files
```
checkpoints/
├── hla1_checkpoint.pth         # Player 1 High-Level Agent
├── hla2_checkpoint.pth         # Player 2 High-Level Agent
├── ta1_checkpoint.pth          # Player 1 Tactical Agent
├── ta2_checkpoint.pth          # Player 2 Tactical Agent
├── lla1_checkpoint.pth         # Player 1 Low-Level Agent
└── lla2_checkpoint.pth         # Player 2 Low-Level Agent
```

### Checkpoint Migration
If you encounter checkpoint loading errors after code updates:
```bash
# Check checkpoint compatibility
python migrate_checkpoints.py --check-only

# Migrate old checkpoints to new format
python migrate_checkpoints.py --migrate

# Start fresh if migration fails
python scripts/main.py --mode train --clear-checkpoints --episodes 100
```

## Training Output and Monitoring

### Real-Time Information
```
Episode 1: Player 1 wins (Score: 15-8, Turns: 5)
Episode 2: Player 2 wins (Score: 12-10, Turns: 4)
...
Training Statistics (Episodes 1-10):
  Player 1 Win Rate: 40.0%
  Player 2 Win Rate: 60.0%
  Average Turns per Episode: 4.5
  Average Episode Score Difference: 3.2
```

### Deployment Learning Tracking
- **Deployment Success/Failure**: Messages about deployment decision quality
- **Zone Selection**: AI learning defender deployment zone choices
- **Reserves Optimization**: AI learning when to use reserves vs battlefield deployment
- **Position Evaluation**: AI learning optimal unit positioning within zones

### Learning Progression Indicators
- **Win Rate Trends**: Should become more balanced as both AIs improve
- **Game Length Stabilization**: Episodes should reach consistent turn counts
- **Reward Progression**: Reward values should generally increase over time
- **Strategic Complexity**: More sophisticated deployment and tactical decisions

## Training Performance and Optimization

### Expected Training Progression
1. **Initial Episodes (1-50)**: Random-like behavior, high variance in game length
2. **Early Learning (50-200)**: Basic tactical understanding develops
3. **Strategic Development (200-500)**: Deployment strategies emerge
4. **Advanced Play (500+)**: Complex multi-phase coordination

### Performance Monitoring
Track these key metrics:
- **Balanced Win Rates**: Both players should win approximately 50% after sufficient training
- **Stable Game Length**: Average turns per episode should stabilize
- **Increasing Rewards**: Cumulative rewards should trend upward
- **Deployment Success**: Fewer deployment failures and better positioning

### Training Tips
- **Longer Training**: More episodes generally lead to better strategic play
- **Checkpoint Frequency**: More frequent checkpoints help recover from training issues
- **Manual Observation**: Use `--manual-phases` periodically to observe learning progress
- **Fresh Starts**: Sometimes starting fresh training can help overcome local optima

## Advanced Training Features

### Manual Phases for Learning Observation
```bash
# Watch deployment phase learning
python scripts/main.py --mode train --episodes 5 --manual-phases
```
Benefits:
- See AI deployment decision-making process
- Understand how AI learns zone selection
- Observe reserves vs battlefield decisions
- Watch tactical positioning improvement

### Multi-Army Training
```bash
# Train with different army compositions
python scripts/main.py --mode train --episodes 200 --player1-army armies/ultramarines.txt
python scripts/main.py --mode train --episodes 200 --player1-army armies/blood_angels.txt
```
Benefits:
- AI learns to handle different unit types
- Develops counter-strategies for various armies
- Improves tactical flexibility

## Troubleshooting Training Issues

### Common Problems and Solutions

**Checkpoint Loading Errors**
```bash
# Solution: Clear and restart
python scripts/main.py --mode train --clear-checkpoints --episodes 100
```

**Deployment Failures During Training**
- Check army list files for valid units
- Verify battlefield dimensions are appropriate
- System automatically falls back to simple positioning

**Training Convergence Issues**
- Increase episode count: `--episodes 2000`
- Try fresh training: `--clear-checkpoints`
- Monitor win rate balance over time

**Memory Issues During Long Training**
- Reduce checkpoint interval: `--checkpoint-interval 20`
- Run shorter episode batches
- Monitor system memory usage

## Integration with Gameplay

After training, AI agents can be used for:

### Interactive Gameplay
```bash
# Play against trained AI
python scripts/main.py --mode play --player1 human --player2 ai

# Watch trained AIs battle
python scripts/main.py --mode play --player1 ai --player2 ai
```

### Continued Learning
```bash
# Resume training with existing checkpoints
python scripts/main.py --mode train --episodes 500
```

## Files and Architecture

### Core Training Files
- `scripts/main.py`: Main training loop and episode management
- `src/warhammer40k_ai/agents/hrl_agent.py`: HRL agent implementations with learning
- `src/warhammer40k_ai/classes/game.py`: Game state management and training integration

### Training Support
- `migrate_checkpoints.py`: Checkpoint management and migration
- `CHECKPOINT_MIGRATION.md`: Detailed checkpoint handling guide
- `checkpoints/`: Directory for AI training progress

This training system provides a comprehensive framework for developing sophisticated Warhammer 40k AI opponents that learn strategic deployment, tactical phase management, and operational execution through hierarchical reinforcement learning. 