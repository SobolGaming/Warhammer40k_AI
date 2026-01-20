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

2. **Updated Warhammer 40k Data**:
```bash
python3 scripts/get_wahapedia_data.py -f -c -o wahapedia_data -s wahapedia_data
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
  - [Ability Support Matrix](docs/ABILITY_SUPPORT_MATRIX.md): engine support status for abilities and stratagems.
  - [Wargear Keyword Support Matrix](docs/WARGEAR_KEYWORD_SUPPORT_MATRIX.md): wargear keyword behavior coverage.
  - [Optional Wargear Support Matrix](docs/OPTIONAL_WARGEAR_SUPPORT_MATRIX.md): optional wargear and replacement rules support.
  - [Damaged Profile Support Matrix](docs/DAMAGED_PROFILE_SUPPORT_MATRIX.md): damaged profile handling coverage.
- **Rules and mechanics**
  - [Charge roll modifiers](docs/CHARGE_ROLL_MODIFIERS.md): parsing and application of charge modifiers.
  - [Mortal wounds](docs/MORTAL_WOUNDS.md): mortal wound timing and spillover handling.
  - [Melee target allocation](docs/MELEE_TARGET_ALLOCATION.md): multi-target melee allocation flow.
  - [Pile-in and consolidate implementation](docs/PILE_IN_AND_CONSOLIDATE_IMPLEMENTATION.md): fight-phase move rules and constraints.
  - [Ruins terrain system](docs/RUINS_TERRAIN_SYSTEM.md): terrain, floors, and line-of-sight behavior in ruins.
  - [Reserve limits implementation](docs/RESERVE_LIMITS_IMPLEMENTATION.md): reserve caps and enforcement.
- **Setup, UI, and decisions**
  - [Deployment architecture](docs/DEPLOYMENT_ARCHITECTURE.md): deployment sequence and decision flow.
  - [Mission deployment system](docs/MISSION_DEPLOYMENT_SYSTEM.md): mission-specific deployment steps and logic.
  - [Mission selection dialog](docs/MISSION_SELECTION_DIALOG.md): mission selection UI flow.
  - [Army mustering scaffolding](docs/ARMY_MUSTERING_SCAFFOLDING.md): current in-engine mustering placeholders.
  - [Dialog manager](docs/DIALOG_MANAGER.md): modal dialog routing and stacking behavior.
  - [Player configuration](docs/PLAYER_CONFIGURATION.md): controller ownership and UI enablement.
- **Networking and save/load**
  - [Network + save/load design](docs/NETWORK_SAVELOAD_DESIGN.md): snapshot, event log, and decision API plan.
- **Faction support docs**
  - [Adepta Sororitas](docs/factions/adepta_sororitas.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Adeptus Custodes](docs/factions/adeptus_custodes.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Adeptus Mechanicus](docs/factions/adeptus_mechanicus.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Aeldari](docs/factions/aeldari.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Astra Militarum](docs/factions/astra_militarum.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Chaos Daemons](docs/factions/chaos_daemons.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Chaos Knights](docs/factions/chaos_knights.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Chaos Space Marines](docs/factions/chaos_space_marines.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Death Guard](docs/factions/death_guard.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Drukhari](docs/factions/drukhari.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Emperor's Children](docs/factions/emperor_s_children.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Genestealer Cults](docs/factions/genestealer_cults.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Grey Knights](docs/factions/grey_knights.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Imperial Agents](docs/factions/imperial_agents.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Imperial Knights](docs/factions/imperial_knights.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Leagues of Votann](docs/factions/leagues_of_votann.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Necrons](docs/factions/necrons.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Orks](docs/factions/orks.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Space Marines](docs/factions/space_marines.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [T'au Empire](docs/factions/t_au_empire.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Thousand Sons](docs/factions/thousand_sons.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [Tyranids](docs/factions/tyranids.md): faction abilities, detachments, stratagems, enhancements, datasheets.
  - [World Eaters](docs/factions/world_eaters.md): faction abilities, detachments, stratagems, enhancements, datasheets.

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
