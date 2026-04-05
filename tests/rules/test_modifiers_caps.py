import unittest


class TestCoreRulesCharacteristicCaps(unittest.TestCase):
    def test_damage_floor_and_zero_exception(self):
        from warhammer40k_ai.utility.modifiers import apply_characteristic_caps

        self.assertEqual(apply_characteristic_caps("damage", 0, allow_damage_zero=False), 1)
        self.assertEqual(apply_characteristic_caps("damage", 0, allow_damage_zero=True), 0)
        self.assertEqual(apply_characteristic_caps("damage", -3, allow_damage_zero=False), 1)

    def test_attacks_strength_toughness_floor_1(self):
        from warhammer40k_ai.utility.modifiers import apply_characteristic_caps

        for c in ("attacks", "strength", "toughness"):
            self.assertEqual(apply_characteristic_caps(c, 0), 1)
            self.assertEqual(apply_characteristic_caps(c, -5), 1)

    def test_objective_control_never_below_0(self):
        from warhammer40k_ai.utility.modifiers import apply_characteristic_caps

        self.assertEqual(apply_characteristic_caps("objective_control", -1), 0)
        self.assertEqual(apply_characteristic_caps("oc", -10), 0)

    def test_ap_never_worse_than_0(self):
        from warhammer40k_ai.utility.modifiers import apply_characteristic_caps

        self.assertEqual(apply_characteristic_caps("ap", 1), 0)
        self.assertEqual(apply_characteristic_caps("ap", 0), 0)
        self.assertEqual(apply_characteristic_caps("ap", -2), -2)

    def test_leadership_clamped_between_5_and_8(self):
        from warhammer40k_ai.utility.modifiers import apply_characteristic_caps

        self.assertEqual(apply_characteristic_caps("leadership", 4), 5)  # can't be 4+ or better
        self.assertEqual(apply_characteristic_caps("leadership", 9), 8)  # can't be 9+ or worse
        self.assertEqual(apply_characteristic_caps("leadership", 6), 6)

    def test_move_and_range_floor_1(self):
        from warhammer40k_ai.utility.modifiers import apply_characteristic_caps

        self.assertEqual(apply_characteristic_caps("movement", 0), 1)
        self.assertEqual(apply_characteristic_caps("range", 0, is_ranged_weapon_range=True), 1)
        self.assertEqual(apply_characteristic_caps("range", 0, is_ranged_weapon_range=False), 0)


if __name__ == "__main__":
    unittest.main()


