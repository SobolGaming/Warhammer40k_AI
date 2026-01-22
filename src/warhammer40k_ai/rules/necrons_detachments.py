from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class NecronsDetachmentManager(DetachmentManagerBase):
    faction_id = "NEC"

    def is_starshatter_arsenal(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Starshatter Arsenal")

    def _unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        kw = (keyword or "").strip()
        if not kw:
            return False
        try:
            return bool(unit.has_any_keyword(kw))
        except Exception:
            pass
        try:
            raw = [str(k or "") for k in (getattr(unit, "keywords", []) or [])]
            raw += [str(k or "") for k in (getattr(unit, "faction_keywords", []) or [])]
            return kw.lower() in {k.lower() for k in raw if str(k).strip()}
        except Exception:
            return False

    def unit_is_necrons(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "NECRONS"):
            return True
        return self._army_faction_matches(self.faction_id)

    def unit_is_vehicle_or_mounted(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "VEHICLE") or self._unit_has_keyword(unit, "MOUNTED")

    def unit_is_titanic(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if bool(getattr(unit, "is_titanic", False)):
                return True
        except Exception:
            pass
        return self._unit_has_keyword(unit, "TITANIC")

    def relentless_onslaught_applies(self, unit) -> bool:
        if not self.is_starshatter_arsenal():
            return False
        return self.unit_is_necrons(unit)

    def relentless_onslaught_hit_bonus(self, attacker_unit, target_unit, *, game=None) -> tuple[int, str]:
        if not self.relentless_onslaught_applies(attacker_unit):
            return 0, ""
        if attacker_unit is None or target_unit is None:
            return 0, ""
        game_map = getattr(game, "map", None) if game is not None else None
        try:
            if bool(attacker_unit._target_within_objective_range(target_unit, game_map)):
                return 1, "Relentless Onslaught (+1 to hit vs objective)"
        except Exception:
            pass
        return 0, ""

    def relentless_onslaught_assault_applies(self, unit) -> bool:
        if not self.relentless_onslaught_applies(unit):
            return False
        if self.unit_is_titanic(unit):
            return False
        return self.unit_is_vehicle_or_mounted(unit)
