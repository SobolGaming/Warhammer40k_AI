import unittest


class TestCoreRulesModifiers(unittest.TestCase):
    def test_example_1_attacks_double_then_add(self):
        from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp, apply_numeric_modifiers

        base = 3
        mods = [
            Modifier(ModifierOp.MUL, 2, source="double attacks"),
            Modifier(ModifierOp.ADD, 1, source="add 1 attacks"),
        ]
        out, _dbg = apply_numeric_modifiers(base, mods)
        self.assertEqual(out, 7)

    def test_example_2a_oc_halve_then_add(self):
        from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp, apply_numeric_modifiers

        base = 2
        mods = [
            Modifier(ModifierOp.DIV, 2, source="halve OC"),
            Modifier(ModifierOp.ADD, 1, source="add 1 OC"),
        ]
        out, _dbg = apply_numeric_modifiers(base, mods)
        self.assertEqual(out, 2)

    def test_example_2b_battleshock_sets_oc_to_0_before_modifiers(self):
        from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp, apply_numeric_modifiers

        base = 2
        mods = [
            Modifier(ModifierOp.SET, 0, source="battle-shock"),
            Modifier(ModifierOp.DIV, 2, source="halve OC"),
            Modifier(ModifierOp.ADD, 1, source="add 1 OC"),
        ]
        out, _dbg = apply_numeric_modifiers(base, mods)
        self.assertEqual(out, 1)

    def test_round_up_after_all_modifiers(self):
        from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp, apply_numeric_modifiers

        # 1 / 2 = 0.5 -> rounds up to 1
        out, _dbg = apply_numeric_modifiers(1, [Modifier(ModifierOp.DIV, 2, source="halve")])
        self.assertEqual(out, 1)

        # 3 / 2 + 1 = 2.5 -> rounds up to 3
        mods = [Modifier(ModifierOp.DIV, 2), Modifier(ModifierOp.ADD, 1)]
        out, _dbg = apply_numeric_modifiers(3, mods)
        self.assertEqual(out, 3)

    def test_unmodifiable_raw_values_never_change(self):
        from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp, apply_numeric_modifiers

        out, _dbg = apply_numeric_modifiers(0, [Modifier(ModifierOp.ADD, 5)], base_raw="-")
        self.assertEqual(out, 0)

        out, _dbg = apply_numeric_modifiers(20, [Modifier(ModifierOp.SUB, 10)], base_raw='20+"')
        self.assertEqual(out, 20)


if __name__ == "__main__":
    unittest.main()


