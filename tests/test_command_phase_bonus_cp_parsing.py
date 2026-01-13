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


class TestCommandPhaseBonusCpParsing(unittest.TestCase):
    def test_command_phase_bonus_cp_from_ability(self):
        ability = {
            "name": "Tactical Insight",
            "description": "At the start of your Command phase, you gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Commander", abilities=[ability])
        self.assertEqual(int(unit.special_rules.get("command_phase_bonus_cp", 0)), 1)

    def test_command_phase_bonus_cp_on_battlefield(self):
        ability = {
            "name": "Strategic Acumen",
            "description": "At the start of your Command phase, if this model is on the battlefield, you gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Commander", abilities=[ability])
        self.assertEqual(int(unit.special_rules.get("command_phase_bonus_cp", 0)), 1)


if __name__ == "__main__":
    unittest.main()
