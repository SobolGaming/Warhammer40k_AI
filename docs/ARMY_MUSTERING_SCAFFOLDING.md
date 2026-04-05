## Army Mustering Scaffolding

This document describes the current Army Mustering scaffolding in the engine and UI.
It is still incomplete from a full in-engine roster-authoring perspective, but PR-002
introduced a real build-side army model so list construction meaning no longer lives only
inside the runtime `Army` object.

### Scope and intent

Army mustering exists today primarily to:
- load armies from list files during setup, or
- accept a serializable in-engine build request that can already represent the main
  11th-edition list-building seams.

Runtime unit materialization from those requests is still pending. Parsed list files remain
the only path that builds full runtime units today.

### Current scaffolding components

#### Data model

- `ArmyBlueprint` (`src/warhammer40k_ai/roster/army_build.py`)
  - Build-time representation of army construction.
  - Holds battle size, points limit, detachment selections, unit entries,
    enhancement assignments, attachment bindings, and Force Disposition data.
- `DetachmentSelection` (`src/warhammer40k_ai/roster/army_build.py`)
  - Represents one selected detachment and its detachment-point cost.
- `DetachmentInstance` (`src/warhammer40k_ai/roster/army_runtime.py`)
  - Runtime counterpart of `DetachmentSelection`.
  - Carries runtime detachment identity, owning faction, detachment type, and detachment-point cost.
- `RosterEntry` (`src/warhammer40k_ai/roster/army_build.py`)
  - Build-side unit entry used before runtime `Unit` objects are materialized.
- `EnhancementAssignment` (`src/warhammer40k_ai/roster/army_build.py`)
  - Explicit enhancement-to-unit assignment record.
  - Its metadata can now represent upgrade-tag targeting for eligible non-Character units.
- `AttachmentBinding` (`src/warhammer40k_ai/roster/army_attachments.py`)
  - Explicit build-side leader/support attachment selection.
- `ValidatedMuster` (`src/warhammer40k_ai/roster/army_build.py`)
  - Validated build payload consumed by runtime mustering.
- `ArmyMusterRequest` (`src/warhammer40k_ai/roster/army_muster.py`)
  - Serializable request wrapper for in-engine mustering.
  - Can now represent:
    - `battle_size`
    - `points_limit`
    - multiple `detachments`
    - `detachment_points_budget`
    - explicit `units`
    - `enhancement_assignments`
    - `attachment_bindings`
    - `force_disposition` / `allowed_force_dispositions`
  - Keeps a temporary `detachment_type` adapter for the legacy single-detachment shape.
- `UnitSelection` (`src/warhammer40k_ai/roster/army_muster.py`)
  - Legacy request shape retained only as a migration adapter into `RosterEntry`.

#### Muster execution

- `ArmyMusterer.muster_army()` (`src/warhammer40k_ai/roster/army_muster.py`)
  - Normalizes and validates requests through `ValidatedMuster`.
  - Builds a runtime `Army` façade and attaches:
    - `army.army_blueprint`
    - `army.validated_muster`
    - `army.detachments`
    - `army.detachment_points_summary`
    - `army.attachment_bindings`
    - build-side detachments / unit entries / enhancement assignments / attachment bindings
    - detachment-point budget/spend metadata
    - Force Disposition metadata
  - Keeps the explicit runtime boundary that unit entries are representable but not yet
    materialized from in-engine requests; if `unit_entries` are present,
    `NotImplementedError` is raised.

- `Game.execute_muster_armies_phase()` (`src/warhammer40k_ai/engine/game.py`)
  - Runs during setup phase `MUSTER_ARMIES`.
  - If `player1_muster` / `player2_muster` are provided, uses `ArmyMusterer`.
  - Otherwise loads from army list files via `parse_army_list()`.
  - Uses defaults if no files are provided:
    - player1: `army_lists/warhammer_app_dump.txt`
    - player2: `army_lists/chaos_daemons_GT2023.txt`
  - Rebuilds the entity registry after mustering so decisions can resolve unit/model IDs.
  - After army load, resolves Daemonic Allegiance choices:
    - If a player has local control and the event system is configured,
      publishes `daemonic_allegiance_prompt`.
    - Otherwise resolves allegiances automatically.

#### Build validation

- `src/warhammer40k_ai/roster/army_validation.py`
  - normalizes raw muster requests into `ArmyBlueprint`
  - applies the temporary single-detachment adapter
  - validates faction support
  - validates detachment-point budget spend
  - validates references from unit entries, enhancement assignments, and attachment bindings
  - validates chosen Force Disposition against any allowed set

#### Runtime/list validation

- Army list parsing in the network server (`army_submit`) still runs `Army.validate()` on the parsed list.
- Runtime detachment-aware rule lookups now consume `army.detachments` through shared helpers in
  `army.py` / `detachment_manager.py`, with `army.detachment_type` retained only as a narrow
  compatibility adapter.
- The existing runtime/list validation in `Army` still includes:
  - Epic Hero duplicates
  - warlord eligibility restrictions
  - datasheet "one-of" restrictions
  - named unit caps inferred from ability text
  - Ynnari Epic Hero restrictions
  - the rest of the established roster validation currently housed in `army.py`
- Enhancement assignment validation now also supports upgrade-tag representations for
  eligible non-Character units.

#### UI touchpoints

- Setup flow: `SetupPhaseHandler` (`src/warhammer40k_ai/UI/phases/phase_manager.py`)
  - Spacebar advances setup phases.
  - After `MUSTER_ARMIES`, the UI refreshes roster panes.
- Daemonic Allegiance dialog: `src/warhammer40k_ai/UI/dialogs/daemonic_allegiance_dialog.py`
  - Modal dialog that supports a mustering-only choice.
- Info pane label: `src/warhammer40k_ai/UI/panels/info_pane.py`
  - Shows "Loading army lists and preparing forces" during `MUSTER_ARMIES`.

#### Parse extraction

- Army-list parsing now lives in `src/warhammer40k_ai/roster/army_parse.py`.
- `src/warhammer40k_ai/roster/army.py` keeps wrapper entrypoints:
  - `parse_army_list()`
  - `parse_army_list_text()`
  - `add_unit_to_army()`
- Parsed list files now also attach a build-side `ArmyBlueprint` / `ValidatedMuster`
  summary to the runtime `Army` so parsed rosters participate in the same new build model.

#### Save/load scaffolding

- `army_muster_requests` is still included in game snapshots in
  `src/warhammer40k_ai/engine/snapshot.py`.
- `ArmyMusterRequest` now has explicit `to_dict()` / `from_dict()` support so
  multi-detachment request payloads, enhancement assignments, and attachment bindings have
  a stable serializable form.
- Runtime `DetachmentInstance` values are also serializable through army snapshot state, and
  session manifests now expose `detachment_types` alongside the legacy primary
  `detachment_type`.
- This remains the placeholder path for future network-safe mustering inputs.
  See `docs/NETWORK_SAVELOAD_DESIGN.md` for serialization requirements.

### Current limitations

- In-engine unit materialization from `RosterEntry` is not implemented yet.
- Attachment bindings are representable and validated structurally, but they do not yet drive
  runtime unit joining; that remains later port work.
- The deep runtime/list validation stack is still mostly housed in `Army.validate()`.
- Mustering choices are not yet represented as decision requests in the engine
  other than existing Daemonic Allegiance prompts when applicable.

### Expected evolution (linked to network/save/load work)

When full UI mustering is implemented, this scaffolding is expected to grow into:
- a serializable, decision-driven mustering flow aligned with
  `docs/NETWORK_SAVELOAD_DESIGN.md`,
- explicit decision requests for faction, detachment, unit picks, wargear,
  enhancements, and warlord selection,
- runtime unit materialization from `ValidatedMuster`,
- validation of points limits, mustering restrictions, and spawn-only units,
- stable IDs for unit selections so networked clients can replay the same choices,
- runtime attachment and enhancement assignment application consuming the build-side model directly.
