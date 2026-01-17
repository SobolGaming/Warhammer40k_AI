from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional


@dataclass
class RulesContext:
    player: object
    army: object
    faction_id: str
    detachment_type: str
    _manager_cache: dict[tuple[str, tuple[str, ...]], bool] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_player(cls, player: object) -> "RulesContext":
        try:
            army = player.get_army()
        except Exception:
            army = getattr(player, "army", None)
        faction_id = ""
        detachment_type = ""
        if army is not None:
            try:
                faction_id = str(getattr(army, "faction_id", "") or "")
            except Exception:
                faction_id = ""
            try:
                detachment_type = str(getattr(army, "detachment_type", "") or "")
            except Exception:
                detachment_type = ""
        return cls(
            player=player,
            army=army,
            faction_id=faction_id,
            detachment_type=detachment_type,
        )

    def has_faction_id(self, *ids: str) -> bool:
        if not self.faction_id:
            return False
        fid = self.faction_id.strip().upper()
        for entry in ids:
            if fid == str(entry or "").strip().upper():
                return True
        return False

    def _normalize_detachment(self, text: str) -> str:
        norm = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
        return re.sub(r"\s+", " ", norm).strip()

    def has_detachment_type(self, *names: str) -> bool:
        if not self.detachment_type:
            return False
        det = self._normalize_detachment(self.detachment_type)
        if not det:
            return False
        for name in names:
            target = self._normalize_detachment(name)
            if not target:
                continue
            if det == target:
                return True
            if det.endswith("s") and det[:-1] == target:
                return True
            if target.endswith("s") and target[:-1] == det:
                return True
            if det in target or target in det:
                return True
        return False

    def manager_active(self, attr: str, method_names: Iterable[str] = ()) -> bool:
        methods = tuple(method_names or ())
        key = (attr, methods)
        cached = self._manager_cache.get(key)
        if cached is not None:
            return cached
        army = self.army
        if army is None:
            self._manager_cache[key] = False
            return False
        try:
            mgr = getattr(army, attr, None)
        except Exception:
            mgr = None
        if mgr is None:
            self._manager_cache[key] = False
            return False
        if not methods:
            self._manager_cache[key] = True
            return True
        found = False
        for name in methods:
            fn = getattr(mgr, name, None)
            if callable(fn):
                try:
                    found = True
                    if fn():
                        self._manager_cache[key] = True
                        return True
                except Exception:
                    self._manager_cache[key] = False
                    return False
        result = not found
        self._manager_cache[key] = result
        return result


def any_faction(contexts: Iterable[RulesContext], *ids: str) -> bool:
    for ctx in contexts:
        if ctx and ctx.has_faction_id(*ids):
            return True
    return False


def any_manager(
    contexts: Iterable[RulesContext],
    attr: str,
    method_names: Iterable[str] = (),
) -> bool:
    for ctx in contexts:
        if ctx and ctx.manager_active(attr, method_names):
            return True
    return False


def any_detachment(contexts: Iterable[RulesContext], *names: str) -> bool:
    for ctx in contexts:
        if ctx and ctx.has_detachment_type(*names):
            return True
    return False
