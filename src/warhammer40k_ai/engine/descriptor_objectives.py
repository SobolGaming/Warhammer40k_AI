from __future__ import annotations

from typing import Any

from ..battlefield.objective_sites import resolve_objective_id, resolve_objective_site
from .descriptor_bundle import CompiledDescriptor, descriptor_id, iter_objectives, json_safe


def build_objective_descriptor_payload(objective: object) -> dict[str, Any]:
    objective_id = resolve_objective_id(objective)
    site = resolve_objective_site(objective)
    if site is None:
        return json_safe(
            {
                "objective_id": objective_id,
                "geometry": {},
                "control_region": {},
                "score_source_bindings": [],
                "transform_flags": {},
                "controller_player_id": "",
            }
        )

    if hasattr(site, "to_state_entry"):
        state_entry = dict(site.to_state_entry(objective_id=objective_id))
        controller_player_id = str(state_entry.get("controller_player_id", "") or "")
        transform_flags = {
            "removed": bool(getattr(site, "removed", False)),
            "is_hazard": bool(getattr(site, "is_hazard", False)),
            "terraformed_by_player_id": str(getattr(getattr(site, "terraformed_by", None), "id", "") or ""),
            "cleansed_by_player_id": str(getattr(getattr(site, "cleansed_by", None), "id", "") or ""),
        }
        payload = {
            "objective_id": objective_id,
            "objective_site_id": str(state_entry.get("objective_site_id", "") or ""),
            "site_kind": str(state_entry.get("site_kind", "") or ""),
            "geometry": dict(state_entry.get("geometry", {}) or {}),
            "control_region": dict(state_entry.get("control_region", {}) or {}),
            "score_source_bindings": [
                str(source.get("score_source_id", "") or "")
                for source in list(state_entry.get("score_sources", []) or [])
            ],
            "sticky_behavior": {
                "sticky_enabled": bool(getattr(site, "sticky_controller", None) is not None),
                "sticky_controller_player_id": str(getattr(getattr(site, "sticky_controller", None), "id", "") or ""),
            },
            "transform_flags": transform_flags,
            "controller_player_id": controller_player_id,
        }
        return json_safe(payload)

    controller = getattr(site, "controlling_player", None)
    payload = {
        "objective_id": objective_id,
        "objective_site_id": str(getattr(site, "id", objective_id) or objective_id),
        "site_kind": "MARKER",
        "geometry": {
            "kind": "MARKER",
            "position": [
                float(getattr(site, "x", 0.0) or 0.0),
                float(getattr(site, "y", 0.0) or 0.0),
                float(getattr(site, "z", 0.0) or 0.0),
            ],
            "control_radius": float(getattr(site, "control_radius", 0.0) or 0.0),
        },
        "control_region": {
            "region_id": f"region:objective:{objective_id}",
            "kind": "OBJECTIVE_CONTROL_RADIUS",
            "center": [
                float(getattr(site, "x", 0.0) or 0.0),
                float(getattr(site, "y", 0.0) or 0.0),
                float(getattr(site, "z", 0.0) or 0.0),
            ],
            "radius": float(getattr(site, "control_radius", 0.0) or 0.0),
        },
        "score_source_bindings": [f"score_source:objective:{objective_id}"],
        "sticky_behavior": {
            "sticky_enabled": bool(getattr(site, "sticky_controller", None) is not None),
            "sticky_controller_player_id": str(getattr(getattr(site, "sticky_controller", None), "id", "") or ""),
        },
        "transform_flags": {
            "removed": bool(getattr(site, "removed", False)),
            "is_hazard": bool(getattr(site, "is_hazard", False)),
            "terraformed_by_player_id": str(getattr(getattr(site, "terraformed_by", None), "id", "") or ""),
            "cleansed_by_player_id": str(getattr(getattr(site, "cleansed_by", None), "id", "") or ""),
        },
        "controller_player_id": str(getattr(controller, "id", "") or ""),
    }
    return json_safe(payload)


def compile_objective_descriptors(game: object) -> tuple[CompiledDescriptor, ...]:
    descriptors: list[CompiledDescriptor] = []
    for objective in iter_objectives(game):
        payload = build_objective_descriptor_payload(objective)
        descriptors.append(
            CompiledDescriptor(
                family="ObjectiveDescriptor",
                descriptor_id=descriptor_id("objective_descriptor", payload),
                payload=payload,
            )
        )
    descriptors.sort(key=lambda descriptor: str(descriptor.descriptor_id))
    return tuple(descriptors)


__all__ = ["build_objective_descriptor_payload", "compile_objective_descriptors"]
