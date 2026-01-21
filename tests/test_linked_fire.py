"""
Tests for Linked Fire wargear keyword support.

Linked Fire allows Fire Prism units to measure range and visibility from another friendly Fire Prism,
with the weapon's Attacks characteristic becoming 1 when doing so.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.aura_utils import get_eligible_linked_fire_origin_units


class TestLinkedFireKeywordDetection(unittest.TestCase):
    """Test that Linked Fire keyword is correctly detected on weapon profiles."""
    
    def test_is_linked_fire_detects_keyword(self):
        """Test that is_linked_fire() returns True when 'linked fire' keyword is present."""
        profile = WargearProfile.__new__(WargearProfile)
        profile.keywords = ["Linked Fire", "Heavy"]
        
        self.assertTrue(profile.is_linked_fire())
    
    def test_is_linked_fire_case_insensitive(self):
        """Test that is_linked_fire() is case-insensitive."""
        profile = WargearProfile.__new__(WargearProfile)
        profile.keywords = ["LINKED FIRE"]
        
        self.assertTrue(profile.is_linked_fire())
    
    def test_is_linked_fire_returns_false_when_absent(self):
        """Test that is_linked_fire() returns False when keyword is not present."""
        profile = WargearProfile.__new__(WargearProfile)
        profile.keywords = ["Heavy", "Blast"]
        
        self.assertFalse(profile.is_linked_fire())


class TestLinkedFireEligibility(unittest.TestCase):
    """Test eligibility checks for Linked Fire origin units."""
    
    def _create_fire_prism(self, name, army, x=0.0, y=0.0):
        """Helper to create a Fire Prism unit."""
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name.lower().replace(" ", "_")
        unit.keywords = ["Fire Prism", "Vehicle"]
        unit.deployed = True
        
        # Create a model
        model = SimpleNamespace()
        model.name = f"{name} Model"
        model.is_alive = True
        model.x = x
        model.y = y
        model.z = 0.0
        model.facing = 0.0
        model.base_size = 1.0
        model.height = 5.0
        unit.models = [model]
        
        # Mock methods
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.has_any_keyword = lambda kw: kw.upper() in [k.upper() for k in unit.keywords]
        
        return unit
    
    def test_eligible_units_excludes_bearer(self):
        """Test that the bearer unit is excluded from eligible origins."""
        army = SimpleNamespace()
        army.units = []

        bearer = self._create_fire_prism("Bearer Prism", army)
        other = self._create_fire_prism("Other Prism", army, x=10.0)

        army.units = [bearer, other]

        # Mock game_map with LOS check and get_friendly_units
        game_map = SimpleNamespace()
        game_map.has_line_of_sight = lambda m1, m2: True
        game_map.can_model_see_model = lambda m1, m2: True
        game_map.get_friendly_units = lambda u: [bearer, other]

        eligible = get_eligible_linked_fire_origin_units(bearer, game_map=game_map)

        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0], other)
        self.assertNotIn(bearer, eligible)
    
    def test_eligible_units_requires_fire_prism_keywords(self):
        """Test that only units with FIRE and PRISM keywords are eligible."""
        army = SimpleNamespace()
        army.units = []

        bearer = self._create_fire_prism("Bearer Prism", army)
        fire_prism = self._create_fire_prism("Fire Prism", army, x=10.0)

        # Create a non-Fire Prism unit
        other_unit = Unit.__new__(Unit)
        other_unit.name = "Other Unit"
        other_unit._id = "other_unit"
        other_unit.keywords = ["Vehicle"]
        other_unit.deployed = True
        other_unit.models = [SimpleNamespace(is_alive=True, x=15.0, y=0.0, z=0.0, facing=0.0, base_size=1.0, height=5.0)]
        other_unit.is_alive = lambda: True
        other_unit.get_parent_army = lambda: army
        other_unit.has_any_keyword = lambda kw: kw.upper() in [k.upper() for k in other_unit.keywords]

        army.units = [bearer, fire_prism, other_unit]

        # Mock game_map
        game_map = SimpleNamespace()
        game_map.has_line_of_sight = lambda m1, m2: True
        game_map.can_model_see_model = lambda m1, m2: True
        game_map.get_friendly_units = lambda u: [bearer, fire_prism, other_unit]

        eligible = get_eligible_linked_fire_origin_units(bearer, game_map=game_map)

        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0], fire_prism)

    def test_eligible_units_requires_visibility(self):
        """Test that visibility is required for Linked Fire origin."""
        army = SimpleNamespace()
        army.units = []

        bearer = self._create_fire_prism("Bearer Prism", army)
        other = self._create_fire_prism("Other Prism", army, x=10.0)

        army.units = [bearer, other]

        game_map = SimpleNamespace()
        game_map.can_model_see_model = lambda m1, m2: False
        game_map.get_friendly_units = lambda u: [bearer, other]

        eligible = get_eligible_linked_fire_origin_units(bearer, game_map=game_map)

        self.assertEqual(len(eligible), 0)
    
    def test_eligible_units_requires_same_army(self):
        """Test that only friendly units (same army) are eligible."""
        army1 = SimpleNamespace()
        army1.units = []
        army2 = SimpleNamespace()
        army2.units = []

        bearer = self._create_fire_prism("Bearer Prism", army1)
        friendly = self._create_fire_prism("Friendly Prism", army1, x=10.0)
        enemy = self._create_fire_prism("Enemy Prism", army2, x=15.0)

        army1.units = [bearer, friendly]
        army2.units = [enemy]

        # Mock game_map - get_friendly_units should only return units from same army
        game_map = SimpleNamespace()
        game_map.has_line_of_sight = lambda m1, m2: True
        game_map.can_model_see_model = lambda m1, m2: True
        game_map.get_friendly_units = lambda u: [bearer, friendly]  # Only army1 units

        eligible = get_eligible_linked_fire_origin_units(bearer, game_map=game_map)

        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0], friendly)
        self.assertNotIn(enemy, eligible)


class TestLinkedFireRangeAndLOS(unittest.TestCase):
    """Test that range and LOS are measured from origin unit when using Linked Fire."""

    def _create_unit_with_weapon(self, name, army, x=0.0, y=0.0, has_linked_fire=False):
        """Helper to create a unit with a weapon."""
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name.lower().replace(" ", "_")
        unit.keywords = ["Fire Prism", "Vehicle"] if "Prism" in name else ["Vehicle"]
        unit.deployed = True
        # is_vehicle and is_monster are properties, so we can't set them directly
        # They are derived from keywords, so setting keywords is sufficient

        # Create a model
        from src.warhammer40k_ai.utility.model_base import Base, BaseType
        model = SimpleNamespace()
        model.name = f"{name} Model"
        model.is_alive = True
        model.x = x
        model.y = y
        model.z = 0.0
        model.facing = 0.0
        model.base_size = 1.0
        model.height = 5.0
        # Create base and set its position
        model.model_base = Base(BaseType.CIRCULAR, 1.0)  # 1" circular base
        model.model_base.set_position(x, y, 0.0)
        model.abilities = []  # No abilities

        # Create weapon
        weapon = SimpleNamespace()
        weapon.name = "Prism cannon - focused lances"
        weapon.profiles = {}

        profile = WargearProfile.__new__(WargearProfile)
        profile.name = "Prism cannon - focused lances"
        profile.keywords = ["Linked Fire", "Heavy"] if has_linked_fire else ["Heavy"]
        profile.parent_wargear = weapon
        profile.range = SimpleNamespace(max=48.0)
        profile.attacks = SimpleNamespace(value=2)
        profile.is_pistol = lambda: False
        profile.is_blast = lambda: False
        profile.is_indirect_fire = lambda: False
        profile.is_linked_fire = lambda: has_linked_fire

        weapon.profiles["default"] = profile
        model.wargear = [weapon]
        unit.models = [model]

        # Mock methods
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.has_any_keyword = lambda kw: kw.upper() in [k.upper() for k in unit.keywords]
        unit.get_models_for_collision = lambda: unit.models
        unit._has_line_of_sight_to_target = lambda m, tu, gm: True
        unit._attacking_unit_has_any_los_to_target_unit = lambda tu, gm: True
        unit._can_shoot_while_engaged = lambda m, wp, tu, gm: True
        unit._is_controlling_players_shooting_phase = lambda: False

        return unit, profile

    def test_range_measured_from_origin_unit(self):
        """Test that range is measured from origin unit models, not bearer."""
        army = SimpleNamespace()

        # Bearer at (0, 0), origin at (30, 0), target at (70, 0)
        # Bearer is 70" from target (out of 48" range)
        # Origin is 40" from target (within 48" range)
        bearer, profile = self._create_unit_with_weapon("Bearer Prism", army, x=0.0, y=0.0, has_linked_fire=True)
        origin, _ = self._create_unit_with_weapon("Origin Prism", army, x=30.0, y=0.0)
        target, _ = self._create_unit_with_weapon("Target", army, x=70.0, y=0.0)

        # Mock game_map
        game_map = SimpleNamespace()
        game_map.has_line_of_sight = lambda m1, m2: True
        game_map.is_within_engagement_range = lambda u1, u2: False
        game_map.get_friendly_units = lambda u: []
        game_map.get_enemy_units = lambda u: []

        # Without origin unit: should be out of range
        can_shoot_without_origin = bearer._can_model_shoot_weapon_at_target(
            bearer.models[0], profile, target, game_map, origin_unit=None
        )
        self.assertFalse(can_shoot_without_origin, "Bearer should be out of range without Linked Fire")

        # With origin unit: should be in range
        can_shoot_with_origin = bearer._can_model_shoot_weapon_at_target(
            bearer.models[0], profile, target, game_map, origin_unit=origin
        )
        self.assertTrue(can_shoot_with_origin, "Bearer should be in range when using Linked Fire from origin")


class TestLinkedFireAttacksOverride(unittest.TestCase):
    """Test that Attacks characteristic is overridden to 1 when using Linked Fire."""

    def test_attacks_override_applied_when_using_linked_fire(self):
        """Test that attacks_override=1 is passed to weapon.attack() when using Linked Fire."""
        # Create mock units
        army = SimpleNamespace()
        bearer = Unit.__new__(Unit)
        bearer.name = "Bearer Prism"
        bearer._id = "bearer_prism"
        bearer.keywords = ["FIRE", "PRISM"]
        bearer.deployed = True

        origin = Unit.__new__(Unit)
        origin.name = "Origin Prism"
        origin._id = "origin_prism"
        origin.keywords = ["FIRE", "PRISM"]
        origin.deployed = True

        target = Unit.__new__(Unit)
        target.name = "Target"
        target._id = "target"

        # Create models
        bearer_model = SimpleNamespace(is_alive=True, name="Bearer Model", x=0.0, y=0.0, z=0.0, facing=0.0, base_size=1.0, height=5.0)
        origin_model = SimpleNamespace(is_alive=True, name="Origin Model", x=10.0, y=0.0, z=0.0, facing=0.0, base_size=1.0, height=5.0)
        target_model = SimpleNamespace(is_alive=True, name="Target Model", x=20.0, y=0.0, z=0.0, facing=0.0, base_size=1.0, height=5.0)

        bearer.models = [bearer_model]
        origin.models = [origin_model]
        target.models = [target_model]

        # Create weapon with Linked Fire
        weapon = SimpleNamespace()
        weapon.name = "Prism cannon - focused lances"
        weapon.profiles = {}

        profile = WargearProfile.__new__(WargearProfile)
        profile.name = "Prism cannon - focused lances"
        profile.keywords = ["Linked Fire"]
        profile.parent_wargear = weapon
        profile.range = SimpleNamespace(max=48.0)
        profile.attacks = SimpleNamespace(value=2)
        profile.is_one_shot = lambda: False
        profile.is_bubblechukka = lambda: False

        # Mock attack method to capture parameters
        attack_calls = []
        def mock_attack(*args, **kwargs):
            attack_calls.append(kwargs)
            return SimpleNamespace(total_hits=1)

        profile.attack = mock_attack
        weapon.profiles["default"] = profile
        bearer_model.wargear = [weapon]

        # Mock game_map and methods
        game_map = SimpleNamespace()
        game_map.has_line_of_sight = lambda m1, m2: True

        bearer.get_parent_army = lambda: army
        bearer.is_alive = lambda: True
        bearer.get_models_for_collision = lambda: bearer.models
        bearer._can_model_shoot_weapon_at_target = lambda m, wp, tu, gm, origin_unit=None: True

        # Execute weapon attacks with Linked Fire origin
        result = bearer._execute_weapon_attacks(
            profile,
            target,
            [bearer_model],
            game_map,
            linked_fire_origin_unit=origin
        )

        # Verify attack was called with attacks_override=1
        self.assertEqual(len(attack_calls), 1)
        self.assertEqual(attack_calls[0].get("attacks_override"), 1)
        self.assertEqual(attack_calls[0].get("attacks_override_note"), "Linked Fire")


if __name__ == "__main__":
    unittest.main()
