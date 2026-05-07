# Tournament Evaluation Pipeline

This document defines the canonical PR-MUSTER-006 evaluation path for policy
bundles and tournament rosters.

Related docs:
- `docs/AI_MUSTERING_TOURNAMENT_ARCHITECTURE.md`
- `docs/TOURNAMENT_EVALUATION_OBJECTIVE.md`
- `docs/ML_ARTIFACT_REGISTRY.md`
- `docs/ML_DEPENDENCY_BOUNDARY.md`
- `docs/BUILD_CAPABILITY_SCHEMA.md`
- `docs/TOURNAMENT_FIELD_SCHEMA.md`
- `docs/MUSTERING_DATA_SPEC.md`

## Purpose

PR-MUSTER-006 standardizes one auditable evaluation path for:
- a `PolicyBundle` on its own
- a fixed tournament roster conditioned on an `ArmyBlueprint`, an
  `EventPolicyDescriptor`, and a `TournamentFieldDistribution`

The pipeline defines what "headless fixed" means for deterministic smoke
validation and what "training-grade" means for stricter dataset gating.

## Entry Points

The canonical entry scripts are:
- `scripts/evaluate_policy_bundle.py`
- `scripts/evaluate_tournament_roster.py`

Both scripts call the same shared runtime module:
- `src/warhammer40k_ai/ml/evaluation_pipeline.py`

The shared path composes existing infrastructure instead of introducing a
parallel evaluation stack:
1. `scripts/run_headless_self_play.py`
2. strict replay audit through `ReplayStoreReader.reconstruct_game_at_decision(..., strict=True)`
3. `relabel_decision_records(...)`
4. `build_training_manifest(...)`
5. gate validation and report generation

## Evaluation Modes

Two evaluation modes are supported.

### `headless_fixed`

Use `headless_fixed` for deterministic smoke evaluation. This mode is intended
to answer:
- does headless self-play complete
- do saved replay sessions round-trip under strict replay
- do relabeled records build a minimally coherent manifest

The fixed gate profile for this mode is:
- `headless_fixed_v1`

`headless_fixed_v1` requires:
- at least one decision record
- complete semantic candidate metadata
- complete relabel status coverage
- game ids present on records

### `training_grade`

Use `training_grade` when the run must meet the canonical pre-ML training data
quality bar.

The gate profile for this mode is:
- `pre_ml_baseline_v1`

If `pre_ml_baseline_v1` fails, the evaluation fails.

## Report Directory Contract

Each evaluation run emits an auditable report directory under
`models/reports/` unless an explicit `--report-dir` is supplied.

The report directory contains:
- `bundle_resolution.json`
- `self_play_report.json`
- `self_play_stdout.txt`
- `self_play_stderr.txt`
- `decision_records_raw.json`
- `decision_records_relabeled.json`
- `training_manifest.json`
- `replay_report.json`
- `gate_report.json`
- `per_match.csv`
- `summary.json`

Large DecisionRecord corpora are written and consumed as streamed JSON arrays.
`decision_records_raw.json` is emitted one game at a time by self-play, and
`decision_records_relabeled.json` plus `training_manifest.json` are produced in
a single streaming relabel/manifest pass. Evaluation code must not load the full
raw or relabeled corpus into memory for gate checks.

Tournament-roster evaluation also writes:
- `roster_context.json`
- `muster_record.json`
- `mustering_manifest.json`

`summary.json` links these mustering artifacts through
`roster_evaluation.muster_record_path`,
`roster_evaluation.mustering_manifest_path`, and
`roster_evaluation.lineage`. That lineage captures the rules bundle,
build-capability profile, capability schema, field distribution, event policy,
policy bundle, and descriptor-bundle scope used for the run.

`summary.json` exposes the required utility decomposition:
- completion rate
- replay pass rate
- manifest gate status
- VP / win metrics
- no-progress ratio
- timeout or max-phase-step exit ratio across requested games when failure counts
  are observable
- controller complexity metrics

## Exit Semantics

Bundle and roster evaluation are success-only when all of the following hold:
- headless self-play exits with return code `0`
- strict replay audit passes
- the active manifest gate passes

The scripts return exit code `1` when replay audit fails or when
`pre_ml_baseline_v1` fails under `training_grade`.

Roster evaluation does not soften these failures. A tournament-roster run fails
if self-play fails, replay fails, or the manifest gate fails.

## Heuristic-Only Bundles

Heuristic-only bundles are a first-class supported path. The loader resolves
framework-free default heuristics without requiring `warhammer40k_ai[ml]` extras
to be installed.

This keeps evaluation usable for:
- headless CI smoke runs
- replay and gate regression checks
- local tournament-evaluation experiments that do not ship learned artifacts

Schema-selection note:
- evaluation bundles may intentionally request `capability_schema:build_capability_v2`
  for preview combat studies while leaving `build_capability_v1` as the default
  portable descriptor schema.

## Roster Context Note

`scripts/evaluate_tournament_roster.py` currently uses runtime army files for
the actual self-play match execution. The supplied `ArmyBlueprint`,
`EventPolicyDescriptor`, `TournamentFieldDistribution`, and snapshot-scoped
`rules_data_dir` are used to compile deterministic roster context and optional
heuristic matchup evaluation into `roster_context.json` and `summary.json`.

This means:
- runtime self-play still follows the authored army files
- build-capability and matchup provenance are snapshot-scoped and deterministic
- the report already captures the fixed-roster evaluation context required by
  the tournament ABI

That boundary is intentional for this milestone. It keeps replay-grade
evaluation auditable without introducing a second mustering path for the live
self-play script.
