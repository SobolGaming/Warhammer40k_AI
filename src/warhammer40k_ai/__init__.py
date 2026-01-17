"""
warhammer40k_ai package bootstrap.

This project runs on Windows where the default console encoding can be cp1252. A lot of
engine/debug output includes Unicode (e.g. icons) which can raise UnicodeEncodeError
during automated tests. Reconfigure stdout/stderr to UTF-8 (with replacement) early so
prints/logging never crash the engine.
"""

from __future__ import annotations

import sys


def _reconfigure_stream(stream) -> None:
    try:
        # Python 3.7+: TextIOBase.reconfigure
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # Never fail import due to console quirks.
        return


_reconfigure_stream(sys.stdout)
_reconfigure_stream(sys.stderr)


