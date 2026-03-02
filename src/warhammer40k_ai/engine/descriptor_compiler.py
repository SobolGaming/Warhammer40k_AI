from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from ..rules.enhancement_descriptors import (
    EnhancementToolDescriptor,
    get_enhancement_tool_descriptor,
)
from ..rules.stratagem_descriptors import (
    StratagemToolDescriptor,
    get_stratagem_tool_descriptor,
)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _json_safe(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, set):
        items = [_json_safe(inner) for inner in value]
        return sorted(items, key=lambda inner: str(inner))
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _descriptor_id(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:16]}"


def _footprint_points(feature: object) -> list[list[float]]:
    footprint = getattr(feature, "footprint", None)
    exterior = getattr(footprint, "exterior", None)
    coords = list(getattr(exterior, "coords", []) or []) if exterior is not None else []
    result: list[list[float]] = []
    for coord in coords:
        if not isinstance(coord, (list, tuple)) or len(coord) < 2:
            continue
        result.append([_safe_float(coord[0]), _safe_float(coord[1])])
    return result


def _terrain_semantic_tags(terrain_type: str) -> list[str]:
    key = str(terrain_type or "").strip().upper()
    if key == "RUINS":
        return ["BLOCKER", "STAGING_ANCHOR", "BREACHABLE_REGION"]
    if key == "WOODS":
        return ["COVER_REGION", "SOFT_BLOCKER"]
    if key == "CRATER_AND_RUBBLE":
        return ["COVER_REGION", "DIFFICULT_REGION"]
    if key == "BARRICADE_AND_FUEL_PIPES":
        return ["LINEAR_BLOCKER", "COVER_REGION"]
    if key == "DEBRIS_AND_STATUARY":
        return ["COVER_REGION", "NO_END_MOVE_REGION"]
    if key == "HILLS_AND_SEALED_BUILDINGS":
        return ["ELEVATION_ANCHOR", "STAGING_ANCHOR"]
    return []


def _iter_players(game: object) -> list[object]:
    players = list(getattr(game, "players", []) or [])
    return sorted(players, key=lambda player: str(getattr(player, "id", "") or ""))


def _iter_units(game: object) -> list[object]:
    units: list[object] = []
    for player in _iter_players(game):
        army = getattr(player, "army", None)
        units.extend(list(getattr(army, "units", []) or []))
    return units


def _iter_objectives(game: object) -> list[object]:
    game_map = getattr(game, "map", None)
    objectives = list(getattr(game_map, "objectives", []) or [])
    return sorted(objectives, key=lambda objective: str(getattr(objective, "id", "") or ""))


def _iter_terrain(game: object) -> list[object]:
    game_map = getattr(game, "map", None)
    terrain = list(getattr(game_map, "terrain_features", []) or [])
    return sorted(terrain, key=lambda feature: str(getattr(feature, "id", "") or ""))


def _objective_payload(objective: object) -> dict[str, Any]:
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
                _safe_float(getattr(marker, "x", 0.0)),
                _safe_float(getattr(marker, "y", 0.0)),
                _safe_float(getattr(marker, "z", 0.0)),
            ],
            "control_radius": _safe_float(getattr(marker, "control_radius", 0.0)),
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
    return _json_safe(payload)


def _terrain_payload(feature: object) -> dict[str, Any]:
    terrain_type_obj = getattr(feature, "terrain_type", None)
    terrain_type = str(getattr(terrain_type_obj, "name", terrain_type_obj or "") or "")
    payload = {
        "terrain_id": str(getattr(feature, "id", "") or ""),
        "terrain_type": terrain_type,
        "geometry": {
            "footprint": _footprint_points(feature),
            "bounding_box": _json_safe(dict(getattr(feature, "bounding_box", {}) or {})),
        },
        "line_of_sight_semantics": {
            "has_walls": bool(getattr(feature, "walls", None)),
            "has_openings": bool(getattr(feature, "openings", None)),
        },
        "cover_semantics": {
            "provides_cover": bool(dict(getattr(feature, "traversal_rules", {}) or {}).get("provides_cover", False)),
        },
        "movement_semantics": _json_safe(dict(getattr(feature, "traversal_rules", {}) or {})),
        "layer_count": int(len(list(getattr(feature, "floors", []) or []))),
        "semantic_tags": _terrain_semantic_tags(terrain_type),
    }
    return _json_safe(payload)


def _serialize_mission_zone(zone: object) -> dict[str, Any]:
    cutouts: list[dict[str, Any]] = []
    for cutout in list(getattr(zone, "cutouts", []) or []):
        cutout_type_obj = getattr(cutout, "cutout_type", None)
        cutouts.append(
            {
                "cutout_type": str(getattr(cutout_type_obj, "value", cutout_type_obj or "") or ""),
                "center_x": _safe_float(getattr(cutout, "center_x", 0.0)),
                "center_y": _safe_float(getattr(cutout, "center_y", 0.0)),
                "parameters": _json_safe(getattr(cutout, "parameters", None)),
            }
        )
    vertices: list[list[float]] = []
    for vertex in list(getattr(zone, "vertices", []) or []):
        if not isinstance(vertex, (list, tuple)) or len(vertex) < 2:
            continue
        vertices.append([_safe_float(vertex[0]), _safe_float(vertex[1])])
    zone_type_obj = getattr(zone, "zone_type", None)
    return {
        "name": str(getattr(zone, "name", "") or ""),
        "zone_type": str(getattr(zone_type_obj, "value", zone_type_obj or "") or ""),
        "vertices": vertices,
        "cutouts": cutouts,
    }


def _deployment_payload(game: object) -> dict[str, Any]:
    deployment_state = dict(getattr(game, "deployment_zones", {}) or {})
    zone_entries: list[dict[str, Any]] = []
    for player_id in sorted(str(player_id) for player_id in deployment_state.keys()):
        entry = deployment_state.get(player_id)
        if isinstance(entry, dict):
            mission_zones = [
                _serialize_mission_zone(zone)
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
                    "raw_zone": _json_safe(entry),
                }
            )
    payload = {
        "selected_mission_deployment": str(
            dict(getattr(game, "selected_mission_info", {}) or {}).get("deployment", "") or ""
        ),
        "selected_layout": _safe_int(
            dict(getattr(game, "selected_mission_info", {}) or {}).get("layout", 0), 0
        ),
        "attacker_index": _safe_int(getattr(game, "attacker_index", 0), 0),
        "defender_index": _safe_int(getattr(game, "defender_index", 0), 0),
        "deployment_turn_index": _safe_int(getattr(game, "deployment_turn_index", 0), 0),
        "zone_entries": zone_entries,
    }
    return _json_safe(payload)


def _scoring_window_payload(game: object) -> list[dict[str, Any]]:
    players = _iter_players(game)
    player_ids = [str(getattr(player, "id", "") or "") for player in players if str(getattr(player, "id", "") or "")]
    battle_round = _safe_int(getattr(game, "turn", 0), 0)
    windows = [
        {
            "window_id": "window_primary_active_command",
            "owner_player_id": player_ids[0] if player_ids else "",
            "phase": "COMMAND_PHASE",
            "battle_round": battle_round,
        },
        {
            "window_id": "window_primary_opponent_command",
            "owner_player_id": player_ids[1] if len(player_ids) > 1 else "",
            "phase": "COMMAND_PHASE",
            "battle_round": battle_round,
        },
        {
            "window_id": "window_endgame",
            "owner_player_id": "",
            "phase": "ENDGAME",
            "battle_round": battle_round,
        },
    ]
    return _json_safe(windows)


def _mission_payload(game: object) -> dict[str, Any]:
    selected = dict(getattr(game, "selected_mission_info", {}) or {})
    objective_ids = [
        str(getattr(objective, "id", "") or "")
        for objective in _iter_objectives(game)
    ]
    scoring_sources = [f"score_source:objective:{objective_id}" for objective_id in objective_ids if objective_id]
    primary_name = str(selected.get("primary", "") or "").strip().lower()
    action_sites: list[str] = []
    if "terraform" in primary_name:
        action_sites.append("ACTION_SITE_TERRAFORM")
    if "scorched earth" in primary_name:
        action_sites.append("ACTION_SITE_SCORCHED_EARTH")
    payload = {
        "selected_mission_info": _json_safe(selected),
        "secondary_mission_mode": str(getattr(game, "secondary_mission_mode", "") or ""),
        "battle_round_structure": {
            "max_rounds": 5,
            "current_battle_round": _safe_int(getattr(game, "turn", 0), 0),
        },
        "scoring_windows": _scoring_window_payload(game),
        "primary_scoring_sources": scoring_sources,
        "denial_windows": [
            {
                "window_id": "window_primary_opponent_command",
                "type": "PRIMARY_DENIAL",
            }
        ],
        "secondary_generation_mechanics": {
            "deck_mode": str(getattr(game, "secondary_mission_mode", "") or ""),
        },
        "catch_up_mechanics": [],
        "action_site_semantics": sorted(action_sites),
        "deployment_map_hooks": {
            "deployment_name": str(selected.get("deployment", "") or ""),
            "layout": _safe_int(selected.get("layout", 0), 0),
        },
    }
    return _json_safe(payload)


def _enhancement_tool_payload(descriptor: EnhancementToolDescriptor) -> dict[str, Any]:
    return _json_safe(
        {
            "tool_type": "ENHANCEMENT",
            "tool_id": str(descriptor.enhancement_id or ""),
            "name": str(descriptor.name or ""),
            "timing": str(descriptor.timing or ""),
            "target": str(descriptor.target or ""),
            "duration": str(descriptor.duration or ""),
            "effect": str(descriptor.effect or ""),
            "range_in": _safe_float(descriptor.range_in, 0.0) if descriptor.range_in is not None else None,
            "once_per_battle": bool(descriptor.once_per_battle),
            "effect_params": _json_safe(dict(descriptor.effect_params or {})),
        }
    )


def _stratagem_tool_payload(descriptor: StratagemToolDescriptor) -> dict[str, Any]:
    return _json_safe(
        {
            "tool_type": "STRATAGEM",
            "tool_id": str(descriptor.stratagem_id or ""),
            "name": str(descriptor.name or ""),
            "timing": str(descriptor.timing or ""),
            "target": str(descriptor.target or ""),
            "duration": str(descriptor.duration or ""),
            "effect": str(descriptor.effect or ""),
            "cp_cost": _safe_int(descriptor.cp_cost, 0),
            "range_in": _safe_float(descriptor.range_in, 0.0) if descriptor.range_in is not None else None,
            "once_per_battle_round": bool(descriptor.once_per_battle_round),
            "effect_params": _json_safe(dict(descriptor.effect_params or {})),
        }
    )


@dataclass(frozen=True)
class CompiledDescriptor:
    family: str
    descriptor_id: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": str(self.family or ""),
            "descriptor_id": str(self.descriptor_id or ""),
            "payload": _json_safe(self.payload),
        }


@dataclass(frozen=True)
class CompiledDescriptorBundle:
    mission_descriptor: CompiledDescriptor
    objective_descriptors: tuple[CompiledDescriptor, ...]
    terrain_descriptors: tuple[CompiledDescriptor, ...]
    deployment_descriptor: CompiledDescriptor
    tool_descriptors: tuple[CompiledDescriptor, ...]
    bundle_id: str

    def descriptor_ids(self) -> dict[str, Any]:
        return {
            "mission_descriptor_id": str(self.mission_descriptor.descriptor_id or ""),
            "objective_descriptor_ids": [
                str(descriptor.descriptor_id or "")
                for descriptor in self.objective_descriptors
            ],
            "terrain_descriptor_ids": [
                str(descriptor.descriptor_id or "")
                for descriptor in self.terrain_descriptors
            ],
            "deployment_descriptor_id": str(self.deployment_descriptor.descriptor_id or ""),
            "tool_descriptor_ids": [
                str(descriptor.descriptor_id or "")
                for descriptor in self.tool_descriptors
            ],
        }


def _bundle_id(
    mission_descriptor_id: str,
    objective_descriptor_ids: list[str],
    terrain_descriptor_ids: list[str],
    deployment_descriptor_id: str,
    tool_descriptor_ids: list[str],
) -> str:
    payload = {
        "mission_descriptor_id": mission_descriptor_id,
        "objective_descriptor_ids": sorted(objective_descriptor_ids),
        "terrain_descriptor_ids": sorted(terrain_descriptor_ids),
        "deployment_descriptor_id": deployment_descriptor_id,
        "tool_descriptor_ids": sorted(tool_descriptor_ids),
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"descriptor_bundle:{digest[:16]}"


def compile_descriptor_bundle(game: object) -> CompiledDescriptorBundle:
    mission_payload = _mission_payload(game)
    mission_descriptor = CompiledDescriptor(
        family="MissionDescriptor",
        descriptor_id=_descriptor_id("mission_descriptor", mission_payload),
        payload=mission_payload,
    )

    objective_descriptors: list[CompiledDescriptor] = []
    for objective in _iter_objectives(game):
        payload = _objective_payload(objective)
        objective_descriptors.append(
            CompiledDescriptor(
                family="ObjectiveDescriptor",
                descriptor_id=_descriptor_id("objective_descriptor", payload),
                payload=payload,
            )
        )
    objective_descriptors.sort(key=lambda descriptor: str(descriptor.descriptor_id))

    terrain_descriptors: list[CompiledDescriptor] = []
    for feature in _iter_terrain(game):
        payload = _terrain_payload(feature)
        terrain_descriptors.append(
            CompiledDescriptor(
                family="TerrainDescriptor",
                descriptor_id=_descriptor_id("terrain_descriptor", payload),
                payload=payload,
            )
        )
    terrain_descriptors.sort(key=lambda descriptor: str(descriptor.descriptor_id))

    deployment_payload = _deployment_payload(game)
    deployment_descriptor = CompiledDescriptor(
        family="DeploymentDescriptor",
        descriptor_id=_descriptor_id("deployment_descriptor", deployment_payload),
        payload=deployment_payload,
    )

    tool_descriptors: dict[str, CompiledDescriptor] = {}
    for unit in _iter_units(game):
        enhancement = getattr(unit, "enhancement", None)
        if enhancement is None:
            continue
        enhancement_id = str(getattr(enhancement, "id", "") or "")
        enhancement_name = str(getattr(enhancement, "name", "") or "")
        descriptor = get_enhancement_tool_descriptor(
            enhancement_id=enhancement_id,
            name=enhancement_name,
        )
        if descriptor is None:
            continue
        payload = _enhancement_tool_payload(descriptor)
        descriptor_id = (
            f"tool_descriptor:enhancement:{payload['tool_id']}"
            if str(payload.get("tool_id", "") or "")
            else _descriptor_id("tool_descriptor", payload)
        )
        tool_descriptors[descriptor_id] = CompiledDescriptor(
            family="ToolDescriptor",
            descriptor_id=descriptor_id,
            payload=payload,
        )

    for player in _iter_players(game):
        stratagem_manager = getattr(player, "stratagems", None)
        available = list(getattr(stratagem_manager, "available", []) or [])
        for stratagem in available:
            descriptor = getattr(stratagem, "tool_descriptor", None)
            if descriptor is None:
                descriptor = get_stratagem_tool_descriptor(
                    stratagem_id=str(getattr(stratagem, "id", "") or ""),
                    name=str(getattr(stratagem, "name", "") or ""),
                )
            if descriptor is None:
                continue
            payload = _stratagem_tool_payload(descriptor)
            descriptor_id = (
                f"tool_descriptor:stratagem:{payload['tool_id']}"
                if str(payload.get("tool_id", "") or "")
                else _descriptor_id("tool_descriptor", payload)
            )
            tool_descriptors[descriptor_id] = CompiledDescriptor(
                family="ToolDescriptor",
                descriptor_id=descriptor_id,
                payload=payload,
            )

    sorted_tool_descriptors = tuple(
        tool_descriptors[key]
        for key in sorted(tool_descriptors.keys())
    )

    bundle_id = _bundle_id(
        mission_descriptor_id=mission_descriptor.descriptor_id,
        objective_descriptor_ids=[descriptor.descriptor_id for descriptor in objective_descriptors],
        terrain_descriptor_ids=[descriptor.descriptor_id for descriptor in terrain_descriptors],
        deployment_descriptor_id=deployment_descriptor.descriptor_id,
        tool_descriptor_ids=[descriptor.descriptor_id for descriptor in sorted_tool_descriptors],
    )
    return CompiledDescriptorBundle(
        mission_descriptor=mission_descriptor,
        objective_descriptors=tuple(objective_descriptors),
        terrain_descriptors=tuple(terrain_descriptors),
        deployment_descriptor=deployment_descriptor,
        tool_descriptors=sorted_tool_descriptors,
        bundle_id=bundle_id,
    )
