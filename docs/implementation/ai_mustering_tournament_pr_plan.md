# AI Mustering, Tournament Roster Optimization, and Model Artifact PR Plan

## Purpose

Define a concrete implementation sequence for adding AI-facing army mustering, tournament roster evaluation, and future learned roster optimization to the codebase **without** creating brittle, edition-locked behavior.

This plan is designed to work with the current `dev` branch state:

- `ArmyBlueprint` already carries detachments, detachment-point budget, unit entries, enhancement assignments, attachment bindings, a selected `force_disposition`, and allowed force dispositions.
- runtime mustering still stops short of materializing `unit_entries` into a playable `Army`.
- the ML boundary exists, but `src/warhammer40k_ai/ml/` is still intentionally minimal.
- broad hierarchical training is still blocked until the separate 11e port `PR-015` lands.

This plan therefore splits work into:

1. **implementable now** work that is safe before final 11th-edition exactness
2. **post-PR-015** work once final 11th rules are live
3. **ongoing patch-cycle** work for points, dataslates, errata, and codex churn

---

## Strategic framing

The list-building problem should **not** be modeled as “find the strongest list in abstract.”

The actual optimization target is:

```text
best fixed tournament roster for the current controller family
across a distribution of opponents, missions, terrain layouts,
deployments, and event-policy constraints
```

The real object of optimization is therefore:

```text
(ArmyBlueprint, policy_bundle_id, rules_bundle_id, field_distribution_id, event_policy_id)
```

Not just:

```text
ArmyBlueprint
```

That distinction is critical because a roster can be theoretically powerful while still being:

- too brittle into a diverse 5–6 round tournament field
- too terrain-dependent under a given mission pack
- too compute-expensive for the current AI controller to pilot well
- too sensitive to one dataslate, one points table, or one codex snapshot

---

## Design invariants

These invariants apply to every PR in this plan.

1. **Legality remains engine-side.**
   No learned model is allowed to invent illegal rosters. Search/edit actions must pass through the existing validator and mustering pipeline.

2. **The learned system evaluates and ranks.**
   Search constructs candidate rosters; learned components score matchups, playbooks, or candidate edits.

3. **Rules and descriptors are the portability axis.**
   Artifacts are keyed primarily by `rules_bundle_id`, descriptor provenance, feature-schema versions, and capability-schema versions — not by faction or detachment name alone.

4. **The capability compiler is deterministic.**
   Any roster-level semantic summary must be recomputed from rules/descriptors, not hand-maintained per patch.

5. **Tournament policy is explicit.**
   Do not hard-code assumptions like “Force Disposition is always locked” or “it is always changeable round to round.” Model event policy as data.

6. **Controller realizability matters.**
   Evaluation must include controller difficulty, timeout risk, no-progress risk, and replay stability — not just win rate.

7. **Artifacts are composable.**
   Shared encoders, rules adapters, Tier 3 heads, matchup evaluators, and playbook selectors should be independently swappable.

8. **Future patching should be local.**
   Points updates, dataslates, errata, codex releases, mission-pack changes, and terrain-pack changes should primarily require:
   - rules-bundle refresh
   - descriptor recompilation
   - capability recompilation
   - evaluator re-slicing
   - small adapter/head updates when needed

---

## Grounding in the current repo

The following current-dev facts shape the plan:

- `ArmyBlueprint` is already the correct build-time seam and should remain the root build object.
- `ArmyMusterer.muster_army()` still raises `NotImplementedError` when validated musters contain `unit_entries`; that must be closed before AI mustering can be evaluated end to end.
- the current ML subtree is deliberately minimal, so the first AI-facing infra PRs should remain framework-free.
- the canonical pre-ML data gate is already `pre_ml_baseline_v1`, and “headless fixed” should mean: self-play completes, strict replay passes, and the manifest gate passes.
- the 11e port plan still defers broad hierarchical training until port `PR-015` is complete.

---

## Core objects to introduce

### 1. `BuildCapabilityProfile`

A deterministic, rules-derived roster summary compiled from:

- `ArmyBlueprint`
- active `rules_bundle_id`
- relevant descriptor bundles
- event-policy context when needed

This should summarize what a roster can do, not merely what units it contains.

Suggested capability groups:

- board control / spread
- OC density / objective stickiness
- melee delivery / charge reliability
- ranged anti-vehicle / anti-elite / anti-horde
- action economy / mission-task capacity
- reserve pressure and reserve denial
- durability by damage band
- detachment economy / enhancement economy
- attachment graph richness and dependency risk
- force-disposition affordances
- terrain-occlusion reliance
- hidden/obscuring leverage
- elevated-fire / plunging leverage
- towering leverage / exposure
- deployment pressure / reveal pressure
- redundancy / failure tolerance
- controller complexity / branching cost

The exact semantics must be **rules-derived** and schema-versioned.

### 2. `TournamentFieldDistribution`

A data object describing the distribution of opponent rosters and event context to evaluate against.

Suggested fields:

- `field_distribution_id`
- `rules_bundle_id`
- `event_policy_id`
- opponent roster entries or archetype slices with weights
- mission/deployment/terrain distributions
- terrain-layout pack id
- optional round-count / event format metadata
- optional Swiss or random-pairing evaluation mode

### 3. `EventPolicyDescriptor`

Make tournament constraints explicit instead of implicit.

Suggested fields:

- `event_policy_id`
- `force_disposition_lock_mode`: `event_locked | round_locked | flexible`
- `secondary_selection_mode`
- `terrain_layout_mode`
- `clock_policy`
- `pairing_mode`: `iid | swiss`
- `roster_submission_mode`
- `max_rounds`

This is what keeps the system portable between 10th, preview 11th, final 11th, and future event packs.

### 4. `PolicyBundle`

A runtime assembly of controller artifacts and heuristic fallbacks.

It should map decision families to either:

- learned artifact ids
- heuristic implementations
- explicit fallback order

### 5. `MusterRecord`

A telemetry object for roster-evaluation and roster-search experiments.

Suggested fields:

- `muster_record_id`
- `army_blueprint_hash`
- `rules_bundle_id`
- `descriptor_bundle_id`
- `build_capability_profile_id`
- `event_policy_id`
- `field_distribution_id`
- `policy_bundle_id`
- utility decomposition
- replay/gate results
- search trace / edit actions
- provenance: git commit, schema versions, manifests

---

## Recommended storage model

Do **not** store learned models primarily by faction or detachment.

Use a two-layer storage model:

```text
models/
  registry.json
  artifacts/
    <artifact_id>/
      manifest.json
      config.json
      metrics.json
      checkpoint.safetensors
  bundles/
    <policy_bundle_id>.json
  reports/
    <evaluation_run_id>/
      summary.json
      per_match.csv
      gate_report.json
      replay_report.json
```

### Artifact manifest fields

Every artifact manifest should include at least:

- `artifact_id`
- `family_id`
- `component_type`
- `tier`
- `architecture_id`
- `feature_schema_id`
- `capability_schema_id`
- `training_manifest_path`
- `training_manifest_hash`
- `rules_bundle_scope`
- `descriptor_bundle_scope`
- `version_adapter_boundary_id`
- `event_policy_scope`
- `git_commit`
- `parent_artifact_ids`
- `metrics`
- `status`: `experimental | candidate | blessed | deprecated`

### Bundle manifest fields

Every bundle manifest should include at least:

- `policy_bundle_id`
- `controller_type`
- `rules_bundle_scope`
- `event_policy_scope`
- `components` mapping decision family to artifact or heuristic
- `fallbacks`
- `required_feature_schema_ids`
- `required_capability_schema_ids`
- `created_from_commit`

---

## Recommended module layout

### Engine / roster / evaluation side

```text
src/warhammer40k_ai/roster/
  unit_materialization.py
  build_capability.py
  build_capability_schema.py
  matchup_context.py
  tournament_field.py
  event_policy.py
  tournament_roster_evaluator.py
  roster_edit_actions.py
  roster_repair.py
  roster_search.py
  roster_search_report.py
  muster_record.py
  muster_manifest.py
```

### Descriptor side

```text
src/warhammer40k_ai/engine/
  descriptor_build_capability.py
  descriptor_event_policy.py
```

### ML boundary side

```text
src/warhammer40k_ai/ml/
  interfaces.py
  registry.py
  policy_bundle.py
  features/
  datasets/
  models/
  backends/
```

### Scripts

```text
scripts/
  evaluate_policy_bundle.py
  evaluate_tournament_roster.py
  search_tournament_roster.py
  build_mustering_manifest.py
```

---

## Tournament evaluation objective

Use a utility that rewards broad-field performance rather than one-trick spike performance.

Suggested default objective:

```text
U(roster) = mean_match_EV
            - λ * downside_risk
            - μ * controller_compute_cost
            - ν * replay_failure_cost
            + ξ * plan_coverage
```

Where:

- `mean_match_EV` = mean VP delta or win probability across the sampled field
- `downside_risk` = CVaR / worst-decile performance across bad matchups
- `controller_compute_cost` = timeout risk, no-progress risk, action-budget stress
- `replay_failure_cost` = strict replay drift or data-gate failure penalties
- `plan_coverage` = number of opponent/mission/terrain contexts where the roster still has a coherent plan

This objective should be configurable and versioned.

---

## Implementation phases

## Phase A — implementable now, before 11e port `PR-015`

These PRs are safe to implement immediately.

### PR-MUSTER-001 — Normative docs and ABI for roster optimization

**Status:** Completed and pushed to `dev` on April 14, 2026 as commit `84bedca8` (`Add PR-MUSTER-001 mustering tournament ABI docs`).

**Goal**

Create the normative docs that define the stable ABI for roster evaluation, artifact storage, and tournament policy.

**Start condition**

- current `dev`
- no framework-specific ML runtime stack exists yet

**Main changes**

- add `docs/ML_ARTIFACT_REGISTRY.md`
- add `docs/AI_MUSTERING_TOURNAMENT_ARCHITECTURE.md`
- add `docs/TOURNAMENT_EVALUATION_OBJECTIVE.md`
- define `PolicyBundle`, artifact manifest fields, and promotion states
- define `EventPolicyDescriptor`
- define the optimization target as `(ArmyBlueprint, policy_bundle_id, rules_bundle_id, field_distribution_id, event_policy_id)`
- state explicitly that direct end-to-end list generation is **not** the first learned target

**End condition**

- docs are normative enough that future PRs can reference them instead of restating conventions
- artifact/bundle ids, schema ids, and provenance rules are specified
- no code behavior changes yet

**Acceptance checks**

- docs contain at least one example artifact manifest and one example bundle manifest
- docs describe the no-ML-extras compatibility requirement
- docs describe patch-scope and retraining-scope rules

**Non-goals**

- model training
- runtime controller changes
- roster evaluation code

**Dependencies**

- none

---

### PR-MUSTER-002 — Framework-free ML interfaces, registry, and bundle loader

**Status:** Completed on April 14, 2026. Acceptance checks passed and the full `python3 -m pytest tests/` suite is green.

**Goal**

Add the minimal ML-facing runtime interfaces without introducing framework coupling into the engine.

**Start condition**

- PR-MUSTER-001 merged
- `src/warhammer40k_ai/ml/` still boundary-only

**Main changes**

- add `src/warhammer40k_ai/ml/interfaces.py`
- add `src/warhammer40k_ai/ml/registry.py`
- add `src/warhammer40k_ai/ml/policy_bundle.py`
- define protocols for:
  - `CandidateRanker`
  - `MatchupEvaluator`
  - `PlaybookSelector`
  - `ArtifactResolver`
  - `PolicyBundleLoader`
- support heuristic-only bundle resolution when no learned artifacts are installed

**End condition**

- a policy bundle can be loaded and resolved with zero ML extras installed
- engine/runtime imports still work without `[ml]`

**Acceptance checks**

- regression tests verify no forbidden ML imports leak into engine/replay code paths
- a heuristic-only bundle can be loaded from JSON and used to resolve decision handlers
- unknown artifact ids fail with clear diagnostics

**Non-goals**

- torch backends
- checkpoint loading
- training loops

**Dependencies**

- PR-MUSTER-001

---

### PR-MUSTER-003 — Finish runtime mustering for validated `unit_entries`

**Status:** Completed on April 14, 2026. Acceptance checks passed and the full `python3 -m pytest tests/` suite is green.

**Goal**

Close the current `ArmyMusterer` gap so validated build-time rosters become playable runtime armies.

**Start condition**

- current mustering path still raises on non-empty `unit_entries`

**Main changes**

- add `src/warhammer40k_ai/roster/unit_materialization.py`
- implement runtime materialization from validated roster entries
- preserve:
  - multi-detachment structure
  - detachment-point spend
  - enhancement assignments
  - Leader/Support/bodyguard bindings
  - force-disposition selections / allowances
- add a stable `army_blueprint_hash`
- expose a path that evaluates from `ArmyBlueprint` directly, not only army-list text files

**End condition**

- a validated muster with `unit_entries` can produce a playable runtime `Army`
- headless setup and first turn succeed from blueprint-originated armies

**Acceptance checks**

- multi-detachment validated muster materializes and survives snapshot/save-load
- attached Leader/Support bindings persist into runtime state
- enhancement assignments and warnings serialize correctly
- headless smoke test succeeds from blueprint input

**Non-goals**

- learned mustering
- roster search

**Dependencies**

- PR-MUSTER-001

---

### PR-MUSTER-004 — Deterministic `BuildCapabilityProfile` compiler

**Goal**

Create the deterministic semantic layer that explains what a roster can do in gameplay terms.

**Start condition**

- PR-MUSTER-003 merged
- `ArmyBlueprint` and validated muster materialization are stable

**Main changes**

- add `src/warhammer40k_ai/roster/build_capability.py`
- add `src/warhammer40k_ai/roster/build_capability_schema.py`
- add `src/warhammer40k_ai/engine/descriptor_build_capability.py`
- add `docs/BUILD_CAPABILITY_SCHEMA.md`
- compile a JSON-safe profile from `ArmyBlueprint` + `rules_bundle_id`
- include a deterministic `build_capability_profile_id`
- expose a clear `capability_schema_id`

**Design constraint**

Feature names should be **generic and portable**, for example:

- `terrain_occlusion_reliance`
- `elevated_fire_affinity`
- `deployment_reveal_pressure`
- `charge_delivery_reliance`
- `objective_spread_tolerance`
- `attachment_dependency_risk`
- `controller_complexity_index`

Avoid hard-wiring preview-era 11e wording into schema names.

**End condition**

- the same blueprint under the same rules bundle compiles to the same capability profile id
- changing rules bundle or schema version changes the profile deterministically

**Acceptance checks**

- deterministic compilation tests
- explicit schema-version bump behavior tests
- regression fixtures for mixed-detachment, melee-heavy, towering-heavy, and action-heavy rosters

**Non-goals**

- learned evaluation
- search
- PR-015 final 11e exactness assumptions

**Dependencies**

- PR-MUSTER-003

---

### PR-MUSTER-005 — `TournamentFieldDistribution` and `EventPolicyDescriptor`

**Goal**

Represent opponent fields and tournament constraints as first-class data.

**Start condition**

- PR-MUSTER-004 merged

**Main changes**

- add `src/warhammer40k_ai/roster/tournament_field.py`
- add `src/warhammer40k_ai/roster/matchup_context.py`
- add `src/warhammer40k_ai/roster/event_policy.py`
- add `docs/TOURNAMENT_FIELD_SCHEMA.md`
- define:
  - weighted opponent roster entries or archetype slices
  - mission/deployment/terrain distributions
  - event lock rules for force disposition and other pregame choices
  - pairing mode (`iid`, `swiss`)
  - clock and evaluation budget metadata

**End condition**

- the system can represent “evaluate this roster into this field under this event policy” without hard-coded tournament assumptions

**Acceptance checks**

- field distributions validate and hash deterministically
- event policy differences alter matchup context deterministically
- 10th-style and preview-11e-style event policies can coexist as data

**Non-goals**

- roster search
- learned matchup evaluation

**Dependencies**

- PR-MUSTER-004

---

### PR-MUSTER-006 — Unified evaluation pipeline for bundles and rosters

**Goal**

Add a single evaluation path that defines “headless fixed” and “training-grade” for controllers and rosters.

**Start condition**

- PR-MUSTER-002, PR-MUSTER-003, PR-MUSTER-004, PR-MUSTER-005 merged

**Main changes**

- add `scripts/evaluate_policy_bundle.py`
- add `scripts/evaluate_tournament_roster.py`
- integrate the existing path:
  1. headless self-play generation
  2. strict replay audit
  3. relabel
  4. manifest build and gate enforcement
  5. evaluation report generation
- expose utility decomposition:
  - completion rate
  - replay pass rate
  - manifest gate status
  - VP / win metrics
  - no-progress ratio
  - timeout or max-phase-step exits
  - controller complexity metrics

**End condition**

- a roster evaluation run fails if self-play fails, replay fails, or the manifest gate fails
- a bundle evaluation run produces an auditable report directory

**Acceptance checks**

- deterministic seeded smoke evaluation
- failing replay causes non-zero exit
- failing `pre_ml_baseline_v1` causes non-zero exit
- heuristic-only bundles work without ML extras installed

**Non-goals**

- learned matchup evaluator
- roster search

**Dependencies**

- PR-MUSTER-002 through PR-MUSTER-005

---

### PR-MUSTER-007 — Deterministic roster edit DSL and non-learned search

**Goal**

Create the offline optimizer that searches legal roster space without any learned model requirement.

**Start condition**

- PR-MUSTER-006 merged

**Main changes**

- add `src/warhammer40k_ai/roster/roster_edit_actions.py`
- add `src/warhammer40k_ai/roster/roster_repair.py`
- add `src/warhammer40k_ai/roster/roster_search.py`
- add `src/warhammer40k_ai/roster/roster_search_report.py`
- implement edit actions such as:
  - add/remove detachment
  - swap detachment
  - add/remove unit entry
  - change wargear choice
  - assign/remove enhancement
  - bind/unbind leader or support attachment
  - rebalance detachment-point spend
  - mutate force-disposition lock choice when event policy permits it
- support beam search, local search, or evolutionary search under one interface

**End condition**

- search can generate legal candidate rosters from a seed blueprint and return ranked reports
- no illegal intermediate roster escapes validation

**Acceptance checks**

- search returns only validator-approved blueprints
- search reports include utility decomposition and edit traces
- search is reproducible under fixed seeds

**Non-goals**

- learned guidance
- direct roster generation model

**Dependencies**

- PR-MUSTER-006

---

### PR-MUSTER-008 — Mustering telemetry, manifests, and experiment corpus

**Goal**

Create a dedicated experiment/data layer for roster evaluation and future learned list-building.

**Start condition**

- PR-MUSTER-006 and PR-MUSTER-007 merged

**Main changes**

- add `src/warhammer40k_ai/roster/muster_record.py`
- add `src/warhammer40k_ai/roster/muster_manifest.py`
- add `docs/MUSTERING_DATA_SPEC.md`
- add `scripts/build_mustering_manifest.py`
- capture:
  - blueprint hashes
  - capability profile ids
  - field distribution ids
  - policy bundle ids
  - event policy ids
  - utility terms
  - replay/gate outcomes
  - search-edit sequences
  - provenance
- support slicing by:
  - rules bundle
  - capability schema id
  - field distribution id
  - event policy id
  - faction/detachment tags
  - controller bundle

**End condition**

- roster-search and roster-evaluation experiments become auditable, sliceable, and reusable for later training

**Acceptance checks**

- manifest CLI can filter and summarize mustering corpora
- schema version changes are explicit and validated
- reports include lineage back to rules and descriptor provenance

**Non-goals**

- learned evaluator
- learned proposer

**Dependencies**

- PR-MUSTER-006 and PR-MUSTER-007

---

### PR-MUSTER-009 — Baseline heuristic matchup evaluator and tournament utility model

**Goal**

Add a strong non-learned baseline scorer before any learned matchup model exists.

**Start condition**

- PR-MUSTER-004, PR-MUSTER-005, and PR-MUSTER-008 merged

**Main changes**

- add `src/warhammer40k_ai/roster/matchup_heuristics.py`
- add `src/warhammer40k_ai/roster/tournament_utility.py`
- score roster-vs-field fit from capability profiles and event-policy context
- include downside-risk and controller-difficulty penalties
- use this evaluator to seed roster search and to generate bootstrapping labels

**End condition**

- search can run with a deterministic evaluator even before learned models exist
- evaluation reports can decompose the utility terms clearly

**Acceptance checks**

- heuristic matchup scores are deterministic
- utility decomposition is auditable and human-readable
- at least one regression fixture demonstrates why a broad-field roster outranks a one-trick roster under the configured utility

**Non-goals**

- learned models
- PR-015 exact final 11e tuning

**Dependencies**

- PR-MUSTER-004, PR-MUSTER-005, PR-MUSTER-008

---

## Phase B — after 11e port `PR-015` and final 11th rules are live

These PRs should start only after release-day exactness is complete.

### PR-MUSTER-010 — Final 11e exactness update for capability compiler and event defaults

**Goal**

Replace preview-safe assumptions with final 11th rules data where needed.

**Start condition**

- 11e port `PR-015` merged
- final 11th rules corpus, points, missions, terrain pack, and detachment data ingested

**Main changes**

- reconcile `BuildCapabilityProfile` against final 11e semantics
- update event-policy defaults to final tournament assumptions
- update terrain/objective-related capability derivations
- regenerate golden fixtures and docs

**End condition**

- no preview-only capability assumptions remain in active defaults
- capability compiler is final-11e exact under the launch bundle

**Acceptance checks**

- release-day rules bundle goldens pass
- preview-only TODOs removed or explicitly retained behind legacy test fixtures
- evaluation reports show correct final-rules provenance

**Non-goals**

- learned matchup evaluator yet

**Dependencies**

- 11e port `PR-015`
- PR-MUSTER-004 and PR-MUSTER-005

---

### PR-MUSTER-011 — Torch backend, dataset loaders, and artifact runtime plumbing

**Goal**

Add framework-specific ML plumbing entirely behind the existing boundary.

**Start condition**

- PR-MUSTER-002 and PR-MUSTER-008 merged
- 11e port `PR-015` complete

**Main changes**

- add `src/warhammer40k_ai/ml/backends/torch/`
- add `src/warhammer40k_ai/ml/datasets/`
- add dataset loaders for mustering corpora and matchup corpora
- add runtime checkpoint loading for supported artifact families
- preserve heuristic fallbacks when artifacts are missing or incompatible

**End condition**

- learned artifacts can be loaded behind the bundle interface without changing engine imports

**Acceptance checks**

- installs remain optional under `[ml]`
- bundle runtime can load or reject artifacts with clear compatibility diagnostics
- no engine-side imports depend on torch

**Non-goals**

- direct roster proposer

**Dependencies**

- PR-MUSTER-002, PR-MUSTER-008, PR-MUSTER-010

---

### PR-MUSTER-012 — Learned matchup evaluator v1

**Goal**

Train the first learned model for roster optimization: a matchup/value model, not a direct list generator.

**Start condition**

- PR-MUSTER-011 merged
- sufficient mustering corpus and evaluation reports exist

**Main changes**

- add `src/warhammer40k_ai/ml/features/roster_features.py`
- add `src/warhammer40k_ai/ml/models/matchup_evaluator.py`
- train a model over:
  - self capability profile
  - opponent capability profile
  - event policy
  - mission/deployment/terrain context
  - controller bundle identity
- predict:
  - expected VP delta
  - win probability
  - downside risk
  - controller difficulty proxy

**End condition**

- the learned matchup evaluator can outperform the heuristic baseline on held-out evaluation sets
- the bundle system can swap between heuristic and learned evaluator cleanly

**Acceptance checks**

- documented train/val/test splits by rules and field provenance
- metrics beat heuristic baseline on defined targets
- artifact manifest includes capability-schema and event-policy compatibility

**Non-goals**

- direct roster generation
- Tier 1 planner training

**Dependencies**

- PR-MUSTER-011

---

### PR-MUSTER-013 — Search-guided tournament roster optimizer using learned evaluation

**Goal**

Use the learned matchup evaluator to guide search over legal roster edits.

**Start condition**

- PR-MUSTER-012 merged

**Main changes**

- update `roster_search.py` to support learned evaluators through bundle resolution
- support evaluator ensembles and fallback to heuristic scores
- add an explicit optimization mode for:
  - mean EV
  - downside-robust event lists
  - controller-friendly lists
  - meta-targeted lists

**End condition**

- search can produce ranked tournament rosters using learned guidance while preserving engine-side legality

**Acceptance checks**

- search remains deterministic under fixed seeds and fixed evaluator checkpoints
- fallback to heuristic evaluator is seamless
- reports include which evaluator(s) contributed to ranking

**Non-goals**

- direct end-to-end list generation

**Dependencies**

- PR-MUSTER-012

---

### PR-MUSTER-014 — Pregame playbook selector for fixed submitted rosters

**Goal**

Separate roster construction from round-by-round plan selection.

**Start condition**

- PR-MUSTER-012 merged
- sufficient matchup corpus exists

**Main changes**

- add `src/warhammer40k_ai/ml/models/playbook_selector.py`
- add `docs/PREGAME_PLAYBOOK_SCHEMA.md`
- predict or rank a per-round playbook conditioned on:
  - submitted roster
  - opponent roster
  - mission/deployment/terrain context
  - event policy
- playbook outputs can include:
  - reserve posture
  - aggression posture
  - terrain-usage posture
  - target-priority bands
  - early-turn board-control posture
  - if event policy allows it, round-level force-disposition choice

**End condition**

- the system can separate “which roster did we submit?” from “how do we pilot this matchup?”

**Acceptance checks**

- event-policy constraints are enforced
- no playbook output requests illegal pregame choices
- playbook provenance is logged in evaluation reports

**Non-goals**

- replacing Tier 1/Tier 2 globally

**Dependencies**

- PR-MUSTER-012

---

### PR-MUSTER-015 — Roster-conditioned Tier 3 adapter support

**Goal**

Let existing Tier 3 models consume roster/opponent capability context without retraining the full stack.

**Start condition**

- PR-MUSTER-011 and PR-MUSTER-014 merged

**Main changes**

- add small adapter inputs or context vectors for:
  - self capability profile
  - opponent capability profile
  - playbook id
  - event policy id
- apply to narrow, legal-candidate ranking tasks first:
  - targeting
  - fight order
  - tool usage
  - later movement

**End condition**

- Tier 3 heads can exploit roster-level context while still ranking legal candidates only

**Acceptance checks**

- adapter-on vs adapter-off ablations are reported
- artifact manifests declare required capability schema ids
- fallback behavior remains valid when adapters are unavailable

**Non-goals**

- full Tier 1/Tier 2 HRL training

**Dependencies**

- PR-MUSTER-011 and PR-MUSTER-014

---

## Phase C — ongoing patch-cycle hardening

These PRs can land incrementally after the core system exists.

### PR-MUSTER-016 — Patch adaptation and artifact promotion pipeline

**Goal**

Make points changes, dataslates, errata, codexes, mission-pack updates, and terrain-pack changes cheap to evaluate and cheap to patch.

**Start condition**

- PR-MUSTER-011 through PR-MUSTER-015 in place

**Main changes**

- add artifact compatibility checks against:
  - `rules_bundle_id`
  - `descriptor_bundle_id`
  - `capability_schema_id`
  - `event_policy_id`
- add promotion workflow:
  - `experimental -> candidate -> blessed -> deprecated`
- add automated evaluation matrix on patch ingestion
- document “re-evaluate / fine-tune / retrain” rules per artifact family

**End condition**

- a patch release can be assessed by recomputing descriptors/capabilities and re-running evaluation before any retraining decision is made

**Acceptance checks**

- a changed rules bundle invalidates incompatible artifacts cleanly
- compatibility diagnostics explain why an artifact cannot be promoted
- reports quantify whether a small adapter refresh is enough

**Non-goals**

- forcing retraining on every patch

**Dependencies**

- PR-MUSTER-011 through PR-MUSTER-015

---

### PR-MUSTER-017 — Swiss-event simulator and downside-risk tuning

**Goal**

Improve tournament realism once the basic roster optimizer is already working.

**Start condition**

- PR-MUSTER-013 merged

**Main changes**

- add Swiss pairing simulation as an evaluation mode
- add CVaR and worst-round utility options
- compare “meta farming” vs “broad consistency” rosters under realistic event progression

**End condition**

- the optimizer can target actual event success instead of just IID matchup averages

**Acceptance checks**

- Swiss and IID evaluation modes are reproducible and separately reported
- downside-robust utility tuning is documented and test-covered

**Non-goals**

- changing the legality pipeline

**Dependencies**

- PR-MUSTER-013

---

### PR-MUSTER-018 — Optional retrieval/proposal model for roster ideation

**Goal**

Add a proposal model only after the evaluator/search stack is already strong and auditable.

**Start condition**

- PR-MUSTER-013 stable in practice
- mustering corpora large and diverse enough

**Main changes**

- add an optional retrieval or proposal model that emits candidate blueprint edits or seed rosters
- require every proposed roster to pass validator + evaluator + replay/gate evaluation
- treat this as a speed/ideation layer, not the source of truth

**End condition**

- the model can propose useful seeds, but final ranking still comes from search + evaluator

**Acceptance checks**

- proposals are auditable and reproducible
- proposal quality is measured against search-only baselines
- invalid proposals are rejected before evaluation

**Non-goals**

- replacing deterministic validation and evaluator-based ranking

**Dependencies**

- PR-MUSTER-013

---

## Special handling for 10th-edition data

10th data may still be useful, but only in limited roles.

Allowed uses:

- pretraining a roster encoder
- pretraining a matchup evaluator on broad capability relationships
- testing the mustering/evaluation/search stack
- generating negative examples for portability tests

Disallowed uses:

- treating 10th data as canonical supervision for production 11th tournament list building
- hard-coding 10th mission geometry or objective assumptions into shared schemas
- keying artifact compatibility only by faction labels while ignoring rules-bundle provenance

---

## Why the first learned model should be a matchup evaluator, not a direct list builder

A direct list-builder model is the wrong first learned target because it is:

- harder to debug
- harder to patch across rules updates
- harder to constrain legally
- harder to optimize for downside risk and controller difficulty

The first learned model should instead answer:

> how well does this fixed roster perform across this opponent field, under this event policy, with this controller bundle?

That keeps the learned problem small, portable, and auditable.

---

## Release and maintenance rules

### A roster-optimization artifact may not be promoted unless:

- headless evaluation completes successfully
- strict replay passes
- required manifest gates pass
- provenance fields are complete
- schema compatibility checks pass

### A patch should trigger this order of operations:

1. ingest or refresh rules bundles / descriptors
2. recompile capability profiles
3. re-run roster and bundle evaluations
4. assess whether heuristic behavior remains acceptable
5. assess whether small adapters are enough
6. only then consider larger retraining

### A model should never be considered portable unless:

- its feature schema is versioned
- its capability schema is versioned
- its rules-bundle compatibility is explicit
- its event-policy compatibility is explicit
- its fallback behavior is defined

---

## Short recommendation on sequencing

If only a few PRs can be done soon, do them in this order:

1. `PR-MUSTER-001` docs and ABI
2. `PR-MUSTER-002` framework-free ML registry and bundle loader
3. `PR-MUSTER-003` runtime `unit_entries` materialization
4. `PR-MUSTER-004` deterministic capability compiler
5. `PR-MUSTER-005` field + event policy schema
6. `PR-MUSTER-006` unified evaluation pipeline
7. `PR-MUSTER-007` non-learned search
8. `PR-MUSTER-008` mustering telemetry and manifests
9. `PR-MUSTER-009` heuristic matchup evaluator

That sequence creates a complete non-learned tournament roster lab first, which is the safest foundation for future experimentation.

---

## Success criteria for the whole initiative

This initiative is successful when the repo can:

1. materialize and validate mixed-detachment tournament rosters from `ArmyBlueprint`
2. evaluate a fixed roster across a configurable field and event policy
3. reject rosters that the current AI controller cannot pilot reliably
4. log mustering experiments with full rules/descriptor provenance
5. swap heuristic and learned evaluators through bundle manifests
6. survive rules churn by recompiling descriptors and patching small artifacts instead of restarting the full stack
7. optimize for broad tournament robustness rather than one-match spike performance

---

## Reference paths in the current repo

- `docs/implementation/11e_port_pr_plan.md`
- `docs/AI_REINTRODUCTION_PLAN.md`
- `docs/AI_MUSTERING_TOURNAMENT_ARCHITECTURE.md`
- `docs/HEADLESS_SELF_PLAY_RUNBOOK.md`
- `docs/ML_ARTIFACT_REGISTRY.md`
- `docs/TOURNAMENT_EVALUATION_OBJECTIVE.md`
- `docs/TRAINING_DATA_SPEC.md`
- `docs/ML_DEPENDENCY_BOUNDARY.md`
- `src/warhammer40k_ai/roster/army_build.py`
- `src/warhammer40k_ai/roster/army_muster.py`
- `src/warhammer40k_ai/engine/descriptor_army_build.py`
- `src/warhammer40k_ai/ml/dependency_boundary.py`
