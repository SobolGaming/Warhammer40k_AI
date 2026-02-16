from __future__ import annotations

import os
import threading
from typing import Dict

_TRUTHY = {"1", "true", "yes", "on"}
_ENABLED = str(os.getenv("WH40K_REGEX_METRICS", "") or "").strip().lower() in _TRUTHY
_COUNTS: Dict[str, int] = {}
_LOCK = threading.RLock()


def is_enabled() -> bool:
    with _LOCK:
        return bool(_ENABLED)


def enable(*, reset: bool = False) -> None:
    global _ENABLED
    with _LOCK:
        _ENABLED = True
        if reset:
            _COUNTS.clear()


def disable() -> None:
    global _ENABLED
    with _LOCK:
        _ENABLED = False


def reset() -> None:
    with _LOCK:
        _COUNTS.clear()


def increment(key: str, amount: int = 1) -> None:
    if not key:
        return
    with _LOCK:
        if not _ENABLED:
            return
        current = int(_COUNTS.get(key, 0) or 0)
        _COUNTS[key] = current + max(0, int(amount or 0))


def snapshot() -> Dict[str, int]:
    with _LOCK:
        return {str(k): int(v) for k, v in _COUNTS.items()}


def format_report() -> str:
    data = snapshot()
    if not data:
        return "Regex hotspot counters: no captured invocations.\n"

    lines = ["Regex hotspot counters (descending):"]
    for key, value in sorted(data.items(), key=lambda item: (-int(item[1]), item[0])):
        lines.append(f"- {key}: {int(value)}")
    lines.append("")
    return "\n".join(lines)

