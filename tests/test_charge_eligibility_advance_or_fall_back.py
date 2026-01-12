import unittest


class _MockDatasheet:
    def __init__(self, name, *, abilities=None):
        self.name = name
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
                "W": "2",
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


def _make_unit(name, *, abilities=None):
    from warhammer40k_ai.classes.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


class TestChargeEligibilityAdvanceOrFallBack(unittest.TestCase):
    def test_charge_after_advance_or_fall_back(self):
        ability = {
            "name": "Acrobatic",
            "description": "This unit is eligible to declare a charge in a turn in which it Advanced or Fell Back.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Harlequins", abilities=[ability])

        self.assertTrue(unit.has_advance_and_charge())
        self.assertTrue(unit.can_charge_after_fall_back())


if __name__ == "__main__":
    unittest.main()
