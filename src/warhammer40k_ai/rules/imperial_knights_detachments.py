from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class ImperialKnightsDetachmentManager(DetachmentManagerBase):
    faction_id = "QI"
    DETACHMENT_VALOURSTRIKE_LANCE = "Valourstrike Lance"

    def is_valourstrike_lance(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_VALOURSTRIKE_LANCE)

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _unit_is_imperial_knights(self, unit) -> bool:
        return self._unit_has_keyword_or_faction(unit, "IMPERIAL KNIGHTS", faction_id=self.faction_id)

    @staticmethod
    def _weapon_is_ranged(weapon_profile) -> bool:
        if weapon_profile is None:
            return False
        parent = getattr(weapon_profile, "parent_wargear", None)
        return bool(parent is not None and callable(getattr(parent, "is_ranged", None)) and parent.is_ranged())

    def bold_gallantry_assault_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_valourstrike_lance():
            return False
        if unit is None or not self._unit_in_army(unit):
            return False
        if not self._unit_is_imperial_knights(unit):
            return False
        if weapon_profile is None:
            return True
        return self._weapon_is_ranged(weapon_profile)
