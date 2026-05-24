"""
Fight Phase Manager for Warhammer 40k.

Manages the proper two-stage fight phase structure with alternating player selection:
1. Fight First Stage - Units that charged or have Fight First abilities
2. Remaining Combatants Stage - All other eligible units

Within each stage, players alternate selecting units to fight, with the non-current player going first.
"""

from typing import TYPE_CHECKING, List, Optional, Dict, Callable
from enum import Enum
from ..units.unit import Unit
from ..units.model import Model
from ..roster.player import Player
from ..utility.calcs import clear_enemy_model_cache
from ..utility.entity_ids import get_entity_id
from .combat_timing import fight_phase_move_steps, fight_phase_starting_player
from . import fight_engagement as _fight_engagement
from . import fight_order as _fight_order
from . import fight_resolution as _fight_resolution
from .decision_port import get_decision_provider
from .fight_scheduler import FightScheduler, FightSchedulerStage
from .unit_turn_provenance import set_status_tokens_on_unit, status_tokens_on_unit
from .decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_SELECT_UNIT
from ..utility.event_bus import append_action
import logging
logger = logging.getLogger(__name__)


def _fight_entity_id(entity: object | None) -> str:
    if entity is None:
        return ""
    try:
        return str(get_entity_id(entity) or "")
    except ValueError:
        return ""


def _melee_declaration_diagnostic(
    *,
    target_unit: object | None,
    model: object | None,
    weapon_profile: object | None,
    reason: str = "",
    attacks_executed: int | None = None,
    damage_dealt: int | None = None,
    models_killed: int | None = None,
) -> dict:
    row = {
        "target_unit_id": _fight_entity_id(target_unit),
        "model_id": _fight_entity_id(model),
        "model_name": str(getattr(model, "name", "") or ""),
        "weapon_profile_id": _fight_entity_id(weapon_profile),
        "weapon_profile_name": str(getattr(weapon_profile, "name", "") or ""),
        "reason": str(reason or ""),
    }
    if attacks_executed is not None:
        row["attacks_executed"] = int(attacks_executed or 0)
    if damage_dealt is not None:
        row["damage_dealt"] = int(damage_dealt or 0)
    if models_killed is not None:
        row["models_killed"] = int(models_killed or 0)
    return row


if TYPE_CHECKING:
    from .game import Game

class FightStage(Enum):
    PILE_IN_ACTIVE = "Pile In Active"
    PILE_IN_REACTIVE = "Pile In Reactive"
    FIGHT_FIRST = "Fight First"
    REMAINING_COMBATANTS = "Remaining Combatants"
    CONSOLIDATE_BATCH = "Consolidate Batch"
    COMPLETE = "Complete"

class FightPhaseManager:
    """Manages the fight phase with proper alternating player selection."""
    
    def __init__(self, game: 'Game'):
        self.game = game
        self.current_stage = FightStage.FIGHT_FIRST
        self.scheduler = None
        self.active_player = None  # Player who needs to select next
        self.fought_units = set()  # Units that have already fought this phase
        self.stage_complete = False
        # Counter-Offensive support: force a specific unit to fight next.
        self._forced_next_unit = None
        self._forced_next_player = None
        # Cache fight phase players for refresh requests.
        self._current_player = None
        self._opponent_player = None
        self._pending_target_selection_unit = None
        self._pending_fight_sequence = None
        # Callbacks for human player interaction
        self.on_unit_selection_required = None
        self.on_target_selection_required = None
        self.on_movement_required = None
        self.on_weapon_selection_required = None
        self.on_target_allocation_required = None
        self.on_stage_complete = None

    def _canonical_unit_for_fight(self, unit: Unit) -> Unit:
        return _fight_engagement._canonical_unit_for_fight(self, unit)

    def _as_attached_view(self, unit: Unit) -> Unit:
        return _fight_engagement._as_attached_view(self, unit)
        
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
        self._pending_target_selection_unit = None
        self._pending_fight_sequence = None
        self.scheduler = FightScheduler(
            self.game,
            current_player=current_player,
            opponent_player=opponent_player,
        )
        self.scheduler.start()
        self._reset_fight_phase_eligibility_flags(current_player, opponent_player)

        self._resume_scheduler_stage(current_player, opponent_player, advance=False)

    def _reset_fight_phase_eligibility_flags(self, current_player: Player, opponent_player: Player) -> None:
        _fight_order._reset_fight_phase_eligibility_flags(self, current_player, opponent_player)

    def _mark_units_eligible_to_fight_this_phase(self, units: List[Unit]) -> None:
        _fight_order._mark_units_eligible_to_fight_this_phase(self, units)
    
    def _start_fight_first_stage(self, current_player: Player, opponent_player: Player) -> None:
        """Start the Fight First stage."""
        logger.info("Starting Fight First Stage")
        self.current_stage = FightStage.FIGHT_FIRST
        if self.scheduler is not None:
            self.scheduler.state = self.scheduler._with_stage(FightSchedulerStage.FIGHTS_FIRST)
            self.scheduler._capture_attack_stage("fight_first")

        # Get Fight First units for both players with detailed debugging
        current_player_units = self._get_eligible_units_for_player(current_player)
        opponent_units = self._get_eligible_units_for_player(opponent_player)

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

        if self.scheduler is not None:
            self.active_player = self.scheduler.current_stage_starting_player()
        else:
            self.active_player = fight_phase_starting_player(
                self.game,
                current_player,
                opponent_player,
                stage_name="fight_first",
            )
        self._request_unit_selection(current_player, opponent_player)
    
    def _start_remaining_combatants_stage(self, current_player: Player, opponent_player: Player) -> None:
        """Start the Remaining Combatants stage."""
        logger.info("Starting Remaining Combatants Stage")
        self.current_stage = FightStage.REMAINING_COMBATANTS
        if self.scheduler is not None:
            self.scheduler.state = self.scheduler._with_stage(FightSchedulerStage.REMAINING_COMBATANTS)
            self.scheduler._capture_attack_stage("remaining_combatants")

        # Get remaining combatant units for both players with detailed debugging
        current_player_units = self._get_eligible_units_for_player(current_player)
        opponent_units = self._get_eligible_units_for_player(opponent_player)

        logger.info(f"Current Player ({current_player.name}): {len(current_player_units)} Remaining units")
        if current_player_units:
            for unit in current_player_units:
                logger.info(f"  - {unit.name} (eligible_to_fight: {unit.is_eligible_to_fight(self.game.map)})")

        logger.info(f"Opponent ({opponent_player.name}): {len(opponent_units)} Remaining units")
        if opponent_units:
            for unit in opponent_units:
                logger.info(f"  - {unit.name} (eligible_to_fight: {unit.is_eligible_to_fight(self.game.map)})")

        if not current_player_units and not opponent_units:
            logger.info("No remaining combatant units - moving to next fight step")
            self._complete_current_stage(current_player, opponent_player)
            return

        if self.scheduler is not None:
            self.active_player = self.scheduler.current_stage_starting_player()
        else:
            self.active_player = fight_phase_starting_player(
                self.game,
                current_player,
                opponent_player,
                stage_name="remaining_combatants",
            )
        self._request_unit_selection(current_player, opponent_player)

    def _start_consolidate_batch_stage(self, current_player: Player, opponent_player: Player) -> None:
        logger.info("Starting Consolidate Batch Stage")
        self.current_stage = FightStage.CONSOLIDATE_BATCH
        self.active_player = current_player
        self._request_next_batch_consolidate(current_player, opponent_player)

    def _start_pile_in_batch_stage(self, current_player: Player, opponent_player: Player) -> None:
        if self.scheduler is None:
            self._start_fight_first_stage(current_player, opponent_player)
            return
        if self.scheduler.state.stage == FightSchedulerStage.PILE_IN_ACTIVE:
            logger.info("Starting Active Player Pile-in Batch Stage")
            self.current_stage = FightStage.PILE_IN_ACTIVE
        else:
            logger.info("Starting Reactive Player Pile-in Batch Stage")
            self.current_stage = FightStage.PILE_IN_REACTIVE
        self.active_player = self.scheduler.current_stage_player()
        self._request_next_batch_pile_in(current_player, opponent_player)

    def _request_next_batch_pile_in(self, current_player: Player, opponent_player: Player) -> None:
        if self.scheduler is None:
            self._start_fight_first_stage(current_player, opponent_player)
            return
        fighting_unit = self.scheduler.next_pile_in_unit()
        if fighting_unit is None:
            self._complete_current_stage(current_player, opponent_player)
            return
        unit_id = str(get_entity_id(fighting_unit) or "")
        boundary = self.scheduler.stage_decision_boundary(
            player=self.active_player,
            unit=fighting_unit,
            decision_category=str(self.current_stage.name).lower(),
        ).to_dict()
        self._pending_fight_sequence = {
            "mode": "pile_in_batch",
            "fighting_unit_id": unit_id,
            "target_declarations": [],
            "step": "pile_in",
            "fight_stage_boundary": boundary,
        }
        request = self._queue_fight_move_request(
            fighting_unit=fighting_unit,
            target_declarations={},
            movement_type="pile_in",
        )
        if request is None:
            self.on_fight_move_resolved(
                unit_id=unit_id,
                movement_type="pile_in",
            )

    def _request_next_batch_consolidate(self, current_player: Player, opponent_player: Player) -> None:
        if self.scheduler is None:
            self._complete_fight_phase()
            return
        fighting_unit = self.scheduler.next_consolidate_unit()
        if fighting_unit is None:
            self._complete_current_stage(current_player, opponent_player)
            return
        self._pending_fight_sequence = {
            "mode": "consolidate_batch",
            "fighting_unit_id": str(get_entity_id(fighting_unit) or ""),
            "target_declarations": [],
            "step": "consolidate",
        }
        request = self._queue_fight_move_request(
            fighting_unit=fighting_unit,
            target_declarations={},
            movement_type="consolidate",
        )
        if request is None:
            self.on_fight_move_resolved(
                unit_id=str(get_entity_id(fighting_unit) or ""),
                movement_type="consolidate",
            )

    def _resume_scheduler_stage(self, current_player: Player, opponent_player: Player, *, advance: bool = True) -> None:
        if self.scheduler is None:
            self._start_fight_first_stage(current_player, opponent_player)
            return
        state = self.scheduler.advance_to_actionable_stage() if advance else self.scheduler.state
        if state.stage in {FightSchedulerStage.PILE_IN_ACTIVE, FightSchedulerStage.PILE_IN_REACTIVE}:
            self._start_pile_in_batch_stage(current_player, opponent_player)
            return
        if state.stage == FightSchedulerStage.FIGHTS_FIRST:
            self._start_fight_first_stage(current_player, opponent_player)
            return
        if state.stage == FightSchedulerStage.REMAINING_COMBATANTS:
            self._start_remaining_combatants_stage(current_player, opponent_player)
            return
        if state.stage == FightSchedulerStage.CONSOLIDATE_BATCH:
            self._start_consolidate_batch_stage(current_player, opponent_player)
            return
        self._complete_fight_phase()
    
    def _request_unit_selection(self, current_player: Player, opponent_player: Player) -> None:
        """Request unit selection from the active player."""
        if self.scheduler is not None:
            self.scheduler.refresh_stage_injections(fought_units=self.fought_units)
        must_fight_units = self._must_fight_next_units()
        if must_fight_units:
            forced = must_fight_units[0]
            owner = self._owner_player_for_unit(forced)
            if owner is not None:
                self.active_player = owner
            eligible_units = [forced]
            logger.info(
                "%s must be the next unit selected to fight due to a status token",
                getattr(forced, "name", "Unit"),
            )
            self._queue_fight_selection_decision(
                current_player=current_player,
                opponent_player=opponent_player,
                eligible_units=eligible_units,
                reason="must_fight_next",
            )
            if self.on_unit_selection_required:
                self.on_unit_selection_required(self.active_player, eligible_units, self.current_stage)
            return
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

        self._queue_fight_selection_decision(
            current_player=current_player,
            opponent_player=opponent_player,
            eligible_units=eligible_units,
            reason="stage_selection",
        )

        if self.on_unit_selection_required:
            self.on_unit_selection_required(self.active_player, eligible_units, self.current_stage)

    def _queue_fight_selection_decision(
        self,
        *,
        current_player: Player,
        opponent_player: Player,
        eligible_units: List[Unit],
        reason: str,
    ):
        del current_player, opponent_player
        queue_select = getattr(self.game, "_queue_fight_phase_selection", None)
        if not callable(queue_select):
            return None
        extra_context = {
            "fight_scheduler": self.scheduler.decision_context() if self.scheduler is not None else {},
            "fight_selection_reason": str(reason or ""),
        }
        if self.scheduler is not None:
            extra_context["fight_stage_boundary"] = self.scheduler.stage_decision_boundary(
                player=self.active_player,
                decision_category=str(reason or "stage_selection"),
            ).to_dict()
        return queue_select(
            player=self.active_player,
            eligible_units=eligible_units,
            stage=self.current_stage,
            extra_context=extra_context,
        )

    def _must_fight_next_units(self) -> list[Unit]:
        if self.scheduler is None:
            return []
        return list(self.scheduler.must_fight_next_units(fought_units=self.fought_units) or [])

    @staticmethod
    def _owner_player_for_unit(unit: Unit):
        if unit is None:
            return None
        army_getter = getattr(unit, "get_parent_army", None)
        army = army_getter() if callable(army_getter) else getattr(unit, "parent_army", None)
        return getattr(army, "player", None) if army is not None else None
    
    def _get_eligible_units_for_player(self, player: Player) -> List[Unit]:
        return _fight_order._get_eligible_units_for_player(self, player)

    def _is_forced_unit_valid(self, unit: Unit) -> bool:
        return _fight_order._is_forced_unit_valid(self, unit)

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

    def _record_unit_fight_completion(self, fighting_unit: Unit) -> None:
        fighting_unit = self._canonical_unit_for_fight(fighting_unit)
        pending = dict(self._pending_fight_sequence or {})
        if str(pending.get("fighting_unit_id", "") or "") == str(get_entity_id(fighting_unit) or ""):
            self._pending_fight_sequence = None
        self.fought_units.add(fighting_unit)
        self._consume_must_fight_next_tokens(fighting_unit)
        if self.scheduler is not None:
            self.scheduler._record_trace(
                "unit_fight_completed",
                unit_id=str(get_entity_id(fighting_unit) or ""),
                stage=str(getattr(self.current_stage, "name", "") or ""),
            )
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
        publish_activation = getattr(self.game, "_publish_unit_activation_event", None)
        if callable(publish_activation):
            phase_step = self._fight_phase_step_name()
            stage_name = str(getattr(self.current_stage, "name", "") or "")
            publish_activation(
                "unit_fight_ended",
                unit=fighting_unit,
                player=self.active_player,
                phase_name="FIGHT_PHASE",
                phase_step=phase_step,
                selection_purpose="ACTIVATE_FIGHTING_UNIT",
                stage=stage_name,
            )
            publish_activation(
                "unit_activation_ended",
                unit=fighting_unit,
                player=self.active_player,
                phase_name="FIGHT_PHASE",
                phase_step=phase_step,
                selection_purpose="ACTIVATE_FIGHTING_UNIT",
                stage=stage_name,
            )

    def finalize_unit_fight(self, fighting_unit: Unit, current_player: Player, opponent_player: Player) -> None:
        """Finalize a unit's fight sequence and advance turn order."""
        self._record_unit_fight_completion(fighting_unit)
        self._switch_active_player(current_player, opponent_player)
    
    def unit_selected(self, selected_unit: Unit, current_player: Player, opponent_player: Player) -> None:
        """Handle unit selection from the active player."""
        selected_unit = self._canonical_unit_for_fight(selected_unit)
        if self.scheduler is not None:
            self.scheduler._record_trace(
                "unit_selected_to_fight",
                unit_id=str(get_entity_id(selected_unit) or ""),
                stage=str(getattr(self.current_stage, "name", "") or ""),
            )
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
        publish_activation = getattr(self.game, "_publish_unit_activation_event", None)
        if callable(publish_activation):
            publish_activation(
                "unit_fight_started",
                unit=selected_unit,
                player=self.active_player,
                phase_name="FIGHT_PHASE",
                phase_step=self._fight_phase_step_name(),
                selection_purpose="ACTIVATE_FIGHTING_UNIT",
                stage=str(getattr(self.current_stage, "name", "") or ""),
            )

        # Find eligible targets for this unit
        eligible_targets = self._get_eligible_targets(selected_unit)

        if not eligible_targets:
            if self._queue_overrun_pile_in_if_available(selected_unit):
                return
            logger.info(f"{selected_unit.name} has no eligible targets")
            append_action(
                self.active_player,
                f"{selected_unit.name}: no eligible melee targets; fight activation ends.",
            )
            try:
                if hasattr(selected_unit, "clear_selected_to_action_reroll_choice"):
                    selected_unit.clear_selected_to_action_reroll_choice(action="fight")
            except Exception:
                pass
            self.finalize_unit_fight(selected_unit, current_player, opponent_player)
            return

        if self._has_pending_battle_focus_confirmation(selected_unit):
            self._pending_target_selection_unit = selected_unit
            return
        
        # Always show target selection dialog, even for single targets
        # This gives the user a chance to see what's happening and confirm the attack
        self._dispatch_target_selection(selected_unit, eligible_targets)

    def _queue_overrun_pile_in_if_available(self, fighting_unit: Unit) -> bool:
        if self.scheduler is None or not bool(self.scheduler.overrun_available_for(fighting_unit)):
            return False
        fighting_unit = self._canonical_unit_for_fight(fighting_unit)
        logger.info(f"{fighting_unit.name} is using an overrun pile-in to regain combat engagement")
        self._pending_fight_sequence = {
            "mode": "overrun",
            "fighting_unit_id": str(get_entity_id(fighting_unit) or ""),
            "step": "pile_in",
            "target_declarations": [],
        }
        request = self._queue_fight_move_request(
            fighting_unit=fighting_unit,
            target_declarations={},
            movement_type="pile_in",
        )
        if request is None:
            self.on_fight_move_resolved(
                unit_id=str(get_entity_id(fighting_unit) or ""),
                movement_type="pile_in",
            )
        return True

    def _dispatch_target_selection(self, selected_unit: Unit, eligible_targets: List[Unit]) -> None:
        logger.info(f"{selected_unit.name} can fight {len(eligible_targets)} target(s): {[target.name for target in eligible_targets]}")
        queue_request = getattr(self.game, "_queue_fight_target_selection_request", None)
        request = None
        if callable(queue_request):
            request = queue_request(
                fighting_unit=selected_unit,
                eligible_targets=eligible_targets,
                active_player=self.active_player,
            )
        if self.on_target_selection_required:
            self.on_target_selection_required(selected_unit, eligible_targets, self.active_player)
            return
        return request

    def _has_pending_battle_focus_confirmation(self, unit: Unit) -> bool:
        if unit is None:
            return False
        queue = getattr(self.game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        try:
            unit_id = str(get_entity_id(unit) or "")
        except Exception:
            unit_id = ""
        player_id = str(getattr(self.active_player, "id", "") or "")
        for request in list(queue.list() or []):
            ctx = dict(getattr(request, "context", {}) or {})
            if str(getattr(request, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
                continue
            if str(ctx.get("ability", "") or "").strip().lower() != "battle_focus_sudden_strike":
                continue
            if unit_id and str(ctx.get("unit_id", "") or "") != unit_id:
                continue
            if player_id and str(getattr(request, "player_id", "") or "") != player_id:
                continue
            return True
        return False

    def resume_pending_target_selection(self, *, unit_id: str | None = None) -> None:
        unit = self._pending_target_selection_unit
        if unit is None:
            return
        try:
            pending_unit_id = str(get_entity_id(unit) or "")
        except Exception:
            pending_unit_id = ""
        if unit_id and pending_unit_id and str(unit_id) != pending_unit_id:
            return
        self._pending_target_selection_unit = None
        eligible_targets = self._get_eligible_targets(unit)
        if not eligible_targets:
            logger.info(f"{getattr(unit, 'name', 'Unit')} has no eligible targets")
            append_action(
                self.active_player,
                f"{getattr(unit, 'name', 'Unit')}: no eligible melee targets; fight activation ends.",
            )
            try:
                if hasattr(unit, "clear_selected_to_action_reroll_choice"):
                    unit.clear_selected_to_action_reroll_choice(action="fight")
            except Exception:
                pass
            if self._current_player is not None and self._opponent_player is not None:
                self.finalize_unit_fight(unit, self._current_player, self._opponent_player)
            return
        self._dispatch_target_selection(unit, eligible_targets)

    def _fight_phase_step_name(self) -> str:
        if self.current_stage == FightStage.PILE_IN_ACTIVE:
            return "PILE_IN_ACTIVE"
        if self.current_stage == FightStage.PILE_IN_REACTIVE:
            return "PILE_IN_REACTIVE"
        if self.current_stage == FightStage.FIGHT_FIRST:
            return "FIGHT_FIRST"
        if self.current_stage == FightStage.REMAINING_COMBATANTS:
            return "REMAINING_COMBATANTS"
        if self.current_stage == FightStage.CONSOLIDATE_BATCH:
            return "CONSOLIDATE_BATCH"
        return ""

    def _serialize_target_declarations(self, target_declarations: Dict[Unit, List['Model']]) -> list[dict]:
        return _fight_engagement._serialize_target_declarations(self, target_declarations)

    def _resolve_model_by_id(self, model_id: str):
        return _fight_engagement._resolve_model_by_id(self, model_id)

    def _deserialize_target_declarations(self, serialized: list[dict]) -> Dict[Unit, List['Model']]:
        return _fight_engagement._deserialize_target_declarations(self, serialized)

    def _queue_fight_move_request(
        self,
        *,
        fighting_unit: Unit,
        target_declarations: Dict[Unit, List['Model']],
        movement_type: str,
    ):
        return _fight_resolution._queue_fight_move_request(
            self,
            fighting_unit=fighting_unit,
            target_declarations=target_declarations,
            movement_type=movement_type,
        )

    def _queue_declare_melee_weapons_request(
        self,
        *,
        fighting_unit: Unit,
        target_declarations: Dict[Unit, List['Model']],
    ):
        return _fight_resolution._queue_declare_melee_weapons_request(
            self,
            fighting_unit=fighting_unit,
            target_declarations=target_declarations,
        )

    def _queue_allocate_melee_targets_request(
        self,
        *,
        fighting_unit: Unit,
        target_declarations: Dict[Unit, List['Model']],
        weapon_declarations: List[dict],
    ):
        return _fight_resolution._queue_allocate_melee_targets_request(
            self,
            fighting_unit=fighting_unit,
            target_declarations=target_declarations,
            weapon_declarations=weapon_declarations,
        )

    def _resolve_target_declaration_attacks(
        self,
        fighting_unit: Unit,
        target_declarations: Dict[Unit, List['Model']],
        *,
        weapon_declarations: List[dict] | None = None,
    ) -> None:
        _fight_resolution._resolve_target_declaration_attacks(
            self,
            fighting_unit,
            target_declarations,
            weapon_declarations=weapon_declarations,
        )

    def _resolve_allocated_melee_attacks(
        self,
        fighting_unit: Unit,
        ordered_target_units: List[Unit],
        attack_declarations: List[dict],
    ) -> None:
        _fight_resolution._resolve_allocated_melee_attacks(
            self,
            fighting_unit,
            ordered_target_units,
            attack_declarations,
        )

    def _advance_after_attack_resolution(
        self,
        *,
        fighting_unit: Unit,
        target_declarations: Dict[Unit, List['Model']],
    ) -> None:
        sequence = dict(self._pending_fight_sequence or {})
        move_steps = list(fight_phase_move_steps(self.game))
        next_step = ""
        if not (self.scheduler is not None and self.scheduler.uses_consolidate_batch()):
            next_step = move_steps[1] if len(move_steps) > 1 else ""
        if not next_step:
            self._pending_fight_sequence = None
            try:
                if hasattr(fighting_unit, "_clear_formless_horror_allowed"):
                    fighting_unit._clear_formless_horror_allowed()
            except Exception:
                pass
            self._complete_attacks_for_unit(fighting_unit, self._current_player, self._opponent_player)
            return
        self._pending_fight_sequence = {
            **sequence,
            "target_declarations": self._serialize_target_declarations(target_declarations),
            "step": next_step,
        }
        request = self._queue_fight_move_request(
            fighting_unit=fighting_unit,
            target_declarations=target_declarations,
            movement_type=next_step,
        )
        if request is None:
            self.on_fight_move_resolved(
                unit_id=str(get_entity_id(fighting_unit) or ""),
                movement_type=next_step,
            )

    def on_melee_weapons_declared(self, *, unit_id: str, weapon_declarations: List[dict] | None) -> None:
        sequence = dict(self._pending_fight_sequence or {})
        if not sequence:
            return
        if str(sequence.get("fighting_unit_id", "") or "") != str(unit_id or ""):
            return
        resolve_unit = getattr(self.game, "_resolve_unit_by_id", None)
        if not callable(resolve_unit):
            return
        fighting_unit = resolve_unit(str(unit_id or ""))
        if fighting_unit is None:
            self._pending_fight_sequence = None
            return
        target_declarations = self._deserialize_target_declarations(sequence.get("target_declarations", []))
        if not target_declarations:
            self._pending_fight_sequence = None
            return
        declarations = list(weapon_declarations or [])
        if len(target_declarations) > 1:
            self._pending_fight_sequence = {
                **sequence,
                "target_declarations": self._serialize_target_declarations(target_declarations),
                "step": "allocate_melee_targets",
            }
            request = self._queue_allocate_melee_targets_request(
                fighting_unit=fighting_unit,
                target_declarations=target_declarations,
                weapon_declarations=declarations,
            )
            if request is None:
                self.on_melee_target_allocation_resolved(
                    unit_id=str(unit_id or ""),
                    attack_declarations=[],
                )
            return
        self._resolve_target_declaration_attacks(
            fighting_unit,
            target_declarations,
            weapon_declarations=declarations,
        )
        self._advance_after_attack_resolution(
            fighting_unit=fighting_unit,
            target_declarations=target_declarations,
        )

    def on_melee_target_allocation_resolved(self, *, unit_id: str, attack_declarations: List[dict] | None) -> None:
        sequence = dict(self._pending_fight_sequence or {})
        if not sequence:
            return
        if str(sequence.get("fighting_unit_id", "") or "") != str(unit_id or ""):
            return
        resolve_unit = getattr(self.game, "_resolve_unit_by_id", None)
        if not callable(resolve_unit):
            return
        fighting_unit = resolve_unit(str(unit_id or ""))
        if fighting_unit is None:
            self._pending_fight_sequence = None
            return
        target_declarations = self._deserialize_target_declarations(sequence.get("target_declarations", []))
        target_units = [target_unit for target_unit in list(target_declarations or {}) if target_unit is not None]
        self._resolve_allocated_melee_attacks(
            fighting_unit,
            target_units,
            list(attack_declarations or []),
        )
        self._advance_after_attack_resolution(
            fighting_unit=fighting_unit,
            target_declarations=target_declarations,
        )

    def on_fight_within_3_resolved(self, *, unit_id: str) -> None:
        sequence = dict(self._pending_fight_sequence or {})
        if not sequence:
            return
        if str(sequence.get("fighting_unit_id", "") or "") != str(unit_id or ""):
            return
        if str(sequence.get("step", "") or "").strip().lower() != "fight_within_3":
            return
        resolve_unit = getattr(self.game, "_resolve_unit_by_id", None)
        if not callable(resolve_unit):
            return
        fighting_unit = resolve_unit(str(unit_id or ""))
        if fighting_unit is None:
            self._pending_fight_sequence = None
            return
        target_declarations = self._deserialize_target_declarations(sequence.get("target_declarations", []))
        self._pending_fight_sequence = {
            **sequence,
            "target_declarations": self._serialize_target_declarations(target_declarations),
            "step": "declare_melee_weapons",
        }
        request = self._queue_declare_melee_weapons_request(
            fighting_unit=fighting_unit,
            target_declarations=target_declarations,
        )
        if request is None:
            self.on_melee_weapons_declared(
                unit_id=str(unit_id or ""),
                weapon_declarations=[],
            )

    def on_fight_move_resolved(self, *, unit_id: str, movement_type: str) -> None:
        sequence = dict(self._pending_fight_sequence or {})
        if not sequence:
            return
        if str(sequence.get("fighting_unit_id", "") or "") != str(unit_id or ""):
            return
        move_tag = str(movement_type or "").strip().lower()
        expected_step = str(sequence.get("step", "") or "").strip().lower()
        if expected_step and move_tag != expected_step:
            return
        resolve_unit = getattr(self.game, "_resolve_unit_by_id", None)
        if not callable(resolve_unit):
            return
        fighting_unit = resolve_unit(str(unit_id or ""))
        if fighting_unit is None:
            self._pending_fight_sequence = None
            return
        mode = str(sequence.get("mode", "activation") or "activation").strip().lower()
        if mode == "pile_in_batch":
            logger.info(f"{fighting_unit.name} pile-in batch move resolved via MOVE_UNIT")
            stage = self.scheduler.state.stage if self.scheduler is not None else None
            self._pending_fight_sequence = None
            if self.scheduler is not None:
                self.scheduler.mark_pile_in_resolved(fighting_unit, stage)
            self._request_next_batch_pile_in(self._current_player, self._opponent_player)
            return
        if mode == "consolidate_batch":
            logger.info(f"{fighting_unit.name} consolidate batch move resolved via MOVE_UNIT")
            self._pending_fight_sequence = None
            if self.scheduler is not None:
                self.scheduler.mark_consolidate_resolved(fighting_unit)
            self._request_next_batch_consolidate(self._current_player, self._opponent_player)
            return
        if mode == "overrun":
            logger.info(f"{fighting_unit.name} overrun pile-in resolved via MOVE_UNIT")
            self._pending_fight_sequence = None
            eligible_targets = self._get_eligible_targets(fighting_unit)
            if not eligible_targets:
                self._record_unit_fight_completion(fighting_unit)
                self._switch_active_player(self._current_player, self._opponent_player)
                return
            self._dispatch_target_selection(fighting_unit, eligible_targets)
            return
        target_declarations = self._deserialize_target_declarations(sequence.get("target_declarations", []))
        move_steps = list(fight_phase_move_steps(self.game))
        first_step = move_steps[0] if move_steps else ""
        if move_tag == first_step:
            logger.info(f"{fighting_unit.name} pile-in resolved via MOVE_UNIT")
            queue_confirmation = getattr(self.game, "_queue_fight_within_3_confirmation", None)
            confirmation_request = None
            if callable(queue_confirmation):
                target_unit = next((target for target in list(target_declarations or {}) if target is not None), None)
                confirmation_request = queue_confirmation(
                    player=self.active_player,
                    unit=fighting_unit,
                    target_unit=target_unit,
                    context={"fight_phase_flow": True},
                )
            if str(getattr(confirmation_request, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO:
                self._pending_fight_sequence = {
                    **sequence,
                    "target_declarations": self._serialize_target_declarations(target_declarations),
                    "step": "fight_within_3",
                }
                return
            self._pending_fight_sequence = {
                **sequence,
                "target_declarations": self._serialize_target_declarations(target_declarations),
                "step": "fight_within_3",
            }
            self.on_fight_within_3_resolved(unit_id=str(unit_id or ""))
            return
        final_step = move_steps[-1] if move_steps else "consolidate"
        if move_tag != final_step:
            return
        logger.info(f"{fighting_unit.name} consolidate resolved via MOVE_UNIT")
        self._pending_fight_sequence = None
        try:
            if hasattr(fighting_unit, "_clear_formless_horror_allowed"):
                fighting_unit._clear_formless_horror_allowed()
        except Exception:
            pass
        self.finalize_unit_fight(fighting_unit, self._current_player, self._opponent_player)
    
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
        skip_initial_move = bool(
            str(dict(self._pending_fight_sequence or {}).get("mode", "") or "").strip().lower() == "overrun"
        )
        if skip_initial_move:
            self._pending_fight_sequence = None
        self._execute_fight_sequence_with_declarations(
            fighting_unit,
            target_declarations,
            current_player,
            opponent_player,
            ui_callback,
            skip_initial_move=skip_initial_move,
        )
    
    def _get_eligible_targets(self, fighting_unit: Unit, *, ignore_helhunt_target_lock: bool = False) -> List[Unit]:
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

        def _changehost_deceptive_glamour_active(unit: Unit) -> bool:
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("thousand_sons_deceptive_glamour_active")):
                return False
            expires_phase = str(sr.get("thousand_sons_deceptive_glamour_expires_phase", "") or "").strip().upper()
            if expires_phase and expires_phase != "FIGHT_PHASE":
                return False
            try:
                marker_turn = int(sr.get("thousand_sons_deceptive_glamour_turn", 0) or 0)
            except Exception:
                marker_turn = 0
            try:
                current_turn = int(getattr(self.game, "turn", 0) or 0)
            except Exception:
                current_turn = 0
            if marker_turn and current_turn and marker_turn != current_turn:
                return False
            return True

        def _is_scintillating_legions_unit(unit: Unit) -> bool:
            if unit is None:
                return False
            try:
                if hasattr(unit, "has_any_keyword") and unit.has_any_keyword("SCINTILLATING LEGIONS"):
                    return True
            except Exception:
                pass
            try:
                faction_id = str(getattr(unit, "faction_id", "") or "").strip().upper()
                if faction_id in {"SL", "SCINTILLATING LEGIONS", "SCINTILLATING_LEGIONS"}:
                    return True
            except Exception:
                pass
            try:
                for keyword in list(getattr(unit, "faction_keywords", []) or []):
                    if str(keyword or "").strip().upper() == "SCINTILLATING LEGIONS":
                        return True
            except Exception:
                pass
            return False
        
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
                    try:
                        lock_check = getattr(fighting_unit, "_gsc_coordinated_trap_target_locked_to", None)
                        if callable(lock_check) and not bool(lock_check(enemy_root, game=self.game)):
                            continue
                    except Exception:
                        pass
                    try:
                        lock_check = getattr(fighting_unit, "_houndpack_hungry_for_combat_target_locked_to", None)
                        if callable(lock_check) and not bool(lock_check(enemy_root, game=self.game)):
                            continue
                    except Exception:
                        pass
                    try:
                        lock_check = getattr(fighting_unit, "_astra_militarum_engine_of_wrath_target_locked_to", None)
                        if callable(lock_check) and not bool(lock_check(enemy_root, game=self.game)):
                            continue
                    except Exception:
                        pass
                    try:
                        lock_check = getattr(fighting_unit, "_helhunt_merciless_fusillade_target_locked_to", None)
                        if (
                            not bool(ignore_helhunt_target_lock)
                            and callable(lock_check)
                            and not bool(lock_check(enemy_root, game=self.game, attack_type="melee"))
                        ):
                            continue
                    except Exception:
                        pass
                    try:
                        lock_check = getattr(fighting_unit, "_adeptus_custodes_witch_hunters_target_locked_to", None)
                        if callable(lock_check) and not bool(lock_check(enemy_root, game=self.game, attack_type="melee")):
                            continue
                    except Exception:
                        pass
                    eligible_targets.append(enemy_root)
            except Exception:
                continue

        forced_targets = [u for u in list(eligible_targets or []) if _suffering_and_sacrifice_active(u)]
        if forced_targets:
            return forced_targets
        preferred_scintillating_targets = [
            u for u in list(eligible_targets or []) if _is_scintillating_legions_unit(u)
        ]
        if preferred_scintillating_targets:
            filtered_targets = [
                u for u in list(eligible_targets or []) if not _changehost_deceptive_glamour_active(u)
            ]
            if filtered_targets:
                return filtered_targets
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
                            killing_models_by_target=attack_summary.get("killing_models_by_target"),
                            damage_by_target=attack_summary.get("damage_by_target"),
                            successful_attacks=int(attack_summary.get("successful_attacks", 0) or 0),
                            declaration_count=int(attack_summary.get("declaration_count", 0) or 0),
                            executed_declarations=list(attack_summary.get("executed_declarations") or []),
                            skipped_declarations=list(attack_summary.get("skipped_declarations") or []),
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

    def _complete_attacks_for_unit(self, fighting_unit: Unit, current_player: Player, opponent_player: Player) -> None:
        if self.scheduler is not None and self.scheduler.uses_consolidate_batch():
            self.scheduler.queue_consolidate(fighting_unit)
            self._record_unit_fight_completion(fighting_unit)
            self._switch_active_player(current_player, opponent_player)
            return
        self.finalize_unit_fight(fighting_unit, current_player, opponent_player)

    def _execute_fight_sequence_with_declarations(
        self,
        fighting_unit: Unit,
        target_declarations: Dict[Unit, List['Model']],
        current_player: Player,
        opponent_player: Player,
        ui_callback=None,
        *,
        skip_initial_move: bool = False,
    ) -> None:
        """Execute the complete fight sequence with target declarations."""
        logger.info(f"Executing fight sequence with declarations: {fighting_unit.name}")
        fighting_unit = self._canonical_unit_for_fight(fighting_unit)
        move_steps = list(fight_phase_move_steps(self.game))
        if skip_initial_move and move_steps:
            move_steps = move_steps[1:]
        if not move_steps:
            self._pending_fight_sequence = {
                "mode": "activation",
                "fighting_unit_id": str(get_entity_id(fighting_unit) or ""),
                "target_declarations": self._serialize_target_declarations(target_declarations),
                "step": "declare_melee_weapons",
            }
            request = self._queue_declare_melee_weapons_request(
                fighting_unit=fighting_unit,
                target_declarations=target_declarations,
            )
            if request is None:
                self.on_melee_weapons_declared(
                    unit_id=str(get_entity_id(fighting_unit) or ""),
                    weapon_declarations=[],
                )
            return
        self._pending_fight_sequence = {
            "mode": "activation",
            "fighting_unit_id": str(get_entity_id(fighting_unit) or ""),
            "target_declarations": self._serialize_target_declarations(target_declarations),
            "step": move_steps[0],
        }
        request = self._queue_fight_move_request(
            fighting_unit=fighting_unit,
            target_declarations=target_declarations,
            movement_type=move_steps[0],
        )
        if request is None:
            self.on_fight_move_resolved(
                unit_id=str(get_entity_id(fighting_unit) or ""),
                movement_type=move_steps[0],
            )
        return

    def _execute_fight_sequence_with_declarations_ui(self, fighting_unit: Unit, target_declarations: Dict[Unit, List['Model']], current_player: Player, opponent_player: Player, ui_callback) -> None:
        """Execute fight sequence with declarations using individual model movement UI."""
        logger.info(f"Starting UI-based fight sequence with declarations: {fighting_unit.name}")
        move_steps = list(fight_phase_move_steps(self.game))
        if not move_steps:
            self._pending_fight_sequence = {
                "mode": "activation",
                "fighting_unit_id": str(get_entity_id(fighting_unit) or ""),
                "target_declarations": self._serialize_target_declarations(target_declarations),
                "step": "declare_melee_weapons",
            }
            request = self._queue_declare_melee_weapons_request(
                fighting_unit=fighting_unit,
                target_declarations=target_declarations,
            )
            if request is None:
                self.on_melee_weapons_declared(
                    unit_id=str(get_entity_id(fighting_unit) or ""),
                    weapon_declarations=[],
                )
            return
        first_step = move_steps[0]

        # Step 1: Pile-in using Individual Model Movement Dialog
        def on_pile_in_complete(completed: bool):
            logger.info(f"{fighting_unit.name} pile-in completed: {completed}")

            try:
                if completed and hasattr(fighting_unit, "pile_in_towards_enemies"):
                    fighting_unit.pile_in_towards_enemies(getattr(self.game, "map", None))
            except Exception:
                pass

            self._current_player = current_player
            self._opponent_player = opponent_player
            self._pending_fight_sequence = {
                "mode": "activation",
                "fighting_unit_id": str(get_entity_id(fighting_unit) or ""),
                "target_declarations": self._serialize_target_declarations(target_declarations),
                "step": "declare_melee_weapons",
            }
            request = self._queue_declare_melee_weapons_request(
                fighting_unit=fighting_unit,
                target_declarations=target_declarations,
            )
            if request is None:
                self.on_melee_weapons_declared(
                    unit_id=str(get_entity_id(fighting_unit) or ""),
                    weapon_declarations=[],
                )

        # Show pile-in dialog
        ui_callback(first_step, fighting_unit, on_pile_in_complete)

    def _switch_active_player(self, current_player: Player, opponent_player: Player) -> None:
        _fight_order._switch_active_player(self, current_player, opponent_player)

    def _clear_pending_stage_selection_requests(self) -> None:
        clear_pending = getattr(self.game, "_clear_pending_fight_phase_requests", None)
        if not callable(clear_pending):
            return
        phase_step = self._fight_phase_step_name()
        if not phase_step:
            return
        clear_pending(phase_steps=[phase_step], decision_types=[DECISION_SELECT_UNIT])

    def _clear_pending_fight_phase_requests(self) -> None:
        clear_pending = getattr(self.game, "_clear_pending_fight_phase_requests", None)
        if callable(clear_pending):
            clear_pending()

    def _complete_current_stage(self, current_player: Player, opponent_player: Player) -> None:
        """Complete the current stage and move to next or finish."""
        self._clear_pending_stage_selection_requests()
        if self.current_stage == FightStage.COMPLETE:
            self._complete_fight_phase()
            return
        if self.scheduler is None:
            if self.current_stage == FightStage.FIGHT_FIRST:
                self._start_remaining_combatants_stage(current_player, opponent_player)
                return
            self._complete_fight_phase()
            return
        state = self.scheduler.complete_current_stage()
        if state.stage == FightSchedulerStage.FIGHTS_FIRST:
            self._start_fight_first_stage(current_player, opponent_player)
            return
        if state.stage in {FightSchedulerStage.PILE_IN_ACTIVE, FightSchedulerStage.PILE_IN_REACTIVE}:
            self._start_pile_in_batch_stage(current_player, opponent_player)
            return
        if state.stage == FightSchedulerStage.REMAINING_COMBATANTS:
            self._start_remaining_combatants_stage(current_player, opponent_player)
            return
        if state.stage == FightSchedulerStage.CONSOLIDATE_BATCH:
            self._start_consolidate_batch_stage(current_player, opponent_player)
            return
        self._complete_fight_phase()
    
    def _complete_fight_phase(self) -> None:
        """Complete the entire fight phase."""
        logger.info("Fight Phase complete")
        self._clear_pending_fight_phase_requests()
        self.current_stage = FightStage.COMPLETE
        self.stage_complete = True
        if self.scheduler is not None:
            self.scheduler.state = self.scheduler._with_stage(FightSchedulerStage.COMPLETE)
        
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

    @staticmethod
    def _consume_must_fight_next_tokens(unit: Unit) -> None:
        if unit is None:
            return
        remaining = [
            token
            for token in status_tokens_on_unit(unit)
            if str(token.condition_kind or "") != "must_fight_next"
        ]
        if len(remaining) != len(status_tokens_on_unit(unit)):
            set_status_tokens_on_unit(unit, remaining)

    def _default_melee_weapon_declarations(self, unit: Unit) -> List[dict]:
        """Default declaration payload: one primary + all extra-attacks profiles per model."""
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
        try:
            lock_check = getattr(attacking_unit, "_astra_militarum_engine_of_wrath_target_locked_to", None)
            if callable(lock_check) and not bool(lock_check(target_unit, game=self.game)):
                logger.info(
                    "%s can only target the selected Engine of Wrath enemy unit this phase",
                    getattr(attacking_unit, "name", "Unit"),
                )
                return {"hits_by_target": {}, "hit_models_by_target": {}}
        except Exception:
            pass
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
        killing_models_by_target = {}
        damage_by_target = {}
        executed_declarations = []
        skipped_declarations = []
        attack_context = {
            "attack_type": "melee",
            "pending_mortal_wounds": {},
            "defer_mortal_wounds": True,
            "hit_tracker": hit_tracker,
            "hit_models_by_target": hit_models_by_target,
            "hit_models_by_target_psychic": hit_models_by_target_psychic,
            "killing_models_by_target": killing_models_by_target,
            "damage_by_target": damage_by_target,
        }
        base_provider = get_decision_provider(self.game, "damage_allocation_provider")

        for declaration in weapon_declarations:
            model = declaration.get('model')
            weapon_profile = declaration.get('weapon_profile')
            attacks_override = declaration.get('attacks_override')
            attacks_override_modifiers = declaration.get('attacks_override_modifiers')
            attacks_override_note = declaration.get('attacks_override_note')
            wound_target = declaration.get('wound_target')

            if not model or not weapon_profile:
                skipped_declarations.append(
                    _melee_declaration_diagnostic(
                        target_unit=target_unit,
                        model=model,
                        weapon_profile=weapon_profile,
                        reason="missing_model_or_weapon_profile",
                    )
                )
                continue
            if eligible_models is not None and model not in eligible_models:
                logger.info(f"{getattr(model, 'name', 'Model')} is not eligible to fight {getattr(target_unit, 'name', 'Target')}")
                skipped_declarations.append(
                    _melee_declaration_diagnostic(
                        target_unit=target_unit,
                        model=model,
                        weapon_profile=weapon_profile,
                        reason="model_not_eligible_to_fight_target",
                    )
                )
                continue

            logger.info(f"{model.name} attacks with {weapon_profile.name}")
            provider_reset = False
            if wound_target is not None:
                def _forced_provider(unit, candidates, ctx, *, _target=wound_target, _base=base_provider):
                    if isinstance(candidates, (list, tuple, set)) and _target in candidates and getattr(_target, "is_alive", True):
                        return _target
                    if callable(_base):
                        return _base(unit, candidates, ctx)
                    return None
                self.game.install_decision_providers(damage_allocation_provider=_forced_provider)
                provider_reset = True
            try:
                attack_result = weapon_profile.attack(
                    target_unit,
                    model,
                    game_map=game_map,
                    attack_context=attack_context,
                    attacks_override=attacks_override,
                    attacks_override_modifiers=attacks_override_modifiers,
                    attacks_override_note=attacks_override_note,
                )
                executed_declarations.append(
                    _melee_declaration_diagnostic(
                        target_unit=target_unit,
                        model=model,
                        weapon_profile=weapon_profile,
                        reason="executed",
                        attacks_executed=int(getattr(attack_result, "attacks_rolled", 0) or 0),
                        damage_dealt=int(getattr(attack_result, "total_damage_dealt", 0) or 0),
                        models_killed=int(getattr(attack_result, "models_killed", 0) or 0),
                    )
                )
            finally:
                if provider_reset:
                    self.game.install_decision_providers(damage_allocation_provider=base_provider)

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
            "killing_models_by_target": killing_models_by_target,
            "damage_by_target": damage_by_target,
            "successful_attacks": sum(int(row.get("attacks_executed", 0) or 0) for row in executed_declarations),
            "declaration_count": len(list(weapon_declarations or [])),
            "executed_declarations": executed_declarations,
            "skipped_declarations": skipped_declarations,
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
