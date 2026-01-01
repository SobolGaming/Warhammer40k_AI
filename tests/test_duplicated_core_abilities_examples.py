import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestDuplicatedCoreAbilitiesExamples(unittest.TestCase):
    def test_example_1_stealth_not_cumulative(self):
        # Stealth is checked as a boolean; duplicates should not stack.
        from warhammer40k_ai.classes.wargear import Wargear

        w = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        prof = w.profiles["default"]
        attacker_unit = SimpleNamespace(round_state=SimpleNamespace(remained_stationary_this_round=False), special_rules={})
        attacker = SimpleNamespace(name="A", parent_unit=attacker_unit)

        class _Target:
            def has_stealth(self):
                # Even if multiple sources exist, this returns True only once.
                return True

        target = _Target()

        # With BS 4+, a roll of 4 hits normally. With Stealth (-1 to hit), it becomes 5+ and misses.
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=4):
            attack_instance = {}
            res = prof._hit_target_with_tracking(target, attacker, attack_instance)
        self.assertFalse(res["hit"])
        # Modifier list should only include one Stealth entry (not -2).
        stealth_mods = [m for m in res.get("modifiers", []) if "Stealth" in str(m)]
        self.assertEqual(len(stealth_mods), 1)

    def test_example_2_devastating_wounds_not_cumulative(self):
        # Devastating Wounds is a boolean flag; duplicates should not stack to "double mortals".
        from warhammer40k_ai.classes.wargear import Wargear

        # Weapon already has Devastating Wounds; "temporary" would just be another instance.
        w = Wargear(
            {
                "name": "Sternguard Bolt Rifle",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                # NOTE: engine parses weapon keywords from the `description` field for Wahapedia-format exports.
                "description": "Devastating Wounds",
            }
        )
        prof = w.profiles["default"]
        attacker_unit = SimpleNamespace(round_state=SimpleNamespace(remained_stationary_this_round=False), special_rules={})
        attacker = SimpleNamespace(name="A", parent_unit=attacker_unit, has_temporary_devastating_wounds_melee=lambda: False)
        target = SimpleNamespace(toughness=4, get_models_for_wound_allocation=lambda: [SimpleNamespace(is_alive=True)], has_keyword=lambda _k: False)

        # Force a critical wound roll of 6.
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=6):
            attack_instance = {"below_half_distance": False}
            res = prof._wound_target_with_tracking(target, attacker, attack_instance)

        self.assertTrue(res["wound"])
        self.assertTrue(attack_instance.get("mortal_wound", False))
        # Only a boolean is tracked; cannot become "2 mortals" here.
        self.assertIs(attack_instance.get("mortal_wound"), True)

    def test_example_3_sustained_hits_choose_one_instance(self):
        # If multiple Sustained Hits instances exist (1 and 2), they are not cumulative.
        # The controlling player chooses; engine defaults to the "best" (highest avg), so Sustained Hits 2.
        from warhammer40k_ai.classes.wargear import Wargear

        w = Wargear(
            {
                "name": "Heavy Bolter",
                "type": "Ranged",
                "range": "36",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "-1",
                "D": "1",
                # NOTE: engine parses weapon keywords from the `description` field.
                "description": "Sustained Hits 1, Sustained Hits 2",
            }
        )
        prof = w.profiles["default"]
        attacker_unit = SimpleNamespace(round_state=SimpleNamespace(remained_stationary_this_round=False), special_rules={})
        attacker = SimpleNamespace(name="A", parent_unit=attacker_unit)
        target = SimpleNamespace(has_stealth=lambda: False)

        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=6):
            attack_instance = {}
            res = prof._hit_target_with_tracking(target, attacker, attack_instance)

        self.assertTrue(res["hit"])
        self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 2)

    def test_anti_duplicates_choose_best_for_same_keyword(self):
        from warhammer40k_ai.classes.wargear import Wargear

        w = Wargear(
            {
                "name": "Test Anti",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                # NOTE: engine parses weapon keywords from the `description` field.
                "description": "Anti-Vehicle 4+, Anti-Vehicle 3+",
            }
        )
        prof = w.profiles["default"]
        attacker_unit = SimpleNamespace(round_state=SimpleNamespace(remained_stationary_this_round=False), special_rules={})
        attacker = SimpleNamespace(name="A", parent_unit=attacker_unit, has_temporary_devastating_wounds_melee=lambda: False)
        target = SimpleNamespace(
            toughness=10,
            get_models_for_wound_allocation=lambda: [SimpleNamespace(is_alive=True)],
            has_keyword=lambda k: str(k).lower() == "vehicle",
        )

        # Roll a 3: should trigger Anti-Vehicle 3+ (best), even though there's also Anti-Vehicle 4+.
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=3):
            attack_instance = {"below_half_distance": False}
            res = prof._wound_target_with_tracking(target, attacker, attack_instance)
        self.assertTrue(res["wound"])
        self.assertTrue(attack_instance.get("crit_wound", False))


if __name__ == "__main__":
    unittest.main()


