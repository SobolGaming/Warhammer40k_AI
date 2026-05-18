# Roster Search

This document defines the PR-MUSTER-007 offline roster-search seam.

Related docs:
- `docs/AI_MUSTERING_TOURNAMENT_ARCHITECTURE.md`
- `docs/ARMY_MUSTERING_SCAFFOLDING.md`
- `docs/BUILD_CAPABILITY_SCHEMA.md`
- `docs/TOURNAMENT_EVALUATION_OBJECTIVE.md`
- `docs/TOURNAMENT_EVALUATION_PIPELINE.md`

## Purpose

PR-MUSTER-007 adds a deterministic roster-edit DSL and a validator-backed search
loop for offline mustering optimization without any learned-model requirement.

The new modules are:
- `src/warhammer40k_ai/roster/roster_edit_actions.py`
- `src/warhammer40k_ai/roster/roster_repair.py`
- `src/warhammer40k_ai/roster/roster_search.py`
- `src/warhammer40k_ai/roster/roster_search_report.py`

## Search Contract

Roster search operates on `ArmyBlueprint`, not on ad hoc runtime mutations.
Every evaluated candidate is:
1. transformed by explicit roster-edit actions
2. repaired for structural consistency
3. materialized through real runtime mustering
4. validated through runtime army legality rules before scoring

This keeps the optimizer bounded and auditable. Search proposes edits; legality
stays in the existing mustering and runtime validation stack.

## Edit DSL

The deterministic edit DSL supports:
- add detachment
- remove detachment
- swap detachment
- add unit entry
- remove unit entry
- change wargear choice
- assign enhancement
- remove enhancement
- bind attachment
- unbind attachment
- rebalance detachment-point spend
- mutate force disposition
- select warlord

Each edit exposes a stable `action_id` derived from canonical JSON payloads.

## Validation Boundary

The validator-backed boundary for search is:
- `ArmyMusterer.validate_runtime_legality()`

That path materializes the blueprint into a runtime `Army`, applies authored
attachment bindings, validates support-artillery joins, and then runs
`Army.validate()`.

This means roster search inherits the existing engine checks for:
- exactly one valid warlord
- enhancement count limits
- enhancement eligibility and detachment matching
- duplicate datasheet caps
- Epic Hero duplication rules
- leader and support attachment legality
- points limit checks

## Wargear Optionality

Optional wargear mutation is handled through the same build-side and runtime
seam already used by mustering.

`ChangeWargearChoiceAction` edits either:
- `RosterEntry.wargear`
- `RosterEntry.metadata["wargear_by_model"]`

Runtime materialization then routes those choices through:
- `wargear_dict_for_entry(...)`
- `Unit.apply_wargear_options_strict(...)`
- `unit.validate_wargear_selection()`

If a selected option resolves to a datasheet Wargear ability instead of a weapon
profile, the assigned model ability still counts as equipped wargear for active
rule checks.

So optional wargear changes are validated against the actual datasheet option
rules instead of a search-only approximation.

## Search Strategies

`search_rosters(...)` supports three strategies under one interface:
- `beam`
- `local`
- `evolutionary`

All strategies share the same action provider, repair path, validation boundary,
and report schema. Fixed seeds must produce reproducible results.

## Reports

`RosterSearchReport` includes:
- ranked legal candidates only
- utility decomposition
- edit traces
- iteration summaries
- validation-contract metadata

Search reports must remain explicit about the legality contract. If a candidate
cannot pass runtime mustering and validation, it is rejected and not returned as
an evaluated roster.
