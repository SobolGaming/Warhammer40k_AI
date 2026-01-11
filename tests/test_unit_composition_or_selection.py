import unittest


class MockDatasheet:
    def __init__(self):
        self.name = "Test Unit"
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [
            {"description": "1 Alpha, 1 Beta and 8 Gamma"},
            {"description": "OR"},
            {"description": "1 Alpha, 2 Beta and 17 Gamma"},
        ]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 10}]
        self.datasheets_models = [
            {
                "name": "Alpha",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            },
            {
                "name": "Beta",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            },
            {
                "name": "Gamma",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            },
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


class TestUnitCompositionOrSelection(unittest.TestCase):
    def _count_models(self, unit):
        counts = {}
        for model in unit.models:
            counts[model.name] = counts.get(model.name, 0) + 1
        return counts

    def test_selects_first_option_for_ten(self):
        from warhammer40k_ai.classes.unit import Unit

        unit = Unit(MockDatasheet(), quantity=10)
        self.assertEqual(
            self._count_models(unit),
            {"Alpha": 1, "Beta": 1, "Gamma": 8},
        )

    def test_selects_second_option_for_twenty(self):
        from warhammer40k_ai.classes.unit import Unit

        unit = Unit(MockDatasheet(), quantity=20)
        self.assertEqual(
            self._count_models(unit),
            {"Alpha": 1, "Beta": 2, "Gamma": 17},
        )


if __name__ == "__main__":
    unittest.main()
