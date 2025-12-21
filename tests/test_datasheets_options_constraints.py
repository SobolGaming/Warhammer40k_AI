import unittest
from types import SimpleNamespace


class TestDatasheetsOptionsConstraints(unittest.TestCase):
    def _make_wargear(self, name: str, wtype: str = "Ranged"):
        from warhammer40k_ai.classes.wargear import Wargear

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

    def test_equipped_with_condition_only_applies_to_matching_models(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import WargearOption, WargearOptionType, Quantity

        pulse_carbine = self._make_wargear("pulse carbine")
        grenade_launcher = self._make_wargear("semi-automatic grenade launcher")

        u = Unit.__new__(Unit)
        u.models = [
            SimpleNamespace(name="Model", wargear=[pulse_carbine], optional_wargear=[]),
            SimpleNamespace(name="Model", wargear=[], optional_wargear=[]),
        ]
        u.possible_wargear = [pulse_carbine, grenade_launcher]
        u.wargear_options = [
            WargearOption(
                WargearOptionType.ADDITIONAL,
                wargear_from=[],
                wargear_to=[[(1, "semi-automatic grenade launcher")]],
                model_name="model",
                model_quantity=Quantity(min=1, max=2),
                item_quantity=Quantity(min=1, max=1),
                conditionals=["equipped with pulse carbine"],
            )
        ]

        u.apply_wargear_options("semi-automatic grenade launcher")
        self.assertEqual([wg.name for wg in u.models[0].wargear], ["pulse carbine", "semi-automatic grenade launcher"])
        self.assertEqual([wg.name for wg in u.models[1].wargear], [])

    def test_contains_models_condition_blocks_when_not_met(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import WargearOption, WargearOptionType, Quantity

        sniper = self._make_wargear("sniper rifle")
        tankstopper = self._make_wargear("tankstopper rifle")

        opt = WargearOption(
            WargearOptionType.REPLACEMENT,
            wargear_from=[[(1, "sniper rifle")]],
            wargear_to=[[(1, "tankstopper rifle")]],
            model_name="model",
            model_quantity=Quantity(min=1, max=1),
            item_quantity=Quantity(min=1, max=1),
            conditionals=["contains 10 models"],
        )

        u_small = Unit.__new__(Unit)
        u_small.models = [SimpleNamespace(name="Model", wargear=[sniper], optional_wargear=[]) for _ in range(5)]
        u_small.possible_wargear = [sniper, tankstopper]
        u_small.wargear_options = [opt]
        u_small.apply_wargear_options("tankstopper rifle")
        self.assertEqual([wg.name for wg in u_small.models[0].wargear], ["sniper rifle"])

        u_big = Unit.__new__(Unit)
        u_big.models = [SimpleNamespace(name="Model", wargear=[sniper], optional_wargear=[]) for _ in range(10)]
        u_big.possible_wargear = [sniper, tankstopper]
        u_big.wargear_options = [opt]
        u_big.apply_wargear_options("tankstopper rifle")
        self.assertEqual([wg.name for wg in u_big.models[0].wargear], ["tankstopper rifle"])

    def test_cannot_replace_lock_prevents_future_replacement(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import WargearOption, WargearOptionType, Quantity

        lasgun = self._make_wargear("lasgun")
        vox = self._make_wargear("vox-caster")
        flamer = self._make_wargear("flamer")

        u = Unit.__new__(Unit)
        u.models = [SimpleNamespace(name="Model", wargear=[lasgun], optional_wargear=[])]
        u.possible_wargear = [lasgun, vox, flamer]
        u.wargear_options = [
            WargearOption(
                WargearOptionType.ADDITIONAL,
                wargear_from=[],
                wargear_to=[[(1, "vox-caster")]],
                model_name="model",
                model_quantity=Quantity(min=1, max=1),
                item_quantity=Quantity(min=1, max=1),
                conditionals=["cannot replace lasgun"],
            ),
            WargearOption(
                WargearOptionType.REPLACEMENT,
                wargear_from=[[(1, "lasgun")]],
                wargear_to=[[(1, "flamer")]],
                model_name="model",
                model_quantity=Quantity(min=1, max=1),
                item_quantity=Quantity(min=1, max=1),
                conditionals=[],
            ),
        ]

        u.apply_wargear_options("vox-caster")
        self.assertEqual(sorted([wg.name for wg in u.models[0].wargear]), sorted(["lasgun", "vox-caster"]))

        u.apply_wargear_options("flamer")
        # lock should block replacing lasgun
        self.assertEqual(sorted([wg.name for wg in u.models[0].wargear]), sorted(["lasgun", "vox-caster"]))

    def test_unit_unique_weapon_caps_at_one(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import WargearOption, WargearOptionType, Quantity

        plasma = self._make_wargear("plasma gun")
        u = Unit.__new__(Unit)
        u.models = [SimpleNamespace(name="Model", wargear=[], optional_wargear=[]) for _ in range(3)]
        u.possible_wargear = [plasma]
        u.wargear_options = [
            WargearOption(
                WargearOptionType.ADDITIONAL,
                wargear_from=[],
                wargear_to=[[(1, "plasma gun")]],
                model_name="model",
                model_quantity=Quantity(min=1, max=3),
                item_quantity=Quantity(min=1, max=1),
                conditionals=["you cannot select the same weapon from this list more than once per unit"],
            )
        ]

        u.apply_wargear_options("plasma gun")
        total = sum(1 for m in u.models for wg in m.wargear if wg.name == "plasma gun")
        self.assertEqual(total, 1)

    def test_apply_by_name_is_strictly_non_ambiguous(self):
        """
        If a wargear name appears in multiple different option-choices, apply_wargear_options(name) should
        not guess. It should no-op until a disambiguating item is chosen.
        """
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import WargearOption, WargearOptionType, Quantity

        plasma = self._make_wargear("plasma gun")
        melta = self._make_wargear("meltagun")
        flamer = self._make_wargear("flamer")

        u = Unit.__new__(Unit)
        u.models = [SimpleNamespace(name="Model", wargear=[], optional_wargear=[])]
        u.possible_wargear = [plasma, melta, flamer]
        u.wargear_options = [
            WargearOption(
                WargearOptionType.ADDITIONAL,
                wargear_from=[],
                wargear_to=[[(1, "plasma gun")]],
                model_name="model",
                model_quantity=Quantity(min=1, max=1),
                item_quantity=Quantity(min=1, max=1),
                conditionals=[],
            ),
            WargearOption(
                WargearOptionType.ADDITIONAL,
                wargear_from=[],
                wargear_to=[[(1, "plasma gun"), (1, "meltagun")]],
                model_name="model",
                model_quantity=Quantity(min=1, max=1),
                item_quantity=Quantity(min=1, max=1),
                conditionals=[],
            ),
        ]

        # plasma gun is ambiguous (present in both options) -> no-op
        u.apply_wargear_options("plasma gun")
        self.assertEqual([wg.name for wg in u.models[0].wargear], [])

        # meltagun is unique to the second option's choice -> applies that choice
        u.apply_wargear_options("meltagun")
        self.assertEqual(sorted([wg.name for wg in u.models[0].wargear]), sorted(["plasma gun", "meltagun"]))

    def test_item_limit_equals_number_of_equipped_applies_multiple_times(self):
        """
        e.g. "For each Helbrute fist this model is equipped with, it can be equipped with..."
        should add the chosen item once per equipped fist.
        """
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import WargearOption, WargearOptionType, Quantity

        fist = self._make_wargear("helbrute fist", wtype="Melee")
        combi = self._make_wargear("combi-bolter")

        u = Unit.__new__(Unit)
        u.models = [SimpleNamespace(name="Model", wargear=[fist, fist], optional_wargear=[])]
        u.possible_wargear = [fist, combi]
        u.wargear_options = [
            WargearOption(
                WargearOptionType.ADDITIONAL,
                wargear_from=[],
                wargear_to=[[(1, "combi-bolter")]],
                model_name="model",
                model_quantity=Quantity(min=1, max=1),
                item_quantity=Quantity(min=1, max=1),
                conditionals=["item_limit is equal to number of equipped helbrute fist"],
            )
        ]

        # First selection consumes 1 slot
        u.apply_wargear_options("combi-bolter")
        total = sum(1 for wg in u.models[0].wargear if wg.name.lower() == "combi-bolter")
        self.assertEqual(total, 1)

        # Second selection consumes the second slot
        u.apply_wargear_options("combi-bolter")
        total = sum(1 for wg in u.models[0].wargear if wg.name.lower() == "combi-bolter")
        self.assertEqual(total, 2)

        # Third selection should no-op (no slots left)
        u.apply_wargear_options("combi-bolter")
        total = sum(1 for wg in u.models[0].wargear if wg.name.lower() == "combi-bolter")
        self.assertEqual(total, 2)


if __name__ == "__main__":
    unittest.main()

