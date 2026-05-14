# ML Artifact Registry

This document defines the stable file and manifest ABI for roster-evaluation and
policy-bundle artifacts used by AI mustering and tournament optimization.

Related docs:
- `docs/AI_MUSTERING_TOURNAMENT_ARCHITECTURE.md`
- `docs/TOURNAMENT_EVALUATION_OBJECTIVE.md`
- `docs/ML_DEPENDENCY_BOUNDARY.md`
- `docs/SEMANTIC_DIFF_CLASSIFIER.md`
- `docs/VERSION_ADAPTER_BOUNDARY.md`

## Core Policy

- Registry and bundle loading must work with base project dependencies only.
  No caller may require `warhammer40k_ai[ml]` just to read manifests, resolve ids,
  or choose heuristic fallbacks.
- Learned artifacts evaluate or rank. Legality, mustering, and runtime
  materialization remain engine-side.
- Compatibility is keyed by rules, descriptor, event-policy, feature-schema, and
  capability-schema provenance. Faction or detachment labels alone are never
  sufficient compatibility claims.
- Artifact payloads are immutable once published. If payload bits, schema ids, or
  compatibility scope change, mint a new `artifact_id`.
- Policy bundles are immutable routing objects. If component mapping, fallback
  order, or compatibility scope changes, mint a new `policy_bundle_id`.

## Storage Layout

Recommended repository layout:

```text
models/
  registry.json
  artifacts/
    <artifact_storage_token>/
      manifest.json
      config.json
      metrics.json
      checkpoint.safetensors
  bundles/
    <policy_bundle_storage_token>.json
  reports/
    <evaluation_run_id>/
      summary.json
      per_match.csv
      gate_report.json
      replay_report.json
```

Storage rules:
- `models/registry.json` is a convenience index only.
- Per-artifact `manifest.json` and per-bundle `<policy_bundle_storage_token>.json` files are
  the authoritative compatibility records.
- Report outputs are reproducibility artifacts, not compatibility declarations.
- On-disk artifact and bundle paths must be derived through
  `ArtifactManifestStore`, not by interpolating ids directly into paths. The
  current runtime percent-encodes reserved filename characters, so manifest ids
  like `artifact:matchup_evaluator:preview11e_capability_v1:20260414` are stored
  under `artifact%3Amatchup_evaluator%3Apreview11e_capability_v1%3A20260414/`
  and `policy_bundle:heuristic_matchup_baseline_v1` is stored as
  `policy_bundle%3Aheuristic_matchup_baseline_v1.json`.

Current framework-free runtime implementation:
- `src/warhammer40k_ai/ml/interfaces.py`
- `src/warhammer40k_ai/ml/registry.py`
- `src/warhammer40k_ai/ml/policy_bundle.py`

Runtime rules:
- bundle loading must be able to read manifest JSON and resolve heuristic
  components with base project dependencies only
- artifact components with known framework-free architectures resolve to runtime
  objects with base project dependencies only
- unknown artifact architectures may resolve to manifest-backed references before
  checkpoint runtime plumbing exists, but unknown artifact ids must fail with
  clear diagnostics

## Identifier Rules

- All ids must be lower-case ASCII strings using only letters, digits, `:`, `_`,
  `-`, and `.`.
- The following prefixes are reserved:
  - `artifact:`
  - `policy_bundle:`
  - `rules_bundle:`
  - `descriptor_bundle:`
  - `feature_schema:`
  - `capability_schema:`
  - `event_policy:`
  - `field_distribution:`
  - `adapter:`
  - `family:`
- Ids are opaque. Future code may parse prefixes, but must not derive behavior
  from faction names embedded in the remaining suffix.
- Id reuse is forbidden. Once an id has been published in repo history, it must
  never be reassigned to different content.
- `git_commit` must be a commit hash from the source tree that produced the
  artifact or bundle. A full 40-hex hash is preferred; 12+ hex characters is the
  minimum acceptable abbreviation.

## Scope Objects

Compatibility scopes in artifact and bundle manifests use this JSON object:

```json
{
  "match_mode": "exact",
  "ids": ["rules_bundle:preview_11e_q2"]
}
```

Rules:
- `match_mode` is currently required and must be `exact`.
- `ids` must be a sorted, unique, non-empty list of ids from the relevant family.
- If future match modes are added, they must do so under a new manifest schema id.

## Artifact Manifest Fields

Every artifact manifest must include:
- `artifact_manifest_schema_id`
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
- `status`

Field intent:
- `family_id`: stable lineage id used to group replacements and descendants.
- `component_type`: the runtime role this artifact fills, such as
  `matchup_evaluator`, `playbook_selector`, or `roster_edit_ranker`.
- `tier`: logical placement in the controller stack, not a framework detail.
- `feature_schema_id`: the exact runtime feature extractor contract. Current
  framework-free linear candidate rankers export
  `feature_schema:decision_candidate_semantics_v2`, which excludes runtime
  entity ids from learned categorical hash buckets.
- `training_manifest_path` and `training_manifest_hash`: the exact dataset gate
  provenance that produced the artifact.
- `parent_artifact_ids`: immutable lineage links for fine-tunes, adapters, or
  patched descendants.
- `metrics`: JSON-safe summary values only. Raw reports live under `models/reports/`.

## Bundle Manifest Fields

Every policy bundle manifest must include:
- `policy_bundle_schema_id`
- `policy_bundle_id`
- `controller_type`
- `rules_bundle_scope`
- `descriptor_bundle_scope`
- `event_policy_scope`
- `components`
- `fallbacks`
- `required_feature_schema_ids`
- `required_capability_schema_ids`
- `created_from_commit`

Bundle rules:
- `components` maps logical runtime roles to resolution records.
- Each resolution record must contain:
  - `resolver_kind`: `artifact` or `heuristic`
  - `resolver_ref`: an `artifact_id` or heuristic registry id
- `fallbacks` is a mapping from the same logical runtime role to an ordered list
  of heuristic registry ids or alternative `artifact_id` values.
- A bundle intended for normal CI or default local use must resolve to
  `candidate` or `blessed` artifacts only. Referencing an `experimental` artifact
  requires explicit opt-in.

Policy orchestration gameplay controllers use these component names:
- `strategic_planner`
- `tactical_orchestrator`
- `deployment_ranker`
- `movement_ranker`
- `shooting_ranker`
- `charge_ranker`
- `fight_ranker`
- `tool_ranker`
- `reaction_ranker`
- `dice_policy`
- `allocation_ranker`

The default framework-free heuristic registry provides baseline resolver ids of
the form `heuristic:<component>:v1` for each policy orchestration gameplay component.
The existing `candidate_ranker`, `matchup_evaluator`, `playbook_selector`, and
`roster_edit_ranker` component families remain valid for broader evaluation and
mustering workflows.

The first learned gameplay artifact architecture is
`candidate_ranker_linear_v1`. Its artifact directory contains:

```text
manifest.json
config.json
metrics.json
```

`config.json` uses `candidate_ranker_linear_model:v1` and stores sparse
per-decision-type feature weights. The runtime scorer only ranks legal candidates
already supplied by the engine; if the artifact has no weights for a decision
type, the router falls through to the component fallback declared by the policy
bundle.

## Promotion States

Allowed artifact `status` values:
- `experimental`: usable for local research only; not a default dependency.
- `candidate`: passed manifest gates, strict replay, and local evaluation checks.
- `blessed`: recommended default artifact for its scope.
- `deprecated`: kept for replay, comparison, or rollback only.

Allowed status transitions:
- `experimental -> candidate`
- `candidate -> blessed`
- `experimental -> deprecated`
- `candidate -> deprecated`
- `blessed -> deprecated`

Reverse transitions are not allowed. If a replacement artifact regresses, publish
another artifact id instead of mutating history.

Promotion requirements:
- headless evaluation completed successfully
- strict replay passed
- required manifest gates passed
- provenance fields are complete
- schema compatibility checks passed

Capability-schema note:
- preview-combat evaluation artifacts may intentionally target
  `capability_schema:build_capability_v2`, but that remains an explicit
  compatibility split. Existing v1 artifacts and bundles must not broaden their
  required capability-schema ids in place.
- Capability extension groups, such as
  `capability_extension:11e_faction_focus_may2026`, are separate explicit
  descriptor inputs on top of a capability schema. Artifacts that consume those
  extension features must declare a new artifact/policy id; they must not imply
  that plain `build_capability_v2` payloads contain the extension feature set.

## Patch Scope and Retraining Scope

The registry ABI must support patch-local iteration instead of full resets.

Rules:
- Points-only or narrow dataslate changes require a new `rules_bundle_id` and new
  reports. Do not expand an existing artifact's rules scope in place.
- Mission, terrain, or event-policy changes require new descriptor and/or event
  policy scope declarations before promotion. Re-slice evaluation first, then
  decide whether heuristics, adapters, or full retraining are needed.
- Feature or capability schema changes always require new `artifact_id` and
  `policy_bundle_id` values. Schema compatibility claims may not be broadened in
  place.
- Reuse `parent_artifact_ids` to show lineage when a new artifact reuses previous
  weights, adapters, or frozen encoders.
- Use `docs/SEMANTIC_DIFF_CLASSIFIER.md` and
  `docs/VERSION_ADAPTER_BOUNDARY.md` to decide whether a change is adapter-first,
  evaluation-only, or broad-retrain scope.

## Example Artifact Manifest

```json
{
  "artifact_manifest_schema_id": "artifact_manifest_schema:v1",
  "artifact_id": "artifact:matchup_evaluator:preview11e_capability_v1:20260414",
  "family_id": "family:matchup_evaluator",
  "component_type": "matchup_evaluator",
  "tier": "tournament_eval",
  "architecture_id": "matchup_evaluator_baseline_v1",
  "feature_schema_id": "feature_schema:roster_matchup_v1",
  "capability_schema_id": "capability_schema:build_capability_v1",
  "training_manifest_path": "models/reports/run_20260414/training_manifest.json",
  "training_manifest_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
  "rules_bundle_scope": {
    "match_mode": "exact",
    "ids": ["rules_bundle:preview_11e_q2"]
  },
  "descriptor_bundle_scope": {
    "match_mode": "exact",
    "ids": ["descriptor_bundle:preview_11e_q2"]
  },
  "version_adapter_boundary_id": "adapter:rules_conditioned_path:v1",
  "event_policy_scope": {
    "match_mode": "exact",
    "ids": ["event_policy:gt_fixed_roster_v1"]
  },
  "git_commit": "0123456789abcdef0123456789abcdef01234567",
  "parent_artifact_ids": [],
  "metrics": {
    "mean_tournament_utility": 0.58,
    "worst_quartile_utility": 0.34,
    "timeout_rate": 0.0
  },
  "status": "candidate"
}
```

## Example Bundle Manifest

```json
{
  "policy_bundle_schema_id": "policy_bundle_schema:v1",
  "policy_bundle_id": "policy_bundle:heuristic_matchup_baseline_v1",
  "controller_type": "headless_self_play",
  "rules_bundle_scope": {
    "match_mode": "exact",
    "ids": ["rules_bundle:preview_11e_q2"]
  },
  "descriptor_bundle_scope": {
    "match_mode": "exact",
    "ids": ["descriptor_bundle:preview_11e_q2"]
  },
  "event_policy_scope": {
    "match_mode": "exact",
    "ids": ["event_policy:gt_fixed_roster_v1"]
  },
  "components": {
    "matchup_evaluator": {
      "resolver_kind": "artifact",
      "resolver_ref": "artifact:matchup_evaluator:preview11e_capability_v1:20260414"
    },
    "playbook_selector": {
      "resolver_kind": "heuristic",
      "resolver_ref": "heuristic:identity_playbook:v1"
    },
    "roster_edit_ranker": {
      "resolver_kind": "heuristic",
      "resolver_ref": "heuristic:roster_edit_search:v1"
    }
  },
  "fallbacks": {
    "matchup_evaluator": ["heuristic:capability_matchup:v1"],
    "playbook_selector": ["heuristic:identity_playbook:v1"],
    "roster_edit_ranker": ["heuristic:roster_edit_search:v1"]
  },
  "required_feature_schema_ids": ["feature_schema:roster_matchup_v1"],
  "required_capability_schema_ids": ["capability_schema:build_capability_v1"],
  "created_from_commit": "0123456789abcdef0123456789abcdef01234567"
}
```
