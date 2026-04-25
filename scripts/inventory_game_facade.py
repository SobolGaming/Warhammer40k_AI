#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME_PATH = ROOT / "src/warhammer40k_ai/engine/game.py"
ENGINE_PATH = ROOT / "src/warhammer40k_ai/engine"
MIXINS_PATH = ROOT / "src/warhammer40k_ai/engine/game_mixins"
SERVICE_FILES = (
    "game_charge.py",
    "game_commands.py",
    "game_faction_state.py",
    "game_fight.py",
    "game_scoring.py",
)


def _line_count(path: Path) -> int:
    return len(path.read_text().splitlines())


def _public_method_count(path: Path) -> int:
    module = ast.parse(path.read_text())
    game_class = _game_class(module)
    return sum(
        1
        for node in game_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    )


def _game_class(module: ast.Module) -> ast.ClassDef:
    return next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "Game"
    )


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _base_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _game_base_names(path: Path) -> list[str]:
    module = ast.parse(path.read_text())
    game_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "Game"
    )
    return [
        name
        for name in (_base_name(base) for base in game_class.bases)
        if name
    ]


def _class_names(path: Path) -> set[str]:
    module = ast.parse(path.read_text())
    return {
        node.name
        for node in module.body
        if isinstance(node, ast.ClassDef)
    }


def main() -> None:
    game_bases = _game_base_names(GAME_PATH)
    print(f"game.py lines: {_line_count(GAME_PATH)}")
    print(f"Game public methods in game.py: {_public_method_count(GAME_PATH)}")
    print(f"Game base classes: {', '.join(game_bases) if game_bases else '(none)'}")
    print("Inherited game_mixins line counts:")
    for path in sorted(MIXINS_PATH.glob("*.py")):
        if not (_class_names(path) & set(game_bases)):
            continue
        print(f"  {path.name}: {_line_count(path)}")
    print("Extracted game service line counts:")
    for name in SERVICE_FILES:
        path = ENGINE_PATH / name
        if path.exists():
            print(f"  {path.name}: {_line_count(path)}")


if __name__ == "__main__":
    main()
