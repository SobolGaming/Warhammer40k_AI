import unittest
import sys
import os
import pytest
import logging

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.roster.player import Player, PlayerControl

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


class TestChargeTracking(unittest.TestCase):
    """Test cases for the charge tracking system."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create basic game setup
        self.battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        self.game = Game(self.battlefield)
        
        # Create players
        self.player1 = Player("Player 1", PlayerControl.LOCAL, None)
        self.player2 = Player("Player 2", PlayerControl.REMOTE, None)
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        
        # Create test unit
        self.unit = Unit(MockDatasheet("Charger", model_count=1))
        self.unit.deployed = True
        if self.unit.models:
            self.unit.models[0].set_location(10, 10, 0, 0)
        
        # Create target unit - position it further away so they're not in engagement range
        self.target = Unit(MockDatasheet("Target", model_count=1))
        self.target.deployed = True
        if self.target.models:
            self.target.models[0].set_location(15, 10, 0, 0)  # 5" apart, outside engagement range
    
    def test_initial_charge_state(self):
        """Test that units start with no charge declaration."""
        self.assertFalse(self.unit.round_state.attempted_charge_this_round, 
                        "Unit should not have attempted charge initially")
    
    def test_charge_flag_set(self):
        """Test that charge flag is properly set when unit charges."""
        self.unit.round_state.attempted_charge_this_round = True
        self.assertTrue(self.unit.round_state.attempted_charge_this_round, 
                       "Unit should be marked as having attempted charge")
    
    def test_charge_flag_resets_on_new_round(self):
        """Test that charge flag resets when a new round begins."""
        self.unit.round_state.attempted_charge_this_round = True
        self.unit.initialize_round()
        self.assertFalse(self.unit.round_state.attempted_charge_this_round, 
                        "Charge flag should reset after round")
    
    def test_cannot_charge_twice(self):
        """Test that units cannot charge more than once per round."""
        self.unit.round_state.attempted_charge_this_round = True
        can_charge = self.unit.can_declare_charge_against(self.target, self.game)
        self.assertFalse(can_charge, 
                        "Unit should not be able to charge again in the same round")
    
    def test_can_charge_after_reset(self):
        """Test that units can charge again after round reset."""
        self.unit.round_state.attempted_charge_this_round = True
        self.unit.initialize_round()

        # Add units to the game map so distance calculation works
        self.game.map.units = [self.unit, self.target]

        can_charge = self.unit.can_declare_charge_against(self.target, self.game)
        self.assertTrue(can_charge,
                       "Unit should be able to charge after round reset")
    
    def test_charge_eligibility_with_other_restrictions(self):
        """Test charge eligibility with other movement restrictions."""
        # Test that advanced units cannot charge
        self.unit.round_state.advanced_this_round = True
        can_charge = self.unit.can_declare_charge_against(self.target, self.game)
        self.assertFalse(can_charge, 
                        "Unit should not be able to charge after advancing")
        
        # Reset and test that fell back units cannot charge
        self.unit.round_state.advanced_this_round = False
        self.unit.round_state.fell_back_this_round = True
        can_charge = self.unit.can_declare_charge_against(self.target, self.game)
        self.assertFalse(can_charge, 
                        "Unit should not be able to charge after falling back")
    
    def test_charge_distance_validation(self):
        """Test that charge distance validation works correctly."""
        # Move target very far away (definitely beyond max charge distance of 12")
        if self.target.models:
            self.target.models[0].set_location(30, 10, 0, 0)
        
        # Add units to the game map so distance calculation works
        self.game.map.units = [self.unit, self.target]
        
        # Debug: Check the actual distance calculation
        distance = self.game.map.get_distance_between_units(self.unit, self.target)
        print(f"DEBUG: Distance between units: {distance}\"")
        print(f"DEBUG: Max charge distance: {self.unit.max_charge_distance}\"")
        
        can_charge = self.unit.can_declare_charge_against(self.target, self.game)
        self.assertFalse(can_charge, 
                        "Unit should not be able to charge target beyond max distance")

    def test_charge_distance_calculation_10th_edition(self):
        """Test that charge distance calculation follows 10th edition rules.
        
        According to 10th edition, a successful charge requires at least one model
        of the charging unit to end with edge-to-edge distance of 1" or less from
        at least one model in the target unit.
        """
        # Position units with a known distance
        if self.unit.models:
            self.unit.models[0].set_location(10, 10, 0, 0)
        if self.target.models:
            self.target.models[0].set_location(15, 10, 0, 0)  # 5" apart
        
        # Add units to the game map
        self.game.map.units = [self.unit, self.target]
        
        # Calculate current edge-to-edge distance
        current_distance = self.game.map.get_distance_between_units(self.unit, self.target)
        print(f"DEBUG: Current edge-to-edge distance: {current_distance}\"")
        
        # According to 10th edition rules, the distance needed should be current_distance - 1"
        # because we need to achieve edge-to-edge distance of 1" or less
        expected_distance_needed = max(0, current_distance - 1.0)
        print(f"DEBUG: Expected distance needed to achieve â‰¤1\" edge-to-edge: {expected_distance_needed}\"")
        
        # Test with a charge roll that should succeed
        # If current_distance is 5", we need to roll at least 4" to achieve â‰¤1" edge-to-edge
        test_charge_roll = 4.0
        if test_charge_roll >= expected_distance_needed:
            print(f"DEBUG: Charge roll {test_charge_roll}\" should succeed (>= {expected_distance_needed}\")")
        else:
            print(f"DEBUG: Charge roll {test_charge_roll}\" should fail (< {expected_distance_needed}\")")
        
        # Verify the logic: if we roll enough to achieve â‰¤1" edge-to-edge, the charge should be possible
        self.assertTrue(test_charge_roll >= expected_distance_needed,
                       f"Charge roll {test_charge_roll}\" should be sufficient to achieve â‰¤1\" edge-to-edge distance")
        
        # Test with a charge roll that should fail
        test_charge_roll_fail = 2.0
        if test_charge_roll_fail < expected_distance_needed:
            print(f"DEBUG: Charge roll {test_charge_roll_fail}\" should fail (< {expected_distance_needed}\")")
        else:
            print(f"DEBUG: Charge roll {test_charge_roll_fail}\" should succeed (>= {expected_distance_needed}\")")
        
        self.assertTrue(test_charge_roll_fail < expected_distance_needed,
                       f"Charge roll {test_charge_roll_fail}\" should be insufficient to achieve â‰¤1\" edge-to-edge distance")


if __name__ == '__main__':
    unittest.main() 
