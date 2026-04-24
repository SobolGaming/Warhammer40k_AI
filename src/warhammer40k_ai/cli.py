from __future__ import annotations

import argparse
from collections.abc import Sequence

from .console import configure_console_encoding
from .version import APP_VERSION


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="warhammer40k-ai",
        description="Warhammer 40,000 rules engine utilities.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"warhammer40k-ai {APP_VERSION}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_console_encoding()
    parser = _build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
