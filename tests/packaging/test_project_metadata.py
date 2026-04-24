from __future__ import annotations

from importlib import import_module
from pathlib import Path
import tomllib


def _project_metadata() -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    return tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))


def test_project_targets_python_312_or_newer() -> None:
    metadata = _project_metadata()
    assert metadata["project"]["requires-python"] == ">=3.12"


def test_console_script_targets_are_importable() -> None:
    metadata = _project_metadata()
    scripts = dict(metadata["project"].get("scripts", {}) or {})

    assert scripts["warhammer40k-ai"] == "warhammer40k_ai.cli:main"
    assert scripts["warhammer40k-ai-network"] == "warhammer40k_ai.network.cli:main"

    for target in scripts.values():
        module_name, attr_name = target.split(":", 1)
        module = import_module(module_name)
        assert callable(getattr(module, attr_name))


def test_runtime_dependency_groups_are_split() -> None:
    metadata = _project_metadata()
    project = metadata["project"]
    dependencies = set(project.get("dependencies", []) or [])
    optional = project.get("optional-dependencies", {}) or {}

    assert "websockets==11.0.3" in dependencies
    assert "pytest" not in dependencies
    assert "pygame" not in dependencies
    assert "torch>=2.2,<3.0" not in dependencies

    assert "pytest" in set(optional["test"])
    assert "pygame" in set(optional["ui"])
    assert "torch>=2.2,<3.0" in set(optional["ml"])
