from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class AeldariDetachmentManager(DetachmentManagerBase):
    faction_id = "AE"

    def is_warhost_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Warhost")

    def is_armoured_warhost(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Armoured Warhost")

    def is_aspect_host(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Aspect Host")

    def is_devoted_of_ynnead(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Devoted of Ynnead")

    def is_ghosts_of_the_webway(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Ghosts of the Webway")

    def is_guardian_battlehost(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Guardian Battlehost")

    def is_seer_council(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Seer Council")

    def is_serpents_brood(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Serpent's Brood")

    def is_spirit_conclave(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Spirit Conclave")

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        try:
            return unit.get_parent_army() is self.army
        except Exception:
            return False

    def _unit_is_aeldari_vehicle(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "AELDARI") and self._unit_has_keyword(unit, "VEHICLE")

    def _unit_is_aeldari_vehicle_fly(self, unit) -> bool:
        if unit is None:
            return False
        return (
            self._unit_has_keyword(unit, "AELDARI")
            and self._unit_has_keyword(unit, "VEHICLE")
            and self._unit_has_keyword(unit, "FLY")
        )

    def skilled_crews_assault_applies(self, unit) -> bool:
        if not self.is_armoured_warhost():
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_is_aeldari_vehicle(unit)

    def skilled_crews_reroll_advance_applies(self, unit) -> bool:
        if not self.is_armoured_warhost():
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_is_aeldari_vehicle_fly(unit)
