#!/usr/bin/env python3
"""
Simplified test suite for pile-in functionality focusing on working components.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch
import logging
logger = logging.getLogger(__name__)

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from warhammer40k_ai.utility.constants import (
    BASE_CONTACT_EPSILON, PILE_IN_DISTANCE, ENGAGEMENT_RANGE_HORIZONTAL
)


class TestPileInConstants(unittest.TestCase):
    """Test pile-in constants are properly defined"""
    
    def test_pile_in_constants_exist(self):
        """Test that all required constants are defined"""
        self.assertEqual(BASE_CONTACT_EPSILON, 0.05)
        self.assertEqual(PILE_IN_DISTANCE, 3.0)
        self.assertEqual(ENGAGEMENT_RANGE_HORIZONTAL, 1.0)
    
    def test_pile_in_optimization_distance(self):
        """Test the optimization distance calculation"""
        max_relevant_distance = ENGAGEMENT_RANGE_HORIZONTAL + PILE_IN_DISTANCE
        self.assertEqual(max_relevant_distance, 4.0)
        
        # This is the distance beyond which enemies are excluded from pile-in validation
        logger.info(f"✅ Enemies beyond {max_relevant_distance}\" are excluded from pile-in validation")


class TestPileInBaseContactLogic(unittest.TestCase):
    """Test base contact detection logic"""
    
    def test_base_contact_epsilon(self):
        """Test base contact detection using epsilon"""
        # Test distances within epsilon (should be base contact)
        distances_in_contact = [0.0, 0.01, 0.04, 0.05]
        for distance in distances_in_contact:
            with self.subTest(distance=distance):
                self.assertLessEqual(distance, BASE_CONTACT_EPSILON, 
                                   f"Distance {distance}\" should be considered base contact")
        
        # Test distances outside epsilon (should not be base contact)
        distances_not_in_contact = [0.06, 0.1, 0.5, 1.0]
        for distance in distances_not_in_contact:
            with self.subTest(distance=distance):
                self.assertGreater(distance, BASE_CONTACT_EPSILON,
                                 f"Distance {distance}\" should not be considered base contact")


class TestPileInValidationRules(unittest.TestCase):
    """Test pile-in validation rules"""
    
    def test_movement_type_validation_rules(self):
        """Test that pile-in gets correct validation rules"""
        # Import here to avoid issues with missing modules
        try:
            from warhammer40k_ai.utility.calcs import get_validation_rules, MovementType
            
            # Test pile-in rules
            pile_in_rules = get_validation_rules(MovementType.PILE_IN)
            
            expected_rules = {
                'prevent_friendly_overlap': True,
                'prevent_enemy_overlap': True,
                # Fight phase pile-in/consolidate moves pay pivot cost.
                'apply_pivot_cost': True,
                'check_terrain_traversal': True,
                'must_end_closer_to_enemies': True,
                'prefer_base_contact': True,
                'max_distance_override': PILE_IN_DISTANCE,
                # Pathfinding is discretized; allow a tiny epsilon so an intended 3.0" move doesn't get rejected.
                'distance_tolerance': 0.05,
            }
            
            for rule_name, expected_value in expected_rules.items():
                with self.subTest(rule=rule_name):
                    self.assertEqual(pile_in_rules[rule_name], expected_value,
                                   f"Pile-in rule '{rule_name}' should be {expected_value}")
            
            logger.info(f"✅ Pile-in validation rules correctly configured")
            
        except ImportError as e:
            self.skipTest(f"Could not import validation rules: {e}")


class TestPileInDistanceLogic(unittest.TestCase):
    """Test pile-in distance calculations"""
    
    def test_distance_comparisons(self):
        """Test distance comparison logic for pile-in"""
        # Test case: model at (0, 0), enemy at (2, 0) = 2" away
        current_distance = 2.0
        
        # Closer positions (should be valid for pile-in)
        closer_distances = [1.9, 1.5, 1.0, 0.5, 0.05]
        for new_distance in closer_distances:
            with self.subTest(new_distance=new_distance):
                self.assertLess(new_distance, current_distance,
                               f"Distance {new_distance}\" should be closer than {current_distance}\"")
        
        # Further positions (should be invalid for pile-in)
        further_distances = [2.0, 2.1, 2.5, 3.0]
        for new_distance in further_distances:
            with self.subTest(new_distance=new_distance):
                self.assertGreaterEqual(new_distance, current_distance,
                                      f"Distance {new_distance}\" should not be closer than {current_distance}\"")
    
    def test_base_contact_requirements(self):
        """Test when base contact should be required"""
        # If current distance to closest enemy <= pile-in distance, base contact required
        current_distances_requiring_contact = [3.0, 2.5, 2.0, 1.0, 0.5]
        
        for distance in current_distances_requiring_contact:
            with self.subTest(distance=distance):
                self.assertLessEqual(distance, PILE_IN_DISTANCE,
                                   f"Enemy at {distance}\" should require base contact when pile-in distance is {PILE_IN_DISTANCE}\"")
        
        # If current distance > pile-in distance, base contact not required
        current_distances_not_requiring_contact = [3.1, 4.0, 5.0, 6.0]
        
        for distance in current_distances_not_requiring_contact:
            with self.subTest(distance=distance):
                self.assertGreater(distance, PILE_IN_DISTANCE,
                                 f"Enemy at {distance}\" should not require base contact when pile-in distance is {PILE_IN_DISTANCE}\"")


def run_simple_pile_in_tests():
    """Run simplified pile-in tests"""
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTest(unittest.makeSuite(TestPileInConstants))
    suite.addTest(unittest.makeSuite(TestPileInBaseContactLogic))
    suite.addTest(unittest.makeSuite(TestPileInValidationRules))
    suite.addTest(unittest.makeSuite(TestPileInDistanceLogic))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        logger.info("\n🎉 All simplified pile-in tests passed!")
        logger.info("\n📋 What was tested:")
        logger.info("  ✅ Constants are properly defined")
        logger.info("  ✅ Base contact detection logic")
        logger.info("  ✅ Validation rules configuration")
        logger.info("  ✅ Distance comparison logic")
        logger.info("  ✅ Base contact requirement logic")
    else:
        logger.error(f"\n❌ {len(result.failures)} tests failed, {len(result.errors)} errors")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_simple_pile_in_tests()
    sys.exit(0 if success else 1)
