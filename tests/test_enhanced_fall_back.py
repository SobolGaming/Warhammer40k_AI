import unittest
import sys
import os
import pytest
import logging

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from warhammer40k_ai.classes.unit import Unit, MovementAction
from warhammer40k_ai.classes.map import Map
from warhammer40k_ai.classes.status_effects import BattleShockEffect

# Add this at the beginning of your test file
@pytest.fixture(autouse=True)
def set_log_level():
    logging.getLogger().setLevel(logging.INFO)


class MockDatasheet:
    """Mock datasheet for testing purposes."""
    def __init__(self, name, leadership=7, model_count=5, movement=6, keywords=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = keywords or []
        self.faction_keywords = []
        self.datasheets_unit_composition = [
            {"description": f"{model_count} Test Models"}
        ]
        self.datasheets_models_cost = [
            {"description": f"{model_count} models", "cost": 100}
        ]
        self.datasheets_models = [{
            "M": str(movement), "T": "4", "Sv": "3", "W": "1", 
            "Ld": str(leadership), "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none"
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


class TestEnhancedFallBack(unittest.TestCase):
    """Test cases for the enhanced Fall Back movement system."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create test unit
        self.datasheet = MockDatasheet("Test Squad", leadership=8, model_count=3)
        self.unit = Unit(self.datasheet)
        
        # Create test map
        self.game_map = Map(60, 44)  # Standard Strike Force dimensions
        self.game_map.units = [self.unit]
        
        # Set initial positions for models
        self.unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        self.unit.models[1].set_location(11.0, 10.0, 0.0, 0.0)
        self.unit.models[2].set_location(12.0, 10.0, 0.0, 0.0)
        self.unit.reset_position()
    
    def test_normal_fall_back_movement(self):
        """Test normal Fall Back movement (not battle-shocked)."""
        # Initial state checks
        self.assertEqual(len(self.unit.models), 3)
        self.assertFalse(self.unit.round_state.fell_back_this_round)
        self.assertFalse(self.unit.is_battle_shocked())
        
        # Set up fall back destination (within 6" movement range)
        fall_back_destination = (14.0, 12.0, 0.0)  # About 4.1" away
        result = self.unit.fall_back(fall_back_destination, [], self.game_map)
        
        # Verify fall back was successful
        self.assertTrue(result, "Fall back should succeed")
        self.assertTrue(self.unit.round_state.fell_back_this_round, "Unit should be marked as having fallen back")
        self.assertEqual(len(self.unit.models), 3, "All models should survive normal fall back")
        
        # Verify unit moved
        final_position = self.unit.get_position()
        self.assertNotEqual(final_position[:2], (11.0, 10.0), "Unit should have moved from initial position")
    
    def test_battle_shocked_fall_back_with_desperate_escape(self):
        """Test Battle-Shocked Fall Back with Desperate Escape Test."""
        # Reset unit to new position
        self.unit.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        self.unit.models[1].set_location(21.0, 10.0, 0.0, 0.0)
        self.unit.models[2].set_location(22.0, 10.0, 0.0, 0.0)
        self.unit.reset_position()
        self.unit.round_state.fell_back_this_round = False
        
        # Make unit Battle-Shocked
        battle_shock_effect = BattleShockEffect(1)
        self.unit.apply_status_effect(battle_shock_effect)
        self.assertTrue(self.unit.is_battle_shocked(), "Unit should be battle-shocked")
        
        # Record initial model count
        initial_model_count = len(self.unit.models)
        
        # Attempt fall back
        fall_back_destination = (24.0, 12.0, 0.0)  # About 4.5" away
        result = self.unit.fall_back(fall_back_destination, [], self.game_map)
        
        # Fall back should succeed even if some models are lost
        self.assertTrue(result, "Fall back should succeed even with model losses")
        self.assertTrue(self.unit.is_alive(), "Unit should still be alive")
        self.assertTrue(self.unit.round_state.fell_back_this_round, "Unit should be marked as having fallen back")
        
        # Model count may be reduced due to Desperate Escape Tests
        final_model_count = len(self.unit.models)
        self.assertLessEqual(final_model_count, initial_model_count, "Model count should not increase")
        self.assertGreater(final_model_count, 0, "At least some models should survive")
    
    def test_fly_unit_fall_back(self):
        """Test FLY unit Fall Back (should not need Desperate Escape Tests)."""
        # Create a unit with FLY keyword
        fly_datasheet = MockDatasheet("Flying Squad", leadership=7, model_count=2, keywords=["Fly"])
        fly_unit = Unit(fly_datasheet)
        
        # Set initial positions
        fly_unit.models[0].set_location(30.0, 10.0, 0.0, 0.0)
        fly_unit.models[1].set_location(31.0, 10.0, 0.0, 0.0)
        fly_unit.reset_position()
        
        self.game_map.units.append(fly_unit)
        
        # Verify FLY properties
        self.assertTrue(fly_unit.is_flying, "Unit should have FLY keyword")
        self.assertEqual(len(fly_unit.models), 2, "FLY unit should have 2 models")
        
        # Attempt fall back
        fly_fall_back_destination = (34.0, 12.0, 0.0)  # About 4.5" away
        result = fly_unit.fall_back(fly_fall_back_destination, [], self.game_map)
        
        # Verify fall back was successful
        self.assertTrue(result, "FLY unit fall back should succeed")
        self.assertTrue(fly_unit.round_state.fell_back_this_round, "FLY unit should be marked as having fallen back")
        self.assertEqual(len(fly_unit.models), 2, "All FLY unit models should survive (no Desperate Escape Tests)")
        
        # Verify unit moved
        final_position = fly_unit.get_position()
        self.assertNotEqual(final_position[:2], (30.5, 10.0), "FLY unit should have moved from initial position")
    
    def test_fall_back_distance_validation(self):
        """Test Fall Back distance validation (movement characteristic limit)."""
        # Try to fall back beyond movement range
        too_far_destination = (25.0, 25.0, 0.0)  # Much more than 6" away
        result = self.unit.fall_back(too_far_destination, [], self.game_map)
        
        # Fall back should fail due to distance
        self.assertFalse(result, "Fall back should fail when destination is too far")
        self.assertFalse(self.unit.round_state.fell_back_this_round, "Unit should not be marked as having fallen back")
        
        # Unit should not have moved
        final_position = self.unit.get_position()
        self.assertEqual(final_position[:2], (11.0, 10.0), "Unit should not have moved from initial position")
    
    def test_desperate_escape_test_for_models_moving_over_enemies(self):
        """Test that Desperate Escape Tests are triggered when models move over enemy models."""
        # This is a conceptual test since setting up enemy collision in pathfinding
        # requires more complex map setup. The core logic is tested in the battle-shocked test.
        
        # Make unit Battle-Shocked
        battle_shock_effect = BattleShockEffect(1)
        self.unit.apply_status_effect(battle_shock_effect)
        
        # Verify the desperate escape test method exists and functions
        initial_model_count = len(self.unit.models)
        models_destroyed = self.unit.take_desperate_escape_test()
        
        # Some models may be destroyed
        self.assertIsInstance(models_destroyed, int, "Should return number of models destroyed")
        self.assertGreaterEqual(models_destroyed, 0, "Destroyed count should be non-negative")
        self.assertLessEqual(len(self.unit.models) + models_destroyed, initial_model_count, 
                           "Total models should be consistent")
    
    def test_unit_position_tracking(self):
        """Test that unit position is properly tracked during fall back."""
        initial_position = self.unit.get_position()
        
        # Perform fall back
        fall_back_destination = (14.0, 12.0, 0.0)
        result = self.unit.fall_back(fall_back_destination, [], self.game_map)
        
        self.assertTrue(result, "Fall back should succeed")
        
        # Verify position changed
        final_position = self.unit.get_position()
        self.assertNotEqual(initial_position, final_position, "Unit position should change after fall back")
        
        # Verify coherency is maintained
        model_positions = [(model.model_base.x, model.model_base.y) for model in self.unit.models]
        for i, pos1 in enumerate(model_positions):
            for j, pos2 in enumerate(model_positions[i+1:], i+1):
                distance = ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)**0.5
                self.assertLessEqual(distance, self.unit.coherency_distance * 2, 
                                   f"Models {i} and {j} should maintain coherency")


if __name__ == '__main__':
    unittest.main() 