from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

from .cdt_mesh import SurfaceCdtMesh
from .types import SurfaceId
from .world_snapshot import WorldSnapshot


@dataclass(frozen=True)
class StaticMeshCacheKey:
    terrain_revision: str
    support_surface_revision: str
    movement_profile_signature: str
    footprint_class: str
    base_clearance_bucket: str
    prefer_constrained: bool


@dataclass(frozen=True, eq=False)
class StaticMeshCacheEntry:
    surface_meshes: tuple[tuple[SurfaceId, SurfaceCdtMesh], ...]
    connectors: tuple[object, ...]


def clearance_bucket_for_radius(base_radius: float) -> str:
    """Return an exact circular-clearance key to avoid cross-radius mesh reuse."""
    clamped = max(0.0, float(base_radius))
    return f"{clamped:.4f}"


def build_static_mesh_cache_key(
    world_snapshot: WorldSnapshot,
    *,
    footprint_class: str,
    base_clearance_bucket: str,
    prefer_constrained: bool,
) -> StaticMeshCacheKey:
    return StaticMeshCacheKey(
        terrain_revision=str(world_snapshot.terrain_revision),
        support_surface_revision=str(world_snapshot.support_surface_revision),
        movement_profile_signature=str(world_snapshot.movement_profile_signature),
        footprint_class=str(footprint_class),
        base_clearance_bucket=str(base_clearance_bucket),
        prefer_constrained=bool(prefer_constrained),
    )


class StaticMeshCache:
    def __init__(self, *, max_entries: int = 32):
        self._max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[StaticMeshCacheKey, StaticMeshCacheEntry] = OrderedDict()

    def get(self, key: StaticMeshCacheKey) -> Optional[StaticMeshCacheEntry]:
        entry = self._entries.get(key)
        if entry is None:
            return None
        self._entries.move_to_end(key)
        return entry

    def put(self, key: StaticMeshCacheKey, entry: StaticMeshCacheEntry) -> None:
        self._entries[key] = entry
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()

    def size(self) -> int:
        return len(self._entries)


_STATIC_MESH_CACHE = StaticMeshCache(max_entries=64)


def get_static_mesh_cache() -> StaticMeshCache:
    return _STATIC_MESH_CACHE


def clear_static_mesh_cache() -> None:
    _STATIC_MESH_CACHE.clear()


__all__ = [
    "StaticMeshCache",
    "StaticMeshCacheEntry",
    "StaticMeshCacheKey",
    "build_static_mesh_cache_key",
    "clear_static_mesh_cache",
    "clearance_bucket_for_radius",
    "get_static_mesh_cache",
]
