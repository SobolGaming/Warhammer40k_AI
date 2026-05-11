#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from warhammer40k_ai.ml.limited_use_sources import summarize_limited_use_source_entries


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan Wahapedia JSON sources for once-per-battle and other limited-use rules text."
    )
    parser.add_argument("--repo-root", default=".", help="Repository root containing wahapedia_data/.")
    parser.add_argument("--output", default="", help="Optional JSON output path.")
    parser.add_argument(
        "--no-entries",
        action="store_true",
        help="Omit individual matching entries from the JSON output.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = summarize_limited_use_source_entries(repo_root=Path(args.repo_root).expanduser())
    if args.no_entries:
        summary = dict(summary)
        summary.pop("entries", None)
    text = json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True)
    output = str(args.output or "").strip()
    if output:
        path = Path(output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"Limited-use source scan: {path}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
