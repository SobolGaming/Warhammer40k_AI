# Bringing Back AI (HRL + Training Plan)

This document defines a version-portable AI architecture and training plan for Warhammer 40,000 matched play.

The design goal is not only to survive routine rules patches without breaking legality. The stronger goal is to preserve useful learned behavior across points updates, dataslates, mission-pack changes, terrain-pack changes, and future editions with minimal retraining. Wherever possible, the engine should patch behavior by recompiling rules descriptors, regenerating semantic candidate features, and fine-tuning small adapters or heads rather than retraining the full stack.

## Purpose

- Define the AI architecture and interfaces needed to support Warhammer 40,000 matched play.
- Provide a training and retraining plan resilient to points updates, dataslates, errata, mission-pack changes, terrain-pack changes, and future editions.
- Specify the engineering roadmap to make AI integration testable and incremental.
- Keep learned behavior portable across rules bundles by pushing mission, objective, terrain, deployment, and tool semantics into versioned engine descriptors and rule-derived candidate metadata.

The portability target is not just "legal actions remain legal after a patch", but "high-value behavior can be preserved across patches and editions by recompiling descriptors and relabeling semantic features with minimal retraining."

## Live-Service Rules Assumptions

- Matched Play is treated as a versioned rules bundle, not a single static ruleset.
- The active bundle may change independently across:
  - core rules
  - rules commentary / errata
  - mission pack
  - terrain pack
  - dataslate
  - points pack
  - faction and detachment tools
- The AI must survive regular patch churn and should prefer descriptor recompilation, replay relabeling, and adapter updates over broad retraining.
- A future edition transition should be handled as a semantic migration first and a full retrain only if smaller transfer methods fail.

## Primary Objective

- Maximize VP delta (your VP minus opponent VP) over 5 rounds within tournament time constraints.
- Optimize both VP gain and VP denial.
- Preserve strategic competence across rules updates by planning over stable affordances rather than edition-specific labels.

## Key Constraints

- Tournament time budget is hard and cannot be treated as an afterthought.
- Movement has the highest branching factor and the strictest legality requirements.
- Mission, terrain, and scoring semantics can change independently from unit and weapon data.
- The AI must be anytime, computationally bounded, and deterministic under replay.

## Portability Principles

- Learn invariant affordances, not edition-specific labels.
- Keep legality in the engine and keep most semantics in engine-derived descriptors.
- Represent missions, objectives, terrain, deployment, and tools as data, not hard-coded policy assumptions.
- Recompute semantic candidate features under the active rules bundle so the model ranks fresh semantics, not stale board patterns.
- Prefer small version adapters, replay relabeling, and head fine-tuning before any broad retraining.
- Treat edition changes as structured diffs across legality, geometry, scoring, and resource economy.

## Rules Bundle and Descriptor Model

The engine must treat matched play as a compiled rules bundle, not a monolithic ruleset id.

### Rules Bundle Identity

Minimum fields:

- `core_rules_id`
- `rules_commentary_id`
- `mission_pack_id`
- `terrain_pack_id`
- `dataslate_id`
- `points_id`
- `faction_pack_id`
- `detachment_pack_id`

A convenience `rules_bundle_id` may be derived from the above, but the atomic ids remain first-class and must appear in logs, datasets, and replay artifacts.

### Descriptor Families

The following descriptor families must be versioned, serializable, and consumable by both engine and learner-facing feature pipelines:

- `MissionDescriptor`
- `ObjectiveDescriptor`
- `TerrainDescriptor`
- `DeploymentDescriptor`
- `ToolDescriptor`

### MissionDescriptor

Must describe:

- battle-round structure
- scoring windows
- score-source definitions
- denial windows
- secondary generation and discard mechanics
- catch-up or asymmetric mechanics
- action-site semantics
- deployment-map hooks
- endgame scoring hooks

### ObjectiveDescriptor

Must describe:

- geometric footprint or marker interaction
- control test semantics
- whether models can end moves on or overlap the marker
- sticky or non-sticky behavior
- score-source bindings
- transform, deactivate, or migrate rules
- action hooks tied to that objective
- public versus hidden semantics if relevant

### TerrainDescriptor

Must describe:

- footprint and volume
- floor and layer structure
- line-of-sight and visibility semantics
- cover semantics
- movement traversal semantics by archetype
- objective overlap semantics where relevant
- staging, blocker, breachable, and lane-control tags

### DeploymentDescriptor

Must describe:

- deployment zones
- reserve entry constraints
- edge and lane semantics
- mission-specific zone transforms

### ToolDescriptor

Retain the existing structured tool approach, but treat tool descriptors as one member of a broader descriptor family rather than the only major semantic descriptor.

## HRL Architecture

### Tier 0: Rules Compiler, Action Masking, and Semantic Affordance Generation (Non-learned)

Responsibilities:

- Load the active rules bundle.
- Compile mission, objective, terrain, deployment, and tool descriptors.
- Enumerate decision points and legal candidate actions.
- Enforce legality in the engine, not in the policy.
- Derive semantic affordances from current rules plus current board state.
- Produce opportunity catalogs and candidate metadata that can be regenerated after patches.

Tier 0 owns:
- legality
- scoring-window computation
- score-source binding
- control-region derivation
- terrain semantics
- candidate generation
- time-budget enforcement

### Tier 1: Strategic Planner (Learned)

Tier 1 plans over stable semantic affordances rather than hard-coding objective ids.

Primary outputs:

- scoring-window priorities
- priority opportunities
- denial opportunities
- staging regions
- reserve-denial goals
- action-enablement goals
- resource posture
- risk posture
- unit priority tiers

Tier 1 should prefer abstractions such as:
- scoring source
- denial source
- control region
- staging region
- action site
- reserve lane
- safe firing lane

Tier 1 should avoid direct dependency on current objective labels whenever an abstract score-source representation is available.

### Tier 2: Tactical Binder / Orchestrator (Learned)

Tier 2 binds Tier 1 opportunities to current-rules concrete targets.

Responsibilities:

- convert abstract opportunities into per-unit tasks
- bind opportunities to region ids, source refs, and action-enablement targets
- allocate compute budgets based on value and urgency
- set resource posture for the phase or sequence
- hand off MovementIntents and other decision-specific intents to Tier 0

Tier 2 may use concrete objective ids and terrain pieces as late-bound execution details, but those should not be the primary strategic abstraction.

### Tier 3: Micro-Executors (Learned + Solver)

Tier 3 ranks legal candidates for movement, targeting, charges, fight ordering, and tool usage.

Responsibilities:

- score solver-generated legal candidates
- consume rule-derived semantic candidate metadata
- operate as a candidate ranker and selector, not a legality generator
- minimize dependence on edition-specific raw labels where semantic engine features are available

### Tier 4: Telemetry, Replay, and Relabeling (Non-learned + Learner Support)

Responsibilities:

- deterministic replay
- candidate-set validation
- cross-version replay-to-relabel
- dataset generation for human play, heuristic play, and self-play
- training data manifests, validation, and provenance

## Decision API Contract

All player decisions must use a unified decision interface exposed by the engine.

### Decision Schema

```python
class Decision:
    decision_id: str
    decision_type: str
    actor_player_id: str
    context: dict
    candidates: list[CandidateAction]
    mask: list[bool]
```

### CandidateAction Schema

```python
class CandidateAction:
    action_id: str
    params: dict
    metadata: dict
```

Candidate enumeration remains intent-driven and solver-backed. Policies select among legal candidates instead of generating raw coordinates or free-form legal interpretations.

### Required Decision Context Fields

Minimum context fields for portability-aware policies:

- `rules_bundle`
- `phase`
- `mission_state`
- `terrain_state_summary`
- `score_window_state`
- `opportunity_catalog`
- `plan_id`
- `task`
- `compute_tier`
- `time_budget_ms`

### Required Candidate Metadata Classes

Candidate metadata should include both solver metrics and semantic projections.

#### Solver / geometry metadata

Examples:
- `solver_ms`
- `path_witness_ref`
- `corridor_witness_ref`
- `tight_clearance`
- `coherency_score`
- `threat_exposure_score`

#### Semantic candidate metadata

Minimum target set:
- `projected_score_delta_next_window`
- `projected_score_delta_round`
- `projected_deny_delta_next_window`
- `projected_control_delta`
- `projected_action_enablement_delta`
- `projected_exposure_delta`
- `projected_trade_ev`
- `cover_delta`
- `los_delta`
- `resource_delta`
- `rules_provenance_refs`

The model should rank candidates using semantic features recomputed under the active rules bundle. That makes policy behavior more portable than ranking on raw board geometry alone.

## Human Gameplay Telemetry and Learning

Human games are a first-class data source for bootstrapping and realism. The telemetry contract must align with the Decision API so human actions map to the same candidate-based policies used by AI.

### DecisionRecord Schema (Minimum)

See `DECISION_RECORD_SCHEMA.json` for the canonical JSON schema.

DecisionRecord is a telemetry superset of the Decision API:

- `decision_id`, `decision_type`, `candidates`, and `mask` mirror the Decision object
- `chosen_action_id` mirrors the selected `CandidateAction.action_id`
- telemetry-only fields add replay, relabeling, timing, and outcome context

Each decision should capture:

- identification and determinism:
  - `game_id`
  - `turn_id`
  - `phase`
  - `decision_id`
  - `decision_type`
  - atomic rules ids and convenience `rules_bundle_id`
  - `global_seed`
  - `decision_seed`
- observation:
  - replayable `omniscient_state`
  - `player_obs_state(player_id)`
- candidate set:
  - full `candidates`
  - `mask`
  - stable `action_id`
  - `params`
  - `metadata`
- choice:
  - `chosen_action_id`
  - wall-clock time used
- outcome:
  - immediate deltas
  - end-of-turn return
  - end-of-game return where available

### HumanActionCandidate Injection (Required)

Humans will often select actions not present in the solver's top-K candidates. To keep training aligned:

- always generate the solver candidate set for the decision
- when a human commits an action, validate it and compute required witness artifacts
- if the action is not already in the candidate set, append a `HumanActionCandidate` with exact params and witnesses, then mark it as the chosen action

This preserves a candidate-based dataset even for free-form UI actions.

### Cross-Version Relabel Support (Required)

DecisionRecord must preserve enough information to be re-evaluated under a different rules bundle.

Minimum additional requirements:

- state snapshots or deltas sufficient to reconstruct semantic affordances
- descriptor ids used at record time
- optional relabel fields:
  - `relabel_rules_bundle`
  - `relabel_status`
  - `relabel_candidate_map`
  - `chosen_action_status_under_relabel`

Replay under the original bundle must remain exact. Relabel under a new bundle may regenerate candidates and semantic metadata. Chosen actions that become illegal under a new bundle must be marked accordingly or mapped to a nearest legal analogue only when deterministic mapping rules exist.

### Invalid Attempt Telemetry (Optional but Recommended)

When a human attempts an illegal action and the UI rejects it:

- log the attempted action as invalid with the rejection reason
- preserve enough context for later UI explainability and proposal models

### Usage by Tier

- Tier 3: primary supervised source via learning-to-rank over candidates
- Tier 2: auxiliary supervision for tasking, posture, and binding
- Tier 1: RL or self-play primary, with optional self-supervised targets from observed opportunity priorities

## Canonical State Contract

State blobs are deterministic, versioned JSON objects used for telemetry, replay, relabeling, and feature extraction.

### Required Top-Level Fields

- `state_blob_version`
- `rules_bundle`
- `battle_round`
- `phase`
- `active_player_id`
- `players`
- `mission_state`
- `deployment_state`
- `objectives`
- `scoring_surfaces`
- `control_regions`
- `terrain`
- `units`

### Design Notes

- Terrain must be a first-class top-level field, not an implied side-channel.
- Objective markers and score sources are distinct concepts if the active mission pack requires that distinction.
- The state must preserve enough structure for descriptor recompilation and relabeling.
- Public geometry and public semantic state must be available to both replay and model feature extraction.
- Hidden information must remain hidden in player-perspective views.

### Derived Deterministic Features

Tier 0 may precompute deterministic derived features such as:

- engagement state
- visible threat bands
- control-region membership
- score-source reachability
- reserve-denial coverage
- action-site reachability
- terrain traversal flags
- line-of-sight feasibility summaries

## Movement System Design

Movement still uses intent, constrained optimization, and full path witnesses. The new requirement is that movement scoring should be driven by stable affordances and rule-derived semantics rather than raw objective ids.

### MovementIntent Schema (Required)

```python
class MovementIntent:
    target_region_ids: list[str]
    target_opportunity_ids: list[str]
    desired_affordances: list[str]
    screen_deny_targets: list[str]
    weights: dict
    anchors: dict[str, str]
    constraint_toggles: dict
```

Examples of `desired_affordances`:
- `HOLD_SCORE_SOURCE`
- `DENY_SCORE_SOURCE`
- `STAGE_FOR_NEXT_WINDOW`
- `ENABLE_ACTION`
- `RESERVE_DENY`
- `LANE_CONTROL`
- `TRADE_SETUP`

`objective_targets` may still exist as a late-bound concrete field inside Tier 0 or Tier 2 execution, but it should not be the primary strategic abstraction.

### PathWitness Contract (Required)

Full path means a compact witness, not a high-resolution trace.

ModelPathWitness primitives:
- `translate`
- `pivot`
- `floor_transition`

Required invariants:
- the path is contiguous and ordered
- the first pose matches the start pose
- the final pose matches the chosen endpoint
- segment length respects the active legality mode
- layer changes occur only on valid transitions

Required validations:
- continuous forbidden-volume intersection checks
- continuous impassable-terrain checks
- enemy-pass-through constraints
- distance accounting using the active rules bundle
- pivot accounting according to the active rules bundle

### Candidate Metadata for Movement

Movement candidates should include both geometry facts and semantic projections, for example:

- `screen_coverage_cells`
- `coherency_min_degree`
- `threat_exposure_score`
- `projected_control_delta`
- `projected_score_delta_next_window`
- `projected_deny_delta_next_window`
- `cover_delta`
- `lane_control_delta`
- `projected_action_enablement_delta`

### Tight Clearance, Orientation, and Continuous Validation

Retain the current continuous-validation posture:

- segment and volume intersections, not endpoint sampling
- adaptive segment length in tight intervals
- orientation-sensitive constraints where required
- pivot accounting once per move when the current rules bundle requires it

## Stratagems and Abilities as Tools

Keep the shared tool-descriptor approach, but make it part of the larger portability story.

- One shared policy may be conditioned on faction, detachment, and toolset.
- Tool descriptors must be serializable, patchable, and consumable by the rules-conditioned encoder.
- Tool semantics should be recomputed under the active bundle and surfaced through candidate metadata and context fields.

### Tool Descriptor Schema (Required)

Minimum fields:

- timing windows
- target constraints and legality hooks
- cost
- effect category and parameters
- duration
- expiry conditions
- semantic tags describing whether the tool primarily affects:
  - score generation
  - denial
  - damage spike
  - durability
  - movement
  - action enablement
  - reserve interaction

## Compute Budget and Time Manager

Time management is a hard subsystem, not a later optimization.

- per decision-type time caps
- per unit or task priority multipliers
- anytime behavior that returns the best current candidate if time expires
- time budgets logged with decisions for profiling and retraining
- fallback policies that remain fully legal and replay-safe

Time-budget features should also be visible to Tier 3 so the model learns to behave appropriately under bounded search.

## State Space Design

### Representation Split

Use three representation paths with late fusion:

- Invariant board encoder:
  - units
  - distances
  - occupancy
  - generic threat
  - generic control geometry

- Rules-conditioned encoder:
  - mission descriptors
  - terrain descriptors
  - objective descriptors
  - deployment descriptors
  - tool descriptors
  - scoring-window state

- Candidate encoder:
  - solver-generated action features
  - semantic candidate metadata
  - time-budget and compute-tier features

Tier heads should fuse these representations late. Prefer small adapters or LoRA-style patches on the rules-conditioned path when rules bundles change.

### Node Types

Invariant-heavy:
- unit nodes
- region nodes
- generic control nodes
- phase and resource nodes

Rules-conditioned:
- score-source nodes
- objective descriptor nodes
- terrain descriptor nodes
- deployment nodes
- tool nodes
- scoring-window nodes

### Edge Types

Invariant-heavy:
- unit-to-unit distance and threat edges
- unit-to-region occupancy and reachability
- generic line-of-sight feasibility

Rules-conditioned:
- unit-to-score-source influence
- unit-to-terrain traversal semantics
- unit-to-action-site eligibility
- tool-to-unit legality and effect edges

## Training Plan

### Stage 0: Heuristic Baselines

- implement baseline bots for scoring, killing, denial, trading, and staging
- use them for seed data and early opponents

### Stage 0.5: Descriptor Compiler and Replay-to-Relabel

This stage must be complete before serious model investment.

- compile mission, objective, terrain, deployment, and tool descriptors
- validate descriptor serialization and deterministic loading
- regenerate semantic candidate features under alternate rules bundles
- validate relabel quality on regression packs
- build a semantic diff classifier that scopes the smallest necessary retraining surface

### Stage 1: Imitation Learning

- train Tier 3 executors using human, heuristic, and search-generated demonstrations
- train on candidate semantics, not just candidate identity
- keep legality fully in Tier 0

### Stage 2: HRL Self-Play

- freeze Tier 3 initially
- train Tier 1 and Tier 2 with VP-delta reward and shaping
- condition on rules bundles explicitly

### Stage 3: Limited Lookahead

- use shallow rollouts and bounded lookahead for critical decision points
- ensure lookahead consumes active-bundle semantics and not stale assumptions

### Stage 4: Adapter and Head Fine-Tuning

- prefer version adapters and small heads before touching invariant encoders
- use relabeled replay data wherever possible
- rehearse against prior regression packs to avoid forgetting

### Stage 5: Broader Joint Fine-Tuning

- only escalate to broader unfreezing when smaller transfer methods are insufficient
- preserve regression suites across old and new bundles

## Patch and Version Handling

Every training run, replay, and dataset manifest must be tagged with the atomic rules ids and the convenience `rules_bundle_id`.

### Semantic Diff Classifier

The patch classifier should identify which semantic surfaces changed:

- legality surface
- geometry / movement / visibility surface
- scoring surface
- resource economy / tool surface
- combat surface
- deployment / reserve surface
- entity taxonomy surface

This classifier determines what needs to be:
- recompiled
- relabeled
- fine-tuned
- left frozen

### Minimal Transfer Policy

- Do not retrain legality. Legality lives in Tier 0.
- Do not broadly retrain on points-only changes unless in-game value calibration materially shifts.
- Do not make Tier 1 dependent on objective ids when a more abstract score-source representation exists.
- Do not let the movement model memorize terrain semantics that the engine can derive and patch directly.

### Freeze / Retrain Matrix

#### Points-only or list-building change

Primary action:
- update muster evaluator
- recalibrate value estimates if needed

Usually retrain:
- none or small value calibration head

Usually freeze:
- invariant encoder
- movement executor
- most strategic heads

#### Datasheet or combat-profile change

Primary action:
- recompute threat and trade features

Usually retrain:
- targeting and trade-evaluation heads if needed

Usually freeze:
- movement legality
- most Tier 1 scoring logic

#### Tool or resource economy change

Primary action:
- update tool descriptors and legality hooks

Usually retrain:
- resource and timing heads
- optional Tier 2 posture head

Usually freeze:
- movement
- invariant board encoder

#### Mission scoring or objective-function change

Primary action:
- rebuild mission and objective descriptors
- relabel replays under the new scoring surface

Usually retrain:
- Tier 1 planner heads
- Tier 2 binding heads

Usually freeze:
- invariant encoder
- movement legality
- most geometry-specific heads

#### Terrain semantics or traversal change

Primary action:
- update terrain descriptors and movement legality
- regenerate movement candidate metadata

Usually retrain:
- movement and positioning heads only if semantic rank ordering changes materially

Usually freeze:
- strategic heads unless terrain changes also alter scoring surfaces

#### Deployment or reserve change

Primary action:
- update deployment descriptors and reserve-lane affordances

Usually retrain:
- reserve-denial and early-turn staging heads

Usually freeze:
- late-game micro heads unless candidates change materially

#### New edition

Primary action:
- compile a new descriptor bundle
- run cross-version replay-to-relabel
- train version adapters and rule-conditioned heads first

Escalation:
- broaden retraining only if adapter transfer is insufficient

A new edition is treated as a descriptor and adapter migration first, not an automatic full restart.

## Cross-Version Replay-to-Relabel Pipeline

This pipeline is required before serious model investment.

1. Load historical DecisionRecords and state snapshots.
2. Reconstruct the board state under the original rules bundle.
3. Compile a new target rules bundle.
4. Recompute descriptors, semantic affordances, legal candidates, and candidate metadata under the new bundle.
5. Mark whether the original chosen action:
   - remains legal and semantically comparable
   - remains legal but changes value
   - becomes illegal and needs mapping
   - becomes unrepresentable under the new bundle
6. Distill updated behavior into small adapters or heads before attempting broad retraining.
7. Run regression suites under both old and new bundles.

This is the preferred path for mission-pack churn, terrain-pack churn, and edition migration.

## Success Criteria

### Engineering

- deterministic replay from action logs
- all decisions pass through the Decision API
- movement solver outputs legal placements with full path witnesses
- bounded runtime per tier
- rules descriptors compile deterministically
- cross-version relabeling produces auditable outputs

### AI

- Tier 3 achieves competent play via imitation learning
- Tier 1 and Tier 2 improve VP delta via self-play
- patch updates allow localized adaptation without breaking legality
- mission and terrain changes can often be handled by descriptor recompilation plus small transfer updates
- edition transitions start with descriptor migration and adapter transfer rather than broad restart

## Notes and Principles

- Legality is enforced by the engine, not by the policy.
- Keep interfaces stable across rules bundles.
- Prefer incremental, testable PRs that preserve determinism.
- Use solver outputs to handle geometry; policies handle tradeoffs.
- Keep mission, objective, terrain, deployment, and tool semantics patchable as data.
- Recompute semantic candidate features under the current bundle rather than reusing stale policy assumptions.

## ML Gate Criteria (Must Be Closed Before PR 15)

- Training data specification finalized:
  - demo formats
  - storage layout
  - minimum dataset sizes for Tier 3 pretraining
- Movement solver worst-case limits finalized:
  - maximum runtime budget
  - fallback behavior documented and enforced by tests
- Rules-bundle tagging finalized:
  - exact atomic ids
  - storage locations in logs and snapshots
  - replay reproducibility tests
- Descriptor compiler complete for:
  - mission
  - objective
  - terrain
  - deployment
  - tools
- StateBlob finalized for semantic relabeling:
  - terrain
  - mission_state
  - scoring_surfaces
  - control_regions
  - rules_bundle
- Candidate metadata generator finalized for:
  - movement
  - targeting
  - charges
  - fight activations
  - tool decisions
- Cross-version replay-to-relabel CLI exists and passes regression tests.
- Model version-adapter boundary is finalized.
- Semantic diff classifier is finalized and wired into retraining scope selection.

## Pre-ML PR Tracker (Living)

This section is the authoritative tracker for remaining AI reintroduction work before ML-library onboarding.
As of March 2, 2026, the foundational portability PR set is complete on `dev`.

### Completed Foundation PRs

| PR ID | Scope | Status | Primary Artifacts |
| --- | --- | --- | --- |
| `PR-AI-001` | Rules-bundle decomposition and DecisionRecord schema support | DONE | `docs/DECISION_RECORD_SCHEMA.json`, `docs/DECISION_RECORD_TELEMETRY.md` |
| `PR-AI-002` | StateBlob portability top-level fields | DONE | `docs/STATE_BLOB_SCHEMA.md` |
| `PR-AI-003` | Tier 1 and Tier 2 opportunity-first migration | DONE | `docs/TIER1_PLAN_SCHEMA.md`, `docs/TIER2_ORCHESTRATION.md` |
| `PR-AI-004` | Descriptor compiler (mission/objective/terrain/deployment/tools) | DONE | `docs/RULES_DESCRIPTOR_COMPILER.md`, `tests/test_descriptor_compiler.py` |
| `PR-AI-005` | Cross-version replay-to-relabel pipeline and CLI | DONE | `docs/DECISION_RECORD_REPLAY.md`, `scripts/relabel_decision_records.py`, `tests/test_relabel_pipeline.py` |
| `PR-AI-006` | Semantic diff classifier and retraining-scope selector | DONE | `docs/SEMANTIC_DIFF_CLASSIFIER.md`, `scripts/classify_semantic_diff.py`, `tests/test_semantic_diff.py` |
| `PR-AI-007` | Semantic candidate metadata normalization across decision types | DONE | `src/warhammer40k_ai/engine/candidate_semantics.py`, `tests/test_candidate_semantic_metadata.py` |
| `PR-AI-008` | Version-adapter boundary contract in decision context | DONE | `docs/VERSION_ADAPTER_BOUNDARY.md`, `tests/test_version_adapter_boundary.py` |
| `PR-AI-009` | Training-data manifest specification and CLI checks | DONE | `docs/TRAINING_DATA_SPEC.md`, `scripts/build_training_manifest.py`, `tests/test_training_manifest.py` |
| `PR-AI-010` | Network/save-load rules-bundle contract alignment | DONE | `docs/NETWORK_SAVELOAD_DESIGN.md` |

### Remaining Required PRs Before PR-AI-015

| PR ID | Scope | Status | Why Open | Exit Criteria |
| --- | --- | --- | --- | --- |
| `PR-AI-011` | Movement solver worst-case budget + fallback hardening | DONE | Closed on March 2, 2026: movement solver over-budget and in-budget runtime behavior is now locked by explicit regression assertions. | Enforced by `tests/test_movement_solver_budget.py` and documented in `docs/TIME_MANAGER_POLICY.md`. |
| `PR-AI-012` | Rules-bundle reproducibility matrix across snapshot/replay/state blob | DONE | Closed on March 2, 2026: dedicated matrix regression coverage now locks rules-bundle stability across record logging, snapshot save/load, state blob, and strict replay. | Enforced by `tests/test_rules_bundle_reproducibility_matrix.py` and documented in `docs/DECISION_RECORD_REPLAY.md`. |
| `PR-AI-013` | Semantic candidate metadata v2 (computed, not heuristic defaults) | DONE | Closed on March 3, 2026: semantic metadata now uses deterministic decision-specific projections (movement, targeting, charge, fight, tool) and relabel recomputes those projections under target bundles. | Enforced by `tests/test_candidate_semantic_metadata.py` and `tests/test_relabel_pipeline.py` value-shift regressions. |
| `PR-AI-014` | Training-data gate profile finalization | DONE | Closed on March 3, 2026: canonical `pre_ml_baseline_v1` gate profile is now a normative artifact in training-data docs and manifest output, with explicit profile compliance checks for minimum record volume and required semantic/relabel coverage. | Enforced by `src/warhammer40k_ai/engine/training_manifest.py`, `scripts/build_training_manifest.py --enforce-gate-profile`, and regression coverage in `tests/test_training_manifest.py` / `tests/test_training_manifest_cli.py`. |
| `PR-AI-015` | ML dependency onboarding boundary PR | BLOCKED | By definition this PR must only land after all pre-ML gates are closed. | All items in `## ML Gate Criteria (Must Be Closed Before PR 15)` are explicitly marked closed in this tracker, with passing regression evidence. |

Reopen policy:
- If any item in `## ML Gate Criteria (Must Be Closed Before PR 15)` regresses, add a new `PR-AI-0XX` row here and block `PR-AI-015` until resolved.

## Related Documents To Update In Lockstep

- `docs/TIER1_PLAN_SCHEMA.md`
  - move from objective-id planning to opportunity and scoring-window planning

- `docs/STATE_BLOB_SCHEMA.md`
  - add `rules_bundle`, `mission_state`, `deployment_state`, `terrain`, `scoring_surfaces`, and `control_regions`

- `docs/DECISION_RECORD_SCHEMA.json`
  - add rules-bundle decomposition and relabel support fields

- movement-intent schema docs
  - replace `objective_targets` as the primary strategic abstraction
