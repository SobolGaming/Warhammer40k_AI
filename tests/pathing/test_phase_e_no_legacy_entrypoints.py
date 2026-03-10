from __future__ import annotations

import ast
from pathlib import Path


_FORBIDDEN = {
    "unified_pathfinding",
    "get_individual_model_movement_path",
    "get_movement_path_preview",
    "get_charge_movement_path",
    "get_unit_movement_path_preview",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_phase_e_src_has_no_legacy_pathing_entrypoint_imports_or_calls() -> None:
    src_root = _repo_root() / "src"
    violations: list[str] = []

    for file_path in sorted(src_root.rglob("*.py")):
        source = file_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "warhammer40k_ai.utility.calcs":
                for alias in node.names:
                    if alias.name in _FORBIDDEN:
                        violations.append(f"{file_path}: import {alias.name}")
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in _FORBIDDEN:
                    violations.append(f"{file_path}:{node.lineno} calls {func.id}")
                if isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN:
                    violations.append(f"{file_path}:{node.lineno} calls .{func.attr}")

    assert not violations, "Legacy pathing entrypoints detected:\n" + "\n".join(violations)
