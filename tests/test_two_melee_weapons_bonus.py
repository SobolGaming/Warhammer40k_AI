import unittest


class _MockDatasheet:
    def __init__(self, *, abilities=None):
        self.name = "Test Unit"
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "5",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(*, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(abilities=abilities)
    return Unit(datasheet)


def _make_melee_wargear(name: str):
    from warhammer40k_ai.units.wargear import Wargear

    return Wargear(
        {
            "name": name,
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


class TestTwoMeleeWeaponsBonus(unittest.TestCase):
    def test_two_melee_weapons_bonus_applies(self):
        ability = {
            "name": "Devoted to Destruction",
            "description": (
                "If this model is equipped with two melee weapons in addition to its close combat weapon, "
                "add 2 to the Attacks characteristic of those two weapons."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit(abilities=[ability])
        model = unit.models[0]

        ccw = _make_melee_wargear("Close combat weapon")
        fist = _make_melee_wargear("Helbrute fist")
        scourge = _make_melee_wargear("Power scourge")
        model.wargear = [ccw, fist, scourge]

        bonus, eligible = unit.get_two_melee_weapons_bonus(model)
        self.assertEqual(bonus, 2)
        self.assertEqual({w.name for w in eligible}, {"Helbrute fist", "Power scourge"})

        model.wargear.append(_make_melee_wargear("Extra blade"))
        bonus, eligible = unit.get_two_melee_weapons_bonus(model)
        self.assertEqual(bonus, 0)
        self.assertEqual(eligible, [])


if __name__ == "__main__":
    unittest.main()
