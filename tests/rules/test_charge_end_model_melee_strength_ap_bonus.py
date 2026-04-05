import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestChargeEndModelMeleeStrengthApBonus(unittest.TestCase):
    def _make_unit(self, name, *, abilities=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.models = []
        unit.possible_abilities = list(abilities or [])
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_members = lambda: [unit]
        unit.get_attached_unit_models = lambda: list(unit.models)
        return unit

    def _make_model(self, name, unit):
        model = Model(
            name=name,
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def test_charge_end_model_only_strength_ap_bonus_applies_to_leader_model(self):
        ability = Ability(
            "Brutal Raider",
            "CSM",
            (
                "Each time this model's unit ends a Charge move, until the end of the turn, add 1 to the "
                "Strength characteristic of melee weapons equipped by this model and improve the Armour "
                "Penetration characteristics of those weapons by 1."
            ),
            "Datasheet",
            "",
        )

        bodyguard = self._make_unit("Bodyguard")
        leader = self._make_unit("Reave-Captain", abilities=[ability])
        leader.can_be_attached_to = [bodyguard.name]
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        bodyguard.get_attached_unit_members = lambda: [bodyguard, leader]
        leader.get_attached_unit_root = lambda: bodyguard

        bodyguard_model = self._make_model("Bodyguard Model", bodyguard)
        leader_model = self._make_model("Reave-Captain Model", leader)
        bodyguard.models = [bodyguard_model]
        leader.models = [leader_model]
        bodyguard.get_attached_unit_models = lambda: [bodyguard_model, leader_model]

        applied = bodyguard._apply_charge_end_model_melee_strength_ap_bonuses()
        self.assertTrue(applied)

        bodyguard_strength_bonus, _ = bodyguard_model.get_temporary_melee_strength_bonus()
        self.assertEqual(bodyguard_strength_bonus, 0)
        self.assertEqual(bodyguard_model.get_temporary_melee_ap_bonus(), 0)

        leader_strength_bonus, reasons = leader_model.get_temporary_melee_strength_bonus()
        self.assertEqual(leader_strength_bonus, 1)
        self.assertEqual(leader_model.get_temporary_melee_ap_bonus(), 1)
        self.assertTrue(any("Brutal Raider" in reason for reason in reasons))

    def test_charge_end_model_only_strength_ap_bonus_expires_end_of_fight_phase(self):
        ability = Ability(
            "Brutal Raider",
            "CSM",
            (
                "Each time this model's unit ends a Charge move, until the end of the turn, add 1 to the "
                "Strength characteristic of melee weapons equipped by this model and improve the Armour "
                "Penetration characteristics of those weapons by 1."
            ),
            "Datasheet",
            "",
        )
        unit = self._make_unit("Solo Captain", abilities=[ability])
        unit_model = self._make_model("Captain", unit)
        unit.models = [unit_model]

        applied = unit._apply_charge_end_model_melee_strength_ap_bonuses()
        self.assertTrue(applied)
        self.assertEqual(unit_model.get_temporary_melee_ap_bonus(), 1)
        self.assertEqual(unit_model.get_temporary_melee_strength_bonus()[0], 1)

        unit_model.on_phase_end(SimpleNamespace(name="FIGHT_PHASE"))
        self.assertEqual(unit_model.get_temporary_melee_ap_bonus(), 0)
        self.assertEqual(unit_model.get_temporary_melee_strength_bonus()[0], 0)


if __name__ == "__main__":
    unittest.main()
