# Warhammer 40,000 Rules Engine

Interactive Warhammer 40k 10th Edition rules implementation with a graphical UI, official setup phases, and full deployment sequencing.

## Features

- Official setup phases, deployment system, and battle round mechanics
- Interactive UI with unit details, deployment controls, and battlefield visualization
- Manual phase control for step-through gameplay with `--manual-phases`
- Wahapedia data import tooling for datasheets and rules
- Support matrices and rules coverage documentation

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
python3 -m get_wahapedia_data -f -c -o ../wahapedia_data -s ../wahapedia_data
cd ..
```

### Usage Examples

#### Interactive Gameplay
```bash
# Local vs local
python3 scripts/main.py --player1-army army_lists/chaos_test.txt --player2-army army_lists/aeldari_test.txt

# Manual phase control
python3 scripts/main.py --manual-phases
```

#### Data Exploration
```bash
# Browse Wahapedia data
python3 -m warhammer40k_ai.UI.wahapedia_ui
```

## Command Line Options

### Player Configuration
- `--player1-army <file>`: Army list file for Player 1 (default: army_lists/chaos_test.txt)
- `--player2-army <file>`: Army list file for Player 2 (default: army_lists/aeldari_test.txt)

### Advanced Options
- `--manual-phases`: Require SPACE key to advance phases

## Architecture

### Game System
- Complete setup phases: army loading, battlefield creation, attacker/defender determination, deployment, and first turn order
- Official deployment: alternating deployment with proper zones, reserves, and strategic reserves
- Battle round system: command, movement, shooting, charge, and fight phases with official rules

### User Interface
- Battlefield view: zoomable map with units, terrain, objectives, and deployment zones
- Roster panes: interactive unit lists showing health, equipment, and deployment status
- Info panel: game state, turn information, and deployment action tracking
- Unit details: comprehensive stat sheets with weapons, abilities, and rules

## Files and Documentation

- `README.md`: This file

### Documentation

- **Support matrices**
  - [Ability Support Matrix](docs/ABILITY_SUPPORT_MATRIX.md)
  - [Wargear Keyword Support Matrix](docs/WARGEAR_KEYWORD_SUPPORT_MATRIX.md)
  - [Optional Wargear Support Matrix](docs/OPTIONAL_WARGEAR_SUPPORT_MATRIX.md)
  - [Damaged Profile Support Matrix](docs/DAMAGED_PROFILE_SUPPORT_MATRIX.md)
- **Design/implementation docs**
  - [Player configuration](docs/PLAYER_CONFIGURATION.md)
  - [Deployment architecture](docs/DEPLOYMENT_ARCHITECTURE.md)
  - [Mission deployment system](docs/MISSION_DEPLOYMENT_SYSTEM.md)
  - [Mission selection dialog](docs/MISSION_SELECTION_DIALOG.md)
  - [Reserve limits implementation](docs/RESERVE_LIMITS_IMPLEMENTATION.md)
  - [Ruins terrain system](docs/RUINS_TERRAIN_SYSTEM.md)
  - [Pile-in implementation](docs/PILE_IN_IMPLEMENTATION.md)

## Project Structure

```
Warhammer40k_AI/
|-- README.md
|-- AGENTS.md
|-- scripts/
|   |-- main.py
|-- src/warhammer40k_ai/
|   |-- battlefield/
|   |   |-- map.py
|   |   |-- terrain_layouts.py
|   |-- engine/
|   |   |-- game.py
|   |   |-- phase.py
|   |   |-- turn_manager.py
|   |   |-- deployment.py
|   |   |-- fight_phase_manager.py
|   |   |-- mission_cards.py
|   |   |-- missions.py
|   |   |-- commands.py
|   |   |-- decisions.py
|   |   |-- random_source.py
|   |-- roster/
|   |   |-- army.py
|   |   |-- army_muster.py
|   |   |-- player.py
|   |-- rules/
|   |   |-- stratagems.py
|   |   |-- enhancement.py
|   |   |-- detachment_registry.py
|   |   |-- <faction>_detachments.py
|   |-- units/
|   |   |-- unit.py
|   |   |-- model.py
|   |   |-- wargear.py
|   |   |-- ability.py
|   |   |-- status_effects.py
|   |-- UI/
|   |   |-- game_ui.py
|   |   |-- panels/
|   |   |-- dialogs/
|   |   |-- ui_utils.py
|   |   |-- wahapedia_ui.py
|   |-- utility/
|   |   |-- calcs.py
|   |   |-- aura_utils.py
|   |   |-- event_bus.py
|   |   |-- dice.py
|   |   |-- model_base.py
|   |   |-- modifiers.py
|   |-- waha_helper/
|   |   |-- waha_helper.py
|-- army_lists/
|-- docs/
|-- tests/
|-- wahapedia_data/
|-- RuleSets/
```

### Directory and File Roles

- `README.md`: Project overview, setup, and architecture snapshot.
- `AGENTS.md`: Local development instructions for Codex.
- `scripts/`: Entry points and helper scripts (including `main.py`).
- `src/warhammer40k_ai/battlefield/`: Map geometry, terrain layouts, objectives, and placement rules.
- `src/warhammer40k_ai/engine/`: Game loop, setup/phase flow, missions, and decision plumbing.
- `src/warhammer40k_ai/roster/`: Army composition, mustering, and player ownership.
- `src/warhammer40k_ai/rules/`: Rule managers, detachments, enhancements, stratagems, and faction logic.
- `src/warhammer40k_ai/units/`: Unit/model/wargear primitives plus status effects.
- `src/warhammer40k_ai/UI/`: Rendering and interactive UI; no core rules live here.
- `src/warhammer40k_ai/utility/`: Shared helpers (geometry, dice, modifiers, event bus).
- `src/warhammer40k_ai/waha_helper/`: Wahapedia data ingestion and lookup helpers.
- `army_lists/`: Example army lists for quick runs.
- `docs/`: Design and support documentation.
- `tests/`: Automated tests.
- `wahapedia_data/`: Extracted data assets (not committed).
- `RuleSets/`: Static ruleset sources and references.

## License

This project is licensed under the MIT License.
