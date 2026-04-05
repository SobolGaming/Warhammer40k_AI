from __future__ import annotations

from pathlib import Path
import runpy
import setuptools

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


def test_setup_exposes_ml_extra_and_keeps_core_install_requires_ml_free(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _capture_setup(*args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(setuptools, "setup", _capture_setup)
    repo_root = Path(__file__).resolve().parents[2]
    runpy.run_path(str(repo_root / "setup.py"), run_name="__main__")

    extras = dict(captured.get("extras_require", {}) or {})
    assert "ml" in extras
    ml_extra = [str(item) for item in list(extras["ml"] or [])]
    assert any(dep.startswith("torch") for dep in ml_extra)
    assert any(dep.startswith("ray") for dep in ml_extra)
    assert any(dep.startswith("wandb") for dep in ml_extra)

    install_requires = [str(item) for item in list(captured.get("install_requires", []) or [])]
    assert find_forbidden_core_dependencies(install_requires) == []


def test_engine_and_replay_import_without_ml_stack() -> None:
    from warhammer40k_ai.engine.game import Game  # noqa: F401
    from warhammer40k_ai.engine.replay import replay_decision_records  # noqa: F401
