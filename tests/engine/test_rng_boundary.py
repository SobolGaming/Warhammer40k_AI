import ast
from pathlib import Path


CORE_DIRS = (
    "src/warhammer40k_ai/battlefield",
    "src/warhammer40k_ai/engine",
    "src/warhammer40k_ai/rules",
    "src/warhammer40k_ai/units",
)
ALLOWED_RANDOM_FILES = {
    Path("src/warhammer40k_ai/engine/random_source.py"),
    Path("src/warhammer40k_ai/utility/RNG.py"),
    Path("src/warhammer40k_ai/utility/rng.py"),
}
BANNED_RANDOM_CALLS = {"choice", "randint", "randrange", "random", "sample", "shuffle", "uniform"}


def test_core_runtime_does_not_use_global_random_calls():
    repo_root = Path(__file__).resolve().parents[2]
    violations: list[str] = []

    for core_dir in CORE_DIRS:
        for path in (repo_root / core_dir).rglob("*.py"):
            rel_path = path.relative_to(repo_root)
            if rel_path in ALLOWED_RANDOM_FILES:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(rel_path))
            random_aliases = set()
            direct_random_imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "random":
                            random_aliases.add(alias.asname or alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module == "random":
                    for alias in node.names:
                        direct_random_imports.add(alias.asname or alias.name)
            if direct_random_imports:
                violations.append(f"{rel_path}: from random import {sorted(direct_random_imports)}")
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id in random_aliases
                    and func.attr in BANNED_RANDOM_CALLS
                ):
                    violations.append(f"{rel_path}:{node.lineno}: random.{func.attr}()")

    assert violations == []
