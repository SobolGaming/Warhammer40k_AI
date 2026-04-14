# Tournament Evaluation Objective

This document defines what the roster optimizer is trying to maximize.

Related docs:
- `docs/AI_MUSTERING_TOURNAMENT_ARCHITECTURE.md`
- `docs/TOURNAMENT_EVALUATION_PIPELINE.md`
- `docs/ML_ARTIFACT_REGISTRY.md`
- `docs/ARMY_MUSTERING_SCAFFOLDING.md`

## Optimization Target

The smallest unit of evaluation is:

```text
(ArmyBlueprint, policy_bundle_id, rules_bundle_id, field_distribution_id, event_policy_id)
```

The objective is not "find the strongest list in abstract."
The objective is:

```text
best fixed tournament roster for the current controller family
across a distribution of opponents, missions, terrain layouts,
deployments, and event-policy constraints
```

## Objective Definition

Rank fixed submitted rosters by expected tournament utility across a field
distribution. A good roster is one that:
- stays legal under the active rules bundle
- performs well across varied pairings and event context
- remains pilotable by the current controller bundle
- avoids brittle dependence on one mission, one terrain layout, or one narrow
  matchup slice

An initial scalar utility may be computed as:

```text
expected_match_value
+ vp_margin_term
- downside_risk_penalty
- controller_realizability_penalty
```

The exact weighting may evolve, but the decomposition must remain visible in
telemetry and reports.

## Required Utility Components

Every tournament evaluation should expose, at minimum:
- expected match outcome contribution
- VP or round-points margin contribution
- downside-risk contribution across poor pairings and context variance
- controller realizability penalties
- replay or stability penalties when deterministic execution degrades

Controller realizability includes:
- timeout risk
- no-progress risk
- excessive branching cost
- unstable replay behavior

## Field and Policy Dependence

Tournament evaluation is conditioned on:
- opponent roster or archetype weights
- mission distribution
- deployment distribution
- terrain distribution
- event policy
- controller bundle

Event policy is part of the objective because fixed-roster value changes when:
- force disposition is event-locked vs round-flexible
- pairing is iid vs swiss
- clock or terrain policy changes what the controller can pilot reliably

## Non-Goals

These are explicitly out of scope for the first learned stage:
- direct end-to-end list generation
- bypassing validator or mustering legality checks
- optimizing only for one mirror, one mission, or one terrain table
- treating faction names as sufficient artifact compatibility metadata

Direct end-to-end list generation is not the first learned target. The first
learned target should be a bounded evaluator that scores fixed rosters,
matchups, playbooks, or candidate edits inside a deterministic search loop.

## Evaluation Invariants

- Legality remains engine-side.
- Evaluation ranks or scores; it does not authorize illegal rosters.
- Event policy must be explicit, never implied by a hidden default.
- Controller bundle identity is part of the optimization target.
- Utility outputs must be logged in a `MusterRecord`-compatible form.

## Practical Recommendation

Start with:
- heuristic or learned matchup evaluation for fixed rosters
- deterministic search over explicit roster edits
- optional learned ranking of candidate edits

Defer:
- open-ended roster generation models
- end-to-end list builders whose legality and portability are hard to audit
