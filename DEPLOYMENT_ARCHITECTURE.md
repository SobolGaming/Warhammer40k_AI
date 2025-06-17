# Warhammer 40k Deployment System Architecture

## Overview

The deployment system has been refactored to properly separate the core game mechanics from AI-specific implementation. This follows the principle that game rules should be independent of whether players are AI or human.

## Architecture Components

### 1. Core Deployment System (`src/warhammer40k_ai/classes/deployment.py`)

#### `DeploymentManager`
- **Purpose**: Implements the official Warhammer 40k 10th Edition deployment sequence
- **Independence**: Works with any player type (AI, Human, or mixed)
- **Responsibilities**:
  - Determine Attacker/Defender via dice roll
  - Manage deployment zone selection
  - Handle reserves declarations
  - Execute alternating deployment
  - Determine first turn player

#### `DeploymentDecisionMaker` (Abstract Base Class)
- **Purpose**: Interface for making deployment decisions
- **Methods**:
  - `choose_deployment_zone()`: Select deployment zone (defender only)
  - `declare_reserves()`: Decide unit reserves/deployment
  - `choose_unit_deployment_position()`: Position units within zones

#### `HumanDeploymentDecisionMaker`
- **Purpose**: Implementation for human players
- **Features**:
  - UI integration support
  - Fallback defaults when no UI available
  - Can be extended for different UI systems

### 2. AI Integration (`src/warhammer40k_ai/agents/hrl_agent.py`)

#### `AIDeploymentDecisionMaker`
- **Purpose**: AI implementation of deployment decisions
- **Integration**: Connects to `HighLevelAgent` neural networks
- **Learning**: Computes and stores rewards for policy updates

#### Enhanced `HighLevelAgent`
- **New Networks**:
  - `deployment_zone_net`: Choose deployment zone
  - `reserves_selection_net`: Reserves vs deploy decisions
  - `unit_deployment_net`: Unit positioning within zones
- **Learning**: Separate policy updates for each decision type

## Official Warhammer 40k Deployment Sequence

The system implements the official 10th Edition deployment rules:

1. **🎲 Determine Attacker and Defender**
   - Roll-off with D6 dice
   - Winner becomes Attacker, loser is Defender
   - Re-roll ties

2. **🎯 Defender Chooses Deployment Zone**
   - Defender selects from available zones
   - Attacker gets the remaining zone

3. **📦 Declare Reserves & Strategic Reserves**
   - Both players simultaneously decide:
     - Deploy normally
     - Put in Reserves (Deep Strike, etc.)
     - Put in Strategic Reserves (board edge)

4. **🚢 Alternating Deployment**
   - Defender deploys first unit
   - Players alternate until all units deployed
   - Only units not in reserves are deployed

5. **🥇 Determine First Turn**
   - Attacker rolls D6
   - 1-3: Defender goes first
   - 4-6: Attacker goes first

## Usage Examples

### AI vs AI Deployment
```python
from warhammer40k_ai.classes.deployment import DeploymentManager
from warhammer40k_ai.agents.hrl_agent import HighLevelAgent, AIDeploymentDecisionMaker

# Create agents
player1_agent = HighLevelAgent(game, player1, player2, objectives, commands)
player2_agent = HighLevelAgent(game, player2, player1, objectives, commands)

# Create decision makers
decision_makers = {
    player1.name: AIDeploymentDecisionMaker(player1_agent),
    player2.name: AIDeploymentDecisionMaker(player2_agent)
}

# Execute deployment
deployment_manager = DeploymentManager(game)
results = deployment_manager.execute_deployment_sequence(decision_makers)
```

### Human vs AI Deployment
```python
from warhammer40k_ai.classes.deployment import DeploymentManager, HumanDeploymentDecisionMaker

# Create decision makers
decision_makers = {
    human_player.name: HumanDeploymentDecisionMaker(ui_interface),
    ai_player.name: AIDeploymentDecisionMaker(ai_agent)
}

# Execute deployment (same interface!)
deployment_manager = DeploymentManager(game)
results = deployment_manager.execute_deployment_sequence(decision_makers)
```

### Human vs Human Deployment
```python
# Create decision makers (both human)
decision_makers = {
    player1.name: HumanDeploymentDecisionMaker(ui_interface),
    player2.name: HumanDeploymentDecisionMaker(ui_interface)
}

# Execute deployment (same interface!)
deployment_manager = DeploymentManager(game)
results = deployment_manager.execute_deployment_sequence(decision_makers)
```

## Benefits of This Architecture

### 1. **Separation of Concerns**
- Game rules are independent of player type
- AI learning is separate from core mechanics
- UI integration is modular

### 2. **Flexibility**
- Supports any combination of player types
- Easy to add new decision-making implementations
- Consistent interface regardless of player type

### 3. **Extensibility**
- New deployment rules can be added to `DeploymentManager`
- Different AI approaches can implement `DeploymentDecisionMaker`
- UI systems can be plugged in via `HumanDeploymentDecisionMaker`

### 4. **Maintainability**
- Clear boundaries between components
- Easy to test individual components
- Changes to rules don't affect AI code and vice versa

## Integration with Existing Code

To integrate this system:

1. **Replace existing deployment**: Replace `auto_deploy_units()` calls with the new system
2. **Add unit abilities**: Implement methods like `unit.has_deep_strike()` for reserves decisions
3. **UI integration**: Connect `HumanDeploymentDecisionMaker` to your UI system
4. **Add objectives**: Provide objectives list to agents for strategic decisions

## File Structure

```
src/warhammer40k_ai/
├── classes/
│   ├── deployment.py          # Core deployment system
│   └── __init__.py           # Export deployment classes
├── agents/
│   └── hrl_agent.py          # AI-specific deployment integration
└── ...

deployment_example.py          # Usage examples
DEPLOYMENT_ARCHITECTURE.md    # This documentation
```

This architecture ensures that the deployment system follows proper software engineering principles while implementing the official Warhammer 40k rules accurately for all player types. 