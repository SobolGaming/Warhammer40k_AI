from __future__ import annotations

from collections.abc import Mapping

from .deployment_candidates import layout_candidates
from .mission_selection import get_mission_pack


def normalize_layout_selection(layout: object, *, allowed_layouts) -> int:
    if isinstance(layout, Mapping):
        if "layout" not in layout:
            raise ValueError("Deployment layout mapping must contain 'layout'.")
        layout = layout.get("layout")
    selected_layout = int(layout)
    if selected_layout not in layout_candidates(allowed_layouts):
        raise ValueError(f"Unsupported terrain layout {selected_layout}.")
    return selected_layout


def validate_selected_mission_choice(choice: Mapping[str, object], *, layout: object) -> tuple[object, int]:
    selection = dict(choice or {})
    pack = get_mission_pack(str(selection.get("pack_id") or selection.get("mission_pack_id") or ""))
    deployment_definition = pack.deployment_by_id(str(selection.get("deployment_definition_id", "") or ""))
    allowed_layouts = list(selection.get("layouts", []) or deployment_definition.allowed_layouts)
    selected_layout = normalize_layout_selection(layout, allowed_layouts=allowed_layouts)
    return deployment_definition, selected_layout
