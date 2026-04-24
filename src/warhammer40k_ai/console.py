from __future__ import annotations

import sys
from typing import TextIO


def _reconfigure_stream(stream: TextIO) -> None:
    try:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        return


def configure_console_encoding() -> None:
    """Use UTF-8 for CLI output on consoles that support reconfiguration."""

    for stream in (sys.stdout, sys.stderr):
        _reconfigure_stream(stream)
