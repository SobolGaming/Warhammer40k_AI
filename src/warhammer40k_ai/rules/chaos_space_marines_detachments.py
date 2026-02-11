from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class ChaosSpaceMarinesDetachmentManager(DetachmentManagerBase):
    faction_id = "CSM"

    DETACHMENT_CABAL_OF_CHAOS = "Cabal of Chaos"
    DETACHMENT_RENEGADE_RAIDERS = "Renegade Raiders"

    def is_cabal_of_chaos(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_CABAL_OF_CHAOS)

    def is_renegade_raiders(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_RENEGADE_RAIDERS)

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _model_in_army(self, model) -> bool:
        if model is None:
            return False
        return self._unit_in_army(getattr(model, "parent_unit", None))

    def _unit_is_heretic_astartes(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "HERETIC ASTARTES")

    def _model_is_heretic_astartes(self, model) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any) and bool(has_any("HERETIC ASTARTES")):
            return True
        has_keyword = getattr(model, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("HERETIC ASTARTES")):
            return True
        return self._unit_is_heretic_astartes(getattr(model, "parent_unit", None))

    def raiders_and_reavers_assault_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_renegade_raiders():
            return False
        if unit is None or not self._unit_in_army(unit):
            return False
        if not self._unit_is_heretic_astartes(unit):
            return False
        if weapon_profile is None:
            return True
        parent = getattr(weapon_profile, "parent_wargear", None)
        if parent is None:
            return False
        return bool(getattr(parent, "is_ranged", lambda: False)())

    def raiders_and_reavers_ap_bonus(self, model, target_unit, *, game_map=None) -> int:
        if not self.is_renegade_raiders():
            return 0
        if model is None or target_unit is None or not self._model_in_army(model):
            return 0
        if not self._model_is_heretic_astartes(model):
            return 0
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return 0
        within_objective = getattr(unit, "_target_within_objective_range", None)
        if not callable(within_objective):
            return 0
        if bool(within_objective(target_unit, game_map)):
            return 1
        return 0
