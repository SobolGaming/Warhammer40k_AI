from __future__ import annotations

from typing import Any

from .descriptor_bundle import CompiledDescriptor, descriptor_id, json_safe, safe_float, safe_int


def serialize_mission_zone(zone: object) -> dict[str, Any]:
    cutouts: list[dict[str, Any]] = []
    for cutout in list(getattr(zone, "cutouts", []) or []):
        cutout_type_obj = getattr(cutout, "cutout_type", None)
        cutouts.append(
            {
                "cutout_type": str(getattr(cutout_type_obj, "value", cutout_type_obj or "") or ""),
                "center_x": safe_float(getattr(cutout, "center_x", 0.0)),
                "center_y": safe_float(getattr(cutout, "center_y", 0.0)),
                "parameters": json_safe(getattr(cutout, "parameters", None)),
            }
        )
    vertices: list[list[float]] = []
    for vertex in list(getattr(zone, "vertices", []) or []):
        if not isinstance(vertex, (list, tuple)) or len(vertex) < 2:
            continue
        vertices.append([safe_float(vertex[0]), safe_float(vertex[1])])
    zone_type_obj = getattr(zone, "zone_type", None)
    return {
        "name": str(getattr(zone, "name", "") or ""),
        "zone_type": str(getattr(zone_type_obj, "value", zone_type_obj or "") or ""),
        "vertices": vertices,
        "cutouts": cutouts,
    }


def build_deployment_descriptor_payload(game: object) -> dict[str, Any]:
    deployment_state = dict(getattr(game, "deployment_zones", {}) or {})
    zone_entries: list[dict[str, Any]] = []
    for player_id in sorted(str(player_id) for player_id in deployment_state.keys()):
        entry = deployment_state.get(player_id)
        if isinstance(entry, dict):
            mission_zones = [
                serialize_mission_zone(zone)
                for zone in list(entry.get("mission_zones", []) or [])
            ]
            zone_entries.append(
                {
                    "player_id": player_id,
                    "mission_zones": mission_zones,
                }
            )
        else:
            zone_entries.append(
                {
                    "player_id": player_id,
                    "raw_zone": json_safe(entry),
                }
            )
    payload = {
        "selected_mission_deployment": str(
            dict(getattr(game, "selected_mission_info", {}) or {}).get("deployment", "") or ""
        ),
        "selected_layout": safe_int(
            dict(getattr(game, "selected_mission_info", {}) or {}).get("layout", 0),
            0,
        ),
        "attacker_index": safe_int(getattr(game, "attacker_index", 0), 0),
        "defender_index": safe_int(getattr(game, "defender_index", 0), 0),
        "deployment_turn_index": safe_int(getattr(game, "deployment_turn_index", 0), 0),
        "zone_entries": zone_entries,
    }
    return json_safe(payload)


def compile_deployment_descriptor(game: object) -> CompiledDescriptor:
    payload = build_deployment_descriptor_payload(game)
    return CompiledDescriptor(
        family="DeploymentDescriptor",
        descriptor_id=descriptor_id("deployment_descriptor", payload),
        payload=payload,
    )


__all__ = ["build_deployment_descriptor_payload", "compile_deployment_descriptor", "serialize_mission_zone"]
