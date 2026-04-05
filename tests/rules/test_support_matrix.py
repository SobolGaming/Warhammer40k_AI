from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
import unittest


CASE_DIR = Path(__file__).resolve().parent / "support_matrix_cases"
CASE_PATTERN = "case_support_matrix_*.py"


def _load_case_module(path: Path, ordinal: int):
    module_name = f"tests.rules.support_matrix_cases.{path.stem}_{ordinal}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load support matrix case module from {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _export_case_tests() -> None:
    for ordinal, path in enumerate(sorted(CASE_DIR.glob(CASE_PATTERN))):
        module = _load_case_module(path, ordinal)
        stem = path.stem.replace("-", "_")

        for name, obj in vars(module).items():
            if inspect.isfunction(obj) and name.startswith("test_"):
                export_name = f"test_{stem}__{name[5:]}"
                globals()[export_name] = obj
                continue

            if (
                inspect.isclass(obj)
                and issubclass(obj, unittest.TestCase)
                and name.startswith("Test")
            ):
                export_name = f"{name}_{stem}"
                globals()[export_name] = obj


_export_case_tests()
