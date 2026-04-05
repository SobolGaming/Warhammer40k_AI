"""
Tests for Psychic Assassin wargear keyword support.

Psychic Assassin changes the weapon's Attacks characteristic to 6 when targeting a unit with the PSYKER keyword.
This also tests the model vs unit keyword semantics (unit keywords are the union of all model keywords).
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.wargear import WargearProfile


class TestPsychicAssassinKeywordDetection(unittest.TestCase):
    """Test that Psychic Assassin keyword is correctly detected on weapon profiles."""
    
    def test_is_psychic_assassin_detects_keyword(self):
        """Test that is_psychic_assassin() returns True when 'psychic assassin' keyword is present."""
        profile = WargearProfile.__new__(WargearProfile)
        profile.keywords = ["Psychic Assassin", "Precision"]
        
        self.assertTrue(profile.is_psychic_assassin())
    
    def test_is_psychic_assassin_case_insensitive(self):
        """Test that is_psychic_assassin() is case-insensitive."""
        profile = WargearProfile.__new__(WargearProfile)
        profile.keywords = ["PSYCHIC ASSASSIN"]
        
        self.assertTrue(profile.is_psychic_assassin())
    
    def test_is_psychic_assassin_returns_false_when_absent(self):
        """Test that is_psychic_assassin() returns False when keyword is not present."""
        profile = WargearProfile.__new__(WargearProfile)
        profile.keywords = ["Precision", "Devastating Wounds"]
        
        self.assertFalse(profile.is_psychic_assassin())


class TestModelKeywordSemantics(unittest.TestCase):
    """Test that model keywords work correctly and unit keywords are computed as union."""
    
    def _create_model(self, name, keywords=None, faction_keywords=None):
        """Helper to create a model with keywords."""
        model = Model.__new__(Model)
        model.name = name
        model.keywords = list(keywords or [])
        model.faction_keywords = list(faction_keywords or [])
        model.wounds = 3  # is_alive is computed from wounds > 0
        model._base_wounds = 3
        return model
    
    def test_model_has_keyword(self):
        """Test that Model.has_keyword() correctly checks model-level keywords."""
        model = self._create_model("Test Model", keywords=["INFANTRY", "PSYKER"])
        
        self.assertTrue(model.has_keyword("PSYKER"))
        self.assertTrue(model.has_keyword("psyker"))  # Case-insensitive
        self.assertTrue(model.has_keyword("INFANTRY"))
        self.assertFalse(model.has_keyword("VEHICLE"))
    
    def test_model_has_any_keyword_checks_both_lists(self):
        """Test that Model.has_any_keyword() checks both keywords and faction_keywords."""
        model = self._create_model(
            "Test Model",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["CHAOS", "THOUSAND SONS"]
        )
        
        self.assertTrue(model.has_any_keyword("PSYKER"))
        self.assertTrue(model.has_any_keyword("CHAOS"))
        self.assertTrue(model.has_any_keyword("thousand sons"))  # Case-insensitive
        self.assertFalse(model.has_any_keyword("IMPERIUM"))
    
    def test_unit_keywords_are_union_of_model_keywords(self):
        """Test that unit keywords are computed as the union of all model keywords."""
        # Create a unit with mixed models
        unit = Unit.__new__(Unit)
        unit.name = "Mixed Unit"
        unit.keywords = []  # Unit-level keywords (empty for this test)
        unit.faction_keywords = []
        unit.attached_leaders = []
        unit.bodyguard_unit = None
        
        # Create models with different keywords
        model1 = self._create_model("Psyker Model", keywords=["INFANTRY", "PSYKER"])
        model2 = self._create_model("Regular Model", keywords=["INFANTRY"])
        model3 = self._create_model("Another Psyker", keywords=["INFANTRY", "PSYKER", "CHARACTER"])
        
        unit.models = [model1, model2, model3]
        
        # Get effective keywords
        effective_keywords = unit.get_effective_keywords()
        effective_keywords_lower = [k.lower() for k in effective_keywords]
        
        # Should contain union of all model keywords
        self.assertIn("infantry", effective_keywords_lower)
        self.assertIn("psyker", effective_keywords_lower)
        self.assertIn("character", effective_keywords_lower)
        
        # Unit should have PSYKER keyword because at least one model has it
        self.assertTrue(unit.has_any_keyword("PSYKER"))


class TestPsychicAssassinAttacksOverride(unittest.TestCase):
    """Test that Psychic Assassin correctly overrides Attacks to 6 when targeting PSYKER units."""
    
    def _create_psychic_assassin_weapon(self):
        """Helper to create a weapon with Psychic Assassin keyword."""
        wargear_data = {
            'range': '18',
            'A': '3',
            'BS_WS': '2+',
            'S': '5',
            'AP': '-3',
            'D': '3',
            'description': 'Psychic Assassin, Precision'
        }
        profile = WargearProfile('animus_speculum', wargear_data)
        return profile

    def _create_normal_weapon(self):
        """Helper to create a weapon without Psychic Assassin keyword."""
        wargear_data = {
            'range': '24',
            'A': '4',
            'BS_WS': '3+',
            'S': '4',
            'AP': '-1',
            'D': '1',
            'description': ''  # No keywords
        }
        profile = WargearProfile('bolter', wargear_data)
        return profile

    def _create_unit_with_keywords(self, name, keywords=None, faction_keywords=None):
        """Helper to create a unit with specific keywords."""
        unit = Unit.__new__(Unit)
        unit.name = name
        unit.keywords = list(keywords or [])
        unit.faction_keywords = list(faction_keywords or [])
        unit.attached_leaders = []
        unit.bodyguard_unit = None

        # Create a model with the same keywords
        model = Model.__new__(Model)
        model.name = f"{name} Model"
        model.keywords = list(keywords or [])
        model.faction_keywords = list(faction_keywords or [])
        model.wounds = 3  # is_alive is computed from wounds > 0
        model._base_wounds = 3

        unit.models = [model]
        unit.has_any_keyword = lambda kw: kw.upper() in [k.upper() for k in unit.get_effective_keywords()]

        return unit, model

    def test_psychic_assassin_override_applies_to_psyker_target(self):
        """Test that Psychic Assassin weapon gets Attacks=6 when targeting PSYKER unit."""
        weapon = self._create_psychic_assassin_weapon()
        psyker_unit, psyker_model = self._create_unit_with_keywords(
            "Psyker Unit",
            keywords=["INFANTRY", "PSYKER"]
        )
        attacker_unit, attacker_model = self._create_unit_with_keywords(
            "Attacker Unit",
            keywords=["INFANTRY"]
        )

        # Verify weapon has Psychic Assassin
        self.assertTrue(weapon.is_psychic_assassin())

        # Verify target has PSYKER keyword
        self.assertTrue(psyker_unit.has_any_keyword("PSYKER"))

        # Test preview_attack_count with PSYKER target
        with patch.object(attacker_model, 'return_closest_model_in_unit', return_value=(psyker_model, 10.0)):
            attack_info = weapon.preview_attack_count(psyker_unit, attacker_model, publish_roll_event=False)

            # Should override to 6 attacks
            self.assertEqual(attack_info.num_attacks, 6)
            self.assertIn("Psychic Assassin", attack_info.special_modifiers)

    def test_psychic_assassin_no_override_for_non_psyker_target(self):
        """Test that Psychic Assassin weapon uses base Attacks when targeting non-PSYKER unit."""
        weapon = self._create_psychic_assassin_weapon()
        normal_unit, normal_model = self._create_unit_with_keywords(
            "Normal Unit",
            keywords=["INFANTRY"]
        )
        attacker_unit, attacker_model = self._create_unit_with_keywords(
            "Attacker Unit",
            keywords=["INFANTRY"]
        )

        # Verify weapon has Psychic Assassin
        self.assertTrue(weapon.is_psychic_assassin())

        # Verify target does NOT have PSYKER keyword
        self.assertFalse(normal_unit.has_any_keyword("PSYKER"))

        # Test preview_attack_count with non-PSYKER target
        with patch.object(attacker_model, 'return_closest_model_in_unit', return_value=(normal_model, 10.0)):
            attack_info = weapon.preview_attack_count(normal_unit, attacker_model, publish_roll_event=False)

            # Should use base attacks (3)
            self.assertEqual(attack_info.num_attacks, 3)
            self.assertNotIn("Psychic Assassin", attack_info.special_modifiers)

    def test_normal_weapon_no_override_for_psyker_target(self):
        """Test that normal weapons (without Psychic Assassin) don't get override even vs PSYKER."""
        weapon = self._create_normal_weapon()
        psyker_unit, psyker_model = self._create_unit_with_keywords(
            "Psyker Unit",
            keywords=["INFANTRY", "PSYKER"]
        )
        attacker_unit, attacker_model = self._create_unit_with_keywords(
            "Attacker Unit",
            keywords=["INFANTRY"]
        )

        # Verify weapon does NOT have Psychic Assassin
        self.assertFalse(weapon.is_psychic_assassin())

        # Verify target has PSYKER keyword
        self.assertTrue(psyker_unit.has_any_keyword("PSYKER"))

        # Test preview_attack_count with PSYKER target
        with patch.object(attacker_model, 'return_closest_model_in_unit', return_value=(psyker_model, 10.0)):
            attack_info = weapon.preview_attack_count(psyker_unit, attacker_model, publish_roll_event=False)

            # Should use base attacks (4)
            self.assertEqual(attack_info.num_attacks, 4)
            self.assertNotIn("Psychic Assassin", attack_info.special_modifiers)


if __name__ == '__main__':
    unittest.main()


