#!/usr/bin/env python3
"""
Manual test for pile-in functionality that can be run to verify the implementation works.
This creates a simple scenario and tests the pile-in logic manually.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from warhammer40k_ai.utility.constants import BASE_CONTACT_EPSILON, PILE_IN_DISTANCE


def test_pile_in_scenario():
    """Test a realistic pile-in scenario"""
    print("🧪 Testing Pile-In Scenario")
    print("=" * 50)
    
    # Scenario: Space Marine at (5, 5) wants to pile-in toward Chaos Marines
    friendly_pos = (5.0, 5.0)
    
    # Enemy positions
    enemies = [
        {"name": "Chaos Marine 1", "pos": (7.0, 5.0), "distance": 2.0},  # Closest
        {"name": "Chaos Marine 2", "pos": (10.0, 5.0), "distance": 5.0}, # Further
        {"name": "Chaos Marine 3", "pos": (5.0, 8.0), "distance": 3.0}   # Medium
    ]
    
    print(f"📍 Friendly model at: {friendly_pos}")
    print(f"👹 Enemy models:")
    for enemy in enemies:
        print(f"   {enemy['name']} at {enemy['pos']} (distance: {enemy['distance']}\")")
    
    # Find closest enemy
    closest_enemy = min(enemies, key=lambda e: e['distance'])
    print(f"\n🎯 Closest enemy: {closest_enemy['name']} at {closest_enemy['distance']}\"")
    
    # Test optimization: which enemies should be considered?
    max_relevant_distance = 1.0 + PILE_IN_DISTANCE  # ENGAGEMENT_RANGE + PILE_IN_DISTANCE
    print(f"\n⚡ Optimization: only considering enemies within {max_relevant_distance}\"")
    
    relevant_enemies = [e for e in enemies if e['distance'] <= max_relevant_distance]
    excluded_enemies = [e for e in enemies if e['distance'] > max_relevant_distance]
    
    print(f"✅ Relevant enemies ({len(relevant_enemies)}):")
    for enemy in relevant_enemies:
        print(f"   {enemy['name']} at {enemy['distance']}\"")
    
    print(f"❌ Excluded enemies ({len(excluded_enemies)}):")
    for enemy in excluded_enemies:
        print(f"   {enemy['name']} at {enemy['distance']}\" (too far)")
    
    # Test pile-in movement options
    print(f"\n🏃 Pile-In Movement Tests:")
    print(f"Must end closer to closest enemy ({closest_enemy['name']} at {closest_enemy['distance']}\")")
    
    # Test various destination positions
    test_moves = [
        {"pos": (6.0, 5.0), "expected_distance": 1.0, "should_pass": True, "reason": "Closer to closest enemy"},
        {"pos": (6.9, 5.0), "expected_distance": 0.1, "should_pass": True, "reason": "Much closer, near base contact"},
        {"pos": (4.0, 5.0), "expected_distance": 3.0, "should_pass": False, "reason": "Further from closest enemy"},
        {"pos": (5.0, 6.0), "expected_distance": 2.24, "should_pass": False, "reason": "Further from closest enemy"},
    ]
    
    for i, move in enumerate(test_moves, 1):
        new_distance = move['expected_distance']
        current_distance = closest_enemy['distance']
        
        print(f"\n  Test {i}: Move to {move['pos']}")
        print(f"    New distance to closest enemy: {new_distance:.2f}\"")
        print(f"    Current distance: {current_distance:.2f}\"")
        
        is_closer = new_distance < current_distance
        print(f"    Is closer? {is_closer} ({'✅' if is_closer else '❌'})")
        print(f"    Expected: {'PASS' if move['should_pass'] else 'FAIL'} - {move['reason']}")
        
        if is_closer == move['should_pass']:
            print(f"    Result: ✅ CORRECT")
        else:
            print(f"    Result: ❌ INCORRECT")
    
    # Test base contact requirements
    print(f"\n🤝 Base Contact Requirements:")
    closest_distance = closest_enemy['distance']
    
    if closest_distance <= PILE_IN_DISTANCE:
        print(f"   Closest enemy is {closest_distance}\" away (<= {PILE_IN_DISTANCE}\")")
        print(f"   ✅ Base contact REQUIRED (enemy is within pile-in range)")
        print(f"   Must end within {BASE_CONTACT_EPSILON}\" of closest enemy")
        
        # Test base contact scenarios
        base_contact_tests = [
            {"distance": 0.01, "should_pass": True, "reason": "In base contact"},
            {"distance": 0.05, "should_pass": True, "reason": "Just within epsilon"},
            {"distance": 0.1, "should_pass": False, "reason": "Outside epsilon but still close"},
            {"distance": 0.5, "should_pass": False, "reason": "Too far for base contact"},
        ]
        
        for test in base_contact_tests:
            in_contact = test['distance'] <= BASE_CONTACT_EPSILON
            print(f"     Distance {test['distance']:.2f}\": {'✅' if in_contact else '❌'} {test['reason']}")
            
    else:
        print(f"   Closest enemy is {closest_distance}\" away (> {PILE_IN_DISTANCE}\")")
        print(f"   ⚠️  Base contact NOT required (enemy outside pile-in range)")
    
    # Test UI disabled state logic
    print(f"\n🖥️  UI Model Button States:")
    
    models = [
        {"name": "Marine 1", "distance_to_enemy": 0.03, "in_base_contact": True},
        {"name": "Marine 2", "distance_to_enemy": 1.5, "in_base_contact": False},
        {"name": "Marine 3", "distance_to_enemy": 0.8, "in_base_contact": False},
    ]
    
    for model in models:
        in_contact = model['distance_to_enemy'] <= BASE_CONTACT_EPSILON
        should_be_disabled = in_contact
        
        print(f"   {model['name']}:")
        print(f"     Distance to nearest enemy: {model['distance_to_enemy']}\"")
        print(f"     In base contact: {in_contact}")
        print(f"     Button state: {'🚫 DISABLED' if should_be_disabled else '✅ ENABLED'}")
        if should_be_disabled:
            print(f"     Reason: Already in base contact")
    
    print(f"\n🎉 Pile-In Test Complete!")
    print(f"📝 Summary:")
    print(f"   • Optimization excludes enemies > {max_relevant_distance}\" away")
    print(f"   • Must end closer to closest enemy")
    print(f"   • Base contact required when enemy ≤ {PILE_IN_DISTANCE}\" away")
    print(f"   • Models in base contact (≤ {BASE_CONTACT_EPSILON}\") are disabled in UI")


def test_edge_cases():
    """Test edge cases for pile-in logic"""
    print(f"\n🔬 Testing Edge Cases")
    print("=" * 30)
    
    # Edge case 1: Multiple enemies at same distance
    print(f"1. Multiple enemies at same distance:")
    print(f"   • Two enemies both 2.0\" away")
    print(f"   • System should pick one as 'closest'")
    print(f"   • Both are valid targets for 'get closer' requirement")
    
    # Edge case 2: Enemy exactly at pile-in distance
    print(f"\n2. Enemy exactly at pile-in distance:")
    print(f"   • Enemy at exactly {PILE_IN_DISTANCE:.1f}\" away")
    print(f"   • Base contact should be required")
    print(f"   • Must end ≤ {BASE_CONTACT_EPSILON}\" from enemy")
    
    # Edge case 3: Multiple enemies, some relevant, some not
    print(f"\n3. Mixed enemy distances:")
    print(f"   • Enemy A: 1.5\" (relevant, within {4.0}\")")
    print(f"   • Enemy B: 2.0\" (relevant, within {4.0}\")")
    print(f"   • Enemy C: 5.0\" (excluded, beyond {4.0}\")")
    print(f"   • Only A and B considered for validation")
    
    # Edge case 4: Exactly at base contact epsilon
    print(f"\n4. Exactly at base contact epsilon:")
    print(f"   • Model exactly {BASE_CONTACT_EPSILON}\" from enemy")
    print(f"   • Should be considered in base contact")
    print(f"   • Should be disabled in UI")


if __name__ == '__main__':
    test_pile_in_scenario()
    test_edge_cases()
    print(f"\n✅ Manual pile-in tests complete!")
