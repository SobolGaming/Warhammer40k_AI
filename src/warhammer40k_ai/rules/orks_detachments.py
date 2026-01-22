from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class OrksDetachmentManager(DetachmentManagerBase):
    faction_id = "ORK"

    def is_war_horde(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("War Horde")

    def war_horde_sustained_hits_value(self, unit, *, attack_type: str = "", keyword: str = "ORKS") -> int:
        if not self.is_war_horde():
            return 0
        if unit is None:
            return 0
        if str(attack_type or "").strip().lower() not in ("", "melee"):
            return 0
        if not self._unit_has_keyword_or_faction(unit, keyword, faction_id=self.faction_id):
            return 0
        return 1
