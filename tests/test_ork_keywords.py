"""
Tests for Ork-specific wargear keywords:
- Bubblechukka
- Dead Choppy
- Harpooned
- Hooked
- Impaled
- Snagged
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from warhammer40k_ai.units.wargear import WargearProfile, Wargear


class TestOrkKeywords(unittest.TestCase):
    """Test suite for Ork wargear keywords"""

    def _make_profile(self, keywords_str: str, weapon_type: str = "Ranged") -> WargearProfile:
        """Helper to create a WargearProfile with specified keywords"""
        parent_wargear = SimpleNamespace(
            name="Test Weapon",
            is_melee=lambda: weapon_type.lower() == "melee",
            is_ranged=lambda: weapon_type.lower() == "ranged"
        )

        profile_data = {
            'name': 'Test Profile',
            'type': weapon_type,
            'range': '12' if weapon_type.lower() == "ranged" else 'Melee',
            'A': '2',
            'BS_WS': '3+',
            'S': '5',
            'AP': '-1',
            'D': '1',
            'description': keywords_str
        }

        profile = WargearProfile('default', profile_data, parent_wargear)
        return profile

    def _make_attacker(self, wargear_list=None):
        """Helper to create a mock attacker model"""
        class _Unit:
            special_rules = {}
            def get_parent_army(self):
                return None
            def get_attached_unit_root(self):
                return self
        
        unit = _Unit()
        attacker = SimpleNamespace(
            name="Attacker",
            parent_unit=unit,
            wargear=wargear_list or []
        )
        return attacker

    def _make_target(self, has_monster=False, has_vehicle=False):
        """Helper to create a mock target unit"""
        def _has_keyword(kw: str) -> bool:
            kw_lower = kw.lower()
            if kw_lower == "monster":
                return has_monster
            if kw_lower == "vehicle":
                return has_vehicle
            return False

        target = SimpleNamespace(
            name="Target Unit",
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=_has_keyword
        )
        return target

    ###########################################################################
    # Keyword Detection Tests
    ###########################################################################

    def test_bubblechukka_detection(self):
        """Test that Bubblechukka keyword is properly detected"""
        profile = self._make_profile("bubblechukka, blast")
        self.assertTrue(profile.is_bubblechukka())

    def test_bubblechukka_profile_selection_method_exists(self):
        """Test that Bubblechukka profile selection method exists"""
        profile = self._make_profile("bubblechukka, blast")

        # Verify the method exists and can be called
        self.assertTrue(hasattr(profile, 'get_bubblechukka_profile_for_roll'))
        self.assertTrue(callable(profile.get_bubblechukka_profile_for_roll))

    def test_bubblechukka_profile_selection_invalid_roll(self):
        """Test Bubblechukka profile selection with invalid rolls"""
        profile = self._make_profile("bubblechukka, blast")

        # Test invalid rolls
        self.assertIsNone(profile.get_bubblechukka_profile_for_roll(0))
        self.assertIsNone(profile.get_bubblechukka_profile_for_roll(7))
        self.assertIsNone(profile.get_bubblechukka_profile_for_roll(-1))

    def test_bubblechukka_non_bubblechukka_weapon(self):
        """Test that non-Bubblechukka weapons return None"""
        profile = self._make_profile("blast, rapid fire 2")

        # Should return None for non-Bubblechukka weapons
        self.assertIsNone(profile.get_bubblechukka_profile_for_roll(3))

    def test_bubblechukka_full_weapon_with_profiles(self):
        """Test Bubblechukka weapon with all three profiles"""
        from warhammer40k_ai.units.wargear import Wargear

        # Create the Bubblechukka weapon with the "big bubble" profile
        # The Wargear class automatically extracts the profile name from the weapon name
        bubblechukka = Wargear({
            'name': 'Bubblechukka – big bubble',
            'type': 'Ranged',
            'range': '48',
            'A': '2D6',
            'BS_WS': '4+',
            'S': '6',
            'AP': '-1',
            'D': '1',
            'description': 'bubblechukka, blast'
        })

        # Add the other two profiles
        bubblechukka.add_profile('wobbly bubble', {
            'range': '48',
            'A': 'D6',
            'BS_WS': '4+',
            'S': '9',
            'AP': '-2',
            'D': '3',
            'description': 'bubblechukka, blast'
        })

        bubblechukka.add_profile('dense bubble', {
            'range': '48',
            'A': 'D3',
            'BS_WS': '4+',
            'S': '12',
            'AP': '-3',
            'D': 'D6+3',
            'description': 'bubblechukka, blast'
        })

        # Test that the weapon is detected as Bubblechukka
        self.assertTrue(bubblechukka.is_bubblechukka())

        # Test profile selection for each roll range
        big_bubble = bubblechukka.profiles['big bubble']

        # Rolls 1-2 should select big bubble
        self.assertEqual(big_bubble.get_bubblechukka_profile_for_roll(1).name, 'big bubble')
        self.assertEqual(big_bubble.get_bubblechukka_profile_for_roll(2).name, 'big bubble')

        # Rolls 3-4 should select wobbly bubble
        self.assertEqual(big_bubble.get_bubblechukka_profile_for_roll(3).name, 'wobbly bubble')
        self.assertEqual(big_bubble.get_bubblechukka_profile_for_roll(4).name, 'wobbly bubble')

        # Rolls 5-6 should select dense bubble
        self.assertEqual(big_bubble.get_bubblechukka_profile_for_roll(5).name, 'dense bubble')
        self.assertEqual(big_bubble.get_bubblechukka_profile_for_roll(6).name, 'dense bubble')
    
    def test_dead_choppy_detection(self):
        """Test that Dead Choppy keyword is properly detected"""
        profile = self._make_profile("dead choppy", weapon_type="Melee")
        self.assertTrue(profile.is_dead_choppy())
    
    def test_harpooned_detection(self):
        """Test that Harpooned keyword is properly detected"""
        profile = self._make_profile("harpooned")
        self.assertTrue(profile.is_harpooned())
    
    def test_hooked_detection(self):
        """Test that Hooked keyword is properly detected"""
        profile = self._make_profile("hooked")
        self.assertTrue(profile.is_hooked())
    
    def test_impaled_detection(self):
        """Test that Impaled keyword is properly detected"""
        profile = self._make_profile("anti-monster 2+, anti-vehicle 2+, impaled")
        self.assertTrue(profile.is_impaled())
    
    def test_snagged_detection(self):
        """Test that Snagged keyword is properly detected"""
        profile = self._make_profile("anti-monster 2+, anti-vehicle 2+, snagged")
        self.assertTrue(profile.is_snagged())

    ###########################################################################
    # Dead Choppy Tests
    ###########################################################################

    def test_dead_choppy_logic_implemented(self):
        """Test that Dead Choppy detection and logic is implemented in wargear.py"""
        # This test verifies the keyword detection works
        # The actual attacks bonus logic is tested via integration tests
        # since it requires full Model/Unit mocking
        profile = self._make_profile("dead choppy", weapon_type="Melee")
        self.assertTrue(profile.is_dead_choppy())

        # Verify the method exists and can be called
        self.assertTrue(hasattr(profile, 'is_dead_choppy'))
        self.assertTrue(callable(profile.is_dead_choppy))

    ###########################################################################
    # Harpooned Tests
    ###########################################################################

    def test_harpooned_sets_flag_on_monster_hit(self):
        """Test that Harpooned sets charge bonus on unit when hitting MONSTER"""
        profile = self._make_profile("harpooned")
        attacker = self._make_attacker()
        target = self._make_target(has_monster=True)

        attack_instance = {}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            result = profile._hit_target_with_tracking(target, attacker, attack_instance)

        self.assertTrue(result['hit'])
        # Check that the charge bonus was set on the attacker's unit
        self.assertTrue(hasattr(attacker.parent_unit, "_ork_charge_bonuses"))
        target_id = getattr(target, "_id", id(target))
        self.assertIn(target_id, attacker.parent_unit._ork_charge_bonuses)
        bonus_info = attacker.parent_unit._ork_charge_bonuses[target_id]
        self.assertEqual(bonus_info["bonus"], 2)
        self.assertEqual(bonus_info["source"], "Harpooned")
        self.assertFalse(bonus_info["no_overwatch"])
        self.assertIn("Harpooned", str(result['special_effects']))

    def test_harpooned_sets_flag_on_vehicle_hit(self):
        """Test that Harpooned sets charge bonus on unit when hitting VEHICLE"""
        profile = self._make_profile("harpooned")
        attacker = self._make_attacker()
        target = self._make_target(has_vehicle=True)

        attack_instance = {}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            result = profile._hit_target_with_tracking(target, attacker, attack_instance)

        self.assertTrue(result['hit'])
        # Check that the charge bonus was set on the attacker's unit
        self.assertTrue(hasattr(attacker.parent_unit, "_ork_charge_bonuses"))
        target_id = getattr(target, "_id", id(target))
        self.assertIn(target_id, attacker.parent_unit._ork_charge_bonuses)
        bonus_info = attacker.parent_unit._ork_charge_bonuses[target_id]
        self.assertEqual(bonus_info["bonus"], 2)
        self.assertEqual(bonus_info["source"], "Harpooned")
        self.assertFalse(bonus_info["no_overwatch"])
        self.assertIn("Harpooned", str(result['special_effects']))

    def test_harpooned_no_flag_on_infantry_hit(self):
        """Test that Harpooned does NOT set flag when hitting non-MONSTER/VEHICLE"""
        profile = self._make_profile("harpooned")
        attacker = self._make_attacker()
        target = self._make_target(has_monster=False, has_vehicle=False)

        attack_instance = {}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            result = profile._hit_target_with_tracking(target, attacker, attack_instance)

        self.assertTrue(result['hit'])
        # Should NOT set charge bonus for non-MONSTER/VEHICLE
        self.assertFalse(hasattr(attacker.parent_unit, "_ork_charge_bonuses"))
        self.assertNotIn("Harpooned", str(result['special_effects']))

    ###########################################################################
    # Hooked Tests
    ###########################################################################

    def test_hooked_sets_flag_on_monster_hit(self):
        """Test that Hooked sets charge bonus and overwatch prevention flag"""
        profile = self._make_profile("hooked")
        attacker = self._make_attacker()
        target = self._make_target(has_monster=True)

        attack_instance = {}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            result = profile._hit_target_with_tracking(target, attacker, attack_instance)

        self.assertTrue(result['hit'])
        # Check that the charge bonus was set on the attacker's unit
        self.assertTrue(hasattr(attacker.parent_unit, "_ork_charge_bonuses"))
        target_id = getattr(target, "_id", id(target))
        self.assertIn(target_id, attacker.parent_unit._ork_charge_bonuses)
        bonus_info = attacker.parent_unit._ork_charge_bonuses[target_id]
        self.assertEqual(bonus_info["bonus"], 2)
        self.assertEqual(bonus_info["source"], "Hooked")
        self.assertTrue(bonus_info["no_overwatch"])  # Hooked prevents Overwatch
        self.assertIn("Hooked", str(result['special_effects']))
        self.assertIn("no Overwatch", str(result['special_effects']))

    ###########################################################################
    # Impaled Tests
    ###########################################################################

    def test_impaled_sets_flag_on_vehicle_hit(self):
        """Test that Impaled sets charge bonus flag when hitting VEHICLE"""
        profile = self._make_profile("anti-monster 2+, anti-vehicle 2+, impaled")
        attacker = self._make_attacker()
        target = self._make_target(has_vehicle=True)

        attack_instance = {}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            result = profile._hit_target_with_tracking(target, attacker, attack_instance)

        self.assertTrue(result['hit'])
        # Check that the charge bonus was set on the attacker's unit
        self.assertTrue(hasattr(attacker.parent_unit, "_ork_charge_bonuses"))
        target_id = getattr(target, "_id", id(target))
        self.assertIn(target_id, attacker.parent_unit._ork_charge_bonuses)
        bonus_info = attacker.parent_unit._ork_charge_bonuses[target_id]
        self.assertEqual(bonus_info["bonus"], 2)
        self.assertEqual(bonus_info["source"], "Impaled")
        self.assertFalse(bonus_info["no_overwatch"])
        self.assertIn("Impaled", str(result['special_effects']))

    ###########################################################################
    # Snagged Tests
    ###########################################################################

    def test_snagged_sets_flag_on_monster_hit(self):
        """Test that Snagged sets charge bonus and overwatch prevention flag"""
        profile = self._make_profile("anti-monster 2+, anti-vehicle 2+, snagged")
        attacker = self._make_attacker()
        target = self._make_target(has_monster=True)

        attack_instance = {}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            result = profile._hit_target_with_tracking(target, attacker, attack_instance)

        self.assertTrue(result['hit'])
        # Check that the charge bonus was set on the attacker's unit
        self.assertTrue(hasattr(attacker.parent_unit, "_ork_charge_bonuses"))
        target_id = getattr(target, "_id", id(target))
        self.assertIn(target_id, attacker.parent_unit._ork_charge_bonuses)
        bonus_info = attacker.parent_unit._ork_charge_bonuses[target_id]
        self.assertEqual(bonus_info["bonus"], 2)
        self.assertEqual(bonus_info["source"], "Snagged")
        self.assertTrue(bonus_info["no_overwatch"])  # Snagged prevents Overwatch
        self.assertIn("Snagged", str(result['special_effects']))
        self.assertIn("no Overwatch", str(result['special_effects']))

    ###########################################################################
    # Integration Tests for Charge Bonuses and Overwatch Prevention
    ###########################################################################

    def test_charge_bonus_applied_from_harpooned(self):
        """Test that Harpooned +2 charge bonus is applied in _apply_charge_modifiers"""
        from warhammer40k_ai.engine.game import Game
        from warhammer40k_ai.units.unit import Unit

        # Create a mock game and units
        game = SimpleNamespace(map=None, turn=1)
        charging_unit = SimpleNamespace(
            _ork_charge_bonuses={
                "target_123": {
                    "bonus": 2,
                    "source": "Harpooned",
                    "no_overwatch": False
                }
            },
            _filter_internal_rivalries_roll_modifiers=lambda mods, kind: mods,
            _filter_driven_by_ultimate_rage_roll_modifiers=lambda mods, kind: mods,
            special_rules={}
        )
        target_unit = SimpleNamespace(_id="target_123")

        # Create a minimal Game instance just to test _apply_charge_modifiers
        game_obj = Game.__new__(Game)
        game_obj.map = None

        # Test that the bonus is applied
        base_roll = 7
        modified_roll = game_obj._apply_charge_modifiers(charging_unit, base_roll, target_unit)

        self.assertEqual(modified_roll, 9)  # 7 + 2 from Harpooned

    def test_overwatch_prevented_by_hooked(self):
        """Test that Hooked prevents Overwatch from being queued"""
        from warhammer40k_ai.engine.stratagems import StratagemManager
        from warhammer40k_ai.engine.player import Player

        # Create mock objects
        moving_unit = SimpleNamespace(
            _ork_charge_bonuses={
                "defender_unit_id": {
                    "bonus": 2,
                    "source": "Hooked",
                    "no_overwatch": True
                }
            },
            get_parent_army=lambda: SimpleNamespace(player=SimpleNamespace(name="Attacker"))
        )

        defender_unit = SimpleNamespace(
            _id="defender_unit_id",
            is_alive=lambda: True,
            deployed=True,
            is_titanic=False
        )

        defender_player = SimpleNamespace(
            name="Defender",
            command_points=1,
            get_army=lambda: SimpleNamespace(units=[defender_unit])
        )

        game = SimpleNamespace(
            get_current_player=lambda: SimpleNamespace(name="Attacker"),
            map=SimpleNamespace(get_distance_between_units=lambda u1, u2: 10.0)
        )

        # Create stratagem manager
        stratagem_mgr = StratagemManager.__new__(StratagemManager)
        stratagem_mgr.player = defender_player
        stratagem_mgr.game = game
        stratagem_mgr._used_this_turn = {}
        stratagem_mgr._current_phase_name = "Charge phase"
        stratagem_mgr._pending_reactions = []

        # Mock the stratagem
        stratagem_mgr.get_by_name = lambda name: SimpleNamespace(
            is_phase_allowed=lambda phase: True,
            is_turn_allowed=lambda is_active: True,
            cp_cost=1
        )

        # Call _maybe_queue_overwatch - it should return early due to Hooked
        stratagem_mgr._maybe_queue_overwatch(moving_unit, "charge", "start")

        # Verify that no Overwatch was queued
        self.assertEqual(len(stratagem_mgr._pending_reactions), 0)


if __name__ == "__main__":
    unittest.main()


