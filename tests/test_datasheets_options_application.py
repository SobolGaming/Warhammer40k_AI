import unittest
from types import SimpleNamespace


class TestDatasheetsOptionsApplication(unittest.TestCase):
    def _make_wargear(self, name: str, wtype: str = "Ranged"):
        from warhammer40k_ai.classes.wargear import Wargear

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
                "description": "",
            }
        )

    def test_apply_replacement_option_equips_new_wargear(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import WargearOption, WargearOptionType, Quantity

        bolt_pistol = self._make_wargear("bolt pistol")
        plasma_pistol = self._make_wargear("plasma pistol")

        u = Unit.__new__(Unit)
        u.models = [SimpleNamespace(name="Model", wargear=[bolt_pistol], optional_wargear=[])]
        u.possible_wargear = [bolt_pistol, plasma_pistol]
        u.wargear_options = [
            WargearOption(
                WargearOptionType.REPLACEMENT,
                wargear_from=[[(1, "bolt pistol")]],
                wargear_to=[[(1, "plasma pistol")]],
                model_name="model",
                model_quantity=Quantity(min=1, max=1),
                item_quantity=Quantity(min=1, max=1),
                conditionals=[],
            )
        ]

        u.apply_wargear_options("plasma pistol")
        m = u.models[0]
        self.assertEqual([wg.name for wg in m.wargear], ["plasma pistol"])

    def test_apply_additional_option_adds_wargear(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import WargearOption, WargearOptionType, Quantity

        storm_bolter = self._make_wargear("storm bolter")

        u = Unit.__new__(Unit)
        u.models = [SimpleNamespace(name="Model", wargear=[], optional_wargear=[])]
        u.possible_wargear = [storm_bolter]
        u.wargear_options = [
            WargearOption(
                WargearOptionType.ADDITIONAL,
                wargear_from=[],
                wargear_to=[[(1, "storm bolter")]],
                model_name="model",
                model_quantity=Quantity(min=1, max=1),
                item_quantity=Quantity(min=1, max=1),
                conditionals=[],
            )
        ]

        u.apply_wargear_options("storm bolter")
        self.assertEqual(u.models[0].wargear[0].name, "storm bolter")

    def test_all_models_replacement_is_all_or_none(self):
        """
        "All models in this unit..." is a boolean toggle: either every model replaces, or none do.
        """
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import WargearOption, WargearOptionType, Quantity

        flamestorm = self._make_wargear("flamestorm gauntlets")
        boltstorm = self._make_wargear("auto boltstorm gauntlets")
        fragstorm = self._make_wargear("fragstorm grenade launcher")

        u = Unit.__new__(Unit)
        u.models = [
            SimpleNamespace(name="Model", wargear=[flamestorm], optional_wargear=[]),
            SimpleNamespace(name="Model", wargear=[flamestorm], optional_wargear=[]),
        ]
        u.possible_wargear = [flamestorm, boltstorm, fragstorm]
        u.wargear_options = [
            WargearOption(
                WargearOptionType.REPLACEMENT,
                wargear_from=[[(1, "flamestorm gauntlets")]],
                wargear_to=[[(1, "auto boltstorm gauntlets"), (1, "fragstorm grenade launcher")]],
                model_name="model",
                model_quantity=Quantity(min=2, max=2),  # all-or-none
                item_quantity=Quantity(min=1, max=1),
                conditionals=[],
            )
        ]

        u.apply_wargear_options("auto boltstorm gauntlets")
        for m in u.models:
            self.assertEqual(sorted([wg.name for wg in m.wargear]), sorted(["auto boltstorm gauntlets", "fragstorm grenade launcher"]))

        # Now break eligibility: second model doesn't have flamestorm gauntlets -> nothing should change.
        u2 = Unit.__new__(Unit)
        u2.models = [
            SimpleNamespace(name="Model", wargear=[flamestorm], optional_wargear=[]),
            SimpleNamespace(name="Model", wargear=[], optional_wargear=[]),
        ]
        u2.possible_wargear = [flamestorm, boltstorm, fragstorm]
        u2.wargear_options = list(u.wargear_options)

        u2.apply_wargear_options("auto boltstorm gauntlets")
        self.assertEqual([wg.name for wg in u2.models[0].wargear], ["flamestorm gauntlets"])
        self.assertEqual([wg.name for wg in u2.models[1].wargear], [])


if __name__ == "__main__":
    unittest.main()

