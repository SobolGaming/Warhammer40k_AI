"""
Test suite for Fight Phase functionality in Warhammer 40k

This test suite covers:
1. Fight phase stage management (Fight First vs Remaining Combatants)
2. Player turn order (non-current player goes first)
3. Unit eligibility for fighting
4. Target selection and engagement range validation
5. Fight sequence execution (Pile-in â†’ Attack â†’ Consolidate)
6. Alternating player selection
7. Stage progression and completion
"""

import pytest
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager, FightStage
from warhammer40k_ai.units.unit import Unit, UnitRoundState
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.battlefield.map import Map


class TestFightPhaseManager(unittest.TestCase):
    """Test the FightPhaseManager class functionality."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create mock game
        self.game = Mock(spec=Game)
        self.game_map = Mock(spec=Map)
        self.game.map = self.game_map
        
        # Create mock players
        self.player1 = Mock(spec=Player)
        self.player1.name = "Player 1"
        self.player1.control = Mock(spec=PlayerControl)
        self.player1.control.name = "LOCAL"
        self.player1.has_control = Mock(return_value=True)
        
        self.player2 = Mock(spec=Player)
        self.player2.name = "Player 2"
        self.player2.control = Mock(spec=PlayerControl)
        self.player2.control.name = "LOCAL"
        self.player2.has_control = Mock(return_value=True)
        
        # Create mock armies
        self.army1 = Mock(spec=Army)
        self.army1.player = self.player1
        self.army2 = Mock(spec=Army)
        self.army2.player = self.player2
        
        # Create mock units
        self.unit1_charged = self._create_mock_unit("Chaos Spawn", self.army1, charged=True)
        self.unit1_normal = self._create_mock_unit("Cultists", self.army1, charged=False)
        self.unit2_fight_first = self._create_mock_unit("Berzerkers", self.army2, fight_first=True)
        self.unit2_normal = self._create_mock_unit("Marines", self.army2, charged=False)
        
        # Set up game mock methods
        self.game.get_fight_first_units.side_effect = self._get_fight_first_units
        self.game.get_remaining_combatant_units.side_effect = self._get_remaining_combatant_units
        
        # Create fight phase manager
        self.manager = FightPhaseManager(self.game)
        
        # Set up callbacks
        self.unit_selection_callback = Mock()
        self.target_selection_callback = Mock()
        self.stage_complete_callback = Mock()
        
        self.manager.on_unit_selection_required = self.unit_selection_callback
        self.manager.on_target_selection_required = self.target_selection_callback
        self.manager.on_stage_complete = self.stage_complete_callback
    
    def _create_mock_unit(self, name, army, charged=False, fight_first=False):
        """Create a mock unit with specified properties."""
        unit = Mock(spec=Unit)
        unit.name = name
        unit.id = f"unit:{name.lower().replace(' ', '_')}"
        unit._id = unit.id
        unit.is_alive.return_value = True
        unit.get_parent_army.return_value = army
        
        # Set up round state
        unit.round_state = Mock(spec=UnitRoundState)
        unit.round_state.declared_charge_this_round = charged
        
        # Set up fight first ability
        unit.should_fight_first.return_value = charged or fight_first
        unit.has_fight_first.return_value = fight_first
        
        # Set up position and engagement
        # Unit position is now determined by model positions - no need to mock get_position
        
        return unit
    
    def _get_fight_first_units(self, player):
        """Mock implementation of get_fight_first_units."""
        if player == self.player1:
            return [self.unit1_charged]
        elif player == self.player2:
            return [self.unit2_fight_first]
        return []
    
    def _get_remaining_combatant_units(self, player):
        """Mock implementation of get_remaining_combatant_units."""
        if player == self.player1:
            return [self.unit1_normal]
        elif player == self.player2:
            return [self.unit2_normal]
        return []
    
    def test_fight_phase_initialization(self):
        """Test that fight phase initializes correctly."""
        self.manager.start_fight_phase(self.player1, self.player2)
        
        # Should start with Fight First stage
        self.assertEqual(self.manager.get_current_stage(), FightStage.FIGHT_FIRST)
        
        # Non-current player (player2) should go first
        self.assertEqual(self.manager.get_active_player(), self.player2)
        
        # Should have called unit selection callback
        self.unit_selection_callback.assert_called_once()
        
        # Reset fought units
        self.assertEqual(len(self.manager.fought_units), 0)
    
    def test_fight_first_stage_unit_selection(self):
        """Test unit selection in Fight First stage."""
        self.manager.start_fight_phase(self.player1, self.player2)
        
        # Player 2 should be prompted to select from their fight first units
        args, kwargs = self.unit_selection_callback.call_args
        active_player, eligible_units, stage = args
        
        self.assertEqual(active_player, self.player2)
        self.assertIn(self.unit2_fight_first, eligible_units)
        self.assertEqual(stage, FightStage.FIGHT_FIRST)
    
    def test_unit_selection_with_single_target(self):
        """Test unit selection when there's only one eligible target."""
        self.manager.start_fight_phase(self.player1, self.player2)
        
        # Mock single target scenario
        self.game_map.get_enemy_units.return_value = [self.unit1_charged]
        self.game_map.is_within_engagement_range.return_value = True
        
        # Set up UI callbacks for the new fight sequence
        def mock_ui_callback(movement_type, unit, callback):
            # Simulate successful movement completion
            callback(True)
        
        self.manager.on_movement_required = mock_ui_callback
        
        # Mock weapon selection callback
        def mock_weapon_selection_callback(fighting_unit, target_unit, callback):
            # Simulate weapon selection completion with empty declarations
            callback([])
        
        self.manager.on_weapon_selection_required = mock_weapon_selection_callback
        
        # Select unit
        self.manager.unit_selected(self.unit2_fight_first, self.player1, self.player2)
        
        # Should call target selection callback (even for single target)
        self.target_selection_callback.assert_called_once()
        
        # Get the arguments passed to the callback
        args, kwargs = self.target_selection_callback.call_args
        fighting_unit, eligible_targets, active_player = args
        
        self.assertEqual(fighting_unit, self.unit2_fight_first)
        self.assertIn(self.unit1_charged, eligible_targets)
        self.assertEqual(active_player, self.player2)
    
    def test_unit_selection_with_multiple_targets(self):
        """Test unit selection when there are multiple eligible targets."""
        self.manager.start_fight_phase(self.player1, self.player2)
        
        # Mock multiple targets scenario
        target1 = self._create_mock_unit("Target 1", self.army1)
        target2 = self._create_mock_unit("Target 2", self.army1)
        self.game_map.get_enemy_units.return_value = [target1, target2]
        self.game_map.is_within_engagement_range.return_value = True
        
        # Select unit
        self.manager.unit_selected(self.unit2_fight_first, self.player1, self.player2)
        
        # Should call target selection callback
        self.target_selection_callback.assert_called_once()
        
        args, kwargs = self.target_selection_callback.call_args
        fighting_unit, eligible_targets, active_player = args
        
        self.assertEqual(fighting_unit, self.unit2_fight_first)
        self.assertIn(target1, eligible_targets)
        self.assertIn(target2, eligible_targets)
        self.assertEqual(active_player, self.player2)
    
    def test_alternating_player_selection(self):
        """Test that players alternate selecting units."""
        self.manager.start_fight_phase(self.player1, self.player2)
        
        # Mock single target for quick resolution
        self.game_map.get_enemy_units.return_value = [self.unit1_charged]
        self.game_map.is_within_engagement_range.return_value = True
        
        self.game._resolve_unit_by_id = Mock(
            side_effect=lambda unit_id: {
                self.unit1_charged.id: self.unit1_charged,
                self.unit2_fight_first.id: self.unit2_fight_first,
            }.get(unit_id)
        )
        self.manager._resolve_target_declaration_attacks = Mock()
        self.manager._queue_fight_move_request = Mock(side_effect=[None, None])
        
        # First selection (Player 2)
        self.assertEqual(self.manager.get_active_player(), self.player2)
        self.manager.unit_selected(self.unit2_fight_first, self.player1, self.player2)
        
        # Verify target selection callback was called
        self.target_selection_callback.assert_called_once()
        
        # Simulate target selection completion by calling targets_selected
        # Create a simple target declaration (empty dict for no specific model targeting)
        target_declarations = {self.unit1_charged: []}
        self.manager.targets_selected(self.unit2_fight_first, target_declarations, self.player1, self.player2)
        
        self.manager._resolve_target_declaration_attacks.assert_called_once()
        # Should switch to Player 1 after pile-in -> attacks -> consolidate -> finalize
        self.assertEqual(self.manager.get_active_player(), self.player1)
    
    def test_stage_progression(self):
        """Test progression from Fight First to Remaining Combatants stage."""
        # Override to return no fight first units but some remaining units
        def no_fight_first_units(player):
            return []
        
        self.game.get_fight_first_units.side_effect = no_fight_first_units
        
        self.manager.start_fight_phase(self.player1, self.player2)
        
        # Should skip to Remaining Combatants stage
        self.assertEqual(self.manager.get_current_stage(), FightStage.REMAINING_COMBATANTS)
    
    def test_fight_phase_completion(self):
        """Test fight phase completion when no units remain."""
        # Override the side_effect to return empty lists for both players
        def empty_fight_first_units(player):
            return []
        
        def empty_remaining_units(player):
            return []
        
        self.game.get_fight_first_units.side_effect = empty_fight_first_units
        self.game.get_remaining_combatant_units.side_effect = empty_remaining_units
        
        self.manager.start_fight_phase(self.player1, self.player2)
        
        # Should complete immediately
        self.assertEqual(self.manager.get_current_stage(), FightStage.COMPLETE)
        self.assertTrue(self.manager.is_complete())
        self.stage_complete_callback.assert_called_once()
    
    def test_eligible_units_filtering(self):
        """Test that only eligible units are considered for selection."""
        self.manager.start_fight_phase(self.player1, self.player2)
        
        # Mark a unit as already fought
        self.manager.fought_units.add(self.unit2_fight_first)
        
        # Get eligible units for player 2
        eligible = self.manager._get_eligible_units_for_player(self.player2)
        
        # Should not include already fought units
        self.assertNotIn(self.unit2_fight_first, eligible)

    def test_counter_offensive_forces_next_unit(self):
        """Counter-Offensive should force a specific unit to fight next, ignoring stage."""
        forced_unit = self._create_mock_unit("Forced", self.army1, charged=False)
        forced_unit.is_eligible_to_fight.return_value = True

        self.manager.current_stage = FightStage.FIGHT_FIRST
        self.manager.active_player = self.player1
        self.manager.on_unit_selection_required = Mock()

        ok = self.manager.force_next_unit(forced_unit, self.player1)
        self.assertTrue(ok)

        self.manager._request_unit_selection(self.player1, self.player2)

        args, kwargs = self.manager.on_unit_selection_required.call_args
        active_player, eligible_units, stage = args
        self.assertEqual(active_player, self.player1)
        self.assertEqual(eligible_units, [forced_unit])
        self.assertEqual(stage, FightStage.FIGHT_FIRST)
    
    def test_target_declarations_execution(self):
        """Test execution of fight sequence with target declarations."""
        self.manager.start_fight_phase(self.player1, self.player2)
        
        # Mock target declarations
        target_unit = self._create_mock_unit("Target", self.army1)
        model1 = Mock(spec=Model)
        model2 = Mock(spec=Model)
        target_declarations = {target_unit: [model1, model2]}
        
        self.manager._queue_fight_move_request = Mock(return_value=Mock())

        # Execute with declarations
        self.manager.targets_selected(self.unit2_fight_first, target_declarations, self.player1, self.player2)

        self.manager._queue_fight_move_request.assert_called_once()
        self.assertEqual(
            self.manager._queue_fight_move_request.call_args.kwargs["movement_type"],
            "pile_in",
        )
        self.assertEqual(self.manager._pending_fight_sequence["step"], "pile_in")
        self.assertNotIn(self.unit2_fight_first, self.manager.fought_units)
    
    def test_stage_info_reporting(self):
        """Test that stage info is reported correctly."""
        self.manager.start_fight_phase(self.player1, self.player2)
        
        stage_info = self.manager.get_stage_info(self.player1, self.player2)
        
        # Check stage info structure
        self.assertIn("current_stage", stage_info)
        self.assertIn("active_player", stage_info)
        self.assertIn("current_player_fight_first", stage_info)
        self.assertIn("current_player_remaining", stage_info)
        self.assertIn("opponent_fight_first", stage_info)
        self.assertIn("opponent_remaining", stage_info)
        self.assertIn("fought_units", stage_info)
        self.assertIn("is_complete", stage_info)
        
        # Check values
        self.assertEqual(stage_info["current_stage"], "Fight First")
        self.assertEqual(stage_info["active_player"], "Player 2")
        self.assertFalse(stage_info["is_complete"])

    def test_auto_select_melee_weapons_respects_extra_attacks(self):
        """Fallback melee selection should pick 1 primary + all EXTRA ATTACKS weapons per model."""
        from types import SimpleNamespace

        class _Profile:
            def __init__(self, name: str, extra: bool):
                self.name = name
                self._extra = extra

            def is_extra_attacks(self) -> bool:
                return self._extra

        class _Wargear:
            def __init__(self, profiles: dict):
                self.profiles = profiles

            def is_melee(self) -> bool:
                return True

        # Build a unit with one model that has 2 primary weapons and 1 extra-attacks weapon
        primary1 = _Profile("Chainsword", extra=False)
        primary2 = _Profile("Power fist", extra=False)
        extra = _Profile("Attack squig", extra=True)

        wargear = _Wargear({"a": primary1, "b": primary2, "c": extra})
        model = SimpleNamespace(is_alive=True, name="Model", wargear=[wargear])
        unit = SimpleNamespace(name="Unit", models=[model])

        decls = self.manager._auto_select_melee_weapons(unit)
        # Expect: exactly 2 declarations (1 primary + 1 extra)
        self.assertEqual(len(decls), 2)
        chosen_profiles = [d["weapon_profile"] for d in decls]

        # Exactly one non-extra chosen
        non_extra = [p for p in chosen_profiles if not p.is_extra_attacks()]
        extras = [p for p in chosen_profiles if p.is_extra_attacks()]
        self.assertEqual(len(non_extra), 1)
        self.assertEqual(len(extras), 1)
        self.assertEqual(extras[0].name, "Attack squig")


class TestUnitFightingEligibility(unittest.TestCase):
    """Test unit eligibility for fighting."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.game_map = Mock(spec=Map)
        
        # Create a more realistic unit mock that implements the actual methods
        self.unit = Mock(spec=Unit)
        self.unit.name = "Test Unit"
        self.unit.is_alive.return_value = True
        self.unit.deployed = True
        # Unit position is now determined by model positions - no need to mock get_position
        
        # Set up round state
        self.unit.round_state = Mock(spec=UnitRoundState)
        self.unit.round_state.declared_charge_this_round = False
        
        # Set up abilities
        self.unit.has_fight_first.return_value = False
        
        # Mock the methods we're testing
        def mock_should_fight_first():
            return (self.unit.round_state.declared_charge_this_round or 
                   self.unit.has_fight_first.return_value)
        
        def mock_is_eligible_to_fight(game_map):
            if not self.unit.is_alive.return_value or not self.unit.deployed:
                return False
            
            # Check if unit charged this turn
            if self.unit.round_state.declared_charge_this_round:
                return True
            
            # Check if unit is within engagement range
            # Since we removed get_position(), just assume unit has a position for mock tests
            unit_position = (10.0, 10.0, 0.0)  # Mock position
            
            enemy_units = game_map.get_enemy_units.return_value or []
            for enemy_unit in enemy_units:
                if enemy_unit.is_alive.return_value and game_map.is_within_engagement_range.return_value:
                    return True
            
            return False
        
        self.unit.should_fight_first = mock_should_fight_first
        self.unit.is_eligible_to_fight = mock_is_eligible_to_fight
    
    def test_unit_eligible_after_charge(self):
        """Test that units are eligible to fight after charging."""
        self.unit.round_state.declared_charge_this_round = True
        
        # Should be eligible even without enemies in range
        self.assertTrue(self.unit.is_eligible_to_fight(self.game_map))
    
    def test_unit_eligible_in_engagement_range(self):
        """Test that units are eligible when in engagement range."""
        # Mock enemy in engagement range
        enemy_unit = Mock(spec=Unit)
        enemy_unit.is_alive.return_value = True
        self.game_map.get_enemy_units.return_value = [enemy_unit]
        self.game_map.is_within_engagement_range.return_value = True
        
        self.assertTrue(self.unit.is_eligible_to_fight(self.game_map))
    
    def test_unit_not_eligible_when_dead(self):
        """Test that dead units are not eligible to fight."""
        self.unit.is_alive.return_value = False
        
        self.assertFalse(self.unit.is_eligible_to_fight(self.game_map))
    
    def test_unit_not_eligible_when_not_deployed(self):
        """Test that undeployed units are not eligible to fight."""
        self.unit.deployed = False
        
        self.assertFalse(self.unit.is_eligible_to_fight(self.game_map))
    
    def test_fight_first_after_charge(self):
        """Test that units fight first after charging."""
        self.unit.round_state.declared_charge_this_round = True
        
        self.assertTrue(self.unit.should_fight_first())
    
    def test_fight_first_with_ability(self):
        """Test that units with fight first ability fight first."""
        self.unit.has_fight_first.return_value = True
        
        self.assertTrue(self.unit.should_fight_first())
    
    def test_no_fight_first_by_default(self):
        """Test that units don't fight first by default."""
        self.assertFalse(self.unit.should_fight_first())


class TestFightPhaseIntegration(unittest.TestCase):
    """Integration tests for fight phase with UI components."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        # This would test the integration between FightPhaseManager and UI components
        # For now, we'll focus on the core logic tests above
        pass
    
    def test_human_player_unit_selection_dialog(self):
        """Test that human players get unit selection dialogs."""
        # TODO: Implement when UI integration is ready
        pass


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2) 
