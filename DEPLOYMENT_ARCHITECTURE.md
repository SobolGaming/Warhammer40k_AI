# Warhammer 40k Deployment System Architecture

## Overview

The deployment system implements the official Warhammer 40k 10th Edition deployment sequence with full support for AI training, human interaction, and mixed gameplay. The architecture separates core game mechanics from player implementation, supporting manual phase control, deployment action tracking, and enhanced UI integration.

## Architecture Components

### 1. Core Deployment System (`src/warhammer40k_ai/classes/deployment.py`)

#### `DeploymentManager`
- **Purpose**: Implements the official Warhammer 40k 10th Edition deployment sequence
- **Independence**: Works with any player type (AI, Human, or mixed)
- **Responsibilities**:
  - Determine Attacker/Defender via dice roll
  - Manage deployment zone selection
  - Handle reserves declarations
  - Execute alternating deployment with proper turn tracking
  - Determine first turn player
  - Track deployment actions for UI display

#### `DeploymentDecisionMaker` (Abstract Base Class)
- **Purpose**: Interface for making deployment decisions
- **Methods**:
  - `choose_deployment_zone()`: Select deployment zone (defender only)
  - `declare_reserves()`: Decide unit reserves/deployment
  - `choose_unit_deployment_position()`: Position units within zones

#### `HumanDeploymentDecisionMaker`
- **Purpose**: Implementation for human players with full UI integration
- **Features**:
  - Interactive deployment through roster pane clicks
  - Deployment choice dialogs (battlefield vs reserves)
  - Real-time deployment zone visualization
  - Fallback defaults when no UI available

### 2. AI Integration (`src/warhammer40k_ai/agents/hrl_agent.py`)

#### `AIDeploymentDecisionMaker`
- **Purpose**: AI implementation of deployment decisions
- **Integration**: Connects to `HighLevelAgent` neural networks
- **Learning**: Computes and stores rewards for policy updates
- **Strategic Decisions**: Zone selection, reserves optimization, positioning

#### Enhanced `HighLevelAgent`
- **New Networks**:
  - `deployment_zone_net`: Choose deployment zone strategically
  - `reserves_selection_net`: Optimize reserves vs deploy decisions
  - `unit_deployment_net`: Tactical unit positioning within zones
- **Learning**: Separate policy updates for each decision type with reward tracking

### 3. Game Integration (`src/warhammer40k_ai/classes/game.py`)

#### Enhanced Game State Management
- **Setup Phases**: Seven official setup phases with proper progression
- **Manual Phase Support**: Optional SPACE key control for phase advancement
- **Deployment Action Tracking**: Records and displays all deployment actions
- **Player Role Tracking**: Attacker/Defender determination and UI updates

#### Key Methods
- `complete_deployment_phase(manual_phases=False)`: Main deployment orchestration
- `record_deployment_action()`: Track unit deployments for UI display
- `clear_deployment_actions()`: Clean up after deployment phase
- `execute_official_deployment()`: Core deployment sequence execution

### 4. UI Integration (`src/warhammer40k_ai/UI/game_ui.py`)

#### Enhanced GameView Features
- **Deployment Action Display**: Shows last deployment for each player
- **Turn Indication**: Clear display of whose turn it is during deployment
- **Manual Phase Support**: Visual indicators for manual mode
- **Roster Pane Updates**: Player names include Attacker/Defender roles

#### Visual Enhancements
- **Deployment Zones**: Enhanced visualization with thicker borders, corner markers
- **Unit Status**: Color-coded health and deployment status indicators
- **Info Panel**: Real-time game state and deployment progress display

## Official Warhammer 40k Deployment Sequence

The system implements the complete official 10th Edition deployment rules:

1. **Determine Attacker and Defender**
   - Roll-off with D6 dice (re-roll ties)
   - Winner becomes Attacker, loser is Defender
   - UI updates to show player roles

2. **Defender Chooses Deployment Zone**
   - Defender selects from available zones
   - Attacker gets the remaining zone
   - Visual zone highlighting in UI

3. **Declare Reserves & Strategic Reserves**
   - Both players simultaneously decide:
     - Deploy normally on battlefield
     - Put in Reserves (Deep Strike, etc.)
     - Put in Strategic Reserves (board edge)
   - Interactive dialogs for human players

4. **Alternating Deployment**
   - Defender deploys first unit
   - Players alternate until all units deployed
   - Only units not in reserves are deployed
   - Manual phases mode: SPACE required between each deployment
   - Deployment action tracking: "Be'lakor deployed at (15.3, 22.7)"

5. **Determine First Turn**
   - Attacker rolls D6
   - 1-3: Defender goes first
   - 4-6: Attacker goes first

## Manual Phases Integration

### Deployment Phase Manual Control
```python
# In Game.complete_deployment_phase()
if manual_phases:
    self.waiting_for_deployment_input = True
    # Each deployment action waits for SPACE key
    # UI shows "Manual Deployment Mode: Press SPACE to continue"
```

### Features
- **Individual Action Control**: Each unit deployment requires separate SPACE press
- **Turn Visualization**: Clear indication of whose deployment turn it is
- **Action Tracking**: Real-time display of deployment decisions
- **Learning Tool**: Perfect for understanding official deployment rules

## Usage Examples

### AI vs AI with Manual Phases (Learning/Debugging)
```python
# Command line
python scripts/main.py --mode play --player1 ai --player2 ai --manual-phases

# In code
deployment_manager = DeploymentManager(game)
results = deployment_manager.execute_deployment_sequence(
    decision_makers, manual_phases=True
)
```

### Human vs AI Deployment
```python
from warhammer40k_ai.classes.deployment import DeploymentManager, HumanDeploymentDecisionMaker

# Create decision makers with UI integration
decision_makers = {
    human_player.name: HumanDeploymentDecisionMaker(ui_interface),
    ai_player.name: AIDeploymentDecisionMaker(ai_agent)
}

# Execute with action tracking
deployment_manager = DeploymentManager(game)
results = deployment_manager.execute_deployment_sequence(decision_makers)
```

### Training Integration
```python
# AI training with deployment learning
player1_agent = HighLevelAgent(game, player1, player2, objectives, commands)
player2_agent = HighLevelAgent(game, player2, player1, objectives, commands)

# Deployment decisions become part of AI learning
decision_makers = {
    player1.name: AIDeploymentDecisionMaker(player1_agent),
    player2.name: AIDeploymentDecisionMaker(player2_agent)
}

# Training includes deployment rewards
deployment_manager = DeploymentManager(game)
results = deployment_manager.execute_deployment_sequence(decision_makers)
```

## Benefits of Current Architecture

### 1. **Official Rule Compliance**
- Complete implementation of Warhammer 40k 10th Edition deployment
- Proper attacker/defender mechanics
- Accurate zone selection and reserves handling

### 2. **Educational Value**
- Manual phases mode for learning deployment rules
- Step-by-step progression through official sequence
- Visual feedback for all deployment decisions

### 3. **Flexibility**
- Supports any combination of player types
- Manual phase control optional
- Easy integration with different UI systems

### 4. **AI Learning Integration**
- Deployment becomes part of strategic learning
- Separate neural networks for different deployment decisions
- Reward tracking for deployment performance

### 5. **Enhanced User Experience**
- Real-time deployment action tracking
- Clear turn indication and progress display
- Visual enhancements for better gameplay understanding

## Recent Enhancements

### Deployment Action Tracking
- Records all deployment decisions with locations
- Displays actions in UI near appropriate player roster
- Shows "Unit placed in Reserves" or "Be'lakor deployed at (15.3, 22.7)"
- Clears actions when deployment phase ends

### UI Improvements
- Player names show roles: "Player 1 (Attacker) (AI)"
- Turn indication: "DEPLOY ARMIES: Defender's Turn"
- Manual deployment mode indicators
- Enhanced visual zone boundaries and markers

### Manual Phase Enhancement
- Individual deployment action control
- SPACE key required between each deployment
- Perfect for learning and demonstration
- Works with all player type combinations

## Integration Points

### With Main Game Loop
- Seven setup phases including deployment
- Manual phase support throughout game
- Proper state management and progression

### With UI System
- Real-time deployment action display
- Turn indication and progress tracking
- Interactive deployment for human players

### With AI Training
- Deployment rewards integrated into learning
- Strategic deployment decision making
- Long-term tactical improvement

## File Structure

```
src/warhammer40k_ai/
├── classes/
│   ├── deployment.py          # Core deployment system
│   ├── game.py               # Game state and phase management
│   └── __init__.py           # Export deployment classes
├── agents/
│   └── hrl_agent.py          # AI deployment integration
├── UI/
│   └── game_ui.py            # UI deployment features
└── ...

scripts/main.py               # Main entry point with deployment
README.md                     # Updated usage examples
DEPLOYMENT_ARCHITECTURE.md    # This documentation
```

This architecture ensures that the deployment system follows official Warhammer 40k rules while providing excellent support for learning, debugging, AI training, and interactive gameplay across all player type combinations. 