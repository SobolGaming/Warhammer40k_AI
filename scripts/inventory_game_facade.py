#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME_PATH = ROOT / "src/warhammer40k_ai/engine/game.py"
MIXINS_PATH = ROOT / "src/warhammer40k_ai/engine/game_mixins"


def _line_count(path: Path) -> int:
    return len(path.read_text().splitlines())


def _public_method_count(path: Path) -> int:
    module = ast.parse(path.read_text())
    game_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "Game"
    )
    return sum(
        1
        for node in game_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    )


def main() -> None:
    print(f"game.py lines: {_line_count(GAME_PATH)}")
    print(f"Game public methods in game.py: {_public_method_count(GAME_PATH)}")
    print("game_mixins line counts:")
    for path in sorted(MIXINS_PATH.glob("*.py")):
        print(f"  {path.name}: {_line_count(path)}")


if __name__ == "__main__":
    main()
