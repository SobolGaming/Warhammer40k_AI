from __future__ import annotations

from .deployment_candidates import layout_candidates


def default_layout_for_selection(allowed_layouts) -> int:
    return layout_candidates(allowed_layouts)[0]
