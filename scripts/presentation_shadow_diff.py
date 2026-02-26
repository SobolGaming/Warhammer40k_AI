#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_envelopes(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list of envelopes.")
    result: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError(f"{path} contains a non-dict envelope entry.")
        result.append(entry)
    return result


def _normalize(entry: dict) -> dict:
    return {
        "sequence_id": int(entry.get("sequence_id", -1)),
        "payload": dict(entry.get("payload", {}) or {}),
    }


def compare_streams(left: list[dict], right: list[dict]) -> list[str]:
    issues: list[str] = []
    if len(left) != len(right):
        issues.append(f"Length mismatch: left={len(left)} right={len(right)}")
    for idx, (l_raw, r_raw) in enumerate(zip(left, right)):
        l = _normalize(l_raw)
        r = _normalize(r_raw)
        if l != r:
            issues.append(f"Envelope mismatch at index {idx}: left={l} right={r}")
            break
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two presentation envelope streams.")
    parser.add_argument("left", help="Path to left JSON envelope list")
    parser.add_argument("right", help="Path to right JSON envelope list")
    args = parser.parse_args()

    left = _load_envelopes(Path(args.left))
    right = _load_envelopes(Path(args.right))
    issues = compare_streams(left, right)
    if issues:
        for line in issues:
            print(line)
        return 1
    print(f"OK: streams match ({len(left)} envelopes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
