import unittest
from src.warhammer40k_ai.waha_helper import WahaHelper
from src.warhammer40k_ai.classes.unit import Unit
from src.warhammer40k_ai.utility.model_base import convert_mm_to_inches
import pytest
import logging

# Add this at the beginning of your test file
@pytest.fixture(autouse=True)
def set_log_level():
    logging.getLogger().setLevel(logging.INFO)
    # You can change INFO to DEBUG, WARNING, ERROR, or CRITICAL

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
            self.assertEqual(model.name, "Bloodletter")

        # Check common attributes for all models
        for model in bloodletters_unit.models:
            self.assertEqual(model.movement, 6)
            self.assertEqual(model.toughness, 4)
            self.assertEqual(model.save, 7)
            self.assertEqual(model.wounds, 1)
            self.assertEqual(model.leadership, 7)
            self.assertEqual(model.objective_control, 2)
            self.assertEqual(model.model_base.getRadius(), convert_mm_to_inches(32 / 2))

        # Check weapons
        
        self.assertGreater(len(bloodletters_unit.default_wargear), 0)
        hellblade = next((wargear for wargear in bloodletters_unit.default_wargear if wargear.name == "Hellblade"), None)
        self.assertIsNotNone(hellblade)
        self.assertEqual(hellblade.range.min, 0)
        self.assertEqual(hellblade.range.max, 0)
        self.assertEqual(hellblade.attacks.resolve(), 2)
        self.assertEqual(hellblade.skill, 3)
        self.assertEqual(hellblade.strength, 5)
        self.assertEqual(hellblade.ap, -2)
        self.assertEqual(hellblade.damage, 2)

        # Test wargear options
        bloodletters_unit.apply_wargear_options(bloodletters_unit.wargear_options)

        # Check if wargear options were applied correctly
        models_with_instrument = [model for model in bloodletters_unit.models if "instrument of Chaos" in model.optional_wargear]
        models_with_icon = [model for model in bloodletters_unit.models if "daemonic icon" in model.optional_wargear]

        self.assertEqual(len(models_with_instrument), 1, "Expected 1 model with instrument of Chaos")
        self.assertEqual(len(models_with_icon), 1, "Expected 1 model with daemonic icon")
        self.assertNotEqual(models_with_instrument[0], models_with_icon[0], "Instrument and icon should be on different models")

        bloodletters_unit.print_unit()

        # New test for wounding and killing a model
        self.assertEqual(len(bloodletters_unit.models), 10, "Unit should start with 10 models")

        # Wound a model
        bloodletters_unit.models[0].take_damage(1)
        self.assertEqual(len(bloodletters_unit.models), 9, "Unit should have 9 models after one is killed")

        # Check that the Bloodreaper (first model) was removed
        self.assertNotEqual(bloodletters_unit.models[0].name, "Bloodreaper", "Bloodreaper should have been removed")

        # Wound another model, but not enough to kill it
        bloodletters_unit.models[0].take_damage(0)
        self.assertEqual(len(bloodletters_unit.models), 9, "Unit should still have 9 models")
        self.assertEqual(bloodletters_unit.models[0].wounds, 1, "Model should still have 1 wound")

if __name__ == '__main__':
    unittest.main()