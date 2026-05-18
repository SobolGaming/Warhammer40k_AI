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
available, but validated `ArmyBlueprint` requests can now also materialize full runtime
units directly.

### Current scaffolding components

#### Data model

- `ArmyBlueprint` (`src/warhammer40k_ai/roster/army_build.py`)
  - Build-time representation of army construction.
  - Holds battle size, points limit, detachment selections, unit entries,
    enhancement assignments, broader upgrade assignments, attachment bindings,
    and Force Disposition data.
- `DetachmentSelection` (`src/warhammer40k_ai/roster/army_build.py`)
  - Represents one selected detachment and its detachment-point cost.
- `DetachmentInstance` (`src/warhammer40k_ai/roster/army_runtime.py`)
  - Runtime counterpart of `DetachmentSelection`.
  - Carries runtime detachment identity, owning faction, detachment type, and detachment-point cost.
- `RosterEntry` (`src/warhammer40k_ai/roster/army_build.py`)
  - Build-side unit entry used before runtime `Unit` objects are materialized.
- `EnhancementAssignment` (`src/warhammer40k_ai/roster/army_build.py`)
  - Explicit enhancement-to-unit assignment record.
- `UpgradeAssignment` / `RosterUpgradeAssignment` (`src/warhammer40k_ai/roster/army_build.py`)
  - Explicit 11e-prep upgrade assignment record distinct from legacy enhancements.
  - Tracks source detachment, unit/model/weapon-profile target kind, target ids,
    maximum target cardinality, enhancement-budget counting behavior, points-cost
    mode, selected weapon-profile identity, declaration step, and metadata.
  - Preview-only fixtures can represent unit-only upgrades, model-only upgrades,
    selected weapon-profile upgrades, and upgrades that do not count toward the
    normal enhancement total without changing released 10e enhancement behavior.
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
    - `upgrade_assignments`
    - `attachment_bindings`
    - `force_disposition` / `allowed_force_dispositions`
  - Requires explicit `detachments`; the temporary single-detachment request adapter has been removed.
- `UnitSelection` (`src/warhammer40k_ai/roster/army_muster.py`)
  - Legacy request shape retained only as a migration adapter into `RosterEntry`.

#### Muster execution

- `ArmyMusterer.muster_army()` (`src/warhammer40k_ai/roster/army_muster.py`)
  - Normalizes and validates requests through `ValidatedMuster`.
  - Builds a runtime `Army` façade without pre-seeding a detachment, materializes
    validated `unit_entries`, and attaches:
    - `army.army_blueprint`
    - `army.army_blueprint_hash`
    - `army.validated_muster`
    - `army.detachments`
    - `army.detachment_points_summary`
    - `army.attachment_bindings`
    - build-side detachments / unit entries / enhancement assignments / attachment bindings
    - build-side upgrade assignments
    - detachment-point budget/spend metadata
    - Force Disposition metadata
  - Uses `src/warhammer40k_ai/roster/unit_materialization.py` to resolve datasheets,
    apply serialized wargear selections, assign enhancements, preserve deterministic
    `build_entry_id` values, and select the authored warlord.
  - `ArmyMusterer.validate_runtime_legality()` reuses the same materialization path,
    then applies authored attachment bindings, validates support-artillery joins,
    and runs `Army.validate()` so build-side callers can enforce real runtime
    muster legality without going through army-list text parsing.
  - `ArmyMusterer.muster_blueprint()` exposes the same runtime mustering path directly
    from an `ArmyBlueprint`.
  - `src/warhammer40k_ai/roster/roster_synthesis.py` builds deterministic
    10th-edition seeded `ArmyBlueprint` candidates and accepts only candidates
    that pass `ArmyMusterer.validate_runtime_legality()` and army-list export
    round-trip validation.
  - Single-detachment parse/snapshot helpers that still begin from a known primary detachment now
    use `Army.with_detachment(...)` instead of constructor seeding.

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
  - validates faction support
  - validates detachment-point budget spend
  - validates references from unit entries, enhancement assignments, upgrade assignments,
    and attachment bindings
  - validates upgrade cardinality, target kind, source detachment, selected weapon-profile
    identity for weapon-profile upgrades, points-cost mode, and enhancement-budget counting mode
  - validates chosen Force Disposition against any allowed set
  - leaves deep roster legality to runtime validation so build-side search and
    authored muster requests can share the same `Army.validate()` rules

#### Runtime/list validation

- Army list parsing in the network server (`army_submit`) still runs `Army.validate()` on the parsed list.
- Runtime detachment-aware rule lookups now consume `army.detachments` through shared helpers in
  `army.py` / `detachment_manager.py`; `army.detachment_type` is now a read-only compatibility view
  over the authoritative primary detachment instance, not a separate runtime source of truth.
- The existing runtime/list validation in `Army` still includes:
  - Epic Hero duplicates
  - warlord eligibility restrictions
  - datasheet "one-of" restrictions
  - named unit caps inferred from ability text
  - Ynnari Epic Hero restrictions
  - the rest of the established roster validation currently housed in `army.py`
- Broader upgrade assignment validation now lives in `UpgradeAssignment` instead of
  overloading legacy enhancement metadata.
- Search and repair flows can now validate `ArmyBlueprint` candidates through the
  same runtime legality path, which is where warlord, enhancement, duplicate
  datasheet, attachment, and optional-wargear rules are ultimately enforced.

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
- Synthesized roster exports are app-style text files and must parse through
  `parse_army_list_text()` to be accepted into a `RosterSynthesisReport`.
- Parsed list units now also receive deterministic `build_entry_id` values aligned with
  the parsed `RosterEntry` records so authored attachment bindings can be projected into
  runtime setup when present.
- Copied army-list text may omit continuation bullets on model loadout lines; quantity
  lines under an active unit are parsed as model/loadout details unless they include a
  points value, so copied wargear lines do not become bogus unit headers.
- Non-app text headers support both list-name-first exports and faction/battle-size/
  detachment headers, preserving the intended faction and detachment in parsed rosters.
- Tournament-list imports now tolerate accent-insensitive datasheet/model labels,
  slash-separated category headers, common singular/plural model-heading variants
  (`Guardsmen`/`Guardsman`, `Boyz`/`Boy`, `Wyches`/`Wych`), and wargear ability
  labels that would otherwise collide with parsed replacement-option bundles.

#### Save/load scaffolding

- `army_muster_requests` is still included in game snapshots in
  `src/warhammer40k_ai/engine/snapshot.py`.
- `ArmyMusterRequest` now has explicit `to_dict()` / `from_dict()` support so
  multi-detachment request payloads, enhancement assignments, upgrade assignments,
  and attachment bindings have a stable serializable form.
- Runtime `DetachmentInstance` values are also serializable through army snapshot state, and
  session manifests now expose `primary_detachment_type` plus `detachment_types`.
- Runtime units can now carry `build_entry_id` linkage to their build-side entries so
  authored attachment bindings round-trip cleanly through setup/replay state.
- Runtime armies now also carry a deterministic `army_blueprint_hash` so build-side
  provenance survives descriptor compilation, save/load, and future evaluation records.
- This remains the placeholder path for future network-safe mustering inputs.
  See `docs/NETWORK_SAVELOAD_DESIGN.md` for serialization requirements.

### Current limitations

- Attachment bindings can now optionally pre-seed runtime leader/support joins during
  `DECLARE_BATTLE_FORMATIONS` when the runtime army already has materialized units and
  matching `build_entry_id` values.
- The current live declaration flow is still supported and remains the fallback
  path for rosters that do not provide authored attachment bindings.
- Build-side unit entries still rely on resolvable datasheet and enhancement names plus
  the existing serialized wargear string / `wargear_by_model` representations.
- Optional wargear is already addressed in the current mustering seam: build-side
  wargear changes are translated into runtime option application through
  `wargear_dict_for_entry(...)`, `Unit.apply_wargear_options_strict(...)`, and
  `unit.validate_wargear_selection()`.
- The deep runtime/list validation stack is still mostly housed in `Army.validate()`.
- Mustering choices are not yet represented as decision requests in the engine
  other than existing Daemonic Allegiance prompts when applicable.

### Expected evolution (linked to network/save/load work)

When full UI mustering is implemented, this scaffolding is expected to grow into:
- a serializable, decision-driven mustering flow aligned with
  `docs/NETWORK_SAVELOAD_DESIGN.md`,
- explicit decision requests for faction, detachment, unit picks, wargear,
  enhancements, and warlord selection,
- validation of points limits, mustering restrictions, and spawn-only units,
- stable IDs for unit selections so networked clients can replay the same choices,
- runtime attachment and enhancement assignment application consuming the build-side model directly.

See `docs/ATTACHMENT_RUNTIME.md` for the current attachment build/runtime seam.
