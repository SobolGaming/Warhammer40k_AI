import unittest
from types import SimpleNamespace


class TestArmyListWargearValidation(unittest.TestCase):
    def _make_wargear(self, name: str, wtype: str = "Ranged", keywords: str = ""):
        from warhammer40k_ai.units.wargear import Wargear

        # Minimal valid wargear_data for construction
        return Wargear(
            {
                "name": name,
                "type": wtype,
                "range": "24" if wtype.lower() == "ranged" else "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": keywords,  # parsed into profile keywords (e.g. "Pistol")
            }
        )

    def test_validate_wargear_selection_enforces_two_ranged_requires_pistol(self):
        from warhammer40k_ai.units.unit import Unit

        rifle = self._make_wargear("rifle", wtype="Ranged")
        carbine = self._make_wargear("carbine", wtype="Ranged")
        pistol = self._make_wargear("sidearm", wtype="Ranged", keywords="Pistol")

        u = Unit.__new__(Unit)
        u.name = "Test Unit"
        u._wargear_constraints = {
            "max_ranged_weapons": None,
            "two_ranged_requires_pistol": True,
            "two_ranged_requires_cyclone_pair": False,
            "mutex_sets": [],
            "max_counts": {},
            "model_option_mutex": False,
            "forbidden_if_any_option": set(),
        }

        # Invalid: two ranged, none pistol
        u.models = [SimpleNamespace(name="Model", wargear=[rifle, carbine], optional_wargear=[])]
        with self.assertRaises(ValueError):
            u.validate_wargear_selection()

        # Valid: two ranged, exactly one pistol
        u.models = [SimpleNamespace(name="Model", wargear=[rifle, pistol], optional_wargear=[])]
        u.validate_wargear_selection()


