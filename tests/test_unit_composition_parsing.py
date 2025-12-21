import unittest


class TestUnitCompositionParsing(unittest.TestCase):
    def test_simple_and_range_entries(self):
        from warhammer40k_ai.classes.unit import Unit

        u = Unit.__new__(Unit)
        rows = [{"description": "1 Boss Nob"}, {"description": "2-5 Space Marine Bikers"}]
        parsed = u._parse_unit_composition(rows)
        self.assertEqual(parsed["Boss Nob"], (1, 1))
        self.assertEqual(parsed["Space Marine Bikers"], (2, 5))

    def test_composite_and_splits_into_multiple_entries(self):
        from warhammer40k_ai.classes.unit import Unit

        u = Unit.__new__(Unit)
        rows = [{"description": "1 Runtherd and 10 Gretchin"}]
        parsed = u._parse_unit_composition(rows)
        self.assertEqual(parsed["Runtherd"], (1, 1))
        self.assertEqual(parsed["Gretchin"], (10, 10))

    def test_composite_commas_and_and(self):
        from warhammer40k_ai.classes.unit import Unit

        u = Unit.__new__(Unit)
        rows = [{"description": "1 Grenadier Sergeant, 7 Grenadiers and 1 Heavy Weapons Team"}]
        parsed = u._parse_unit_composition(rows)
        self.assertEqual(parsed["Grenadier Sergeant"], (1, 1))
        self.assertEqual(parsed["Grenadiers"], (7, 7))
        self.assertEqual(parsed["Heavy Weapons Team"], (1, 1))

    def test_does_not_split_and_inside_model_name(self):
        # "Adrasite and Pyrithite" is part of the model name; it should not split because it's not followed by a digit.
        from warhammer40k_ai.classes.unit import Unit

        u = Unit.__new__(Unit)
        rows = [{"description": "5 Custodian Guard with Adrasite and Pyrithite Spears"}]
        parsed = u._parse_unit_composition(rows)
        self.assertEqual(parsed, {"Custodian Guard with Adrasite and Pyrithite Spears": (5, 5)})

    def test_ignores_maximum_lines_and_or(self):
        from warhammer40k_ai.classes.unit import Unit

        u = Unit.__new__(Unit)
        rows = [
            {"description": "This unit can contain a maximum of 10 models."},
            {"description": "10 MODELS MAXIMUM"},
            {"description": "OR"},
            {"description": "1 Warboss"},
        ]
        parsed = u._parse_unit_composition(rows)
        self.assertEqual(parsed, {"Warboss": (1, 1)})
        # The cap should be captured for validation logic.
        self.assertEqual(getattr(u, "unit_models_maximum", None), 10)


if __name__ == "__main__":
    unittest.main()

