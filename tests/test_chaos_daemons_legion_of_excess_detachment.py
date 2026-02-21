import unittest


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Chaos Daemons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "5",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords)
    return Unit(datasheet)


class TestChaosDaemonsLegionOfExcessDetachment(unittest.TestCase):
    def test_beguiling_aura_allows_charge_after_fall_back(self):
        from warhammer40k_ai.roster.army import Army

        army = Army("Chaos Daemons", detachment_type="Legion of Excess")
        army.faction_id = "CD"
        unit = _make_unit(
            "Daemonettes",
            keywords=["SLAANESH"],
            faction_keywords=["LEGIONES DAEMONICA"],
        )
        army.add_unit(unit)

        self.assertTrue(unit.can_charge_after_fall_back())

    def test_beguiling_aura_requires_slaanesh_legiones_daemonica(self):
        from warhammer40k_ai.roster.army import Army

        army = Army("Chaos Daemons", detachment_type="Legion of Excess")
        army.faction_id = "CD"
        unit = _make_unit(
            "Bloodletters",
            keywords=["KHORNE"],
            faction_keywords=["LEGIONES DAEMONICA"],
        )
        army.add_unit(unit)

        self.assertFalse(unit.can_charge_after_fall_back())


if __name__ == "__main__":
    unittest.main()
