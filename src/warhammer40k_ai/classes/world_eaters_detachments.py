from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class WorldEatersDetachmentManager(DetachmentManagerBase):
    faction_id = "WE"

    def is_berzerker_warband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Berzerker Warband")

    def relentless_rage_applies(self, unit) -> bool:
        if not self.is_berzerker_warband():
            return False
        if unit is None:
            return False
        try:
            if unit.has_any_keyword("WORLD EATERS"):
                return True
            return False
        except Exception:
            return self._army_faction_matches(self.faction_id)
