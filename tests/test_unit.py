import unittest
from warhammer40k_ai.waha_helper import WahaHelper
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import convert_mm_to_inches
import pytest
import logging

# Add this at the beginning of your test file
@pytest.fixture(autouse=True)
def set_log_level():
    logging.getLogger().setLevel(logging.INFO)
    # You can change INFO to DEBUG, WARNING, ERROR, or CRITICAL

pytestmark = pytest.mark.slow


class TestWahaHelper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.waha_helper = WahaHelper()

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
        self.assertEqual(len(bloodletters_unit.unit_composition), 2)
        self.assertEqual(bloodletters_unit.unit_composition["Bloodreaper"][1], 1)
        self.assertEqual(bloodletters_unit.unit_composition["Bloodletters"][1], 9)

        # Check models
        self.assertEqual(len(bloodletters_unit.models), 10)

        # Check the first model (Bloodreaper)
        self.assertEqual(bloodletters_unit.models[0].name, "Bloodreaper")
        for model in bloodletters_unit.models[1:]:
            self.assertEqual(model.name, "Bloodletter")

        # Check common attributes for all models
        for model in bloodletters_unit.models:
            self.assertEqual(model.movement, 8)
            self.assertEqual(model.toughness, 4)
            self.assertEqual(model.save, 7)
            self.assertEqual(model.wounds, 1)
            self.assertEqual(model.leadership, 7)
            self.assertEqual(model.objective_control, 2)
            self.assertEqual(model.model_base.get_radius(), convert_mm_to_inches(32 / 2))

        # Check weapons
        bloodletters_unit.add_wargear()
        self.assertGreater(len(bloodletters_unit.possible_wargear), 0)
        hellblade = next((wargear for wargear in bloodletters_unit.possible_wargear if wargear.name == "Hellblade"), None)
        self.assertIsNotNone(hellblade)
        self.assertEqual(hellblade.get_range().min, 0)
        self.assertEqual(hellblade.get_range().max, 0)
        self.assertEqual(hellblade.get_attacks().resolve(), 2)
        self.assertEqual(hellblade.get_skill(), 3)
        self.assertEqual(hellblade.get_strength(), 5)
        self.assertEqual(hellblade.get_ap(), -2)
        self.assertEqual(hellblade.get_damage(), 2)

        # Test wargear options
        bloodletters_unit.apply_wargear_options()

        # Check if wargear options were applied correctly
        models_with_instrument = [model for model in bloodletters_unit.models if "instrument of chaos" in model.optional_wargear]
        models_with_icon = [model for model in bloodletters_unit.models if "daemonic icon" in model.optional_wargear]

        self.assertEqual(len(models_with_instrument), 1, "Expected 1 model with instrument of chaos")
        self.assertEqual(len(models_with_icon), 1, "Expected 1 model with daemonic icon")
        self.assertNotEqual(models_with_instrument[0], models_with_icon[0], "Instrument and icon should be on different models")

        bloodletters_unit.print_unit()

        # New test for wounding and killing a model
        self.assertEqual(len(bloodletters_unit.models), 10, "Unit should start with 10 models")

        # Wound a model
        bloodletters_unit.models[0].take_damage(1, False, None)
        self.assertEqual(len(bloodletters_unit.models), 9, "Unit should have 9 models after one is killed")

        # Check that the Bloodreaper (first model) was removed
        self.assertNotEqual(bloodletters_unit.models[0].name, "Bloodreaper", "Bloodreaper should have been removed")

        # Wound another model, but not enough to kill it
        bloodletters_unit.models[0].take_damage(0, False, None)
        self.assertEqual(len(bloodletters_unit.models), 9, "Unit should still have 9 models")
        self.assertEqual(bloodletters_unit.models[0].wounds, 1, "Model should still have 1 wound")

    def test_servitor_battleclade_base_sizes(self):
        datasheet_name = "Servitor Battleclade"
        datasheet = self.waha_helper.get_full_datasheet_info_by_name(datasheet_name)
        self.assertIsNotNone(datasheet, f"Datasheet for {datasheet_name} not found")

        unit = Unit(datasheet)

        underseer = [m for m in unit.models if m.name == "Servitor Underseer"]
        gun_servitors = [m for m in unit.models if m.name == "Gun Servitor"]
        combat_servitors = [m for m in unit.models if m.name == "Combat Servitor"]

        self.assertEqual(len(underseer), 1)
        self.assertEqual(len(gun_servitors), 2)
        self.assertEqual(len(combat_servitors), 6)

        expected_32 = convert_mm_to_inches(32 / 2)
        expected_25 = convert_mm_to_inches(25 / 2)

        self.assertEqual(underseer[0].model_base.get_radius(), expected_32)
        for model in gun_servitors:
            self.assertEqual(model.model_base.get_radius(), expected_32)
        for model in combat_servitors:
            self.assertEqual(model.model_base.get_radius(), expected_25)

        datasheet_name = "Jakhals"
        datasheet = self.waha_helper.get_full_datasheet_info_by_name(datasheet_name)
        self.assertIsNotNone(datasheet, f"Datasheet for {datasheet_name} not found")

        unit = Unit(datasheet)

        pack_leader = [m for m in unit.models if m.name == "Jakhal Pack Leader"]
        dishonoured = [m for m in unit.models if m.name == "Dishonoured"]
        jakhals = [m for m in unit.models if m.name == "Jakhal"]

        self.assertEqual(len(pack_leader), 1)
        self.assertEqual(len(dishonoured), 1)
        self.assertEqual(len(jakhals), 8)

        expected_jakhal = convert_mm_to_inches(28.5 / 2)
        expected_dishonoured = convert_mm_to_inches(40 / 2)

        self.assertEqual(pack_leader[0].model_base.get_radius(), expected_jakhal)
        self.assertEqual(dishonoured[0].model_base.get_radius(), expected_dishonoured)
        for model in jakhals:
            self.assertEqual(model.model_base.get_radius(), expected_jakhal)

if __name__ == '__main__':
    unittest.main()
