from __future__ import annotations

from typing import Any

from ..battlefield.objective_sites import resolve_objective_id, resolve_objective_site
from .state_blob_rules import json_safe


def objective_entries(game: object) -> list[dict[str, Any]]:
    game_map = getattr(game, "map", None)
    objectives = list(getattr(game_map, "objectives", []) or [])
    entries: list[dict[str, Any]] = []
    for objective in objectives:
        site = resolve_objective_site(objective)
        if site is None:
            continue
        objective_id = resolve_objective_id(objective)
        if hasattr(site, "to_state_entry"):
            entries.append(dict(site.to_state_entry(objective_id=objective_id)))
            continue
        controller = getattr(site, "controlling_player", None)
        entries.append(
            {
                "objective_id": objective_id,
                "objective_site_id": str(getattr(site, "id", objective_id) or objective_id),
                "site_kind": "MARKER",
                "position": [
                    float(getattr(site, "x", 0.0) or 0.0),
                    float(getattr(site, "y", 0.0) or 0.0),
                    float(getattr(site, "z", 0.0) or 0.0),
                ],
                "control_radius": float(getattr(site, "control_radius", 0.0) or 0.0),
                "controller_player_id": str(getattr(controller, "id", "") or ""),
                "sticky_controller_player_id": str(getattr(getattr(site, "sticky_controller", None), "id", "") or ""),
                "removed": bool(getattr(site, "removed", False)),
                "geometry": {
                    "kind": "MARKER",
                    "position": [
                        float(getattr(site, "x", 0.0) or 0.0),
                        float(getattr(site, "y", 0.0) or 0.0),
                        float(getattr(site, "z", 0.0) or 0.0),
                    ],
                    "control_radius": float(getattr(site, "control_radius", 0.0) or 0.0),
                    "feature_key": "",
                    "feature_label": "",
                },
                "control_region": {
                    "region_id": f"region:objective:{objective_id}",
                    "kind": "OBJECTIVE_CONTROL_RADIUS",
                    "objective_id": objective_id,
                    "objective_site_id": str(getattr(site, "id", objective_id) or objective_id),
                    "center": [
                        float(getattr(site, "x", 0.0) or 0.0),
                        float(getattr(site, "y", 0.0) or 0.0),
                        float(getattr(site, "z", 0.0) or 0.0),
                    ],
                    "radius": float(getattr(site, "control_radius", 0.0) or 0.0),
                    "metadata": {},
                },
                "score_sources": [
                    {
                        "score_source_id": f"score_source:objective:{objective_id}",
                        "kind": "OBJECTIVE_CONTROL",
                        "objective_id": objective_id,
                        "objective_site_id": str(getattr(site, "id", objective_id) or objective_id),
                        "label": str(getattr(objective, "name", "") or ""),
                        "controller_player_id": str(getattr(controller, "id", "") or ""),
                        "points_value": int(getattr(objective, "points", 0) or 0),
                        "metadata": {},
                    }
                ],
            }
        )
    entries.sort(key=lambda entry: str(entry["objective_id"]))
    return json_safe(entries)


def scoring_surfaces(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    for objective in list(entries or []):
        for score_source in list(objective.get("score_sources", []) or []):
            surfaces.append(dict(score_source))
    surfaces.sort(key=lambda entry: str(entry.get("score_source_id", "")))
    return json_safe(surfaces)


def control_regions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    for objective in list(entries or []):
        control_region = dict(objective.get("control_region", {}) or {})
        if not control_region:
            continue
        regions.append(control_region)
    regions.sort(key=lambda entry: str(entry.get("region_id", "")))
    return json_safe(regions)


__all__ = ["control_regions", "objective_entries", "scoring_surfaces"]
