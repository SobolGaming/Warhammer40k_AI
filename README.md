# Warhammer 40,000 Rules Engine

Interactive Warhammer 40k 10th Edition rules implementation with a graphical UI, official setup phases, and full deployment sequencing.

The repository is now in an 11th-edition-first port-prep phase. Structural work is
landing behind stable façades so release-day 11th rules ingestion can happen
cleanly without carrying a long-lived dual-edition architecture. See
`docs/implementation/11e_port_pr_plan.md` for the migration guardrails and PR
status.

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

### Optional ML Setup

Install optional ML dependencies only when you are working on ML-boundary components.

```bash
# Recommended: isolated virtual environment
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux/macOS
# source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -e ".[ml]"
```

Verify optional ML dependencies are visible:

```bash
python -c "from warhammer40k_ai.ml import detect_ml_dependency_status; print(detect_ml_dependency_status().to_dict())"
```

Expected result:
- `"ready": True`
- `missing_packages` is empty

2. **Updated Warhammer 40k Data**:
```bash
python3 scripts/get_wahapedia_data.py -f -c -o wahapedia_data -s wahapedia_data
python3 scripts/diff_wahapedia_data.py --old wahapedia_data/Archive/ --new wahapedia_data/ --out docs/wahapedia_diff.txt
```

Afterwards, I issue the following prompt to GPT-5.3-Codex:
```bash
Review the latest wahapedia pull resulting in docs/wahapedia_diff.txt and summarize what the changes are in terms of what factions, detachments, enhancements, stratagems, units or unit abilitty or datasheet changes have occurred. Also, inform me if any of the changes, and which ones, require us to modify any implemented engine behavior.
```

### Usage Examples

#### Interactive Gameplay
```bash
# Local vs local
python3 scripts/main.py --player1-army army_lists/chaos_test.txt --player2-army army_lists/aeldari_test.txt

# Manual phase control
python3 scripts/main.py --manual-phases
```

#### Network Play (Server/Client)
```bash
# Server (TLS required)
python3 -m warhammer40k_ai.network.cli server --host 0.0.0.0 --port 40000 --cert tests/fixtures/tls/server.crt --key tests/fixtures/tls/server.key

# Client 1 (Player 1, pygame UI)
python3 -m warhammer40k_ai.network.cli client-ui --server wss://localhost:40000 --ca-cert tests/fixtures/tls/server.crt --display-name "Player One" --role player1 --army-file army_lists/chaos_test.txt --ready

# Client 2 (Player 2, headless)
python3 -m warhammer40k_ai.network.cli client --server wss://localhost:40000 --ca-cert tests/fixtures/tls/server.crt --display-name "Player Two" --role player2 --army-file army_lists/aeldari_test.txt --ready

# Spectator (pygame UI)
python3 -m warhammer40k_ai.network.cli client-ui --server wss://localhost:40000 --ca-cert tests/fixtures/tls/server.crt --display-name "Spectator One" --role spectator
```

Notes:
- The server requires TLS. For local/dev testing, self-signed certs are provided in `tests/fixtures/tls/`.
- For custom certs, generate your own and pass `--cert`/`--key`.
- Clients can pass `--insecure` for dev-only TLS bypass (not recommended).
- Use `client-ui` for human players (pygame UI); use `client` for headless AI/spectator tooling.
- Spectators can join at any time (including mid-game) and are read-only.

#### Data Exploration
```bash
# Browse Wahapedia data
python3 -m warhammer40k_ai.UI.wahapedia_ui
```

#### Headless Self-Play Data (Baseline)
```bash
# Generate headless self-play DecisionRecords (with reward labels)
python scripts/run_headless_self_play.py --games 5 --workers 2 --reserve-policy forced_only --max-reserves-arrival-seconds 10 --player1-army army_lists/chaos_test.txt --player2-army army_lists/aeldari_test.txt --output data/headless_self_play_decision_records.json

# Optional: also persist per-game replay sessions for UI playback
python scripts/run_headless_self_play.py --games 5 --workers 2 --reserve-policy forced_only --max-reserves-arrival-seconds 10 --player1-army army_lists/chaos_test.txt --player2-army army_lists/aeldari_test.txt --output data/headless_self_play_decision_records.json --replay-dir data/headless_self_play_replays

# Step through one recorded game in the replay viewer
python scripts/replay_viewer.py --session-id selfplay:000000 --replay-dir data/headless_self_play_replays

# Relabel records to a target rules bundle before gate enforcement
python scripts/relabel_decision_records.py \
  --input data/headless_self_play_decision_records.json \
  --output data/headless_self_play_decision_records_relabeled.json

# Optional: re-annotate rewards on an existing relabeled DecisionRecord file
python scripts/annotate_decision_rewards.py \
  --input data/headless_self_play_decision_records_relabeled.json \
  --output data/headless_self_play_decision_records_rewarded.json \
  --reward-profile dense_vp_delta_v1

# Build and enforce the canonical pre-ML manifest gate (judges whether the games were meaningful)
python scripts/build_training_manifest.py --input data/headless_self_play_decision_records_rewarded.json --output data/training_manifest.json --source-tag self_play --enforce-gate-profile

# Gate profile now checks dataset quality in addition to schema coverage:
# - minimum games observed / game_id coverage
# - tactical-decision density per game
# - combat-or-scoring activity ratio
# - no-progress game ratio
# - nontrivial VP game ratio
# Full workflow guidance: docs/HEADLESS_SELF_PLAY_RUNBOOK.md
# Replay viewer workflow: generate with --replay-dir, then open via scripts/replay_viewer.py
# Throughput tip: use --workers <N> for parallel game generation.
# Stability defaults: forced-only reserves declaration + 10s per-unit reserves-arrival cap.
```

## Command Line Options

### Player Configuration
- `--player1-army <file>`: Army list file for Player 1 (default: army_lists/chaos_test.txt)
- `--player2-army <file>`: Army list file for Player 2 (default: army_lists/aeldari_test.txt)

### Advanced Options
- `--manual-phases`: Require SPACE key to advance phases

## Testing

```bash
# Full suite (parallel by default via setup.cfg)
python -m pytest tests/

# Fast feedback lane: skip long integration/slow tests
python -m pytest tests/ -m "not slow and not integration"

# Explicit full run with worker/process details
python -m pytest tests/ -n auto --dist loadscope
```

Marker conventions:
- `@pytest.mark.slow`: expensive deterministic tests.
- `@pytest.mark.integration`: multi-subsystem end-to-end flows (network, persistence, full parsing).

## Architecture

For a high-level overview of the codebase structure and data flow, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Game System
- Complete setup phases: army loading, battlefield creation, attacker/defender determination, deployment, and first turn order
- Official deployment: alternating deployment with proper zones, reserves, and strategic reserves
- Battle round system: command, movement, shooting, charge, and fight phases with official rules
- `src/warhammer40k_ai/engine/game.py` is the `Game` facade and orchestration entry point.
- Heavy phase and rules-timing handlers are split into focused mixins under `src/warhammer40k_ai/engine/game_mixins/`.

### Unit Architecture
- `src/warhammer40k_ai/units/unit.py` is the facade/entry module for `Unit`, `UnitRoundState`, `MovementAction`, and `MovementState`.
- Heavy `Unit` behavior is split into focused mixins under `src/warhammer40k_ai/units/unit_mixins/` for easier maintenance and safer code review.
- External imports remain stable (`from warhammer40k_ai.units.unit import Unit`), while internal behavior is specialized by phase/domain.

### Stratagem Architecture
- `src/warhammer40k_ai/rules/stratagems.py` remains the `StratagemManager` facade and orchestration layer.
- Faction/detachment-specific target-selection helpers are progressively split into focused modules (for example `stratagems_world_eaters.py`, `stratagems_chaos_knights.py`, `stratagems_chaos_daemons.py`, `stratagems_necrons.py`, `stratagems_aeldari.py`, `stratagems_orks.py`) to keep stratagem logic maintainable as detachments expand.
- Shared stratagem targetability rules stay centralized (`_unit_cannot_be_target_of_stratagem`) and are reused by specialized modules.

### AI Reintroduction Foundations
- `src/warhammer40k_ai/engine/decision_record.py`: DecisionRecord emission, schema checks, invalid-attempt logging, and HumanActionCandidate injection.
- `src/warhammer40k_ai/engine/state_blob.py`: deterministic omniscient and per-player observation state blobs.
- `src/warhammer40k_ai/engine/replay.py`: DecisionRecord replay path with strict candidate/mask drift checks.
- `src/warhammer40k_ai/engine/time_manager.py`: per-decision budget policy with compute-tier multipliers.
- `src/warhammer40k_ai/engine/tier1_plan.py`: deterministic Tier-1 strategic plan schema and baseline heuristic planner.
- `src/warhammer40k_ai/engine/tier2_orchestrator.py`: deterministic Tier-2 per-unit task scaffolding with movement-intent emission.
- `src/warhammer40k_ai/engine/movement_intent.py`, `src/warhammer40k_ai/engine/movement_solver.py`, and `src/warhammer40k_ai/engine/path_witness.py`: movement-intent driven candidates, PathWitness refs, and continuous path/tight-clearance validation.

### User Interface
- Battlefield view: zoomable map with units, terrain, objectives, and deployment zones
- Roster panes: interactive unit lists showing health, equipment, and deployment status
- Info panel: game state, turn information, and deployment action tracking
- Unit details: comprehensive stat sheets with weapons, abilities, and rules

## Files and Documentation

- `README.md`: This file

### Documentation

- **AI planning and telemetry**
  - [AI reintroduction plan](docs/AI_REINTRODUCTION_PLAN.md): HRL architecture, movement solver design, and training roadmap.
    - Roadmap status: PR1-PR15 completed (see Engineering Roadmap section in the plan).
  - [ML dependency boundary](docs/ML_DEPENDENCY_BOUNDARY.md): optional ML extras, runtime guards, and core/ML dependency-lane separation.
  - [Headless self-play runbook](docs/HEADLESS_SELF_PLAY_RUNBOOK.md): end-to-end AI-vs-AI data generation, reward annotation, and quality-gate evaluation.
  - [Training reward profiles](docs/TRAINING_REWARD_PROFILES.md): deterministic reward-label profiles and annotation pipeline.
  - [DecisionRecord schema](docs/DECISION_RECORD_SCHEMA.json): telemetry contract for human/AI decisions and replay.
  - [DecisionRecord telemetry](docs/DECISION_RECORD_TELEMETRY.md): runtime record guarantees and required fields.
  - [DecisionRecord replay](docs/DECISION_RECORD_REPLAY.md): strict replay guarantees and failure modes.
  - [StateBlob schema](docs/STATE_BLOB_SCHEMA.md): canonical omniscient/player observation payload contract.
  - [Tier 1 plan schema](docs/TIER1_PLAN_SCHEMA.md): strategic plan payload and baseline behavior.
  - [Tier 2 orchestration](docs/TIER2_ORCHESTRATION.md): per-unit task bundle scaffolding and context wiring.
  - [Time manager policy](docs/TIME_MANAGER_POLICY.md): decision budgets, compute-tier multipliers, and fallback behavior.
  - [MovementIntent](docs/MOVEMENT_INTENT.md): movement-intent schema and candidate metrics.
  - [PathWitness contract](docs/PATH_WITNESS_CONTRACT.md): witness fields and validation invariants.
  - [Tight clearance policy](docs/TIGHT_CLEARANCE_POLICY.md): clearance profiling and orientation constraints.
- **Support matrices**
  - [Ability Support Matrix](docs/ABILITY_SUPPORT_MATRIX.md): engine support status for abilities and stratagems.
  - [Wargear Keyword Support Matrix](docs/WARGEAR_KEYWORD_SUPPORT_MATRIX.md): wargear keyword behavior coverage.
  - [Optional Wargear Support Matrix](docs/OPTIONAL_WARGEAR_SUPPORT_MATRIX.md): optional wargear and replacement rules support.
  - [Damaged Profile Support Matrix](docs/DAMAGED_PROFILE_SUPPORT_MATRIX.md): damaged profile handling coverage.
- **Rules and mechanics**
  - [Movement system](docs/MOVEMENT_SYSTEM.md): pathing, coherency, and movement types.
  - [Model geometry overrides](docs/MODEL_GEOMETRY_OVERRIDES.md): hull/compound footprints, model height, and flying-base z-offset resolution.
  - [Mortal wounds](docs/MORTAL_WOUNDS.md): mortal wound timing and spillover handling.
  - [Melee target allocation](docs/MELEE_TARGET_ALLOCATION.md): multi-target melee allocation flow.
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
  - [Network gameplay plan](docs/NETWORK_GAMEPLAY.md): asyncio WebSocket architecture, lobby flow, and role-based play.
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
|   |   |-- game_mixins/
|   |   |   |-- setup_deployment_reserves_mixin.py
|   |   |   |-- missions_scoring_actions_mixin.py
|   |   |   |-- reactive_decisions_mixin.py
|   |   |   |-- shooting_fight_handlers_mixin.py
|   |   |   |-- phase_handlers_mixin.py
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
|   |   |-- stratagems_world_eaters.py
|   |   |-- stratagems_chaos_knights.py
|   |   |-- stratagems_chaos_daemons.py
|   |   |-- stratagems_necrons.py
|   |   |-- stratagems_aeldari.py
|   |   |-- stratagems_orks.py
|   |   |-- enhancement.py
|   |   |-- detachment_registry.py
|   |   |-- <faction>_detachments.py
|   |-- units/
|   |   |-- unit.py
|   |   |-- unit_mixins/
|   |   |   |-- _common.py
|   |   |   |-- rules_parsing_mixin.py
|   |   |   |-- datasheet_wargear_mixin.py
|   |   |   |-- damage_death_mixin.py
|   |   |   |-- state_attachment_mixin.py
|   |   |   |-- actions_movement_mixin.py
|   |   |   |-- shooting_mixin.py
|   |   |   |-- positioning_mixin.py
|   |   |   |-- keywords_detachments_mixin.py
|   |   |   |-- ability_specs_mixin.py
|   |   |   |-- late_gameplay_mixin.py
|   |   |-- model.py
|   |   |-- wargear.py
|   |   |-- ability.py
|   |   |-- status_effects.py
|   |-- network/
|   |   |-- transport.py
|   |   |-- lobby.py
|   |   |-- control.py
|   |   |-- server.py
|   |   |-- client.py
|   |   |-- cli.py
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
|   |-- fixtures/
|   |   |-- tls/
|-- wahapedia_data/
|-- RuleSets/
```

### Directory and File Roles

- `README.md`: Project overview, setup, and architecture snapshot.
- `AGENTS.md`: Local development instructions for Codex.
- `scripts/`: Entry points and helper scripts (including `main.py`).
- `src/warhammer40k_ai/battlefield/`: Map geometry, terrain layouts, objectives, and placement rules.
- `src/warhammer40k_ai/engine/`: Game loop, setup/phase flow, missions, and decision plumbing.
  - `game.py`: public `Game` facade/composition root.
  - `game_mixins/`: specialized `Game` behavior slices by phase/domain timing.
- `src/warhammer40k_ai/roster/`: Army composition, mustering, and player ownership.
- `src/warhammer40k_ai/rules/`: Rule managers, detachments, enhancements, stratagems, and faction logic.
- `src/warhammer40k_ai/units/`: Unit/model/wargear primitives plus status effects.
  - `unit.py`: public `Unit` facade and shared enums/state objects.
  - `unit_mixins/`: specialized `Unit` behavior slices (parsing, wargear, movement, shooting, damage, reserves, specs).
- `src/warhammer40k_ai/network/`: WebSocket transport, lobby state, control protocol, server/client orchestration.
- `src/warhammer40k_ai/UI/`: Rendering and interactive UI; no core rules live here.
- `src/warhammer40k_ai/utility/`: Shared helpers (geometry, dice, modifiers, event bus).
- `src/warhammer40k_ai/waha_helper/`: Wahapedia data ingestion and lookup helpers.
- `army_lists/`: Example army lists for quick runs.
- `docs/`: Design and support documentation.
- `tests/`: Automated tests.
- `tests/fixtures/tls/`: Self-signed TLS certs used by network integration tests.
- `wahapedia_data/`: Extracted data assets (not committed).
- `RuleSets/`: Static ruleset sources and references.

## License

This project is licensed under the MIT License.
