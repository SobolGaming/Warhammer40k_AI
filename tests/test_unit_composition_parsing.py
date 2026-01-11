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

    def test_or_splits_options_and_tracks_maximum(self):
        from warhammer40k_ai.classes.unit import Unit

        u = Unit.__new__(Unit)
        rows = [
            {"description": "This unit can contain a maximum of 20 models."},
            {"description": "20 MODELS MAXIMUM"},
            {"description": "1 Jakhal Pack Leader, 1 Dishonoured and 8 Jakhals"},
            {"description": "or:"},
            {"description": "1 Jakhal Pack Leader, 2 Dishonoured and 17 Jakhals"},
        ]
        parsed = u._parse_unit_composition(rows)
        self.assertEqual(parsed, {"Jakhal Pack Leader": (1, 1), "Dishonoured": (1, 1), "Jakhals": (8, 8)})
        self.assertEqual(
            getattr(u, "unit_composition_options", None),
            [
                {"Jakhal Pack Leader": (1, 1), "Dishonoured": (1, 1), "Jakhals": (8, 8)},
                {"Jakhal Pack Leader": (1, 1), "Dishonoured": (2, 2), "Jakhals": (17, 17)},
            ],
        )
        # The cap should be captured for validation logic.
        self.assertEqual(getattr(u, "unit_models_maximum", None), 20)

    def test_or_groups_multiline_entries(self):
        from warhammer40k_ai.classes.unit import Unit

        u = Unit.__new__(Unit)
        rows = [
            {"description": "1 Kill Team Sergeant"},
            {"description": "1 Gravis Veteran"},
            {"description": "3 Deathwatch Veterans"},
            {"description": "OR"},
            {"description": "1 Kill Team Sergeant"},
            {"description": "2 Gravis Veterans"},
            {"description": "7 Deathwatch Veterans"},
        ]
        parsed = u._parse_unit_composition(rows)
        opts = getattr(u, "unit_composition_options", [])
        self.assertEqual(len(opts), 2)
        self.assertEqual(parsed, opts[0])
        self.assertEqual(opts[0]["Kill Team Sergeant"], (1, 1))
        self.assertEqual(opts[0]["Gravis Veteran"], (1, 1))
        self.assertEqual(opts[0]["Deathwatch Veterans"], (3, 3))
        self.assertEqual(opts[1]["Kill Team Sergeant"], (1, 1))
        self.assertEqual(opts[1]["Gravis Veterans"], (2, 2))
        self.assertEqual(opts[1]["Deathwatch Veterans"], (7, 7))


if __name__ == "__main__":
    unittest.main()
