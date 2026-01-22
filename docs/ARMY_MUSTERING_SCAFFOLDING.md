## Army Mustering Scaffolding

This document describes the current Army Mustering scaffolding in the engine and UI.
It is intentionally minimal and will be updated as full UI army mustering is implemented,
especially alongside the work in `docs/NETWORK_SAVELOAD_DESIGN.md`.

### Scope and intent

Army mustering exists today primarily to:
- load armies from list files during setup, or
- accept a minimal in-engine request for faction/detachment/points only.

Full unit selection, wargear, enhancements, and roster validation are not implemented.

### Current scaffolding components

#### Data model

- `UnitSelection` (`src/warhammer40k_ai/roster/army_muster.py`)
  - Placeholder record for future unit picks.
  - Fields include name, count, wargear, enhancements, and `is_warlord`.
  - Not used in the engine yet.
- `ArmyMusterRequest` (`src/warhammer40k_ai/roster/army_muster.py`)
  - Minimal request for in-engine mustering.
  - Fields: `faction`, `detachment_type`, `points_limit`, and `units`.
  - `units` must be empty today or `NotImplementedError` is raised.

#### Muster execution

- `ArmyMusterer.muster_army()` (`src/warhammer40k_ai/roster/army_muster.py`)
  - Validates the request, resolves faction ID, and constructs a basic `Army`.
  - Calls `Army.configure_rule_managers()` and ignores errors (placeholder behavior).
  - Rejects non-empty `units` with `NotImplementedError`.

- `Game.execute_muster_armies_phase()` (`src/warhammer40k_ai/engine/game.py`)
  - Runs during setup phase `MUSTER_ARMIES`.
  - If `player1_muster` / `player2_muster` are provided, uses `ArmyMusterer`.
  - Otherwise loads from army list files via `parse_army_list()`.
  - Uses defaults if no files are provided:
    - player1: `army_lists/warhammer_app_dump.txt`
    - player2: `army_lists/chaos_daemons_GT2023.txt`
  - After army load, resolves Daemonic Allegiance choices:
    - If a player has local control and the event system is configured,
      publishes `daemonic_allegiance_prompt`.
    - Otherwise resolves allegiances automatically.

#### UI touchpoints

- Setup flow: `SetupPhaseHandler` (`src/warhammer40k_ai/UI/phases/phase_manager.py`)
  - Spacebar advances setup phases.
  - After `MUSTER_ARMIES`, the UI refreshes roster panes.
- Daemonic Allegiance dialog: `src/warhammer40k_ai/UI/dialogs/daemonic_allegiance_dialog.py`
  - Modal dialog that supports a mustering-only choice.
- Info pane label: `src/warhammer40k_ai/UI/panels/info_pane.py`
  - Shows "Loading army lists and preparing forces" during `MUSTER_ARMIES`.

#### Save/load scaffolding

- `army_muster_requests` is included in game snapshots:
  - Serialized in `_serialize_game_state()` and restored in `_apply_game_state()`
    in `src/warhammer40k_ai/engine/snapshot.py`.
- This is a minimal placeholder for future network-safe mustering inputs.
  See `docs/NETWORK_SAVELOAD_DESIGN.md` for serialization requirements.

### Current limitations

- Unit selection and validation are not implemented for in-engine mustering.
- Wargear, enhancements, and warlord selection are not applied for in-engine mustering
  (army list parsing applies them and validates enhancement eligibility).
- Detachment rules and mustering restrictions are not enforced by the scaffolding.
- `Army.configure_rule_managers()` errors are suppressed in the mustering path.
- Mustering choices are not yet represented as decision requests in the engine
  (except for Daemonic Allegiance prompts when applicable).

### Expected evolution (linked to network/save/load work)

When full UI mustering is implemented, this scaffolding is expected to grow into:
- a serializable, decision-driven mustering flow aligned with
  `docs/NETWORK_SAVELOAD_DESIGN.md`,
- explicit decision requests for faction, detachment, unit picks, wargear,
  enhancements, and warlord selection,
- validation of points limits, mustering restrictions, and spawn-only units,
- stable IDs for unit selections so networked clients can replay the same choices.
