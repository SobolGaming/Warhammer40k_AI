import unittest


class TestInvulnerableSaveAbilities(unittest.TestCase):
    def _make_model(self, name: str, save: int):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        return Model(
            name=name,
            movement=6,
            toughness=4,
            save=save,
            wounds=2,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1),
        )

    def test_parse_loadout_adds_optional_wargear_for_wargear_ability(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.ability import Ability

        u = Unit.__new__(Unit)
        u.possible_wargear = []
        u.possible_abilities = [
            Ability(
                "Storm Shield",
                "",
                "The bearer has a 4+ invulnerable save.",
                "Wargear",
                "",
            )
        ]
        loadout = "This model is equipped with: Storm Shield."
        wargear, optional = u._parse_loadout(loadout, model_name="", return_optional=True)
        self.assertEqual(wargear, [])
        self.assertEqual(optional, ["Storm Shield"])

    def test_model_invulnerable_save_from_optional_wargear(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.units.wargear import WargearProfile

        unit = Unit.__new__(Unit)
        unit.possible_wargear = []
        unit.possible_abilities = [
            Ability(
                "Storm Shield",
                "",
                "The bearer has a 4+ invulnerable save.",
                "Wargear",
                "",
            )
        ]
        unit._ability_cache = {}

        model_with = self._make_model("With Shield", save=5)
        model_without = self._make_model("No Shield", save=5)
        model_with.optional_wargear.append("Storm Shield")

        model_with.set_parent_unit(unit)
        model_without.set_parent_unit(unit)
        unit.models = [model_with, model_without]

        profile = WargearProfile(
            "default",
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
            },
        )

        res_with = profile._save_with_tracking(
            model_with,
            {"weapon_profile": profile, "is_mortal": False},
            ap=0,
        )
        res_without = profile._save_with_tracking(
            model_without,
            {"weapon_profile": profile, "is_mortal": False},
            ap=0,
        )

        self.assertEqual(res_with["final_save"], 4)
        self.assertEqual(res_without["final_save"], 5)


if __name__ == "__main__":
    unittest.main()
