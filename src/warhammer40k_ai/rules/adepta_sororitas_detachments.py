from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class AdeptaSororitasDetachmentManager(DetachmentManagerBase):
    faction_id = "AS"

    THE_BLOOD_OF_MARTYRS_NAME = "The Blood of Martyrs"
    SACRED_RITES_NAME = "Sacred Rites"
    FERVENT_PURGATION_NAME = "Fervent Purgation"

    def is_hallowed_martyrs(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hallowed Martyrs")

    def is_army_of_faith(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Army of Faith")

    def is_bringers_of_flame(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Bringers of Flame")

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

    def sacred_rites_max_acts_of_faith_per_phase(self, unit) -> int:
        """
        Army of Faith: ADEPTA SORORITAS units can perform up to two Acts of Faith per phase.
        """
        if not self.is_army_of_faith():
            return 1
        if unit is None:
            return 1
        if not self.unit_is_adepta_sororitas(unit):
            return 1
        return 2

    def fervent_purgation_assault_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_bringers_of_flame():
            return False
        if unit is None:
            return False
        if not self.unit_is_adepta_sororitas(unit):
            return False
        if weapon_profile is None:
            return True
        parent = getattr(weapon_profile, "parent_wargear", None)
        if parent is None:
            return False
        is_ranged_fn = getattr(parent, "is_ranged", None)
        if not callable(is_ranged_fn):
            return False
        return bool(is_ranged_fn())

    def fervent_purgation_strength_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        if not self.is_bringers_of_flame():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return 0, ""
        if not self.fervent_purgation_assault_applies(attacker_unit, weapon_profile):
            return 0, ""
        try:
            distance = float((attack_instance or {}).get("distance_to_target", 0.0) or 0.0)
        except Exception:
            distance = 0.0
        if distance <= 0.0 and target_unit is not None:
            game_map = None
            try:
                game_map = getattr(getattr(attacker_unit.get_parent_army(), "player", None), "game", None).map
            except Exception:
                game_map = None
            if game_map is not None:
                try:
                    distance = float(game_map.get_distance_between_units(attacker_unit, target_unit))
                except Exception:
                    distance = 0.0
        if distance <= 0.0 or distance > 6.0 + 1e-6:
            return 0, ""
        return 1, self.FERVENT_PURGATION_NAME

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
