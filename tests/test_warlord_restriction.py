import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = ["CHARACTER"]
        self.faction_keywords = ["TEST"]
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


def _make_unit(name, *, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


class TestWarlordRestriction(unittest.TestCase):
    def test_cannot_be_warlord_rule_blocks_selection(self):
        from warhammer40k_ai.roster.army import Army, ArmyValidationError

        abilities = [
            {
                "name": "Cannot Be Warlord",
                "description": "This model cannot be your Warlord.",
                "type": "Abilities",
                "parameter": "",
            }
        ]
        unit = _make_unit("Restricted", abilities=abilities)
        army = Army("Test", "Detachment")
        army.faction_id = "TS"
        army.add_unit(unit)

        self.assertTrue(unit.special_rules.get("cannot_be_warlord"))
        with self.assertRaises(ArmyValidationError):
            army.select_warlord(unit)

    def test_no_restriction_allows_selection(self):
        from warhammer40k_ai.roster.army import Army

        unit = _make_unit("Allowed")
        army = Army("Test", "Detachment")
        army.faction_id = "TS"
        army.add_unit(unit)

        army.select_warlord(unit)
        self.assertTrue(unit.is_warlord)


if __name__ == "__main__":
    unittest.main()
