# Warhammer 40k Deployment System Architecture

## Overview

The deployment system implements the official Warhammer 40k 10th Edition deployment sequence. It uses a unified API that supports UI-driven decisions and future external controllers, with optional manual phase control.

## Core Architecture Principles

1. **Single source of truth**: All deployment logic flows through `DeploymentManager`.
2. **Decision-maker abstraction**: Deployment choices are handled through `DeploymentDecisionMaker`.
3. **Consistent validation**: All inputs use the same rule checks for zones, reserves, and unit restrictions.

## Decision Maker Interface

All controllers implement the same interface, ensuring consistent behavior:

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

### Human Deployment Decision Maker

`HumanDeploymentDecisionMaker` drives UI or console input:

- **UI path**: Click-based zone selection and placement
- **Console fallback**: Text prompts when UI is unavailable

## Unified Deployment Execution

Regardless of controller, the flow is identical:

```python
class DeploymentManager:
    def execute_deployment_sequence(self, decision_makers: Dict[str, DeploymentDecisionMaker]) -> dict:
        self.attacker, self.defender = self.determine_attacker_and_defender()
        defender_decision_maker = decision_makers[self.defender.name]
        chosen_zone = defender_decision_maker.choose_deployment_zone(available_zones)
        defender_reserves = defender_decision_maker.declare_reserves(self.defender)
        attacker_reserves = attacker_decision_maker.declare_reserves(self.attacker)
        self.execute_alternating_deployment(deployment_results, decision_makers)
        first_turn_player = self.determine_first_turn()
        return deployment_results
```

## Validation Consistency

All controllers use the same validation rules:

- Deployment position validation via `is_valid_deployment_position()`
- Reserve limits enforced by `Army` helper methods
- Zone boundary checks and mission polygon validation
- Unit restrictions (infiltrate, deep strike, must-start-in-reserves)

## UI Integration

`GameView` and the UI panels provide:

- Deployment zone visualization and labels
- Turn indication during alternating deployment
- Deployment action tracking in the info panel
- Manual phase indicators

## Manual Phases Integration

Manual phases require SPACE to advance:

- Setup phases advance one at a time
- Deployment actions wait between each unit placement
- Battle rounds advance phase-by-phase

## File Structure

```
src/warhammer40k_ai/
|-- classes/
|   |-- deployment.py          # Core deployment system
|   |-- game.py                # Game state and setup phase management
|-- UI/
|   |-- game_ui.py             # UI deployment features
scripts/main.py                # Main entry point
```

This architecture keeps deployment rules centralized and consistent while supporting UI-driven decisions and future external controllers.
