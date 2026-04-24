from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tomllib

import warhammer40k_ai.ml.dependency_boundary as dependency_boundary
from warhammer40k_ai.ml.dependency_boundary import (
    MLDependencyBoundaryError,
    detect_ml_dependency_status,
    find_forbidden_core_dependencies,
    normalize_dependency_name,
    require_ml_dependencies,
)


def test_normalize_dependency_name_handles_versions_and_extras() -> None:
    assert normalize_dependency_name("torch>=2.2,<3.0") == "torch"
    assert normalize_dependency_name("ray[rllib]>=2.0") == "ray"
    assert normalize_dependency_name("torch_geometric==2.6.1") == "torch-geometric"
    assert normalize_dependency_name("   ") == ""


def test_find_forbidden_core_dependencies_flags_ml_libraries() -> None:
    deps = [
        "numpy>=2.0",
        "torch>=2.2",
        "ray[rllib]>=2.0",
        "requests==2.31.0",
    ]
    found = find_forbidden_core_dependencies(deps)
    assert found == ["ray", "torch"]


def test_detect_ml_dependency_status_is_deterministic_shape() -> None:
    first = detect_ml_dependency_status().to_dict()
    second = detect_ml_dependency_status().to_dict()
    assert first == second
    assert "ready" in first
    assert "missing_packages" in first
    assert "available_packages" in first


def test_require_ml_dependencies_raises_actionable_error_when_missing(monkeypatch) -> None:
    def _always_missing(_name: str):
        return None

    monkeypatch.setattr(dependency_boundary.importlib.util, "find_spec", _always_missing)
    try:
        require_ml_dependencies()
    except MLDependencyBoundaryError as exc:
        message = str(exc)
        assert "warhammer40k_ai[ml]" in message
        assert "missing:" in message
    else:
        raise AssertionError("Expected MLDependencyBoundaryError when ML imports are unavailable")


def test_pyproject_exposes_ml_extra_and_keeps_core_dependencies_ml_free() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    metadata = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]

    extras = dict(project.get("optional-dependencies", {}) or {})
    assert "ml" in extras
    ml_extra = [str(item) for item in list(extras["ml"] or [])]
    assert any(dep.startswith("torch") for dep in ml_extra)
    assert any(dep.startswith("ray") for dep in ml_extra)
    assert any(dep.startswith("wandb") for dep in ml_extra)

    dependencies = [str(item) for item in list(project.get("dependencies", []) or [])]
    assert find_forbidden_core_dependencies(dependencies) == []


def test_engine_and_replay_import_without_ml_stack() -> None:
    from warhammer40k_ai.engine.game import Game  # noqa: F401
    from warhammer40k_ai.engine.replay import replay_decision_records  # noqa: F401
    from warhammer40k_ai.ml import JSONPolicyBundleLoader  # noqa: F401
    from warhammer40k_ai.ml import HeuristicRegistry  # noqa: F401


def test_engine_and_replay_imports_do_not_load_forbidden_ml_modules() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = """
import sys

from warhammer40k_ai.engine.game import Game  # noqa: F401
from warhammer40k_ai.engine.replay import replay_decision_records  # noqa: F401
from warhammer40k_ai.ml import HeuristicRegistry  # noqa: F401
from warhammer40k_ai.ml import JSONPolicyBundleLoader  # noqa: F401

forbidden = {"torch", "torchrl", "torch_geometric", "ray", "wandb"}
loaded = sorted(name for name in sys.modules if name.split(".", 1)[0] in forbidden)
if loaded:
    raise SystemExit(",".join(loaded))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
