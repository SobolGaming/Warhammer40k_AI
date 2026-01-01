import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestAgainstAttackCharacteristicsTiming(unittest.TestCase):
    def test_damage_characteristic_save_bonus_applies_for_allocated_attack(self):
        from warhammer40k_ai.classes.wargear import Wargear

        # Damage characteristic is 1 (fixed), so the "vs Damage 1" rule should apply.
        w = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        prof = w.profiles["default"]

        target_unit = SimpleNamespace(special_rules={"armor_save_bonus_vs_damage_characteristic": {1: 1}})
        target_model = SimpleNamespace(name="T", save=4, inv_save=(None, ""), parent_unit=target_unit)

        # Without the +1, a 3 on a 4+ save fails. With +1, it succeeds.
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=3):
            res = prof._save_with_tracking(target_model, attack_instance={}, ap=0)
        self.assertTrue(res["saved"])
        self.assertIn("vs Damage 1", " ".join(res.get("special_effects", [])))

    def test_damage_characteristic_save_bonus_does_not_apply_when_damage_not_fixed(self):
        from warhammer40k_ai.classes.wargear import Wargear

        w = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "D3",
                "description": "",
            }
        )
        prof = w.profiles["default"]

        target_unit = SimpleNamespace(special_rules={"armor_save_bonus_vs_damage_characteristic": {1: 1}})
        target_model = SimpleNamespace(name="T", save=4, inv_save=(None, ""), parent_unit=target_unit)

        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=3):
            res = prof._save_with_tracking(target_model, attack_instance={}, ap=0)
        self.assertFalse(res["saved"])
        self.assertNotIn("vs Damage 1", " ".join(res.get("special_effects", [])))


if __name__ == "__main__":
    unittest.main()


