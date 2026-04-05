from __future__ import annotations

from typing import Any

from .descriptor_bundle import CompiledDescriptor, descriptor_id, iter_objectives, json_safe, safe_float


def build_objective_descriptor_payload(objective: object) -> dict[str, Any]:
    objective_id = str(getattr(objective, "id", "") or "")
    location = getattr(objective, "location", None)
    marker = location if location is not None else objective
    controller = getattr(marker, "controlling_player", None)
    sticky_controller = getattr(marker, "sticky_controller", None)
    removed = bool(getattr(marker, "removed", False))
    terraformed_by = getattr(marker, "terraformed_by", None)
    cleansed_by = getattr(marker, "cleansed_by", None)
    is_hazard = bool(getattr(marker, "is_hazard", False))
    payload = {
        "objective_id": objective_id,
        "geometry": {
            "position": [
                safe_float(getattr(marker, "x", 0.0)),
                safe_float(getattr(marker, "y", 0.0)),
                safe_float(getattr(marker, "z", 0.0)),
            ],
            "control_radius": safe_float(getattr(marker, "control_radius", 0.0)),
        },
        "control_test_semantics": "OBJECTIVE_CONTROL_SUM_WITHIN_RADIUS",
        "marker_interaction_semantics": {
            "allows_overlap": True,
            "allows_end_move_on_marker": True,
        },
        "sticky_behavior": {
            "sticky_enabled": sticky_controller is not None,
            "sticky_controller_player_id": str(getattr(sticky_controller, "id", "") or ""),
        },
        "score_source_bindings": [f"score_source:objective:{objective_id}"],
        "transform_flags": {
            "removed": removed,
            "is_hazard": is_hazard,
            "terraformed_by_player_id": str(getattr(terraformed_by, "id", "") or ""),
            "cleansed_by_player_id": str(getattr(cleansed_by, "id", "") or ""),
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
