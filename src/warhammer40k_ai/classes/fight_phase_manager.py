"""
Fight Phase Manager for Warhammer 40k AI

Manages the proper two-stage fight phase structure with alternating player selection:
1. Fight First Stage - Units that charged or have Fight First abilities
2. Remaining Combatants Stage - All other eligible units

Within each stage, players alternate selecting units to fight, with the non-current player going first.
"""

from typing import List, Optional, Dict, Callable
from enum import Enum
from .unit import Unit
from .model import Model
from .player import Player
from ..utility.calcs import clear_enemy_model_cache
from .game import Game

class FightStage(Enum):
    FIGHT_FIRST = "Fight First"
    REMAINING_COMBATANTS = "Remaining Combatants"
    COMPLETE = "Complete"

class FightPhaseManager:
    """Manages the fight phase with proper alternating player selection."""
    
    def __init__(self, game: 'Game'):
        self.game = game
        self.current_stage = FightStage.FIGHT_FIRST
        self.active_player = None  # Player who needs to select next
        self.fought_units = set()  # Units that have already fought this phase
        self.stage_complete = False
        
        # Callbacks for human player interaction
        self.on_unit_selection_required = None  # Callback when human needs to select unit
        self.on_target_selection_required = None  # Callback when human needs to select targets
        self.on_stage_complete = None  # Callback when stage is complete
        
    def start_fight_phase(self, current_player: Player, opponent_player: Player) -> None:
        """Start the fight phase with proper initialization."""
        print("⚔️ Starting Fight Phase")
        
        # Reset state
        self.fought_units.clear()
        self.current_stage = FightStage.FIGHT_FIRST
        self.stage_complete = False
        
        # In fight phase, the non-current player goes first
        self.active_player = opponent_player
        
        # Start with Fight First stage
        self._start_fight_first_stage(current_player, opponent_player)
    
    def _start_fight_first_stage(self, current_player: Player, opponent_player: Player) -> None:
        """Start the Fight First stage."""
        print("⚔️ Starting Fight First Stage")
        self.current_stage = FightStage.FIGHT_FIRST

        # Get Fight First units for both players with detailed debugging
        current_player_units = self.game.get_fight_first_units(current_player)
        opponent_units = self.game.get_fight_first_units(opponent_player)

        print(f"  Current Player ({current_player.name}): {len(current_player_units)} Fight First units")
        if current_player_units:
            for unit in current_player_units:
                print(f"    - {unit.name} (charged: {getattr(unit.round_state, 'charged_this_round', False)}, fight_first_ability: {unit.has_fight_first()})")

        print(f"  Opponent ({opponent_player.name}): {len(opponent_units)} Fight First units")
        if opponent_units:
            for unit in opponent_units:
                print(f"    - {unit.name} (charged: {getattr(unit.round_state, 'charged_this_round', False)}, fight_first_ability: {unit.has_fight_first()})")

        if not current_player_units and not opponent_units:
            print("📋 No units with Fight First abilities - moving to Remaining Combatants")
            self._start_remaining_combatants_stage(current_player, opponent_player)
            return

        # Start alternating selection with opponent (non-current player)
        self.active_player = opponent_player
        self._request_unit_selection(current_player, opponent_player)
    
    def _start_remaining_combatants_stage(self, current_player: Player, opponent_player: Player) -> None:
        """Start the Remaining Combatants stage."""
        print("⚔️ Starting Remaining Combatants Stage")
        self.current_stage = FightStage.REMAINING_COMBATANTS

        # Get remaining combatant units for both players with detailed debugging
        current_player_units = self.game.get_remaining_combatant_units(current_player)
        opponent_units = self.game.get_remaining_combatant_units(opponent_player)

        print(f"  Current Player ({current_player.name}): {len(current_player_units)} Remaining units")
        if current_player_units:
            for unit in current_player_units:
                print(f"    - {unit.name} (eligible_to_fight: {unit.is_eligible_to_fight(self.game.map)})")

        print(f"  Opponent ({opponent_player.name}): {len(opponent_units)} Remaining units")
        if opponent_units:
            for unit in opponent_units:
                print(f"    - {unit.name} (eligible_to_fight: {unit.is_eligible_to_fight(self.game.map)})")

        if not current_player_units and not opponent_units:
            print("📋 No remaining combatant units - Fight Phase complete")
            self._complete_fight_phase()
            return

        # Start alternating selection with opponent (non-current player)
        self.active_player = opponent_player
        self._request_unit_selection(current_player, opponent_player)
    
    def _request_unit_selection(self, current_player: Player, opponent_player: Player) -> None:
        """Request unit selection from the active player."""
        # Get eligible units for the active player in current stage
        eligible_units = self._get_eligible_units_for_player(self.active_player)
        
        if not eligible_units:
            # Active player has no units - switch to other player
            other_player = opponent_player if self.active_player == current_player else current_player
            other_eligible = self._get_eligible_units_for_player(other_player)
            
            if not other_eligible:
                # No units for either player - stage complete
                self._complete_current_stage(current_player, opponent_player)
                return
            
            # Switch to other player
            self.active_player = other_player
            eligible_units = other_eligible
        
        print(f"🎯 {self.active_player.name} must select a unit to fight ({self.current_stage.value} stage)")
        print(f"   Eligible units: {[unit.name for unit in eligible_units]}")
        
        # Call callback for unit selection
        if self.on_unit_selection_required:
            self.on_unit_selection_required(self.active_player, eligible_units, self.current_stage)
    
    def _get_eligible_units_for_player(self, player: Player) -> List[Unit]:
        """Get eligible units for a player in the current stage."""
        if self.current_stage == FightStage.FIGHT_FIRST:
            all_units = self.game.get_fight_first_units(player)
        elif self.current_stage == FightStage.REMAINING_COMBATANTS:
            all_units = self.game.get_remaining_combatant_units(player)
        else:
            return []
        
        # Filter out units that have already fought
        return [unit for unit in all_units if unit not in self.fought_units and unit.is_alive()]
    
    def unit_selected(self, selected_unit: Unit, current_player: Player, opponent_player: Player) -> None:
        """Handle unit selection from the active player."""
        print(f"⚔️ {self.active_player.name} selected {selected_unit.name} to fight")
        
        # Find eligible targets for this unit
        eligible_targets = self._get_eligible_targets(selected_unit)
        
        if not eligible_targets:
            print(f"❌ {selected_unit.name} has no eligible targets")
            return
        
        # Always show target selection dialog, even for single targets
        # This gives the user a chance to see what's happening and confirm the attack
        print(f"🎯 {selected_unit.name} can fight {len(eligible_targets)} target(s): {[target.name for target in eligible_targets]}")
        self.on_target_selection_required(selected_unit, eligible_targets, self.active_player)
    
    def targets_selected(self, fighting_unit: Unit, target_declarations: Dict[Unit, List['Model']], current_player: Player, opponent_player: Player) -> None:
        """Handle target selection and execute the fight sequence."""
        print(f"⚔️ {fighting_unit.name} will fight with target declarations:")
        for target_unit, models in target_declarations.items():
            print(f"  {len(models)} models attacking {target_unit.name}")
        
        # Execute the complete fight sequence
        ui_callback = getattr(self, 'on_movement_required', None)
        self._execute_fight_sequence_with_declarations(fighting_unit, target_declarations, current_player, opponent_player, ui_callback)
    
    def _get_eligible_targets(self, fighting_unit: Unit) -> List[Unit]:
        """Get all eligible targets for a fighting unit."""
        eligible_targets = []
        
        enemy_units = self.game.map.get_enemy_units(fighting_unit)
        for enemy_unit in enemy_units:
            if enemy_unit.is_alive() and self.game.map.is_within_engagement_range(fighting_unit, enemy_unit):
                eligible_targets.append(enemy_unit)
        
        return eligible_targets
    
    def _execute_fight_sequence(self, fighting_unit: Unit, target_unit: Unit, current_player: Player, opponent_player: Player, ui_callback=None) -> None:
        """Execute the complete fight sequence for a single target."""
        print(f"⚔️ Executing fight sequence: {fighting_unit.name} vs {target_unit.name}")

        # If UI callback is provided, use individual model movement for pile-in and consolidate
        if ui_callback:
            self._execute_fight_sequence_with_ui(fighting_unit, target_unit, current_player, opponent_player, ui_callback)
        else:
            # Fallback to old unit-level methods
            self._execute_fight_sequence_legacy(fighting_unit, target_unit, current_player, opponent_player)

    def _execute_fight_sequence_with_ui(self, fighting_unit: Unit, target_unit: Unit, current_player: Player, opponent_player: Player, ui_callback) -> None:
        """Execute fight sequence using individual model movement UI."""
        print(f"⚔️ Starting UI-based fight sequence: {fighting_unit.name} vs {target_unit.name}")

        # Step 1: Pile-in using Individual Model Movement Dialog
        def on_pile_in_complete(completed: bool):
            print(f"📍 {fighting_unit.name} pile-in completed: {completed}")

            # Step 2: Melee weapon selection
            def on_weapon_selection_complete(weapon_declarations):
                print(f"⚔️ {fighting_unit.name} weapon selection completed: {len(weapon_declarations)} weapons")

                # Step 3: Resolve melee attacks
                self._resolve_melee_attacks(fighting_unit, target_unit, weapon_declarations)

                # Step 4: Consolidate using Individual Model Movement Dialog
                def on_consolidate_complete(completed: bool):
                    print(f"🏃 {fighting_unit.name} consolidate completed: {completed}")

                    # Mark unit as having fought
                    self.fought_units.add(fighting_unit)
                    try:
                        fighting_unit.round_state.fought_this_phase = True
                    except Exception:
                        pass

                    # Switch to other player for next selection
                    self._switch_active_player(current_player, opponent_player)

                # Show consolidate dialog
                ui_callback('consolidate', fighting_unit, on_consolidate_complete)

            # Show melee weapon selection dialog
            if hasattr(self, 'on_weapon_selection_required') and self.on_weapon_selection_required:
                self.on_weapon_selection_required(fighting_unit, target_unit, on_weapon_selection_complete)
            else:
                # Fallback: auto-select all melee weapons
                print("⚠️ No weapon selection callback - auto-selecting all melee weapons")
                weapon_declarations = self._auto_select_melee_weapons(fighting_unit)
                on_weapon_selection_complete(weapon_declarations)

        # Show pile-in dialog
        ui_callback('pile_in', fighting_unit, on_pile_in_complete)

    def _execute_fight_sequence_legacy(self, fighting_unit: Unit, target_unit: Unit, current_player: Player, opponent_player: Player) -> None:
        """Execute fight sequence using legacy unit-level methods."""
        print(f"📍 {fighting_unit.name} piles in...")
        fighting_unit.pile_in_towards_enemies(self.game.map)

        # Step 2: Make melee attacks
        print(f"⚔️ {fighting_unit.name} makes melee attacks against {target_unit.name}")
        # TODO: Implement proper melee attack resolution

        # Step 3: Consolidate
        print(f"🏃 {fighting_unit.name} consolidates...")
        fighting_unit.consolidate_towards_enemies(self.game.map)

        # Mark unit as having fought
        self.fought_units.add(fighting_unit)
        try:
            fighting_unit.round_state.fought_this_phase = True
        except Exception:
            pass

        # Switch to other player for next selection
        self._switch_active_player(current_player, opponent_player)
    
    def _execute_fight_sequence_with_declarations(self, fighting_unit: Unit, target_declarations: Dict[Unit, List['Model']], current_player: Player, opponent_player: Player, ui_callback=None) -> None:
        """Execute the complete fight sequence with target declarations."""
        print(f"⚔️ Executing fight sequence with declarations: {fighting_unit.name}")

        # If UI callback is provided, use individual model movement for pile-in and consolidate
        if ui_callback:
            self._execute_fight_sequence_with_declarations_ui(fighting_unit, target_declarations, current_player, opponent_player, ui_callback)
        else:
            # Fallback to old unit-level methods
            self._execute_fight_sequence_with_declarations_legacy(fighting_unit, target_declarations, current_player, opponent_player)

    def _execute_fight_sequence_with_declarations_ui(self, fighting_unit: Unit, target_declarations: Dict[Unit, List['Model']], current_player: Player, opponent_player: Player, ui_callback) -> None:
        """Execute fight sequence with declarations using individual model movement UI."""
        print(f"⚔️ Starting UI-based fight sequence with declarations: {fighting_unit.name}")

        # Step 1: Pile-in using Individual Model Movement Dialog
        def on_pile_in_complete(completed: bool):
            print(f"📍 {fighting_unit.name} pile-in completed: {completed}")

            # Step 2: Make melee attacks based on declarations
            print(f"⚔️ {fighting_unit.name} makes melee attacks")
            for target_unit, attacking_models in target_declarations.items():
                print(f"  {len(attacking_models)} models attacking {target_unit.name}")
                # TODO: Implement proper melee attack resolution with model-specific targeting

            # Step 3: Consolidate using Individual Model Movement Dialog
            def on_consolidate_complete(completed: bool):
                print(f"🏃 {fighting_unit.name} consolidate completed: {completed}")

                # Mark unit as having fought
                self.fought_units.add(fighting_unit)
                try:
                    fighting_unit.round_state.fought_this_phase = True
                except Exception:
                    pass

                # Switch to other player for next selection
                self._switch_active_player(current_player, opponent_player)

            # Show consolidate dialog
            ui_callback('consolidate', fighting_unit, on_consolidate_complete)

        # Show pile-in dialog
        ui_callback('pile_in', fighting_unit, on_pile_in_complete)

    def _execute_fight_sequence_with_declarations_legacy(self, fighting_unit: Unit, target_declarations: Dict[Unit, List['Model']], current_player: Player, opponent_player: Player) -> None:
        """Execute fight sequence with declarations using legacy unit-level methods."""
        # Step 1: Pile-in
        print(f"📍 {fighting_unit.name} piles in...")
        fighting_unit.pile_in_towards_enemies(self.game.map)

        # Step 2: Make melee attacks based on declarations
        print(f"⚔️ {fighting_unit.name} makes melee attacks")
        for target_unit, attacking_models in target_declarations.items():
            print(f"  {len(attacking_models)} models attacking {target_unit.name}")
            # TODO: Implement proper melee attack resolution with model-specific targeting

        # Step 3: Consolidate
        print(f"🏃 {fighting_unit.name} consolidates...")
        fighting_unit.consolidate_towards_enemies(self.game.map)
        
        # Mark unit as having fought
        self.fought_units.add(fighting_unit)
        try:
            fighting_unit.round_state.fought_this_phase = True
        except Exception:
            pass
        
        # Switch to other player for next selection
        self._switch_active_player(current_player, opponent_player)
    
    def _switch_active_player(self, current_player: Player, opponent_player: Player) -> None:
        """Switch the active player and continue the fight phase."""
        # Switch active player
        self.active_player = opponent_player if self.active_player == current_player else current_player

        # Clear enemy model cache when switching players since enemy positions may have changed
        clear_enemy_model_cache(id(self.game.map))
        print(f"⚔️ Fight phase player switched to {self.active_player.name} - cleared enemy model cache")

        # Request next unit selection
        self._request_unit_selection(current_player, opponent_player)
    
    def _complete_current_stage(self, current_player: Player, opponent_player: Player) -> None:
        """Complete the current stage and move to next or finish."""
        if self.current_stage == FightStage.FIGHT_FIRST:
            self._start_remaining_combatants_stage(current_player, opponent_player)
        elif self.current_stage == FightStage.REMAINING_COMBATANTS:
            self._complete_fight_phase()
    
    def _complete_fight_phase(self) -> None:
        """Complete the entire fight phase."""
        print("✅ Fight Phase complete")
        self.current_stage = FightStage.COMPLETE
        self.stage_complete = True
        
        if self.on_stage_complete:
            self.on_stage_complete()
    
    def get_current_stage(self) -> FightStage:
        """Get the current fight stage."""
        return self.current_stage
    
    def get_active_player(self) -> Optional[Player]:
        """Get the player who needs to make the next selection."""
        return self.active_player
    
    def is_complete(self) -> bool:
        """Check if the fight phase is complete."""
        return self.current_stage == FightStage.COMPLETE

    def _resolve_melee_attacks(self, attacking_unit: Unit, target_unit: Unit, weapon_declarations: List) -> None:
        """Resolve melee attacks with detailed output like shooting."""
        print(f"⚔️ Resolving melee attacks: {attacking_unit.name} vs {target_unit.name}")

        # Begin attack resolution window so attached leaders don't separate mid-melee sequence.
        try:
            if hasattr(target_unit, "begin_attack_resolution"):
                target_unit.begin_attack_resolution()
        except Exception:
            pass

        for declaration in weapon_declarations:
            model = declaration.get('model')
            weapon_profile = declaration.get('weapon_profile')

            if not model or not weapon_profile:
                continue

            print(f"🗡️ {model.name} attacks with {weapon_profile.name}")

            # Get number of attacks
            attacks = weapon_profile.attacks
            if isinstance(attacks, str):
                # Handle dice notation like "D6" or "2D6"
                from ..utility.dice import get_roll
                attacks = get_roll(attacks)

            print(f"🎲 Number of attacks: {attacks}")

            # Roll to hit
            hit_rolls = []
            hits = 0
            for i in range(attacks):
                from ..utility.dice import get_roll
                roll = get_roll("1D6")
                hit_rolls.append(roll)
                if roll >= weapon_profile.weapon_skill:
                    hits += 1

            print(f"🎯 Hit rolls: {hit_rolls} (WS {weapon_profile.weapon_skill}+) - {hits} hits")

            if hits == 0:
                print("❌ No hits - attack sequence ends")
                continue

            # Roll to wound
            wound_rolls = []
            wounds = 0
            for i in range(hits):
                from ..utility.dice import get_roll
                roll = get_roll("1D6")
                wound_rolls.append(roll)
                # Simplified wound calculation - would need proper S vs T comparison
                wound_target = 4  # Placeholder
                if roll >= wound_target:
                    wounds += 1

            print(f"🩸 Wound rolls: {wound_rolls} (need {wound_target}+) - {wounds} wounds")

            if wounds == 0:
                print("❌ No wounds - attack sequence ends")
                continue

            # Apply damage
            damage_per_wound = weapon_profile.damage
            if isinstance(damage_per_wound, str):
                from ..utility.dice import get_roll
                damage_per_wound = get_roll(damage_per_wound)

            total_damage = wounds * damage_per_wound
            print(f"💥 {wounds} wounds × {damage_per_wound} damage = {total_damage} total damage")

            # Apply damage to target unit
            target_unit.take_damage(total_damage)
            print(f"🎯 {target_unit.name} takes {total_damage} damage")

        # End attack resolution window for this target after this unit has finished its melee attacks.
        try:
            game_map = getattr(self.game, "map", None)
            if hasattr(target_unit, "end_attack_resolution"):
                target_unit.end_attack_resolution(game_map=game_map)
        except Exception:
            pass

    def _auto_select_melee_weapons(self, unit: Unit) -> List:
        """Auto-select melee weapons for a unit (fallback).

        Respects the EXTRA ATTACKS rule:
        - Select ONE melee weapon that does NOT have EXTRA ATTACKS (if any)
        - Also select ALL melee weapons that DO have EXTRA ATTACKS
        """
        weapon_declarations = []

        for model in unit.models:
            if not model.is_alive:
                continue

            # Collect melee profiles by category
            primary_candidates = []  # (profile, profile_name)
            extra_attack_profiles = []  # (profile, profile_name)

            for wargear in getattr(model, "wargear", []) or []:
                try:
                    if not (hasattr(wargear, "profiles") and wargear.is_melee()):
                        continue
                except Exception:
                    continue
                for profile_name, profile in getattr(wargear, "profiles", {}).items():
                    try:
                        if getattr(profile, "is_extra_attacks", lambda: False)():
                            extra_attack_profiles.append((profile, profile_name))
                        else:
                            primary_candidates.append((profile, profile_name))
                    except Exception:
                        primary_candidates.append((profile, profile_name))

            # Pick one primary weapon deterministically (first listed)
            if primary_candidates:
                profile, profile_name = primary_candidates[0]
                weapon_declarations.append({
                    'model': model,
                    'weapon_profile': profile,
                    'profile_name': profile_name
                })

            # Always include all extra attacks profiles
            for profile, profile_name in extra_attack_profiles:
                weapon_declarations.append({
                    'model': model,
                    'weapon_profile': profile,
                    'profile_name': profile_name
                })

        print(f"🗡️ Auto-selected {len(weapon_declarations)} melee weapons for {unit.name}")
        return weapon_declarations
    
    def get_stage_info(self, current_player: Player, opponent_player: Player) -> Dict:
        """Get information about the current stage for UI display."""
        current_fight_first = self.game.get_fight_first_units(current_player)
        current_remaining = self.game.get_remaining_combatant_units(current_player)
        opponent_fight_first = self.game.get_fight_first_units(opponent_player)
        opponent_remaining = self.game.get_remaining_combatant_units(opponent_player)
        
        # Filter out units that have already fought
        current_fight_first = [u for u in current_fight_first if u not in self.fought_units and u.is_alive()]
        current_remaining = [u for u in current_remaining if u not in self.fought_units and u.is_alive()]
        opponent_fight_first = [u for u in opponent_fight_first if u not in self.fought_units and u.is_alive()]
        opponent_remaining = [u for u in opponent_remaining if u not in self.fought_units and u.is_alive()]
        
        return {
            "current_stage": self.current_stage.value,
            "active_player": self.active_player.name if self.active_player else None,
            "current_player_fight_first": len(current_fight_first),
            "current_player_remaining": len(current_remaining),
            "opponent_fight_first": len(opponent_fight_first),
            "opponent_remaining": len(opponent_remaining),
            "fought_units": len(self.fought_units),
            "is_complete": self.is_complete()
        } 