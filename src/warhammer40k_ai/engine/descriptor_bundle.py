from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from ..battlefield.terrain_runtime import iter_runtime_terrain


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): json_safe(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [json_safe(inner) for inner in value]
    if isinstance(value, set):
        items = [json_safe(inner) for inner in value]
        return sorted(items, key=lambda inner: str(inner))
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def descriptor_id(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:16]}"


def iter_players(game: object) -> list[object]:
    players = list(getattr(game, "players", []) or [])
    return sorted(players, key=lambda player: str(getattr(player, "id", "") or ""))


def iter_units(game: object) -> list[object]:
    units: list[object] = []
    for player in iter_players(game):
        army = getattr(player, "army", None)
        units.extend(list(getattr(army, "units", []) or []))
    return units


def iter_objectives(game: object) -> list[object]:
    game_map = getattr(game, "map", None)
    objectives = list(getattr(game_map, "objectives", []) or [])
    return sorted(objectives, key=lambda objective: str(getattr(objective, "id", "") or ""))


def iter_terrain(game: object) -> list[object]:
    return list(iter_runtime_terrain(game))


@dataclass(frozen=True)
class CompiledDescriptor:
    family: str
    descriptor_id: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": str(self.family or ""),
            "descriptor_id": str(self.descriptor_id or ""),
            "payload": json_safe(self.payload),
        }


@dataclass(frozen=True)
class CompiledDescriptorBundle:
    mission_descriptor: CompiledDescriptor
    objective_descriptors: tuple[CompiledDescriptor, ...]
    terrain_descriptors: tuple[CompiledDescriptor, ...]
    deployment_descriptor: CompiledDescriptor
    army_build_descriptor: CompiledDescriptor
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
            "army_build_descriptor_id": str(self.army_build_descriptor.descriptor_id or ""),
            "tool_descriptor_ids": [
                str(descriptor.descriptor_id or "")
                for descriptor in self.tool_descriptors
            ],
        }


def descriptor_bundle_id(
    *,
    mission_descriptor_id: str,
    objective_descriptor_ids: list[str],
    terrain_descriptor_ids: list[str],
    deployment_descriptor_id: str,
    army_build_descriptor_id: str,
    tool_descriptor_ids: list[str],
) -> str:
    payload = {
        "mission_descriptor_id": mission_descriptor_id,
        "objective_descriptor_ids": sorted(objective_descriptor_ids),
        "terrain_descriptor_ids": sorted(terrain_descriptor_ids),
        "deployment_descriptor_id": deployment_descriptor_id,
        "army_build_descriptor_id": army_build_descriptor_id,
        "tool_descriptor_ids": sorted(tool_descriptor_ids),
    }
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"descriptor_bundle:{digest[:16]}"


__all__ = [
    "CompiledDescriptor",
    "CompiledDescriptorBundle",
    "canonical_json",
    "descriptor_bundle_id",
    "descriptor_id",
    "iter_objectives",
    "iter_players",
    "iter_terrain",
    "iter_units",
    "json_safe",
    "safe_float",
    "safe_int",
]
