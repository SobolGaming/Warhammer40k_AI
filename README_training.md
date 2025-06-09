# Warhammer 40k AI Training System

This system implements a hierarchical reinforcement learning (HRL) approach for training AI agents to play Warhammer 40k. The AI consists of three layers:

1. **High-Level Agent (Strategic)** - Chooses objectives and high-level commands
2. **Tactical Agent** - Handles phase-specific unit actions (movement, shooting, fighting)
3. **Low-Level Agent (Operational)** - Executes precise unit movements

## Features

- **Persistent Learning**: AI agents save and load checkpoints to learn over multiple sessions
- **Automated Unit Deployment**: No manual intervention required during training
- **Training Statistics**: Track win rates, average game length, and other metrics
- **Configurable Training**: Adjust number of episodes, checkpoint intervals, etc.

## Usage

### Training Mode (Default)

Run AI vs AI training for 1000 episodes:
```bash
python scripts/main.py --mode train --episodes 1000
```

Run shorter training session with more frequent checkpoints:
```bash
python scripts/main.py --mode train --episodes 100 --checkpoint-interval 5
```

### Manual Play Mode

Play manually with trained AI opponents:
```bash
python scripts/main.py --mode play
```

## Command Line Options

- `--mode`: Choose 'train' for AI training or 'play' for manual gameplay
- `--episodes`: Number of training episodes (default: 1000)
- `--checkpoint-interval`: Save checkpoints every N episodes (default: 10)

## Checkpoint System

- Checkpoints are automatically saved in the `checkpoints/` directory
- Training automatically resumes from the last checkpoint if available
- Final checkpoints are saved with `_final.pth` suffix after training completion
- Each agent type (high-level, tactical, low-level) has separate checkpoints for each player

## Training Output

The system provides detailed logging including:
- Episode-by-episode results (winner, scores, game length)
- Periodic training statistics (win rates, average turns per episode)
- Reward calculations for each agent layer
- Deployment success/failure messages

## Architecture

### High-Level Agent
- **Input**: Game state features (scores, unit counts, distances to objectives)
- **Output**: Objective selection + command choice
- **Reward**: Based on distance improvement to objectives and final game outcome

### Tactical Agent
- **Movement Phase**: Chooses movement actions and destinations
- **Shooting Phase**: Selects targets and weapon profiles
- **Fight Phase**: Chooses melee targets and weapon profiles
- **Rewards**: Based on damage dealt, objectives captured, tactical improvements

### Low-Level Agent
- **Function**: Executes precise unit movements and combat calculations
- **Rewards**: Based on successful action execution

## Performance Monitoring

Track these metrics during training:
- Win rate trends for each player
- Average game length (should stabilize as agents improve)
- Reward values (should generally increase over time)
- Checkpoint file sizes (verify saves are working)

## Troubleshooting

**Deployment Failures**: If units fail to auto-deploy, the system falls back to simple positioning. Check map size and unit counts.

**Memory Issues**: For long training runs, consider reducing checkpoint intervals or running shorter episodes.

**Convergence Issues**: If win rates don't improve, consider adjusting learning rates in the agent constructors.

## Next Steps

- Monitor initial training runs to ensure agents are learning
- Experiment with different reward scaling factors
- Add more sophisticated objective types
- Implement additional tactical considerations (line of sight, terrain effects)

## Files Modified

- `scripts/main.py`: Main training loop and automated deployment
- `src/warhammer40k_ai/agents/hrl_agent.py`: HRL agent implementations with checkpointing
- `src/warhammer40k_ai/classes/player.py`: Added distance calculation methods 