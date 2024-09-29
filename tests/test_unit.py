import unittest
from src.warhammer40k_ai.waha_helper import WahaHelper
from src.warhammer40k_ai.classes.unit import Unit
from src.warhammer40k_ai.utility.model_base import ConvertMMToInches

class TestWahaHelper(unittest.TestCase):
    def setUp(self):
        self.waha_helper = WahaHelper()

    def test_create_bloodletters_unit(self):
        datasheet_name = "Bloodletters"
        datasheet = self.waha_helper.get_full_datasheet_info_by_name(datasheet_name)
        self.assertIsNotNone(datasheet, f"Datasheet for {datasheet_name} not found")

        bloodletters_unit = Unit(datasheet)

        self.assertEqual(bloodletters_unit.name, "Bloodletters")
        self.assertEqual(bloodletters_unit.faction, "Chaos Daemons")
        self.assertIn("Khorne", bloodletters_unit.keywords)
        self.assertIn("Legiones Daemonica", bloodletters_unit.faction_keywords)

        # Check unit composition
        self.assertEqual(len(bloodletters_unit.composition), 2)
        self.assertEqual(bloodletters_unit.composition[0], (1, "Bloodreaper"))
        self.assertEqual(bloodletters_unit.composition[1], (9, "Bloodletters"))

        # Check models
        self.assertEqual(len(bloodletters_unit.models), 10)

        # Check the first model (Bloodreaper)
        self.assertEqual(bloodletters_unit.models[0].name, "Bloodreaper")
        for model in bloodletters_unit.models[1:]:
            self.assertEqual(model.name, "Bloodletters")

        # Check common attributes for all models
        for model in bloodletters_unit.models:
            self.assertEqual(model.movement, 6)
            self.assertEqual(model.toughness, 4)
            self.assertEqual(model.save, 7)
            self.assertEqual(model.wounds, 1)
            self.assertEqual(model.leadership, 7)
            self.assertEqual(model.objective_control, 2)
            self.assertEqual(model.base_size.getRadius(), ConvertMMToInches(32 / 2))

        # Check weapons
        
        self.assertGreater(len(bloodletters_unit.unit_wargear), 0)
        hellblade = next((wargear for wargear in bloodletters_unit.unit_wargear if wargear.name == "Hellblade"), None)
        self.assertIsNotNone(hellblade)
        self.assertEqual(hellblade.range.min, 0)
        self.assertEqual(hellblade.range.max, 0)
        self.assertEqual(hellblade.attacks.resolve(), 2)
        self.assertEqual(hellblade.skill, 3)
        self.assertEqual(hellblade.strength, 5)
        self.assertEqual(hellblade.ap, -2)
        self.assertEqual(hellblade.damage, 2)


if __name__ == '__main__':
    unittest.main()