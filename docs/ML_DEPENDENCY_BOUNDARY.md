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
pip install "warhammer40k_ai[ml]"
```

`pyproject.toml` exposes this extra as `project.optional-dependencies.ml`.

Recommended full setup flow from repository root:

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux/macOS
# source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[ml]"
```

Verification command:

```bash
python -c "from warhammer40k_ai.ml import detect_ml_dependency_status; print(detect_ml_dependency_status().to_dict())"
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
  artifact components to manifest-backed references until backend-specific
  runtimes land.

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
- unknown artifact ids fail with clear diagnostics
