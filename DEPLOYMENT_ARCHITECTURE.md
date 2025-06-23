# Warhammer 40k Deployment System Architecture

## Overview

The deployment system implements the official Warhammer 40k 10th Edition deployment sequence with full support for AI training, human interaction, and mixed gameplay. The architecture separates core game mechanics from player implementation, supporting manual phase control, deployment action tracking, and enhanced UI integration.

## Deployment API Flow and Player Types

### Core Architecture Principles

The deployment system follows a **unified API architecture** that ensures consistent behavior across all game modes and player types:

1. **Single Source of Truth**: All deployment logic flows through the same `DeploymentManager` class
2. **Player Type Abstraction**: AI and Human players implement the same `DeploymentDecisionMaker` interface
3. **Mode Independence**: Training and Play modes use identical core logic
4. **Consistent Validation**: All players use the same rule validation functions

### Player Type Decision Makers

#### AI Players (`AIDeploymentDecisionMaker`)
- **Implementation**: Neural network-based decisions via `HighLevelAgent`
- **Zone Selection**: `deployment_zone_net` neural network
- **Reserves Declaration**: `reserves_selection_net` with official 50% limits
- **Unit Positioning**: `unit_deployment_net` for tactical placement
- **Learning**: Stores rewards for reinforcement learning
- **Speed**: Instant decisions
- **Consistency**: Identical behavior in training and play modes

#### Human Players (`HumanDeploymentDecisionMaker`)
- **Implementation**: UI-based interactions with fallback console options
- **Zone Selection**: Interactive dialog or console input
- **Reserves Declaration**: Step-by-step unit selection dialogs
- **Unit Positioning**: Mouse click positioning on battlefield
- **Learning**: No learning component
- **Speed**: Waits for human input
- **UI Integration**: Full visual feedback and deployment zone highlighting

### Game Mode API Flows

#### Training Mode (`--mode train`)
```
Command Line: python scripts/main.py --mode train --episodes 1000

Flow:
1. Both players automatically set to AI (regardless of --player1/--player2 args)
2. No pygame UI initialization
3. execute_setup_phases() called automatically
4. For DEPLOY_ARMIES phase:
   - decision_makers[player.name] = AIDeploymentDecisionMaker(agent)
   - game.execute_current_setup_phase(decision_makers=decision_makers)
5. Pure AI vs AI execution with no rendering
6. AI learning and checkpoint saving enabled
```

#### Play Mode - AI vs AI (`--mode play --player1 ai --player2 ai`)
```
Command Line: python scripts/main.py --mode play --player1 ai --player2 ai

Flow:
1. Both players set to AI
2. Full pygame UI initialization
3. Manual setup phase progression (SPACE key required)
4. For DEPLOY_ARMIES phase:
   - decision_makers[player.name] = AIDeploymentDecisionMaker(agent)
   - game.execute_current_setup_phase(decision_makers=decision_makers, manual_phases=True)
5. AI decisions with full UI rendering and visualization
6. Deployment actions displayed in UI
```

#### Play Mode - Human vs AI (`--mode play --player1 human --player2 ai`)
```
Command Line: python scripts/main.py --mode play --player1 human --player2 ai

Flow:
1. Player 1 set to HUMAN, Player 2 set to AI
2. Full pygame UI initialization with HumanUIInterface
3. Manual setup phase progression (SPACE key required)
4. For DEPLOY_ARMIES phase:
   - decision_makers[player1.name] = HumanDeploymentDecisionMaker(ui_interface)
   - decision_makers[player2.name] = AIDeploymentDecisionMaker(agent)
   - game.execute_current_setup_phase(decision_makers=decision_makers, manual_phases=True)
5. Mixed interaction: Human clicks for deployment, AI auto-deploys on their turns
6. Full deployment action tracking and visualization
```

#### Play Mode - Human vs Human (`--mode play --player1 human --player2 human`)
```
Command Line: python scripts/main.py --mode play --player1 human --player2 human

Flow:
1. Both players set to HUMAN
2. Full pygame UI initialization with HumanUIInterface
3. Manual setup phase progression (SPACE key required)
4. For DEPLOY_ARMIES phase:
   - decision_makers[player1.name] = HumanDeploymentDecisionMaker(ui_interface)
   - decision_makers[player2.name] = HumanDeploymentDecisionMaker(ui_interface)
   - game.execute_current_setup_phase(decision_makers=decision_makers, manual_phases=True)
5. Both players use UI for all deployment decisions
6. Alternating human control with clear turn indicators
```

### Unified Deployment Execution

Regardless of player types or game mode, all deployment flows through the same execution path:

```python
# Core execution - identical for all modes and player types
class DeploymentManager:
    def execute_deployment_sequence(self, decision_makers: Dict[str, DeploymentDecisionMaker]) -> dict:
        # 1. Determine Attacker/Defender (dice roll)
        self.attacker, self.defender = self.determine_attacker_and_defender()
        
        # 2. Defender chooses deployment zone
        defender_decision_maker = decision_makers[self.defender.name]
        chosen_zone = defender_decision_maker.choose_deployment_zone(available_zones)
        
        # 3. Declare reserves (both players simultaneously)
        defender_reserves = defender_decision_maker.declare_reserves(self.defender)
        attacker_reserves = attacker_decision_maker.declare_reserves(self.attacker)
        
        # 4. Alternating deployment (defender first)
        self.execute_alternating_deployment(deployment_results, decision_makers)
        
        # 5. Determine first turn (attacker rolls)
        first_turn_player = self.determine_first_turn()
        
        return deployment_results
```

### Decision Maker Interface Consistency

All player types implement the same interface, ensuring API consistency:

```python
class DeploymentDecisionMaker(ABC):
    @abstractmethod
    def choose_deployment_zone(self, available_zones: List[dict]) -> dict:
        """Choose deployment zone as the defender."""
        pass
    
    @abstractmethod
    def declare_reserves(self, player: Player) -> dict:
        """Decide which units go into reserves, strategic reserves, or deploy normally."""
        pass
    
    @abstractmethod
    def choose_unit_deployment_position(self, unit: 'Unit', deployment_zone: dict, 
                                       already_deployed: List['Unit']) -> Tuple[float, float]:
        """Choose where to deploy a specific unit within the deployment zone."""
        pass
```

### Validation Consistency

**Critical**: All player types use identical validation functions, ensuring fair gameplay:

- **Deployment Position**: `is_valid_deployment_position()` - same for AI and human
- **Reserve Limits**: 50% unit/points limits enforced identically
- **Zone Boundaries**: Same deployment zone validation
- **Unit Restrictions**: Same infiltrate, deep strike, and positioning rules

### Special Cases and Edge Conditions

#### Human Players in Training Mode
```python
# If somehow --player1 human is specified with --mode train
if player_configs.get('training_mode', False):
    # Human players are converted to AI for training consistency
    decision_makers[player.name] = AIDeploymentDecisionMaker(agent)
```

#### Manual Phases in Training Mode
```python
# Training with observation: python scripts/main.py --mode train --manual-phases
# Allows step-by-step observation of AI training decisions
if training_mode and manual_phases:
    # Still pure AI vs AI, but with SPACE key progression for observation
```

#### UI Fallbacks for Human Players
```python
# If UI interface is not available, human players fall back to console input
if self.ui_interface:
    return self.ui_interface.choose_deployment_zone(available_zones)
else:
    # Console-based selection with text prompts
    return self.console_choose_deployment_zone(available_zones)
```

### Performance and Learning Characteristics

| **Mode** | **UI Rendering** | **AI Learning** | **Speed** | **Use Case** |
|----------|------------------|-----------------|-----------|--------------|
| **Training** | None | ✅ Active | Fast | AI development, automated learning |
| **Play - AI vs AI** | Full | ⚠️ Passive | Medium | AI demonstration, debugging |
| **Play - Human vs AI** | Full | ⚠️ Passive | Human-paced | Interactive gameplay, learning |
| **Play - Human vs Human** | Full | None | Human-paced | Pure human gameplay |

**Note**: In play mode, AI learning is "passive" - rewards are computed but policy updates are less frequent to maintain stable gameplay.

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

### 6. **API Consistency**
- Single source of truth for all deployment logic
- Identical validation functions for all player types
- Consistent behavior across training and play modes
- Fair gameplay regardless of player type combination

## Recent Enhancements

### Deployment Action Tracking
- Records all deployment decisions with locations
- Displays actions in UI near appropriate player roster
- Clear turn indicators during alternating deployment

### Validation Unification
- Removed duplicate deployment validation functions
- All players now use `is_valid_deployment_position()`
- Consistent rule enforcement across AI and human players

### Mode-Independent Architecture
- Training and play modes use identical core logic
- AI behavior is 100% consistent between modes
- Only UI rendering differs between modes

## Troubleshooting

### Common Issues and Solutions

**Deployment Validation Errors**: All players use the same validation functions, so if one player type can't deploy somewhere, neither can the other.

**AI Inconsistency Between Modes**: AI uses identical neural networks and decision logic in both training and play modes.

**Manual Phases Not Working**: Ensure you're using `--mode play` for interactive manual phases functionality.

**Human UI Not Responding**: Check that `ui_interface` is properly passed to `HumanDeploymentDecisionMaker`.

**Reserve Limits Not Enforced**: Both AI and human players enforce the same 50% unit/points limits through the decision maker interface.

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