from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class ChaosDaemonsDetachmentManager(DetachmentManagerBase):
    faction_id = "CD"

    def is_shadow_legion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Shadow Legion")

    def is_legion_of_excess_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Legion of Excess")

    def is_daemonic_incursion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Daemonic Incursion")

    def first_prince_of_chaos_active(self) -> bool:
        return self.is_shadow_legion_detachment()

    def seductive_gambit_applies(self, unit) -> bool:
        if not self.is_legion_of_excess_detachment():
            return False
        if unit is None:
            return False
        try:
            return bool(unit.has_any_keyword("SLAANESH"))
        except Exception:
            return False
