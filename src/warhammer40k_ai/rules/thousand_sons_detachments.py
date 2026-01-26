from __future__ import annotations

from typing import Optional

from .detachment_manager import DetachmentManagerBase


class ThousandSonsDetachmentManager(DetachmentManagerBase):
    faction_id = "TS"

    def is_rubricae_phalanx(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Rubricae Phalanx")

    def _model_is_rubricae(self, model) -> bool:
        if model is None:
            return False
        try:
            fn = getattr(model, "has_any_keyword", None)
            if callable(fn) and fn("RUBRICAE"):
                return True
        except Exception:
            pass
        try:
            unit = getattr(model, "parent_unit", None)
        except Exception:
            unit = None
        return self._unit_has_keyword(unit, "RUBRICAE")

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        try:
            unit = getattr(model, "parent_unit", None)
        except Exception:
            unit = None
        if unit is None:
            return False
        try:
            return unit.get_parent_army() is self.army
        except Exception:
            return False

    def rubricae_phalanx_armor_save_bonus(
        self,
        model,
        *,
        damage_characteristic: Optional[int] = None,
    ) -> int:
        """
        Detachment ability: All is Dust (Rubricae Phalanx).

        Each time an attack with an unmodified Damage characteristic of 1 is allocated to a
        Rubricae model from your army, add 1 to any armour saving throw made against that attack.
        """
        if not self.is_rubricae_phalanx():
            return 0
        if damage_characteristic is None:
            return 0
        try:
            if int(damage_characteristic) != 1:
                return 0
        except Exception:
            return 0
        if not self._model_is_rubricae(model):
            return 0
        if not self._model_in_army(model):
            return 0
        return 1
