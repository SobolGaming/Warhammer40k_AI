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


class TestBearerSmokeKeyword(unittest.TestCase):
    def test_bearer_smoke_keyword_added(self):
        ability = {
            "name": "Smoke Launcher",
            "description": "The bearer has the SMOKE keyword.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Smoke Unit", abilities=[ability])
        self.assertTrue(unit.has_keyword("SMOKE"))


if __name__ == "__main__":
    unittest.main()
