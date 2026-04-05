from __future__ import annotations

from typing import Any

from .state_blob_rules import safe_float


def objective_entries(game: object) -> list[dict[str, Any]]:
    game_map = getattr(game, "map", None)
    objectives = list(getattr(game_map, "objectives", []) or [])
    entries: list[dict[str, Any]] = []
    for objective in objectives:
        objective_id = str(getattr(objective, "id", "") or "")
        controller = getattr(objective, "controlling_player", None)
        entries.append(
            {
                "objective_id": objective_id,
                "position": [
                    safe_float(getattr(objective, "x", 0.0), 0.0),
                    safe_float(getattr(objective, "y", 0.0), 0.0),
                    safe_float(getattr(objective, "z", 0.0), 0.0),
                ],
                "control_radius": safe_float(getattr(objective, "control_radius", 0.0), 0.0),
                "controller_player_id": str(getattr(controller, "id", "") or ""),
            }
        )
    entries.sort(key=lambda entry: str(entry["objective_id"]))
    return entries


def scoring_surfaces(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    for objective in entries:
        objective_id = str(objective.get("objective_id", "") or "")
        surfaces.append(
            {
                "score_source_id": f"score_source:objective:{objective_id}",
                "kind": "OBJECTIVE_CONTROL",
                "objective_id": objective_id,
                "controller_player_id": str(objective.get("controller_player_id", "") or ""),
            }
        )
    surfaces.sort(key=lambda entry: str(entry["score_source_id"]))
    return surfaces


def control_regions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    for objective in entries:
        objective_id = str(objective.get("objective_id", "") or "")
        position = list(objective.get("position", [0.0, 0.0, 0.0]) or [0.0, 0.0, 0.0])
        regions.append(
            {
                "region_id": f"region:objective:{objective_id}",
                "kind": "OBJECTIVE_CONTROL_RADIUS",
                "center": [safe_float(position[0]), safe_float(position[1]), safe_float(position[2])],
                "radius": safe_float(objective.get("control_radius", 0.0), 0.0),
                "objective_id": objective_id,
            }
        )
    regions.sort(key=lambda entry: str(entry["region_id"]))
    return regions


__all__ = ["control_regions", "objective_entries", "scoring_surfaces"]
