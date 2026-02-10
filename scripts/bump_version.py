#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
import logging
logger = logging.getLogger(__name__)

VERSION_PATH = Path(__file__).resolve().parents[1] / "src" / "warhammer40k_ai" / "version.py"


def _read_version() -> tuple[str, str]:
    content = VERSION_PATH.read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', content, re.M)
    if not match:
        raise RuntimeError("APP_VERSION not found in version.py")
    return match.group(1), content


def _parse_semver(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Unsupported version format: {version}. Expected MAJOR.MINOR.PATCH")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _format_version(major: int, minor: int, patch: int) -> str:
    return f"{major}.{minor}.{patch}"


def _bump(version: str, part: str) -> str:
    major, minor, patch = _parse_semver(version)
    if part == "major":
        return _format_version(major + 1, 0, 0)
    if part == "minor":
        return _format_version(major, minor + 1, 0)
    if part == "patch":
        return _format_version(major, minor, patch + 1)
    raise ValueError(f"Unknown bump part: {part}")


def _write_version(new_version: str, content: str) -> None:
    new_content, count = re.subn(
        r'^(APP_VERSION\s*=\s*["\'])([^"\']+)(["\'])',
        rf"\g<1>{new_version}\g<3>",
        content,
        flags=re.M,
    )
    if count != 1:
        raise RuntimeError("Failed to update APP_VERSION in version.py")
    VERSION_PATH.write_text(new_content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump Warhammer40k_AI app version")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--major", action="store_true", help="Bump major version")
    group.add_argument("--minor", action="store_true", help="Bump minor version")
    group.add_argument("--patch", action="store_true", help="Bump patch version")
    group.add_argument("--set", dest="set_version", help="Set explicit version (MAJOR.MINOR.PATCH)")
    args = parser.parse_args()

    current_version, content = _read_version()
    if args.set_version:
        _parse_semver(args.set_version)
        new_version = args.set_version
    elif args.major:
        new_version = _bump(current_version, "major")
    elif args.minor:
        new_version = _bump(current_version, "minor")
    else:
        new_version = _bump(current_version, "patch")

    if new_version == current_version:
        logger.info(f"Version unchanged: {current_version}")
        return

    _write_version(new_version, content)
    logger.info(f"Version updated: {current_version} -> {new_version}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
