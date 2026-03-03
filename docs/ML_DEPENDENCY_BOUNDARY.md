# ML Dependency Boundary

This document defines the dedicated ML onboarding boundary for the engine.

Primary artifacts:
- `src/warhammer40k_ai/ml/dependency_boundary.py`
- `src/warhammer40k_ai/ml/__init__.py`
- `setup.py` (`extras_require["ml"]`)
- `tests/test_ml_dependency_boundary.py`

## Core Policy

- Core engine/runtime dependencies must remain ML-framework free.
- ML libraries are allowed only as optional extras, never in core `install_requires`.
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

`setup.py` exposes this extra as `extras_require["ml"]`.

Recommended full setup flow from repository root:

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux/macOS
# source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
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

## Regression Coverage

`tests/test_ml_dependency_boundary.py` validates:
- dependency name normalization and forbidden-core scanning
- deterministic dependency status shape
- actionable runtime error text when ML extras are missing
- `setup.py` exposes `ml` extras while core `install_requires` remains ML-free
- engine/replay imports stay functional without ML stack
