# Warhammer40k_AI — 11th Edition Port Preparation Implementation Plan (PR-by-PR)

## Purpose

This document is an execution plan for GPT-5.4 to prepare the `SobolGaming/Warhammer40k_AI` codebase for a clean one-way transition from 10th Edition assumptions to an 11th Edition-first architecture.

**Execution contract:** PR-001 through PR-011 prepare the codebase so the final rules can be ingested cleanly when they are live. They should not be treated as permission to encode preview articles as final canonical gameplay. PR-012 is the release-day exactness pass.

This plan is **preview-driven**, not release-day finalization. It is based on the currently announced 11th Edition changes around:

- multi-detachment army construction
- detachment-point budgeting
- Force Dispositions affecting mission generation
- revised pregame sequencing
- terrain-footprint / key-location style objective handling
- attachment semantics (Leader / Support selected during list building)
- edition-level runtime invariants (e.g. stratagem stacking limits, charge target timing, melee/disembark timing changes)

The project does **not** need backward-compatible 10th support after 11th launches. Temporary adapters are acceptable during migration, but the end state should be 11th-first and 10th-only assumptions should be removed.

## Source inputs

Use these as the authoritative context while implementing:

### Repository
- Repo root: `https://github.com/SobolGaming/Warhammer40k_AI/`
- README: `README.md`
- Architecture: `docs/ARCHITECTURE.md`
- AI portability plan: `docs/AI_REINTRODUCTION_PLAN.md`
- Mustering scaffolding: `docs/ARMY_MUSTERING_SCAFFOLDING.md`
- Mission/deployment docs: `docs/MISSION_DEPLOYMENT_SYSTEM.md`
- Decision telemetry / replay docs:
  - `docs/DECISION_RECORD_TELEMETRY.md`
  - `docs/DECISION_RECORD_REPLAY.md`
  - `docs/SEMANTIC_DIFF_CLASSIFIER.md`

### Warhammer Community preview articles
- New edition reveal:
  - `https://www.warhammer-community.com/en-gb/articles/ctdexme4/warhammer-40000-the-new-edition-is-revealed-at-adepticon-preview-2026/`
- Missions / Force Dispositions:
  - `https://www.warhammer-community.com/en-gb/articles/oefzq9fg/new40k-how-your-army-affects-your-mission/`
- Army building:
  - `https://www.warhammer-community.com/en-gb/articles/95fucn12/building-an-army-in-the-new-edition-of-warhammer-40000/`

## Working rules for GPT-5.4

1. **Do not implement speculative final rules text** beyond what is already previewed.
2. **Do implement architectural seams** so release-day rule ingestion becomes mostly data/config work.
3. **Prefer one-way migrations** over long-lived compatibility layers.
4. **Preserve deterministic replay / telemetry / descriptor provenance** at every step.
5. **Favor focused modules over giant files.** When touching an oversized file, split responsibility instead of adding more code to the monolith.
6. **Use `git mv` where possible** to preserve history for moved files.
7. **Keep PRs reviewable.** If a PR would exceed roughly 1,500 changed lines excluding pure moves/renames, split it.
8. **No broad neural-network training in this plan.** Only add the plumbing and stable interfaces required to make later training portable.
9. **Every PR must end with passing tests** for the touched area, updated docs for changed public interfaces, and no broken replay serialization.
10. **PR-001 through PR-011 are compatibility/preparation PRs only.** They may add schemas, adapters, hooks, services, validators, data compilers, and provisional placeholder content, but they must not claim to implement final authoritative 11th Edition rules.
11. **PR-012 is the first PR allowed to ingest and activate exact 11th Edition release behavior/data.** Before PR-012, any preview-derived runtime behavior must be clearly marked provisional and limited to scaffolding, stubs, feature-gated validation, or placeholder data needed to keep the architecture coherent.

## Global design decisions

These are the architecture decisions that should govern all PRs in this plan:

### A. Separate army construction from runtime army state
Introduce an explicit army-build domain layer:
- `ArmyBlueprint`
- `DetachmentSelection`
- `DetachmentInstance`
- `EnhancementAssignment`
- `AttachmentBinding`
- `ValidatedMuster`
- `RuntimeArmy`

Do **not** continue to treat the runtime `Army` object as the source of truth for list construction.

### B. Make multi-detachment an engine primitive
A runtime army must carry:
- a collection of detachment instances
- a detachment-point budget and spend summary
- explicit attachment bindings chosen during list building
- the chosen Force Disposition for the current battle

### C. Treat army build as a descriptor family
Add a new descriptor family:
- `ArmyBuildDescriptor`

It must participate in:
- descriptor bundle compilation
- version adapter boundaries
- decision records
- training manifests
- replay relabeling

### D. Mission generation must be data-driven
Stop hard-coding fixed approved mission combinations for matched play. Replace them with:
- `MissionPack`
- `MissionPairing`
- `ForceDisposition`
- `DeploymentDefinition`
- `TwistDefinition`
- `SecondaryRuleSet`

### E. Objective semantics must separate site, control, and scoring
Push these concepts into runtime and serialization:
- `ObjectiveSite`
- `ControlRegion`
- `ScoreSource`

This is required to support terrain-footprint / key-location objectives cleanly.

### F. Centralize edition invariants
Do not bury 11th-edition invariants inside faction files. Add engine-level enforcement points for:
- stratagem stacking restrictions
- charge target timing
- attachment/runtime bodyguard rules
- melee timing hooks
- disembark timing hooks

---

# Codebase review and refactor recommendations

## Repository shape review

The top-level package layout is workable and already separated into major domains (`battlefield`, `engine`, `network`, `roster`, `rules`, `units`, `ml`). The biggest structural risk is **not folder layout**. It is that a handful of very large files still act as cross-domain “god modules”, which will make the 11th port much harder unless they are decomposed as part of the migration.

The tests directory is also too flat and too large; it needs package-aligned reorganization so the new 11th-specific work can land into obvious, discoverable places.

## Oversized / over-broad file review

### Immediate split targets (must be addressed in this plan)

| File | Approx size | Why it is too broad | Recommended split | Planned PRs |
|---|---:|---|---|---|
| `src/warhammer40k_ai/engine/game.py` | 15,202 lines / 673 KB | Central orchestrator for too many concerns: setup flow, phase flow, objectives, scoring, decisions, AI hooks, serialization, combat wiring | Split into `game_setup_flow.py`, `game_phase_flow.py`, `game_decision_runtime.py`, `game_scoring.py`, `game_objectives.py`, `game_serialization.py`; keep `game.py` as thin façade/wiring shell | PR-005, PR-006, PR-007, PR-009 |
| `src/warhammer40k_ai/roster/player.py` | 6,945 lines / 320 KB | Mixes player identity, control mode, CP/resources, VP scoring, mission cards/secondaries, UI state, reaction/usage tracking | Split into `player_control.py`, `player_resources.py`, `player_scoring.py`, `player_missions.py`, `player_ui.py`; keep `player.py` as façade/dataclass | PR-005 |
| `src/warhammer40k_ai/units/unit.py` | 5,716 lines / 316 KB | Mixes composition, movement, combat, ability plumbing, attachments, serialization, state mutation | Split into `unit_state.py`, `unit_composition.py`, `unit_movement.py`, `unit_combat.py`, `unit_abilities.py`, `unit_attachments.py`, `unit_serialization.py` | PR-008, PR-009 |
| `src/warhammer40k_ai/roster/army.py` | 4,310 lines / 180 KB | Mixes parsing/loading, validation, army construction, runtime state, enhancements, attachments | Split into `army_build.py`, `army_validation.py`, `army_runtime.py`, `army_parse.py`, `army_attachments.py` | PR-002, PR-003 |
| `src/warhammer40k_ai/battlefield/map.py` | 3,232 lines / 139 KB | Mixes geometry, terrain, occupancy, objective logic, control queries | Split into `map_geometry.py`, `terrain_runtime.py`, `objective_sites.py`, `control_queries.py` | PR-007 |
| `src/warhammer40k_ai/units/model.py` | 2,781 lines / 108 KB | Mixes model state, base geometry, damage/wound interactions, movement helpers | Split into `model_state.py`, `model_geometry.py`, `model_damage.py` | PR-008 or PR-009 if needed |
| `src/warhammer40k_ai/engine/attack_resolution.py` | 2,656 lines / 131 KB | Mixes sequencing, modifiers, damage allocation, reporting, side effects | Split into `attack_sequence.py`, `attack_modifiers.py`, `damage_allocation.py`, `attack_reporting.py` | PR-009 |
| `src/warhammer40k_ai/engine/deployment.py` | 1,522 lines / 69.5 KB | Mixes flow, validation, data definitions, runtime choices | Split into `deployment_flow.py`, `deployment_validation.py`, `deployment_types.py` | PR-005, PR-006 |
| `src/warhammer40k_ai/engine/deployment_solver.py` | 1,494 lines / 66.7 KB | Mixes candidate generation, heuristics, ranking, solver orchestration | Split into `deployment_candidates.py`, `deployment_heuristics.py`, `deployment_ranker_adapter.py` | PR-005, PR-010 |
| `src/warhammer40k_ai/engine/fight_phase_manager.py` | 1,299 lines / 60.5 KB | Mixes eligibility, order, pile-in/consolidate movement, fight resolution hooks | Split into `fight_order.py`, `fight_engagement.py`, `fight_resolution.py` | PR-009 |
| `src/warhammer40k_ai/engine/training_manifest.py` | 973 lines / 49.6 KB | Mixes manifest schema, IO, filtering, validation, build logic | Split into `training_manifest_schema.py`, `training_manifest_builder.py`, `training_manifest_io.py`, `training_manifest_validate.py` | PR-010 |
| `tests/` | >1,000 visible entries; 165 omitted | Too flat for discoverability and makes new edition work harder to organize | Reorganize into `tests/engine`, `tests/roster`, `tests/units`, `tests/battlefield`, `tests/rules`, `tests/network`, `tests/replay`, `tests/ai`, `tests/integration`, `tests/fixtures` | PR-001 |

### Moderate-size files that should be split by concern before adding 11th features

| File | Approx size | Why split even though size is manageable | Recommended split | Planned PR |
|---|---:|---|---|---|
| `src/warhammer40k_ai/engine/state_blob.py` | 570 lines / 24.3 KB | Central schema file spanning rules bundle, mission, terrain, objectives, units; high churn risk | Split into `state_blob_rules.py`, `state_blob_players.py`, `state_blob_mission.py`, `state_blob_objectives.py`, `state_blob_terrain.py`, `state_blob_units.py` | PR-004 |
| `src/warhammer40k_ai/engine/descriptor_compiler.py` | 510 lines / 19.6 KB | Central compiler already spans mission, objectives, terrain, deployment, tools; 11th needs army-build descriptors too | Split into `descriptor_bundle.py`, `descriptor_mission.py`, `descriptor_objectives.py`, `descriptor_terrain.py`, `descriptor_deployment.py`, `descriptor_tools.py`, `descriptor_army_build.py` | PR-004 |

### Lower-priority split candidates (do not front-load unless touched by 11th work)

| File | Approx size | Recommendation | Planned handling |
|---|---:|---|---|
| `src/warhammer40k_ai/rules/enhancement_effects.py` | 832 lines / 35 KB | Split into core interfaces + effect implementations only if upgrade-tag / enhancement targeting work makes it grow materially | Defer unless touched in PR-003 or PR-008 |
| `src/warhammer40k_ai/network/server.py` | 827 lines / 35.9 KB | Acceptable for now; only split if setup flow/network authority changes force broad edits | Defer |
| `src/warhammer40k_ai/network/game_session.py` | 358 lines / 13.6 KB | Fine as-is for now | Defer |
| `src/warhammer40k_ai/engine/mission_selection.py` | 37 lines / 2.5 KB | Not oversized, but semantically obsolete; replace entirely | PR-006 |

## File-size / focus guardrails after refactor

These are not hard rules, but they should guide review:

- Façade/orchestration modules: target **< 400 LOC**
- Core domain modules: target **< 800 LOC**
- Anything over **1,200 LOC** requires explicit justification in the PR description
- A module should own **one primary reason to change**
- Faction-specific data/rule modules can exceed these thresholds only when they are mostly declarative and narrowly scoped

---

# PR sequence

## PR status tracker

Update this tracker whenever a planned PR is completed and pushed so the document
shows what is done versus what remains.

| PR | Status | Notes |
|---|---|---|
| PR-001 | Completed | Pushed to `dev` on April 5, 2026 as commit `af21acb1` (`Add 11e port scaffolding and reorganize tests`). |
| PR-002 | Pending | Not started. |
| PR-003 | Pending | Not started. |
| PR-004 | Pending | Not started. |
| PR-005 | Pending | Not started. |
| PR-006 | Pending | Not started. |
| PR-007 | Pending | Not started. |
| PR-008 | Pending | Not started. |
| PR-009 | Pending | Not started. |
| PR-010 | Pending | Not started. |
| PR-011 | Pending | Not started. |
| PR-012 | Pending | Not started. |

## PR-001 — Repository scaffolding, architectural guardrails, and test reorganization

**Status:** Completed and pushed to `dev` on April 5, 2026 in commit `af21acb1`.

### Goal
Create the package/file scaffolding that will let the 11th-edition work land into focused modules instead of growing existing god files. Reorganize tests into package-aligned directories.

### Why now
If this is not done first, subsequent PRs will either:
- continue growing giant files, or
- require repeated disruptive path moves later.

### Main changes
1. Add an `11th_porting_plan.md` or ADR-style note in `docs/` summarizing the architecture decisions in this document.
2. Create destination modules/files for future splits with minimal façade wiring, but do **not** move functional logic yet except trivial helpers.
3. Reorganize `tests/` into package-aligned subdirectories:
   - `tests/engine/`
   - `tests/roster/`
   - `tests/units/`
   - `tests/battlefield/`
   - `tests/rules/`
   - `tests/network/`
   - `tests/replay/`
   - `tests/ai/`
   - `tests/integration/`
   - `tests/fixtures/`
4. Add review guardrails to docs or contributor notes:
   - no new feature work in oversized monoliths when a split target exists
   - prefer adding to focused modules created by this plan

### Start condition
- Current `dev` branch is green.
- No functional 11th-edition behavior has been added yet.

### End condition
- New module scaffolding exists for the planned splits.
- `tests/` is reorganized without behavior change.
- Imports and test discovery still work.
- README / docs mention that the codebase is beginning an 11th-edition-first migration.
- No gameplay behavior changes.

### Acceptance checks
- Existing tests pass after path updates.
- No public API breakage beyond import-path updates handled by shims.
- No replay/schema changes yet.

### Non-goals
- No army-build behavior changes.
- No mission-system changes.
- No runtime rules changes.

### Notes
Keep this PR mostly structural. If it grows too large, split the test reorg into PR-001A and scaffolding into PR-001B.

---

## PR-002 — Extract army-build domain from `army.py` / `army_muster.py`

### Goal
Introduce a dedicated army construction layer that models 11th-edition list building separately from runtime army state.

### Why now
This is the most important domain seam. Multi-detachment, detachment points, upgrade-tag enhancements, and pre-selected attachments all live here.

### Main changes
1. Add new build-side types:
   - `ArmyBlueprint`
   - `DetachmentSelection`
   - `EnhancementAssignment`
   - `AttachmentBinding`
   - `ValidatedMuster`
   - `UnitEntry` / `RosterEntry` (pick one name and use it consistently)
2. Expand or replace `ArmyMusterRequest` so it can represent:
   - battle size / points limit
   - multiple detachment selections
   - detachment-point budget
   - explicit unit entries
   - enhancement assignments
   - attachment bindings
   - chosen Force Disposition (or allowed disposition set if chosen later)
3. Keep a temporary adapter that maps the old single-detachment request shape into the new build model.
4. Move list parsing / validation logic out of `army.py` into focused files:
   - `army_build.py`
   - `army_validation.py`
   - `army_parse.py`
   - `army_attachments.py`
5. Update docs for mustering scaffolding to reflect the new target architecture.

### Start condition
- PR-001 merged.
- Tests are passing on the reorganized layout.

### End condition
- The codebase has an explicit build-time army model.
- The runtime army object is no longer the only place where army-construction meaning lives.
- Old single-detachment request flow still works through a migration adapter.
- `army.py` shrinks and becomes a façade or runtime-focused module.

### Acceptance checks
- Unit tests cover:
  - multi-detachment selection serialization/deserialization
  - detachment-point budget validation
  - enhancement assignment representation
  - attachment binding representation
  - legacy request adapter
- No game runtime changes yet beyond consuming `ValidatedMuster`.

### Non-goals
- No mission generation yet.
- No detachment runtime behavior changes yet.
- No 10th rules cleanup yet.

---

## PR-003 — Multi-detachment runtime integration and detachment-instance APIs

### Goal
Make multi-detachment a runtime primitive and remove the single `army.detachment_type` assumption from engine/rules integration points.

### Why now
The army-build model is not useful unless runtime systems can consume it directly.

### Main changes
1. Introduce `DetachmentInstance` as the runtime counterpart of `DetachmentSelection`.
2. Change the runtime army to carry:
   - `detachments: list[DetachmentInstance]`
   - detachment-point summary
   - chosen Force Disposition for the battle
   - attachment bindings derived from the validated build
3. Refactor `detachment_manager.py` / `detachment_registry.py` so managers work from detachment instances rather than a single army-level detachment string.
4. Separate:
   - faction-wide rule providers
   - detachment-granted rules
   - enhancement-granted rules
5. Add support in the representation for upgrade-tag enhancements that can target eligible non-Character units.
6. Remove direct reads of `army.detachment_type` from runtime logic, leaving only a short-lived adapter if needed.

### Start condition
- PR-002 merged.
- Build-side mustering types are stable.

### End condition
- Runtime code uses detachment instances, not a single detachment-type field.
- Existing factions/detachments still load through a one-detachment default path.
- The engine can represent an 11th-style army with multiple detachments, even if some final release-day validation details remain TODO.

### Acceptance checks
- Tests cover:
  - one-army / multiple-detachment runtime instantiation
  - rule-provider lookup by detachment instance
  - upgrade-tag enhancement attachment to eligible non-Character units
  - no unintended regressions in current detachment loading
- `army.py` no longer owns build parsing/validation responsibilities.

### Non-goals
- No mission-system rewrite yet.
- No objective/runtime geometry changes yet.

---

## PR-004 — Descriptor/state schema split and `ArmyBuildDescriptor`

### Goal
Make army construction a first-class descriptor family and split central schema/compiler files by concern before 11th-specific logic expands them further.

### Why now
This is the seam that protects future model portability and replay consistency.

### Main changes
1. Split `descriptor_compiler.py` into focused modules:
   - `descriptor_bundle.py`
   - `descriptor_mission.py`
   - `descriptor_objectives.py`
   - `descriptor_terrain.py`
   - `descriptor_deployment.py`
   - `descriptor_tools.py`
   - `descriptor_army_build.py`
2. Split `state_blob.py` into focused modules:
   - `state_blob_rules.py`
   - `state_blob_players.py`
   - `state_blob_mission.py`
   - `state_blob_objectives.py`
   - `state_blob_terrain.py`
   - `state_blob_units.py`
3. Add:
   - `ArmyBuildDescriptor`
   - `army_build_descriptor_id`
   - `detachment_descriptor_ids` if needed
4. Extend the compiled descriptor bundle to include army-build descriptors.
5. Extend version-adapter boundaries and decision context plumbing so army-build descriptors are tracked wherever mission/objective/terrain/deployment/tool descriptors are already tracked.
6. Update docs that describe descriptor bundles and rules-boundary portability.

### Start condition
- PR-003 merged.
- Army-build and detachment-instance runtime objects exist.

### End condition
- Descriptor compilation is modular.
- State blob schema is modular.
- Army-build descriptor IDs are carried alongside existing descriptor IDs.
- Version boundaries can distinguish not just the mission pack but also the army construction semantics that produced the battle.

### Acceptance checks
- Snapshot/state-blob serialization round-trips with new fields.
- Descriptor bundle IDs remain deterministic.
- Existing replay fixtures either continue to load with defaults or are migrated explicitly.
- Tests cover descriptor compilation for at least:
  - single-detachment legacy-shaped army
  - multi-detachment army
  - armies with attachment bindings / enhancement assignments

### Non-goals
- No mission generation rewrite yet.
- No combat-rule changes yet.

---

## PR-005 — Pregame flow state machine and `game.py` / `player.py` decomposition

### Goal
Replace the current setup sprawl with an explicit, testable, data-driven pregame state machine that can represent the announced 11th sequence without treating preview text as final release logic. Break apart `game.py` and `player.py` while doing it.

### Why now
The port will become fragile if 11th setup flow is layered onto the existing game/player monoliths.

### Main changes
1. Extract setup orchestration out of `game.py` into focused modules:
   - `game_setup_flow.py`
   - `game_phase_flow.py`
   - `game_decision_runtime.py`
   - `game_scoring.py`
   - `game_serialization.py`
2. Decompose `player.py` into:
   - `player_control.py`
   - `player_resources.py`
   - `player_scoring.py`
   - `player_missions.py`
   - `player_ui.py`
3. Add an explicit pregame state machine covering:
   1. Muster armies
   2. Determine mission
   3. Determine deployment
   4. Optional Twist
   5. Create battlefield
   6. Determine attacker and defender
   7. Select secondary missions
4. Move deployment-flow orchestration out of the `game.py` monolith as part of this state-machine extraction.
5. Keep runtime/public entrypoints stable by letting `game.py` and `player.py` act as thin façade modules.

### Start condition
- PR-004 merged.
- Descriptor/state schema updates are stable.

### End condition
- Setup flow is an explicit state machine, not implicit logic spread across the monolith.
- `game.py` and `player.py` are materially smaller and narrower in responsibility.
- The engine can drive setup via deterministic requests/responses in the new order.
- Any preview-derived sequence/content that is not yet final is represented as provisional data or stubs, not as hard-coded canonical release rules.

### Acceptance checks
- Tests cover the entire pregame transition graph.
- Save/load and replay still function through the new setup flow.
- `game.py` is reduced substantially and no longer owns unrelated responsibilities directly.
- `player.py` no longer mixes resources, scoring, UI, and mission-hand state in one giant module.

### Non-goals
- No final mission-pairing logic yet.
- No objective-footprint logic yet.
- No claim that preview sequencing text is the final release implementation.

---

## PR-006 — Mission pack compiler, Force Dispositions, and mission/deployment rewrite

### Goal
Replace the hard-coded matched-play mission combination table with a data-driven mission/disposition compiler that can express the announced 11th concepts once final data is ingested, without hard-coding preview articles as final canon.

### Why now
The current fixed mission-combination table is too 10th-shaped and blocks portability.

### Main changes
1. Replace or retire `mission_selection.py` and its `APPROVED_MISSION_COMBINATIONS`.
2. Introduce data-driven mission types:
   - `ForceDisposition`
   - `MissionPack`
   - `MissionPairing`
   - `MissionDefinition`
   - `DeploymentDefinition`
   - `TwistDefinition`
   - `SecondaryRuleSet`
3. Implement mission generation from the pair:
   - `player_a.chosen_force_disposition`
   - `player_b.chosen_force_disposition`
4. Keep deployment definitions reusable so familiar layouts (e.g. Dawn of War / Hammer and Anvil / Tipping Point style deployments) remain configuration, not hard-coded branching.
5. Split deployment logic:
   - `deployment_types.py`
   - `deployment_flow.py`
   - `deployment_validation.py`
   - `deployment_candidates.py`
   - `deployment_heuristics.py`
6. Make twist handling explicit in the setup flow, even if preview-era twist content is only stubbed.

### Start condition
- PR-005 merged.
- Pregame state machine exists.

### End condition
- Matched-play mission generation is driven by force-disposition-capable mission-pack data.
- The fixed 10th-style approved-combinations table is no longer the primary path.
- Deployment selection is modular and data-driven.
- Preview-era disposition/missions content may remain placeholder or stubbed until PR-012 confirms the exact release behavior.

### Acceptance checks
- Tests cover all supported disposition pairings.
- Setup flow can advance from army build to mission selection to deployment using the new compiler.
- Mission descriptors and deployment descriptors remain deterministic.

### Non-goals
- No final release-day mission balance tuning.
- No AI training yet against the new mission space.
- No presentation of preview-derived mission pairing details as final released rules.

---

## PR-007 — Objective-site runtime model and battlefield map decomposition

### Goal
Refactor objective handling so the engine can represent terrain-footprint / key-location objectives without pretending everything is a circular marker.

### Why now
This is the second major 11th-edition pressure point after army construction.

### Main changes
1. Add explicit runtime primitives:
   - `ObjectiveSite`
   - `ControlRegion`
   - `ScoreSource`
2. Refactor `map.py` into focused modules:
   - `map_geometry.py`
   - `terrain_runtime.py`
   - `objective_sites.py`
   - `control_queries.py`
3. Update mission runtime and state schema to use the new primitives.
4. Allow objective sites to reference:
   - marker geometry
   - terrain footprint geometry
   - keyed battlefield features
5. Ensure scoring logic reads from `ScoreSource`, not directly from site geometry.
6. Ensure control checks read from `ControlRegion`, not directly from scoring definitions.

### Start condition
- PR-006 merged.
- Mission generation is data-driven.

### End condition
- Objective scoring/control semantics are decoupled from a marker-only representation.
- Battlefield geometry code is narrower in responsibility.
- At least one mission/test fixture uses a terrain-footprint or key-location objective model.

### Acceptance checks
- Tests cover:
  - marker-style objective site
  - terrain-footprint objective site
  - control-region computation
  - score-source VP evaluation independent of site shape
- State-blob and replay data include the new representations cleanly.

### Non-goals
- No combat/timing changes yet.
- No final release-day terrain-pack ingestion yet.

---

## PR-008 — Attachment model rewrite, Leader/Support semantics, and `unit.py` / `army.py` decomposition

### Goal
Move attachment semantics to the build/runtime seam and make leader/support/bodyguard behavior explicit and testable, while keeping preview-derived rule details provisional until the final 11th text is available.

### Why now
11th previewed changes make attachments a list-building concern, not just a pregame runtime choice.

### Main changes
1. Make attachment bindings chosen during army construction authoritative for runtime setup.
2. Add explicit support for:
   - one Leader attachment slot
   - one Support attachment slot
   - bodyguard requirements for Support
3. Refactor `unit.py`:
   - `unit_state.py`
   - `unit_composition.py`
   - `unit_abilities.py`
   - `unit_attachments.py`
   - `unit_serialization.py`
4. If needed, refactor `model.py` into:
   - `model_state.py`
   - `model_geometry.py`
   - `model_damage.py`
5. Localize bodyguard-death / attachment-dissolution logic so character-owned abilities are not silently lost just because a joined unit died.
6. Update mustering/runtime validation so illegal support-without-bodyguard states fail clearly.

### Start condition
- PR-007 merged.
- Army build and objective/missions seams are stable.

### End condition
- Attachment bindings are authored at list-build time and propagated into runtime setup.
- Runtime unit attachment logic is explicit and decomposed.
- Character/support/bodyguard semantics are no longer hidden inside broad unit logic.
- Exact released attachment exceptions remain data/config work for PR-012.

### Acceptance checks
- Tests cover:
  - valid leader attachment
  - valid support attachment
  - invalid support without bodyguard
  - bodyguard death with character retained
  - serialization of attachment bindings through setup/replay
- `unit.py` and `army.py` are materially smaller after the move.

### Non-goals
- No stratagem stacking or charge-timing changes yet.
- No final codex-specific leader/support exceptions unless already needed for current data.

---

## PR-009 — Edition invariants, combat timing hooks, and attack/fight decomposition

### Goal
Centralize the engine services, validation points, and timing hooks required by the previewed 11th-edition invariants, and split the combat monoliths while doing it. Do not treat preview text as final canonical behavior until PR-012.

### Why now
These are rules-semantics changes that should live at engine level, not as incidental patches scattered across phases or faction code.

### Main changes
1. Add a `StratagemApplicationLedger` (or similarly named runtime service) that can enforce per-unit/per-phase stacking rules.
2. Update charge sequencing so:
   - the roll occurs first
   - legal target binding occurs after the roll using post-roll legal checks
3. Add centralized hook points for:
   - melee eligibility / order updates
   - pile-in / consolidate timing changes
   - disembark timing changes relevant to combat flow
4. Decompose:
   - `attack_resolution.py` -> `attack_sequence.py`, `attack_modifiers.py`, `damage_allocation.py`, `attack_reporting.py`
   - `fight_phase_manager.py` -> `fight_order.py`, `fight_engagement.py`, `fight_resolution.py`
   - `unit.py` combat-related behavior -> `unit_combat.py`
5. Make these invariant checks version-aware through the rules bundle / adapter layer, but target 11th as the default end state.

### Start condition
- PR-008 merged.
- Attachment and runtime object model are stable.

### End condition
- Combat/timing invariants are centralized.
- The engine has the services/hooks needed to enforce per-unit/per-phase stratagem restrictions when final rules data is ingested.
- Charge-target timing is represented in the flow architecture so final released legality can be applied cleanly.
- Attack/fight modules are decomposed into focused units.

### Acceptance checks
- Tests cover:
  - stratagem-ledger enforcement points / validation plumbing
  - post-roll charge-target legality hooks
  - fight ordering / eligibility hooks
  - unchanged deterministic replay for equivalent scripted combat sequences
- Combat-related monolith files are materially smaller.

### Non-goals
- No ML training yet.
- No full release-day codex audit yet.
- No claim that preview-derived combat timing semantics are final until PR-012.

---

## PR-010 — Replay/telemetry/training-manifest updates and safe pre-11th AI scope

### Goal
Update replay, telemetry, relabeling, and training-manifest systems so future models can survive the edition transition with descriptor- and bundle-aware conditioning.

### Why now
Only after the runtime seams are stable should the data pipeline be updated to match them.

### Main changes
1. Update decision telemetry, replay snapshots, and relabeling flows to carry:
   - army-build descriptor IDs
   - detachment-instance metadata where needed
   - objective-site / score-source / control-region state
2. Refactor `training_manifest.py` into:
   - `training_manifest_schema.py`
   - `training_manifest_builder.py`
   - `training_manifest_io.py`
   - `training_manifest_validate.py`
3. Extend manifest slicing / filtering to include:
   - `rules_bundle_id`
   - `army_build_descriptor_id`
   - mission/objective/terrain/deployment/tool descriptors
4. Update controller inputs and any adapter-boundary code to consume the new descriptor family.
5. Add an explicit “safe to train pre-11th” policy in docs:
   - Allowed:
     - Tier 3 micro-executors
     - candidate-level movement/targeting/fight-order scorers
     - deterministic tool-usage policies conditioned on semantic metadata
   - Deferred until final 11th rules land:
     - Tier 1 strategic planners
     - mission-wide planning policies tied to current objective geometry
     - deployment rankers that internalize the old mission system
     - list-building agents

### Start condition
- PR-009 merged.
- Runtime state and descriptors are stable enough to serialize.

### End condition
- Replay/telemetry/training systems understand the new 11th-oriented runtime model.
- Portable training slices can be defined across rules bundles and army-build descriptors.
- Documentation clearly states what training is and is not safe to start before final 11th rules release.

### Acceptance checks
- Relabeling works against new replay/state schema.
- Training manifests can filter on army-build descriptors.
- At least one end-to-end replay fixture exercises:
  - multi-detachment army
  - chosen Force Disposition
  - objective-site / score-source state
  - attachment bindings
- No silent loss of provenance fields.

### Non-goals
- No actual large-scale model training jobs.
- No training-quality optimization beyond manifest correctness and portability plumbing.

---

## PR-011 — Remove 10th-only assumptions, collapse temporary adapters, and update docs to 11th-first-ready

### Goal
Delete transitional 10th-only architectural assumptions so the codebase does not carry long-lived migration debt, while keeping final rules exactness deferred to PR-012.

### Why now
The project does not intend to keep supporting 10th after 11th launches.

### Main changes
1. Remove temporary migration shims that are no longer necessary:
   - single-detachment army adapters
   - legacy `detachment_type` compatibility reads
   - old mission-combination selection paths
2. Update README and architecture docs:
   - remove “10th Edition implementation” framing
   - describe the new 11th-first seams
3. Update any public docs/examples/scripts that still assume:
   - one detachment
   - objective markers only
   - mission selection independent of army build
   - attachment choices made only at game start
4. Add regression tests that ensure the new seams remain first-class.

### Start condition
- PR-010 merged.
- The new architecture is fully in place.

### End condition
- No primary runtime path depends on 10th-only structure.
- Docs consistently describe the system as 11th-first-ready.
- The codebase is simpler than a compatibility-heavy dual-edition design.

### Acceptance checks
- Search confirms removal of primary `army.detachment_type` dependency outside intentional compatibility tombstones or deleted code.
- Search confirms the old hard-coded matched-play mission combination table is gone or marked dead.
- README/docs are consistent with the new architecture.

### Non-goals
- No final release-data ingestion if the official rulebooks/indexes are not yet available.
- No post-launch balancing work.
- No claim that preview-based placeholder behavior is the final shipped 11th ruleset.

---

## PR-012 — Release-day alignment PR (required when final 11th rules are in hand)

### Goal
Swap preview-driven placeholders and assumptions for final release-day data and exact wording once the real 11th core rules / mission pack / army-construction texts are available.

### Why now
The previous PRs build the right seams, but preview articles are not a substitute for the final rules corpus.

### Main changes
1. Ingest final 11th mission pack / army construction / deployment / twist / objective wording.
2. Replace preview TODOs / placeholder assumptions with exact implementations.
3. Re-run semantic-diff / replay migration / descriptor compilation checks.
4. Rebaseline fixtures where the final wording differs from the preview.
5. Perform a final audit of detachment-point handling, attachment rules, secondaries, and edition invariants.

### Start condition
- Official 11th rules data is available to the team.
- PR-011 merged.

### End condition
- Preview assumptions are either confirmed and retained or replaced with final release behavior.
- The repo is ready to begin real 11th data collection and safe training under the updated manifests.

### Acceptance checks
- All preview TODOs are closed or intentionally deferred with issue links.
- Final release-day smoke tests pass across:
  - army build
  - setup flow
  - mission generation
  - objective/control/scoring
  - attachments
  - core combat timing invariants

### Non-goals
- Broad model retraining. That should be a separate post-port effort.

---

# Cross-PR dependency graph

Use this dependency order unless a smaller split is obviously safer:

1. PR-001 → scaffolding / tests
2. PR-002 → army-build domain
3. PR-003 → multi-detachment runtime
4. PR-004 → descriptors / state schema
5. PR-005 → pregame state machine / game-player split
6. PR-006 → mission/disposition compiler
7. PR-007 → objective-site runtime / battlefield split
8. PR-008 → attachments / unit-army split
9. PR-009 → edition invariants / combat split
10. PR-010 → replay / telemetry / training plumbing
11. PR-011 → remove 10th-only assumptions
12. PR-012 → release-day exactness pass

If a PR is too large, split it at module boundaries, not at arbitrary halfway points.

---

# Execution notes for GPT-5.4

## How to handle large-file splits
- First create focused target modules and move logically cohesive methods/helpers.
- Keep the original giant file as a façade that imports from the new modules.
- Once the new modules are stable and call sites are migrated, shrink the façade further.
- Avoid a giant “move everything everywhere” PR.

## How to handle adapters
- Temporary adapters are acceptable in PR-002 through PR-010.
- They should be clearly marked with:
  - `TODO(11e-cleanup)` or equivalent
  - a reference to PR-011 as the deletion point

## How to handle tests during reorganization
- Preserve existing assertions whenever possible.
- Prefer moving tests rather than rewriting them.
- Add new tests in package-aligned directories immediately; do not add more root-level flat tests.

## How to handle docs
Every PR must update the docs that define the changed subsystem. At minimum:
- PR-002 / PR-003: army mustering docs
- PR-004 / PR-010: AI / replay / telemetry docs
- PR-005 / PR-006: mission/deployment docs
- PR-007: state blob / battlefield docs
- PR-008 / PR-009: architecture docs
- PR-011: README and top-level architecture docs

---

# Post-port training guidance

Do **not** start broad hierarchical training before PR-010 and PR-012 are complete.

## Training work that is reasonable before final 11th rules
- Tier 3 action-scoring / candidate-ranking models that are conditioned on semantic metadata and descriptor bundles
- narrow movement/targeting/fight-order ranking tasks
- controller policies whose legality and semantics are recomputed from descriptors at runtime

## Training work to defer
- full strategic planners
- list-building agents
- mission-generation-aware planning models
- deployment rankers trained on the current 10th-shaped mission structure
- any policy that assumes current objective markers are the stable abstraction

---

# Final definition of done

The port-prep effort is complete when all of the following are true:

1. Army construction is a first-class domain separate from runtime army state.
2. Multi-detachment armies are native runtime objects.
3. Army build participates in descriptors, version boundaries, replay, and manifests.
4. Mission generation is data-driven from Force Dispositions, not a fixed 10th combination table.
5. Objectives are modeled as sites/control/scoring, not marker-only assumptions.
6. Attachment bindings are chosen at build time and propagated cleanly to runtime.
7. Edition invariants are enforced centrally.
8. Giant files have been materially reduced and split along coherent responsibility boundaries.
9. The codebase is 11th-first and no longer architecturally anchored to 10th.
10. Pre-11th training is limited to portable, descriptor-conditioned components.
