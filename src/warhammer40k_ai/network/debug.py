from __future__ import annotations

import os
from typing import Any

_DEBUG_ENV = "W40K_NETWORK_LOG"


def network_debug_enabled() -> bool:
    value = os.getenv(_DEBUG_ENV, "")
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _shorten(value: Any, limit: int = 200) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)]}..."


def log_network(event: str, **fields: Any) -> None:
    if not network_debug_enabled():
        return
    parts = []
    for key, val in fields.items():
        if val is None:
            continue
        parts.append(f"{key}={_shorten(val)}")
    if parts:
        print(f"[network] {event} " + " ".join(parts))
    else:
        print(f"[network] {event}")
