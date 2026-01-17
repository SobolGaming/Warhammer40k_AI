import unittest
from types import SimpleNamespace


class TestDatasheetsWargearParsing(unittest.TestCase):
    def test_multprofile_weapon_rows_merge_into_one_wargear(self):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        ds = SimpleNamespace(
            datasheets_wargear=[
                {
                    "name": "Plasma gun – standard",
                    "type": "Ranged",
                    "range": "24",
                    "A": "1",
                    "BS_WS": "3+",
                    "S": "8",
                    "AP": "-3",
                    "D": "1",
                    "description": "",
                },
                {
                    "name": "Plasma gun – supercharge",
                    "type": "Ranged",
                    "range": "24",
                    "A": "1",
                    "BS_WS": "3+",
                    "S": "8",
                    "AP": "-3",
                    "D": "2",
                    "description": "hazardous",
                },
            ]
        )

        wargear = u._parse_wargear(ds)
        self.assertEqual(len(wargear), 1)
        self.assertEqual(wargear[0].name.lower(), "plasma gun")
        self.assertIn("standard", wargear[0].profiles)
        self.assertIn("supercharge", wargear[0].profiles)

    def test_loadout_matching_ignores_apostrophes(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.wargear import Wargear

        u = Unit.__new__(Unit)
        u.possible_wargear = [Wargear({"name": "Khaine’s Blade", "type": "Melee", "range": "Melee", "A": "1", "BS_WS": "3+", "S": "4", "AP": "0", "D": "1", "description": ""})]
        loadout = "This model is equipped with: Khaine's Blade."
        found = u._parse_loadout(loadout, model_name="")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "Khaine's Blade")

    def test_keywords_parse_defensively(self):
        from warhammer40k_ai.units.wargear import Wargear

        w = Wargear(
            {
                "name": "Test gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "rapid fire 1; sustained hits 2, twin-linked",
            }
        )
        prof = w.profiles["default"]
        self.assertTrue(prof.is_rapid_fire())
        self.assertTrue(prof.is_sustained_hits())
        self.assertTrue(prof.is_twin_linked())

    def test_loadout_parses_an_model_prefix(self):
        # Ensure "An X is equipped with:" is parsed (not just "A X is equipped with:")
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.wargear import Wargear

        u = Unit.__new__(Unit)
        u.possible_wargear = [Wargear({"name": "onslaught gatling cannon", "type": "Ranged", "range": "24", "A": "1", "BS_WS": "3+", "S": "5", "AP": "0", "D": "1", "description": ""})]
        loadout = "An Invader ATV is equipped with: onslaught gatling cannon."
        found = u._parse_loadout(loadout, model_name="invader atv")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name.lower(), "onslaught gatling cannon")


if __name__ == "__main__":
    unittest.main()

