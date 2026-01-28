# Bringing Back AI (HRL + Training Plan)

This document consolidates the HRL design and training plan for reintroducing Artificial Intelligence into the Warhammer 40,000 game engine. It is based on the provided summaries and is structured to be implemented over incremental PRs while preserving determinism and rules accuracy.

## Purpose

- Define the AI architecture and interfaces needed to support Warhammer 40,000 matched play.
- Provide a training and retraining plan that is resilient to points updates, dataslates, errata, and future editions.
- Specify the engineering roadmap to make AI integration testable and incremental.

## Target Environment

- Matched Play, Chapter Approved 2025-2026.
- 2000 points.
- Frequent points and rules updates.
- Likely future edition change (10e to 11e).

## Primary Objective

- Maximize VP delta (your VP minus opponent VP) over 5 rounds within tournament time constraints.
- Optimize for both VP gain and VP denial.

## Key Constraints

- Tournament time budget: roughly 75 minutes per player.
- Movement has the highest branching factor and strict legality requirements.
- The AI must be anytime and computationally bounded.

## HRL Architecture

### Tier 0: Ruleset and Action Masking (Non-learned)

- Load ruleset version and points package.
- Enumerate decision points and legal candidate actions.
- Enforce legality in the engine, not in the policy.

### Tier 1: Strategic Planner (Learned)

- Outputs a Plan at the start of each round or turn.
- Plan includes primary objectives, denial targets, secondary posture, risk posture, CP budget posture, and unit priority tiers.

### Tier 2: Tactical Orchestrator (Learned)

- Converts the Plan into unit-level tasks and resource posture.
- Assigns intents such as score, deny, screen, stage, trade, protect, bait.
- Allocates compute budgets based on unit priority tiers.

### Tier 3: Micro-Executors (Learned + Solver)

- Executes movement, target selection, charges, and fight activation order.
- Uses solver-generated legal candidates and learned scoring.

## Decision API Contract

All player decisions must use a unified decision interface exposed by the engine.

### Decision Schema

```
class Decision:
    decision_id: str
    decision_type: str  # MOVE_UNIT, SELECT_TARGETS, DECLARE_CHARGE, PLAY_STRATAGEM, ...
    actor_player_id: str
    context: dict
    candidates: list[CandidateAction]
    mask: list[bool]
```

### CandidateAction Schema

```
class CandidateAction:
    action_id: str
    params: dict
    metadata: dict
```

- Candidate enumeration is intent-driven and solver-backed.
- The policy selects among legal candidates instead of generating raw coordinates.

## Human Gameplay Telemetry & Learning

Human games are a first-class data source for bootstrapping and realism. The telemetry contract must align with the Decision API so human actions map to the same candidate-based policies used by AI.

### DecisionRecord Schema (Minimum)

See [DECISION_RECORD_SCHEMA.json](DECISION_RECORD_SCHEMA.json) for the canonical JSON schema.

Each decision (human or AI) emits a DecisionRecord with:

- Identification and determinism: `game_id`, `turn_id`, `phase`, `decision_id`, `decision_type`,
  `ruleset_id`, `dataslate_id`, `points_id`, `global_seed`, `decision_seed`.
- Observation: canonicalized snapshot or replayable delta, stored as:
  `omniscient_state` and `player_obs_state(player_id)`.
- Candidate set: full `candidates` list and `mask` at decision time.
  Each CandidateAction includes stable `action_id`/hash, `params`, and `metadata`
  (e.g., solver metrics, time spent, threat estimates).
- Choice: `chosen_action_id` and wall-clock time used.
- Outcome: immediate deltas (VP, CP, destroyed units, etc.) and end-of-turn/end-of-game returns.

### HumanActionCandidate Injection (Required)

Humans will often select actions not present in the solver's top-K candidates. To keep training aligned:

- Always generate the solver candidate set for the decision.
- When a human commits an action, validate it and compute required PathWitness artifacts.
- If the action is not already in the candidate set, append a `HumanActionCandidate` with
  the exact params and witnesses, then mark it as the chosen action.

This preserves a candidate-based dataset even for freeform UI actions.

### Determinism and Reproducibility

- If candidate generation is stochastic, record `decision_seed` and the full candidate list.
- Replayers must be able to reconstruct the exact candidate set and outcome for training.

### Invalid Attempt Telemetry (Optional but Recommended)

When a human attempts an illegal action and the UI rejects it:

- Log the attempted action as an invalid record with the rejection reason.
- This supports later UI explainability and proposal models.

### Usage by Tier

- Tier 3: primary supervised source (learning-to-rank over candidates for movement/targets/charges/fights).
- Tier 2: optional auxiliary supervision (infer unit roles and CP posture from observed actions).
- Tier 1: keep RL/self-play primary; optionally add self-supervised prediction targets.

## Movement System Design

- Movement uses intent, constrained optimization, and full path witnesses.
- Full path witnesses are required to ensure rules-faithful legality.
- Solver output includes per-model endpoints, path witnesses, and legality proof metadata.

### MovementIntent Schema (Required)

MovementIntent is the compact, expressive input that drives solver candidate generation.

```
class MovementIntent:
    objective_targets: list[str]            # objective_id or region_id
    screen_deny_targets: list[str]          # region_id or lane_id
    weights: dict                           # screen_coverage, coherency, threat_avoid, obj_proximity
    anchors: dict[str, str]                 # {model_id: region_id}, optional, 0-3 anchors
    constraint_toggles: dict                # avoid_los_to, avoid_threat_range_of, keep_in_cover, etc.
```

### PathWitness Contract (Required)

Full path means a compact witness (polyline + events), not a high-resolution trace.

ModelPathWitness primitives: `translate`, `pivot`, `floor_transition`.

Required fields (per primitive):
- `from_pose`, `to_pose`, `theta`, `pivot_cost_applied`, `layer_id`

Required invariants:
- Path is contiguous and ordered; first `from_pose` equals starting pose; last `to_pose` equals endpoint.
- Translation segment length <= max segment length for the current clearance mode.
- `layer_id` changes only on `floor_transition` primitives.

Required validations per translation segment:
- Continuous intersection with forbidden Engagement Range regions when applicable.
- Continuous intersection with impassable terrain boundaries given traversal archetype.
- Enemy model pass-through constraints (movement-type dependent).

Required distance accounting:
- Translation distance computed per segment using the active ruleset's distance mode.
- Pivot penalty applied once per move when any pivot occurs (`pivot_cost_applied` on first pivot only).

### Path-Time Legality Constraints (Continuous)

- Cannot enter Engagement Range at any point during Normal/Advance moves unless the mover is explicitly permitted.
- Cannot pass through enemy models unless the movement type explicitly allows it.
- Traversal archetype (breach, fly, walker, etc.) determines which terrain volumes are impassable.

### Corridor and Segment Witnesses

- CorridorWitness per base profile group per unit move.
- ModelPathWitness per model with translation segments, pivots, and floor transitions.
- Continuous segment intersection checks, not endpoint sampling.

### Segment Granularity

- Default max segment length: 0.5 inches.
- Tight or orientation-sensitive: 0.25 inches.
- Extreme escalation: 0.1 inches.

### Tight Clearance Detection

- Elliptical bases: tight if b <= clearance < a.
- Rectangular hulls: tight if w <= clearance < sqrt(l^2 + w^2).
- Tight intervals trigger stricter segment length and pivot constraints.

In tight intervals, orientation is constrained:
- Apply yaw-band constraints relative to local corridor direction.
- Allow pivots only if resulting yaw remains within the admissible band.
- Escalate to finer discretization only when clearance is near r_in.

### Pivot Handling

- Pivot penalty applies once if any pivot occurs.
- Solver avoids pivots unless needed for clearance or intent.

## Stratagems and Abilities as Tools

- One shared policy conditioned on faction, detachment, and toolset.
- Toolset includes stratagems, enhancements, and once-per-battle rules.
- Optional adapters or MoE gating for detachment specialization.

### Tool Descriptor Schema (Required)

Tools are represented as structured effect descriptors to enable generalization and patch resiliency.

Minimum fields:
- Timing window(s).
- Target constraints and legality hooks.
- Cost (CP, once-per-battle, etc.).
- Effect category + parameters (modify hit/wound/save/damage/move/OC/etc.).
- Duration and expiry conditions.

## Compute Budget / Time Manager

Time management is a concrete subsystem, not an open question.

- Per decision type time caps (movement, shooting allocation, charge planning, etc.).
- Per unit priority multipliers (P0/P1/P2).
- Anytime behavior: return best candidate found so far and fall back to simpler intent if time expires.
- Time budgets are logged with decisions for profiling and retraining.

## Training Plan

### Stage 0: Heuristic Baselines

- Implement baseline bots for scoring, killing, denial, and trading.
- Use for imitation learning seed data and early opponents.

### Stage 1: Imitation Learning

- Train Tier 3 executors using heuristic and search-generated demonstrations.

### Stage 2: HRL Self-Play

- Freeze Tier 3 initially.
- Train Tier 1 and Tier 2 with VP delta reward and shaping.

### Stage 3: Limited Lookahead

- Use shallow rollouts and bounded MCTS-like evaluation for critical decision points.

### Stage 4: Joint Fine-Tuning

- Gradually unfreeze Tier 3.
- Use regression scenarios to prevent degradation.

## Patch and Version Handling

- Every training run is tagged with ruleset_id, dataslate_id, and points_id.
- Patch diff classifier determines retraining scope.

### Example Retraining Map

- Points-only update: fine-tune value head and Tier 1 planner.
- Dataslate weapon tweaks: fine-tune threat and targeting executor.
- Stratagem economy changes: retrain Tier 2 resource head.
- Mission scoring change: retrain Tier 1 planner.
- Movement rules change: update engine and retrain movement executor.
- New edition: rebuild adapters and executors, transfer high-level VP concepts.

### Worked Examples (Freeze vs Retrain)

- Movement rules change (e.g., traversal or ER path constraints update): update engine legality + movement solver, retrain Tier 3 movement executor; freeze Tier 1/2; use rehearsal on prior movement regression suite.
- Tool change (e.g., stratagem timing/target/cost update): update tool descriptor and legality hooks, fine-tune Tier 2 resource head; freeze movement executor; add targeted sims covering the updated tool window and target constraints.

## Army Muster System

- Separate agent from in-game AI.
- Use roster search plus learned evaluator.
- Output roster, detachment, enhancements, and optional playbook prior.

## Runtime Control Loop

1. Tier 1 emits Plan.
2. Tier 2 assigns unit tasks and resource posture.
3. Tier 0 enumerates legal candidates and masks.
4. Tier 3 selects and executes candidates.
5. Log all decisions and outcomes for training.

## Engineering Roadmap (Incremental PRs)

1. Ruleset/version plumbing and deterministic replay.
2. Unified Decision API with action masking.
3. DecisionRecord logging + dual-view observation + HumanActionCandidate injection + deterministic replayer.
4. State encoding foundation with canonical perspectives.
5. Tier 1 Plan schema integrated into decision contexts.
6. Compute Budget / Time Manager (caps, multipliers, anytime fallback).
7. MovementIntent schema and solver hooks.
8. PathWitness artifacts with continuous validation.
9. Tight clearance detection and pivot constraints.
10. Tier 2 orchestration scaffolding.
11. Training harness with league self-play.
12. Army muster generator and evaluator prototype.

## ML Framework Recommendation

### Primary Framework

- PyTorch is recommended for flexibility, debuggability, and integration with the Python rules engine.

### Supporting Libraries

- TorchRL for buffers and RL plumbing.
- PyTorch Geometric or DGL for graph encoders.
- Ray for distributed rollouts and league training.
- Hydra for configuration management.
- Weights & Biases for experiment tracking.

### Alternatives

- JAX may offer throughput but benefits require heavy environment refactor.
- TensorFlow offers fewer practical advantages for this design.

## State Space Design

### Shared Encoder

- One global graph encoder for all tiers.
- Tier-specific heads consume pooled global embeddings or decision queries.

### Node Types

- Unit nodes: position, wounds, OC, mobility, combat summary, points cost.
- Objective nodes: control state, scoring relevance.
- Terrain nodes: footprint, floors, passability.
- Tool nodes: stratagems and enhancements with constraints and costs.
- Game-phase node: round, phase, CP, VP, secondary state.

### Edge Types

- Unit-to-unit: distance bins, engagement, LOS feasibility, threat overlap.
- Unit-to-objective: control and contest features.
- Unit-to-terrain: inside footprint, blocked-by, passability.
- Aura/support edges: derived, not learned.

### Tier-Specific Views

- Tier 1: coarse board control, scoring potentials, resource posture, force health.
- Tier 2: unit granularity, threat overlap, phase action economy, tool availability.
- Tier 3: global embedding plus solver-generated candidate features.

## Success Criteria

### Engineering

- Deterministic replay from action logs.
- All decisions pass through the Decision API.
- Movement solver outputs legal placements with full path witnesses.
- Bounded runtime per Plan tier.

### AI

- Tier 3 competent play via imitation learning.
- Tier 1 and Tier 2 improve VP delta via self-play.
- Patch updates allow localized retraining without breaking legality.

## Notes and Principles

- Legality is enforced by the engine, not by the policy.
- Keep interfaces stable across ruleset versions.
- Prefer incremental, testable PRs that preserve determinism.
- Use solver outputs to handle geometry; policies handle tradeoffs.

## Open Questions and Decisions Needed

### Resolved

- Painted bonus always applies. Reward normalization assumes 90 effective VP.
- Every engine decision must route through the unified Decision API with deterministic request/response mapping. Gaps must be corrected.

### Open

- Training data specification: define heuristic demo formats, storage, and minimum dataset sizes for Tier 3 pretraining.
- Movement solver worst-case limits: specify maximum allowed runtime and fallback behavior when dense terrain causes solver escalation.
- Ruleset/version tagging schema: define exact fields and where they are stored in logs and snapshots for reproducible training/evaluation.
