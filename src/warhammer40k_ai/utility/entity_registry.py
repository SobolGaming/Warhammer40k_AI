from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .entity_ids import get_entity_id, maybe_entity_id
from .ordering import sorted_by_id


@dataclass
class EntityRegistry:
    _by_kind: Dict[str, Dict[str, object]] = field(default_factory=dict)

    def register(self, entity: object, *, kind: Optional[str] = None) -> str:
        if entity is None:
            raise ValueError("Cannot register a None entity.")
        entity_id = get_entity_id(entity)
        bucket = self._by_kind.setdefault(kind or entity.__class__.__name__, {})
        bucket[entity_id] = entity
        return entity_id

    def register_many(self, entities: Iterable[object], *, kind: Optional[str] = None) -> None:
        for entity in list(entities or []):
            if entity is None:
                continue
            self.register(entity, kind=kind)

    def unregister(self, entity: object, *, kind: Optional[str] = None) -> None:
        if entity is None:
            return
        entity_id = maybe_entity_id(entity)
        if not entity_id:
            return
        bucket = self._by_kind.get(kind or entity.__class__.__name__)
        if not bucket:
            return
        bucket.pop(entity_id, None)

    def get(self, entity_id: str, *, kind: Optional[str] = None) -> Optional[object]:
        if not entity_id:
            return None
        if kind:
            return self._by_kind.get(kind, {}).get(entity_id)
        for bucket in self._by_kind.values():
            if entity_id in bucket:
                return bucket[entity_id]
        return None

    def list(self, *, kind: str) -> List[object]:
        return sorted_by_id(self._by_kind.get(kind, {}).values())

    def kinds(self) -> List[str]:
        return sorted(self._by_kind.keys())

    def clear(self) -> None:
        self._by_kind.clear()


def rebuild_registry_from_game(registry: EntityRegistry, game: object) -> None:
    registry.clear()

    players = list(getattr(game, "players", []) or [])
    registry.register_many(players, kind="player")

    for player in players:
        army = getattr(player, "army", None)
        if army is None:
            getter = getattr(player, "get_army", None)
            if callable(getter):
                army = getter()
        if army is None:
            continue
        registry.register(army, kind="army")
        units = list(getattr(army, "units", []) or [])
        registry.register_many(units, kind="unit")
        for unit in units:
            models = list(getattr(unit, "models", []) or [])
            registry.register_many(models, kind="model")
            for model in models:
                registry.register_many(getattr(model, "wargear", []) or [], kind="wargear")
            lost_models = list(getattr(unit, "models_lost", []) or [])
            registry.register_many(lost_models, kind="model")
            for model in lost_models:
                registry.register_many(getattr(model, "wargear", []) or [], kind="wargear")
            registry.register_many(getattr(unit, "status_effects", []) or [], kind="effect")

        cult_ambush = getattr(army, "cult_ambush", None)
        if cult_ambush is not None:
            registry.register_many(getattr(cult_ambush, "markers", []) or [], kind="marker")

        deathstrike = getattr(army, "deathstrike", None)
        if deathstrike is not None:
            markers = getattr(deathstrike, "_markers", {}) or {}
            registry.register_many(markers.values(), kind="deathstrike_marker")

    game_map = getattr(game, "map", None)
    if game_map is not None:
        registry.register_many(getattr(game_map, "terrain_features", []) or [], kind="terrain")
        registry.register_many(getattr(game_map, "terrain_areas", []) or [], kind="terrain_area")
        objectives = list(getattr(game_map, "objectives", []) or [])
        registry.register_many(objectives, kind="objective")
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is not None:
                registry.register(loc, kind="objective_marker")

    objectives = list(getattr(game, "objectives", []) or [])
    registry.register_many(objectives, kind="objective")
    for obj in objectives:
        loc = getattr(obj, "location", None)
        if loc is not None:
            registry.register(loc, kind="objective_marker")

    decision_queue = getattr(game, "decision_queue", None)
    if decision_queue is not None:
        registry.register_many(getattr(decision_queue, "list", lambda: [])(), kind="decision")
    registry.register_many(getattr(game, "command_queue", []) or [], kind="command")
