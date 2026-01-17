import unittest
from types import SimpleNamespace


class TestBondsman(unittest.TestCase):
    def test_defenders_duty_reduces_damage(self):
        from warhammer40k_ai.rules.bondsman import BondsmanManager
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.units.wargear import Wargear
        from warhammer40k_ai.utility.model_base import Base, BaseType

        source_unit = SimpleNamespace(
            name="Knight",
            possible_abilities=["Defender's Duty (Bondsman)"],
            abilities=[],
        )
        target_unit = SimpleNamespace(
            name="Armiger",
            special_rules={},
            models=[],
            has_feel_no_pain=lambda: [],
            damaged_profile=None,
            damaged_profile_desc=None,
        )

        mgr = BondsmanManager()
        self.assertTrue(mgr.apply_bondsman_effects(source_unit, target_unit))
        self.assertEqual(target_unit.special_rules.get("bondsman_damage_reduction"), 1)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = SimpleNamespace(special_rules={}, get_parent_army=lambda: None)

        target_model = Model(
            name="Target",
            movement=6,
            toughness=5,
            save=3,
            wounds=6,
            leadership=7,
            objective_control=2,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.set_parent_unit(target_unit)
        target_unit.models = [target_model]

        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "2",
            "description": "",
            "type": "Melee",
            "name": "Test Weapon",
        }
        profile = Wargear(data).profiles["default"]

        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )

        self.assertEqual(target_model.wounds, before - 1)


if __name__ == "__main__":
    unittest.main()
