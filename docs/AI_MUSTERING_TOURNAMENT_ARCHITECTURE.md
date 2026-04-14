# AI Mustering Tournament Architecture

This document defines the stable architecture seam for AI-facing army mustering,
tournament roster evaluation, and future roster optimization.

Related docs:
- `docs/ARMY_MUSTERING_SCAFFOLDING.md`
- `docs/ML_ARTIFACT_REGISTRY.md`
- `docs/TOURNAMENT_EVALUATION_OBJECTIVE.md`
- `docs/ML_DEPENDENCY_BOUNDARY.md`

## Optimization Target

The object of optimization is:

```text
(ArmyBlueprint, policy_bundle_id, rules_bundle_id, field_distribution_id, event_policy_id)
```

A roster is never evaluated in isolation. It is always evaluated under:
- a rules bundle
- a controller bundle
- a field model
- an explicit event policy

## System Boundaries

- `ArmyBlueprint` remains the build-side root object for authored or searched
  rosters.
- Existing validator and mustering code remain the only legality gate.
- Search operates by proposing deterministic edits to build-side roster data and
  then re-running validation and mustering.
- Tournament evaluation sits above the engine. It does not bypass runtime legality
  checks.
- Registry metadata, bundle manifests, and heuristic fallback selection must be
  readable without ML extras installed.
- Direct end-to-end list generation is not the first learned target.

## Core Objects

### `ArmyBlueprint`

`ArmyBlueprint` is the canonical build-time roster object.

Responsibilities:
- roster composition
- detachment selection
- detachment-point budget
- enhancement assignment
- attachment binding
- selected and allowed force dispositions

Non-responsibilities:
- final legality verdicts without validation
- runtime combat behavior
- learned evaluation output

### `BuildCapabilityProfile`

`BuildCapabilityProfile` is a deterministic, JSON-safe summary of what a roster
can do under the active rules and descriptors.

Inputs:
- `ArmyBlueprint`
- `rules_bundle_id`
- descriptor provenance
- `event_policy_id` when policy affects semantics

Requirements:
- schema-versioned
- recomputed from rules and descriptors
- never hand-maintained by faction label alone
- suitable for both heuristic and learned evaluators

### `TournamentFieldDistribution`

`TournamentFieldDistribution` describes the environment a fixed roster is tested
against.

Required fields:
- `field_distribution_schema_id`
- `field_distribution_id`
- `rules_bundle_id`
- `event_policy_id`
- opponent roster entries or archetype slices with weights
- mission, deployment, and terrain distributions
- terrain layout pack id

Optional fields:
- round count
- event format metadata
- pairing metadata

### `EventPolicyDescriptor`

`EventPolicyDescriptor` makes tournament constraints explicit instead of implicit.

Required fields:
- `event_policy_schema_id`
- `event_policy_id`
- `force_disposition_lock_mode`
- `secondary_selection_mode`
- `terrain_layout_mode`
- `clock_policy`
- `pairing_mode`
- `roster_submission_mode`
- `max_rounds`

Stable enums defined in this ABI:
- `force_disposition_lock_mode`: `event_locked | round_locked | flexible`
- `pairing_mode`: `iid | swiss`

All other enum families are schema-versioned and may expand only under a new
`event_policy_schema_id`.

### `PolicyBundle`

`PolicyBundle` is the runtime assembly of controller-facing artifacts and
heuristics used during tournament evaluation.

Responsibilities:
- map logical runtime roles to artifacts or heuristics
- declare compatibility scope for rules, descriptors, and event policy
- declare required feature and capability schemas
- define explicit fallback order

Non-responsibilities:
- roster legality
- direct ownership of artifact files
- implicit compatibility inference from faction labels

### `MusterRecord`

`MusterRecord` is the telemetry object for roster-evaluation and roster-search
experiments.

Required provenance families:
- `army_blueprint_hash`
- `rules_bundle_id`
- `descriptor_bundle_id`
- `build_capability_profile_id`
- `event_policy_id`
- `field_distribution_id`
- `policy_bundle_id`
- git commit
- schema ids

Expected evaluation content:
- utility decomposition
- replay and gate results
- search trace or edit actions when search is involved

## Evaluation Loop

1. Author or search a candidate `ArmyBlueprint`.
2. Validate the build-side roster and, when required, materialize runtime form
   through engine-side mustering.
3. Compile a deterministic `BuildCapabilityProfile`.
4. Resolve the active `PolicyBundle`.
5. Evaluate the fixed roster across the configured `TournamentFieldDistribution`
   under the active `EventPolicyDescriptor`.
6. Emit a `MusterRecord` with full provenance and decomposed utility output.
7. Feed search or comparison code from those records. Search never bypasses
   validation, mustering, or compatibility checks.

## Determinism and Portability

- Candidate rosters, capability profiles, and policy bundle ids must be
  serializable and replay-stable.
- Any randomized search or evaluation helper must use injected RNG and record
  enough provenance to reproduce the run.
- Controller realizability matters. Timeout risk, no-progress behavior, and
  replay stability are first-class evaluation inputs, not post-hoc notes.
- Heuristics and learned artifacts must be swappable behind the same
  `PolicyBundle` contract.

## First Learned Targets

The first learned targets should be bounded evaluators, not direct list builders.

Recommended early learned targets:
- matchup evaluator
- playbook selector for fixed submitted rosters
- roster-edit ranker used inside deterministic search

Deferred target:
- direct end-to-end list generation from raw prompts or latent samples
