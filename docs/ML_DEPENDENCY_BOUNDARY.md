# ML Dependency Boundary

This document defines the dedicated ML onboarding boundary for the engine.

Primary artifacts:
- `src/warhammer40k_ai/ml/dependency_boundary.py`
- `src/warhammer40k_ai/ml/__init__.py`
- `src/warhammer40k_ai/ml/interfaces.py`
- `src/warhammer40k_ai/ml/registry.py`
- `src/warhammer40k_ai/ml/policy_bundle.py`
- `pyproject.toml` (`project.optional-dependencies.ml`)
- `tests/rules/test_ml_dependency_boundary.py`
- `tests/ai/test_ml_policy_bundle.py`

## Core Policy

- Core engine/runtime dependencies must remain ML-framework free.
- ML libraries are allowed only as optional extras, never in core dependencies.
- ML-facing code is isolated under `src/warhammer40k_ai/ml/`.
- Engine and replay imports must work when ML extras are not installed.

Blocked from core dependency lane:
- `torch`
- `torchrl`
- `torch-geometric`
- `ray`
- `wandb`

## Optional Extra

Install ML stack only when needed:

```bash
uv sync --extra ml
```

`pyproject.toml` exposes this extra as `project.optional-dependencies.ml`.

Recommended full setup flow from repository root:

```bash
uv sync --extra ml
```

Verification command:

```bash
uv run python -c "from warhammer40k_ai.ml import detect_ml_dependency_status; print(detect_ml_dependency_status().to_dict())"
```

Healthy environment expectation:
- `ready` is `True`
- `missing_packages` is empty

## Runtime Guard

`require_ml_dependencies()` enforces an actionable runtime guard for ML entrypoints:
- checks whether optional ML modules are importable
- raises `MLDependencyBoundaryError` with install guidance if missing

`detect_ml_dependency_status()` returns a deterministic status payload:
- `ready`
- `missing_packages`
- `available_packages`

Framework-free registry and bundle behavior now lives alongside the dependency
boundary:
- `interfaces.py` defines protocol-only runtime contracts for candidate ranking,
  matchup evaluation, playbook selection, artifact resolution, and bundle loading.
- `registry.py` loads and validates manifest JSON without importing ML extras.
- `policy_bundle.py` resolves heuristic-only bundles directly and resolves
  known framework-free artifact components directly. Unknown artifact
  architectures still resolve to manifest-backed references until their runtime
  backend lands.
- `linear_candidate_ranker.py` provides the first base-dependency learned
  candidate ranker. It is a sparse linear scorer over DecisionRecord candidate
  semantic metadata and deterministic hashed categorical features; it does not
  require the `ml` optional extra. The exported
  `feature_schema:decision_candidate_semantics_v2` feature set intentionally
  excludes runtime entity ids such as `action_id`, `unit_id`, and `target_unit_id`
  from learned hash buckets, and instead hashes stable semantic fields such as
  action type, candidate label, ability name, tool id, phase, and selection
  purpose.
- `imitation_training.py` trains that ranker from relabeled DecisionRecords using
  a game-id split and exports artifact manifests plus a model-backed policy
  bundle under `models/`.

First offline imitation-training command:

```bash
uv run python scripts/train_imitation_candidate_ranker.py \
  --records data/training_gate_20260507_100match_we_aeldari/decision_records_relabeled.json \
  --training-manifest data/training_gate_20260507_100match_we_aeldari/training_manifest.json \
  --models-root models \
  --run-id linear_imitation_we_aeldari_100_v1 \
  --policy-bundle-id policy_bundle:linear_imitation_we_aeldari_100_v1
```

The exported bundle can be evaluated through the normal policy-bundle gate:

```bash
uv run python scripts/evaluate_policy_bundle.py \
  --policy-bundle policy_bundle:linear_imitation_we_aeldari_100_v1 \
  --models-root models \
  --player1-army army_lists/WE_Daemonkin_2000.txt \
  --player2-army army_lists/Aeldari_Warhost_2000.txt
```

## Regression Coverage

`tests/rules/test_ml_dependency_boundary.py` validates:
- dependency name normalization and forbidden-core scanning
- deterministic dependency status shape
- actionable runtime error text when ML extras are missing
- `pyproject.toml` exposes `ml` extras while core dependencies remain ML-free
- engine/replay imports stay functional without ML stack
- engine/replay import paths do not load forbidden ML modules as a side effect

`tests/ai/test_ml_policy_bundle.py` validates:
- heuristic-only bundle manifests load from JSON with zero ML extras installed
- bundle components resolve to concrete heuristic handlers through the registry
- manifest-backed artifact references resolve without checkpoint loading
- framework-free linear candidate-ranker artifacts resolve to runtime rankers
- unknown artifact ids fail with clear diagnostics

`tests/ai/test_imitation_training.py` validates:
- game-id train/validation splitting
- artifact and bundle export for a learned candidate ranker
- loading the exported bundle through `AIPolicyOrchestrator`
