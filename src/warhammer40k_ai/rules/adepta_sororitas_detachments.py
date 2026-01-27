from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class AdeptaSororitasDetachmentManager(DetachmentManagerBase):
    faction_id = "AS"

    THE_BLOOD_OF_MARTYRS_NAME = "The Blood of Martyrs"

    def is_hallowed_martyrs(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hallowed Martyrs")

    def unit_is_adepta_sororitas(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "ADEPTA SORORITAS"):
            return True
        return self._army_faction_matches(self.faction_id)

    def model_is_adepta_sororitas(self, model, unit) -> bool:
        if model is not None and hasattr(model, "has_any_keyword"):
            if bool(model.has_any_keyword("ADEPTA SORORITAS")):
                return True
        return self.unit_is_adepta_sororitas(unit)

    def blood_of_martyrs_hit_bonus(self, model, unit) -> tuple[int, str]:
        """
        Hallowed Martyrs: +1 to Hit while the model's unit is below Starting Strength.
        """
        if not self.is_hallowed_martyrs():
            return 0, ""
        if unit is None or not self.model_is_adepta_sororitas(model, unit):
            return 0, ""
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if hasattr(root, "is_below_starting_strength") and root.is_below_starting_strength():
            return 1, f"{self.THE_BLOOD_OF_MARTYRS_NAME} (+1 to hit below Starting Strength)"
        return 0, ""

    def blood_of_martyrs_wound_bonus(self, model, unit) -> tuple[int, str]:
        """
        Hallowed Martyrs: +1 to Wound while the model's unit is Below Half-strength.
        """
        if not self.is_hallowed_martyrs():
            return 0, ""
        if unit is None or not self.model_is_adepta_sororitas(model, unit):
            return 0, ""
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if hasattr(root, "is_below_half_strength") and root.is_below_half_strength():
            return 1, f"{self.THE_BLOOD_OF_MARTYRS_NAME} (+1 to wound below Half-strength)"
        return 0, ""
