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

#### Mapping to Decision API Contract

DecisionRecord is a telemetry superset of the Decision API:

- `decision_id`, `decision_type`, `candidates`, and `mask` mirror the Decision object.
- `chosen_action_id` mirrors the selected `CandidateAction.action_id`.
- Telemetry-only fields add replay and learning context: state snapshots, RNG seeds, wall-clock timing, and outcomes.

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

## Examples (Tiered Contracts + Telemetry)

Below are four realistic examples that mirror the contracts in this document and the telemetry constraints in `DECISION_RECORD_SCHEMA.json`.

Tier overview reference:
- Tier 0 = ruleset loader + decision/candidate enumeration + action masking + time manager
- Tier 1 = strategic Plan (explicit)
- Tier 2 = per-unit tasks + per-unit MovementIntent + compute budgets
- Tier 3 = micro-executor that scores/selects among candidates
- Tier 4 = telemetry + learner consuming DecisionRecord (and HumanActionCandidate injection)

### Example 1 - Start of Turn: Tier-1 Plan -> Tier-2 Tasks -> Tier-0 Budgeting

Situation (high-level): Round 2, Player P1's turn, Command phase. P1 is slightly ahead on VP; wants to hold two objectives, screen a reserve lane, and avoid spending CP offensively this turn.

Tier 0 -> Tier 1: PLAN_REQUEST (state summary)

```yaml
msg:
  from: tier0.engine
  to: tier1.strategic_planner
  type: PLAN_REQUEST
  payload:
    game_id: "g_2026_01_28_0007"
    ruleset_id: "core_rules_24.09+updates_v1.8_rc1.7"
    dataslate_id: "balance_dataslate_v3.3"
    points_id: "mfm_v3.8"
    round: 2
    active_player: "P1"
    phase: "COMMAND"
    clock:
      p1_time_remaining_ms: 3680000   # ~61.3 min left
      p2_time_remaining_ms: 3725000
    score:
      vp: { P1: 18, P2: 14 }
      primary_last_round: { P1: 5, P2: 10 }
    resources:
      cp: { P1: 2, P2: 3 }
      once_per_battle_available:
        P1: ["unit:P1_U12_teleport", "unit:P1_U3_heroic_intervention"]
    board_summary:
      objectives:
        - { id: "O1_home_P1", controlled_by: "P1", contestable_next_round: false }
        - { id: "O2_mid_left", controlled_by: "P2", contestable_next_round: true }
        - { id: "O3_mid_right", controlled_by: "None", contestable_next_round: true }
      opponent_threats:
        - { unit_id: "P2_U7_melee_blob", threat_type: "charge", threat_range_in: 18 }
        - { unit_id: "P2_U2_long_guns", threat_type: "shooting", threat_range_in: 36 }
    notes:
      - "Reserve denial matters: opponent has 2 units in reserves"
```

Tier 1 -> Tier 2: PLAN (explicit output)

```yaml
msg:
  from: tier1.strategic_planner
  to: tier2.tactical_orchestrator
  type: PLAN
  payload:
    plan_id: "plan_r2_p1_t1"
    horizon:
      current_round: 2
      lookahead_rounds: 2
    primary_plan:
      hold_objectives: ["O1_home_P1", "O3_mid_right"]
      contest_objectives: ["O2_mid_left"]
      deny_opponent_primary_next_round: true
    secondary_posture:
      mode: "TACTICAL"
      discard_policy: "discard_if_p_success_lt_0.35"
    resource_posture:
      cp_budget:
        reserve_for_defense: 2
        max_offensive_spend_this_turn: 0
      once_per_battle_policy:
        "unit:P1_U12_teleport": "hold_for_turn3_or_when_flip_possible"
    risk_posture:
      variance: "LOW"      # ahead -> reduce variance
      aggression: "MEDIUM" # still contest mid-left
    unit_priority_tiers:
      P0: ["P1_U8_fast_screeners", "P1_U4_primary_flipper"]
      P1: ["P1_U2_mid_holder", "P1_U6_fire_support"]
      P2: ["P1_U1_home_holder"]
```

Tier 2 -> Tier 0: TASK_ASSIGNMENTS + MovementIntents + compute budgets

```yaml
msg:
  from: tier2.tactical_orchestrator
  to: tier0.engine
  type: TASK_ASSIGNMENTS
  payload:
    plan_id: "plan_r2_p1_t1"
    unit_tasks:
      P1_U8_fast_screeners:
        task: "SCREEN"
        subtask: "deny_reserves_lane_L3"
        compute_tier: "P0"
        movement_intent:
          objective_targets: ["O3_mid_right"]
          screen_deny_targets: ["lane_L3_backfield_gap"]
          weights:
            screen_coverage: 0.55
            coherency: 0.25
            threat_avoid: 0.15
            obj_proximity: 0.05
          anchors:
            m0: "lane_L3_backfield_gap"   # lead model anchors the deny line
          constraint_toggles:
            avoid_threat_range_of: ["P2_U7_melee_blob"]
            keep_in_cover: true

      P1_U4_primary_flipper:
        task: "CONTEST"
        subtask: "flip_O2_mid_left"
        compute_tier: "P0"
        movement_intent:
          objective_targets: ["O2_mid_left"]
          screen_deny_targets: []
          weights:
            screen_coverage: 0.05
            coherency: 0.20
            threat_avoid: 0.35
            obj_proximity: 0.40
          anchors: {}
          constraint_toggles:
            avoid_los_to: ["P2_U2_long_guns"]

    time_manager_policy:
      decision_caps_ms:
        MOVE_UNIT: 220
        SELECT_TARGETS: 140
        PLAY_STRATAGEM: 60
        DECLARE_CHARGE: 120
      tier_multipliers:
        P0: 1.8
        P1: 1.0
        P2: 0.5
```

What this shows:
- Tier 1 sets global intent (VP/deny/CP/risk posture).
- Tier 2 turns that into unit intents and compute-tier budgets.
- Tier 0 receives both and uses them to parameterize candidate generation and enforce time caps.

### Example 2 - Movement: Tier-2 MovementIntent -> Tier-0 candidates -> Tier-3 selects -> Tier-4 logs

Situation (high-level): Movement phase. Unit P1_U8_fast_screeners has oval bases and must thread a gap near ruins. The move is not a charge, so the path cannot enter Engagement Range during the move. The solver detects a tight clearance interval (orientation-sensitive) and generates candidates accordingly.

Tier 0 -> Tier 3: MOVE_UNIT Decision + candidates

```yaml
msg:
  from: tier0.engine
  to: tier3.micro_executor
  type: DECISION
  payload:
    decision_id: "d_r2_p1_move_P1_U8"
    decision_type: "MOVE_UNIT"
    actor_player_id: "P1"
    context:
      phase: "MOVEMENT"
      plan_id: "plan_r2_p1_t1"
      unit_id: "P1_U8_fast_screeners"
      task: "SCREEN"
      compute_tier: "P0"
      time_budget_ms: 396     # 220ms cap * 1.8 P0 multiplier
      movement_intent:
        objective_targets: ["O3_mid_right"]
        screen_deny_targets: ["lane_L3_backfield_gap"]
        weights: {screen_coverage: 0.55, coherency: 0.25, threat_avoid: 0.15, obj_proximity: 0.05}
        anchors: {m0: "lane_L3_backfield_gap"}
        constraint_toggles: {avoid_threat_range_of: ["P2_U7_melee_blob"], keep_in_cover: true}

    candidates:
      - action_id: "move_P1_U8_cand_00_noop"
        params:
          unit_id: "P1_U8_fast_screeners"
          placement_ref: "placement://noop"
          path_witness_ref: "path://noop"
        metadata:
          solver_ms: 1
          screen_coverage_cells: 42
          coherency_min_degree: 3
          threat_exposure_score: 0.18
          pivot_penalty_used: 0.0
          tight_clearance: false
          corridor_witness_ref: "corr://none"

      - action_id: "move_P1_U8_cand_01_wide_safe"
        params:
          unit_id: "P1_U8_fast_screeners"
          placement_ref: "placement://P1_U8/01"
          path_witness_ref: "path://P1_U8/01"
        metadata:
          solver_ms: 58
          screen_coverage_cells: 96
          coherency_min_degree: 2
          threat_exposure_score: 0.22
          pivot_penalty_used: 1.0
          tight_clearance: false
          corridor_witness_ref: "corr://oval_60x35/routeA"

      - action_id: "move_P1_U8_cand_02_thread_ruins_gap"
        params:
          unit_id: "P1_U8_fast_screeners"
          placement_ref: "placement://P1_U8/02"
          path_witness_ref: "path://P1_U8/02"
        metadata:
          solver_ms: 143
          screen_coverage_cells: 141
          coherency_min_degree: 2
          threat_exposure_score: 0.19
          pivot_penalty_used: 1.0
          tight_clearance: true
          corridor_witness_ref: "corr://oval_60x35/routeB"
          segment_max_in: 0.25

    mask: [true, true, true]
```

Tier 3 -> Tier 0: selection (candidate scoring / chosen action)

```yaml
msg:
  from: tier3.micro_executor
  to: tier0.engine
  type: CHOICE
  payload:
    decision_id: "d_r2_p1_move_P1_U8"
    chosen_action_id: "move_P1_U8_cand_02_thread_ruins_gap"
    score_breakdown:
      move_P1_U8_cand_00_noop: {total: 0.31, screen: 0.18, coherency: 0.10, threat: 0.03}
      move_P1_U8_cand_01_wide_safe: {total: 0.67, screen: 0.39, coherency: 0.18, threat: 0.10}
      move_P1_U8_cand_02_thread_ruins_gap: {total: 0.79, screen: 0.55, coherency: 0.16, threat: 0.08}
    notes:
      - "Tight clearance true but threat exposure lowest among high-screen options"
      - "Pivot penalty used once; acceptable under current move allowance"
```

Tier 4: emitted DecisionRecord (valid JSON per schema)

```json
{
  "schema_version": "1.0.0",
  "game_id": "g_2026_01_28_0007",
  "turn_id": 2,
  "phase": "MOVEMENT",
  "decision_id": "d_r2_p1_move_P1_U8",
  "decision_type": "MOVE_UNIT",
  "ruleset_id": "core_rules_24.09+updates_v1.8_rc1.7",
  "dataslate_id": "balance_dataslate_v3.3",
  "points_id": "mfm_v3.8",
  "global_seed": 4128891,
  "decision_seed": 99312044,
  "omniscient_state": {
    "round": 2,
    "active_player": "P1",
    "vp": { "P1": 18, "P2": 14 },
    "cp": { "P1": 2, "P2": 3 },
    "active_unit_id": "P1_U8_fast_screeners"
  },
  "player_obs_state": {
    "P1": { "round": 2, "phase": "MOVEMENT", "my_cp": 2, "my_vp": 18 },
    "P2": { "round": 2, "phase": "MOVEMENT", "my_cp": 3, "my_vp": 14 }
  },
  "candidates": [
    {
      "action_id": "move_P1_U8_cand_00_noop",
      "params": {
        "unit_id": "P1_U8_fast_screeners",
        "placement_ref": "placement://noop",
        "path_witness_ref": "path://noop"
      },
      "metadata": {
        "solver_ms": 1,
        "screen_coverage_cells": 42,
        "coherency_min_degree": 3,
        "threat_exposure_score": 0.18,
        "pivot_penalty_used": 0.0,
        "tight_clearance": false,
        "corridor_witness_ref": "corr://none"
      }
    },
    {
      "action_id": "move_P1_U8_cand_01_wide_safe",
      "params": {
        "unit_id": "P1_U8_fast_screeners",
        "placement_ref": "placement://P1_U8/01",
        "path_witness_ref": "path://P1_U8/01"
      },
      "metadata": {
        "solver_ms": 58,
        "screen_coverage_cells": 96,
        "coherency_min_degree": 2,
        "threat_exposure_score": 0.22,
        "pivot_penalty_used": 1.0,
        "tight_clearance": false,
        "corridor_witness_ref": "corr://oval_60x35/routeA"
      }
    },
    {
      "action_id": "move_P1_U8_cand_02_thread_ruins_gap",
      "params": {
        "unit_id": "P1_U8_fast_screeners",
        "placement_ref": "placement://P1_U8/02",
        "path_witness_ref": "path://P1_U8/02"
      },
      "metadata": {
        "solver_ms": 143,
        "screen_coverage_cells": 141,
        "coherency_min_degree": 2,
        "threat_exposure_score": 0.19,
        "pivot_penalty_used": 1.0,
        "tight_clearance": true,
        "corridor_witness_ref": "corr://oval_60x35/routeB",
        "segment_max_in": 0.25
      }
    }
  ],
  "mask": [true, true, true],
  "chosen_action_id": "move_P1_U8_cand_02_thread_ruins_gap",
  "wall_clock_ms": 187,
  "time_budget_ms": 396,
  "outcome": {
    "immediate_deltas": {
      "vp": { "P1": 0, "P2": 0 },
      "cp": { "P1": 0, "P2": 0 },
      "moved_units": ["P1_U8_fast_screeners"],
      "notes": ["move_success=true", "path_witness_validated=true"]
    },
    "end_of_turn_return": 0.0
  },
  "human_action_injected": false,
  "valid": true
}
```

What this shows:
- Tier 2's MovementIntent drives candidate generation (solver-backed).
- Tier 3 is purely a candidate ranker/selector (no legality learning).
- Tier 4 logs a replayable, trainable record aligned with the DecisionRecord schema.

### Example 3 - Stratagem posture + shooting targets: legal vs policy-allowed separation

Situation (high-level): Shooting phase. A unit can fire; there is an optional legal stratagem that improves output. Tier 1 plan says reserve 2 CP for defense, so Tier 2 sets a policy posture, but Tier 0 still enumerates all legal stratagem candidates.

Tier 0 -> Tier 3: PLAY_STRATAGEM decision

```yaml
msg:
  from: tier0.engine
  to: tier3.micro_executor
  type: DECISION
  payload:
    decision_id: "d_r2_p1_shoot_strat_P1_U6"
    decision_type: "PLAY_STRATAGEM"
    actor_player_id: "P1"
    context:
      phase: "SHOOTING"
      plan_id: "plan_r2_p1_t1"
      unit_id: "P1_U6_fire_support"
      cp_available: 2
      cp_reserved_for_defense: 2
      note: "cp_reserved_for_defense is POLICY, not legality"

    candidates:
      - action_id: "strat_none"
        params: { stratagem_id: "NONE" }
        metadata: { cp_cost: 0, expected_value_delta: 0.00 }

      - action_id: "strat_core_command_reroll"
        params: { stratagem_id: "CORE_COMMAND_REROLL", when: "SHOOTING", target_roll: "hit" }
        metadata: { cp_cost: 1, expected_value_delta: 0.08 }

      - action_id: "strat_detachment_damage_boost"
        params: { stratagem_id: "DETACHMENT_DAMAGE_BOOST", when: "SHOOTING", unit_id: "P1_U6_fire_support" }
        metadata:
          cp_cost: 1
          expected_value_delta: 0.14
          violates_cp_policy: true   # still legal; planner will penalize
    mask: [true, true, true]
```

Tier 3 choice (reflecting CP policy)

```yaml
msg:
  from: tier3.micro_executor
  to: tier0.engine
  type: CHOICE
  payload:
    decision_id: "d_r2_p1_shoot_strat_P1_U6"
    chosen_action_id: "strat_none"
    rationale:
      - "Plan reserves 2 CP for defense; spending 1 reduces defensive coverage"
      - "EV gain is small this phase; prefer variance reduction"
```

What this shows:
- Tier 0 enumerates legality; Tier 1/2 impose strategy policy, not legality.
- Tier 3 sees both and chooses accordingly (good separation of concerns).

### Example 4 - HumanActionCandidate injection (freeform move becomes a candidate)

Situation (high-level): Human player drags models to a legal end placement that is not in solver top-K. Engine injects it as a candidate so the dataset stays candidate-based.

Tier 4: DecisionRecord showing injected human action (valid JSON per schema)

```json
{
  "schema_version": "1.0.0",
  "game_id": "g_2026_01_28_0012",
  "turn_id": 1,
  "phase": "MOVEMENT",
  "decision_id": "d_r1_p2_move_P2_U5",
  "decision_type": "MOVE_UNIT",
  "ruleset_id": "core_rules_24.09+updates_v1.8_rc1.7",
  "dataslate_id": "balance_dataslate_v3.3",
  "points_id": "mfm_v3.8",
  "global_seed": 771192,
  "decision_seed": 771200,
  "omniscient_state": "stateblob://g_2026_01_28_0012/r1/p2/move/P2_U5/before",
  "player_obs_state": {
    "P1": "stateblob://g_2026_01_28_0012/r1/p1/obs",
    "P2": "stateblob://g_2026_01_28_0012/r1/p2/obs"
  },
  "candidates": [
    {
      "action_id": "move_P2_U5_cand_00_safe",
      "params": { "unit_id": "P2_U5", "placement_ref": "placement://P2_U5/00", "path_witness_ref": "path://P2_U5/00" },
      "metadata": { "solver_ms": 33, "screen_coverage_cells": 60, "coherency_min_degree": 2, "threat_exposure_score": 0.11 }
    },
    {
      "action_id": "move_P2_U5_cand_01_aggressive",
      "params": { "unit_id": "P2_U5", "placement_ref": "placement://P2_U5/01", "path_witness_ref": "path://P2_U5/01" },
      "metadata": { "solver_ms": 40, "screen_coverage_cells": 84, "coherency_min_degree": 1, "threat_exposure_score": 0.29 }
    },
    {
      "action_id": "move_P2_U5_human_injected_02",
      "params": { "unit_id": "P2_U5", "placement_ref": "placement://P2_U5/human/02", "path_witness_ref": "path://P2_U5/human/02" },
      "metadata": { "solver_ms": 0, "human_freeform": true, "screen_coverage_cells": 78, "coherency_min_degree": 2, "threat_exposure_score": 0.14 }
    }
  ],
  "mask": [true, true, true],
  "chosen_action_id": "move_P2_U5_human_injected_02",
  "wall_clock_ms": 6120,
  "time_budget_ms": 220,
  "outcome": {
    "immediate_deltas": { "vp": { "P1": 0, "P2": 0 }, "cp": { "P1": 0, "P2": 0 } },
    "end_of_turn_return": 0.0
  },
  "human_action_injected": true,
  "valid": true
}
```

What this shows:
- Human play remains compatible with Tier-3 "rank candidates" training because the final action is always represented as a candidate.

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

### ID Derivation Rule (Canonical)

- Use the version string on page 1 of each official PDF as the authoritative ID.
- If the Core Rules PDF has no explicit version string, use the date token in the filename (e.g., `core_rules_24.09`).
- Compose:
  - `ruleset_id = core_rules_<core_rules_version_or_date>+updates_v<errata_version>_rc<commentary_version>`
  - `dataslate_id = balance_dataslate_v<dataslate_version>`
  - `points_id = mfm_v<mfm_version>`

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

Note: PRs 1-12 explicitly avoid ML libraries. Keep the engine importable and replayable without any ML stack installed.

1. ✅ Ruleset/version plumbing + deterministic replay
   - Goal: make the engine replayable and patch-versioned before any AI logic lands.
   - Ruleset identity:
     - Plumb ruleset_id, dataslate_id, points_id into game state snapshots, event log records, and decision contexts.
     - Enforce a single active ruleset bundle per game instance.
   - Deterministic RNG:
     - Centralize RNG into an injectable, seedable service (no random.* scattered).
     - Ensure all stochastic resolution uses that RNG (dice, random target selection, any sampling).
   - Deterministic iteration:
     - Eliminate nondeterminism from iteration over sets/maps where it affects ordering.
     - Sort entity IDs before enumerating candidates or events.
   - Replay primitive:
     - Create a replayer that can replay a game from event log or decision log.
   - Tests:
     - Same seed -> identical event log hash.
     - Replay produces identical end state.
   - Docs:
     - Document the canonical source of ruleset IDs and where they are stored.
   - Policy: no ML libs.

2. ✅ Unified Decision API + action masking
   - Goal: every human/AI choice becomes the same deterministic Decision -> chosen CandidateAction interface.
   - Decision objects:
     - Every choice in all phases emits a Decision with decision_id, decision_type, context, candidates[], mask[].
   - CandidateAction invariants:
     - Deterministic ordering of candidates with a stable sort key.
     - Stable action_id format derived from canonical params (or a canonical hash).
   - Masking:
     - Provide legality mask + optional mask_reasons[] (useful for UI and debugging).
   - Controller boundary:
     - Introduce a controller interface used by human UI, remote/network, and heuristic AI (no ML).
   - Tests:
     - Decision candidate set matches golden snapshot.
     - Mask length == candidates length.
     - Chosen action rejected if mask is false.
   - Docs:
     - Add or refresh a Decision types catalog (even if partial initially).
   - Policy: no ML libs.

3. DecisionRecord logging + dual-view observation + HumanActionCandidate injection + deterministic replayer
   - Goal: make human games a first-class dataset source aligned to candidate-based RL later.
   - DecisionRecord writer:
     - Emit DecisionRecord for every decision: include global_seed, decision_seed, full candidates, mask, timing, outcome.
   - Dual view observation:
     - Store omniscient_state snapshot/delta and player_obs_state[player_id] snapshot/delta.
   - Schema enforcement:
     - Validate every record against DECISION_RECORD_SCHEMA.json in debug/test builds.
     - Add schema version bump rules if fields change.
   - HumanActionCandidate injection:
     - For freeform UI actions (movement especially): validate, compute required witnesses, append candidate if not present, select it.
   - Invalid attempt telemetry (optional but high value):
     - When UI rejects a human action, log valid=false with invalid_attempt + rejection_reason.
   - Deterministic replay:
     - Add a replayer mode: replay by DecisionRecords.
     - Assert candidate sets match recorded candidates (or fail loudly).
   - Tests:
     - Round-trip: play -> log -> replay -> identical end state.
     - HumanActionCandidate injection yields chosen_action_id present in candidates.
   - Docs:
     - Add a telemetry contract appendix pointing to the JSON schema.
   - Policy: no ML libs.

4. State encoding foundation with canonical perspectives
   - Goal: define stable, patch-resilient state blobs and feature extraction without ML.
   - Canonicalization:
     - Define StateBlob contents (full JSON snapshot or delta reference path).
     - Ensure serialization is deterministic and versioned.
   - Perspective transform:
     - Implement player_obs_state(P1) / player_obs_state(P2) consistently.
     - Define hidden vs public information (tactical cards, secret objectives, etc).
   - Derived features (engine-side):
     - Precompute deterministic derived facts (engagement range, objective control, threat range flags).
   - Tests:
     - Canonical snapshot stable under serialization.
     - Perspective transform does not leak hidden info.
   - Docs:
     - StateBlob schema description (even if not JSON-schema yet).
   - Policy: no ML libs.

5. Tier 1 Plan schema integrated into decision contexts
   - Goal: make the Plan real and plumb it end-to-end, even if heuristic initially.
   - Plan schema:
     - Implement Plan object exactly as documented: primary/deny, secondary posture, risk, CP posture, unit tiers.
   - Heuristic Tier-1 baseline (recommended):
     - Add a simple rule-based planner producing hold/contest suggestions, CP reserve posture, priority tiers.
   - Integration:
     - Plan is attached into Decision.context for later tiers.
   - Tests:
     - Plan exists for each turn start.
     - Plan ID threads through decisions for that turn.
   - Docs:
     - Plan schema + example.
   - Policy: no ML libs.

6. Compute Budget / Time Manager
   - Goal: make tournament-speed a hard contract now, not a later optimization.
   - Time manager:
     - Per decision type caps + tier multipliers (P0/P1/P2).
   - Anytime cut-off:
     - Return best candidate so far or fallback to simpler intent when time expires.
   - Telemetry:
     - Record time_budget_ms and wall_clock_ms in DecisionRecord.
   - Performance harness:
     - Benchmarks for candidate generation time and movement solve time.
   - Tests:
     - Hard cap respected (no runaway solve).
   - Docs:
     - Time manager policies and timeout behavior.
   - Policy: no ML libs.

7. MovementIntent schema + solver hooks
   - Goal: encode intent and let the solver generate legal candidates.
   - MovementIntent implementation:
     - Objective targets, deny regions, weights, anchors (0-3), constraint toggles.
   - Intent -> solver objective weights:
     - Objective proximity scoring, screen/deny coverage scoring (grid approximation allowed),
       coherency robustness scoring, threat exposure penalty.
   - Candidate generation:
     - Produce top-K candidates with metadata (solver_ms, screen coverage, threat score, etc).
   - Tests:
     - Same intent + same seed -> same candidates.
     - Candidate metadata present.
   - Docs:
     - MovementIntent examples and expected candidate metrics.
   - Policy: no ML libs.

8. PathWitness artifacts + continuous validation
   - Goal: enforce path legality and support deterministic replay/training.
   - Witness formats:
     - CorridorWitness per base profile group.
     - ModelPathWitness per model (translate, pivot, floor_transition).
   - Continuous checks:
     - Segment/volume intersections (not endpoint sampling).
   - Distance accounting:
     - Translation cost + pivot cost once-per-move.
   - Storage:
     - Use *_ref strings in candidates so DecisionRecords stay compact.
   - Tests:
     - Witness contiguous; ends match final pose.
     - Illegal engagement range crossing during Normal move is caught.
   - Docs:
     - PathWitness contract (ensure implementation matches).
   - Policy: no ML libs.

9. Tight clearance detection + pivot/orientation constraints
   - Goal: make oval bases and hull footprints behave credibly in tight gaps.
   - Clearance profiling:
     - Compute local clearance along corridor.
   - Tight interval tagging:
     - Ellipse: b <= clearance < a.
     - Hull: w <= clearance < sqrt(l^2 + w^2).
   - Adaptive segment length:
     - 0.5 inch default, 0.25 inch in tight, 0.1 inch escalation.
   - Orientation constraints:
     - Enforce yaw-band restriction (conservative first pass ok).
   - Tests:
     - Regression scenarios for threading cases (major does not fit, minor does).
   - Policy: no ML libs.

10. Tier 2 orchestration scaffolding
   - Goal: turn Plan into per-unit tasks and intents, with compute tiers.
   - Task schema:
     - SCORE / SCREEN / STAGE / TRADE / DENY / PROTECT / BAIT.
   - Heuristic Tier-2 baseline (recommended):
     - Deterministic orchestrator assigns tasks based on Plan + board control and emits MovementIntent weights.
   - Resource posture stub:
     - CP reserve policy enforcement at Tier 2 (Tier 0 still enumerates legal stratagems).
   - Tests:
     - Tasking emitted each phase/turn with Plan.
     - Compute tiers map to time manager multipliers.
   - Policy: no ML libs.

11. Training harness with league self-play (no ML)
   - Goal: build the harness in two sub-phases so ML can be delayed.
   - 11A) Harness and league skeleton (no ML):
     - Headless match runner for human, heuristic, and random controllers.
     - League manager (minimal) with opponent snapshots (heuristics/configs first).
     - Dataset generator: write DecisionRecords to disk for every match.
     - Offline evaluation: VP delta, decision counts by type, time usage vs budget.
   - Tests:
     - 10 game batch completes and produces valid DecisionRecords.
   - Policy: no ML libs.

12. Army muster generator + evaluator prototype
   - Goal: provide a meta-game roster search loop without ML dependencies initially.
   - Roster generator:
     - Legal 2000-point rosters from in-repo structured data.
   - Evaluator:
     - Heuristic scoring (robustness, OC mass, threat mix, scoring tools).
   - Integration:
     - Output playbook prior inputs to Tier 1/2 (risk posture defaults, CP posture defaults).
   - Tests:
     - Generates legal rosters deterministically with the same seed.
   - Docs:
     - Muster evaluator assumptions.
   - Policy: no ML libs.

## Add-on PRs to explicitly delay PyTorch

13. Optional ML dependency boundary (no training yet)
   - Strict dependency rule: core engine must import without torch installed.
   - Create warhammer40k_ai/ml/ package guarded behind optional extras.
   - Implement DecisionRecord dataset loader (pure Python).
   - Feature extraction pipeline (pure Python; outputs numpy arrays or JSON).
   - Add a tiny null model interface for inference that returns uniform scores.

14. First learned component: Tier 3 candidate ranker (offline supervised)
   - Only now bring in PyTorch (and later TorchRL/PyG if needed).
   - Train on DecisionRecords from human games and heuristic self-play:
     - Learning-to-rank or classification over candidates.
   - Verify deterministic inference (seeded, no dropout during eval).
   - Regression suite: model cannot propose illegal actions because it only ranks legal candidates.

## ML Framework Recommendation

Note: PyTorch and supporting ML libraries are intentionally deferred until the optional ML boundary and first learned component milestones (PR 13/14). Do not add ML dependencies to core before then.

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
