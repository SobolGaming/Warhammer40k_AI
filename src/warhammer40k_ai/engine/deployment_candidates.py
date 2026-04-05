from __future__ import annotations

from typing import Iterable


def layout_candidates(allowed_layouts: Iterable[int] | None) -> list[int]:
    values = sorted({int(value) for value in list(allowed_layouts or [])})
    if not values:
        raise ValueError("Deployment selection requires at least one terrain layout.")
    return values
