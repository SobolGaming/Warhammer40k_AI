import unittest
from unittest.mock import patch
from types import SimpleNamespace


class TestConversionKeyword(unittest.TestCase):
    """Test suite for the Conversion weapon keyword.
    
    Conversion: Each time an attack is made with this weapon, if the target is more than 12"
    from the bearer, an unmodified successful Hit roll of 4+ scores a Critical Hit.
    """
    
    def _make_ranged_profile(self, keywords: str = "", bs: str = "3+", weapon_range: str = "24"):
        """Helper to create a weapon profile with specified keywords."""
        from warhammer40k_ai.units.wargear import Wargear

        data = {
            "name": "Test Weapon",
            "type": "Ranged",
            "range": weapon_range,
            "A": "1",
            "BS_WS": bs,
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": keywords,
        }
        parent = Wargear(data)
        return parent.profiles["default"]
    
    def _make_attacker(self, distance_to_target: float = 10.0):
        """Helper to create attacker model with controlled distance to target."""
        class _Unit:
            def get_parent_army(self):
                return None
            
            def get_attached_unit_root(self):
                return self
        
        unit = _Unit()
        attacker = SimpleNamespace(
            name="Attacker",
            parent_unit=unit,
        )
        
        # Mock return_closest_model_in_unit to return controlled distance
        def mock_closest(target_unit):
            return (SimpleNamespace(is_alive=True), distance_to_target)
        
        attacker.return_closest_model_in_unit = mock_closest
        return attacker
    
    def _make_target(self):
        """Helper to create a simple target unit."""
        return SimpleNamespace(
            name="Target",
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda k: False,
        )
    
    def test_conversion_keyword_detection(self):
        """Test that Conversion keyword is properly detected."""
        profile = self._make_ranged_profile("conversion")
        self.assertTrue(profile.is_conversion())
        # Without attacker, should default to 12.0
        self.assertEqual(profile.get_conversion_distance(), 12.0)
        self.assertEqual(profile.get_conversion_crit_threshold(), 4)

    def test_conversion_distance_parsing_12_inches(self):
        """Test that Conversion distance is parsed from unit ability (12\")."""
        # Create a mock datasheet with Conversion ability at 12"
        class MockDatasheet:
            datasheets_abilities = [{
                "name": "Conversion",
                "description": 'Each time an attack made with this weapon targets a unit more than 12" from the bearer, an unmodified successful Hit roll of 4+ scores a Critical Hit.',
                "type": "Wargear profile"
            }]

        class MockUnit:
            datasheet = MockDatasheet()

        attacker = SimpleNamespace(
            name="Test Model",
            parent_unit=MockUnit()
        )

        profile = self._make_ranged_profile("conversion")
        distance = profile.get_conversion_distance(attacker)
        self.assertEqual(distance, 12.0)

    def test_conversion_distance_parsing_18_inches(self):
        """Test that Conversion distance is parsed from unit ability (18\")."""
        # Create a mock datasheet with Conversion ability at 18"
        class MockDatasheet:
            datasheets_abilities = [{
                "name": "Conversion",
                "description": 'Each time an attack made with this weapon targets a unit more than 18" from the bearer, an unmodified successful Hit roll of 4+ scores a Critical Hit.',
                "type": "Wargear profile"
            }]

        class MockUnit:
            datasheet = MockDatasheet()

        attacker = SimpleNamespace(
            name="Test Model",
            parent_unit=MockUnit()
        )

        profile = self._make_ranged_profile("conversion")
        distance = profile.get_conversion_distance(attacker)
        self.assertEqual(distance, 18.0)

    def test_conversion_distance_parsing_24_inches(self):
        """Test that Conversion distance is parsed from unit ability (24\")."""
        # Create a mock datasheet with Conversion ability at 24"
        class MockDatasheet:
            datasheets_abilities = [{
                "name": "Conversion",
                "description": 'Each time an attack is made with this weapon, if the target is more than 24" from the bearer, an unmodified successful Hit roll of 4+ scores a Critical Hit.',
                "type": "Wargear profile"
            }]

        class MockUnit:
            datasheet = MockDatasheet()

        attacker = SimpleNamespace(
            name="Test Model",
            parent_unit=MockUnit()
        )

        profile = self._make_ranged_profile("conversion")
        distance = profile.get_conversion_distance(attacker)
        self.assertEqual(distance, 24.0)
    
    def test_conversion_inactive_within_threshold(self):
        """Test that Conversion does not activate when target is within 12"."""
        profile = self._make_ranged_profile("conversion")
        attacker = self._make_attacker(distance_to_target=12.0)  # Exactly 12"
        target = self._make_target()
        attack_instance = {}
        
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)
        
        # Should hit (BS 3+, rolled 4), but NOT critical (distance not > 12")
        self.assertTrue(res["hit"])
        self.assertFalse(attack_instance.get("crit_hit", False))
    
    def test_conversion_active_beyond_threshold(self):
        """Test that Conversion activates when target is beyond 12"."""
        profile = self._make_ranged_profile("conversion")
        attacker = self._make_attacker(distance_to_target=13.0)  # Beyond 12"
        target = self._make_target()
        attack_instance = {'conversion_active': True}  # Simulate conversion being active
        
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)
        
        # Should hit AND be critical (Conversion active, unmodified 4+)
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("crit_hit", False))
        self.assertIn("Conversion", str(res.get("special_effects", [])))
    
    def test_conversion_requires_successful_hit_with_negative_modifier(self):
        """Test that Conversion requires the hit to succeed after modifiers."""
        profile = self._make_ranged_profile("conversion", bs="4+")  # BS 4+
        attacker = self._make_attacker(distance_to_target=13.0)
        target = self._make_target()
        # Apply a -1 to hit modifier via Stealth
        target.has_stealth = lambda: True
        attack_instance = {'conversion_active': True}
        
        # Unmodified 4, but with -1 to hit modifier (final needed would be 5+)
        # This test simulates the scenario where modifiers cause a miss
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)
        
        # With BS 4+ and -1 to hit, roll of 4 should miss and not become critical
        self.assertFalse(res["hit"])
        self.assertFalse(attack_instance.get("crit_hit", False))

    def test_conversion_with_unmodified_6_baseline(self):
        """Test that unmodified 6 is always critical (baseline rule)."""
        profile = self._make_ranged_profile("conversion")
        attacker = self._make_attacker(distance_to_target=13.0)
        target = self._make_target()
        attack_instance = {'conversion_active': True}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)

        # Should be critical from baseline rule (unmodified 6)
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("crit_hit", False))
        # Should have "Natural 6" in effects, not Conversion
        effects_str = str(res.get("special_effects", []))
        self.assertIn("Natural 6", effects_str)

    def test_conversion_with_lethal_hits(self):
        """Test that Conversion-triggered crits work with Lethal Hits."""
        profile = self._make_ranged_profile("conversion, lethal hits")
        attacker = self._make_attacker(distance_to_target=13.0)
        target = self._make_target()
        attack_instance = {'conversion_active': True}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)

        # Should be critical from Conversion, and Lethal Hits should apply
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("crit_hit", False))
        self.assertTrue(attack_instance.get("lethal_hit", False))

    def test_conversion_with_sustained_hits(self):
        """Test that Conversion-triggered crits work with Sustained Hits."""
        profile = self._make_ranged_profile("conversion, sustained hits 1")
        attacker = self._make_attacker(distance_to_target=13.0)
        target = self._make_target()
        attack_instance = {'conversion_active': True}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)

        # Should be critical from Conversion, and Sustained Hits should apply
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("crit_hit", False))
        self.assertGreater(attack_instance.get("sustained_hit", 0), 0)

    def test_conversion_boundary_exact_distance(self):
        """Test strict > comparison at exactly 12.0"."""
        profile = self._make_ranged_profile("conversion")

        # Test at exactly 12.0" - should NOT activate
        attacker_at_12 = self._make_attacker(distance_to_target=12.0)
        target = self._make_target()
        attack_instance_12 = {'conversion_active': False}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res_12 = profile._hit_target_with_tracking(target, attacker_at_12, attack_instance_12)

        self.assertTrue(res_12["hit"])
        self.assertFalse(attack_instance_12.get("crit_hit", False))

        # Test at 12.1" - should activate
        attacker_beyond = self._make_attacker(distance_to_target=12.1)
        attack_instance_beyond = {'conversion_active': True}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res_beyond = profile._hit_target_with_tracking(target, attacker_beyond, attack_instance_beyond)

        self.assertTrue(res_beyond["hit"])
        self.assertTrue(attack_instance_beyond.get("crit_hit", False))

    def test_conversion_unmodified_1_always_fails(self):
        """Test that unmodified 1 always fails, even with Conversion active."""
        profile = self._make_ranged_profile("conversion")
        attacker = self._make_attacker(distance_to_target=13.0)
        target = self._make_target()
        attack_instance = {'conversion_active': True}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=1):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)

        # Should always miss on unmodified 1
        self.assertFalse(res["hit"])
        self.assertFalse(attack_instance.get("crit_hit", False))

    def test_conversion_unmodified_3_misses_below_threshold(self):
        """Test that unmodified 3 doesn't trigger Conversion (below 4+ threshold)."""
        profile = self._make_ranged_profile("conversion", bs="3+")
        attacker = self._make_attacker(distance_to_target=13.0)
        target = self._make_target()
        attack_instance = {'conversion_active': True}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)

        # Should hit (BS 3+, rolled 3), but NOT critical (unmodified < 4)
        self.assertTrue(res["hit"])
        self.assertFalse(attack_instance.get("crit_hit", False))

    def test_conversion_does_not_apply_to_baseline_critical(self):
        """Test that Conversion doesn't double-apply to baseline criticals."""
        profile = self._make_ranged_profile("conversion")
        attacker = self._make_attacker(distance_to_target=13.0)
        target = self._make_target()
        attack_instance = {'conversion_active': True}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)

        # Should be critical from baseline (unmodified 6), not from Conversion
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("crit_hit", False))
        effects_str = str(res.get("special_effects", []))
        # Should mention Natural 6, not Conversion
        self.assertIn("Natural 6", effects_str)

    def test_conversion_with_dark_pacts_lethal_hits(self):
        """Test that Conversion-upgraded crits apply Dark Pacts Lethal Hits."""
        profile = self._make_ranged_profile("conversion")

        # Create attacker with Dark Pacts active
        class _Unit:
            special_rules = {
                "dark_pacts_active": True,
                "dark_pacts_choice": "LETHAL HITS"
            }
            def get_parent_army(self):
                return None
            def get_attached_unit_root(self):
                return self

        unit = _Unit()
        attacker = SimpleNamespace(
            name="Attacker",
            parent_unit=unit,
        )

        def mock_closest(target_unit):
            return (SimpleNamespace(is_alive=True), 13.0)

        attacker.return_closest_model_in_unit = mock_closest

        target = self._make_target()
        attack_instance = {'conversion_active': True}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)

        # Should be critical from Conversion, and Dark Pacts Lethal Hits should apply
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("crit_hit", False))
        self.assertTrue(attack_instance.get("lethal_hit", False))
        self.assertIn("Conversion", str(res.get("special_effects", [])))
        self.assertIn("Lethal Hits", str(res.get("special_effects", [])))

    def test_conversion_with_bondsman_sustained_hits(self):
        """Test that Conversion-upgraded crits apply Bondsman Sustained Hits."""
        profile = self._make_ranged_profile("conversion")

        # Create attacker with Bondsman Sustained Hits
        class _Unit:
            special_rules = {
                "bondsman_sustained_hits": True
            }
            def get_parent_army(self):
                return None
            def get_attached_unit_root(self):
                return self

        unit = _Unit()
        attacker = SimpleNamespace(
            name="Attacker",
            parent_unit=unit,
        )

        def mock_closest(target_unit):
            return (SimpleNamespace(is_alive=True), 13.0)

        attacker.return_closest_model_in_unit = mock_closest

        target = self._make_target()
        attack_instance = {'conversion_active': True}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)

        # Should be critical from Conversion, and Bondsman Sustained Hits should apply
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("crit_hit", False))
        self.assertGreater(attack_instance.get("sustained_hit", 0), 0)
        self.assertIn("Conversion", str(res.get("special_effects", [])))
        self.assertIn("Sustained Hits", str(res.get("special_effects", [])))


if __name__ == "__main__":
    unittest.main()

