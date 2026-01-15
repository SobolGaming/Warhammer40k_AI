import unittest
from types import SimpleNamespace


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


class TestChargeMoveDevastatingWounds(unittest.TestCase):
    def test_charge_move_grants_devastating_wounds_melee(self):
        ability = {
            "name": "Grisly Onslaught",
            "description": (
                "Each time this model makes a Charge move, until the end of the turn, its melee weapons "
                "have the [DEVASTATING WOUNDS] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Charger", abilities=[ability])

        self.assertFalse(unit.models[0].has_temporary_devastating_wounds_melee())
        applied = unit._apply_charge_move_devastating_wounds()
        self.assertTrue(applied)
        self.assertTrue(unit.models[0].has_temporary_devastating_wounds_melee())

        # End of Fight phase clears the temporary effect.
        phase = SimpleNamespace(name="FIGHT_PHASE")
        unit.models[0].on_phase_end(phase)
        self.assertFalse(unit.models[0].has_temporary_devastating_wounds_melee())


if __name__ == "__main__":
    unittest.main()
