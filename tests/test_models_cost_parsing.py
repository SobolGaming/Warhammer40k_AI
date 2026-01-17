import unittest
from types import SimpleNamespace


class TestDatasheetsModelsCost(unittest.TestCase):
    def test_composite_description_sums_model_counts(self):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        parsed = u._parse_models_cost(
            [
                {"description": "1 Sword Brother, 4 Initiates and 5 Neophytes", "cost": "135"},
                {"description": "1 Sword Brother, 9 Initiates and 10 Neophytes", "cost": "290"},
            ]
        )
        self.assertEqual(parsed, {10: 135, 20: 290})

    def test_addon_model_cost_is_added_to_unit_cost(self):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        u.models_cost = {3: 80, 6: 160}
        u.models_cost_addons = {"attack bike": 55}
        u.enhancement = None

        # 3 bikes + 1 attack bike => base bucket 3 (80) + 55
        u.models = [SimpleNamespace(name="Space Marine Bike") for _ in range(3)] + [SimpleNamespace(name="Attack Bike")]
        self.assertEqual(u.get_unit_cost(), 135)

        # 6 bikes + 1 attack bike => base bucket 6 (160) + 55
        u.models = [SimpleNamespace(name="Space Marine Bike") for _ in range(6)] + [SimpleNamespace(name="Attack Bike")]
        self.assertEqual(u.get_unit_cost(), 215)

    def test_addon_cost_is_case_insensitive(self):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        u.models_cost = {5: 115}
        u.models_cost_addons = {"shadow spectre exarch": 30}
        u.enhancement = None
        u.models = [SimpleNamespace(name="Shadow Spectre") for _ in range(5)] + [SimpleNamespace(name="SHADOW SPECTRE EXARCH")]
        self.assertEqual(u.get_unit_cost(), 145)

    def test_calculate_points_ignores_non_numeric_keys(self):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        # Simulate a fallback dict that may contain non-int keys
        u.models_cost = {"spawn_on_death": 0, 3: 80}
        self.assertEqual(u.calculate_points(3), 80)
        self.assertEqual(u.calculate_points(1), 0)


if __name__ == "__main__":
    unittest.main()

