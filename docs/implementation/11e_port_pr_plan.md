# Warhammer40k_AI — 11th Edition Port Preparation Implementation Plan (PR-by-PR)

## Purpose

This document is an execution plan for GPT-5.4 to prepare the `SobolGaming/Warhammer40k_AI` codebase for a clean one-way transition from 10th Edition assumptions to an 11th Edition-first architecture.

**Execution contract:** PR-001 through PR-014, plus the compatibility addendum PRs `PR-014A` through `PR-014L`, prepare the codebase so the final rules can be ingested cleanly when they are live. They should not be treated as permission to encode preview articles as final canonical gameplay. PR-015 is the release-day exactness pass.

This plan is **preview-driven**, not release-day finalization. It is based on the currently announced 11th Edition changes around:

- multi-detachment army construction
- detachment-point budgeting
- Force Dispositions affecting mission generation
- revised pregame sequencing
- terrain features plus terrain areas
- Hidden / detection-range / Obscuring terrain interactions
- terrain-area-driven cover and height-based Plunging Fire
- mission-authored terrain layouts and standard footprint templates
- terrain-footprint / key-location style objective handling
- attachment semantics (Leader / Support selected during list building)
- edition-level runtime invariants (e.g. stratagem stacking limits, charge target timing, melee/disembark timing changes)
- repeated faction-focus mechanics from May 2026 previews, including detection markers, preview weapon/movement keywords, broader upgrade semantics, reactive movement, fight interrupts, and unit-turn provenance

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
- Terrain:
  - `https://www.warhammer-community.com/en-gb/articles/xlppkx5s/new40k-take-cover-with-updated-terrain-rules/`
- Combat:
  - `https://www.warhammer-community.com/en-gb/articles/m3son4il/new40k-combat-changes-shake-up-fighting-in-the-new-edition/` (published April 15, 2026)
- Army building:
  - `https://www.warhammer-community.com/en-gb/articles/95fucn12/building-an-army-in-the-new-edition-of-warhammer-40000/`
- May 2026 faction-focus articles:
  - treated as preview-only design inputs until PR-015 or later final rules ingestion
  - tracked explicitly by PR-014L source catalog work instead of encoded as live faction rules

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
10. **PR-001 through PR-014 and `PR-014A` through `PR-014L` are compatibility/preparation PRs only.** They may add schemas, adapters, hooks, services, validators, data compilers, and provisional placeholder content, but they must not claim to implement final authoritative 11th Edition rules.
11. **PR-015 is the first PR allowed to ingest and activate exact 11th Edition release behavior/data.** Before PR-015, any preview-derived runtime behavior must be clearly marked provisional and limited to scaffolding, stubs, feature-gated validation, or placeholder data needed to keep the architecture coherent.

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

### G. Separate terrain features from terrain areas
Introduce explicit terrain-area runtime/state/descriptor objects instead of treating a terrain feature footprint as the only battlefield terrain abstraction.

Do **not** overload `TerrainFeature` to stand in for both article concepts once terrain-area data starts appearing in the runtime.

### H. Terrain visibility and cover must be service-based
Move terrain visibility, cover, and elevation evaluation behind dedicated services / context objects instead of continuing to grow `Map`-local special cases or save-step booleans.

Do **not** keep encoding new terrain semantics directly as ad-hoc checks in `Map` or as one-off mutations on wound/save payloads.

### I. Mission pairings own recommended terrain layouts
Recommended terrain layouts belong to mission pairings (or pairing-owned mission entries), not generic deployment definitions.

Terrain layouts should be authored from reusable terrain-area templates and recipes, not only ruin presets.

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
| `src/warhammer40k_ai/engine/game_mixins/setup_deployment_reserves_mixin.py` | 4,698 lines / 218 KB | Concentrates reserve-entry eligibility, reinforcement sequencing, and landing-geometry validation in one mixin, which makes ingress-distance and reserve-arrival timing changes risky to isolate | Split into `reserve_entry_rules.py`, `reserve_entry_geometry.py`, and a thin mixin/orchestrator façade | PR-014C |
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

## Terrain follow-up note

PR-007 established the battlefield/objective split, but the April 8, 2026 terrain preview adds a second terrain-focused preparation seam that still deserves additive work before release-day exactness:

- terrain areas as first-class runtime/state objects
- Hidden / detection-range / Obscuring visibility plumbing
- terrain cover and Plunging Fire service boundaries
- mission-authored terrain layouts and standard area templates

These should land as additive scaffolding PRs before the final release-day exactness pass.

## Combat preview addendum

The April 15, 2026 combat preview adds concrete pre-release surfaces that justify one more compatibility-only tranche before PR-015:

- engagement range expands to 2"
- movement can pass through enemy engagement range so long as it does not finish there
- charge targets are selected after the roll
- ingress-style reserve arrivals become more than 8" away
- all pile-ins batch before attacks
- the active player picks first among Fights First units
- eligible units that become unengaged can make an overrun fight
- all consolidates batch at the end and can reach new enemies or nearby objectives

The current repo already has promising seams (`combat_timing.py`, `fight_move.py`, `fight_order.py`, `descriptor_build_capability.py`), but they are still too coarse for release-day exactness. Today:

- `CombatTimingProfile` only carries a small set of booleans plus a single `fight_stage_start_player`
- engagement range still leaks through raw constants and low-level fight-move heuristics
- `fight_phase_manager.py` still assumes a per-unit fight sequence instead of a batch scheduler
- reserve-entry legality is still concentrated in `setup_deployment_reserves_mixin.py`
- build capability semantics are still versioned as `build_capability_v1`

To keep PR-015 focused on final corpus ingestion rather than structural rewrites, slot the following additive PRs in before it.

## Faction-focus preview addendum

As of May 13, 2026, the faction-focus series is showing repeated mechanics across factions, but those previews are still not final live rules. The preparation work before PR-015 should therefore stay infrastructure-first and preview-gated.

Repeated surfaces now worth preparing:

- detection-range manipulation and Hidden-preserving shooting
- preview weapon and movement keywords (`CLEAVE X`, updated `HEAVY`, `MOBILE`, plus generic keyword hooks)
- broader Upgrade payloads that target units, models, or weapon profiles and may or may not count toward enhancement limits
- richer reactive movement, reserve exits, Heroic Intervention modes, and stratagem mode choices
- fight interrupt semantics such as Fights First injection and "must fight next"
- unit-turn provenance such as set-up-this-turn, model move distance, shot-this-turn, Hidden exemptions, battle-shock persistence, and temporary tactical status tokens
- deterministic build-capability extensions for preview mechanics without changing the base artifact ABI every time a new article lands
- explicit preview source cataloging and generic goldens that do not ingest faction-focus rules as live faction data

Recommended implementation priority for the new block:

1. PR-014F — detection markers and Hidden-preserving shooting
2. PR-014E — mechanics and keyword registry
3. PR-014H — unit turn provenance and tactical status tokens
4. PR-014I — reactive movement and stratagem-mode decision framework
5. PR-014J — actionable fight scheduler stages
6. PR-014G — upgrade assignment and enhancement-budget modes
7. PR-014K — capability extension registry
8. PR-014L — preview source catalog and generic goldens

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
| PR-002 | Completed | Pushed to `dev` on April 5, 2026 as commit `b234185c` (`Implement PR-002 army build domain extraction`). |
| PR-003 | Completed | Pushed to `dev` on April 5, 2026 as commit `882103c9` (`Implement PR-003 runtime detachment integration`). |
| PR-004 | Completed | Pushed to `dev` on April 5, 2026 as commit `5ca1a905` (`Implement PR-004 descriptor and state blob split`). |
| PR-005 | Completed | Pushed to `dev` on April 5, 2026 as commit `27c56016` (`Implement PR-005 pregame flow and facade splits`). |
| PR-006 | Completed | Pushed to `dev` on April 5, 2026 as commit `327328e8` (`Implement PR-006 mission pack compiler and deployment split`). |
| PR-007 | Completed | Pushed to `dev` on April 5, 2026 as commit `f5f265c7` (`Implement PR-007 objective site runtime and map split`). |
| PR-008 | Completed | Pushed to `dev` on April 5, 2026 as commit `412032aa` (`Implement PR-008 optional attachment runtime and setup integration`). |
| PR-009 | Completed | Pushed to `dev` on April 5, 2026 as commit `bb8cf6dc` (`Implement PR-009 combat timing and decomposition`). |
| PR-010 | Completed | Pushed to `dev` on April 6, 2026 as commit `ee0c065b` (`Implement PR-010 replay and training manifest updates`). |
| PR-011 | Completed | Pushed to `dev` on April 6, 2026 as commit `a46574c4` (`Implement PR-011 detachment seam cleanup`). |
| PR-012 | Completed | Implemented terrain-area runtime, serialization, and objective/layout identifier scaffolding on April 8, 2026. |
| PR-013 | Completed | Implemented terrain visibility, cover, and elevation service scaffolding on April 8, 2026. |
| PR-014 | Completed | Implemented mission-authored terrain layout recipes, pairing-owned preview layout recommendations, explicit preview visibility gating, and terrain/module splits on April 8, 2026. |
| PR-014A | Completed | Implemented combat rules/geometry profiles, preview-aware engagement hooks, and charge-resolution state scaffolding on April 16, 2026. |
| PR-014B | Completed | Implemented fight scheduler / entitlement scaffolding, preview overrun handoff, and objective-site consolidate routing on April 16, 2026. |
| PR-014C | Completed | Implemented reserve-entry rules/geometry extraction, shared reserve legality helpers, and preview-gated ingress regression coverage on April 16, 2026. |
| PR-014D | Completed | Implemented `build_capability_v2`, explicit descriptor targeting, and deterministic combat-preview golden coverage on April 16, 2026. |
| PR-014E | Completed | Pushed to `dev` on May 13, 2026 as commit `fb4c258b` (`Implement PR-014E keyword registry runtime`). |
| PR-014F | Completed | Pushed to `dev` on May 13, 2026 as commit `f48f9d0e` (`Implement PR-014F detection marker infrastructure`). |
| PR-014G | Completed | Pushed to `dev` on May 13, 2026 as commit `01c0249f` (`Implement PR-014G upgrade assignment semantics`). |
| PR-014H | Completed | Pushed to `dev` on May 13, 2026 as commit `a328e227` (`Implement PR-014H unit turn provenance`). |
| PR-014I | Completed | Adds reactive move specs, modal stratagem requests, ledger exceptions, docs, and preview-gated goldens. |
| PR-014J | Completed | Adds actionable pile-in/consolidate scheduler boundaries, must-fight-next constraints, fight trace context, and replay-visible move categories. |
| PR-014K | Completed | Adds explicit build-capability extension groups, May 2026 faction-focus features, descriptor provenance, and v2+extension test coverage. |
| PR-014L | Pending | Preview source catalog and generic preview-gated golden tests. |
| PR-015 | Pending | Release-day exactness pass. |

## PR-001 — Repository scaffolding, architectural guardrails, and test reorganization

**Status:** Completed and pushed to `dev` on April 5, 2026 as commit `af21acb1` (`Add 11e port scaffolding and reorganize tests`).

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

**Status:** Completed and pushed to `dev` on April 5, 2026 as commit `b234185c` (`Implement PR-002 army build domain extraction`).

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

**Status:** Completed and pushed to `dev` on April 5, 2026 as commit `882103c9` (`Implement PR-003 runtime detachment integration`).

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

**Status:** Completed and pushed to `dev` on April 5, 2026 as commit `5ca1a905` (`Implement PR-004 descriptor and state blob split`).

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

**Status:** Completed and pushed to `dev` on April 5, 2026 as commit `27c56016` (`Implement PR-005 pregame flow and facade splits`).

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

**Status:** Completed and pushed to `dev` on April 5, 2026 as commit `327328e8` (`Implement PR-006 mission pack compiler and deployment split`).

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
- Preview-era disposition/missions content may remain placeholder or stubbed until PR-015 confirms the exact release behavior.

### Acceptance checks
- Tests cover all supported disposition pairings.
- Setup flow can advance from army build to mission selection to deployment using the new compiler.
- Mission descriptors and deployment descriptors remain deterministic.

### Non-goals
- No final release-day mission balance tuning.
- No AI training yet against the new mission space.
- No presentation of preview-derived mission pairing details as final released rules.

### Implementation notes
- Chapter Approved 2025-26 remains fully supported as the current default/autorandom matched-play pack.
- Additional provisional mission-pack entries can now appear when both armies expose compatible Force Dispositions.
- Twist handling is explicit in setup state: Chapter Approved entries resolve as "no twist", while preview-era entries remain stubbed placeholders until PR-015.

---

## PR-007 — Objective-site runtime model and battlefield map decomposition

**Status:** Completed and pushed to `dev` on April 5, 2026 as commit `f5f265c7` (`Implement PR-007 objective site runtime and map split`).

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

### Implementation notes
- Objective runtime now separates `ObjectiveSite`, `ControlRegion`, and `ScoreSource` in the battlefield layer while preserving `ObjectivePoint` as the stable import alias.
- `map.py` now acts as the stable facade over focused battlefield modules: `map_geometry.py`, `terrain_runtime.py`, `objective_sites.py`, and `control_queries.py`.
- State blobs, descriptors, and snapshots now preserve marker, terrain-footprint, and keyed-feature objective-site semantics; `state_blob_version` is now `1.2.0`.

---

## PR-008 — Attachment model rewrite, Leader/Support semantics, and `unit.py` / `army.py` decomposition

**Status:** Completed and pushed to `dev` on April 5, 2026 as commit `412032aa` (`Implement PR-008 optional attachment runtime and setup integration`).

### Goal
Move attachment semantics to the build/runtime seam and make leader/support/bodyguard behavior explicit and testable, while keeping preview-derived rule details provisional until the final 11th text is available.

### Why now
11th previewed changes make attachments a list-building concern, not just a pregame runtime choice.

### Main changes
1. Make attachment bindings chosen during army construction optionally authoritative for runtime setup when those bindings are provided.
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
- Attachment bindings can be authored at list-build time and propagated into runtime setup when present, while unresolved armies can still use the current `DECLARE_BATTLE_FORMATIONS` attachment decisions.
- Runtime unit attachment logic is explicit and decomposed.
- Character/support/bodyguard semantics are no longer hidden inside broad unit logic.
- Exact released attachment exceptions remain data/config work for PR-015.

### Acceptance checks
- Tests cover:
  - valid leader attachment
  - valid support attachment
  - invalid support without bodyguard
  - bodyguard death with character retained
  - serialization of attachment bindings through setup/replay
- `unit.py` attachment runtime state and `army.py` attachment validation/orchestration are routed through focused modules.

### Non-goals
- No stratagem stacking or charge-timing changes yet.
- No final codex-specific leader/support exceptions unless already needed for current data.

### Implementation notes
- Build-authored attachment bindings are currently optional. When absent, the current 10th-edition `DECLARE_BATTLE_FORMATIONS` attachment decisions remain the active path.
- `unit.py` stayed as the required facade; PR-008 extracted attachment runtime state into `unit_mixins/attachment_runtime_mixin.py` and army-side orchestration into `roster/army_attachment_runtime.py`.
- Parsed list units now receive deterministic `build_entry_id` values so authored bindings can be applied and round-tripped through setup, snapshots, and replay.

---

## PR-009 — Edition invariants, combat timing hooks, and attack/fight decomposition

**Status:** Completed and pushed to `dev` on April 5, 2026 as commit `bb8cf6dc` (`Implement PR-009 combat timing and decomposition`).

### Goal
Centralize the engine services, validation points, and timing hooks required by the previewed 11th-edition invariants, and split the combat monoliths while doing it. Do not treat preview text as final canonical behavior until PR-015.

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
   - `unit.py` combat-related behavior -> `unit_mixins/combat_runtime_mixin.py` while preserving `unit.py` as the required facade
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
- No claim that preview-derived combat timing semantics are final until PR-015.

---

## PR-010 — Replay/telemetry/training-manifest updates and safe pre-11th AI scope

**Status:** Completed and pushed to `dev` on April 6, 2026 as commit `ee0c065b` (`Implement PR-010 replay and training manifest updates`).

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

**Status:** Completed and pushed to `dev` on April 6, 2026 as commit `a46574c4` (`Implement PR-011 detachment seam cleanup`).

### Goal
Delete transitional 10th-only architectural assumptions so the codebase does not carry long-lived migration debt, while keeping final rules exactness deferred to PR-015.

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
- Search confirms removal of primary `army.detachment_type` dependency outside the read-only compatibility accessor or deleted code.
- Search confirms the old hard-coded matched-play mission combination table is gone or marked dead.
- README/docs are consistent with the new architecture.

### Non-goals
- No final release-data ingestion if the official rulebooks/indexes are not yet available.
- No post-launch balancing work.
- No claim that preview-based placeholder behavior is the final shipped 11th ruleset.

---

## PR-012 — Terrain-area runtime, serialization, and objective/layout identifiers

**Status:** Completed on April 8, 2026.

### Goal
Add first-class terrain-area runtime/state/descriptor objects and bind objective/layout metadata to them without activating preview terrain behavior as final canon.

### Why now
The April 8, 2026 terrain article makes terrain a two-layer model: terrain features plus terrain areas. The repo already has terrain-footprint objective support, but runtime terrain still revolves around `TerrainFeature` and feature footprints alone.

### Main changes
1. Add explicit terrain-area runtime/state types:
   - `TerrainArea`
   - terrain-area resolver helpers
   - deterministic terrain-area IDs
2. Extend battlefield runtime so the map can carry `terrain_areas` alongside `terrain_features`.
3. Extend descriptors, state blobs, snapshots, and version boundaries to serialize / compile terrain areas deterministically.
4. Extend `ObjectiveSite` / `ControlRegion` to carry:
   - `terrain_area_id`
   - `layout_slot_id`
5. Add temporary adapters that can derive provisional terrain-area records from existing terrain-feature footprints when explicit authored areas do not yet exist.
6. Update battlefield/runtime docs to describe the new feature-versus-area split and provisional adapter behavior.

### Start condition
- PR-011 merged.
- Current objective-site / battlefield split is stable.

### End condition
- The engine can represent terrain features and terrain areas separately.
- Objective/control/scoring runtime can point at a terrain area without inferring it indirectly from a feature label.
- Replay/state/descriptor plumbing preserves terrain-area identity cleanly.

### Acceptance checks
- Terrain-area state-blob and snapshot round-trip tests pass.
- Descriptor bundle IDs remain deterministic when terrain areas are present.
- Objective-site tests cover terrain-area and layout-slot identifier round-tripping.
- Existing terrain-feature-only fixtures still load through compatibility adapters.

### Non-goals
- No live Hidden / detection-range / Obscuring activation yet.
- No final release-day terrain data ingestion.
- No mission-layout template rewrite yet.

### Implementation notes
- This PR is driven by the April 8, 2026 terrain preview article, which states that terrain is made up of terrain features and terrain areas and that terrain-area footprints will be standardized.
- Objective/terrain interaction exactness still remains deferred until final release data is available.

---

## PR-013 — Hidden/detection visibility scaffolding, cover abstraction, and elevation queries

**Status:** Completed on April 8, 2026.

### Goal
Extract terrain visibility/cover logic into dedicated services and add provisional Hidden / detection-range / Plunging scaffolding without cutting the repo over to preview behavior as final canonical gameplay.

### Why now
The current repo still has ruins-centric LOS and feature-centric cover logic concentrated in `Map`, while cover is still injected as a save-side boolean. The April 8 preview adds Hidden, detection range, Obscuring terrain areas, BS-based cover, and updated height-based Plunging Fire expectations.

### Main changes
1. Extract terrain evaluation out of `map.py` into focused services/modules, at minimum:
   - `terrain_visibility.py`
   - `terrain_cover.py`
   - `terrain_elevation.py`
2. Introduce a neutral terrain combat/visibility context object that can carry:
   - visibility reasons
   - obscuring state
   - detection-range state
   - attacker skill modifiers
   - save modifiers
3. Add provisional Hidden-state data plumbing for units/models:
   - hidden eligibility
   - “did not shoot in the current or preceding player turn” tracking hooks
   - detection-range override data
   - explicit visibility-reason traces
4. Add elevation / Plunging query hooks that can answer:
   - whether an attacker is on a qualifying 3"+ section of terrain feature
   - whether the target contains ground-level models
   - whether a TOWERING short-range exception applies
5. Route existing terrain cover logic through the new services while keeping current 10th-style cover outputs alive behind compatibility adapters until PR-015.
6. Add clearly preview-derived tests for Hidden / Obscuring and Plunging examples without claiming the final release wording is already implemented.

### Start condition
- PR-012 merged.
- Terrain areas exist in runtime/state/descriptor plumbing.

### End condition
- LOS/cover/plunging evaluation is no longer trapped inside `Map` special cases.
- The engine has explicit provisional hooks for Hidden and detection range.
- Terrain cover can migrate later from save modifiers to BS modifiers without another monolithic refactor.

### Acceptance checks
- Existing LOS/cover tests continue to pass or are intentionally updated through compatibility adapters.
- New preview-derived tests cover:
  - Hidden blocked by distance
  - detection-range visibility override
  - area-based obscuring
  - 3"+ elevated Plunging query scaffolding
- Visibility and cover reason traces are deterministic and serializable.

### Non-goals
- No final BS-based cover cutover yet.
- No final TOWERING / Plunging behavior activation yet.
- No final objective-and-terrain interaction behavior yet.

---

## PR-014 — Mission-authored terrain layouts, template shapes, and preview pack alignment

**Status:** Completed on April 8, 2026.

### Goal
Make terrain layouts pairing-authored mission data built from reusable terrain-area templates instead of ruin presets, and update the preview mission-pack scaffolding to the currently announced five Force Dispositions while staying explicitly provisional.

### Why now
The April 3 mission preview says each mission pairing recommends three terrain layouts, and the April 8 terrain preview adds the standard terrain-area template shapes and sizes. The current repo still stores layouts on deployment definitions and instantiates layouts through a ruin-preset registry.

### Main changes
1. Split or replace `terrain_layouts.py` into focused pieces, for example:
   - `terrain_area_templates.py`
   - `terrain_layout_recipes.py`
   - `terrain_feature_renderers.py`
2. Add standard terrain-area templates for the published preview sizes:
   - large rectangles
   - large right-angle triangles
   - medium rectangles
   - long lines
   - short lines
3. Move recommended-layout ownership from generic `DeploymentDefinition.allowed_layouts` to mission-pairing-owned layout recommendations.
4. Update the provisional preview mission pack from the placeholder three-disposition model to the announced five Force Dispositions and a 5x5 pairing matrix.
5. Bind layout recipes to deterministic `layout_slot_id`s and terrain-area IDs so future objective/terrain rules can refer to authored battlefield areas directly.
6. Update mission/deployment docs and catalog tests to reflect pairing-owned recommended layouts and explicitly provisional preview data.

### Start condition
- PR-012 and PR-013 merged.
- Mission compiler and battlefield/runtime seams are stable.

### End condition
- Terrain layouts are authored from terrain-area templates/recipes, not only ruin presets.
- Recommended layouts are owned by mission pairings, not by reusable deployment definitions alone.
- The preview pack matches the currently announced Force Disposition catalog while remaining provisional.

### Acceptance checks
- Terrain template construction tests cover rectangles, right-angle triangles, long lines, and short lines.
- Mission-selection tests cover the five Force Dispositions and pairing-owned layout recommendations.
- Existing deployment/layout entrypoints keep working through compatibility adapters or façade functions.

### Non-goals
- No exact release-day mission/layout data ingestion.
- No final competitive-layout audit.
- No activation of final objective interactions before the official objective article / rules corpus is available.

---

## PR-014A — Combat rules profiles, combat geometry, and charge-resolution state

**Status:** Completed on April 16, 2026.

### Goal
Replace the current coarse combat timing/profile seam with rules-pack-driven combat rules and geometry services so PR-015 can swap exact 11th values without another combat rewrite.

### Why now
The April 15, 2026 combat preview splits several concepts that the current `CombatTimingProfile` still collapses together: engagement geometry, charge target timing, stage-specific fight ordering, move batching, and end-state legality.

### Main changes
1. Replace `CombatTimingProfile` with richer `CombatRulesProfile` and `CombatGeometryProfile` structures keyed by the rules bundle / adapter boundary.
2. Move engagement range, pass-through-enemy-engagement policy, ingress exclusion distance, charge target selection window, charge end-state constraints, pile-in batching mode, consolidate batching mode, overrun enablement, and stage-specific fight-order priority into those profiles.
3. Extract combat-geometry queries from raw constants and fight-move heuristics so charge / pile-in / consolidate validation ask a shared service for states such as `BASE_CONTACT`, `ENGAGED`, and `UNENGAGED`.
4. Introduce `ChargeResolutionChoice` and `ChargeOutcome` records that can represent post-roll target choice, a deliberate decline-to-charge path, reachable targets, chosen targets, and deterministic end-state legality.
5. Keep live runtime behavior preview-gated or adapter-selected; do not treat preview values as final canonical wording before PR-015.

### Acceptance checks
- Tests cover profile-driven 2" engagement evaluation, including an across-wall case where engagement is legal without base contact.
- Charge-resolution tests cover post-roll target choice plumbing and deterministic serialization of reachable/chosen target sets.
- Low-level fight-move and charge validation code read engagement geometry from the new profile/service boundary instead of hard-coded horizontal-distance assumptions.

### Non-goals
- No final release-day combat wording lock-in.
- No codex-specific combat exception audit yet.

---

## PR-014B — Fight scheduler and fight-entitlement snapshot

**Status:** Completed on April 16, 2026.

### Goal
Add a deterministic batch-oriented fight-step scheduler so pile-ins, attacks, overrun fights, and consolidates can be modeled as stage-level flow instead of as incidental side effects inside a per-unit fight loop.

### Why now
The April 15, 2026 combat preview changes the shape of the fight step itself: all pile-ins happen before attacks, Fights First selection has its own priority rule, overrun fights depend on start-of-step entitlement, and all consolidates happen at the end.

### Main changes
1. Add `fight_scheduler.py` with explicit stages such as `PILE_IN_ACTIVE`, `PILE_IN_REACTIVE`, `FIGHTS_FIRST`, `REMAINING_COMBATANTS`, and `CONSOLIDATE_BATCH`.
2. Add `fight_entitlements.py` to snapshot `engaged_at_step_start`, `charged_this_turn`, `eligible_due_to_prior_engagement`, `overrun_available`, and `consolidate_entitled`.
3. Route `fight_phase_manager.py` through the scheduler while keeping it as a façade/orchestrator entrypoint.
4. Separate Fights First ordering from the ordering of remaining combatants so the active player can be first among Fights First units without overloading one `fight_stage_start_player` field.
5. Redirect consolidate objective-seeking heuristics from raw `game_map.objectives` access to the newer objective-site / control-region surfaces.

### Acceptance checks
- Tests cover active-player-first ordering among Fights First units.
- Tests cover an overrun fight after a transport-destruction disembark sequence.
- Tests cover consolidate-to-objective behavior using objective-site / control-region geometry rather than ad hoc objective coordinates.
- Replay/decision traces remain deterministic across the staged fight flow.

### Non-goals
- No broad rewrite of attack resolution outside the scheduler/entitlement boundary.
- No local-only UI shortcuts; all choices still route through deterministic decision/action surfaces.

### Implemented notes
- Added `src/warhammer40k_ai/engine/fight_scheduler.py` and `src/warhammer40k_ai/engine/fight_entitlements.py`.
- Routed `fight_phase_manager.py` and `fight_order.py` through preview-aware stage snapshots so
  Fights First ordering and overrun eligibility no longer depend on one flat stage-start flag.
- Added preview overrun pile-in handoff for units that were eligible at step start but became
  unengaged before target declaration.
- Added end-batch consolidate staging and objective-site/control-region consolidate fallback
  routing in `fight_move.py` and `utility/calcs.py`.
- Added targeted regression coverage in:
  - `tests/engine/test_fight_scheduler.py`
  - `tests/rules/test_fight_phase_pile_in_consolidate_rules.py`

---

## PR-014C — Reserve-entry rules and geometry extraction

**Status:** Completed.

### Goal
Extract reserve-entry legality and landing geometry from the current monolithic setup mixin so the previewed >8" ingress exclusion can land as a profile/data change instead of another deep monolith edit.

### Why now
`setup_deployment_reserves_mixin.py` is still 4,698 lines, and the April 15, 2026 combat preview materially changes ingress geometry even though the downstream charge math stays separate.

### Main changes
1. Split reserve-entry legality into focused `reserve_entry_rules.py` and `reserve_entry_geometry.py` modules, leaving `setup_deployment_reserves_mixin.py` as a thin orchestration façade.
2. Move enemy-proximity exclusion checks, landing-envelope generation, and reserve-entry-kind-specific legality into rules-pack-driven helpers.
3. Preserve current live distances unless the preview bundle is explicitly selected; do not globally activate the >8" rule before PR-015.
4. Keep reserve landing geometry and charge-resolution math as separate services so future release-day wording can adjust one without entangling the other.

### Acceptance checks
- Tests cover current and preview-gated reserve-entry exclusion distances through the extracted helper layer.
- Tests confirm the preview >8" rule creates a larger landing envelope while leaving charge-success math independent.
- The setup mixin shrinks materially and delegates reserve legality to focused modules.

### Non-goals
- No final release-day reserve/deep-strike wording audit yet.
- No codex- or mission-specific reserve exception sweep beyond what the extraction requires.

### Implemented notes
- Added `src/warhammer40k_ai/engine/reserve_entry_rules.py` and
  `src/warhammer40k_ai/engine/reserve_entry_geometry.py` as the shared reserve-entry
  legality / geometry seam.
- Routed `engine/decision_handlers/movement.py` through the shared reserve evaluator so the
  authoritative `MOVE_UNIT` reserve-arrival path no longer hard-codes ingress geometry inline.
- Reduced `engine/game_mixins/setup_deployment_reserves_mixin.py` to façade-style wrappers for
  reserve placement legality, strategic-reserve edge checks, and battlefield-edge distance.
- Reused the shared reserve geometry placement builder from
  `engine/headless_policy_controller.py` so headless reserve synthesis and authoritative
  validation stay aligned.
- Added targeted regression coverage in `tests/engine/test_reserve_entry_rules.py` for current
  versus preview-gated ingress exclusion and for reserve validation remaining separate from
  charge-resolution state.

---

## PR-014D — `build_capability_v2` and combat-preview golden tests

**Status:** Completed.

### Goal
Upgrade AI-facing build-capability semantics and lock the new combat/reserve seams down with deterministic golden tests before release-day exactness.

### Why now
The repo already has a deterministic build-capability compiler, but the current `build_capability_v1` schema cannot express several preview-driven combat traits that will matter for mustering heuristics and matchup evaluation once PR-015 swaps in final values.

### Main changes
1. Add a versioned `build_capability_v2` schema and descriptor path for combat-preview-aware semantics.
2. Introduce capability fields such as:
   - `charge_option_flexibility`
   - `ingress_charge_conversion`
   - `fight_order_resilience`
   - `overrun_chain_potential`
   - `consolidate_objective_swing`
   - `engagement_footprint_pressure`
   - `transport_pop_punish_index`
3. Add deterministic combat golden tests for:
   - 2" across-wall engagement
   - post-roll charge target choice
   - active-player-first among Fights First
   - overrun after a transport pop
   - consolidate-to-objective
   - preview >8" ingress landing-envelope expansion with charge math kept separate
4. Update the relevant build-capability and AI artifact docs so schema selection and feature intent are explicit.

### Acceptance checks
- Descriptor compilation can intentionally target `build_capability_v2` without breaking deterministic descriptor IDs for a fixed schema/version selection.
- Golden tests pass under deterministic replay conditions and clearly separate preview scaffolding from release-day exactness.
- Docs describe the new schema fields and their intended preview-only role ahead of PR-015.

### Non-goals
- No broad model training or heuristic retuning.
- No attempt to infer final point values, datasheet changes, or codex-level melee behavior from the preview article alone.

### Implemented notes
- Added `BUILD_CAPABILITY_SCHEMA_V2` in `src/warhammer40k_ai/roster/build_capability_schema.py`
  with seven preview-combat-aware capability fields while leaving v1 as the default portable schema.
- Extended `src/warhammer40k_ai/roster/build_capability.py` so deterministic compilation can
  derive preview-combat semantics from the active combat rules/geometry profile when a v2-capable schema is requested.
- Verified `src/warhammer40k_ai/engine/descriptor_build_capability.py` can intentionally target
  v2 without changing the default descriptor contract.
- Added `tests/engine/test_combat_preview_golden.py` plus fixture-backed snapshot coverage for
  2" engagement, post-roll charge target choice, active-player-first Fights First ordering,
  overrun after a transport pop, consolidate-to-objective, and preview reserve-entry geometry.
- Updated build-capability, evaluation-pipeline, artifact-registry, and implementation-plan docs
  so schema intent and preview-only scope are explicit ahead of PR-015.

---

## PR-014E — Mechanics and keyword registry

**Status:** Completed and pushed to `dev` on May 13, 2026 as commit `fb4c258b` (`Implement PR-014E keyword registry runtime`).

### Goal
Add a rules-pack-driven keyword/effect registry for preview keywords and future codex keywords.

### Main changes
1. Add focused modules such as `rules/mechanic_registry.py`, `engine/weapon_keyword_runtime.py`, and `engine/movement_keyword_runtime.py`.
2. Define `KeywordDefinition` / `MechanicDefinition` payloads with `keyword_id`, `display_name`, `scope`, `timing_window`, `parameter_schema`, `enabled_by_profile`, and `source_provenance`.
3. Add preview-gated/inert definitions for `CLEAVE`, updated `HEAVY`, `MOBILE`, and generic hooks for `ASSAULT`, `LANCE`, `HAZARDOUS`, `RAPID_FIRE`, `SUSTAINED_HITS`, and `LETHAL_HITS`.
4. Implement generic `CLEAVE X` attack-dice modification at gather-attack-dice time, with target model count snapshotted at Select Targets.
5. Keep all current 10e behavior unchanged unless an explicit preview profile enables the keyword runtime.

### Acceptance checks
- `CLEAVE 1` and `CLEAVE 2` preview fixtures modify attack dice deterministically.
- Multi-target attacks do not receive Cleave dice.
- Updated Heavy criteria are evaluable from unit-turn provenance once PR-014H lands.
- `MOBILE` is represented as a movement keyword without changing default live terrain behavior.

### Implemented notes
- Added `rules/mechanic_registry.py`, `engine/weapon_keyword_runtime.py`, and `engine/movement_keyword_runtime.py`.
- Added preview-gated generic keyword definitions and source provenance for `CLEAVE`, updated `HEAVY`, `MOBILE`, `ASSAULT`, `LANCE`, `HAZARDOUS`, `RAPID_FIRE`, `SUSTAINED_HITS`, and `LETHAL_HITS`.
- Wired `CLEAVE X` through attack declarations and `AttackSequence.context` so target model count is captured at Select Targets.
- Added preview golden coverage under `tests/preview_11e/test_keyword_cleave_golden.py`.
- Added `docs/MECHANIC_KEYWORD_REGISTRY.md` and updated keyword semantics docs.

---

## PR-014F — Detection markers and Hidden-preserving shooting

**Status:** Completed and pushed to `dev` on May 13, 2026 as commit `f48f9d0e` (`Implement PR-014F detection marker infrastructure`).

### Goal
Replace ad hoc Hidden/detection logic with a generic marker/query system.

### Main changes
1. Add `battlefield/detection_markers.py` and `battlefield/hidden_state.py`.
2. Represent preview effects as generic `DetectionMarker` state with marker label, source unit, target unit, detection-range delta, duration, detachment/source provenance, and enabled profile.
3. Add `VisibilityModifierQuery` to collect base detection range, marker deltas, attack-scoped deltas, fixed-range overrides, and active-shooting-unit scoping.
4. Add `HiddenShootingExemption` for preview rules that let a unit shoot without losing Hidden.
5. Feed markers and exemptions through `terrain_visibility.py`; do not bypass the visibility service or create faction-specific branches.
6. Serialize marker/exemption state through snapshots, state blobs, DecisionRecord validation, and deterministic event logs.

### Acceptance checks
- Generic `+3` marker works for labels `detected`, `condemned`, `designated`, and `prey_marked`.
- Generic `+6` while-shooting modifier applies only to the active shooting unit/attack context.
- Hidden-preserving shooting exemption prevents a unit from losing Hidden after shooting.
- Marker/exemption state is snapshot/replay/state-blob visible.
- Preview gate disabled means markers do not affect live visibility.

### Implemented notes
- Added preview-gated golden coverage under `tests/preview_11e/test_detection_marker_golden.py`.
- Updated terrain, snapshot, state blob, network/save-load, and DecisionRecord docs/schemas.
- Verified focused visibility/snapshot/state-blob tests and the fast non-slow/non-integration suite in the local working tree.

---

## PR-014G — Upgrade assignment and enhancement-budget modes

**Status:** Completed and pushed to `dev` on May 13, 2026 as commit `01c0249f` (`Implement PR-014G upgrade assignment semantics`).

### Goal
Make 11e-style Upgrade payloads first-class in mustering without treating preview faction upgrades as live data.

### Main changes
1. Add a broader `UpgradeAssignment` / `RosterUpgradeAssignment` model distinct from legacy `EnhancementAssignment`, or narrow `EnhancementAssignment` under that broader type.
2. Track `upgrade_id`, source detachment, target kind (`unit`, `model`, `weapon_profile`), selected target ids, cardinality, budget-counting behavior, points-cost mode, selected weapon profile id, and declaration step.
3. Support preview fixture shapes such as up-to-three-unit upgrades, unit-only upgrades, model-only upgrades, weapon-profile upgrades declared during battle formations, and "does not count toward enhancement total" modes.
4. Keep released 10e roster validation behavior unchanged.

### Acceptance checks
- "Does not count toward enhancement total" preview fixture validates cleanly.
- "Target up to three units" fixture validates cardinality.
- Weapon-profile upgrade fixture persists selected profile identity.
- Descriptor IDs change when upgrade assignment semantics change.

### Implemented notes
- Added `UpgradeAssignment` / `RosterUpgradeAssignment` in the build-side army model.
- Extended `ArmyBlueprint`, `ArmyMusterRequest`, validation, runtime build metadata, snapshots, and `ArmyBuildDescriptor` payloads with `upgrade_assignments`.
- Added validation for source detachment, unit/weapon-profile target references, max-target cardinality, points-cost mode, enhancement-budget counting mode, and selected weapon-profile identity.
- Added preview-gated golden coverage under `tests/preview_11e/test_upgrade_assignment_golden.py`.

---

## PR-014H — Unit turn provenance and tactical status tokens

**Status:** Completed and pushed to `dev` on May 13, 2026 as commit `a328e227` (`Implement PR-014H unit turn provenance`).

### Goal
Centralize "what happened to this unit/model this turn" state used by Heavy, Hidden, reserve-entry, Bridgehead-style effects, actions, battle-shock, and future AI features.

### Main changes
1. Add `UnitTurnProvenance` with fields for set-up/reserve arrival, move types, charge, shooting, max per-model movement distance, and Hidden shooting exemptions.
2. Add a generic `StatusToken` / `UnitCondition` model for transient tactical state with source, kind, expiry, and JSON-safe payload.
3. Route Heavy preview checks, Hidden clearing, set-up-this-turn shooting modifiers, battle-shock persistence, detection/marker state, Fights First injections, "must fight next", and temporary attack modifiers through normalized provenance/token APIs where possible.
4. Serialize provenance/tokens through snapshot and replay.

### Acceptance checks
- Heavy preview fixture reads set-up-this-turn, unengaged, and max model move distance.
- Hidden clearing reads shot-this-turn but respects exemptions.
- Bridgehead-style "set up this turn" modifier is representable without faction-specific logic.
- Battle-shock persistence is representable without assuming automatic Command phase cleanup.
- Status tokens serialize through snapshot and replay.

### Implemented notes
- Added `UnitTurnProvenance`, `StatusToken` / `UnitCondition`, `PhaseBoundary`,
  `TurnBoundary`, and `Manual` expiry records in
  `src/warhammer40k_ai/engine/unit_turn_provenance.py`.
- Added generic helpers for Heavy provenance evaluation, Hidden clearing,
  set-up-this-turn modifier tokens, battle-shock persistence tokens, Fights First,
  "must fight next", and temporary attack modifiers.
- Threaded provenance and status tokens through unit snapshots and state blob
  unit entries; state blobs now use version `1.8.0`.
- Added preview-gated golden coverage under
  `tests/preview_11e/test_unit_turn_provenance_golden.py`.

---

## PR-014I — Reactive movement and stratagem-mode decision framework

**Status:** Completed.

### Goal
Make reactive moves and modal stratagems replayable, scheduler-visible, and remote-play compatible.

### Main changes
1. Add or extend decision kinds for stratagem mode selection, reactive move, surge move, Heroic Intervention mode, and reactive reserve exit.
2. Add `ReactiveMoveSpec` with trigger window, source unit, target reference, move kind, distance expression, destination policy, and end-state policy.
3. Add `StratagemMode` semantics for mode id, CP delta, charge-target policy, and max-roll cap.
4. Update stratagem ledger support for explicit preview exceptions such as repeat-use allowances without weakening general anti-stacking invariants.

### Acceptance checks
- Heroic Intervention mode fixture records selected mode, CP cost, and charge-target policy.
- Reactive normal move can be requested during the opponent's Movement phase.
- Surge move can require movement toward / attempting to finish engaged with the closest enemy.
- Reactive "place unit in Strategic Reserves" is represented as a legal transition, not a teleport hack.
- Stratagem-use exceptions are explicit and reason-traced.

### Implemented notes
- Added `ReactiveMoveSpec`, `StratagemMode`, and
  `ReactiveReserveExitTransition` in
  `src/warhammer40k_ai/engine/reactive_movement.py`.
- Added decision kinds for `SELECT_STRATAGEM_MODE`, `REACTIVE_MOVE`,
  `SURGE_MOVE`, `SELECT_HEROIC_INTERVENTION_MODE`, and
  `SELECT_REACTIVE_RESERVE_EXIT`, with AI-router, manifest, decision catalog,
  and network/save-load mapping updates.
- Added a queue helper for spec-backed reactive movement decisions while
  preserving existing `MOVE_UNIT` reactive movement behavior.
- Extended `StratagemApplicationLedger` with explicit repeat-use exceptions,
  replayable reason traces, and target-stacking enforcement.
- Added preview-gated golden coverage under
  `tests/preview_11e/test_reactive_movement_stratagem_modes_golden.py`.

---

## PR-014J — Make fight scheduler stages actionable, not just labels

**Status:** Completed on May 13, 2026.

### Goal
Turn fight scheduler stages into first-class runtime decision boundaries before release-day fight interrupts and "must fight next" behavior arrive.

### Main changes
1. Expose pile-in and consolidate stages as pauseable scheduler decisions.
2. Snapshot fight entitlements before Fights First and remaining-combatant resolution.
3. Add explicit support for Fights First injection after an enemy fought, "must fight next", multiple Heroic Intervention/countercharge entitlements, overrun/prior-engagement eligibility surviving target removal, and consolidate-to-objective/consolidate-to-engage categories.

### Acceptance checks
- "Must fight next" status token constrains next fight selection.
- Pile-in stage can pause for a decision instead of being skipped.
- Consolidate batch can pause for a decision instead of only draining a queue.
- Fight entitlement snapshots, decisions, and outcomes are replay-visible.
- Existing preview combat goldens still pass.

### Implemented notes
- `fight_scheduler.py` now exposes serialized scheduler state, stage decision boundaries, trace events, pending pile-in/consolidate queues, and deterministic decision context for fight-stage requests.
- `fight_phase_manager.py` routes preview `PILE_IN_ACTIVE`, `PILE_IN_REACTIVE`, and `CONSOLIDATE_BATCH` stages through authoritative `MOVE_UNIT` decisions instead of auto-advancing them.
- Status tokens can inject `fights_first` eligibility and constrain the next selected fighter with `must_fight_next`; consumed tokens are removed once that unit fights.
- Fight movement requests carry explicit decision categories for consolidate-to-engage and consolidate-to-objective, plus entitlement snapshots for replay and AI ranking.
- Regression coverage exercises pile-in pausing, must-fight-next ordering, consolidate decision categories, and existing combat-preview goldens.

---

## PR-014K — Capability extension registry instead of constant schema churn

**Status:** Completed on May 13, 2026.

### Goal
Allow deterministic AI/mustering capability features from faction-focus previews without creating `build_capability_v3`, `v4`, etc. for every preview article.

### Main changes
1. Add `BuildCapabilityExtensionGroup` with group id, feature definitions, source provenance, and explicit activation.
2. Add May 2026 faction-focus extension fields such as `detection_marker_coverage`, `anti_hidden_projection`, `hidden_persistence_value`, `keyword_mutation_density`, `cleave_horde_clearance`, `heavy_stationary_fire_quality`, `mobile_terrain_traversal_value`, `reactive_move_density`, `heroic_intervention_density`, `must_fight_next_leverage`, `action_after_advance_fallback_flex`, `reserve_reposition_flex`, `upgrade_cardinality_complexity`, and `battle_shock_persistence_leverage`.
3. Keep extension features deterministic descriptor inputs, not learned models or widened model-compatibility claims.

### Acceptance checks
- Descriptor can target v2 alone or v2 plus the May 2026 faction-focus extension group.
- Capability descriptor IDs include schema and extension-group IDs.
- Old v1/v2 manifests remain valid.
- Future points/dataslate/codex patches can recompute capabilities without changing artifact ABI.

### Implemented notes
- `build_capability_schema.py` now defines `BuildCapabilityExtensionGroup`, a registry, resolver helpers, and `capability_extension:11e_faction_focus_may2026` with explicit source provenance.
- `compile_build_capability_profile(...)` accepts explicit extension groups, validates the May 2026 group against `build_capability_v2`, and keeps v1/v2 payloads unchanged when no group is active.
- Active extension payloads include `extension_group_ids` and `capability_extension_groups`, so descriptor/profile ids change deterministically when extension semantics are enabled.
- The May 2026 extension fields are deterministic capability scores derived from existing roster shape, combat-preview profile surfaces, and PR-014G upgrade-assignment semantics.
- Documentation and regression coverage lock v2-alone behavior, v2+extension behavior, descriptor id changes, and no implicit artifact compatibility widening.

---

## PR-014L — Preview source catalog and generic golden tests

**Status:** Pending.

### Goal
Track preview-derived assumptions explicitly and add generic preview-gated tests without ingesting preview faction rules as live data.

### Main changes
1. Add `docs/preview_sources/11e_faction_focus_may2026.json`.
2. Record source ids, URLs, publish dates, `preview_only=true`, and observed generic mechanics.
3. Add generic tests for keyword Cleave, detection markers, Hidden-preserving shooting, Heroic Intervention modes, reactive movement, and upgrade assignment.
4. Ensure descriptors/reason traces carry source provenance wherever preview behavior is enabled.

### Acceptance checks
- Every preview-only mechanic test is preview-gated.
- No test requires a real final 11e faction pack.
- Source provenance is present in descriptors/reason traces where preview behavior is enabled.
- PR-015 has a clear checklist of preview assumptions to confirm, replace, or delete.

---

## PR-015 — Release-day alignment PR (required when final 11th rules are in hand)

**Status:** Pending.

### Goal
Swap preview-driven placeholders and assumptions for final release-day data and exact wording once the real 11th core rules / mission pack / army-construction texts are available.

### Why now
The previous PRs build the right seams, but preview articles are not a substitute for the final rules corpus.

### Main changes
1. Ingest final 11th mission pack / army construction / deployment / twist / objective wording.
2. Ingest final terrain-area / Hidden / detection-range / Obscuring / cover / Plunging / layout wording and data.
3. Ingest final combat, charge, reserve-arrival, and fight-step wording/data.
4. Replace preview TODOs / placeholder assumptions with exact implementations.
5. Re-run semantic-diff / replay migration / descriptor compilation checks.
6. Rebaseline fixtures where the final wording differs from the preview.
7. Perform a final audit of detachment-point handling, attachment rules, secondaries, terrain/layout semantics, reserve-entry semantics, build-capability schema alignment, and edition invariants.

### Start condition
- Official 11th rules data is available to the team.
- PR-014L merged, or any intentionally deferred PR-014E through PR-014L item has an explicit owner and release-day mitigation.

### End condition
- Preview assumptions are either confirmed and retained or replaced with final release behavior.
- The repo is ready to begin real 11th data collection and safe training under the updated manifests.

### Acceptance checks
- All preview TODOs are closed or intentionally deferred with issue links.
- Final release-day smoke tests pass across:
  - army build
  - setup flow
  - mission generation
  - terrain areas / layouts / visibility
  - objective/control/scoring
  - attachments
  - reserve entry / ingress
  - build capability descriptor compilation
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
12. PR-012 → terrain-area runtime / objective-layout identifiers
13. PR-013 → visibility / cover / plunging scaffolding
14. PR-014 → terrain layouts / preview pack alignment
15. PR-014A → combat rules profiles / geometry / charge state
16. PR-014B → fight scheduler / entitlements
17. PR-014C → reserve-entry rules / geometry extraction
18. PR-014D → build capability v2 / combat golden tests
19. PR-014F → detection markers / Hidden-preserving shooting
20. PR-014E → mechanics and keyword registry
21. PR-014H → unit turn provenance / tactical status tokens
22. PR-014I → reactive movement / stratagem modes
23. PR-014J → actionable fight scheduler stages
24. PR-014G → upgrade assignment / enhancement-budget modes
25. PR-014K → capability extension registry
26. PR-014L → preview source catalog / generic goldens
27. PR-015 → release-day exactness pass

If a PR is too large, split it at module boundaries, not at arbitrary halfway points.

---

# Execution notes for GPT-5.4

## How to handle large-file splits
- First create focused target modules and move logically cohesive methods/helpers.
- Keep the original giant file as a façade that imports from the new modules.
- Once the new modules are stable and call sites are migrated, shrink the façade further.
- Avoid a giant “move everything everywhere” PR.

## How to handle adapters
- Temporary adapters are acceptable in PR-002 through PR-014L.
- They should be clearly marked with:
  - `TODO(11e-cleanup)` or equivalent
  - a reference to PR-015 as the deletion point

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
- PR-012 / PR-013: battlefield / terrain runtime / state schema docs
- PR-014: mission/deployment and battlefield layout docs
- PR-014A / PR-014B / PR-014C: combat, charge, reserve-entry, and decision/replay docs
- PR-014D: build-capability schema, AI artifact, and combat golden-test docs
- PR-014E: keyword/mechanic registry docs and keyword-runtime tests
- PR-014F: terrain visibility, state blob, snapshot/replay, and network/save-load docs
- PR-014G: army mustering and descriptor docs for upgrade assignment semantics
- PR-014H: unit-turn provenance, state blob, snapshot/replay, and status-token docs
- PR-014I: decision types, network/save-load mapping, reactive movement, and stratagem ledger docs
- PR-014J: fight scheduler, fight-stage decision, and replay docs
- PR-014K: build-capability schema/extension and AI artifact docs
- PR-014L: preview source catalog docs and PR-015 assumption checklist
- PR-015: final release-day rules-ingestion docs and any preview clean-up notes

---

# Post-port training guidance

Do **not** start broad hierarchical training before PR-010 and PR-015 are complete.

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
5. Terrain is modeled as features plus areas, and recommended terrain layouts are pairing-owned data rather than ruin-only presets.
6. Objectives are modeled as sites/control/scoring, not marker-only assumptions.
7. Attachment bindings are chosen at build time and propagated cleanly to runtime.
8. Edition invariants are enforced centrally.
9. Giant files have been materially reduced and split along coherent responsibility boundaries.
10. The codebase is 11th-first and no longer architecturally anchored to 10th.
11. Pre-11th training is limited to portable, descriptor-conditioned components.
