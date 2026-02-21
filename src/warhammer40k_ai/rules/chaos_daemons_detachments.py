from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class ChaosDaemonsDetachmentManager(DetachmentManagerBase):
    faction_id = "CD"

    def _attached_unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        members = (
            list(root.get_attached_unit_members() or [])
            if hasattr(root, "get_attached_unit_members")
            else [root]
        )
        for member in members:
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    def is_shadow_legion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Shadow Legion")

    def is_blood_legion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Blood Legion")

    def is_legion_of_excess_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Legion of Excess")

    def is_daemonic_incursion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Daemonic Incursion")

    def is_plague_legion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Plague Legion")

    def is_scintillating_legion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Scintillating Legion")

    def first_prince_of_chaos_active(self) -> bool:
        return self.is_shadow_legion_detachment()

    def murdercall_applies(self, unit) -> bool:
        if not self.is_blood_legion_detachment():
            return False
        if unit is None:
            return False
        return bool(
            self._attached_unit_has_keyword(unit, "LEGIONES DAEMONICA")
            and self._attached_unit_has_keyword(unit, "KHORNE")
        )

    def blood_tainted_applies(self, unit) -> bool:
        return self.murdercall_applies(unit)

    def beguiling_aura_applies(self, unit) -> bool:
        if not self.is_legion_of_excess_detachment():
            return False
        if unit is None:
            return False
        return bool(
            self._attached_unit_has_keyword(unit, "LEGIONES DAEMONICA")
            and self._attached_unit_has_keyword(unit, "SLAANESH")
        )

    def seductive_gambit_applies(self, unit) -> bool:
        return self.beguiling_aura_applies(unit)
