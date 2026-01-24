#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Optional, Tuple

VERSION_PATH = "src/warhammer40k_ai/version.py"


def _run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _check_staged() -> bool:
    staged = _split_lines(_run_git(["diff", "--cached", "--name-only"]))
    if not staged:
        return True
    if all(path == VERSION_PATH for path in staged):
        return True
    return VERSION_PATH in staged


def _check_range(range_spec: str) -> Tuple[bool, Optional[str]]:
    try:
        commits = _split_lines(_run_git(["rev-list", range_spec]))
    except subprocess.CalledProcessError:
        return True, None
    for commit in commits:
        files = _split_lines(_run_git(["diff-tree", "--no-commit-id", "--name-only", "-r", commit]))
        if not files:
            continue
        if VERSION_PATH not in files:
            return False, commit
    return True, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate version bumps for commits/pushes")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="Check staged files")
    group.add_argument("--range", dest="range_spec", help="Check commit range")
    args = parser.parse_args()

    if args.staged:
        if not _check_staged():
            print(
                "ERROR: Version bump required. Stage changes to src/warhammer40k_ai/version.py "
                "whenever committing non-version files.",
                file=sys.stderr,
            )
            sys.exit(1)
        return

    ok, bad_commit = _check_range(str(args.range_spec))
    if not ok:
        print(
            "ERROR: Version bump required in every commit being pushed. "
            f"Missing {VERSION_PATH} change in commit {bad_commit}.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
