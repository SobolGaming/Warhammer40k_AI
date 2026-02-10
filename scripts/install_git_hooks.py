#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path
import logging
logger = logging.getLogger(__name__)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    hooks_path = repo_root / "scripts" / "githooks"
    if not hooks_path.exists():
        raise RuntimeError("scripts/githooks not found.")
    subprocess.run(
        ["git", "config", "core.hooksPath", "scripts/githooks"],
        check=True,
        cwd=repo_root,
    )
    if os.name != "nt":
        for hook in hooks_path.iterdir():
            if hook.is_file():
                hook.chmod(hook.stat().st_mode | 0o111)
    logger.info("Git hooks installed to scripts/githooks")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
