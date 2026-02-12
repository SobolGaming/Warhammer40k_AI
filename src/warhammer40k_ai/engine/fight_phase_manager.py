"""
Fight Phase Manager for Warhammer 40k.

Manages the proper two-stage fight phase structure with alternating player selection:
1. Fight First Stage - Units that charged or have Fight First abilities
2. Remaining Combatants Stage - All other eligible units

Within each stage, players alternate selecting units to fight, with the non-current player going first.
"""

from typing import List, Optional, Dict, Callable
from enum import Enum
from ..units.unit import Unit
from ..units.model import Model
from ..roster.player import Player
from ..utility.calcs import clear_enemy_model_cache
from ..utility.entity_ids import get_entity_id
from .game import Game
import logging
logger = logging.getLogger(__name__)

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
        # Counter-Offensive support: force a specific unit to fight next.
        self._forced_next_unit = None
        self._forced_next_player = None
        # Cache fight phase players for refresh requests.
        self._current_player = None
        self._opponent_player = None

    def _canonical_unit_for_fight(self, unit: Unit) -> Unit:
        """
        Attached Units are treated as one unit in 10e.

        Internally, this project keeps Leaders as separate Unit objects while attached, so we must
        canonicalize any attached Leader selection to the bodyguard/root unit for fight sequencing.
        """
        try:
            root = unit.get_attached_unit_root()
            # Defensive: tests often use lightweight mocks that may implement the method but
            # return another Mock (not a real Unit). In that case, keep the original unit.
            if root is None:
                return unit
            models = getattr(root, "models", None)
            if not isinstance(models, list):
                return unit
            return root
        except Exception:
            return unit

    def _as_attached_view(self, unit: Unit) -> Unit:
        """
        Return a proxy unit whose `.models` includes all attached members (bodyguard + leaders),
        so weapon selection and melee resolution include leader models without treating them as
        separate selectable units.
        """
        try:
            from ..units.attached_unit import AttachedUnitView
        except Exception:
            AttachedUnitView = None
        root = self._canonical_unit_for_fight(unit)
        if AttachedUnitView is None:
            return root
        try:
            members = list(root.get_attached_unit_members())
            if members and len(members) > 1:
                return AttachedUnitView(root)
        except Exception:
            pass
        return root

        
        # Callbacks for human player interaction
        self.on_unit_selection_required = None  # Callback when human needs to select unit
        self.on_target_selection_required = None  # Callback when human needs to select targets
        self.on_stage_complete = None  # Callback when stage is complete
        
    def start_fight_phase(self, current_player: Player, opponent_player: Player) -> None:
        """Start the fight phase with proper initialization."""
        logger.info("Starting Fight Phase")
        
        # Reset state
        self.fought_units.clear()
        self.current_stage = FightStage.FIGHT_FIRST
        self.stage_complete = False
        self._forced_next_unit = None
        self._forced_next_player = None
        self._current_player = current_player
        self._opponent_player = opponent_player
        
        # In fight phase, the non-current player goes first
        self.active_player = opponent_player
        
        # Start with Fight First stage
        self._start_fight_first_stage(current_player, opponent_player)
    
    def _start_fight_first_stage(self, current_player: Player, opponent_player: Player) -> None:
        """Start the Fight First stage."""
        logger.info("Starting Fight First Stage")
        self.current_stage = FightStage.FIGHT_FIRST

        # Get Fight First units for both players with detailed debugging
        current_player_units = self.game.get_fight_first_units(current_player)
        opponent_units = self.game.get_fight_first_units(opponent_player)

        logger.info(f"Current Player ({current_player.name}): {len(current_player_units)} Fight First units")
        if current_player_units:
            for unit in current_player_units:
                logger.info(f"  - {unit.name} (charged: {getattr(unit.round_state, 'charged_this_round', False)}, "
                    f"fight_first_ability: {unit.has_fight_first()})")

        logger.info(f"Opponent ({opponent_player.name}): {len(opponent_units)} Fight First units")
        if opponent_units:
            for unit in opponent_units:
                logger.info(f"  - {unit.name} (charged: {getattr(unit.round_state, 'charged_this_round', False)}, "
                    f"fight_first_ability: {unit.has_fight_first()})")

        if not current_player_units and not opponent_units:
            logger.info("No units with Fight First abilities - moving to Remaining Combatants")
            self._start_remaining_combatants_stage(current_player, opponent_player)
            return

        # Start alternating selection with opponent (non-current player)
        self.active_player = opponent_player
        self._request_unit_selection(current_player, opponent_player)
    
    def _start_remaining_combatants_stage(self, current_player: Player, opponent_player: Player) -> None:
        """Start the Remaining Combatants stage."""
        logger.info("Starting Remaining Combatants Stage")
        self.current_stage = FightStage.REMAINING_COMBATANTS

        # Get remaining combatant units for both players with detailed debugging
        current_player_units = self.game.get_remaining_combatant_units(current_player)
        opponent_units = self.game.get_remaining_combatant_units(opponent_player)

        logger.info(f"Current Player ({current_player.name}): {len(current_player_units)} Remaining units")
        if current_player_units:
            for unit in current_player_units:
                logger.info(f"  - {unit.name} (eligible_to_fight: {unit.is_eligible_to_fight(self.game.map)})")

        logger.info(f"Opponent ({opponent_player.name}): {len(opponent_units)} Remaining units")
        if opponent_units:
            for unit in opponent_units:
                logger.info(f"  - {unit.name} (eligible_to_fight: {unit.is_eligible_to_fight(self.game.map)})")

        if not current_player_units and not opponent_units:
            logger.info("No remaining combatant units - Fight Phase complete")
            self._complete_fight_phase()
            return

        # Start alternating selection with opponent (non-current player)
        self.active_player = opponent_player
        self._request_unit_selection(current_player, opponent_player)
    
    def _request_unit_selection(self, current_player: Player, opponent_player: Player) -> None:
        """Request unit selection from the active player."""
        # Counter-Offensive: force a specific unit to fight next (ignore stage).
        try:
            if self._forced_next_unit is not None and self._forced_next_player is not None:
                self.active_player = self._forced_next_player
                forced = self._canonical_unit_for_fight(self._forced_next_unit)
                if self._is_forced_unit_valid(forced):
                    eligible_units = [forced]
                    if self.on_unit_selection_required:
                        self.on_unit_selection_required(self.active_player, eligible_units, self.current_stage)
                    return
                self._forced_next_unit = None
                self._forced_next_player = None
        except Exception:
            pass
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
        
        logger.info(f"{self.active_player.name} must select a unit to fight ({self.current_stage.value} stage)")
        logger.info(f"Eligible units: {[unit.name for unit in eligible_units]}")
        
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

        # Attached units: collapse Leaders into their bodyguard/root unit and deduplicate.
        roots: list[Unit] = []
        seen = set()
        for u in list(all_units or []):
            try:
                root = self._canonical_unit_for_fight(u)
            except Exception:
                root = u
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid in seen:
                continue
            seen.add(rid)
            try:
                if root in self.fought_units:
                    continue
            except Exception:
                pass
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue
            roots.append(root)
        return roots

    def _is_forced_unit_valid(self, unit: Unit) -> bool:
        if unit is None:
            return False
        try:
            if unit in self.fought_units:
                return False
        except Exception:
            pass
        try:
            if not unit.is_alive():
                return False
        except Exception:
            pass
        try:
            if not unit.is_eligible_to_fight(self.game.map):
                return False
        except Exception:
            pass
        return True

    def force_next_unit(self, unit: Unit, player: Player) -> bool:
        """Force a specific unit to fight next (Counter-Offensive)."""
        if unit is None or player is None:
            return False
        unit = self._canonical_unit_for_fight(unit)
        try:
            if unit.get_parent_army().player is not player:
                return False
        except Exception:
            pass
        if not self._is_forced_unit_valid(unit):
            return False
        self._forced_next_unit = unit
        self._forced_next_player = player
        return True

    def finalize_unit_fight(self, fighting_unit: Unit, current_player: Player, opponent_player: Player) -> None:
        """Finalize a unit's fight sequence and advance turn order."""
        fighting_unit = self._canonical_unit_for_fight(fighting_unit)
        # Mark unit as having fought
        self.fought_units.add(fighting_unit)
        try:
            fighting_unit.round_state.fought_this_phase = True
        except Exception:
            pass
        try:
            fighting_unit.clear_martial_katah_choice()
        except Exception:
            pass
        try:
            if hasattr(fighting_unit, "clear_fight_within_3_active"):
                fighting_unit.clear_fight_within_3_active()
        except Exception:
            pass
        try:
            if hasattr(fighting_unit, "clear_selected_to_action_reroll_choice"):
                fighting_unit.clear_selected_to_action_reroll_choice(action="fight")
        except Exception:
            pass
        # Publish event for reaction stratagems (e.g. Counter-Offensive)
        try:
            if hasattr(self.game, "event_system"):
                self.game.event_system.publish(
                    "fight_sequence_complete",
                    unit=fighting_unit,
                    player=self.active_player,
                    stage=self.current_stage,
                )
        except Exception:
            pass
        # Switch to other player for next selection
        self._switch_active_player(current_player, opponent_player)
    
    def unit_selected(self, selected_unit: Unit, current_player: Player, opponent_player: Player) -> None:
        """Handle unit selection from the active player."""
        selected_unit = self._canonical_unit_for_fight(selected_unit)
        try:
            if self._forced_next_unit is not None and selected_unit is self._forced_next_unit:
                self._forced_next_unit = None
                self._forced_next_player = None
        except Exception:
            pass
        logger.info(f"{self.active_player.name} selected {selected_unit.name} to fight")

        # Publish an event so reaction stratagems (e.g. EPIC CHALLENGE) can open a window.
        try:
            es = getattr(getattr(self.game, "event_system", None), "publish", None)
            if callable(es):
                self.game.event_system.publish(
                    "fight_unit_selected",
                    unit=selected_unit,
                    selecting_player=self.active_player,
                    stage=self.current_stage,
                )
        except Exception:
            pass
        
        # Find eligible targets for this unit
        eligible_targets = self._get_eligible_targets(selected_unit)
        
        if not eligible_targets:
            logger.info(f"{selected_unit.name} has no eligible targets")
            try:
                if hasattr(selected_unit, "clear_selected_to_action_reroll_choice"):
                    selected_unit.clear_selected_to_action_reroll_choice(action="fight")
            except Exception:
                pass
            return
        
        # Always show target selection dialog, even for single targets
        # This gives the user a chance to see what's happening and confirm the attack
        logger.info(f"{selected_unit.name} can fight {len(eligible_targets)} target(s): {[target.name for target in eligible_targets]}")
        self.on_target_selection_required(selected_unit, eligible_targets, self.active_player)
    
    def targets_selected(self, fighting_unit: Unit, target_declarations: Dict[Unit, List['Model']], current_player: Player, opponent_player: Player) -> None:
        """Handle target selection and execute the fight sequence."""
        logger.info(f"{fighting_unit.name} will fight with target declarations:")
        for target_unit, models in target_declarations.items():
            logger.info(f"  {len(models)} models attacking {target_unit.name}")

        try:
            fighting_unit.round_state.last_fight_targets = list(target_declarations.keys())
        except Exception:
            try:
                setattr(fighting_unit, "_last_fight_targets", list(target_declarations.keys()))
            except Exception:
                pass

        try:
            if hasattr(self.game, "event_system"):
                self.game.event_system.publish(
                    "fight_targets_selected",
                    attacking_unit=fighting_unit,
                    target_units=list(target_declarations.keys()),
                )
        except Exception:
            pass
        
        # Execute the complete fight sequence
        ui_callback = getattr(self, 'on_movement_required', None)
        self._execute_fight_sequence_with_declarations(fighting_unit, target_declarations, current_player, opponent_player, ui_callback)
        try:
            if hasattr(fighting_unit, "_clear_formless_horror_allowed"):
                fighting_unit._clear_formless_horror_allowed()
        except Exception:
            pass
    
    def _get_eligible_targets(self, fighting_unit: Unit) -> List[Unit]:
        """Get all eligible targets for a fighting unit."""
        eligible_targets = []

        def _suffering_and_sacrifice_active(unit: Unit) -> bool:
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("suffering_and_sacrifice_active")):
                return False
            expires_phase = str(sr.get("suffering_and_sacrifice_expires_phase", "") or "").strip().upper()
            if expires_phase and expires_phase != "FIGHT_PHASE":
                return False
            try:
                marker_turn = int(sr.get("suffering_and_sacrifice_turn", 0) or 0)
            except Exception:
                marker_turn = 0
            try:
                current_turn = int(getattr(self.game, "turn", 0) or 0)
            except Exception:
                current_turn = 0
            if marker_turn and current_turn and marker_turn != current_turn:
                return False
            return True
        
        enemy_units = self.game.map.get_enemy_units(fighting_unit)
        seen = set()
        for enemy_unit in list(enemy_units or []):
            # Treat enemy attached units as one target (root unit)
            try:
                enemy_root = self._canonical_unit_for_fight(enemy_unit)
            except Exception:
                enemy_root = enemy_unit
            if enemy_root is None:
                continue
            rid = get_entity_id(enemy_root)
            if rid in seen:
                continue
            seen.add(rid)
            try:
                if enemy_root.is_alive() and self.game.map.is_within_engagement_range(fighting_unit, enemy_root):
                    # AIRCRAFT fight restrictions: only FLY units can fight AIRCRAFT, and AIRCRAFT can only fight FLY.
                    try:
                        if bool(getattr(enemy_root, "is_aircraft", False)) and not bool(getattr(fighting_unit, "is_flying", False)):
                            continue
                        if bool(getattr(fighting_unit, "is_aircraft", False)) and not bool(getattr(enemy_root, "is_flying", False)):
                            continue
                    except Exception:
                        pass
                    try:
                        if hasattr(fighting_unit, "_formless_horror_target_blocked"):
                            blocked = fighting_unit._formless_horror_target_blocked(enemy_root, game=self.game)
                            if isinstance(blocked, bool) and blocked:
                                continue
                    except Exception:
                        pass
                    reason = None
                    try:
                        if hasattr(fighting_unit, "_sensational_performance_restriction_reason"):
                            reason = fighting_unit._sensational_performance_restriction_reason(enemy_root, self.game)
                    except Exception:
                        reason = None
                    if isinstance(reason, str) and reason:
                        continue
                    eligible_targets.append(enemy_root)
            except Exception:
                continue

        forced_targets = [u for u in list(eligible_targets or []) if _suffering_and_sacrifice_active(u)]
        if forced_targets:
            return forced_targets
        return eligible_targets
    
    def _execute_fight_sequence(self, fighting_unit: Unit, target_unit: Unit, current_player: Player, opponent_player: Player, ui_callback=None) -> None:
        """Execute the complete fight sequence for a single target."""
        logger.info(f"Executing fight sequence: {fighting_unit.name} vs {target_unit.name}")

        # If UI callback is provided, use individual model movement for pile-in and consolidate
        if ui_callback:
            self._execute_fight_sequence_with_ui(fighting_unit, target_unit, current_player, opponent_player, ui_callback)
            return
        logger.warning("WARN: Fight sequence requires UI callback; legacy fight flow removed.")
        return

    def _execute_fight_sequence_with_ui(self, fighting_unit: Unit, target_unit: Unit, current_player: Player, opponent_player: Player, ui_callback) -> None:
        """Execute fight sequence using individual model movement UI."""
        fighting_unit = self._canonical_unit_for_fight(fighting_unit)
        target_unit = self._canonical_unit_for_fight(target_unit)
        logger.info(f"Starting UI-based fight sequence: {fighting_unit.name} vs {target_unit.name}")

        # Step 1: Pile-in using Individual Model Movement Dialog
        def on_pile_in_complete(completed: bool):
            logger.info(f"{fighting_unit.name} pile-in completed: {completed}")

            try:
                if completed and hasattr(fighting_unit, "pile_in_towards_enemies"):
                    fighting_unit.pile_in_towards_enemies(getattr(self.game, "map", None))
            except Exception:
                pass

            # Step 2: Melee weapon selection
            def on_weapon_selection_complete(weapon_declarations):
                logger.info(f"{fighting_unit.name} weapon selection completed: {len(weapon_declarations)} weapons")

                # Step 3: Resolve melee attacks
                # Use attached view so leader models fight as part of the attached unit
                attack_summary = self._resolve_melee_attacks(self._as_attached_view(fighting_unit), target_unit, weapon_declarations)
                try:
                    setattr(
                        fighting_unit,
                        "_gift_of_chaos_hit_models_by_target_psychic",
                        dict(attack_summary.get("hit_models_by_target_psychic") or {}),
                    )
                except Exception:
                    pass
                self.game._maybe_trigger_daemonic_poisons(
                    attacker_unit=self._as_attached_view(fighting_unit),
                    hits_by_target=attack_summary.get("hits_by_target"),
                    hit_models_by_target=attack_summary.get("hit_models_by_target"),
                    phase="fight",
                )
                try:
                    if hasattr(self.game, "event_system"):
                        self.game.event_system.publish(
                            "fight_attacks_resolved",
                            unit=fighting_unit,
                            target_unit=target_unit,
                            hits_by_target=attack_summary.get("hits_by_target"),
                            hit_models_by_target=attack_summary.get("hit_models_by_target"),
                            hit_models_by_target_psychic=attack_summary.get("hit_models_by_target_psychic"),
                        )
                except Exception:
                    pass

                # Step 4: Consolidate using Individual Model Movement Dialog
                def on_consolidate_complete(completed: bool):
                    logger.info(f"{fighting_unit.name} consolidate completed: {completed}")

                    try:
                        if completed and hasattr(fighting_unit, "consolidate_towards_enemies"):
                            fighting_unit.consolidate_towards_enemies(getattr(self.game, "map", None))
                    except Exception:
                        pass

                    # Mark unit as having fought
                    self.finalize_unit_fight(fighting_unit, current_player, opponent_player)

                # Show consolidate dialog
                ui_callback('consolidate', fighting_unit, on_consolidate_complete)

            # Show melee weapon selection dialog
            if hasattr(self, 'on_weapon_selection_required') and self.on_weapon_selection_required:
                self.on_weapon_selection_required(self._as_attached_view(fighting_unit), target_unit, on_weapon_selection_complete)
            else:
                logger.warning("WARN: Weapon selection callback required; cannot auto-select melee weapons.")


        # Show pile-in dialog
        ui_callback('pile_in', fighting_unit, on_pile_in_complete)

    def _execute_fight_sequence_with_declarations(self, fighting_unit: Unit, target_declarations: Dict[Unit, List['Model']], current_player: Player, opponent_player: Player, ui_callback=None) -> None:
        """Execute the complete fight sequence with target declarations."""
        logger.info(f"Executing fight sequence with declarations: {fighting_unit.name}")

        # If UI callback is provided, use individual model movement for pile-in and consolidate
        if ui_callback:
            self._execute_fight_sequence_with_declarations_ui(fighting_unit, target_declarations, current_player, opponent_player, ui_callback)
            return
        try:
            if hasattr(fighting_unit, "pile_in_towards_enemies"):
                fighting_unit.pile_in_towards_enemies(getattr(self.game, "map", None))
        except Exception:
            pass
        try:
            auto_decls = self._auto_select_melee_weapons(self._as_attached_view(fighting_unit))
        except Exception:
            auto_decls = []
        hits_by_target_total = {}
        hit_models_by_target_total = {}
        hit_models_by_target_psychic_total = {}
        for target_unit, attacking_models in target_declarations.items():
            attack_summary = {}
            try:
                decls = list(auto_decls or [])
                if attacking_models:
                    decls = [d for d in decls if d.get("model") in attacking_models]
                attack_summary = self._resolve_melee_attacks(self._as_attached_view(fighting_unit), target_unit, decls)
                for unit, hits in (attack_summary.get("hits_by_target") or {}).items():
                    hits_by_target_total[unit] = int(hits_by_target_total.get(unit, 0) or 0) + int(hits or 0)
                for unit, models in (attack_summary.get("hit_models_by_target") or {}).items():
                    if unit not in hit_models_by_target_total:
                        hit_models_by_target_total[unit] = set()
                    try:
                        hit_models_by_target_total[unit].update(set(models or []))
                    except Exception:
                        pass
                for unit, models in (attack_summary.get("hit_models_by_target_psychic") or {}).items():
                    if unit not in hit_models_by_target_psychic_total:
                        hit_models_by_target_psychic_total[unit] = set()
                    try:
                        hit_models_by_target_psychic_total[unit].update(set(models or []))
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if hasattr(self.game, "event_system"):
                    self.game.event_system.publish(
                        "fight_attacks_resolved",
                        unit=fighting_unit,
                        target_unit=target_unit,
                        hits_by_target=attack_summary.get("hits_by_target"),
                        hit_models_by_target=attack_summary.get("hit_models_by_target"),
                        hit_models_by_target_psychic=attack_summary.get("hit_models_by_target_psychic"),
                    )
            except Exception:
                pass
        if hits_by_target_total:
            self.game._maybe_trigger_daemonic_poisons(
                attacker_unit=self._as_attached_view(fighting_unit),
                hits_by_target=hits_by_target_total,
                hit_models_by_target=hit_models_by_target_total,
                phase="fight",
            )
        try:
            setattr(
                fighting_unit,
                "_gift_of_chaos_hit_models_by_target_psychic",
                dict(hit_models_by_target_psychic_total or {}),
            )
        except Exception:
            pass
        try:
            if hasattr(fighting_unit, "consolidate_towards_enemies"):
                fighting_unit.consolidate_towards_enemies(getattr(self.game, "map", None))
        except Exception:
            pass
        self.finalize_unit_fight(fighting_unit, current_player, opponent_player)
        return

    def _execute_fight_sequence_with_declarations_ui(self, fighting_unit: Unit, target_declarations: Dict[Unit, List['Model']], current_player: Player, opponent_player: Player, ui_callback) -> None:
        """Execute fight sequence with declarations using individual model movement UI."""
        logger.info(f"Starting UI-based fight sequence with declarations: {fighting_unit.name}")

        # Step 1: Pile-in using Individual Model Movement Dialog
        def on_pile_in_complete(completed: bool):
            logger.info(f"{fighting_unit.name} pile-in completed: {completed}")

            try:
                if completed and hasattr(fighting_unit, "pile_in_towards_enemies"):
                    fighting_unit.pile_in_towards_enemies(getattr(self.game, "map", None))
            except Exception:
                pass

            # Step 2: Make melee attacks based on declarations
            logger.info(f"{fighting_unit.name} makes melee attacks")
            auto_decls = self._auto_select_melee_weapons(self._as_attached_view(fighting_unit))
            hits_by_target_total = {}
            hit_models_by_target_total = {}
            hit_models_by_target_psychic_total = {}
            for target_unit, attacking_models in target_declarations.items():
                logger.info(f"  {len(attacking_models)} models attacking {target_unit.name}")
                decls = list(auto_decls or [])
                if attacking_models:
                    decls = [d for d in decls if d.get("model") in attacking_models]
                attack_summary = self._resolve_melee_attacks(self._as_attached_view(fighting_unit), target_unit, decls)
                for unit, hits in (attack_summary.get("hits_by_target") or {}).items():
                    hits_by_target_total[unit] = int(hits_by_target_total.get(unit, 0) or 0) + int(hits or 0)
                for unit, models in (attack_summary.get("hit_models_by_target") or {}).items():
                    if unit not in hit_models_by_target_total:
                        hit_models_by_target_total[unit] = set()
                    try:
                        hit_models_by_target_total[unit].update(set(models or []))
                    except Exception:
                        pass
                for unit, models in (attack_summary.get("hit_models_by_target_psychic") or {}).items():
                    if unit not in hit_models_by_target_psychic_total:
                        hit_models_by_target_psychic_total[unit] = set()
                    try:
                        hit_models_by_target_psychic_total[unit].update(set(models or []))
                    except Exception:
                        pass
            if hits_by_target_total:
                self.game._maybe_trigger_daemonic_poisons(
                    attacker_unit=self._as_attached_view(fighting_unit),
                    hits_by_target=hits_by_target_total,
                    hit_models_by_target=hit_models_by_target_total,
                    phase="fight",
                )
            try:
                setattr(
                    fighting_unit,
                    "_gift_of_chaos_hit_models_by_target_psychic",
                    dict(hit_models_by_target_psychic_total or {}),
                )
            except Exception:
                pass
            try:
                if hasattr(self.game, "event_system"):
                    self.game.event_system.publish(
                        "fight_attacks_resolved",
                        unit=fighting_unit,
                        target_unit=None,
                        hits_by_target=hits_by_target_total,
                        hit_models_by_target=hit_models_by_target_total,
                        hit_models_by_target_psychic=hit_models_by_target_psychic_total,
                    )
            except Exception:
                pass

            # Step 3: Consolidate using Individual Model Movement Dialog
            def on_consolidate_complete(completed: bool):
                logger.info(f"{fighting_unit.name} consolidate completed: {completed}")

                try:
                    if completed and hasattr(fighting_unit, "consolidate_towards_enemies"):
                        fighting_unit.consolidate_towards_enemies(getattr(self.game, "map", None))
                except Exception:
                    pass

                self.finalize_unit_fight(fighting_unit, current_player, opponent_player)

            # Show consolidate dialog
            ui_callback('consolidate', fighting_unit, on_consolidate_complete)

        # Show pile-in dialog
        ui_callback('pile_in', fighting_unit, on_pile_in_complete)

    def _switch_active_player(self, current_player: Player, opponent_player: Player) -> None:
        """Switch the active player and continue the fight phase."""
        # Switch active player
        self.active_player = opponent_player if self.active_player == current_player else current_player

        # Clear enemy model cache when switching players since enemy positions may have changed
        clear_enemy_model_cache(id(self.game.map))
        logger.info(f"Fight phase player switched to {self.active_player.name} - cleared enemy model cache")

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
        logger.info("Fight Phase complete")
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

    def _auto_select_melee_weapons(self, unit: Unit) -> List[dict]:
        """Fallback melee selection: one primary + all extra-attacks profiles per model."""
        declarations: list[dict] = []
        if unit is None:
            return declarations
        for model in list(getattr(unit, "models", []) or []):
            if not getattr(model, "is_alive", True):
                continue
            primary_profile = None
            extra_profiles: list = []
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                try:
                    if not bool(getattr(wargear, "is_melee", lambda: False)()):
                        continue
                except Exception:
                    continue
                profiles = getattr(wargear, "profiles", {}) or {}
                for profile in list(profiles.values()):
                    if profile is None:
                        continue
                    is_extra = False
                    try:
                        is_extra = bool(profile.is_extra_attacks())
                    except Exception:
                        is_extra = bool(getattr(profile, "extra_attacks", False))
                    if is_extra:
                        extra_profiles.append(profile)
                    elif primary_profile is None:
                        primary_profile = profile
            if primary_profile is not None:
                declarations.append({"model": model, "weapon_profile": primary_profile})
            for profile in extra_profiles:
                declarations.append({"model": model, "weapon_profile": profile})
        return declarations

    def _resolve_melee_attacks(self, attacking_unit: Unit, target_unit: Unit, weapon_declarations: List) -> Dict:
        """Resolve melee attacks with detailed output like shooting."""
        # AIRCRAFT fight restrictions (defensive guard)
        try:
            if bool(getattr(target_unit, "is_aircraft", False)) and not bool(getattr(attacking_unit, "is_flying", False)):
                logger.info(f"{attacking_unit.name} cannot make melee attacks against AIRCRAFT")
                return {"hits_by_target": {}, "hit_models_by_target": {}}
            if bool(getattr(attacking_unit, "is_aircraft", False)) and not bool(getattr(target_unit, "is_flying", False)):
                logger.info(f"{attacking_unit.name} can only make melee attacks against FLY units")
                return {"hits_by_target": {}, "hit_models_by_target": {}}
        except Exception:
            pass
        logger.info(f"Resolving melee attacks: {attacking_unit.name} vs {target_unit.name}")

        eligible_models = None
        try:
            if hasattr(attacking_unit, "has_fight_within_3_ability") and attacking_unit.has_fight_within_3_ability():
                game_map = getattr(self.game, "map", None)
                eligible_models = set(
                    attacking_unit.get_fight_eligible_models_for_target(
                        target_unit,
                        game_map=game_map,
                        allow_within_3=attacking_unit.fight_within_3_active(),
                    )
                )
        except Exception:
            eligible_models = None

        # Begin attack resolution window so attached leaders don't separate mid-melee sequence.
        try:
            if hasattr(target_unit, "begin_attack_resolution"):
                target_unit.begin_attack_resolution()
        except Exception:
            pass

        game_map = getattr(self.game, "map", None)
        hit_tracker = {}
        hit_models_by_target = {}
        hit_models_by_target_psychic = {}
        attack_context = {
            "pending_mortal_wounds": {},
            "defer_mortal_wounds": True,
            "hit_tracker": hit_tracker,
            "hit_models_by_target": hit_models_by_target,
            "hit_models_by_target_psychic": hit_models_by_target_psychic,
        }
        base_provider = None
        if game_map is not None:
            base_provider = getattr(game_map, "damage_allocation_provider", None)

        for declaration in weapon_declarations:
            model = declaration.get('model')
            weapon_profile = declaration.get('weapon_profile')
            attacks_override = declaration.get('attacks_override')
            attacks_override_modifiers = declaration.get('attacks_override_modifiers')
            attacks_override_note = declaration.get('attacks_override_note')
            wound_target = declaration.get('wound_target')

            if not model or not weapon_profile:
                continue
            if eligible_models is not None and model not in eligible_models:
                logger.info(f"{getattr(model, 'name', 'Model')} is not eligible to fight {getattr(target_unit, 'name', 'Target')}")
                continue

            logger.info(f"{model.name} attacks with {weapon_profile.name}")
            provider_reset = False
            if game_map is not None and wound_target is not None:
                def _forced_provider(unit, candidates, ctx, *, _target=wound_target, _base=base_provider):
                    if isinstance(candidates, (list, tuple, set)) and _target in candidates and getattr(_target, "is_alive", True):
                        return _target
                    if callable(_base):
                        return _base(unit, candidates, ctx)
                    return None
                setattr(game_map, "damage_allocation_provider", _forced_provider)
                provider_reset = True
            try:
                weapon_profile.attack(
                    target_unit,
                    model,
                    game_map=game_map,
                    attack_context=attack_context,
                    attacks_override=attacks_override,
                    attacks_override_modifiers=attacks_override_modifiers,
                    attacks_override_note=attacks_override_note,
                )
            finally:
                if provider_reset and game_map is not None:
                    setattr(game_map, "damage_allocation_provider", base_provider)

        try:
            if hasattr(attacking_unit, "_resolve_pending_attack_mortal_wounds"):
                attacking_unit._resolve_pending_attack_mortal_wounds(
                    attack_context,
                    target_unit,
                    game_map=game_map,
                )
        except Exception:
            pass

        # End attack resolution window for this target after this unit has finished its melee attacks.
        try:
            game_map = getattr(self.game, "map", None)
            if hasattr(target_unit, "end_attack_resolution"):
                target_unit.end_attack_resolution(game_map=game_map)
        except Exception:
            pass
        if hasattr(attacking_unit, "_resolve_pending_horrors_split"):
            attacking_unit._resolve_pending_horrors_split(game_map=game_map)
        return {
            "hits_by_target": hit_tracker,
            "hit_models_by_target": hit_models_by_target,
            "hit_models_by_target_psychic": hit_models_by_target_psychic,
        }

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
