import unittest
from types import SimpleNamespace


class TestEnhancementEffects(unittest.TestCase):
    def test_move_add_uses_unit_stats_modifier(self):
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.classes.enhancement_effects import parse_enhancement_effects, apply_enhancement_effects
        from warhammer40k_ai.classes.status_effects import UnitStatsModifier

        unit = SimpleNamespace(stats={}, special_rules={}, models=[])
        m = Model(
            name="Bearer",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        m.set_parent_unit(unit)
        unit.models = [m]

        effects = parse_enhancement_effects('Add 2" to the bearer\'s Move characteristic.')
        apply_enhancement_effects(unit, effects)

        self.assertIn("movement", unit.stats)
        self.assertEqual(unit.stats["movement"][0], UnitStatsModifier.ADDITIVE)
        self.assertEqual(unit.stats["movement"][1], 2)
        self.assertEqual(m.movement, 8)

    def test_wounds_add_increases_base_and_current(self):
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.classes.enhancement_effects import parse_enhancement_effects, apply_enhancement_effects

        unit = SimpleNamespace(stats={}, special_rules={}, models=[], starting_total_wounds=0)
        m = Model(
            name="Bearer",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        m.set_parent_unit(unit)
        unit.models = [m]
        unit.starting_total_wounds = m._base_wounds

        effects = parse_enhancement_effects("Add 2 to the bearer's Wounds characteristic.")
        apply_enhancement_effects(unit, effects)

        self.assertEqual(m._base_wounds, 7)
        self.assertEqual(m.wounds, 7)
        self.assertEqual(unit.starting_total_wounds, 7)

    def test_melee_asd_bonus_affects_wound_roll_strength(self):
        # S4 vs T5 normally wounds on 5+. With +1S enhancement, wounds on 4+.
        from unittest.mock import patch

        from warhammer40k_ai.classes.wargear import Wargear, WargearProfile
        from warhammer40k_ai.classes.enhancement_effects import parse_enhancement_effects, apply_enhancement_effects

        attacker_unit = SimpleNamespace(stats={}, special_rules={}, models=[])
        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        target_unit = SimpleNamespace(toughness=5, models=[SimpleNamespace(is_alive=True)])

        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Melee",
            "name": "Test Weapon",
        }
        parent = Wargear(data)
        profile: WargearProfile = parent.profiles["default"]

        # No enhancement: roll 4 should fail (needs 5+)
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=4):
            res = profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance={})
        self.assertFalse(res["wound"])

        # Apply enhancement: +1S
        effects = parse_enhancement_effects(
            "Improve the Attacks, Strength and Damage characteristics of melee weapons equipped by the bearer by 1."
        )
        apply_enhancement_effects(attacker_unit, effects)

        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=4):
            res2 = profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance={})
        self.assertTrue(res2["wound"])

    def test_reduce_damage_taken_applies_min_1(self):
        from warhammer40k_ai.classes.wargear import Wargear, WargearProfile
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.classes.enhancement_effects import apply_enhancement_effects, parse_enhancement_effects

        attacker_unit = SimpleNamespace(stats={}, special_rules={}, models=[])
        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        target_unit = SimpleNamespace(
            stats={},
            special_rules={},
            models=[],
            has_feel_no_pain=lambda: [],
            damaged_profile=None,
            damaged_profile_desc=None,
        )
        target_model = Model(
            name="Bearer",
            movement=6,
            toughness=4,
            save=3,
            wounds=10,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.set_parent_unit(target_unit)
        target_unit.models = [target_model]

        apply_enhancement_effects(
            target_unit,
            parse_enhancement_effects("Each time an attack is allocated to the bearer, subtract 1 from the Damage characteristic of that attack."),
        )

        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Melee",
            "name": "Test Weapon",
        }
        parent = Wargear(data)
        profile: WargearProfile = parent.profiles["default"]

        attack_instance = {"below_half_distance": False, "mortal_wound": False}
        before = target_model.wounds
        profile._damage_target_with_tracking(target_model, attacker_model, attack_instance, game_map=None)
        # Damage is 1, reduced by 1 but min 1 => still 1
        self.assertEqual(target_model.wounds, before - 1)


if __name__ == "__main__":
    unittest.main()

