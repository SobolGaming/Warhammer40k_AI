from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class TauEmpireDetachmentManager(DetachmentManagerBase):
    faction_id = "TAU"
    _TAU_EMPIRE_KEYWORDS = ("T'AU EMPIRE", "TAU EMPIRE")

    def is_experimental_prototype_cadre(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Experimental Prototype Cadre")

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _model_is_tau_empire(self, model) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            for keyword in self._TAU_EMPIRE_KEYWORDS:
                if has_any(keyword):
                    return True

        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        return (
            self._unit_has_keyword_or_faction(unit, "T'AU EMPIRE", faction_id=self.faction_id)
            or self._unit_has_keyword_or_faction(unit, "TAU EMPIRE", faction_id=self.faction_id)
        )

    def superior_craftsmanship_range_bonus(self, model, weapon_profile=None, *, game=None) -> int:
        del game  # Future-proofed signature; no phase/turn dependence for this rule.
        if not self.is_experimental_prototype_cadre():
            return 0
        if model is None or weapon_profile is None:
            return 0
        if not self._model_in_army(model):
            return 0
        if not self._model_is_tau_empire(model):
            return 0
        parent = getattr(weapon_profile, "parent_wargear", None)
        is_ranged = bool(parent is not None and callable(getattr(parent, "is_ranged", None)) and parent.is_ranged())
        if not is_ranged:
            return 0
        return 6
