from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from enum import Enum
import html
import re
import logging
import copy
import math
from .event_system import EventSystem
from .map import Map, Objective
from .mission_cards import PrimaryMissionCard, SecondaryMissionCard
from .player import Player
from .unit import Unit
from .model import Model
from ..utility.calcs import get_dist, clear_enemy_model_cache
from ..utility.dice import DiceCollection, get_roll
from ..utility.constants import TOTAL_ROUNDS, ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .army_muster import ArmyMusterRequest

class SetupPhase(Enum):
    """
    The phases of the setup phase.
    """
    MUSTER_ARMIES = 0
    SELECT_MISSION_OBJECTIVES = 1
    CREATE_BATTLEFIELD = 2  # Place terrain, objectives, etc.
    DETERMINE_ATTACKER_AND_DEFENDER = 3
    DECLARE_BATTLE_FORMATIONS = 4  # Attach leaders to units if you want; declare reserve; declare embarked unts
    DEPLOY_ARMIES = 5
    REDEPLOY_UNITS = 6
    DETERMINE_FIRST_TURN_ORDER = 7
    RESOLVE_PREBATTLE_RULES = 8  # Resolve any pre-battle rules, abilities, or stratagems


class BattleRoundPhases(Enum):
    """
    The phases of a battle round.
    """
    COMMAND_PHASE = 0
    MOVEMENT_PHASE = 1
    SHOOTING_PHASE = 2
    CHARGE_PHASE = 3
    FIGHT_PHASE = 4


class BattlefieldSize(Enum):
    COMBAT_PATROL = "Combat Patrol"
    INCURSION = "Incursion"
    STRIKE_FORCE = "Strike Force"
    ONSLAUGHT = "Onslaught"


class Battlefield:
    SIZES: Dict[BattlefieldSize, Dict[str, Any]] = {
        BattlefieldSize.COMBAT_PATROL: {
            "width": 44,
            "height": 30,
            "points": 500,
            "command_points": 0,
            "detachments": 1
        },
        BattlefieldSize.INCURSION: {
            "width": 44,
            "height": 30,
            "points": 1000,
            "command_points": 0,
            "detachments": 2
        },
        BattlefieldSize.STRIKE_FORCE: {
            "width": 60,
            "height": 44,
            "points": 2000,
            "command_points": 0,
            "detachments": 3
        },
        BattlefieldSize.ONSLAUGHT: {
            "width": 90,
            "height": 44,
            "points": 3000,
            "command_points": 0,
            "detachments": 4
        }
    }

    def __init__(self, size: BattlefieldSize = None, width: int = None, height: int = None):
        if size:
            self.size = size
            self.width = self.SIZES[size]["width"]
            self.height = self.SIZES[size]["height"]
            self.points = self.SIZES[size]["points"]
            self.command_points = self.SIZES[size]["command_points"]
            self.detachments = self.SIZES[size]["detachments"]
        else:
            self.size = None
            self.width = width
            self.height = height
            self.points = None
            self.command_points = None
            self.detachments = None

    def __str__(self):
        return f"Battlefield({self.width}\" x {self.height}\")"


class Game:
    def __init__(self, battlefield: Battlefield, players: List[Player] | None = None):
        self.battlefield = battlefield
        # Avoid mutable default arg: always create a fresh list per Game instance.
        self.players = list(players) if players else []
        self.turn = 1
        self.current_player_index = 0
        self.map = Map(battlefield.width, battlefield.height)
        self.event_system = EventSystem()
        self.objectives = []
        self.commands = []
        self.phase = BattleRoundPhases.COMMAND_PHASE  # Initialize phase to COMMAND_PHASE
        self.do_ai_action = False  # Initialize AI action flag
        # Command phase timing: True only during the Battle-shock step of the current player's Command phase.
        self.battle_shock_step_active = False
        
        # Wire game reference into any pre-supplied players
        for p in self.players:
            p.set_game(self)

        # Install default rules subscribers (e.g. on-kill rewards)
        try:
            self._install_default_event_subscribers()
        except Exception:
            pass

        # Setup phase tracking
        self.setup_phase = SetupPhase.MUSTER_ARMIES  # Start with first setup phase
        self.setup_complete = False  # Track when setup is finished
        
        # Deployment tracking
        self.deployment_turn_index = 0  # Track whose turn it is to deploy (0 = defender, 1 = attacker)
        self.attacker_index = None  # Index of the attacking player (will be set during DETERMINE_ATTACKER_AND_DEFENDER)
        self.defender_index = None  # Index of the defending player (will be set during DETERMINE_ATTACKER_AND_DEFENDER)
        self.deployment_zones = {}  # Store deployment zones for visualization {player_name: zone_dict}
        self.waiting_for_deployment_input = False  # Flag for manual phases during deployment
        self.deployment_actions = {}  # Track last deployment action for each player
        # Deployment special rule tracking:
        # If a player deploys a TITANIC unit, they skip their next deployment turn (opponent deploys twice in a row).
        # Stored as {player_index: skip_count}.
        self.deployment_skip_turns: Dict[int, int] = {}
        # UI helper: short, human-readable notice explaining special deployment turn swaps.
        self.deployment_notice: str | None = None
        self.first_turn_player_index = None  # Index of player who goes first (will be set during DETERMINE_FIRST_TURN_ORDER)
        self.battle_round_starting_player_index = None  # Track who started the current battle round
        # Mission actions and event tracking
        self.in_progress_actions: List[Dict[str, Any]] = []
        self.destroyed_units_this_turn: List['Unit'] = []
        self.completed_actions_this_turn: List[Dict[str, Any]] = []
        self.models_destroyed_this_turn: List['Model'] = []
        self.destroyed_units_this_battle_round_by_player: Dict[Player, int] = {}
        # Phase-scoped targeting tracking (for rules like Thrill Seekers).
        # Track attack targets separately from charge targets so abilities can opt in to either.
        self.phase_targeted_units: Dict[str, set[str]] = {}
        self.phase_charge_targets: Dict[str, set[str]] = {}
        # Aeldari: Phoenix Gem pending returns (processed at end of the phase they were destroyed in)
        self._phoenix_gem_pending: List[Dict[str, Any]] = []
        # World Eaters: Blood Surge shooting snapshots (attacker -> {target: model_count})
        self._blood_surge_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        # World Eaters: Frenzy (Helbrute) target snapshots (attacker -> [targets])
        self._frenzy_shooting_targets: Dict['Unit', List['Unit']] = {}
        self._frenzy_fight_targets: Dict['Unit', List['Unit']] = {}
        # Drukhari: Pain Parasite snapshots (attacker -> {target: model_count})
        self._pain_parasite_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        self._pain_parasite_fight_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        # Optional in-engine army mustering requests (player1/player2) for setup phase.
        self.army_muster_requests: Dict[str, Any] = {}

    def _install_default_event_subscribers(self) -> None:
        """Install non-UI rule subscribers that operate off the event system."""
        self.event_system.subscribe("model_destroyed", self._on_model_destroyed_rules)
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_rules)
        # World Eaters: Icon of Khorne (Bloodshed points)
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_bloodshed_points)
        # World Eaters: Blood Tithe (Khorne Daemonkin detachment)
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_blood_tithe)
        # Transport core rules (Destroyed Transport -> Disembark + mortals + battleshock)
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_transport_rules)
        # Detachment abilities that trigger on unit movement events
        self.event_system.subscribe("unit_move_ended", self._on_unit_move_ended_detachment_rules)
        # Datasheet abilities that trigger on charge-move end
        self.event_system.subscribe("unit_move_ended", self._on_unit_move_ended_charge_mortal_wounds)
        # Battle Focus triggers (fall back reactions, fight selection, shooting reactions)
        self.event_system.subscribe("unit_move_started", self._on_unit_move_started_battle_focus)
        self.event_system.subscribe("unit_move_ended", self._on_unit_move_ended_battle_focus)
        self.event_system.subscribe("fight_unit_selected", self._on_fight_unit_selected_battle_focus)
        self.event_system.subscribe("unit_shooting_resolved", self._on_unit_shooting_resolved_battle_focus)
        # Aeldari: Aspect Shrine Token prompt suppression resets after activation
        self.event_system.subscribe("unit_shooting_resolved", self._on_unit_shooting_resolved_aspect_shrine)
        self.event_system.subscribe("fight_sequence_complete", self._on_fight_sequence_complete_aspect_shrine)
        # Phase-level target tracking (Thrill Seekers)
        self.event_system.subscribe("phase_start", self._on_phase_start_target_tracking)
        self.event_system.subscribe("shooting_targets_selected", self._on_shooting_targets_selected_tracking)
        self.event_system.subscribe("charge_declared", self._on_charge_declared_tracking)
        # Dark Pacts trigger windows
        self.event_system.subscribe("shooting_targets_selected", self._on_shooting_targets_selected_dark_pacts)
        self.event_system.subscribe("fight_unit_selected", self._on_fight_unit_selected_dark_pacts)
        # Imperial Knights: Code Chivalric reroll windows
        self.event_system.subscribe("shooting_targets_selected", self._on_shooting_targets_selected_code_chivalric)
        self.event_system.subscribe("fight_unit_selected", self._on_fight_unit_selected_code_chivalric)
        self.event_system.subscribe("unit_shooting_resolved", self._on_unit_shooting_resolved_code_chivalric)
        self.event_system.subscribe("fight_sequence_complete", self._on_fight_sequence_complete_code_chivalric)
        self.event_system.subscribe("model_destroyed", self._on_model_destroyed_code_chivalric)
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_code_chivalric)
        # Adeptus Custodes: Martial Ka'tah selection on fight activation
        self.event_system.subscribe("fight_unit_selected", self._on_fight_unit_selected_martial_katah)
        # Emperor's Children: detachment rule hooks
        self.event_system.subscribe("battle_round_started", self._on_battle_round_started_emperors_children)
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_emperors_children)
        self.event_system.subscribe("unit_shooting_resolved", self._on_unit_shooting_resolved_emperors_children)
        self.event_system.subscribe("fight_attacks_resolved", self._on_fight_attacks_resolved_emperors_children)
        self.event_system.subscribe("fight_unit_selected", self._on_fight_unit_selected_emperors_children)
        self.event_system.subscribe("fight_targets_selected", self._on_fight_targets_selected_tracking)
        # Drukhari: Power from Pain trigger windows
        self.event_system.subscribe("shooting_targets_selected", self._on_shooting_targets_selected_power_from_pain)
        self.event_system.subscribe("fight_unit_selected", self._on_fight_unit_selected_power_from_pain)
        self.event_system.subscribe("unit_move_started", self._on_unit_move_started_power_from_pain)
        self.event_system.subscribe("charge_declared", self._on_charge_declared_power_from_pain)
        self.event_system.subscribe("phase_start", self._on_phase_start_power_from_pain)
        self.event_system.subscribe("phase_end", self._on_phase_end_power_from_pain)
        self.event_system.subscribe("unit_shooting_resolved", self._on_unit_shooting_resolved_power_from_pain)
        self.event_system.subscribe("fight_sequence_complete", self._on_fight_sequence_complete_power_from_pain)
        # World Eaters: Blood Surge trigger window
        self.event_system.subscribe("shooting_targets_selected", self._on_shooting_targets_selected_blood_surge)
        self.event_system.subscribe("unit_shooting_resolved", self._on_unit_shooting_resolved_blood_surge)
        # World Eaters: Frenzy (Helbrute)
        self.event_system.subscribe("shooting_targets_selected", self._on_shooting_targets_selected_frenzy)
        self.event_system.subscribe("fight_targets_selected", self._on_fight_targets_selected_frenzy)
        self.event_system.subscribe("unit_shooting_resolved", self._on_unit_shooting_resolved_frenzy)
        self.event_system.subscribe("fight_attacks_resolved", self._on_fight_attacks_resolved_frenzy)
        # Imperial Knights: Bondsman ongoing effects
        self.event_system.subscribe("phase_start", self._on_phase_start_bondsman)
        self.event_system.subscribe("unit_shooting_resolved", self._on_unit_shooting_resolved_bondsman)
        self.event_system.subscribe("fight_sequence_complete", self._on_fight_sequence_complete_bondsman)
        # Thousand Sons: Cabal of Sorcerers reset at Shooting phase start
        self.event_system.subscribe("phase_start", self._on_phase_start_cabal_of_sorcerers)
        # T'au Empire: For the Greater Good selection at Shooting phase start
        self.event_system.subscribe("phase_start", self._on_phase_start_for_the_greater_good)
        # Temporary effects cleanup (e.g. once-per-battle abilities that last "until end of phase")
        self.event_system.subscribe("phase_end", self._on_phase_end_cleanup)
        # T'au Empire: clear Spotted/Observer state at end of Shooting phase
        self.event_system.subscribe("phase_end", self._on_phase_end_for_the_greater_good)
        # Optional ability timing windows (prompt/decision hooks)
        self.event_system.subscribe("phase_start", self._on_phase_start_optional_abilities)
        # Astra Militarum: Voice of Command issue windows
        self.event_system.subscribe("phase_start", self._on_phase_start_voice_of_command)
        self.event_system.subscribe("phase_end", self._on_phase_end_voice_of_command)
        # Grey Knights: Gate of Infinity (end of opponent's Fight phase)
        self.event_system.subscribe("phase_end", self._on_phase_end_gate_of_infinity)
        # Belakor: Pall of Despair healing on failed Battle-shock tests
        self.event_system.subscribe("battle_shock_test_resolved", self._on_battle_shock_test_resolved_shadow_form)
        # Chaos Knights: Harbingers of Dread (Delirium) on failed Battle-shock tests
        self.event_system.subscribe("battle_shock_test_resolved", self._on_battle_shock_test_resolved_harbingers)
        # Astra Militarum: Voice of Command clears on battle-shock
        self.event_system.subscribe("battle_shock_test_resolved", self._on_battle_shock_test_resolved_voice_of_command)
        # Drukhari: Power from Pain token gain hooks
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_power_from_pain)
        self.event_system.subscribe("battle_shock_test_resolved", self._on_battle_shock_test_resolved_power_from_pain)
        # Genestealer Cults: Cult Ambush (unit destruction + marker clearance)
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_cult_ambush)
        self.event_system.subscribe("unit_move_ended", self._on_unit_move_ended_cult_ambush)
        # Adepta Sororitas: Acts of Faith (Miracle dice gains)
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_acts_of_faith)
        self.event_system.subscribe("model_destroyed_before_removal", self._on_model_destroyed_acts_of_faith)

    def _apply_pall_of_despair_forced_tests(self, current_player, tested_ids: set[str]) -> None:
        if current_player is None:
            return
        try:
            from .shadow_form import shadow_form_sources_with_active_key, KEY_PALL
            from ..utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return

        try:
            enemies = [p for p in (self.players or []) if p is not current_player]
        except Exception:
            enemies = []
        current_army = getattr(current_player, "army", None)
        if current_army is None:
            return
        for enemy_player in enemies:
            army = getattr(enemy_player, "army", None)
            if army is None:
                continue
            sources = shadow_form_sources_with_active_key(army, KEY_PALL, game=self)
            if not sources:
                continue
            for unit in list(getattr(current_army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                        continue
                except Exception:
                    continue
                try:
                    if not bool(getattr(unit, "deployed", True)):
                        continue
                except Exception:
                    pass
                try:
                    uid = str(getattr(unit, "_id", None) or id(unit))
                except Exception:
                    uid = str(id(unit))
                if uid in tested_ids:
                    continue
                try:
                    if hasattr(unit, "is_below_starting_strength") and callable(unit.is_below_starting_strength):
                        if not unit.is_below_starting_strength():
                            continue
                    else:
                        continue
                except Exception:
                    continue
                for source in sources:
                    try:
                        if unit_within_range_of_unit(source, unit, 9.0, use_attached_aggregate=True):
                            unit.take_battle_shock_test(self.turn)
                            tested_ids.add(uid)
                            break
                    except Exception:
                        continue

    def _apply_harbingers_dismay_forced_tests(self, current_player, tested_ids: set[str]) -> None:
        if current_player is None:
            return
        try:
            from .harbingers_of_dread import DISMAY
            from ..utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return

        try:
            enemies = [p for p in (self.players or []) if p is not current_player]
        except Exception:
            enemies = []
        current_army = getattr(current_player, "army", None)
        if current_army is None:
            return

        for enemy_player in enemies:
            army = getattr(enemy_player, "army", None)
            if army is None:
                continue
            mgr = getattr(army, "harbingers_of_dread", None)
            if mgr is None or not getattr(mgr, "_army_has_harbingers", lambda: False)():
                continue
            if not mgr.is_dread_active(DISMAY.key):
                continue
            aura_range = float(mgr.get_aura_range())
            sources = [u for u in list(getattr(army, "units", []) or []) if mgr._unit_is_valid_source(u)]
            if not sources:
                continue

            for unit in list(getattr(current_army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                        continue
                except Exception:
                    continue
                try:
                    if not bool(getattr(unit, "deployed", True)):
                        continue
                except Exception:
                    pass
                try:
                    uid = str(getattr(unit, "_id", None) or id(unit))
                except Exception:
                    uid = str(id(unit))
                if uid in tested_ids:
                    continue
                try:
                    if hasattr(unit, "is_below_starting_strength") and callable(unit.is_below_starting_strength):
                        if not unit.is_below_starting_strength():
                            continue
                    else:
                        continue
                except Exception:
                    continue

                for source in sources:
                    try:
                        if unit_within_range_of_unit(source, unit, aura_range, use_attached_aggregate=True):
                            unit.take_battle_shock_test(self.turn)
                            tested_ids.add(uid)
                            break
                    except Exception:
                        continue

    def _apply_reanimation_protocols_end_command_phase(self, current_player) -> None:
        if current_player is None:
            return
        try:
            army = current_player.get_army()
        except Exception:
            army = getattr(current_player, "army", None)
        if army is None:
            return
        game_map = getattr(self, "map", None)
        provider = getattr(game_map, "reanimation_allocation_provider", None) if game_map is not None else None
        try:
            is_human = bool(getattr(getattr(current_player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False

        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                uid = str(getattr(root, "_id", None) or id(root))
            except Exception:
                uid = str(id(root))
            if uid in seen:
                continue
            seen.add(uid)

            try:
                if not getattr(root, "deployed", True):
                    continue
                if str(getattr(root, "reserve_status", "deployed")) != "deployed":
                    continue
                if hasattr(root, "is_in_reserves") and callable(getattr(root, "is_in_reserves")):
                    if bool(root.is_in_reserves()):
                        continue
                if bool(getattr(root, "embarked_in", None)):
                    continue
                if bool(getattr(root, "is_embarked", False)):
                    continue
            except Exception:
                pass

            try:
                if hasattr(root, "is_alive") and callable(getattr(root, "is_alive")) and not root.is_alive():
                    continue
            except Exception:
                pass

            try:
                if not root.attached_unit_has_reanimation_protocols():
                    continue
            except Exception:
                continue

            try:
                d3 = int(get_roll("D3") or 0)
            except Exception:
                d3 = 0
            if d3 <= 0:
                continue
            try:
                root.apply_reanimation_protocols(d3, game_map=game_map, is_human=is_human, provider=provider)
            except Exception:
                continue

    def _apply_command_phase_regain_wounds(self, current_player) -> None:
        if current_player is None:
            return
        try:
            army = current_player.get_army()
        except Exception:
            army = getattr(current_player, "army", None)
        if army is None:
            return

        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                    continue
            except Exception:
                pass
            try:
                if not bool(getattr(unit, "deployed", True)):
                    continue
            except Exception:
                pass
            try:
                if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                    continue
            except Exception:
                pass
            try:
                if hasattr(unit, "is_in_reserves") and callable(unit.is_in_reserves):
                    if bool(unit.is_in_reserves()):
                        continue
            except Exception:
                pass

            models = list(getattr(unit, "models", []) or [])
            if not models:
                continue
            for model in models:
                try:
                    if not bool(getattr(model, "is_alive", True)):
                        continue
                except Exception:
                    continue
                try:
                    base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
                    current_wounds = int(getattr(model, "wounds", 0) or 0)
                except Exception:
                    continue
                if base_wounds <= 0 or current_wounds <= 0 or current_wounds >= base_wounds:
                    continue
                try:
                    amount = int(unit.get_command_phase_regain_wound_amount(model) or 0)
                except Exception:
                    amount = 0
                if amount <= 0:
                    continue
                try:
                    model.heal(amount)
                except Exception:
                    try:
                        model.wounds = min(base_wounds, current_wounds + amount)
                    except Exception:
                        pass

    def _maybe_prompt_shadow_in_the_warp(self) -> None:
        es = getattr(self, "event_system", None)
        subs = getattr(es, "subscribers", {}) if es is not None else {}
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            try:
                army = player.get_army()
            except Exception:
                army = getattr(player, "army", None)
            if army is None:
                continue
            mgr = getattr(army, "shadow_in_the_warp", None)
            if mgr is None:
                continue
            try:
                if not mgr.can_use_now(game=self, player=player):
                    continue
            except Exception:
                continue
            try:
                is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
            except Exception:
                is_human = False
            if is_human and es is not None and isinstance(subs, dict) and subs.get("shadow_in_the_warp_prompt"):
                es.publish("shadow_in_the_warp_prompt", player=player, game=self)
                continue
            ctx = {
                "ability_name": "Shadow in the Warp",
                "phase": "Command phase",
            }
            try:
                if player._should_use_optional_ability("SHADOW_IN_THE_WARP", ctx):
                    mgr.activate(game=self, player=player)
            except Exception:
                continue

    def _maybe_prompt_waaagh(self) -> None:
        es = getattr(self, "event_system", None)
        subs = getattr(es, "subscribers", {}) if es is not None else {}
        try:
            player = self.get_current_player()
        except Exception:
            player = None
        if player is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = getattr(player, "army", None)
        if army is None:
            return
        mgr = getattr(army, "waaagh", None)
        if mgr is None:
            return
        try:
            if not mgr.can_call_now(game=self, player=player):
                return
        except Exception:
            return
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human and es is not None and isinstance(subs, dict) and subs.get("waaagh_prompt"):
            es.publish("waaagh_prompt", player=player, game=self)
            return
        ctx = {
            "ability_name": "Waaagh!",
            "phase": "Command phase",
        }
        try:
            should = bool(player._should_use_optional_ability("WAAAGH", ctx))
        except Exception:
            should = True
        if should:
            mgr.call_waaagh(game=self, player=player)

    def _on_battle_shock_test_resolved_shadow_form(self, unit=None, passed: bool = True, **_kwargs) -> None:
        if passed is True or unit is None:
            return
        try:
            if self.phase != BattleRoundPhases.COMMAND_PHASE:
                return
        except Exception:
            return
        try:
            current_player = self.get_current_player()
        except Exception:
            current_player = None
        if current_player is None:
            return
        try:
            unit_army = unit.get_parent_army()
        except Exception:
            unit_army = None
        if unit_army is None or getattr(unit_army, "player", None) is not current_player:
            return
        try:
            if hasattr(unit, "is_below_starting_strength") and callable(getattr(unit, "is_below_starting_strength")):
                if not unit.is_below_starting_strength():
                    return
            else:
                return
        except Exception:
            return
        try:
            from .shadow_form import shadow_form_sources_with_active_key, apply_pall_of_despair_heal, KEY_PALL
            from ..utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return

        try:
            enemies = [p for p in (self.players or []) if p is not current_player]
        except Exception:
            enemies = []

        for enemy_player in enemies:
            army = getattr(enemy_player, "army", None)
            if army is None:
                continue
            sources = shadow_form_sources_with_active_key(army, KEY_PALL, game=self)
            if not sources:
                continue
            for source in sources:
                try:
                    if unit_within_range_of_unit(source, unit, 9.0, use_attached_aggregate=True):
                        healed = apply_pall_of_despair_heal(source)
                        if healed > 0:
                            print(f"Shadow Form: {getattr(source, 'name', 'Model')} regains up to {healed} lost wounds (Pall of Despair).")
                except Exception:
                    continue

    def _on_battle_shock_test_resolved_harbingers(self, unit=None, passed: bool = True, **_kwargs) -> None:
        if passed is True or unit is None:
            return
        try:
            if not unit.is_below_half_strength():
                return
        except Exception:
            return
        try:
            unit_army = unit.get_parent_army()
        except Exception:
            unit_army = None
        if unit_army is None:
            return

        try:
            from .harbingers_of_dread import DELIRIUM
            from ..utility.aura_utils import unit_within_range_of_unit
            from ..utility.dice import get_roll
        except Exception:
            return

        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        try:
            enemies = [p for p in (self.players or []) if getattr(p, "army", None) is not unit_army]
        except Exception:
            enemies = []

        for enemy_player in enemies:
            army = getattr(enemy_player, "army", None)
            if army is None:
                continue
            mgr = getattr(army, "harbingers_of_dread", None)
            if mgr is None or not getattr(mgr, "_army_has_harbingers", lambda: False)():
                continue
            if not mgr.is_dread_active(DELIRIUM.key):
                continue
            aura_range = float(mgr.get_aura_range())
            for source in list(getattr(army, "units", []) or []):
                if not mgr._unit_is_valid_source(source):
                    continue
                try:
                    if unit_within_range_of_unit(source, unit, aura_range, use_attached_aggregate=True):
                        d3 = int(get_roll("D3") or 0)
                        try:
                            unit._apply_mortal_wounds_to_unit(unit, d3, game_map=game_map)
                        except Exception:
                            pass
                        print(f"Harbingers of Dread: {getattr(unit, 'name', 'Unit')} suffers {d3} mortal wounds (Delirium).")
                        return
                except Exception:
                    continue

    def _on_battle_shock_test_resolved_voice_of_command(self, unit=None, passed: bool = True, **_kwargs) -> None:
        if unit is None or passed:
            return
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            mgr.clear_order(root)
        except Exception:
            pass
        try:
            for leader in list(getattr(root, "attached_leaders", []) or []):
                mgr.clear_order(leader)
        except Exception:
            pass

    def _on_battle_shock_test_resolved_power_from_pain(self, unit=None, passed: bool = True, **_kwargs) -> None:
        if unit is None or passed:
            return
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "army", None)
            mgr = getattr(army, "power_from_pain", None) if army is not None else None
            if mgr is None:
                continue
            try:
                mgr.on_enemy_battle_shock_failed(unit)
            except Exception:
                continue

    # ---------------- Phoenix Gem (Warhost) ----------------

    def queue_phoenix_gem_return(
        self,
        *,
        unit=None,
        model=None,
        position=None,
        phase_name: str | None = None,
        game_map=None,
    ) -> None:
        if unit is None or model is None:
            return
        payload = {
            "unit": unit,
            "model": model,
            "position": position,
            "phase_name": str(phase_name or "").strip().upper(),
            "game_map": game_map,
        }
        self._phoenix_gem_pending.append(payload)

    def _phoenix_gem_in_engagement_range(self, unit, candidate_base, game_map) -> bool:
        if unit is None or candidate_base is None or game_map is None:
            return False
        try:
            from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
        except Exception:
            return False
        for enemy in list(game_map.get_enemy_units(unit) or []):
            try:
                models = enemy.get_models_for_collision()
            except Exception:
                models = getattr(enemy, "models", []) or []
            for em in list(models or []):
                try:
                    if not getattr(em, "is_alive", True):
                        continue
                except Exception:
                    pass
                try:
                    h = float(horizontal_distance_between_bases_2d(candidate_base, em.model_base))
                    v = float(vertical_distance_between_bases(candidate_base, em.model_base))
                except Exception:
                    continue
                if h <= float(ENGAGEMENT_RANGE_HORIZONTAL) and v <= float(ENGAGEMENT_RANGE_VERTICAL):
                    return True
        return False

    def _find_phoenix_gem_position(self, unit, model, position, game_map):
        if unit is None or model is None or position is None or game_map is None:
            return None
        try:
            x0, y0, z0, f0 = position
        except Exception:
            return None

        def _valid(x, y, z, facing) -> bool:
            temp_added = False
            try:
                if not list(getattr(unit, "models", []) or []):
                    unit.models.append(model)
                    temp_added = True
                if not game_map.is_within_boundary(model, (x, y)):
                    return False
                if game_map.check_collision_with_obstacles(model, (x, y)):
                    return False
                if game_map.check_collision_with_other_friendly_units(model, (x, y)):
                    return False
                if game_map.check_collision_with_other_enemy_units(model, (x, y)):
                    return False
            except Exception:
                return False
            finally:
                if temp_added:
                    try:
                        unit.models.remove(model)
                    except Exception:
                        pass
            try:
                candidate_base = unit._create_potential_base(x, y, z, facing, model=model)
            except Exception:
                return False
            if self._phoenix_gem_in_engagement_range(unit, candidate_base, game_map):
                return False
            return True

        if _valid(x0, y0, z0, f0):
            return (x0, y0, z0, f0)

        max_radius = 12.0
        step = 0.5
        angles = [i * (math.pi / 8.0) for i in range(16)]
        radius = step
        while radius <= max_radius:
            for ang in angles:
                x = x0 + math.cos(ang) * radius
                y = y0 + math.sin(ang) * radius
                if _valid(x, y, z0, f0):
                    return (x, y, z0, f0)
            radius += step
        return None

    def _resolve_phoenix_gem_return(self, payload: Dict[str, Any]) -> None:
        unit = payload.get("unit")
        model = payload.get("model")
        if unit is None or model is None:
            return
        try:
            roll = int(get_roll("D6"))
        except Exception:
            roll = 1
        try:
            print(f"✨ Phoenix Gem: rolled {roll} to return {getattr(model, 'name', 'bearer')}")
        except Exception:
            pass
        if roll < 2:
            try:
                print("❌ Phoenix Gem failed; bearer remains destroyed.")
            except Exception:
                pass
            return

        game_map = payload.get("game_map") or getattr(self, "map", None)
        if game_map is None:
            return

        placement = self._find_phoenix_gem_position(unit, model, payload.get("position"), game_map)
        if placement is None:
            try:
                print("❌ Phoenix Gem: no valid placement found; bearer remains destroyed.")
            except Exception:
                pass
            try:
                unit.models.remove(model)
            except Exception:
                pass
            try:
                unit.models_lost.append(model)
            except Exception:
                pass
            return

        try:
            if model not in list(getattr(unit, "models", []) or []):
                unit.models.append(model)
        except Exception:
            return
        try:
            lost = getattr(unit, "models_lost", None)
            if isinstance(lost, list) and model in lost:
                lost.remove(model)
        except Exception:
            pass
        try:
            model.set_parent_unit(unit)
        except Exception:
            pass
        try:
            model._wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)))
        except Exception:
            pass
        try:
            model.set_location(placement[0], placement[1], placement[2], placement[3])
        except Exception:
            pass
        try:
            if unit not in list(getattr(game_map, "units", []) or []):
                game_map.units.append(unit)
        except Exception:
            pass
        try:
            unit.deployed = True
            unit.reserve_status = "deployed"
        except Exception:
            pass
        try:
            if hasattr(unit, "update_coherency"):
                unit.update_coherency()
        except Exception:
            pass
        try:
            print(f"✅ Phoenix Gem: {getattr(unit, 'name', 'bearer')} returns to the battlefield.")
        except Exception:
            pass

    def _on_phase_start_target_tracking(self, player=None, phase=None, **_kwargs) -> None:
        """Reset phase-scoped target tracking at the start of each phase."""
        self.phase_targeted_units = {}
        self.phase_charge_targets = {}
        self._frenzy_shooting_targets = {}
        self._frenzy_fight_targets = {}

    def _record_phase_target(self, target_unit=None, attacker_unit=None) -> None:
        if target_unit is None or attacker_unit is None:
            return
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        target_id = getattr(target_root, "_id", None)
        attacker_id = getattr(attacker_unit, "_id", None)
        if not target_id or not attacker_id:
            return
        bucket = self.phase_targeted_units.setdefault(target_id, set())
        bucket.add(attacker_id)

    def _record_phase_charge_target(self, target_unit=None, attacker_unit=None) -> None:
        if target_unit is None or attacker_unit is None:
            return
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        target_id = getattr(target_root, "_id", None)
        attacker_id = getattr(attacker_unit, "_id", None)
        if not target_id or not attacker_id:
            return
        bucket = self.phase_charge_targets.setdefault(target_id, set())
        bucket.add(attacker_id)

    def _on_shooting_targets_selected_tracking(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        for t in list(target_units or []):
            self._record_phase_target(t, attacking_unit)

    def _on_charge_declared_tracking(self, unit=None, target_unit=None, **_kwargs) -> None:
        self._record_phase_charge_target(target_unit, unit)

    def _on_shooting_targets_selected_dark_pacts(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not list(target_units or []):
            return
        try:
            phase_name = str(getattr(self.phase, "name", "") or "")
        except Exception:
            phase_name = ""
        try:
            player = attacking_unit.get_parent_army().player
        except Exception:
            player = None
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human and es is not None:
            try:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("dark_pacts_prompt"):
                    es.publish(
                        "dark_pacts_prompt",
                        player=player,
                        unit=attacking_unit,
                        phase_name=phase_name,
                        trigger="shooting",
                        game=self,
                    )
                    return
            except Exception:
                pass
        try:
            attacking_unit.maybe_trigger_dark_pacts(self, phase_name=phase_name, trigger="shooting")
        except Exception:
            return

    def _on_shooting_targets_selected_code_chivalric(self, attacking_unit=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        try:
            army = attacking_unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "code_chivalric", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.on_unit_selected_to_shoot(attacking_unit)
        except Exception:
            return

    def _on_fight_unit_selected_dark_pacts(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            phase_name = str(getattr(self.phase, "name", "") or "")
        except Exception:
            phase_name = ""
        try:
            player = unit.get_parent_army().player
        except Exception:
            player = None
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human and es is not None:
            try:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("dark_pacts_prompt"):
                    es.publish(
                        "dark_pacts_prompt",
                        player=player,
                        unit=unit,
                        phase_name=phase_name,
                        trigger="fight",
                        game=self,
                    )
                    return
            except Exception:
                pass
        try:
            unit.maybe_trigger_dark_pacts(self, phase_name=phase_name, trigger="fight")
        except Exception:
            return

    def _on_fight_unit_selected_code_chivalric(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "code_chivalric", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.on_unit_selected_to_fight(unit)
        except Exception:
            return

    def _on_unit_shooting_resolved_code_chivalric(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            army = attacker_unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "code_chivalric", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.on_unit_shooting_resolved(attacker_unit)
        except Exception:
            return

    def _on_fight_sequence_complete_code_chivalric(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "code_chivalric", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.on_fight_sequence_complete(unit)
        except Exception:
            return

    def _on_model_destroyed_code_chivalric(self, target_model=None, **_kwargs) -> None:
        if target_model is None:
            return
        for player in list(getattr(self, "players", []) or []):
            army = getattr(player, "get_army", lambda: None)()
            mgr = getattr(army, "code_chivalric", None) if army is not None else None
            if mgr is None:
                continue
            try:
                mgr.on_model_destroyed(target_model)
            except Exception:
                continue

    def _on_unit_destroyed_code_chivalric(self, unit=None, destroyed_by_unit=None, **_kwargs) -> None:
        if unit is None or destroyed_by_unit is None:
            return
        try:
            if unit.get_parent_army() == destroyed_by_unit.get_parent_army():
                return
        except Exception:
            return
        try:
            army = destroyed_by_unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "code_chivalric", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.record_enemy_unit_destroyed()
        except Exception:
            return

    def _on_fight_unit_selected_martial_katah(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            if not root.attached_unit_has_martial_katah():
                return
        except Exception:
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        try:
            phase_name = str(getattr(self.phase, "name", "") or "")
        except Exception:
            phase_name = ""
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human and es is not None:
            try:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("martial_katah_prompt"):
                    es.publish(
                        "martial_katah_prompt",
                        player=player,
                        unit=root,
                        phase_name=phase_name,
                        game=self,
                    )
                    return
            except Exception:
                pass
        try:
            import random
            choice = random.choice(["DACATARAI", "RENDAX"])
            root.set_martial_katah_choice(choice)
        except Exception:
            return

    def _on_battle_round_started_emperors_children(self, game=None, battle_round: int = 0, **_kwargs) -> None:
        game = game or self
        try:
            br = int(battle_round or getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        if br <= 0:
            return
        for player in list(getattr(game, "players", []) or []):
            if player is None:
                continue
            try:
                army = player.get_army()
            except Exception:
                army = None
            if army is None:
                continue
            mgr = getattr(army, "emperors_children", None)
            if mgr is None:
                continue
            try:
                mgr.on_battle_round_start(game)
            except Exception:
                pass
            if not getattr(mgr, "is_coterie_of_conceited", lambda: False)():
                continue
            # Pledge target selection (if Warlord on battlefield)
            max_units = 0
            try:
                opponents = [p for p in list(getattr(game, "players", []) or []) if p is not player]
            except Exception:
                opponents = []
            for opp in opponents:
                try:
                    opp_army = opp.get_army()
                    max_units += len(list(getattr(opp_army, "units", []) or []))
                except Exception:
                    continue
            if max_units <= 0:
                max_units = 1
            try:
                mgr.pledge_max_units = int(max_units)
            except Exception:
                pass
            if not getattr(mgr, "warlord_on_battlefield", lambda: False)():
                try:
                    mgr.set_pledge_target(0, battle_round=br, max_value=max_units)
                except Exception:
                    pass
                continue
            try:
                is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
            except Exception:
                is_human = False
            if is_human and getattr(self, "event_system", None) is not None:
                try:
                    subs = getattr(self.event_system, "subscribers", {})
                    if isinstance(subs, dict) and subs.get("emperors_children_pledge_prompt"):
                        self.event_system.publish(
                            "emperors_children_pledge_prompt",
                            player=player,
                            game=game,
                            battle_round=br,
                            max_value=int(max_units),
                            default_value=1,
                            manager=mgr,
                        )
                        continue
                except Exception:
                    pass
            try:
                import random
                pledge = random.randint(1, int(max_units))
                mgr.set_pledge_target(pledge, battle_round=br, max_value=max_units)
            except Exception:
                pass

    def _on_unit_destroyed_emperors_children(self, unit=None, destroyed_by_unit=None, **_kwargs) -> None:
        if unit is None or destroyed_by_unit is None:
            return
        try:
            if unit.get_parent_army() == destroyed_by_unit.get_parent_army():
                return
        except Exception:
            return
        try:
            army = destroyed_by_unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "emperors_children", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.record_enemy_unit_destroyed(unit, destroyed_by_unit, game=self)
        except Exception:
            pass

    def _on_unit_shooting_resolved_emperors_children(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            army = attacker_unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "emperors_children", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.resolve_pending_favoured_champions(attacker_unit, game=self)
        except Exception:
            pass

    def _on_fight_attacks_resolved_emperors_children(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "emperors_children", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.resolve_pending_favoured_champions(unit, game=self)
        except Exception:
            pass

    def _on_fight_unit_selected_emperors_children(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "emperors_children", None) if army is not None else None
        if mgr is None:
            return
        try:
            charged = bool(getattr(getattr(root, "round_state", None), "charged_this_round", False))
        except Exception:
            charged = False

        # Exquisite Swordsmanship (Peerless Bladesmen): choose Lethal or Sustained on charge.
        if charged and getattr(mgr, "exquisite_swordsmanship_applies", lambda _u: False)(root):
            try:
                player = root.get_parent_army().player
            except Exception:
                player = None
            try:
                is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
            except Exception:
                is_human = False
            if is_human and getattr(self, "event_system", None) is not None:
                try:
                    subs = getattr(self.event_system, "subscribers", {})
                    if isinstance(subs, dict) and subs.get("emperors_children_exquisite_prompt"):
                        self.event_system.publish(
                            "emperors_children_exquisite_prompt",
                            player=player,
                            unit=root,
                            phase_name=str(getattr(self.phase, "name", "") or ""),
                            game=self,
                        )
                        return
                except Exception:
                    pass
            try:
                import random
                choice = random.choice(["LETHAL", "SUSTAINED"])
                root.set_exquisite_swordsmanship_choice(choice)
            except Exception:
                pass
            return

        # Sensational Performance (Court of the Phoenician): optional on charge.
        if charged and getattr(mgr, "sensational_performance_applies", lambda _u: False)(root):
            try:
                player = root.get_parent_army().player
            except Exception:
                player = None
            try:
                is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
            except Exception:
                is_human = False
            if is_human and getattr(self, "event_system", None) is not None:
                try:
                    subs = getattr(self.event_system, "subscribers", {})
                    if isinstance(subs, dict) and subs.get("emperors_children_sensational_prompt"):
                        self.event_system.publish(
                            "emperors_children_sensational_prompt",
                            player=player,
                            unit=root,
                            phase_name=str(getattr(self.phase, "name", "") or ""),
                            game=self,
                        )
                        return
                except Exception:
                    pass
            try:
                import random
                use_it = random.choice([True, False])
            except Exception:
                use_it = False
            if use_it:
                try:
                    sr = getattr(root, "special_rules", None)
                    if not isinstance(sr, dict):
                        sr = {}
                    sr["sensational_performance_active"] = True
                    sr["sensational_performance_expires_phase"] = "FIGHT_PHASE"
                    sr["sensational_performance_strength_bonus"] = 1
                    sr["sensational_performance_ap_bonus"] = 1
                    root.special_rules = sr
                except Exception:
                    pass
            try:
                from ..utility.event_bus import append_action
                pname = getattr(player, "name", "") if player is not None else ""
                if pname:
                    action = "activated" if use_it else "skipped"
                    append_action(pname, f"Sensational Performance: {getattr(root, 'name', 'Unit')} {action}.")
            except Exception:
                pass

    def _on_fight_targets_selected_tracking(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        for t in list(target_units or []):
            self._record_phase_target(t, attacking_unit)
        # Drukhari: Pain Parasite snapshot for fight sequences.
        try:
            army = attacking_unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "power_from_pain", None) if army is not None else None
        if mgr is None:
            return
        try:
            sr = getattr(attacking_unit, "special_rules", None)
            has_parasite = isinstance(sr, dict) and sr.get("pain_on_kill_heal")
        except Exception:
            has_parasite = False
        if not has_parasite:
            try:
                abilities = mgr.get_applicable_pain_ability_names(attacking_unit, trigger="fight", game=self)
            except Exception:
                abilities = []
            has_parasite = any(str(a or "").strip().lower() == "pain parasite" for a in abilities)
        if not has_parasite:
            return
        snapshot: Dict['Unit', int] = {}
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                models = target.get_models_for_collision()
            except Exception:
                models = list(getattr(target, "models", []) or [])
            try:
                count = sum(1 for m in models if getattr(m, "is_alive", False))
            except Exception:
                count = 0
            snapshot[target] = int(count)
        if snapshot:
            self._pain_parasite_fight_snapshot[attacking_unit] = snapshot

    def _on_shooting_targets_selected_power_from_pain(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not list(target_units or []):
            return
        try:
            player = attacking_unit.get_parent_army().player
        except Exception:
            player = None
        try:
            army = attacking_unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "power_from_pain", None) if army is not None else None
        if mgr is None:
            return
        abilities = mgr.get_applicable_pain_ability_names(attacking_unit, trigger="shooting", game=self)
        try:
            sr = getattr(attacking_unit, "special_rules", None)
            has_parasite = isinstance(sr, dict) and sr.get("pain_on_kill_heal")
        except Exception:
            has_parasite = False
        if not has_parasite:
            has_parasite = any(str(a or "").strip().lower() == "pain parasite" for a in abilities)
        if has_parasite:
            snapshot: Dict['Unit', int] = {}
            for target in list(target_units or []):
                if target is None:
                    continue
                try:
                    models = target.get_models_for_collision()
                except Exception:
                    models = list(getattr(target, "models", []) or [])
                try:
                    count = sum(1 for m in models if getattr(m, "is_alive", False))
                except Exception:
                    count = 0
                snapshot[target] = int(count)
            if snapshot:
                self._pain_parasite_shooting_snapshot[attacking_unit] = snapshot
        if not abilities:
            return
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human and es is not None:
            try:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("pain_token_prompt"):
                    es.publish(
                        "pain_token_prompt",
                        player=player,
                        unit=attacking_unit,
                        phase_name=str(getattr(self.phase, "name", "") or ""),
                        trigger="shooting",
                        abilities=list(abilities),
                        game=self,
                    )
                    return
            except Exception:
                pass
        try:
            mgr.maybe_empower_unit_for_trigger(attacking_unit, trigger="shooting", game=self)
        except Exception:
            return

    def _on_shooting_targets_selected_blood_surge(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not list(target_units or []):
            return
        if not self.is_shooting_phase():
            return

        snapshot: Dict['Unit', int] = {}
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                if not target.has_blood_surge():
                    continue
            except Exception:
                continue
            try:
                models = list(getattr(target, "models", []) or [])
                count = sum(1 for m in models if getattr(m, "is_alive", False))
            except Exception:
                count = 0
            snapshot[target] = int(count)

        if snapshot:
            self._blood_surge_shooting_snapshot[attacking_unit] = snapshot

    def _on_unit_shooting_resolved_blood_surge(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        if not self.is_shooting_phase():
            return
        snapshot = self._blood_surge_shooting_snapshot.pop(attacker_unit, None)
        if not snapshot:
            return

        for target_unit, before_count in list(snapshot.items()):
            if target_unit is None:
                continue
            try:
                models = list(getattr(target_unit, "models", []) or [])
                after_count = sum(1 for m in models if getattr(m, "is_alive", False))
            except Exception:
                after_count = int(before_count or 0)

            if int(after_count) >= int(before_count or 0):
                continue

            try:
                target_player = target_unit.get_parent_army().player
            except Exception:
                target_player = None
            if target_player is None:
                continue
            try:
                if target_player is self.get_current_player():
                    continue
            except Exception:
                pass

            try:
                if not target_unit.can_blood_surge(game=self, game_map=self.map):
                    continue
            except Exception:
                continue

            es = getattr(self, "event_system", None)
            try:
                if es is not None:
                    es.publish(
                        "blood_surge_triggered",
                        player=target_player,
                        unit=target_unit,
                        attacker_unit=attacker_unit,
                        phase_name=str(getattr(self.phase, "name", "") or "").replace("_", " ").title(),
                        game=self,
                    )
            except Exception:
                pass
            try:
                is_human = bool(getattr(getattr(target_player, "type", None), "name", "") == "HUMAN")
            except Exception:
                is_human = False
            if is_human and es is not None:
                try:
                    subs = getattr(es, "subscribers", {})
                    if isinstance(subs, dict) and subs.get("blood_surge_prompt"):
                        es.publish(
                            "blood_surge_prompt",
                            player=target_player,
                            unit=target_unit,
                            attacker_unit=attacker_unit,
                            phase_name=str(getattr(self.phase, "name", "") or ""),
                            game=self,
                        )
                        continue
                except Exception:
                    pass

            use_it = False
            try:
                if callable(getattr(target_player, "decision_hook", None)):
                    ctx = {
                        "unit": target_unit,
                        "attacker_unit": attacker_unit,
                        "phase_name": str(getattr(self.phase, "name", "") or ""),
                    }
                    use_it = bool(target_player._should_use_optional_ability("BLOOD_SURGE", ctx))
                else:
                    import random
                    use_it = bool(random.choice([True, False]))
            except Exception:
                use_it = False

            if not use_it:
                continue

            try:
                strat_mgr = getattr(target_player, "stratagems", None)
                if strat_mgr is not None:
                    wrath = strat_mgr.get_by_name("BERZERKER’S WRATH") or strat_mgr.get_by_name("BERZERKER'S WRATH")
                    if wrath is not None:
                        phase_name = str(getattr(self.phase, "name", "") or "").replace("_", " ").title()
                        can_wrath = False
                        try:
                            can_wrath = bool(strat_mgr.can_use(
                                wrath.name,
                                target_unit=target_unit,
                                attacker_unit=attacker_unit,
                                phase_name=phase_name or "Shooting phase",
                            ))
                        except Exception:
                            can_wrath = False
                        if can_wrath:
                            import random
                            if random.choice([True, False]):
                                strat_mgr.use(
                                    wrath.name,
                                    target_unit=target_unit,
                                    attacker_unit=attacker_unit,
                                    phase_name=phase_name or "Shooting phase",
                                    dequeue=True,
                                )
            except Exception:
                pass

            try:
                max_distance = int(self.roll_blood_surge_distance(target_unit) or 0)
            except Exception:
                max_distance = 0
            if max_distance <= 0:
                continue

            moved = False
            try:
                moved = bool(target_unit.auto_blood_surge_move(self.map, max_distance))
            except Exception:
                moved = False
            if moved:
                try:
                    target_unit.mark_blood_surge_used(self)
                except Exception:
                    pass

    def _on_shooting_targets_selected_frenzy(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not list(target_units or []):
            return
        if not self.is_shooting_phase():
            return
        self._frenzy_shooting_targets[attacking_unit] = list(target_units)

    def _on_fight_targets_selected_frenzy(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not list(target_units or []):
            return
        if not self.is_fight_phase():
            return
        self._frenzy_fight_targets[attacking_unit] = list(target_units)

    def _on_unit_shooting_resolved_frenzy(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        if not self.is_shooting_phase():
            return
        targets = self._frenzy_shooting_targets.pop(attacker_unit, None)
        if not targets:
            return
        for target_unit in list(targets):
            self._maybe_trigger_frenzy(target_unit, attacker_unit, phase_name="SHOOTING_PHASE")

    def _on_fight_attacks_resolved_frenzy(self, unit=None, target_unit=None, **_kwargs) -> None:
        if unit is None:
            return
        if not self.is_fight_phase():
            return
        targets = self._frenzy_fight_targets.pop(unit, None)
        if not targets and target_unit is not None:
            targets = [target_unit]
        if not targets:
            return
        for tgt in list(targets):
            self._maybe_trigger_frenzy(tgt, unit, phase_name="FIGHT_PHASE")

    def _maybe_trigger_frenzy(self, frenzy_unit=None, attacker_unit=None, *, phase_name: str = "") -> None:
        if frenzy_unit is None or attacker_unit is None:
            return
        try:
            if not frenzy_unit.is_alive():
                return
        except Exception:
            return
        try:
            if not frenzy_unit.has_frenzy():
                return
        except Exception:
            return
        try:
            if frenzy_unit.get_parent_army() == attacker_unit.get_parent_army():
                return
        except Exception:
            return

        options = self._frenzy_available_actions(frenzy_unit, attacker_unit, phase_name=phase_name)
        if not options:
            return

        try:
            player = frenzy_unit.get_parent_army().player
        except Exception:
            player = None
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False

        if is_human and es is not None:
            try:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("frenzy_prompt"):
                    es.publish(
                        "frenzy_prompt",
                        player=player,
                        unit=frenzy_unit,
                        attacker_unit=attacker_unit,
                        phase_name=str(phase_name or getattr(self.phase, "name", "") or ""),
                        options=list(options),
                        game=self,
                    )
                    return
            except Exception:
                pass

        if player is None:
            return

        ctx = {
            "unit": frenzy_unit,
            "attacker_unit": attacker_unit,
            "phase_name": str(phase_name or getattr(self.phase, "name", "") or ""),
            "options": list(options),
        }
        choice = None
        try:
            choice = player._choose_optional_value("FRENZY_ACTION", list(options), ctx)
        except Exception:
            choice = None
        if choice not in options:
            choice = None

        if choice is None:
            if "fight" in options:
                choice = "fight"
            elif "shoot" in options:
                choice = "shoot"

        if choice == "shoot":
            self._execute_frenzy_shooting(frenzy_unit, attacker_unit)
        elif choice == "fight":
            self._execute_frenzy_fight(frenzy_unit, attacker_unit, phase_name=phase_name)

    def _frenzy_available_actions(self, frenzy_unit, attacker_unit, *, phase_name: str = "") -> List[str]:
        if frenzy_unit is None or attacker_unit is None:
            return []
        try:
            if not frenzy_unit.is_alive():
                return []
        except Exception:
            return []
        try:
            if not attacker_unit.is_alive():
                return []
        except Exception:
            return []
        try:
            if frenzy_unit.get_parent_army() == attacker_unit.get_parent_army():
                return []
        except Exception:
            return []

        phase_key = str(phase_name or getattr(self.phase, "name", "") or "").strip().upper()
        if phase_key == "SHOOTING_PHASE":
            if not self.is_shooting_phase():
                return []
            try:
                attacker_player = attacker_unit.get_parent_army().player
                defender_player = frenzy_unit.get_parent_army().player
                if attacker_player is None or defender_player is None:
                    return []
                if self.get_current_player() is not attacker_player:
                    return []
                if attacker_player is defender_player:
                    return []
            except Exception:
                return []
        elif phase_key == "FIGHT_PHASE":
            if not self.is_fight_phase():
                return []
        else:
            return []

        options: List[str] = []
        if self._frenzy_has_eligible_shot(frenzy_unit, attacker_unit):
            options.append("shoot")
        if self._frenzy_can_fight_target(frenzy_unit, attacker_unit, phase_name=phase_key):
            options.append("fight")
        return options

    def _frenzy_can_fight_target(self, frenzy_unit, attacker_unit, *, phase_name: str = "") -> bool:
        if frenzy_unit is None or attacker_unit is None:
            return False
        game_map = getattr(self, "map", None)
        if game_map is None:
            return False
        try:
            if bool(getattr(attacker_unit, "is_aircraft", False)) and not bool(getattr(frenzy_unit, "is_flying", False)):
                return False
            if bool(getattr(frenzy_unit, "is_aircraft", False)) and not bool(getattr(attacker_unit, "is_flying", False)):
                return False
        except Exception:
            pass

        try:
            if game_map.is_within_engagement_range(frenzy_unit, attacker_unit):
                return True
        except Exception:
            pass

        if str(phase_name or "").strip().upper() != "FIGHT_PHASE":
            return False

        return self._frenzy_can_pile_in_to_target(frenzy_unit, attacker_unit)

    def _frenzy_can_pile_in_to_target(self, frenzy_unit, attacker_unit) -> bool:
        game_map = getattr(self, "map", None)
        if game_map is None:
            return False
        from ..utility.constants import PILE_IN_DISTANCE, ENGAGEMENT_RANGE_HORIZONTAL
        max_distance = PILE_IN_DISTANCE
        try:
            override = frenzy_unit.get_fight_phase_move_distance_override("pile_in")
            if override is not None:
                max_distance = float(override)
        except Exception:
            max_distance = PILE_IN_DISTANCE
        try:
            dist = float(game_map.get_distance_between_units(frenzy_unit, attacker_unit))
        except Exception:
            return False
        return dist <= (float(max_distance) + float(ENGAGEMENT_RANGE_HORIZONTAL) + 1e-6)

    def _frenzy_has_eligible_shot(self, frenzy_unit, attacker_unit) -> bool:
        game_map = getattr(self, "map", None)
        if game_map is None:
            return False
        try:
            models = list(getattr(frenzy_unit, "models", []) or [])
        except Exception:
            models = []
        for model in models:
            if not getattr(model, "is_alive", False):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                try:
                    if not wargear.is_ranged():
                        continue
                except Exception:
                    continue
                for profile in getattr(wargear, "profiles", {}).values():
                    try:
                        if frenzy_unit._can_model_shoot_weapon_at_target(model, profile, attacker_unit, game_map):
                            return True
                    except Exception:
                        continue
        return False

    def _build_frenzy_shooting_declarations(self, frenzy_unit, attacker_unit) -> List[dict]:
        game_map = getattr(self, "map", None)
        if game_map is None:
            return []
        profile_to_models: Dict[Any, List[Any]] = {}
        try:
            models = list(getattr(frenzy_unit, "models", []) or [])
        except Exception:
            models = []
        for model in models:
            if not getattr(model, "is_alive", False):
                continue
            best_profile = None
            best_score = -1.0
            for wargear in list(getattr(model, "wargear", []) or []):
                try:
                    if not wargear.is_ranged():
                        continue
                except Exception:
                    continue
                for profile in getattr(wargear, "profiles", {}).values():
                    try:
                        if not frenzy_unit._can_model_shoot_weapon_at_target(model, profile, attacker_unit, game_map):
                            continue
                    except Exception:
                        continue
                    try:
                        score = float(profile.get_damage_potential(attacker_unit))
                    except Exception:
                        score = 0.0
                    if score > best_score:
                        best_score = score
                        best_profile = profile
            if best_profile is not None:
                profile_to_models.setdefault(best_profile, []).append(model)

        declarations: List[dict] = []
        for profile, models in profile_to_models.items():
            declarations.append({
                "weapon_profile": profile,
                "target_unit": attacker_unit,
                "models": models,
            })
        return declarations

    def _execute_frenzy_shooting(self, frenzy_unit, attacker_unit) -> bool:
        declarations = self._build_frenzy_shooting_declarations(frenzy_unit, attacker_unit)
        if not declarations:
            return False
        try:
            return bool(frenzy_unit.execute_shooting_declarations(declarations, self.map, out_of_phase=True))
        except Exception:
            return False

    def _execute_frenzy_fight(self, frenzy_unit, attacker_unit, *, phase_name: str = "") -> bool:
        if not self._frenzy_can_fight_target(frenzy_unit, attacker_unit, phase_name=str(phase_name or "")):
            return False
        game_map = getattr(self, "map", None)
        if game_map is None:
            return False

        engaged = False
        try:
            engaged = bool(game_map.is_within_engagement_range(frenzy_unit, attacker_unit))
        except Exception:
            engaged = False

        moved = False
        try:
            moved = bool(frenzy_unit.pile_in_towards_enemies(game_map))
        except Exception:
            moved = False
        if not engaged and not moved:
            return False

        try:
            from .fight_phase_manager import FightPhaseManager
            mgr = FightPhaseManager(self)
            attacker_view = mgr._as_attached_view(frenzy_unit)
            declarations = mgr._auto_select_melee_weapons(attacker_view, attacker_unit)
        except Exception:
            declarations = []
        if not declarations:
            return False

        self.resolve_frenzy_melee_attacks(frenzy_unit, attacker_unit, declarations)

        try:
            frenzy_unit.consolidate_towards_enemies(game_map)
        except Exception:
            pass

        return True

    def resolve_frenzy_melee_attacks(self, frenzy_unit, target_unit, weapon_declarations: List[dict]) -> None:
        if frenzy_unit is None or target_unit is None:
            return
        if not weapon_declarations:
            return
        try:
            from .fight_phase_manager import FightPhaseManager
            mgr = getattr(self, "fight_phase_manager", None)
            if mgr is None:
                mgr = FightPhaseManager(self)
            attacker_view = mgr._as_attached_view(frenzy_unit)
            mgr._resolve_melee_attacks(attacker_view, target_unit, weapon_declarations)
        except Exception:
            return

    def _on_fight_unit_selected_power_from_pain(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            player = unit.get_parent_army().player
        except Exception:
            player = None
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "power_from_pain", None) if army is not None else None
        if mgr is None:
            return
        abilities = mgr.get_applicable_pain_ability_names(unit, trigger="fight", game=self)
        if not abilities:
            return
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human and es is not None:
            try:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("pain_token_prompt"):
                    es.publish(
                        "pain_token_prompt",
                        player=player,
                        unit=unit,
                        phase_name=str(getattr(self.phase, "name", "") or ""),
                        trigger="fight",
                        abilities=list(abilities),
                        game=self,
                    )
                    return
            except Exception:
                pass
        try:
            mgr.maybe_empower_unit_for_trigger(unit, trigger="fight", game=self)
        except Exception:
            return

    def _on_phase_start_bondsman(self, player=None, phase=None, **_kwargs) -> None:
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname != "FIGHT_PHASE":
            return
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "get_army", lambda: None)()
            mgr = getattr(army, "bondsman", None) if army is not None else None
            if mgr is None:
                continue
            try:
                mgr.on_fight_phase_start(game=self)
            except Exception:
                continue

    def _on_unit_shooting_resolved_bondsman(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            army = attacker_unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "bondsman", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.on_unit_shooting_resolved(attacker_unit, hits_by_target, game=self)
        except Exception:
            return

    def _on_fight_sequence_complete_bondsman(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "bondsman", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.on_fight_sequence_complete(unit, game=self)
        except Exception:
            return

    def _on_unit_move_started_power_from_pain(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        if (action or "").strip().lower() != "advance":
            return
        try:
            player = unit.get_parent_army().player
        except Exception:
            player = None
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "power_from_pain", None) if army is not None else None
        if mgr is None:
            return
        abilities = mgr.get_applicable_pain_ability_names(unit, trigger="advance", game=self)
        if not abilities:
            return
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human and es is not None:
            try:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("pain_token_prompt"):
                    es.publish(
                        "pain_token_prompt",
                        player=player,
                        unit=unit,
                        phase_name=str(getattr(self.phase, "name", "") or ""),
                        trigger="advance",
                        abilities=list(abilities),
                        game=self,
                    )
                    return
            except Exception:
                pass
        try:
            mgr.maybe_empower_unit_for_trigger(unit, trigger="advance", game=self)
        except Exception:
            return

    def _on_charge_declared_power_from_pain(self, unit=None, target_unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            player = unit.get_parent_army().player
        except Exception:
            player = None
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "power_from_pain", None) if army is not None else None
        if mgr is None:
            return
        abilities = mgr.get_applicable_pain_ability_names(unit, trigger="charge", game=self)
        if not abilities:
            return
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human and es is not None:
            try:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("pain_token_prompt"):
                    es.publish(
                        "pain_token_prompt",
                        player=player,
                        unit=unit,
                        phase_name=str(getattr(self.phase, "name", "") or ""),
                        trigger="charge",
                        abilities=list(abilities),
                        game=self,
                    )
                    return
            except Exception:
                pass
        try:
            mgr.maybe_empower_unit_for_trigger(unit, trigger="charge", game=self)
        except Exception:
            return

    def _on_phase_start_power_from_pain(self, player=None, phase=None, **_kwargs) -> None:
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if not pname:
            return

        # Clear pinned/suppressed at the start of the owner's next Command phase.
        if pname == "COMMAND_PHASE":
            owner_name = str(getattr(player, "name", "") or "")
            if owner_name:
                try:
                    current_turn = int(getattr(self, "turn", 0) or 0)
                except Exception:
                    current_turn = 0
                for p in list(getattr(self, "players", []) or []):
                    army = getattr(p, "army", None)
                    for u in list(getattr(army, "units", []) or []):
                        sr = getattr(u, "special_rules", None)
                        if not isinstance(sr, dict):
                            continue
                        if str(sr.get("pain_pinned_owner", "") or "") == owner_name:
                            try:
                                pin_turn = int(sr.get("pain_pinned_turn", 0) or 0)
                            except Exception:
                                pin_turn = 0
                            if current_turn > pin_turn:
                                try:
                                    u.remove_characteristic_modifiers_by_source("pain_pinned")
                                except Exception:
                                    pass
                                try:
                                    mods = sr.get("charge_roll_modifiers", None)
                                    if isinstance(mods, list):
                                        kept = []
                                        for item in mods:
                                            if isinstance(item, dict) and item.get("tag") == "pain_pinned":
                                                continue
                                            kept.append(item)
                                        if kept:
                                            sr["charge_roll_modifiers"] = kept
                                        else:
                                            sr.pop("charge_roll_modifiers", None)
                                except Exception:
                                    pass
                                sr.pop("pain_pinned_owner", None)
                                sr.pop("pain_pinned_turn", None)
                                u.special_rules = sr
                        if str(sr.get("pain_suppressed_owner", "") or "") == owner_name:
                            try:
                                sup_turn = int(sr.get("pain_suppressed_turn", 0) or 0)
                            except Exception:
                                sup_turn = 0
                            if current_turn > sup_turn:
                                for k in ("pain_suppressed_active", "pain_suppressed_owner", "pain_suppressed_turn"):
                                    sr.pop(k, None)
                                u.special_rules = sr

        def _maybe_trigger_for_player(owner_player, trigger: str) -> None:
            if owner_player is None:
                return
            army = getattr(owner_player, "army", None)
            mgr = getattr(army, "power_from_pain", None) if army is not None else None
            if mgr is None or int(getattr(mgr, "tokens", 0) or 0) <= 0:
                return
            es = getattr(self, "event_system", None)
            try:
                is_human = bool(getattr(getattr(owner_player, "type", None), "name", "") == "HUMAN")
            except Exception:
                is_human = False
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                        continue
                except Exception:
                    pass
                try:
                    abilities = mgr.get_applicable_pain_ability_names(unit, trigger=trigger, game=self)
                except Exception:
                    abilities = []
                if not abilities:
                    continue
                if is_human and es is not None:
                    try:
                        subs = getattr(es, "subscribers", {})
                        if isinstance(subs, dict) and subs.get("pain_token_prompt"):
                            es.publish(
                                "pain_token_prompt",
                                player=owner_player,
                                unit=unit,
                                phase_name=str(getattr(self.phase, "name", "") or ""),
                                trigger=trigger,
                                abilities=list(abilities),
                                game=self,
                            )
                            continue
                    except Exception:
                        pass
                try:
                    mgr.maybe_empower_unit_for_trigger(unit, trigger=trigger, game=self)
                except Exception:
                    continue

        if pname == "MOVEMENT_PHASE":
            _maybe_trigger_for_player(player, "movement")
        elif pname == "SHOOTING_PHASE":
            _maybe_trigger_for_player(player, "shooting_start")
        elif pname == "CHARGE_PHASE":
            _maybe_trigger_for_player(player, "charge_start")
        elif pname == "FIGHT_PHASE":
            for p in list(getattr(self, "players", []) or []):
                _maybe_trigger_for_player(p, "fight_start")

    def _on_phase_end_power_from_pain(self, player=None, phase=None, **_kwargs) -> None:
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname != "FIGHT_PHASE":
            return
        # Opponent's Fight phase end triggers (Fade Away).
        for p in list(getattr(self, "players", []) or []):
            if p is None or p is player:
                continue
            army = getattr(p, "army", None)
            mgr = getattr(army, "power_from_pain", None) if army is not None else None
            if mgr is None or int(getattr(mgr, "tokens", 0) or 0) <= 0:
                continue
            es = getattr(self, "event_system", None)
            try:
                is_human = bool(getattr(getattr(p, "type", None), "name", "") == "HUMAN")
            except Exception:
                is_human = False
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    abilities = mgr.get_applicable_pain_ability_names(unit, trigger="opp_fight_end", game=self)
                except Exception:
                    abilities = []
                if not abilities:
                    continue
                if is_human and es is not None:
                    try:
                        subs = getattr(es, "subscribers", {})
                        if isinstance(subs, dict) and subs.get("pain_token_prompt"):
                            es.publish(
                                "pain_token_prompt",
                                player=p,
                                unit=unit,
                                phase_name=str(getattr(self.phase, "name", "") or ""),
                                trigger="opp_fight_end",
                                abilities=list(abilities),
                                game=self,
                            )
                            continue
                    except Exception:
                        pass
                try:
                    mgr.maybe_empower_unit_for_trigger(unit, trigger="opp_fight_end", game=self)
                except Exception:
                    continue

    def _on_unit_shooting_resolved_power_from_pain(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            sr = getattr(attacker_unit, "special_rules", None)
        except Exception:
            sr = None
        if not isinstance(sr, dict):
            sr = {}

        def _is_monster_or_vehicle(unit) -> bool:
            try:
                if bool(getattr(unit, "is_monster", False)) or bool(getattr(unit, "is_vehicle", False)):
                    return True
            except Exception:
                pass
            try:
                return bool(unit.has_keyword("Monster") or unit.has_keyword("Vehicle"))
            except Exception:
                return False

        def _pick_target(filter_fn=None):
            best = None
            best_hits = -1
            for tgt, hits in (hits_by_target or {}).items():
                try:
                    h = int(hits or 0)
                except Exception:
                    h = 0
                if h <= 0:
                    continue
                if filter_fn is not None and not filter_fn(tgt):
                    continue
                if h > best_hits:
                    best_hits = h
                    best = tgt
            return best

        if hits_by_target and (sr.get("pain_shoot_pin") or sr.get("pain_shoot_no_cover") or sr.get("pain_shoot_suppress")):
            try:
                owner_name = attacker_unit.get_parent_army().player.name
            except Exception:
                owner_name = ""
            try:
                current_turn = int(getattr(self, "turn", 0) or 0)
            except Exception:
                current_turn = 0

            if sr.get("pain_shoot_pin"):
                target = _pick_target(lambda t: not _is_monster_or_vehicle(t))
                if target is not None:
                    try:
                        from ..utility.modifiers import Modifier, ModifierOp
                        target.add_characteristic_modifier(
                            "movement",
                            Modifier(ModifierOp.ADD, -2, source="pain_pinned"),
                        )
                    except Exception:
                        pass
                    try:
                        tsr = getattr(target, "special_rules", None)
                        if not isinstance(tsr, dict):
                            tsr = {}
                        mods = list(tsr.get("charge_roll_modifiers", []) or [])
                        mods.append({
                            "value": -2,
                            "source": "Nowhere to Run (Pain)",
                            "tag": "pain_pinned",
                        })
                        tsr["charge_roll_modifiers"] = mods
                        tsr["pain_pinned_owner"] = owner_name
                        tsr["pain_pinned_turn"] = int(current_turn)
                        target.special_rules = tsr
                    except Exception:
                        pass

            if sr.get("pain_shoot_no_cover"):
                target = _pick_target()
                if target is not None:
                    try:
                        tsr = getattr(target, "special_rules", None)
                        if not isinstance(tsr, dict):
                            tsr = {}
                        tsr["pain_no_cover_active"] = True
                        tsr["pain_no_cover_expires_phase"] = str(getattr(self.phase, "name", "") or "").strip().upper()
                        target.special_rules = tsr
                    except Exception:
                        pass

            if sr.get("pain_shoot_suppress"):
                target = _pick_target()
                if target is not None:
                    try:
                        tsr = getattr(target, "special_rules", None)
                        if not isinstance(tsr, dict):
                            tsr = {}
                        tsr["pain_suppressed_active"] = True
                        tsr["pain_suppressed_owner"] = owner_name
                        tsr["pain_suppressed_turn"] = int(current_turn)
                        target.special_rules = tsr
                    except Exception:
                        pass

        # Pain Parasite healing on kills after shooting.
        snapshot = self._pain_parasite_shooting_snapshot.pop(attacker_unit, None)
        if snapshot and sr.get("pain_on_kill_heal"):
            try:
                army = attacker_unit.get_parent_army()
            except Exception:
                army = None
            mgr = getattr(army, "power_from_pain", None) if army is not None else None
            if mgr is not None:
                for target_unit, before_count in list(snapshot.items()):
                    if target_unit is None:
                        continue
                    try:
                        models = target_unit.get_models_for_collision()
                    except Exception:
                        models = list(getattr(target_unit, "models", []) or [])
                    try:
                        after_count = sum(1 for m in models if getattr(m, "is_alive", False))
                    except Exception:
                        after_count = int(before_count or 0)
                    if int(after_count) < int(before_count or 0):
                        try:
                            mgr.apply_pain_parasite_heal(attacker_unit, game=self)
                        except Exception:
                            pass
                        break

    def _on_fight_sequence_complete_power_from_pain(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            sr = getattr(unit, "special_rules", None)
        except Exception:
            sr = None
        snapshot = self._pain_parasite_fight_snapshot.pop(unit, None)
        if not snapshot or not (isinstance(sr, dict) and sr.get("pain_on_kill_heal")):
            return
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "power_from_pain", None) if army is not None else None
        if mgr is None:
            return
        for target_unit, before_count in list(snapshot.items()):
            if target_unit is None:
                continue
            try:
                models = target_unit.get_models_for_collision()
            except Exception:
                models = list(getattr(target_unit, "models", []) or [])
            try:
                after_count = sum(1 for m in models if getattr(m, "is_alive", False))
            except Exception:
                after_count = int(before_count or 0)
            if int(after_count) < int(before_count or 0):
                try:
                    mgr.apply_pain_parasite_heal(unit, game=self)
                except Exception:
                    pass
                break

    def _maybe_prompt_power_from_pain_command_phase(self) -> None:
        try:
            player = self.get_current_player()
        except Exception:
            player = None
        if player is None:
            return
        army = getattr(player, "army", None)
        mgr = getattr(army, "power_from_pain", None) if army is not None else None
        if mgr is None:
            return
        if int(getattr(mgr, "tokens", 0) or 0) <= 0:
            return
        units = []
        for unit in list(getattr(army, "units", []) or []):
            try:
                abilities = mgr.get_applicable_pain_ability_names(unit, trigger="command", game=self)
            except Exception:
                abilities = []
            if abilities:
                units.append((unit, abilities))
        if not units:
            return
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        for unit, abilities in units:
            if is_human and es is not None:
                try:
                    subs = getattr(es, "subscribers", {})
                    if isinstance(subs, dict) and subs.get("pain_token_prompt"):
                        es.publish(
                            "pain_token_prompt",
                            player=player,
                            unit=unit,
                            phase_name=str(getattr(self.phase, "name", "") or ""),
                            trigger="command",
                            abilities=list(abilities),
                            game=self,
                        )
                        continue
                except Exception:
                    pass
            try:
                mgr.maybe_empower_unit_for_trigger(unit, trigger="command", game=self)
            except Exception:
                continue

    def _on_phase_start_optional_abilities(self, player=None, phase=None, **_kwargs) -> None:
        """
        Hook point for optional, player-decided abilities that trigger at specific timing windows.

        Currently supported:
        - Possessed Lord (Once per battle, start of Fight phase): prompt to activate.
        """
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname == "FIGHT_PHASE":
            if player is None:
                return

            # Only prompt the current player for their own optional activations at the start of this Fight phase.
            try:
                if player is not self.get_current_player():
                    return
            except Exception:
                pass

            army = getattr(player, "army", None)
            if army is None:
                return

            for unit in list(getattr(army, "units", []) or []):
                try:
                    if not unit.is_alive():
                        continue
                except Exception:
                    pass
                # Check unit has Possessed Lord ability text (datasheet ability list)
                has_possessed_lord = False
                try:
                    for ab in (getattr(unit, "possible_abilities", []) or []):
                        nm = str(getattr(ab, "name", "") or "").strip().lower()
                        if nm == "possessed lord":
                            has_possessed_lord = True
                            break
                except Exception:
                    has_possessed_lord = False
                if not has_possessed_lord:
                    continue

                # Apply to the first alive model in the unit (typical for character datasheets).
                models = list(getattr(unit, "models", []) or [])
                for m in models:
                    try:
                        if not getattr(m, "is_alive", True):
                            continue
                    except Exception:
                        continue
                    # If already used, skip.
                    try:
                        if getattr(m, "has_used_once_per_battle", lambda _k: False)("possessed_lord"):
                            break
                    except Exception:
                        pass

                    # Decision hook
                    try:
                        ctx = {
                            "ability_name": "Possessed Lord",
                            "unit": getattr(unit, "name", "") or "",
                            "model": getattr(m, "name", "") or "",
                            "phase": "Fight phase",
                        }
                        should = bool(getattr(player, "_should_use_optional_ability", lambda *_a, **_k: False)("POSSESSED_LORD", ctx))
                    except Exception:
                        should = False

                    if should:
                        try:
                            getattr(m, "activate_possessed_lord")()
                        except Exception:
                            pass
                    break
            return

        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        try:
            if player is not self.get_current_player():
                return
        except Exception:
            pass
        army = getattr(player, "army", None)
        if army is None:
            return

        for unit in list(getattr(army, "units", []) or []):
            try:
                if not unit.is_alive():
                    continue
            except Exception:
                pass
            try:
                if not bool(getattr(unit, "is_attached_leader", False)):
                    continue
            except Exception:
                continue

            ability = None
            try:
                ability = unit.get_command_phase_bodyguard_return_ability()
            except Exception:
                ability = None
            if not ability:
                continue
            try:
                bodyguard = unit.get_attached_unit_root()
            except Exception:
                bodyguard = None
            if bodyguard is None or bodyguard is unit:
                continue
            try:
                if not getattr(bodyguard, "deployed", True):
                    continue
                if str(getattr(bodyguard, "reserve_status", "deployed")) != "deployed":
                    continue
                if hasattr(bodyguard, "is_in_reserves") and callable(getattr(bodyguard, "is_in_reserves")):
                    if bool(bodyguard.is_in_reserves()):
                        continue
                if bool(getattr(bodyguard, "embarked_in", None)):
                    continue
                if bool(getattr(bodyguard, "is_embarked", False)):
                    continue
            except Exception:
                pass
            try:
                if len(getattr(bodyguard, "models", []) or []) <= 0:
                    continue
            except Exception:
                continue
            try:
                if not list(getattr(bodyguard, "models_lost", []) or []):
                    continue
            except Exception:
                continue

            amount = int(ability.get("amount", 0) or 0)
            if amount <= 0:
                continue
            try:
                ctx = {
                    "ability_name": ability.get("name", "") or "",
                    "unit": getattr(unit, "name", "") or "",
                    "bodyguard": getattr(bodyguard, "name", "") or "",
                    "amount": amount,
                    "phase": "Command phase",
                }
                should = bool(getattr(player, "_should_use_optional_ability", lambda *_a, **_k: False)("RETURN_BODYGUARD_MODEL", ctx))
            except Exception:
                should = False
            if not should:
                continue
            try:
                destroyed_models = list(getattr(bodyguard, "models_lost", []) or [])
            except Exception:
                destroyed_models = []
            if not destroyed_models:
                continue
            chosen_models = destroyed_models[:amount]
            try:
                returned = unit.return_destroyed_bodyguard_models(
                    amount,
                    game_map=getattr(self, "map", None),
                    chosen_models=chosen_models,
                )
            except Exception:
                returned = 0
            try:
                from ..utility.event_bus import append_action
                pname = str(getattr(player, "name", "") or "")
                if pname:
                    ability_name = ability.get("name", "") or "Bodyguard Return"
                    if returned > 0:
                        names = ", ".join(getattr(m, "name", "Model") for m in (chosen_models[:returned] or []))
                        append_action(pname, f"{ability_name}: returned {names} to {getattr(bodyguard, 'name', 'Unit')}.")
                    else:
                        append_action(pname, f"{ability_name}: no model returned to {getattr(bodyguard, 'name', 'Unit')}.")
            except Exception:
                pass

    def _on_phase_start_cabal_of_sorcerers(self, player=None, phase=None, **_kwargs) -> None:
        """Reset Cabal of Sorcerers usage at the start of the active player's Shooting phase."""
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "cabal_of_sorcerers", None)
        if mgr is None:
            return
        try:
            mgr.on_shooting_phase_start(game=self, player=player)
        except Exception:
            pass

    def _on_phase_start_for_the_greater_good(self, player=None, phase=None, **_kwargs) -> None:
        """Prompt Observer selection at the start of the active player's Shooting phase."""
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "for_the_greater_good", None)
        if mgr is None:
            return
        try:
            mgr.on_shooting_phase_start(game=self, player=player)
        except Exception:
            pass
        try:
            if getattr(self, "event_system", None) is not None:
                self.event_system.publish("for_the_greater_good_prompt", player=player, game=self)
        except Exception:
            pass

    def _on_phase_start_voice_of_command(self, player=None, phase=None, **_kwargs) -> None:
        """Astra Militarum: issue Orders at the start of the Command phase."""
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None or not getattr(mgr, "_army_has_voice", lambda: False)():
            return

        try:
            mgr.clear_orders_for_player(player)
        except Exception:
            pass

        try:
            officers = mgr.get_eligible_officers(game=self, player=player, phase_name=pname, trigger="command_phase_start")
        except Exception:
            officers = []
        if not officers:
            return
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human and es is not None:
            try:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("voice_of_command_prompt"):
                    es.publish(
                        "voice_of_command_prompt",
                        player=player,
                        game=self,
                        phase_name=pname,
                        trigger="command_phase_start",
                    )
                    return
            except Exception:
                pass
        try:
            mgr.auto_issue_orders(self, player, phase_name=pname, trigger="command_phase_start")
        except Exception:
            return

    def _on_phase_end_voice_of_command(self, player=None, phase=None, **_kwargs) -> None:
        """Astra Militarum: issue Orders at end of phase if an Officer disembarked or was set up."""
        if player is None:
            return
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if not pname:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None or not getattr(mgr, "_army_has_voice", lambda: False)():
            return
        try:
            officers = mgr.get_eligible_officers(game=self, player=player, phase_name=pname, trigger="phase_end")
        except Exception:
            officers = []
        if not officers:
            return
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human and es is not None:
            try:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("voice_of_command_prompt"):
                    es.publish(
                        "voice_of_command_prompt",
                        player=player,
                        game=self,
                        phase_name=pname,
                        trigger="phase_end",
                    )
                    return
            except Exception:
                pass
        try:
            mgr.auto_issue_orders(self, player, phase_name=pname, trigger="phase_end")
        except Exception:
            return

    def _on_phase_end_gate_of_infinity(self, player=None, phase=None, **_kwargs) -> None:
        """Grey Knights: Gate of Infinity at the end of the opponent's Fight phase."""
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname != "FIGHT_PHASE":
            return
        if player is None:
            return
        try:
            opponents = [p for p in (self.players or []) if p is not None and p is not player]
        except Exception:
            opponents = []
        if not opponents:
            return
        es = getattr(self, "event_system", None)
        subs = getattr(es, "subscribers", {}) if es is not None else {}
        for opp in opponents:
            if opp is None:
                continue
            try:
                army = opp.get_army()
            except Exception:
                army = None
            if army is None:
                continue
            mgr = getattr(army, "gate_of_infinity", None)
            if mgr is None or not getattr(mgr, "_army_has_gate", lambda: False)():
                continue
            try:
                max_units = int(mgr.get_max_units_for_battlefield(self))
            except Exception:
                max_units = 0
            if max_units <= 0:
                continue
            try:
                eligible = list(mgr.get_eligible_units(game=self, player=opp) or [])
            except Exception:
                eligible = []
            if not eligible:
                continue
            try:
                is_human = bool(getattr(getattr(opp, "type", None), "name", "") == "HUMAN")
            except Exception:
                is_human = False
            if is_human and es is not None and isinstance(subs, dict) and subs.get("gate_of_infinity_prompt"):
                try:
                    es.publish(
                        "gate_of_infinity_prompt",
                        player=opp,
                        game=self,
                        max_units=max_units,
                    )
                except Exception:
                    pass
                continue
            try:
                mgr.auto_gate_units(game=self, player=opp)
            except Exception:
                continue

    def _maybe_prompt_end_of_opponent_turn_strategic_reserves(self, turn_ending_player=None) -> None:
        """Optional end-of-opponent-turn: remove eligible units to Strategic Reserves."""
        if turn_ending_player is None:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return
        es = getattr(self, "event_system", None)
        subs = getattr(es, "subscribers", {}) if es is not None else {}

        for opp in list(getattr(self, "players", []) or []):
            if opp is None or opp is turn_ending_player:
                continue
            try:
                army = opp.get_army()
            except Exception:
                army = None
            if army is None:
                continue

            eligible = []
            seen = set()
            for unit in list(getattr(army, "units", []) or []):
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None:
                    continue
                try:
                    rid = getattr(root, "_id", None) or id(root)
                except Exception:
                    rid = id(root)
                if rid in seen:
                    continue
                seen.add(rid)
                try:
                    if not root.is_alive():
                        continue
                except Exception:
                    pass
                try:
                    if not getattr(root, "deployed", False):
                        continue
                    if str(getattr(root, "reserve_status", "deployed")) != "deployed":
                        continue
                    if bool(getattr(root, "embarked_in", None)) or bool(getattr(root, "is_embarked", False)):
                        continue
                except Exception:
                    continue
                try:
                    ability = root.get_end_of_opponent_turn_strategic_reserves_ability()
                except Exception:
                    ability = None
                if not ability:
                    continue
                engaged = False
                try:
                    for enemy in list(game_map.get_enemy_units(root) or []):
                        if not getattr(enemy, "is_alive", lambda: True)():
                            continue
                        if not getattr(enemy, "deployed", True):
                            continue
                        if game_map.is_within_engagement_range(root, enemy):
                            engaged = True
                            break
                except Exception:
                    engaged = True
                if engaged:
                    continue
                eligible.append({"unit": root, "ability": ability})

            if not eligible:
                continue

            try:
                is_human = bool(getattr(getattr(opp, "type", None), "name", "") == "HUMAN")
            except Exception:
                is_human = False
            if is_human and es is not None and isinstance(subs, dict) and subs.get("opponent_turn_strategic_reserves_prompt"):
                try:
                    es.publish(
                        "opponent_turn_strategic_reserves_prompt",
                        player=opp,
                        units=list(eligible),
                        game=self,
                    )
                except Exception:
                    pass
                continue

            for entry in eligible:
                unit = entry.get("unit")
                ability = entry.get("ability") or {}
                if unit is None:
                    continue
                try:
                    ctx = {
                        "ability_name": ability.get("name", "") or "",
                        "unit": getattr(unit, "name", "") or "",
                        "phase": "End of opponent's turn",
                    }
                    should = bool(opp._should_use_optional_ability("OPPONENT_TURN_STRATEGIC_RESERVES", ctx))
                except Exception:
                    should = False
                if not should:
                    continue
                try:
                    used = unit.enter_strategic_reserves_midgame(
                        game=self,
                        game_map=game_map,
                        reason="end of opponent turn",
                    )
                except Exception:
                    used = False
                if used:
                    try:
                        from ..utility.event_bus import append_action
                        pname = str(getattr(opp, "name", "") or "")
                        if pname:
                            ability_name = ability.get("name", "") or "Strategic Reserves"
                            append_action(pname, f"{ability_name}: {getattr(unit, 'name', 'Unit')} placed into Strategic Reserves.")
                    except Exception:
                        pass

    def _on_phase_end_for_the_greater_good(self, player=None, phase=None, **_kwargs) -> None:
        """Clear For the Greater Good state at the end of the Shooting phase."""
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "for_the_greater_good", None)
        if mgr is None:
            return
        try:
            mgr.on_shooting_phase_end(game=self, player=player)
        except Exception:
            pass

    def _on_phase_end_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Best-effort cleanup for model-level temporary effects that expire at end of a phase."""
        try:
            for p in list(getattr(self, "players", []) or []):
                army = getattr(p, "army", None)
                for u in list(getattr(army, "units", []) or []):
                    for m in list(getattr(u, "models", []) or []):
                        fn = getattr(m, "on_phase_end", None)
                        if callable(fn):
                            fn(phase)
        except Exception:
            return
        # Unit-level temporary effects (e.g. detachment abilities that last until end of turn)
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if not pname:
            return
        try:
            for p in list(getattr(self, "players", []) or []):
                army = getattr(p, "army", None)
                for u in list(getattr(army, "units", []) or []):
                    sr = getattr(u, "special_rules", None)
                    if not isinstance(sr, dict):
                        continue
                    exp = str(sr.get("relentless_rage_expires_phase", "") or "").strip().upper()
                    if exp and exp == pname:
                        for k in (
                            "relentless_rage_melee_attacks_bonus",
                            "relentless_rage_melee_strength_bonus",
                            "relentless_rage_expires_phase",
                        ):
                            sr.pop(k, None)
                    exp = str(sr.get("dark_pacts_expires_phase", "") or "").strip().upper()
                    if exp and exp == pname:
                        for k in ("dark_pacts_active", "dark_pacts_choice", "dark_pacts_expires_phase"):
                            sr.pop(k, None)
                    exp = str(sr.get("exquisite_swordsmanship_expires_phase", "") or "").strip().upper()
                    if exp and exp == pname:
                        for k in ("exquisite_swordsmanship_choice", "exquisite_swordsmanship_expires_phase"):
                            sr.pop(k, None)
                    exp = str(sr.get("fury_of_titan_expires_phase", "") or "").strip().upper()
                    if exp and exp == pname:
                        for k in ("fury_of_titan_active", "fury_of_titan_expires_phase"):
                            sr.pop(k, None)
                    exp = str(sr.get("sensational_performance_expires_phase", "") or "").strip().upper()
                    if exp and exp == pname:
                        for k in (
                            "sensational_performance_active",
                            "sensational_performance_expires_phase",
                            "sensational_performance_strength_bonus",
                            "sensational_performance_ap_bonus",
                        ):
                            sr.pop(k, None)
                    exp = str(sr.get("seductive_gambit_expires_phase", "") or "").strip().upper()
                    if exp and exp == pname:
                        for k in ("seductive_gambit_active", "seductive_gambit_expires_phase"):
                            sr.pop(k, None)
                    exp = str(sr.get("pain_empowered_expires_phase", "") or "").strip().upper()
                    if exp and exp == pname:
                        for k in (
                            "pain_empowered",
                            "pain_empowered_expires_phase",
                            "pain_empowered_sources",
                            "pain_reroll_hit",
                            "pain_reroll_hit_ranged",
                            "pain_reroll_advance",
                            "pain_reroll_charge",
                            "pain_melee_strength_bonus",
                            "pain_melee_strength_set",
                            "pain_melee_ap_bonus",
                            "pain_melee_wound_bonus",
                            "pain_melee_attacks_bonus",
                            "pain_melee_attacks_set_non_character",
                            "pain_melee_hazardous_non_character",
                            "pain_experimental_enhancements_choice",
                            "pain_charge_after_advance",
                            "pain_charge_after_fall_back",
                            "pain_lethal_hits",
                            "pain_lethal_hits_melee",
                            "pain_sustained_hits_value",
                            "pain_archon_poisoned_tongue_choice",
                            "pain_assassins_poisons_active",
                            "pain_ignores_cover_ranged",
                            "pain_melee_wound_roll_defense_mod",
                            "pain_sustained_hits_ranged_vs_vehicle",
                            "pain_sustained_hits_ranged_vs_non_vehicle",
                            "pain_rapid_fire_weapon_bonus",
                            "pain_beast_reroll_hit",
                            "pain_beast_reroll_wound",
                            "pain_advance_no_roll",
                            "pain_advance_fixed_bonus",
                            "pain_fight_on_death_2plus",
                            "pain_shoot_pin",
                            "pain_shoot_no_cover",
                            "pain_shoot_suppress",
                            "pain_on_kill_heal",
                            "pain_rapid_deployment_active",
                            "pain_reroll_wound_ones",
                            "pain_reroll_wound_full_if_objective",
                            "pain_ranged_ap_bonus",
                            "pain_splinter_racks_active",
                            "pain_deep_strike_min_distance",
                        ):
                            sr.pop(k, None)
                    exp = str(sr.get("pain_no_cover_expires_phase", "") or "").strip().upper()
                    if exp and exp == pname:
                        for k in ("pain_no_cover_active", "pain_no_cover_expires_phase"):
                            sr.pop(k, None)
                    exp = str(sr.get("cabal_destinys_ruin_expires_phase", "") or "").strip().upper()
                    if exp and exp == pname:
                        for k in ("cabal_destinys_ruin_mode", "cabal_destinys_ruin_owner", "cabal_destinys_ruin_expires_phase"):
                            sr.pop(k, None)
                    exp = str(sr.get("cabal_twist_of_fate_expires_phase", "") or "").strip().upper()
                    if exp and exp == pname:
                        for k in ("cabal_twist_of_fate_ap_bonus", "cabal_twist_of_fate_owner", "cabal_twist_of_fate_expires_phase"):
                            sr.pop(k, None)
                    if pname == "SHOOTING_PHASE":
                        sr.pop("cabal_temporal_surge_move_max", None)
        except Exception:
            return
        try:
            for p in list(getattr(self, "players", []) or []):
                army = getattr(p, "army", None)
                mgr = getattr(army, "battle_focus", None) if army is not None else None
                if mgr is not None:
                    mgr.cleanup_on_phase_end(phase, p)
        except Exception:
            return

        # Templar Vows: Uphold the Honour of the Emperor sticky objectives at end of your Command phase.
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname == "COMMAND_PHASE":
            try:
                army = getattr(player, "army", None) if player is not None else None
                mgr = getattr(army, "templar_vows", None) if army is not None else None
                if mgr is not None:
                    mgr.on_command_phase_end(game=self, player=player)
            except Exception:
                pass
            # Datasheet abilities: sticky objectives at end of your Command phase.
            try:
                if player is None:
                    raise ValueError("no player")
                army = getattr(player, "army", None)
                if army is None:
                    raise ValueError("no army")
                game_map = getattr(self, "map", None)
                objectives = list(getattr(game_map, "objectives", []) or []) if game_map is not None else []
                if not objectives:
                    raise ValueError("no objectives")
                for obj in objectives:
                    loc = getattr(obj, "location", None)
                    if loc is None or getattr(loc, "removed", False):
                        continue
                    try:
                        loc.update_control(self)
                    except Exception:
                        continue
                seen = set()
                for unit in list(getattr(army, "units", []) or []):
                    try:
                        root = unit.get_attached_unit_root()
                    except Exception:
                        root = unit
                    if root is None:
                        continue
                    try:
                        uid = getattr(root, "_id", id(root))
                    except Exception:
                        uid = id(root)
                    if uid in seen:
                        continue
                    seen.add(uid)
                    try:
                        if not root.attached_unit_has_command_phase_sticky_objective():
                            continue
                    except Exception:
                        continue
                    for obj in objectives:
                        loc = getattr(obj, "location", None)
                        if loc is None or getattr(loc, "removed", False):
                            continue
                        if getattr(loc, "controlling_player", None) is not player:
                            continue
                        try:
                            if not root.is_within_objective_range(loc):
                                continue
                        except Exception:
                            continue
                        try:
                            if hasattr(loc, "set_sticky_control"):
                                loc.set_sticky_control(player, source="unit_sticky_objective")
                            else:
                                loc.sticky_controller = player
                                loc.sticky_source = "unit_sticky_objective"
                                loc.controlling_player = player
                        except Exception:
                            continue
            except Exception:
                pass

        # Cabal of Sorcerers: Temporal Surge charge restriction ends at the end of the turn.
        if pname == "FIGHT_PHASE":
            try:
                owner_name = str(getattr(player, "name", "") or "")
            except Exception:
                owner_name = ""
            try:
                for p in list(getattr(self, "players", []) or []):
                    army = getattr(p, "army", None)
                    for u in list(getattr(army, "units", []) or []):
                        sr = getattr(u, "special_rules", None)
                        if not isinstance(sr, dict):
                            continue
                        if str(sr.get("cabal_temporal_surge_no_charge_turn_owner", "") or "") == owner_name:
                            for k in ("cabal_temporal_surge_no_charge_turn_owner", "cabal_temporal_surge_no_charge_turn"):
                                sr.pop(k, None)
                        if str(sr.get("pain_swooping_descent_no_charge_turn_owner", "") or "") == owner_name:
                            for k in ("pain_swooping_descent_no_charge_turn_owner", "pain_swooping_descent_no_charge_turn"):
                                sr.pop(k, None)
                        if str(sr.get("feigned_retreat_turn_owner", "") or "") == owner_name:
                            for k in ("feigned_retreat_active", "feigned_retreat_turn_owner", "feigned_retreat_turn"):
                                sr.pop(k, None)
                        if str(sr.get("fire_and_fade_no_charge_turn_owner", "") or "") == owner_name:
                            for k in ("fire_and_fade_no_charge_turn_owner", "fire_and_fade_no_charge_turn"):
                                sr.pop(k, None)
                        if str(sr.get("fire_and_fade_no_embark_turn_owner", "") or "") == owner_name:
                            for k in ("fire_and_fade_no_embark_turn_owner", "fire_and_fade_no_embark_turn"):
                                sr.pop(k, None)
            except Exception:
                pass

        # Snapshot objective control at end of each phase for "previous phase" rules.
        try:
            snapshot = {}
            for obj in list(getattr(self.map, "objectives", []) or []):
                loc = getattr(obj, "location", None)
                if loc is None or getattr(loc, "removed", False):
                    continue
                if hasattr(loc, "update_control"):
                    loc.update_control(self)
                snapshot[loc] = getattr(loc, "controlling_player", None)
            self._objective_control_snapshot = snapshot
        except Exception:
            pass

        # Phoenix Gem: resolve pending returns at end of the phase they were destroyed in.
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname:
            try:
                pending = list(getattr(self, "_phoenix_gem_pending", []) or [])
            except Exception:
                pending = []
            if pending:
                remaining = []
                for payload in pending:
                    try:
                        if str(payload.get("phase_name", "") or "").strip().upper() != pname:
                            remaining.append(payload)
                            continue
                    except Exception:
                        remaining.append(payload)
                        continue
                    try:
                        self._resolve_phoenix_gem_return(payload)
                    except Exception:
                        remaining.append(payload)
                try:
                    self._phoenix_gem_pending = remaining
                except Exception:
                    pass

    def _on_unit_move_started_battle_focus(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        if (action or "").strip().lower() != "fall_back":
            return
        try:
            owner = unit.get_parent_army().player
        except Exception:
            owner = None
        for p in list(getattr(self, "players", []) or []):
            if p is None or p is owner:
                continue
            army = getattr(p, "army", None)
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            if mgr is None:
                continue
            mgr.record_enemy_fall_back_start(unit, self)

    def _on_unit_move_ended_battle_focus(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        if (action or "").strip().lower() != "fall_back":
            return
        try:
            owner = unit.get_parent_army().player
        except Exception:
            owner = None
        for p in list(getattr(self, "players", []) or []):
            if p is None or p is owner:
                continue
            army = getattr(p, "army", None)
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            if mgr is None:
                continue
            try:
                is_human = bool(getattr(getattr(p, "type", None), "name", "") == "HUMAN")
            except Exception:
                is_human = False
            if is_human:
                candidates = mgr.consume_opportunity_seized_candidates(unit, self)
                if not candidates:
                    continue
                try:
                    self.event_system.publish(
                        "battle_focus_opportunity_prompt",
                        player=p,
                        moving_unit=unit,
                        candidates=list(candidates),
                        manager=mgr,
                    )
                except Exception:
                    pass
            else:
                mgr.maybe_trigger_opportunity_seized(unit, self)

    def _on_fight_unit_selected_battle_focus(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None or selecting_player is None:
            return
        army = getattr(selecting_player, "army", None)
        mgr = getattr(army, "battle_focus", None) if army is not None else None
        if mgr is None:
            return
        mgr.maybe_trigger_sudden_strike(unit, self)

    def _on_unit_shooting_resolved_battle_focus(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        if not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_player = attacker_unit.get_parent_army().player
        except Exception:
            return
        try:
            if attacker_player is not self.get_current_player():
                return
        except Exception:
            pass

        hits_by_player: dict = {}
        for target_unit, hits in (hits_by_target or {}).items():
            if target_unit is None:
                continue
            try:
                hits = int(hits or 0)
            except Exception:
                hits = 0
            if hits <= 0:
                continue
            try:
                target_player = target_unit.get_parent_army().player
            except Exception:
                continue
            if target_player is attacker_player:
                continue
            hits_by_player.setdefault(target_player, {})[target_unit] = hits

        for player, hits_map in hits_by_player.items():
            army = getattr(player, "army", None)
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            if mgr is None:
                continue
            hit_units = list(hits_map.keys())
            try:
                is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
            except Exception:
                is_human = False
            if is_human:
                candidates = mgr.get_fade_back_candidates(hit_units, self)
                if not candidates:
                    continue
                try:
                    self.event_system.publish(
                        "battle_focus_fade_back_prompt",
                        player=player,
                        attacker_unit=attacker_unit,
                        candidates=list(candidates),
                        hits_by_unit=dict(hits_map),
                        manager=mgr,
                    )
                except Exception:
                    pass
            else:
                for target_unit, hits in hits_map.items():
                    mgr.maybe_trigger_fade_back(attacker_unit, target_unit, hits, self)

    def _on_unit_shooting_resolved_aspect_shrine(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        try:
            root.clear_aspect_shrine_prompt_suppression()
        except Exception:
            pass

    def _on_fight_sequence_complete_aspect_shrine(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            root.clear_aspect_shrine_prompt_suppression()
        except Exception:
            pass

    def _on_unit_move_ended_detachment_rules(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        if (action or "").strip().lower() != "charge":
            return
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return
        we_mgr = getattr(army, "world_eaters_detachments", None)
        if we_mgr is not None and getattr(we_mgr, "relentless_rage_applies", None):
            try:
                applies = bool(we_mgr.relentless_rage_applies(unit))
            except Exception:
                applies = False
            if applies:
                # Relentless Rage applies only to WORLD EATERS units
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["relentless_rage_melee_attacks_bonus"] = 1
                sr["relentless_rage_melee_strength_bonus"] = 2
                sr["relentless_rage_expires_phase"] = "FIGHT_PHASE"
                unit.special_rules = sr
                return

        cd_mgr = getattr(army, "chaos_daemons_detachments", None)
        if cd_mgr is not None and getattr(cd_mgr, "seductive_gambit_applies", None):
            try:
                applies = bool(cd_mgr.seductive_gambit_applies(unit))
            except Exception:
                applies = False
            if applies:
                # Seductive Gambit applies only to LEGIONES DAEMONICA SLAANESH units.
                try:
                    player = unit.get_parent_army().player
                except Exception:
                    player = None
                if player is None:
                    return
                ctx = {"unit": getattr(unit, "name", "") or "", "ability_name": "Seductive Gambit"}
                if not player._should_use_optional_ability("SEDUCTIVE_GAMBIT", ctx):
                    return
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["seductive_gambit_active"] = True
                sr["seductive_gambit_expires_phase"] = "FIGHT_PHASE"
                unit.special_rules = sr

    def _choose_charge_mortal_wounds_target(self, player, unit, candidates, spec):
        if not candidates:
            return None
        choice = None
        if player is not None and hasattr(player, "_choose_optional_value"):
            try:
                ctx = {
                    "unit": getattr(unit, "name", "") or "",
                    "ability": str((spec or {}).get("name", "") or ""),
                    "candidates": [getattr(c, "name", "") for c in candidates],
                }
                choice = player._choose_optional_value("CHARGE_MORTAL_WOUNDS_TARGET", list(candidates), ctx)
            except Exception:
                choice = None
        if choice in candidates:
            return choice
        if isinstance(choice, str):
            wanted = choice.strip().lower()
            for cand in candidates:
                try:
                    if str(getattr(cand, "name", "") or "").strip().lower() == wanted:
                        return cand
                except Exception:
                    continue
        return candidates[0]

    def resolve_charge_end_mortal_wounds(self, unit, target_unit, spec) -> None:
        if unit is None or target_unit is None or not isinstance(spec, dict):
            return
        kind = str(spec.get("kind", "") or "").strip().lower()
        if not kind:
            return
        game_map = getattr(self, "map", None)
        ability_name = str(spec.get("name", "") or "Charge Mortals").strip() or "Charge Mortals"

        try:
            from ..utility.dice import get_roll
        except Exception:
            return

        total_mw = 0
        roll_summary = ""
        if kind == "per_model_4plus_d3":
            try:
                models = list(unit.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(unit, "models", []) or [])
            rolls = []
            d3_rolls = []
            for m in models:
                try:
                    if not getattr(m, "is_alive", False):
                        continue
                except Exception:
                    pass
                try:
                    r = int(get_roll("D6") or 0)
                except Exception:
                    r = 0
                rolls.append(r)
                if r >= 4:
                    try:
                        d3 = int(get_roll("D3") or 0)
                    except Exception:
                        d3 = 0
                    d3_rolls.append(d3)
                    total_mw += d3
            if rolls:
                roll_summary = f"rolls={rolls}"
                if d3_rolls:
                    roll_summary += f", d3={d3_rolls}"
        elif kind == "table_d6_2_3_4_5_6":
            try:
                roll = int(get_roll("D6") or 0)
            except Exception:
                roll = 0
            if 2 <= roll <= 3:
                total_mw = 1
            elif 4 <= roll <= 5:
                try:
                    total_mw = int(get_roll("D3") or 0)
                except Exception:
                    total_mw = 0
            elif roll >= 6:
                try:
                    total_mw = int(get_roll("D3") or 0) + 3
                except Exception:
                    total_mw = 3
            roll_summary = f"roll={roll}"
        else:
            return

        try:
            print(f"{ability_name}: {getattr(unit, 'name', 'Unit')} -> {getattr(target_unit, 'name', 'Target')} ({roll_summary}) => {total_mw} mortal wounds")
        except Exception:
            pass

        if total_mw > 0:
            try:
                unit._apply_mortal_wounds_to_unit(target_unit, int(total_mw), game_map=game_map)
            except Exception:
                pass
        try:
            from ..utility.event_bus import append_action
            pname = str(getattr(getattr(unit.get_parent_army(), "player", None), "name", "") or "")
            if pname:
                append_action(
                    pname,
                    f"{ability_name}: {getattr(unit, 'name', 'Unit')} dealt {int(total_mw)} mortal wounds to {getattr(target_unit, 'name', 'Target')}.",
                )
        except Exception:
            pass

    def _on_unit_move_ended_charge_mortal_wounds(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        if (action or "").strip().lower() != "charge":
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            if not root.is_alive():
                return
        except Exception:
            pass

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        specs = list(sr.get("charge_end_mortal_wounds", []) or [])
        if not specs:
            return

        try:
            enemies = list(game_map.get_enemy_units(root) or [])
        except Exception:
            enemies = []
        engaged = []
        for enemy in enemies:
            if enemy is None:
                continue
            try:
                if not getattr(enemy, "deployed", True):
                    continue
                if hasattr(enemy, "is_alive") and not enemy.is_alive():
                    continue
                if not game_map.is_within_engagement_range(root, enemy):
                    continue
            except Exception:
                continue
            engaged.append(enemy)

        if not engaged:
            return

        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False

        for spec in specs:
            if len(engaged) == 1 or not is_human:
                target = engaged[0] if len(engaged) == 1 else self._choose_charge_mortal_wounds_target(player, root, engaged, spec)
                if target is None:
                    continue
                self.resolve_charge_end_mortal_wounds(root, target, spec)
                continue

            def _on_select(target_unit, _spec=spec, _root=root):
                if target_unit is None:
                    return
                self.resolve_charge_end_mortal_wounds(_root, target_unit, _spec)

            try:
                self.event_system.publish(
                    "charge_mortal_wounds_prompt",
                    player=player,
                    unit=root,
                    candidates=list(engaged),
                    ability=spec,
                    on_select=_on_select,
                )
            except Exception:
                self.resolve_charge_end_mortal_wounds(root, engaged[0], spec)

    def _on_model_destroyed_rules(self, attacker_model=None, attacker_unit=None, target_model=None, target_unit=None, **_kwargs) -> None:
        # Generic partial support for "gain CP when this model destroys an enemy KEYWORD unit/model".
        if attacker_unit is None or target_unit is None:
            return

        # Must be an enemy destroy event
        try:
            if attacker_unit.get_parent_army() == target_unit.get_parent_army():
                return
        except Exception:
            return

        specs = []
        try:
            specs = attacker_unit.get_kill_reward_specs(model=attacker_model)
        except Exception:
            specs = []

        if not specs:
            return

        target_keywords = set()
        try:
            target_keywords = {str(k).upper() for k in getattr(target_unit, "keywords", []) or []}
        except Exception:
            target_keywords = set()

        for spec in specs:
            if spec.get("trigger") != "model_destroyed":
                continue

            # Optional restriction: melee only (Feared Interrogator)
            if spec.get("requires_melee", False):
                try:
                    wp = _kwargs.get("weapon_profile", None)
                    pw = getattr(wp, "parent_wargear", None)
                    if pw is None or not getattr(pw, "is_melee", lambda: False)():
                        continue
                except Exception:
                    continue

            # Keyword matching
            required = set(spec.get("target_keywords", spec.get("required_target_keywords", set())) or set())
            mode = (spec.get("target_keyword_mode", "all") or "all").lower()
            if required:
                if mode == "any":
                    if required.isdisjoint(target_keywords):
                        continue
                else:
                    if not required.issubset(target_keywords):
                        continue

            if spec.get("type") == "gain_cp_on_destroy":
                cp = int(spec.get("cp", 1) or 1)
                try:
                    player = attacker_unit.get_parent_army().player
                    if player is None:
                        continue
                    gained = 0
                    try:
                        if hasattr(player, "gain_command_points"):
                            gained = int(player.gain_command_points(cp, reason=spec.get("source_ability", "")) or 0)
                        else:
                            before = player.command_points
                            player.gain_command_point() if cp == 1 else setattr(player, "command_points", before + cp)
                            gained = cp
                    except Exception:
                        gained = 0
                    try:
                        self.event_system.publish(
                            "command_points_gained",
                            player=player,
                            amount=gained,
                            reason=spec.get("source_ability", ""),
                            attacker_unit=attacker_unit,
                            target_unit=target_unit,
                            attacker_model=attacker_model,
                            target_model=target_model,
                        )
                    except Exception:
                        pass
                except Exception:
                    continue

            if spec.get("type") == "heal_on_destroy":
                # Heal the destroying model (if present)
                if attacker_model is None:
                    continue
                heal_expr = spec.get("heal_expr")
                if not heal_expr:
                    continue
                try:
                    from warhammer40k_ai.utility.dice import get_roll
                    amount = get_roll(heal_expr)
                    attacker_model.heal(amount)
                    try:
                        self.event_system.publish(
                            "model_healed",
                            model=attacker_model,
                            unit=attacker_unit,
                            amount=amount,
                            reason=spec.get("source_ability", ""),
                        )
                    except Exception:
                        pass
                except Exception:
                    continue

    def _on_unit_destroyed_rules(self, unit=None, destroyed_by_unit=None, destroyed_by_model=None, destroyed_by_weapon_profile=None, **_kwargs) -> None:
        # Generic partial support for "... destroys an enemy <KEYWORD> unit, gain X CP".
        if unit is None or destroyed_by_unit is None:
            return

        try:
            if destroyed_by_unit.get_parent_army() == unit.get_parent_army():
                return
        except Exception:
            return

        specs = []
        try:
            specs = destroyed_by_unit.get_kill_reward_specs(model=destroyed_by_model)
        except Exception:
            specs = []

        if not specs:
            return

        target_keywords = set()
        try:
            target_keywords = {str(k).upper() for k in getattr(unit, "keywords", []) or []}
        except Exception:
            target_keywords = set()

        for spec in specs:
            if spec.get("trigger") != "unit_destroyed":
                continue

            # Optional restriction: melee only
            if spec.get("requires_melee", False):
                try:
                    wp = destroyed_by_weapon_profile
                    pw = getattr(wp, "parent_wargear", None)
                    if wp is None or pw is None or not getattr(pw, "is_melee", lambda: False)():
                        continue
                except Exception:
                    continue
            required = set(spec.get("target_keywords", spec.get("required_target_keywords", set())) or set())
            mode = (spec.get("target_keyword_mode", "all") or "all").lower()
            if required:
                if mode == "any":
                    if required.isdisjoint(target_keywords):
                        continue
                else:
                    if not required.issubset(target_keywords):
                        continue

            if spec.get("type") == "gain_cp_on_destroy":
                cp = int(spec.get("cp", 1) or 1)
                try:
                    player = destroyed_by_unit.get_parent_army().player
                    if player is None:
                        continue
                    gained = 0
                    try:
                        if hasattr(player, "gain_command_points"):
                            gained = int(player.gain_command_points(cp, reason=spec.get("source_ability", "")) or 0)
                        else:
                            before = player.command_points
                            player.gain_command_point() if cp == 1 else setattr(player, "command_points", before + cp)
                            gained = cp
                    except Exception:
                        gained = 0
                    try:
                        self.event_system.publish(
                            "command_points_gained",
                            player=player,
                            amount=gained,
                            reason=spec.get("source_ability", ""),
                            attacker_unit=destroyed_by_unit,
                            target_unit=unit,
                            attacker_model=destroyed_by_model,
                        )
                    except Exception:
                        pass
                except Exception:
                    continue

            if spec.get("type") == "heal_on_destroy":
                if destroyed_by_model is None:
                    continue
                heal_expr = spec.get("heal_expr")
                if not heal_expr:
                    continue
                try:
                    from warhammer40k_ai.utility.dice import get_roll
                    amount = get_roll(heal_expr)
                    destroyed_by_model.heal(amount)
                    try:
                        self.event_system.publish(
                            "model_healed",
                            model=destroyed_by_model,
                            unit=destroyed_by_unit,
                            amount=amount,
                            reason=spec.get("source_ability", ""),
                        )
                    except Exception:
                        pass
                except Exception:
                    continue

    def _on_unit_destroyed_bloodshed_points(self, unit=None, destroyed_by_unit=None, **_kwargs) -> None:
        """World Eaters: Icon of Khorne grants Bloodshed points on enemy unit destruction."""
        if unit is None or destroyed_by_unit is None:
            return
        try:
            if destroyed_by_unit.get_parent_army() == unit.get_parent_army():
                return
        except Exception:
            return
        try:
            root = destroyed_by_unit.get_attached_unit_root()
        except Exception:
            root = destroyed_by_unit
        try:
            if not root.attached_unit_has_icon_of_khorne():
                return
        except Exception:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return
        try:
            fid = str(getattr(army, "faction_id", "") or "").strip().upper()
            if fid and fid != "WE":
                return
        except Exception:
            pass
        mgr = getattr(army, "blessings_of_khorne", None)
        if mgr is None:
            return
        try:
            mgr.bloodshed_points = int(getattr(mgr, "bloodshed_points", 0) or 0) + 1
        except Exception:
            return
        try:
            self.event_system.publish(
                "bloodshed_points_gained",
                player=army.player,
                amount=1,
                total=int(getattr(mgr, "bloodshed_points", 0) or 0),
                attacker_unit=root,
                target_unit=unit,
            )
        except Exception:
            pass

    def _on_unit_destroyed_blood_tithe(self, unit=None, destroyed_by_unit=None, **_kwargs) -> None:
        """World Eaters: Blood Tithe points (Khorne Daemonkin detachment)."""
        if unit is None:
            return

        def _publish_btp_update(*, player, total, amount, attacker_unit=None, target_unit=None, roll=None, source=""):
            try:
                payload = {
                    "player": player,
                    "amount": int(amount or 0),
                    "total": int(total or 0),
                    "attacker_unit": attacker_unit,
                    "target_unit": target_unit,
                }
                if roll is not None:
                    payload["roll"] = roll
                if source:
                    payload["source"] = source
                self.event_system.publish("blood_tithe_points_gained", **payload)
                self.event_system.publish(
                    "blood_tithe_updated",
                    player=player,
                    total=int(total or 0),
                    active=[a.name for a in we_mgr.get_active_blood_tithe_abilities()],
                )
            except Exception:
                pass

        # Enhancement: Blood-forged Armour (bearer destroyed -> gain 1 BTP).
        try:
            bearer_army = unit.get_parent_army()
        except Exception:
            bearer_army = None
        we_mgr = getattr(bearer_army, "world_eaters_detachments", None) if bearer_army is not None else None
        if we_mgr is not None and getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
            try:
                sr = getattr(unit, "special_rules", None)
                has_blood_forged = isinstance(sr, dict) and sr.get("enhancement_blood_forged_armour", False)
            except Exception:
                has_blood_forged = False
            if has_blood_forged:
                try:
                    if we_mgr.unit_is_blood_tithe_eligible(unit):
                        total = we_mgr.add_blood_tithe_points(1)
                        _publish_btp_update(
                            player=bearer_army.player,
                            total=total,
                            amount=1,
                            attacker_unit=None,
                            target_unit=unit,
                            source="Blood-forged Armour",
                        )
                except Exception:
                    pass

        if destroyed_by_unit is None:
            return
        try:
            if destroyed_by_unit.get_parent_army() == unit.get_parent_army():
                return
        except Exception:
            return
        try:
            root = destroyed_by_unit.get_attached_unit_root()
        except Exception:
            root = destroyed_by_unit
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return
        we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
            return
        try:
            if not we_mgr.unit_is_blood_tithe_eligible(root):
                return
        except Exception:
            return

        def _attached_unit_has_rule(u, key: str) -> bool:
            try:
                root_unit = u.get_attached_unit_root()
            except Exception:
                root_unit = u
            try:
                members = list(root_unit.get_attached_unit_members() or [])
            except Exception:
                members = [root_unit]
            for member in members:
                try:
                    sr = getattr(member, "special_rules", None)
                    if isinstance(sr, dict) and sr.get(key, False):
                        return True
                except Exception:
                    continue
            return False

        # Enhancement: Blade of Endless Bloodshed (melee kill -> auto gain 1 BTP).
        try:
            wp = _kwargs.get("destroyed_by_weapon_profile", None)
        except Exception:
            wp = None
        is_melee = False
        try:
            parent = getattr(wp, "parent_wargear", None)
            if parent is not None and parent.is_melee():
                is_melee = True
        except Exception:
            is_melee = False
        if is_melee and _attached_unit_has_rule(root, "enhancement_blade_of_endless_bloodshed"):
            total = we_mgr.add_blood_tithe_points(1)
            _publish_btp_update(
                player=army.player,
                total=total,
                amount=1,
                attacker_unit=root,
                target_unit=unit,
                source="Blade of Endless Bloodshed",
            )
            return

        try:
            from warhammer40k_ai.utility.dice import get_roll
            roll = int(get_roll("D6"))
        except Exception:
            roll = 0
        if roll < 3:
            return
        total = we_mgr.add_blood_tithe_points(1)
        _publish_btp_update(
            player=army.player,
            total=total,
            amount=1,
            attacker_unit=root,
            target_unit=unit,
            roll=int(roll),
        )

    def _on_unit_destroyed_power_from_pain(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "army", None)
            mgr = getattr(army, "power_from_pain", None) if army is not None else None
            if mgr is None:
                continue
            try:
                mgr.on_enemy_unit_destroyed(unit)
            except Exception:
                continue

    def _on_unit_destroyed_cult_ambush(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "cult_ambush", None) if army is not None else None
        if mgr is None:
            return
        try:
            if not mgr.can_spend_for_unit(unit):
                return
        except Exception:
            return
        try:
            player = getattr(army, "player", None)
        except Exception:
            player = None
        es = getattr(self, "event_system", None)
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human and es is not None:
            try:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("cult_ambush_prompt"):
                    es.publish(
                        "cult_ambush_prompt",
                        player=player,
                        unit=unit,
                        cost=mgr.resurgence_cost_for_unit(unit),
                        game=self,
                    )
                    return
            except Exception:
                pass
        try:
            mgr.handle_unit_destroyed(unit, game=self, player=player)
        except Exception:
            pass

    def _on_unit_move_ended_cult_ambush(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "army", None)
            mgr = getattr(army, "cult_ambush", None) if army is not None else None
            if mgr is None:
                continue
            try:
                mgr.on_enemy_unit_move_ended(unit, game=self)
            except Exception:
                continue

    def _on_unit_destroyed_acts_of_faith(self, unit=None, last_model=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "acts_of_faith", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.on_unit_destroyed(unit, game=self, game_map=self.map, last_model=last_model)
        except Exception:
            pass

    def _on_model_destroyed_acts_of_faith(self, unit=None, model=None, **_kwargs) -> None:
        if unit is None or model is None:
            return
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "acts_of_faith", None) if army is not None else None
        if mgr is None:
            return
        try:
            mgr.on_model_destroyed(unit, model, game=self, game_map=self.map)
        except Exception:
            pass

    def _on_unit_destroyed_transport_rules(self, unit=None, last_model=None, game_map=None, **_kwargs) -> None:
        """
        10th edition core Transport rule: when a Transport is destroyed, any embarked units must
        immediately disembark (or emergency disembark), take mortal wounds, and become battle-shocked.
        """
        if unit is None or game_map is None:
            return
        try:
            if not getattr(unit, "is_transport", False):
                return
        except Exception:
            return

        passengers = list(getattr(unit, "transport_passengers", []) or [])
        if not passengers:
            return

        # Capture last known transport base for disembark distance checks.
        try:
            if last_model is not None and getattr(last_model, "model_base", None) is not None:
                unit._last_known_base = copy.deepcopy(last_model.model_base)
        except Exception:
            unit._last_known_base = getattr(unit, "_last_known_base", None)

        for p in passengers:
            try:
                # Ensure passenger is not still in map list before disembarking (avoid duplicates)
                if hasattr(game_map, "units") and p in game_map.units:
                    game_map.units.remove(p)
            except Exception:
                pass
            try:
                p.disembark(
                    game_map=game_map,
                    transport_unit=unit,
                    destroyed_transport=True,
                    emergency=False,
                    current_turn=self.turn,
                )
            except Exception:
                # Never allow transport destruction to crash the game loop
                continue

        # Clear passengers list (disembark() should already remove them, but be defensive)
        try:
            unit.transport_passengers = []
        except Exception:
            pass

    def add_player(self, player: Player) -> None:
        """Add a player to the game."""
        self.players.append(player)
        player.set_game(self)

    def add_objective(self, objective: Objective) -> None:
        """Add an objective to the game."""
        self.objectives.append(objective)

    def add_command(self, command: str) -> None:
        """Add a command to the game."""
        self.commands.append(command)

    def get_current_player(self) -> Player:
        """Get the current player."""
        return self.players[self.current_player_index]

    def get_opponent(self) -> Player:
        """Get the opponent of the current player."""
        return self.players[(self.current_player_index + 1) % len(self.players)]

    def get_enemy_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to the opponent of the given player."""
        # Get their opponent (skip players without armies to avoid crashes in partial test setups).
        for p in self.players:
            if p is player:
                continue
            army = getattr(p, "get_army", lambda: None)()
            if army is not None:
                return list(getattr(army, "units", []) or [])
        return []

    def get_battlefield_size(self) -> tuple[int, int]:
        return self.battlefield.width, self.battlefield.height
    
    def set_attacker_defender(self, attacker_index: int, defender_index: int) -> None:
        """DEPRECATED: Set which player is the attacker and which is the defender.
        
        This method should not be used - attacker/defender roles are determined
        during the DETERMINE_ATTACKER_AND_DEFENDER setup phase only.
        """
        import warnings
        warnings.warn("set_attacker_defender is deprecated. Roles are determined during setup phase.", 
                     DeprecationWarning, stacklevel=2)
        self.attacker_index = attacker_index
        self.defender_index = defender_index
        # Defender always starts deployment
        self.deployment_turn_index = self.defender_index
    
    def get_current_deployment_player(self) -> Player:
        """Get the player whose turn it is to deploy."""
        return self.players[self.deployment_turn_index]
    
    def get_attacker(self) -> Player:
        """Get the attacking player."""
        return self.players[self.attacker_index]
    
    def get_defender(self) -> Player:
        """Get the defending player."""
        return self.players[self.defender_index]
    
    def is_deployment_phase(self) -> bool:
        """Check if we're in the deployment phase."""
        # We're in deployment phase if any units are not deployed and it's turn 1
        if self.turn != 1:
            return False
        
        for player in self.players:
            army = player.get_army()
            if army:
                undeployed_units = [u for u in army.units if not u.deployed]
                if undeployed_units:
                    return True
        return False
    
    def can_player_deploy_unit(self, player: Player) -> bool:
        """Check if the given player can deploy a unit (i.e., it's their deployment turn)."""
        if not self.is_deployment_phase():
            return False
        return player == self.get_current_deployment_player()
    
    def get_deployable_units(self, player: Player) -> List['Unit']:
        """Get units that the player can deploy during the deployment phase."""
        if not player.get_army():
            return []
        # Units with deployed=False still need to be placed on the battlefield.
        # Units with deployed=True have been handled (battlefield placement already done OR start in reserves OR start embarked/attached).
        deployable: List['Unit'] = []
        for u in list(player.get_army().units or []):
            if u is None:
                continue
            if getattr(u, "deployed", False):
                continue

            # Attached leaders deploy with their bodyguard
            try:
                if bool(getattr(u, "is_attached_leader", False)):
                    continue
            except Exception:
                pass

            # Embarked units deploy with their transport
            try:
                if bool(getattr(u, "is_embarked", False)) or getattr(u, "embarked_in", None) is not None:
                    continue
            except Exception:
                pass

            # Units allocated to any reserves are not deployed now
            try:
                if getattr(u, "reserve_status", "deployed") in ("reserves", "strategic_reserves"):
                    continue
            except Exception:
                pass

            deployable.append(u)

        return deployable
    
    def record_deployment_action(self, player: Player, unit: 'Unit', action: str, location: tuple = None) -> None:
        """Record a deployment action for display in the InfoPane."""
        if action == 'deployed' and location:
            # Accept both 2D (x,y) and 3D (x,y,z) tuples; ignore extra fields (e.g. facing)
            try:
                x = float(location[0])
                y = float(location[1])
                z = float(location[2]) if len(location) > 2 else 0.0
            except Exception:
                x = y = None
                z = 0.0

            if x is not None and y is not None:
                if abs(z) > 1e-6:
                    action_text = f"{unit.name} deployed at ({x:.1f}, {y:.1f}, {z:.1f})"
                else:
                    action_text = f"{unit.name} deployed at ({x:.1f}, {y:.1f})"
            else:
                action_text = f"{unit.name} deployed"
        elif action == 'reserves':
            action_text = f"{unit.name} placed in Reserves"
        elif action == 'strategic_reserves':
            action_text = f"{unit.name} placed in Strategic Reserves"
        else:
            action_text = f"{unit.name} - {action}"
        
        self.deployment_actions[player.name] = action_text

    def clear_deployment_actions(self) -> None:
        """Clear deployment action history after deployment phase ends."""
        self.deployment_actions = {}
        self.deployment_notice = None
        self.deployment_skip_turns = {}

    def _has_any_other_deployable_units(self, player_index: int) -> bool:
        """Return True if any other player (besides player_index) has deployable units."""
        for i, p in enumerate(self.players):
            if i == player_index:
                continue
            if self.get_deployable_units(p):
                return True
        return False

    def advance_deployment_turn(self, last_deployed_unit: Optional['Unit'] = None) -> None:
        """Advance to the next player's deployment turn.

        Special rule: If the current player deploys a TITANIC unit, they skip their next deployment turn.
        """
        if not self.is_deployment_phase():
            return

        n = len(self.players)
        if n <= 0:
            return

        # If a TITANIC unit was just deployed, the current player skips their next deployment turn.
        if last_deployed_unit is not None and last_deployed_unit.is_titanic:
            cur_idx = int(self.deployment_turn_index)
            self.deployment_skip_turns[cur_idx] = int(self.deployment_skip_turns.get(cur_idx, 0)) + 1
            try:
                deploying_player = self.players[cur_idx]
                opponent_idx = (cur_idx + 1) % n
                opponent_player = self.players[opponent_idx]
                if self.get_deployable_units(opponent_player):
                    self.deployment_notice = (
                        f"📣 {deploying_player.name} deployed a TITANIC unit — they will skip their next deployment turn. "
                        f"{opponent_player.name} will deploy again."
                    )
                else:
                    self.deployment_notice = (
                        f"📣 {deploying_player.name} deployed a TITANIC unit — they would skip their next deployment turn "
                        f"(no opponent units left to benefit)."
                    )
            except Exception:
                # Non-fatal: UI-only helper
                pass

        # Find the next eligible player:
        # - Skip players with no deployable units
        # - Apply "skip next deployment turn" unless there are no other deployable units remaining
        next_idx = (int(self.deployment_turn_index) + 1) % n
        attempts = 0
        while attempts < n:
            skip_cnt = int(self.deployment_skip_turns.get(next_idx, 0) or 0)
            if skip_cnt > 0 and self._has_any_other_deployable_units(next_idx):
                # Consume one skip and move to the next player.
                self.deployment_skip_turns[next_idx] = skip_cnt - 1
                try:
                    skipped_player = self.players[next_idx]
                    other_player = self.players[(next_idx + 1) % n]
                    self.deployment_notice = (
                        f"⏭️ {skipped_player.name} skips this deployment turn (TITANIC rule). "
                        f"{other_player.name} deploys again."
                    )
                except Exception:
                    pass
                next_idx = (next_idx + 1) % n
                attempts += 1
                continue

            candidate_player = self.players[next_idx]
            if self.get_deployable_units(candidate_player):
                self.deployment_turn_index = next_idx
                return

            next_idx = (next_idx + 1) % n
            attempts += 1

        # Fallback: leave turn index unchanged if nobody is deployable (deployment is effectively done).
        return
    
    def complete_deployment_phase(self, manual_phases: bool = False) -> None:
        """Force complete the deployment phase by auto-deploying remaining units one at a time."""
        print("🚀 Starting auto-deployment...")
        
        # Deploy units one at a time, respecting the deployment turn system
        max_attempts = 100  # Safety limit to prevent infinite loops
        attempts = 0
        
        while self.is_deployment_phase() and attempts < max_attempts:
            attempts += 1
            current_player = self.get_current_deployment_player()
            
            if not current_player:
                print("❌ No current deployment player found")
                break
            
            # Get units that need to be deployed for the current player
            undeployed_units = self.get_deployable_units(current_player)
            
            if not undeployed_units:
                # Current player has no more units to deploy, advance to next player
                print(f"Player {current_player.name} has no more units to deploy")
                self.advance_deployment_turn()
                continue
            
            # Auto-deploy the first undeployed unit for the current player
            unit = undeployed_units[0]
            print(f"Auto-deploying {unit.name} for {current_player.name}...")
            
            success = self.auto_deploy_unit(unit)
            if success:
                # Record deployment action
                if unit.position:
                    self.record_deployment_action(current_player, unit, 'deployed', unit.position)
                # Mark unit as deployed and advance to next player's turn
                unit.deployed = True
                self.advance_deployment_turn(unit)
            else:
                print(f"❌ Failed to auto-deploy {unit.name}, advancing anyway")
                # Force deployment to prevent infinite loop
                unit.deployed = True
                unit.reserve_status = 'reserves'  # Mark as failed deployment
                # Record reserves action
                self.record_deployment_action(current_player, unit, 'reserves')
                self.advance_deployment_turn()
            
            # In manual phases mode, pause after each deployment action and require SPACE to continue
            if manual_phases and self.is_deployment_phase():  # Only pause if deployment isn't finished
                print(f"🔧 Deployment action {attempts} completed. Press SPACE to continue deployment...")
                # Set a flag to indicate we're waiting for manual input during deployment
                self.waiting_for_deployment_input = True
                return  # Exit and wait for manual input
        
        if attempts >= max_attempts:
            print(f"⚠️ Auto-deployment stopped after {max_attempts} attempts to prevent infinite loop")
        
        print(f"🎯 Auto-deployment complete after {attempts} deployment actions")
        self.waiting_for_deployment_input = False
    
    def auto_deploy_unit(self, unit: 'Unit') -> bool:
        """Auto-deploy a unit using systematic grid-based search to avoid crowded areas."""
        import random
        
        # Get the unit's player for deployment zone lookup
        player_name = unit.get_parent_army().player.name if unit.get_parent_army() and unit.get_parent_army().player else None
        
        if not player_name:
            logger.error(f"Cannot auto-deploy {unit.name}: No player found")
            return False
        
        # Get deployment constraints
        battlefield_width, battlefield_height = self.get_battlefield_size()
        
        # Determine search area based on unit type and deployment zones
        if unit.has_infiltrate():
            # Infiltrate units can deploy anywhere except restricted areas
            search_zones = self._get_infiltrate_search_zones(player_name, battlefield_width, battlefield_height)
        else:
            # Normal units must deploy within their deployment zone
            if hasattr(self, 'deployment_zones') and player_name in self.deployment_zones:
                zone = self.deployment_zones[player_name]

                # Helper: maximum model base radius approximation
                def _max_base_radius(u: 'Unit') -> float:
                    max_r = 0.5
                    for m in u.models:
                        r = getattr(m.model_base, 'radius', None)
                        if r is None and hasattr(m.model_base, 'get_radius'):
                            r = m.model_base.get_radius()
                        try:
                            r = float(r)
                        except Exception:
                            try:
                                r = float(max(r))
                            except Exception:
                                r = 0.5
                        max_r = max(max_r, r)
                    return max_r

                # Prepare effective mission polygons eroded by base radius to improve hit-rate
                mission_effective_zones = []

                # Check if this is the new mission zone system or old system
                if 'mission_zones' in zone and zone['mission_zones']:
                    from shapely.geometry import Point as _ShPoint, Polygon as _ShPoly
                    from shapely.ops import unary_union as _sh_union

                    # Compute erosion distance based on unit footprint
                    erosion = _max_base_radius(unit)
                    # Reasonable extra margin for formation spread
                    erosion += max(0.25, 0.1 * len(unit.models))

                    # Build effective (cutout-subtracted) polygons and erode
                    for mz in zone['mission_zones']:
                        poly = _ShPoly(mz.vertices)
                        # Subtract cutouts if any
                        if getattr(mz, 'cutouts', None):
                            for c in mz.cutouts:
                                cg = c.get_shapely_geometry()
                                if cg is not None:
                                    poly = poly.difference(cg)
                        # Erode polygon by erosion distance (buffer with negative value)
                        eff = poly.buffer(-erosion)
                        if not eff.is_empty:
                            mission_effective_zones.append(eff)

                    # If nothing usable after erosion, fall back to un-eroded zones
                    if not mission_effective_zones:
                        for mz in zone['mission_zones']:
                            mission_effective_zones.append(_ShPoly(mz.vertices))

                    # Construct an overall bbox to seed grid, but we will filter by polygon.contains
                    if mission_effective_zones:
                        union = _sh_union(mission_effective_zones)
                        min_x, min_y, max_x, max_y = union.bounds
                    else:
                        min_x = min_y = 0.0
                        max_x, max_y = battlefield_width, battlefield_height

                    search_zones = [(max(min_x, 0.0), min(max_x, battlefield_width),
                                     max(min_y, 0.0), min(max_y, battlefield_height))]
                else:
                    # No mission_zones present -> invalid configuration for deployment
                    return False
            else:
                logger.error(f"No deployment zone found for {player_name}")
                return False
        
        # Use systematic grid-based search instead of random
        for zone_idx, zone in enumerate(search_zones):
            x_min, x_max, y_min, y_max = zone
            
            if x_max <= x_min or y_max <= y_min:
                continue  # Skip invalid zones
            
            # Create a finer grid of potential positions
            grid_spacing = 1.0  # Reduced from 2.0 to 1.0 for finer search
            x_positions = []
            y_positions = []
            
            # Generate grid positions (adaptive to unit size)
            x = x_min
            # Use diameter-based spacing where possible to reduce futile tests
            base_step = 2.0 * max(0.5, len(unit.models) * 0.05)
            step = max(0.75, min(2.0, base_step))
            while x <= x_max:
                x_positions.append(x)
                x += step
            
            y = y_min
            while y <= y_max:
                y_positions.append(y)
                y += step
            
            # Shuffle the positions to avoid predictable patterns
            test_positions = [(x, y) for x in x_positions for y in y_positions]
            random.shuffle(test_positions)
            
            # Test positions systematically
            for x, y in test_positions:
                z = 0.0
                
                # If using mission polygons, skip points outside eroded zones early
                try:
                    if 'mission_effective_zones' not in locals():
                        pass
                    else:
                        inside_any = False
                        for eff in mission_effective_zones:
                            if eff.contains(_ShPoint(x, y)):
                                inside_any = True
                                break
                        if not inside_any:
                            continue
                except Exception:
                    # If Shapely not available or error, continue with regular checks
                    pass

                # Quick check: is this position too close to existing units?
                if self._is_position_too_crowded(x, y, unit, player_name):
                    continue
                
                # Check if this position would place all models wholly within the deployment zone
                try:
                    if self.is_valid_deployment_position(unit, x, y, player_name):
                        # Use the proper deployment flow
                        if self._deploy_unit_at_position(unit, x, y, z):
                            print(f"✅ Successfully auto-deployed {unit.name} at ({x:.1f}, {y:.1f})")
                            return True
                except Exception as e:
                    # If formation finding fails, continue to next position
                    continue
        
        print(f"❌ Failed to auto-deploy {unit.name} - no valid positions found")
        return False
    
    def _is_position_too_crowded(self, x: float, y: float, unit: 'Unit', player_name: str) -> bool:
        """Quick check if a position is too close to existing units to likely succeed."""
        # Much more reasonable minimum distance - just need to avoid immediate overlap
        min_distance = max(2.0, len(unit.models) * 0.4)  # Reduced from 4.0 and 0.8
        
        # Check distance to all deployed units
        for player in self.players:
            if not player.get_army():
                continue
            for existing_unit in player.get_army().units:
                if not existing_unit.deployed or existing_unit.reserve_status != 'deployed':
                    continue
                
                # Check distance to closest model in existing unit
                closest_distance = float('inf')
                for model in existing_unit.models:
                    if model.is_alive:
                        model_pos = model.get_location()
                        if model_pos:
                            distance = ((x - model_pos[0]) ** 2 + (y - model_pos[1]) ** 2) ** 0.5
                            closest_distance = min(closest_distance, distance)

                if closest_distance < min_distance:
                    return True
        
        return False

    def _get_infiltrate_search_zones(self, player_name: str, battlefield_width: float, battlefield_height: float) -> list:
        """Get valid search zones for infiltrate units (avoiding enemy deployment zones and 9\" buffer)."""
        # We intentionally do NOT derive "safe" search rectangles from deployment-zone bounding boxes.
        # Infiltrate legality is enforced by the validation logic itself (enemy zone + 9" buffer + enemy models).
        margin = 3.0
        return [(margin, battlefield_width - margin, margin, battlefield_height - margin)]

    def _deploy_unit_at_position(self, unit: 'Unit', x: float, y: float, z: float) -> bool:
        """Deploy a unit at the specified position using the same flow as manual deployment."""
        try:
            # Use the exact same approach as manual deployment in GameView.on_mouse_press
            # Calculate model positions (this also sets the positions internally)
            # CRITICAL: Use deployment-specific boundary repulsors to ensure models stay within deployment zones
            # This must match the repulsors used in is_valid_deployment_position for consistency
            deployment_repulsors = self.get_boundary_repulsors(unit, context='deployment')
            model_positions = unit.calculate_model_positions(x, y, self.map, avoid_friendly_units=False, boundary_repulsors=deployment_repulsors)
            
            if not model_positions:
                try:
                    print(f"🔴 DEBUG: Infiltrate - no model positions found for {unit.name} at candidate ({x:.1f}, {y:.1f})")
                except Exception:
                    pass
                return False
            
            # CRITICAL: Validate that all models are actually within deployment zone after positioning
            # This is a final safety check to catch any edge cases where models extend outside zones
            # EXCEPTION: Skip this check for Infiltrate units as they can deploy outside deployment zones
            player_name = unit.get_parent_army().player.name if unit.get_parent_army() and unit.get_parent_army().player else None
            if player_name and not unit.has_infiltrate():
                for model, position in zip(unit.models, model_positions):
                    model_x, model_y = position[0], position[1]
                    if not self.is_position_wholly_in_deployment_zone(model_x, model_y, model.model_base, player_name):
                        print(f"🔴 CRITICAL: Auto-deployment validation failed - {unit.name} {model.name} at ({model_x:.1f}, {model_y:.1f}) extends outside deployment zone")
                        return False
            
            # Unit position is now determined by model positions
            
            # Place unit on map (same as manual)
            if self.map and self.map.place_unit(unit):
                # Don't set unit.deployed here - let the calling function handle it
                return True
            else:
                return False
                
        except Exception as e:
            return False



    def _auto_position_models(self, unit: 'Unit', center_x: float, center_y: float, center_z: float) -> None:
        """Simple model positioning for auto-deployment without complex validation."""
        import math
        
        if len(unit.models) == 1:
            # Single model - place at center
            unit.models[0].set_location(center_x, center_y, center_z, 0.0)
        else:
            # Multiple models - arrange in a simple circle or line
            coherency_distance = unit.coherency_distance
            models_per_row = min(len(unit.models), 5)  # Max 5 models per row
            
            for i, model in enumerate(unit.models):
                if len(unit.models) <= 5:
                    # Small unit - arrange in a line
                    offset_x = (i - (len(unit.models) - 1) / 2) * (coherency_distance * 0.8)
                    model_x = center_x + offset_x
                    model_y = center_y
                else:
                    # Larger unit - arrange in rows
                    row = i // models_per_row
                    col = i % models_per_row
                    offset_x = (col - (models_per_row - 1) / 2) * (coherency_distance * 0.8)
                    offset_y = row * (coherency_distance * 0.8)
                    model_x = center_x + offset_x
                    model_y = center_y + offset_y
                
                model.set_location(model_x, model_y, center_z, 0.0)

    def is_position_in_deployment_zone(self, x: float, y: float, player_name: str) -> bool:
        """Check if a position is within a player's deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False
        
        if player_name not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_name]
        
        # Only mission zones are supported
        if 'mission_zones' in zone and zone['mission_zones']:
            for mission_zone in zone['mission_zones']:
                if mission_zone.contains_point(x, y):
                    return True
        return False

    def is_model_wholly_in_deployment_zone(self, model: 'Model', player_name: str) -> bool:
        """Check if a model's entire base is wholly within a player's deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            raise RuntimeError("Deployment zones not configured (invalid configuration).")
        
        if player_name not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_name]
        
        # Get model position and base size
        model_x, model_y = model.get_location()[:2]
        base = model.model_base
        base_radius = base.get_radius()
        
        # Require mission_zones polygons
        if 'mission_zones' not in zone or not zone['mission_zones']:
            raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")

        for mission_zone in zone['mission_zones']:
            if base.base_type.name == 'CIRCULAR':
                if mission_zone.contains_circular_base(model_x, model_y, base_radius):
                    return True
            else:
                base_vertices = base.get_vertices_at_position(model_x, model_y)
                if mission_zone.contains_polygon_base(base_vertices):
                    return True
        return False

    def is_position_wholly_in_deployment_zone(self, x: float, y: float, model_base, player_name: str) -> bool:
        """Check if a model base at (x,y) is wholly within the player's deployment zone,
        using mission zones with cutout-aware Shapely checks when available."""
        # Require configured zones
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False

        # Player must have a zone
        if player_name not in self.deployment_zones:
            return False

        zone_info = self.deployment_zones[player_name]

        # Only support mission_zones from missions.py with cutouts
        if 'mission_zones' in zone_info and zone_info['mission_zones']:
            for mission_zone in zone_info['mission_zones']:
                if model_base.base_type.name == 'CIRCULAR':
                    # Coerce radius to scalar
                    radius_val = getattr(model_base, 'radius', None)
                    if radius_val is None:
                        radius_val = model_base.get_radius() if hasattr(model_base, 'get_radius') else 0.5
                    try:
                        radius_val = float(radius_val)
                    except Exception:
                        try:
                            radius_val = float(max(radius_val))
                        except Exception:
                            radius_val = 0.5
                    if mission_zone.contains_circular_base(x, y, radius_val):
                        return True
                else:
                    # Use provided Shapely geometry from the base itself (no legacy vertex fallback)
                    if not hasattr(model_base, 'get_base_shape_at'):
                        return False
                    base_geom = model_base.get_base_shape_at(x, y, getattr(model_base, 'facing', 0.0))
                    if mission_zone.contains_base_geometry(base_geom):
                        return True
            return False
        return False

    def is_position_in_enemy_deployment_zone(self, x: float, y: float, player_name: str) -> bool:
        """Check if a position is within any enemy deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False
        
        for zone_player_name, zone in self.deployment_zones.items():
            if zone_player_name != player_name:
                # Deployment zones are polygons (mission_zones). No rectangular fallback is supported.
                if 'mission_zones' not in zone or not zone['mission_zones']:
                    raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
                for mission_zone in zone['mission_zones']:
                    if mission_zone.contains_point(x, y):
                        return True
        return False

    def get_distance_to_enemy_deployment_zone(self, x: float, y: float, player_name: str) -> float:
        """Get the minimum distance from a position to any enemy deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return float('inf')
        
        min_distance = float('inf')
        
        for zone_player_name, zone in self.deployment_zones.items():
            if zone_player_name != player_name and 'mission_zones' in zone and zone['mission_zones']:
                from shapely.geometry import Point as _ShPoint
                from shapely.geometry import Polygon as _ShPoly
                pt = _ShPoint(x, y)
                for mission_zone in zone['mission_zones']:
                    poly = _ShPoly(mission_zone.vertices)
                    d = pt.distance(poly)
                    if d < min_distance:
                        min_distance = d
        
        return min_distance

    def get_distance_to_enemy_models(self, x: float, y: float, player_name: str) -> float:
        """Get the minimum distance from a position to any enemy model."""
        min_distance = float('inf')
        
        for player in self.players:
            if player.name != player_name and player.get_army():
                for unit in player.get_army().units:
                    if unit.deployed and unit.reserve_status == 'deployed':
                        for model in unit.models:
                            model_x, model_y = model.get_location()[:2]
                            distance = ((x - model_x) ** 2 + (y - model_y) ** 2) ** 0.5
                            min_distance = min(min_distance, distance)
        
        return min_distance

    def get_boundary_repulsors(self, unit: 'Unit', context: str = 'deployment') -> List:
        """Generate boundary repulsors for spatial collision detection.
        
        Args:
            unit: The unit being positioned
            context: 'deployment' or 'movement' - determines which boundaries to include
            
        Returns:
            List of Shapely polygons representing boundary repulsors
        """
        from shapely.geometry import Polygon, Point
        from shapely.affinity import scale
        
        repulsors = []
        battlefield_width, battlefield_height = self.get_battlefield_size()
        player_name = unit.get_parent_army().player.name if unit.get_parent_army() and unit.get_parent_army().player else None
        
        if context == 'deployment':
            # For deployment, add deployment zone boundaries (mission-aware) and cutouts as repulsors
            if hasattr(self, 'deployment_zones') and self.deployment_zones and player_name:
                if player_name in self.deployment_zones:
                    zone = self.deployment_zones[player_name]
                    repulsor_thickness = 0.5  # 0.5 inch thick edge repulsor ring

                    # New mission system: polygon zones + cutouts
                    if 'mission_zones' in zone and zone['mission_zones']:
                        from shapely.geometry import Polygon as _ShPoly
                        for mz in zone['mission_zones']:
                            poly = _ShPoly(mz.vertices)
                            # Outer ring to repel from edges (outside only)
                            ring = poly.buffer(repulsor_thickness).difference(poly)
                            if not ring.is_empty:
                                repulsors.append(ring)
                            # Cutouts act as hard blockers
                            if getattr(mz, 'cutouts', None):
                                for c in mz.cutouts:
                                    cg = c.get_shapely_geometry()
                                    if cg is not None and not cg.is_empty:
                                        repulsors.append(cg)
                    else:
                        raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
        
        elif context == 'movement':
            # For movement, add battlefield edge boundaries as repulsors
            # This prevents units from moving off the battlefield
            repulsor_thickness = 0.5  # 0.5 inch thick repulsor zones
            
            # Left battlefield edge repulsor
            left_edge = Polygon([
                (-repulsor_thickness, -repulsor_thickness),
                (0, -repulsor_thickness),
                (0, battlefield_height + repulsor_thickness),
                (-repulsor_thickness, battlefield_height + repulsor_thickness)
            ])
            repulsors.append(left_edge)
            
            # Right battlefield edge repulsor
            right_edge = Polygon([
                (battlefield_width, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, battlefield_height + repulsor_thickness),
                (battlefield_width, battlefield_height + repulsor_thickness)
            ])
            repulsors.append(right_edge)
            
            # Bottom battlefield edge repulsor
            bottom_edge = Polygon([
                (-repulsor_thickness, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, 0),
                (-repulsor_thickness, 0)
            ])
            repulsors.append(bottom_edge)
            
            # Top battlefield edge repulsor
            top_edge = Polygon([
                (-repulsor_thickness, battlefield_height),
                (battlefield_width + repulsor_thickness, battlefield_height),
                (battlefield_width + repulsor_thickness, battlefield_height + repulsor_thickness),
                (-repulsor_thickness, battlefield_height + repulsor_thickness)
            ])
            repulsors.append(top_edge)
        
        return repulsors

    def is_valid_deployment_position(self, unit: 'Unit', x: float, y: float, player_name: str) -> bool:
        """Check if a position is valid for deploying a unit during deployment phase."""
        # Units in reserves don't need position validation
        if unit.reserve_status in ['reserves', 'strategic_reserves']:
            return True
        
        # Check if unit has Infiltrate ability
        if unit.has_infiltrate():
            # Infiltrate units can deploy anywhere except:
            # 1. Inside enemy deployment zone
            # 2. Within 9" of enemy deployment zone
            # 3. Within 9" of enemy models
            
            # For infiltrate units, we need to check each model's base at the proposed position
            # Calculate model positions using the same logic as unit deployment
            # NOTE: Don't use boundary_repulsors for validation - they make formation finding too restrictive
            # During deployment, use relaxed friendly unit avoidance to allow tighter formations
            # Use deployment boundary repulsors (mission-zone aware) to guide formation inside zone
            deployment_repulsors = self.get_boundary_repulsors(unit, context='deployment')
            model_positions = unit.calculate_model_positions(
                x, y, self.map, avoid_friendly_units=False, boundary_repulsors=deployment_repulsors
            )
            
            if not model_positions:
                return False
                
            from .map import validate_ruins_placement
            for model, position in zip(unit.models, model_positions):
                model_x, model_y = position[0], position[1]
                
                # Check if any part of the model is in enemy deployment zone
                if self.is_position_in_enemy_deployment_zone(model_x, model_y, player_name):
                    try:
                        model_name = getattr(model, 'name', 'model')
                        print(f"🔴 DEBUG: Infiltrate - {unit.name} {model_name} at ({model_x:.1f}, {model_y:.1f}) is inside enemy deployment zone")
                    except Exception:
                        pass
                    return False
                
                # Check 9" distance to enemy deployment zone (from model edge)
                base_radius = model.model_base.get_radius()
                distance_to_enemy_zone = self.get_distance_to_enemy_deployment_zone(model_x, model_y, player_name)
                if distance_to_enemy_zone - base_radius < 9.0:
                    try:
                        model_name = getattr(model, 'name', 'model')
                        print(f"🔴 DEBUG: Infiltrate - {unit.name} {model_name} too close to enemy zone: edge_distance={distance_to_enemy_zone:.2f}\" base_radius={base_radius:.2f}\" < 9\"")
                    except Exception:
                        pass
                    return False
                
                # Check 9" distance to enemy models (from model edge)
                distance_to_enemy_models = self.get_distance_to_enemy_models(model_x, model_y, player_name)
                if distance_to_enemy_models - base_radius < 9.0:
                    try:
                        model_name = getattr(model, 'name', 'model')
                        print(f"🔴 DEBUG: Infiltrate - {unit.name} {model_name} too close to enemy models: edge_distance={distance_to_enemy_models:.2f}\" base_radius={base_radius:.2f}\" < 9\"")
                    except Exception:
                        pass
                    return False
                # RUINS validation: cannot start/end overlapping walls/floors
                model_z = position[2] if len(position) > 2 else 0.0
                ruins_validation = validate_ruins_placement(unit, (model_x, model_y, model_z), self.map.terrain_features, moving_model=model)
                if not ruins_validation['valid']:
                    try:
                        model_name = getattr(model, 'name', 'model')
                        reason = ruins_validation.get('reason', 'unknown')
                        floor_level = ruins_validation.get('floor_level', '?')
                        print(f"🔴 DEBUG: Infiltrate - RUINS validation failed for {unit.name} {model_name}: {reason} (floor {floor_level})")
                    except Exception:
                        pass
                    return False
            
            return True
        else:
            # Normal units must be WHOLLY within their own deployment zone
            # Check that every model's entire base would be within the deployment zone at the proposed position
            # Calculate model positions using the same logic as unit deployment
            # NOTE: Don't use boundary_repulsors for validation - they make formation finding too restrictive
            # During deployment, use relaxed friendly unit avoidance to allow tighter formations
            deployment_repulsors = self.get_boundary_repulsors(unit, context='deployment')
            model_positions = unit.calculate_model_positions(
                x, y, self.map, avoid_friendly_units=False, boundary_repulsors=deployment_repulsors
            )
            
            if not model_positions:
                return False
                
            from .map import validate_ruins_placement
            for model, position in zip(unit.models, model_positions):
                model_x, model_y, model_z = position[0], position[1], position[2]
                
                # Check if this model would be wholly within the deployment zone
                if not self.is_position_wholly_in_deployment_zone(model_x, model_y, model.model_base, player_name):
                    try:
                        model_name = getattr(model, 'name', 'model')
                        print(f"🔴 DEBUG: Zone check failed for {unit.name} {model_name} at ({model_x:.1f}, {model_y:.1f}) in player '{player_name}' zone")
                    except Exception:
                        pass
                    return False
                
                # Check RUINS terrain placement rules
                ruins_validation = validate_ruins_placement(unit, (model_x, model_y, model_z), self.map.terrain_features, moving_model=model)
                if not ruins_validation['valid']:
                    try:
                        model_name = getattr(model, 'name', 'model')
                        print(f"🔴 DEBUG: RUINS validation failed for {unit.name} {model_name}: {ruins_validation['reason']}")
                    except Exception:
                        pass
                    return False
            return True

    def is_valid_single_model_deployment(self, model: 'Model', x: float, y: float, z: float, player_name: str) -> dict:
        """Validate deploying a single model at (x,y,z) during deployment.

        Applies deployment-zone rules (infiltrate vs normal) and RUINS placement rules for the model only.

        Returns a dict: { 'valid': bool, 'reason': str }
        """
        unit = model.parent_unit
        # Units destined for reserves are not placed on battlefield
        if unit.reserve_status in ['reserves', 'strategic_reserves']:
            return {'valid': False, 'reason': 'Unit is in reserves'}

        # Infiltrate logic: anywhere except inside enemy zone or within 9" from enemy zone/models (edge of base)
        if unit.has_infiltrate():
            # Inside enemy zone
            if self.is_position_in_enemy_deployment_zone(x, y, player_name):
                return {'valid': False, 'reason': 'Inside enemy deployment zone'}
            # 9" from enemy zone (from model edge)
            base_radius = model.model_base.get_radius()
            distance_to_enemy_zone = self.get_distance_to_enemy_deployment_zone(x, y, player_name)
            if distance_to_enemy_zone - base_radius < 9.0:
                return {'valid': False, 'reason': 'Too close to enemy deployment zone (<9\")'}
            # 9" from enemy models (from model edge)
            distance_to_enemy_models = self.get_distance_to_enemy_models(x, y, player_name)
            if distance_to_enemy_models - base_radius < 9.0:
                return {'valid': False, 'reason': 'Too close to enemy models (<9\")'}
        else:
            # Normal deployment: wholly within own zone
            if not self.is_position_wholly_in_deployment_zone(x, y, model.model_base, player_name):
                return {'valid': False, 'reason': 'Model base not wholly within deployment zone'}

        # RUINS placement validation for this single model
        from .map import validate_ruins_placement
        ruins_validation = validate_ruins_placement(unit, (x, y, z), self.map.terrain_features, moving_model=model)
        if not ruins_validation['valid']:
            return {'valid': False, 'reason': f"RUINS: {ruins_validation.get('reason', 'invalid placement')}"}

        return {'valid': True, 'reason': 'Valid single-model deployment'}

    def get_distance_between_units(self, unit1: 'Unit', unit2: 'Unit') -> float:
        """Calculate the shortest distance between any two models in the units."""
        shortest_distance = float('inf')
        for model1 in unit1.models:
            closest_model, distance = model1.return_closest_model_in_unit(unit2)
            shortest_distance = min(shortest_distance, distance)
        return shortest_distance

    def next_turn(self):
        """Advance to the next turn (legacy method - turn advancement now handled in next_phase)."""
        # This method is kept for compatibility but turn advancement is now handled in next_phase()
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        if self.current_player_index == 0:
            self.turn += 1
            # Reset phase to COMMAND_PHASE at the start of a new turn
            self.phase = BattleRoundPhases.COMMAND_PHASE

    def next_phase(self):
        """Advance to the next phase."""
        # Phase-end system actions that should occur before we publish phase_end.
        # NOTE: Reinforcements (arriving from reserves) occur at the end of the Movement phase.
        try:
            if getattr(self.phase, "name", None) == "MOVEMENT_PHASE":
                self.handle_reserves_arrival_phase()
        except Exception:
            pass

        # Publish end of current phase before advancing
        try:
            self.event_system.publish("phase_end", player=self.get_current_player(), phase=self.phase)
        except Exception:
            pass
        current_phase_value = self.phase.value
        next_phase_value = (current_phase_value + 1) % len(BattleRoundPhases)
        self.phase = BattleRoundPhases(next_phase_value)
        # Publish phase start for stratagem triggers
        try:
            self.event_system.publish("phase_start", player=self.get_current_player(), phase=self.phase)
        except Exception:
            pass
        
        # Phase-specific resets are no longer needed since we reset all round state at battle round start
        
        if next_phase_value == 0:  # If we've wrapped around to COMMAND_PHASE
            # End-of-turn scoring happens when a player's turn ends (before switching current player)
            try:
                self.end_of_turn_scoring()
            except Exception:
                pass
            # This means we've finished all phases for the current player
            # Switch to the next player
            self.current_player_index = (self.current_player_index + 1) % len(self.players)

            # Clear enemy model cache when switching players since enemy positions may have changed
            clear_enemy_model_cache(id(self.map))
            print(f"🔄 Player switched to {self.get_current_player().name} - cleared enemy model cache")
            
            # Track who started this battle round if not already set
            if self.battle_round_starting_player_index is None:
                # This is the first player switch of the game - the previous player started the round
                self.battle_round_starting_player_index = (self.current_player_index - 1) % len(self.players)
            
            # Check if we've completed a full battle round (both players have had their turn)
            if self.current_player_index == self.battle_round_starting_player_index:
                # We've cycled back to the player who started this battle round
                # Score end-of-battle-round primaries
                try:
                    self.end_of_battle_round_scoring()
                except Exception:
                    pass
                self.turn += 1
                self.battle_round_starting_player_index = self.current_player_index  # This player starts the next round
                
                # Reset round state for ALL units at the start of a new battle round
                for player in self.players:
                    for unit in player.get_army().units:
                        unit.initialize_round()
                    # Army-level battle round start hook (faction rules/buffs)
                    player.get_army().on_battle_round_start(self.turn)

                # Publish start-of-battle-round hook for UI/faction rules (best-effort)
                self.event_system.publish("battle_round_started", game=self, battle_round=self.turn)
            # Start of COMMAND_PHASE for the new current player
            try:
                self.start_command_phase()
            except Exception:
                pass

    def is_command_phase(self) -> bool:
        return self.phase == BattleRoundPhases.COMMAND_PHASE

    def _record_engaged_enemies_at_turn_start(self, player) -> None:
        if player is None:
            return
        try:
            game_map = self.map
        except Exception:
            game_map = None
        if game_map is None:
            return
        army = getattr(player, "army", None)
        if army is None:
            return
        for unit in list(getattr(army, "units", []) or []):
            try:
                if not unit.is_alive() or not unit.deployed:
                    continue
            except Exception:
                continue
            engaged_ids = set()
            try:
                enemies = game_map.get_enemy_units(unit) or []
            except Exception:
                enemies = []
            for enemy in enemies:
                try:
                    if not enemy.is_alive() or not enemy.deployed:
                        continue
                except Exception:
                    continue
                try:
                    if game_map.is_within_engagement_range(unit, enemy):
                        try:
                            root = enemy.get_attached_unit_root()
                        except Exception:
                            root = enemy
                        eid = getattr(root, "_id", None)
                        if eid:
                            engaged_ids.add(eid)
                except Exception:
                    continue
            try:
                unit.round_state.engaged_enemies_at_turn_start = engaged_ids
            except Exception:
                pass

    def _shadow_of_chaos_zones(self, player) -> set[str]:
        zones = {"own"}
        if player is None:
            return zones
        try:
            opponent = next((p for p in (self.players or []) if p is not player), None)
        except Exception:
            opponent = None
        objectives = list(getattr(self.map, "objectives", []) or [])
        nml_total = 0
        nml_controlled = 0
        enemy_total = 0
        enemy_controlled = 0
        for obj in objectives:
            try:
                loc = getattr(obj, "location", None)
                if loc is None or getattr(loc, "removed", False):
                    continue
                loc.update_control(self)
            except Exception:
                continue
            try:
                in_own = self.is_position_in_deployment_zone(loc.x, loc.y, player.name)
            except Exception:
                in_own = False
            in_enemy = False
            try:
                if opponent is not None:
                    in_enemy = self.is_position_in_deployment_zone(loc.x, loc.y, opponent.name)
            except Exception:
                in_enemy = False
            if in_enemy:
                enemy_total += 1
                if getattr(loc, "controlling_player", None) is player:
                    enemy_controlled += 1
            elif not in_own:
                nml_total += 1
                if getattr(loc, "controlling_player", None) is player:
                    nml_controlled += 1
        if nml_total and nml_controlled >= int(math.ceil(nml_total / 2.0)):
            zones.add("nml")
        if enemy_total and enemy_controlled >= int(math.ceil(enemy_total / 2.0)):
            zones.add("enemy")
        return zones

    def _unit_wholly_within_shadow_of_chaos(self, unit: Unit) -> bool:
        try:
            player = unit.get_parent_army().player
        except Exception:
            return False
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        try:
            mgr = getattr(army, "shadow_of_chaos", None) if army is not None else None
        except Exception:
            mgr = None
        if mgr is not None and getattr(mgr, "army_has_shadow", lambda: False)():
            try:
                if mgr.unit_wholly_within_dark_master_aura(unit, army, game=self):
                    return True
            except Exception:
                pass
        zones = self._shadow_of_chaos_zones(player)
        try:
            opponent = next((p for p in (self.players or []) if p is not player), None)
        except Exception:
            opponent = None
        for model in list(getattr(unit, "models", []) or []):
            try:
                if not getattr(model, "is_alive", True):
                    continue
            except Exception:
                continue
            try:
                x, y, _z, _f = model.get_location()
            except Exception:
                try:
                    x, y, _z = model.get_location()
                except Exception:
                    continue
            base = getattr(model, "model_base", None)
            if base is None:
                continue
            in_own = False
            in_enemy = False
            try:
                in_own = self.is_position_wholly_in_deployment_zone(float(x), float(y), base, player.name)
            except Exception:
                in_own = False
            try:
                if opponent is not None:
                    in_enemy = self.is_position_wholly_in_deployment_zone(float(x), float(y), base, opponent.name)
            except Exception:
                in_enemy = False
            if in_own:
                zone = "own"
            elif in_enemy:
                zone = "enemy"
            else:
                zone = "nml"
            if zone not in zones:
                return False
        return True

    def _unit_wholly_within_shadow_of_chaos_zones(self, unit: Unit) -> bool:
        """
        Shadow-of-Chaos check that only uses zone control (deployment zones / No Man's Land),
        excluding aura-based sources like The Dark Master.
        """
        try:
            player = unit.get_parent_army().player
        except Exception:
            return False
        zones = self._shadow_of_chaos_zones(player)
        try:
            opponent = next((p for p in (self.players or []) if p is not player), None)
        except Exception:
            opponent = None
        for model in list(getattr(unit, "models", []) or []):
            try:
                if not getattr(model, "is_alive", True):
                    continue
            except Exception:
                continue
            try:
                x, y, _z, _f = model.get_location()
            except Exception:
                try:
                    x, y, _z = model.get_location()
                except Exception:
                    continue
            base = getattr(model, "model_base", None)
            if base is None:
                continue
            in_own = False
            in_enemy = False
            try:
                in_own = self.is_position_wholly_in_deployment_zone(float(x), float(y), base, player.name)
            except Exception:
                in_own = False
            try:
                if opponent is not None:
                    in_enemy = self.is_position_wholly_in_deployment_zone(float(x), float(y), base, opponent.name)
            except Exception:
                in_enemy = False
            if in_own:
                zone = "own"
            elif in_enemy:
                zone = "enemy"
            else:
                zone = "nml"
            if zone not in zones:
                return False
        return True

    def _warp_rifts_min_distance(self, unit: Unit) -> float:
        try:
            if unit is None or not unit.has_any_keyword("LEGIONES DAEMONICA"):
                return 9.0
        except Exception:
            return 9.0
        try:
            if not unit._is_daemonic_incursion_detachment():
                return 9.0
        except Exception:
            return 9.0
        try:
            if not unit.has_deep_strike():
                return 9.0
        except Exception:
            return 9.0

        try:
            if self._unit_wholly_within_shadow_of_chaos_zones(unit):
                return 6.0
        except Exception:
            pass

        try:
            army = unit.get_parent_army()
        except Exception:
            army = None

        # Warp Rifts cannot bootstrap off the arriving unit's own aura.
        try:
            from .shadow_of_chaos import ShadowOfChaosManager
            from ..utility.aura_utils import unit_wholly_within_range_of_unit
        except Exception:
            ShadowOfChaosManager = None
            unit_wholly_within_range_of_unit = None

        if army is not None and ShadowOfChaosManager is not None and unit_wholly_within_range_of_unit is not None:
            try:
                for source in ShadowOfChaosManager._army_dark_master_units(army):
                    if source is unit:
                        continue
                    if unit_wholly_within_range_of_unit(source, unit, 6.0, use_attached_aggregate=True):
                        return 6.0
            except Exception:
                pass

            god_keywords = {"KHORNE", "TZEENTCH", "NURGLE", "SLAANESH"}
            try:
                for source in ShadowOfChaosManager._army_greater_daemon_units(army):
                    if source is unit:
                        continue
                    shared = False
                    for kw in god_keywords:
                        try:
                            if unit.has_any_keyword(kw) and source.has_any_keyword(kw):
                                shared = True
                                break
                        except Exception:
                            continue
                    if not shared:
                        continue
                    try:
                        if unit_wholly_within_range_of_unit(source, unit, 6.0, use_attached_aggregate=True):
                            return 6.0
                    except Exception:
                        continue
            except Exception:
                pass

        return 9.0
    
    def start_command_phase(self) -> None:
        """Start the command phase: active player gains normal CP, then resolves any bonus CP sources."""
        # Battle-shock expires at the start of *your* next Command phase (even if the unit was later destroyed).
        # Clear it before doing anything else in the Command phase.
        try:
            self.battle_shock_step_active = False
            from .status_effects import BattleShockEffect
            current_player = self.get_current_player()
            for unit in list(getattr(current_player.get_army(), "units", []) or []):
                fn = getattr(unit, "clear_battle_shock", None)
                if callable(fn):
                    fn()
                    continue
                # Fallback for legacy unit-like stubs
                try:
                    for eff in list(getattr(unit, "status_effects", []) or []):
                        if isinstance(eff, BattleShockEffect):
                            unit.remove_status_effect(eff)
                except Exception:
                    continue
        except Exception:
            pass

        # Space Marines: Oath of Moment target selection at the start of your Command phase.
        try:
            current_player = self.get_current_player()
            army = getattr(current_player, "get_army", lambda: None)()
            mgr = getattr(army, "oath_of_moment", None) if army is not None else None
            if mgr is not None:
                mgr.on_command_phase_start(game=self, player=current_player)
                if getattr(self, "event_system", None) is not None:
                    self.event_system.publish("oath_of_moment_prompt", player=current_player, game=self)
        except Exception:
            pass

        # Imperial Knights: Bondsman selection at the start of your Command phase.
        try:
            current_player = self.get_current_player()
            army = getattr(current_player, "get_army", lambda: None)()
            mgr = getattr(army, "bondsman", None) if army is not None else None
            if mgr is not None:
                mgr.on_command_phase_start(game=self, player=current_player)
                if getattr(self, "event_system", None) is not None:
                    self.event_system.publish("bondsman_prompt", player=current_player, game=self)
        except Exception:
            pass

        # Orks: Waaagh! (expires at your next Command phase; prompt to call).
        try:
            current_player = self.get_current_player()
            army = getattr(current_player, "get_army", lambda: None)()
            mgr = getattr(army, "waaagh", None) if army is not None else None
            if mgr is not None:
                mgr.on_command_phase_start(game=self, player=current_player)
        except Exception:
            pass
        # World Eaters: Blood Tithe spending at the start of your Command phase.
        try:
            current_player = self.get_current_player()
            army = getattr(current_player, "get_army", lambda: None)()
            mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if mgr is not None and hasattr(mgr, "on_command_phase_start"):
                mgr.on_command_phase_start(game=self, player=current_player)
        except Exception:
            pass

        # Core (per official app wording): at the start of your Command phase, before doing anything else,
        # BOTH players gain the normal Command phase CP. This normal CP does not count toward the
        # per-battle-round "bonus CP" guardrail.
        try:
            for p in list(self.players):
                if p is None:
                    continue
                if hasattr(p, "gain_normal_command_phase_cp"):
                    p.gain_normal_command_phase_cp()
                elif hasattr(p, "gain_command_points") and hasattr(p, "get_normal_command_phase_cp_gain"):
                    p.gain_command_points(p.get_normal_command_phase_cp_gain(), is_normal_command_phase_gain=True, reason="Normal Command phase CP")
                else:
                    # Best-effort fallback for legacy Player implementations.
                    try:
                        p.command_points += 1
                    except Exception:
                        pass
        except Exception:
            pass

        # Bonus CP sources that trigger in *your* Command phase (e.g., character alive -> gain 1CP).
        # This is NOT the normal command phase CP, so it is subject to the per-battle-round guardrail.
        try:
            cp_player = self.get_current_player()
            if cp_player is not None and hasattr(cp_player, "get_command_phase_bonus_cp_gain") and hasattr(cp_player, "gain_command_points"):
                bonus = int(cp_player.get_command_phase_bonus_cp_gain() or 0)
                if bonus > 0:
                    cp_player.gain_command_points(bonus, reason="Command phase bonus CP")
        except Exception:
            pass
        # Datasheet abilities: start of your Command phase regain lost wounds.
        try:
            self._apply_command_phase_regain_wounds(self.get_current_player())
        except Exception:
            pass
        # Drukhari: Power from Pain tokens at start of your Command phase.
        try:
            current_player = self.get_current_player()
            army = getattr(current_player, "army", None) if current_player is not None else None
            mgr = getattr(army, "power_from_pain", None) if army is not None else None
            if mgr is not None:
                mgr.on_command_phase_start(game=self, player=current_player)
        except Exception:
            pass
        # Explicit phase start publish for command phase entry
        try:
            self.event_system.publish("phase_start", player=self.get_current_player(), phase=self.phase)
        except Exception:
            pass
        # Drukhari: command phase Pain abilities (e.g., Fleshcraft).
        try:
            self._maybe_prompt_power_from_pain_command_phase()
        except Exception:
            pass
        # Tyranids: Shadow in the Warp (once per battle, either player's Command phase).
        try:
            self._maybe_prompt_shadow_in_the_warp()
        except Exception:
            pass
        # Orks: Waaagh! prompt (once per battle, start of your Command phase).
        try:
            self._maybe_prompt_waaagh()
        except Exception:
            pass

        # Execute command actions for current player's units (without resetting round state)
        current_player = self.get_current_player()
        # Burden of Trust: guards last until the start of your next turn
        try:
            self._clear_expired_guards_for_player(current_player)
        except Exception:
            pass
        # Secondary Missions: draw up to two at the start of your Command phase
        before = [getattr(c, 'name', 'Unknown') for c in getattr(current_player, 'active_secondaries', [])]
        current_player.draw_secondary_until_two(self)
        after = [getattr(c, 'name', 'Unknown') for c in getattr(current_player, 'active_secondaries', [])]
        newly_drawn = [name for name in after if name not in before]
        if newly_drawn:
            print(f"🃏 {current_player.name} active Secondaries: {', '.join(after)}")

        # Notify active secondaries about start-of-turn (for cards that snapshot start-of-turn state).
        for card in list(getattr(current_player, "active_secondaries", []) or []):
            fn = getattr(card, "on_turn_start", None)
            if callable(fn):
                try:
                    fn(self, current_player)
                except Exception:
                    pass
        # If in fifth battle round and going second, primary scoring is at end of turn, not here
        tested_ids: set[str] = set()
        self.battle_shock_step_active = True
        for unit in current_player.get_army().units:
            # Do battle shock tests and other command phase actions without resetting round state
            try:
                if hasattr(unit, "is_alive") and callable(getattr(unit, "is_alive")) and not unit.is_alive():
                    continue
            except Exception:
                pass
            # If forced to test for being Below Starting Strength, do not also test for being Below Half-strength
            # unless explicitly stated.
            try:
                if hasattr(unit, "is_below_starting_strength") and callable(getattr(unit, "is_below_starting_strength")) and unit.is_below_starting_strength():
                    print(f"⚠️  {unit.name} is below starting strength - taking Battle-Shock test")
                    unit.take_battle_shock_test(self.turn)
                    try:
                        tested_ids.add(str(getattr(unit, "_id", None) or id(unit)))
                    except Exception:
                        tested_ids.add(str(id(unit)))
                    continue
            except Exception:
                pass
            if unit.is_below_half_strength():
                print(f"⚠️  {unit.name} is below half strength - taking Battle-Shock test")
                unit.take_battle_shock_test(self.turn)
                try:
                    tested_ids.add(str(getattr(unit, "_id", None) or id(unit)))
                except Exception:
                    tested_ids.add(str(id(unit)))

        # Belakor: Pall of Despair can force additional tests for eligible enemy units.
        try:
            self._apply_pall_of_despair_forced_tests(current_player, tested_ids)
        except Exception:
            pass
        # Chaos Knights: Dismay can force additional tests for eligible enemy units.
        try:
            self._apply_harbingers_dismay_forced_tests(current_player, tested_ids)
        except Exception:
            pass
        self.battle_shock_step_active = False

        # Necrons: Reanimation Protocols at end of Command phase (resolve before scoring).
        try:
            self._apply_reanimation_protocols_end_command_phase(current_player)
        except Exception:
            pass

        # Primary mission scoring at command phase (2nd battle round onwards)
        if hasattr(current_player, 'primary_mission') and isinstance(current_player.primary_mission, PrimaryMissionCard):
            vp = current_player.primary_mission.score_at_command_phase(self, current_player)
            if vp:
                added = self.award_vp(
                    current_player,
                    vp,
                    source="primary",
                    card=current_player.primary_mission,
                    timing="End of Command phase",
                )
                if added:
                    print(f"🎯 {current_player.name} scored {added} VP from Primary: {current_player.primary_mission.name}")
        else:
            # Maintain legacy objective control updates for other systems
            for obj in self.map.objectives:
                if hasattr(obj, 'location') and hasattr(obj.location, 'update_control'):
                    obj.location.update_control(self)

        # Leagues of Votann: Prioritised Efficiency (Yield Points + mode updates).
        try:
            for p in list(getattr(self, "players", []) or []):
                army = getattr(p, "army", None)
                mgr = getattr(army, "prioritised_efficiency", None) if army is not None else None
                if mgr is None:
                    continue
                delta = mgr.gain_yield_points(self)
                mode_changed = False
                if p is current_player:
                    mode_changed = mgr.update_mode_for_player(self, p)
                if (delta or mode_changed) and getattr(self, "event_system", None) is not None:
                    self.event_system.publish(
                        "prioritised_efficiency_updated",
                        player=p,
                        game=self,
                        delta=int(delta or 0),
                        mode=getattr(mgr, "mode", None),
                        yield_points=int(getattr(mgr, "yield_points", 0) or 0),
                    )
        except Exception:
            pass

        # Burden of Trust: assign guards at the end of the Command phase.
        try:
            self._assign_burden_of_trust_guards(current_player)
        except Exception:
            pass

        # Publish end of Command phase for Stratagems like NEW ORDERS
        try:
            self.event_system.publish("phase_end", player=self.get_current_player(), phase=self.phase)
        except Exception:
            pass

    def is_movement_phase(self) -> bool:
        return self.phase == BattleRoundPhases.MOVEMENT_PHASE

    def is_shooting_phase(self) -> bool:
        return self.phase == BattleRoundPhases.SHOOTING_PHASE

    def is_charge_phase(self) -> bool:
        return self.phase == BattleRoundPhases.CHARGE_PHASE

    def is_fight_phase(self) -> bool:
        return self.phase == BattleRoundPhases.FIGHT_PHASE

    def can_score_objectives(self) -> bool:
        """Check if objectives can grant points in the current battle round.

        According to Warhammer 40k rules, objectives cannot grant points until
        the 2nd battle round.

        Returns:
            bool: True if objectives can grant points, False otherwise
        """
        return self.turn >= 2

    def get_battle_round(self) -> int:
        """Get the current battle round number.

        Returns:
            int: Current battle round (1-based)
        """
        return self.turn

    # ---------- Scoring windows and tracking ----------

    # Mission pack VP caps (as specified by project rules).
    VP_MAX_TOTAL = 100
    VP_MAX_PRIMARY = 50
    VP_MAX_SECONDARY = 40
    VP_MAX_BATTLE_READY = 10
    VP_MAX_PRIMARY_PLUS_SECONDARY = 90
    VP_MAX_PER_FIXED_SECONDARY_CARD = 20

    def _is_fixed_secondaries(self, player: Player | None = None) -> bool:
        """
        True if the game is using Fixed Secondaries.

        Scoring caps depend on this (20VP max per fixed card). The rest of the fixed-vs-tactical
        flow (draw/discard differences) may be implemented elsewhere.
        """
        mode = getattr(self, "secondary_mission_mode", None)
        return str(mode).lower() == "fixed"

    def _cap_card_vp(self, *, card: object | None, requested_vp: int, player: Player, source: str) -> int:
        """Apply per-card per-turn/total caps (including the Fixed-mission 20VP per-card cap)."""
        if not card:
            try:
                return max(0, int(requested_vp or 0))
            except Exception:
                return 0

        try:
            vp = int(requested_vp or 0)
        except Exception:
            vp = 0
        if vp <= 0:
            return 0

        # Per-turn cap (applies whenever the card scores this window).
        per_turn_cap = getattr(card, "score_cap_per_turn", None)
        if per_turn_cap is not None:
            try:
                vp = min(vp, int(per_turn_cap))
            except Exception:
                pass

        # Total cap across the battle for this specific card instance.
        total_scored = int(getattr(card, "total_scored", 0) or 0)
        total_cap = getattr(card, "score_cap_total", None)
        effective_total_cap: int | None = None
        if total_cap is not None:
            try:
                effective_total_cap = int(total_cap)
            except Exception:
                effective_total_cap = None

        # Fixed missions: 20VP maximum per Fixed Mission card.
        if source == "secondary" and self._is_fixed_secondaries(player):
            if effective_total_cap is None:
                effective_total_cap = self.VP_MAX_PER_FIXED_SECONDARY_CARD
            else:
                effective_total_cap = min(effective_total_cap, self.VP_MAX_PER_FIXED_SECONDARY_CARD)

        if effective_total_cap is not None:
            remaining = max(0, effective_total_cap - total_scored)
            vp = min(vp, remaining)

        return max(0, int(vp))

    def _notify_vp_capped(
        self,
        *,
        player: Player,
        source: str,
        requested_vp: int,
        awarded_vp: int,
        lost_vp: int,
        reasons: list[str],
        card: object | None = None,
    ) -> None:
        """Notify that VP were lost due to caps (via event + console fallback)."""
        if lost_vp <= 0:
            return
        card_name = None
        if card is not None:
            card_name = getattr(card, "name", None)
        payload = {
            "player": player,
            "source": source,
            "requested_vp": int(requested_vp),
            "awarded_vp": int(awarded_vp),
            "lost_vp": int(lost_vp),
            "reasons": list(reasons or []),
            "card_name": card_name,
        }
        # Primary channel: event system (UI/loggers can subscribe)
        try:
            if hasattr(self, "event_system") and hasattr(self.event_system, "publish"):
                self.event_system.publish("vp_capped", **payload)
        except Exception:
            pass
        # Fallback: always print (ensures humans see it in console logs even if no subscriber)
        try:
            label = source
            if card_name:
                label = f"{source} ({card_name})"
            reason_txt = ", ".join(reasons) if reasons else "cap reached"
            print(f"⚠️ {player.name} lost {lost_vp} VP from {label} due to {reason_txt} (attempted {requested_vp}, awarded {awarded_vp}).")
        except Exception:
            pass

    def _current_phase_label(self) -> str:
        try:
            if hasattr(self, "is_in_setup_phase") and self.is_in_setup_phase():
                try:
                    return self.get_current_setup_phase().name.replace("_", " ").title()
                except Exception:
                    return "Setup"
        except Exception:
            pass
        try:
            phase = getattr(self, "phase", None)
            if phase is None:
                return "Unknown Phase"
            if hasattr(phase, "name"):
                return str(phase.name).replace("_", " ").title()
            return str(phase)
        except Exception:
            return "Unknown Phase"

    def _record_vp_award(
        self,
        *,
        player: Player,
        requested_vp: int,
        awarded_vp: int,
        source: str,
        card: object | None = None,
        details: list[str] | str | None = None,
        timing: str | None = None,
    ) -> None:
        try:
            if not hasattr(player, "vp_history") or player.vp_history is None:
                player.vp_history = []
        except Exception:
            return
        card_name = getattr(card, "name", None) if card is not None else None
        card_scoring_text = None
        if card is not None:
            try:
                card_scoring_text = getattr(card, "scoring_text", None) or getattr(card, "summary", None)
            except Exception:
                card_scoring_text = None
        entry = {
            "round": int(getattr(self, "get_battle_round", lambda: 0)() or 0),
            "phase": self._current_phase_label(),
            "timing": timing,
            "source": str(source or ""),
            "card_name": card_name,
            "awarded": int(awarded_vp or 0),
            "requested": int(requested_vp or 0),
            "details": details,
            "card_scoring_text": card_scoring_text,
        }
        try:
            player.vp_history.append(entry)
        except Exception:
            pass

    def award_vp(
        self,
        player: Player,
        requested_vp: int,
        *,
        source: str,
        card: object | None = None,
        details: list[str] | str | None = None,
        timing: str | None = None,
    ) -> int:
        """
        Award VP to a player, enforcing caps:
        - Primary Mission: 50VP max
        - Secondary Missions: 40VP max (and 20VP max per Fixed card, if using Fixed)
        - Battle Ready Army: 10VP max (default TRUE)
        - Primary + Secondary combined: 90VP max
        - Total: 100VP max

        Returns the amount actually awarded (excess is lost).
        """
        try:
            vp = int(requested_vp or 0)
        except Exception:
            vp = 0
        if vp <= 0:
            return 0

        source_key = str(source).lower().strip()

        # Apply per-card caps first (per-turn/per-card totals).
        vp_after_card = self._cap_card_vp(card=card, requested_vp=vp, player=player, source=source_key)
        card_capped = vp_after_card < vp
        vp = vp_after_card
        if vp <= 0:
            # Card caps consumed all requested VP (edge case, but still a "capped" scenario).
            if requested_vp and int(requested_vp or 0) > 0 and card_capped:
                self._notify_vp_capped(
                    player=player,
                    source=source_key,
                    requested_vp=int(requested_vp or 0),
                    awarded_vp=0,
                    lost_vp=int(requested_vp or 0),
                    reasons=["per-card cap"],
                    card=card,
                )
            return 0

        total_scored = int(getattr(player, "score", 0) or 0)
        remaining_total = max(0, self.VP_MAX_TOTAL - total_scored)
        if remaining_total <= 0:
            self._notify_vp_capped(
                player=player,
                source=source_key,
                requested_vp=int(requested_vp or 0),
                awarded_vp=0,
                lost_vp=int(requested_vp or 0),
                reasons=["total cap (100VP)"],
                card=card,
            )
            return 0

        primary_scored = int(getattr(player, "vp_primary", 0) or 0)
        secondary_scored = int(getattr(player, "vp_secondary", 0) or 0)
        battle_ready_scored = int(getattr(player, "vp_battle_ready", 0) or 0)

        max_add = remaining_total
        reasons: list[str] = []
        if source_key == "primary":
            remaining_primary = max(0, self.VP_MAX_PRIMARY - primary_scored)
            remaining_combined = max(0, self.VP_MAX_PRIMARY_PLUS_SECONDARY - (primary_scored + secondary_scored))
            max_add = min(max_add, remaining_primary, remaining_combined)
            if remaining_primary <= 0:
                reasons.append("primary cap (50VP)")
            if remaining_combined <= 0:
                reasons.append("primary+secondary cap (90VP)")
        elif source_key == "secondary":
            remaining_secondary = max(0, self.VP_MAX_SECONDARY - secondary_scored)
            remaining_combined = max(0, self.VP_MAX_PRIMARY_PLUS_SECONDARY - (primary_scored + secondary_scored))
            max_add = min(max_add, remaining_secondary, remaining_combined)
            if remaining_secondary <= 0:
                reasons.append("secondary cap (40VP)")
            if remaining_combined <= 0:
                reasons.append("primary+secondary cap (90VP)")
        elif source_key in ("battle_ready", "battleready", "battle-ready"):
            remaining_br = max(0, self.VP_MAX_BATTLE_READY - battle_ready_scored)
            max_add = min(max_add, remaining_br)
            if remaining_br <= 0:
                reasons.append("battle ready cap (10VP)")

        to_add = min(vp, max_add)
        if to_add <= 0:
            # We were blocked by one or more caps.
            lost = int(requested_vp or 0)
            if card_capped:
                reasons = (reasons or []) + ["per-card cap"]
            if remaining_total <= 0 and "total cap (100VP)" not in reasons:
                reasons = (reasons or []) + ["total cap (100VP)"]
            self._notify_vp_capped(
                player=player,
                source=source_key,
                requested_vp=int(requested_vp or 0),
                awarded_vp=0,
                lost_vp=lost,
                reasons=reasons or ["cap reached"],
                card=card,
            )
            return 0

        # Commit to player totals.
        player.add_score(to_add)
        if source_key == "primary":
            player.vp_primary = primary_scored + to_add
        elif source_key == "secondary":
            player.vp_secondary = secondary_scored + to_add
        elif source_key in ("battle_ready", "battleready", "battle-ready"):
            player.vp_battle_ready = battle_ready_scored + to_add

        # Commit to card totals (only increment by the VP actually awarded).
        if card is not None and hasattr(card, "total_scored"):
            try:
                card.total_scored = int(getattr(card, "total_scored", 0) or 0) + int(to_add)
            except Exception:
                pass

        # Notify if the player didn't receive the full VP they would have otherwise gained.
        if int(requested_vp or 0) > int(to_add):
            notify_reasons = list(reasons or [])
            if card_capped:
                notify_reasons.append("per-card cap")
            if remaining_total < vp:
                # total cap was a limiting factor for this award
                notify_reasons.append("total cap (100VP)")
            self._notify_vp_capped(
                player=player,
                source=source_key,
                requested_vp=int(requested_vp or 0),
                awarded_vp=int(to_add),
                lost_vp=int(requested_vp or 0) - int(to_add),
                reasons=notify_reasons or ["cap reached"],
                card=card,
            )

        try:
            self._record_vp_award(
                player=player,
                requested_vp=int(requested_vp or 0),
                awarded_vp=int(to_add),
                source=source_key,
                card=card,
                details=details,
                timing=timing,
            )
        except Exception:
            pass

        return int(to_add)

    def finalize_battle_scoring(self) -> None:
        """Apply once-per-battle scoring that should only happen at the end of the battle."""
        if getattr(self, "_final_scoring_applied", False):
            return
        if not self.is_game_over():
            return
        for p in list(getattr(self, "players", []) or []):
            if getattr(p, "is_battle_ready", True):
                self.award_vp(
                    p,
                    self.VP_MAX_BATTLE_READY,
                    source="battle_ready",
                    details="Battle Ready bonus",
                    timing="End of battle",
                )
        self._final_scoring_applied = True

    def end_of_turn_scoring(self) -> None:
        """Apply end-of-turn scoring for primaries and secondaries, manage discard rules and CP gain."""
        turn_ending_player = self.get_current_player()

        # Track destroyed units for this turn should already be collected elsewhere; ensure attribute exists
        if not hasattr(self, 'destroyed_units_this_turn'):
            self.destroyed_units_this_turn = []
        if not hasattr(self, 'completed_actions_this_turn'):
            self.completed_actions_this_turn = []

        # Complete mission Actions that trigger at this end of turn FIRST (so scoring can see completions).
        self._complete_actions_for_turn_end(turn_ending_player)

        # Primary: special cases that score at end of turn (e.g., Terraform 1VP per terraformed objective)
        if hasattr(turn_ending_player, 'primary_mission') and isinstance(turn_ending_player.primary_mission, PrimaryMissionCard):
            vp = turn_ending_player.primary_mission.score_at_end_of_turn(self, turn_ending_player)
            if vp:
                added = self.award_vp(
                    turn_ending_player,
                    vp,
                    source="primary",
                    card=turn_ending_player.primary_mission,
                    timing="End of turn",
                )
                if added:
                    print(f"🎯 {turn_ending_player.name} scored {added} VP (end of turn) from Primary: {turn_ending_player.primary_mission.name}")

        # Primary: end-of-opponent's-turn scoring (only for primaries that explicitly do so, e.g. Burden of Trust).
        for p in list(getattr(self, "players", []) or []):
            if p is turn_ending_player:
                continue
            prim = getattr(p, "primary_mission", None)
            fn = getattr(prim, "score_at_end_of_opponents_turn", None)
            if callable(fn):
                try:
                    vp = int(fn(self, p, turn_ending_player) or 0)
                except Exception:
                    vp = 0
                if vp:
                    added = self.award_vp(
                        p,
                        vp,
                        source="primary",
                        card=prim,
                        timing="End of opponent turn",
                    )
                    if added:
                        print(f"🎯 {p.name} scored {added} VP (opponent turn end) from Primary: {getattr(prim, 'name', 'Primary')}")

        # Secondary: evaluate active cards for BOTH players based on the card's scoring window.
        from .mission_cards import SecondaryScoringWindow

        def _should_score(card: SecondaryMissionCard, scoring_player: Player, ending_player: Player) -> bool:
            try:
                window = card.score_window()
            except Exception:
                window = getattr(card, "scoring_window", SecondaryScoringWindow.END_OF_YOUR_TURN)
            if scoring_player is ending_player:
                return window in (SecondaryScoringWindow.END_OF_YOUR_TURN, SecondaryScoringWindow.END_OF_EITHER_PLAYER_TURN)
            return window in (SecondaryScoringWindow.END_OF_EITHER_PLAYER_TURN, SecondaryScoringWindow.END_OF_OPPONENT_TURN)

        # Tactical vs Fixed: in Fixed mode, scored cards are NOT discarded on scoring.
        is_fixed = self._is_fixed_secondaries()

        for scoring_player in list(self.players):
            achieved: list[SecondaryMissionCard] = []
            total_secondary_vp = 0
            for card in list(getattr(scoring_player, 'active_secondaries', [])):
                if not _should_score(card, scoring_player, turn_ending_player):
                    continue
                try:
                    result = card.score_at_end_of_turn(self, scoring_player)
                except Exception:
                    result = None
                if not result:
                    continue
                if result.vp:
                    timing = "End of your turn" if scoring_player is turn_ending_player else "End of opponent turn"
                    added = self.award_vp(
                        scoring_player,
                        result.vp,
                        source="secondary",
                        card=card,
                        details=getattr(result, "details", None),
                        timing=timing,
                    )
                    if added:
                        total_secondary_vp += added
                        print(f"🎯 {scoring_player.name} scored {added} VP from Secondary: {card.name}")
                if getattr(result, 'achieved', False):
                    achieved.append(card)

            # a) Tactical: If you scored 1+ VP from a Secondary, discard that card (achieved).
            if (not is_fixed) and total_secondary_vp > 0:
                scoring_player.discard_achieved_secondaries(achieved)

        # End-of-turn cleanup for temporary stratagem effects.
        try:
            army = getattr(turn_ending_player, "army", None)
            for unit in list(getattr(army, "units", []) or []):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if sr.pop("apoplectic_frenzy_active", None) is not None:
                    sr.pop("apoplectic_frenzy_turn", None)
                    unit.special_rules = sr
        except Exception:
            pass

        # Imperial Knights: Code Chivalric deed completion at end of turn.
        try:
            for p in list(getattr(self, "players", []) or []):
                army = getattr(p, "get_army", lambda: None)()
                mgr = getattr(army, "code_chivalric", None) if army is not None else None
                if mgr is None:
                    continue
                mgr.check_end_of_turn(game=self, turn_ending_player=turn_ending_player)
        except Exception:
            pass

        # b) Allow voluntary discard for current player to gain 1CP (UI/AI should call explicitly). Here we do nothing automatically.

        # c) If deck runs out, player cannot generate additional secondaries (handled by deck empty check during draws)

        # End of opponent's turn: optional abilities to move units into Strategic Reserves.
        try:
            self._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player)
        except Exception:
            pass

        # Clear per-turn event lists
        self.destroyed_units_this_turn = []
        self.completed_actions_this_turn = []
        self.models_destroyed_this_turn = []

    def end_of_battle_round_scoring(self) -> None:
        """Apply end-of-battle-round scoring for primaries that need it (e.g., Purge the Foe)."""
        # Build destroyed counts if not present
        if not hasattr(self, 'destroyed_units_this_battle_round_by_player'):
            self.destroyed_units_this_battle_round_by_player = {}
        for player in self.players:
            # Primary mission score
            if hasattr(player, 'primary_mission') and isinstance(player.primary_mission, PrimaryMissionCard):
                try:
                    vp = player.primary_mission.score_at_end_of_battle_round(self, player)
                except Exception:
                    vp = 0
                if vp:
                    added = self.award_vp(
                        player,
                        vp,
                        source="primary",
                        card=player.primary_mission,
                        timing="End of battle round",
                    )
                    if added:
                        print(f"🎯 {player.name} scored {added} VP (end of battle round) from Primary: {player.primary_mission.name}")

        # Imperial Knights: Code Chivalric deed completion at end of battle round.
        try:
            for p in list(getattr(self, "players", []) or []):
                army = getattr(p, "get_army", lambda: None)()
                mgr = getattr(army, "code_chivalric", None) if army is not None else None
                if mgr is None:
                    continue
                mgr.check_end_of_battle_round(game=self, battle_round=self.turn)
        except Exception:
            pass

        # Emperor's Children: Pledges to the Dark Prince resolution (Coterie of the Conceited).
        try:
            for p in list(getattr(self, "players", []) or []):
                army = getattr(p, "get_army", lambda: None)()
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is None or not getattr(mgr, "is_coterie_of_conceited", lambda: False)():
                    continue
                result = mgr.resolve_pledge_end_of_round(self)
                if result.get("resolved") and getattr(self, "event_system", None) is not None:
                    self.event_system.publish(
                        "emperors_children_pact_points_updated",
                        player=p,
                        game=self,
                        manager=mgr,
                        result=dict(result),
                    )
        except Exception:
            pass

        # Chapter Approved: any units still in reserves at the end of battle round 3 are destroyed.
        # `self.turn` is the current battle round number when this hook is invoked.
        try:
            if int(getattr(self, "turn", 0) or 0) == 3:
                for p in list(getattr(self, "players", []) or []):
                    army = getattr(p, "get_army", lambda: None)()
                    if army is None:
                        continue
                    to_remove = []
                    for u in list(getattr(army, "units", []) or []):
                        try:
                            if getattr(u, "is_in_reserves", lambda: False)() and bool(getattr(u, "_started_in_reserves", False)):
                                to_remove.append(u)
                        except Exception:
                            continue
                    for u in to_remove:
                        try:
                            logger.warning(f"💀 {u.name} destroyed - still in reserves at end of battle round 3")
                        except Exception:
                            pass
                        try:
                            army.units.remove(u)
                        except Exception:
                            pass
        except Exception:
            pass

    def record_unit_destroyed(self, unit: 'Unit') -> None:
        """Record a unit destroyed event and incrementally score relevant secondaries."""
        try:
            self.destroyed_units_this_turn.append(unit)
        except Exception:
            pass
        # Tally for Purge the Foe end-of-battle-round scoring
        try:
            owner_player = unit.get_parent_army().player if unit.get_parent_army() else None
            if owner_player is not None:
                self.destroyed_units_this_battle_round_by_player[owner_player] = self.destroyed_units_this_battle_round_by_player.get(owner_player, 0) + 1
        except Exception:
            pass

        # Incremental scoring for active secondaries that score on unit destruction
        try:
            owner_player = unit.get_parent_army().player if unit.get_parent_army() else None
            for player in self.players:
                if player is owner_player:
                    continue
                for card in getattr(player, 'active_secondaries', []) or []:
                    fn = getattr(card, "on_unit_destroyed", None)
                    if not callable(fn):
                        continue
                    try:
                        points = int(fn(self, player, unit) or 0)
                    except Exception:
                        points = 0
                    if points:
                        detail = None
                        try:
                            if getattr(unit, "is_character", False):
                                detail = f"Destroyed Character unit: {unit.name}"
                            else:
                                detail = f"Destroyed unit: {unit.name}"
                        except Exception:
                            detail = None
                        added = self.award_vp(
                            player,
                            points,
                            source="secondary",
                            card=card,
                            details=detail,
                            timing="Unit destroyed",
                        )
                        if added:
                            print(f"🎯 {player.name} scored {added} VP from Secondary: {getattr(card, 'name', 'Unknown')} (unit destroyed)")
        except Exception:
            pass

    def record_model_destroyed(self, model: 'Model') -> None:
        """Record a model destroyed event and incrementally score relevant secondaries that key off models."""
        try:
            self.models_destroyed_this_turn.append(model)
        except Exception:
            pass

        # Incremental scoring for active secondaries that score on model destruction (e.g., Fixed Assassination).
        try:
            for player in self.players:
                for card in getattr(player, "active_secondaries", []) or []:
                    fn = getattr(card, "on_model_destroyed", None)
                    if not callable(fn):
                        continue
                    try:
                        points = int(fn(self, player, model) or 0)
                    except Exception:
                        points = 0
                    if points:
                        detail = None
                        try:
                            unit = getattr(model, "parent_unit", None)
                            if getattr(model, "is_character", False):
                                detail = f"Destroyed Character: {model.name}"
                            else:
                                detail = f"Destroyed model: {model.name}"
                            if unit is not None and getattr(unit, "name", None) and unit.name != model.name:
                                detail = f"{detail} (Unit: {unit.name})"
                        except Exception:
                            detail = None
                        added = self.award_vp(
                            player,
                            points,
                            source="secondary",
                            card=card,
                            details=detail,
                            timing="Model destroyed",
                        )
                        if added:
                            print(f"🎯 {player.name} scored {added} VP from Secondary: {getattr(card, 'name', 'Unknown')} (model destroyed)")
        except Exception:
            pass

    # ---------- Mission Action APIs ----------

    def _is_unit_eligible_to_start_action(self, unit: 'Unit') -> Dict[str, Any]:
        # Not if Aircraft
        if getattr(unit, 'is_aircraft', False):
            return {"valid": False, "reason": "Aircraft cannot perform Actions"}
        # Not if Battle-shocked
        if unit.is_battle_shocked():
            return {"valid": False, "reason": "Battle-shocked units cannot perform Actions"}
        # Not if already performing an Action / locked
        if bool(getattr(unit.round_state, "action_locked_until_turn_end", False)) or getattr(unit.round_state, "performing_action_name", None):
            return {"valid": False, "reason": "Unit is already performing an Action this turn"}
        # OC 0 cannot perform
        if getattr(unit, 'objective_control', 0) == 0:
            return {"valid": False, "reason": "Units with OC 0 cannot perform Actions"}
        # Not if within engagement range of any enemy (unless TITANIC CHARACTER)
        if any(self.map.is_within_engagement_range(unit, enemy)
               for enemy in self.map.get_enemy_units(unit) if enemy.is_alive()):
            if not (getattr(unit, 'is_titanic', False) and getattr(unit, 'is_character', False)):
                return {"valid": False, "reason": "Units in Engagement Range cannot perform Actions"}
        # Not if advanced or fell back (Templar Vows: Uphold allows INFANTRY to start Actions after advancing).
        if unit.round_state.fell_back_this_round:
            return {"valid": False, "reason": "Units that Fell Back cannot perform Actions"}
        if unit.round_state.advanced_this_round:
            allow_advance_action = False
            try:
                army = unit.get_parent_army()
                mgr = getattr(army, "templar_vows", None) if army is not None else None
                if mgr is not None and mgr.allow_action_after_advance(unit, self):
                    allow_advance_action = True
            except Exception:
                allow_advance_action = False
            if not allow_advance_action:
                return {"valid": False, "reason": "Units that Advanced cannot perform Actions"}
        # Not if not eligible to shoot this phase (includes units that have already been selected to shoot)
        if unit.round_state.shot_this_round:
            return {"valid": False, "reason": "Units already selected to shoot cannot start an Action this phase"}
        return {"valid": True, "reason": "Eligible"}

    def _unit_is_in_player_deployment(self, player: Player, unit: 'Unit') -> bool:
        try:
            zones = self.deployment_zones.get(player.name, {})
            zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
            if not zone:
                return False
            # Use first alive model position
            for model in unit.models:
                if model.is_alive:
                    pos = model.get_location()
                    if pos and hasattr(zone, 'contains_point') and zone.contains_point(pos[0], pos[1]):
                        return True
            return False
        except Exception:
            return False

    def _objective_in_player_deployment(self, player: Player, objective_point) -> bool:
        try:
            zones = self.deployment_zones.get(player.name, {})
            zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
            if not zone:
                return False
            return hasattr(zone, 'contains_point') and zone.contains_point(objective_point.x, objective_point.y)
        except Exception:
            return False

    def _unit_within_any_terrain_feature(self, unit: 'Unit') -> bool:
        try:
            for model in unit.models:
                if not model.is_alive:
                    continue
                base_geom = model.model_base.get_base_shape()
                for t in self.map.terrain_features:
                    if base_geom.intersects(t.footprint):
                        return True
            return False
        except Exception:
            return False

    def _unit_within_range_of_objective(self, unit: 'Unit') -> Optional[Objective]:
        # Return the Objective (from map.objectives) whose point area intersects the unit
        from shapely.geometry import Point as _ShPoint
        for obj in getattr(self.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc:
                continue
            area = _ShPoint(loc.x, loc.y).buffer(loc.control_radius)
            for model in unit.models:
                if not model.is_alive:
                    continue
                try:
                    base = model.model_base.get_base_shape()
                    if base.intersects(area):
                        return obj
                except Exception:
                    # Fallback distance check
                    mpos = model.get_location()
                    if mpos:
                        dx = mpos[0] - loc.x
                        dy = mpos[1] - loc.y
                        if (dx*dx + dy*dy) ** 0.5 <= (loc.control_radius + getattr(model.model_base, 'get_radius', lambda: 1.0)()):
                            return obj
        return None

    # ---------- Primary Mission helpers (Burden of Trust guarding) ----------

    def _clear_expired_guards_for_player(self, player: Player) -> None:
        """Clear any 'guarding' assignments for `player` at the start of their turn."""
        army = getattr(player, "army", None)
        if army is None:
            return
        for u in list(getattr(army, "units", []) or []):
            if getattr(u, "guarding_objective", None) is not None:
                u.guarding_objective = None

    def _assign_burden_of_trust_guards(self, player: Player) -> None:
        """
        End of Command phase (Burden of Trust): for each objective marker the player controls,
        select one eligible unit within range to guard it until the start of the player's next turn.

        Current implementation is deterministic/autopick (UI hooks can override later).
        """
        if getattr(self, "get_battle_round", lambda: 0)() < 2:
            return

        prim = getattr(player, "primary_mission", None)
        try:
            from .mission_cards import BurdenOfTrustPrimary
            if not isinstance(prim, BurdenOfTrustPrimary):
                return
        except Exception:
            return

        # Build list of objectives currently controlled by player.
        controlled = []
        for obj in getattr(self.map, "objectives", []):
            loc = getattr(obj, "location", None)
            if not loc or getattr(loc, "removed", False):
                continue
            if hasattr(loc, "update_control"):
                loc.update_control(self)
            if getattr(loc, "controlling_player", None) is player:
                controlled.append(obj)

        # Candidate units: non-aircraft, alive, deployed.
        candidates = []
        for u in getattr(player.army, "units", []) or []:
            if not u.is_alive() or not getattr(u, "deployed", False):
                continue
            if getattr(u, "is_aircraft", False):
                continue
            candidates.append(u)

        # Assign at most one objective per unit.
        used_units = set()
        for obj in controlled:
            # Find first eligible unit within range of this objective.
            chosen = None
            for u in candidates:
                if id(u) in used_units:
                    continue
                if self._unit_within_range_of_objective(u) is obj:
                    chosen = u
                    break
            if chosen is None:
                continue
            chosen.guarding_objective = obj
            used_units.add(id(chosen))

    def _apply_primary_mission_setup_rules(self) -> None:
        """
        Apply mission-card setup rules that modify objectives at battle start.
        This is invoked after mission objectives are initially placed.
        """
        if not getattr(self, "players", None):
            return
        prim = getattr(self.players[0], "primary_mission", None)
        if prim is None:
            return

        # Helper: objective is in No Man's Land if it is not within any player's deployment zone.
        def _is_nml(loc) -> bool:
            for p in self.players:
                zones = self.deployment_zones.get(p.name, {})
                zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
                if zone and hasattr(zone, "contains_point") and zone.contains_point(loc.x, loc.y):
                    return False
            return True

        # Unexploded Ordnance: NML objectives become Hazard objectives.
        try:
            from .mission_cards import UnexplodedOrdnancePrimary
            if isinstance(prim, UnexplodedOrdnancePrimary):
                for obj in getattr(self.map, "objectives", []) or []:
                    loc = getattr(obj, "location", None)
                    if not loc or getattr(loc, "removed", False):
                        continue
                    if _is_nml(loc):
                        loc.is_hazard = True
        except Exception:
            pass

        # Supply Drop: initialize Alpha/Omega selection if primary supports it.
        try:
            fn = getattr(prim, "initialize_alpha_omega", None)
            if callable(fn):
                fn(self)
        except Exception:
            pass

    def can_start_terraform(self, unit: 'Unit') -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Terraform starts in your Shooting phase"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        # Must be within range of an objective not within your deployment zone
        obj = self._unit_within_range_of_objective(unit)
        if not obj:
            return {"valid": False, "reason": "Unit not within range of an objective"}
        # Objective must not be within your deployment zone
        if self._objective_in_player_deployment(unit.get_parent_army().player, obj.location):
            return {"valid": False, "reason": "Objective is within your deployment zone"}
        return {"valid": True, "reason": "Eligible", "objective": obj}

    def can_start_sabotage(self, unit: 'Unit') -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Sabotage starts in your Shooting phase"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        # Must be within a terrain feature and not within your deployment zone
        if not self._unit_within_any_terrain_feature(unit):
            return {"valid": False, "reason": "Unit must be within a terrain feature"}
        if self._unit_is_in_player_deployment(unit.get_parent_army().player, unit):
            return {"valid": False, "reason": "Unit is within your deployment zone"}
        return {"valid": True, "reason": "Eligible"}

    def can_start_cleanse(self, unit: 'Unit') -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Cleanse starts in your Shooting phase"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        # Must be within range of an objective not within your deployment zone
        obj = self._unit_within_range_of_objective(unit)
        if not obj:
            return {"valid": False, "reason": "Unit not within range of an objective"}
        if self._objective_in_player_deployment(unit.get_parent_army().player, obj.location):
            return {"valid": False, "reason": "Objective is within your deployment zone"}
        return {"valid": True, "reason": "Eligible", "objective": obj}

    def can_start_establish_locus(self, unit: 'Unit') -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Establish Locus starts in your Shooting phase"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        return {"valid": True, "reason": "Eligible"}

    def can_start_the_ritual(self, unit: 'Unit', *, new_objective_xy: Tuple[float, float]) -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "The Ritual starts in your Shooting phase"}
        # Must have The Ritual as the primary mission
        try:
            from .mission_cards import TheRitualPrimary
            if not isinstance(getattr(unit.get_parent_army().player, "primary_mission", None), TheRitualPrimary):
                return {"valid": False, "reason": "Primary mission is not The Ritual"}
        except Exception:
            return {"valid": False, "reason": "Primary mission is not The Ritual"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        try:
            x, y = float(new_objective_xy[0]), float(new_objective_xy[1])
        except Exception:
            return {"valid": False, "reason": "Invalid objective marker position"}

        # Must be within No Man's Land (not in either deployment zone)
        for p in self.players:
            zones = self.deployment_zones.get(p.name, {})
            zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
            if zone and hasattr(zone, "contains_point") and zone.contains_point(x, y):
                return {"valid": False, "reason": "Objective marker must be wholly within No Man's Land"}

        # Must be within 1" of the unit
        from ..utility.aura_utils import horizontal_distance_point_to_model_base_2d
        in_1 = False
        for m in getattr(unit, "models", []) or []:
            if not getattr(m, "is_alive", True):
                continue
            if horizontal_distance_point_to_model_base_2d(m, x, y) <= 1.0 + 1e-6:
                in_1 = True
                break
        if not in_1:
            return {"valid": False, "reason": "Objective marker must be within 1\" of the unit"}

        # Exactly 12" from one other NML objective, and not within 6" of any other objective.
        nml_objs = []
        for obj in getattr(self.map, "objectives", []) or []:
            loc = getattr(obj, "location", None)
            if not loc or getattr(loc, "removed", False):
                continue
            # Only consider NML markers
            in_any_dz = False
            for p in self.players:
                zones = self.deployment_zones.get(p.name, {})
                zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
                if zone and hasattr(zone, "contains_point") and zone.contains_point(loc.x, loc.y):
                    in_any_dz = True
                    break
            if not in_any_dz:
                nml_objs.append(obj)

        def _dist(a, b):
            dx = float(a[0]) - float(b[0])
            dy = float(a[1]) - float(b[1])
            return (dx * dx + dy * dy) ** 0.5

        dists = [(_dist((x, y), (float(o.location.x), float(o.location.y))), o) for o in nml_objs if getattr(o, "location", None)]
        exact_12 = [o for (d, o) in dists if abs(d - 12.0) <= 0.25]
        if len(exact_12) != 1:
            return {"valid": False, "reason": "Objective marker must be set up exactly 12\" from one other No Man's Land objective marker"}
        for (d, o) in dists:
            if o is exact_12[0]:
                continue
            if d < 6.0 - 1e-6:
                return {"valid": False, "reason": "Objective marker must not be within 6\" of any other objective marker"}

        return {"valid": True, "reason": "Eligible", "x": x, "y": y}

    def can_start_move_hazard(self, unit: 'Unit', *, hazard_objective: Objective, new_xy: Tuple[float, float]) -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Move Hazard starts in your Shooting phase"}
        # Must have Unexploded Ordnance as the primary mission
        try:
            from .mission_cards import UnexplodedOrdnancePrimary
            if not isinstance(getattr(unit.get_parent_army().player, "primary_mission", None), UnexplodedOrdnancePrimary):
                return {"valid": False, "reason": "Primary mission is not Unexploded Ordnance"}
        except Exception:
            return {"valid": False, "reason": "Primary mission is not Unexploded Ordnance"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        actor = unit.get_parent_army().player
        if hazard_objective is None or getattr(hazard_objective, "location", None) is None:
            return {"valid": False, "reason": "Invalid hazard objective marker"}
        loc = hazard_objective.location
        if not bool(getattr(loc, "is_hazard", False)):
            return {"valid": False, "reason": "Objective marker is not a Hazard objective marker"}
        if hasattr(loc, "update_control"):
            loc.update_control(self)
        if getattr(loc, "controlling_player", None) is not actor:
            return {"valid": False, "reason": "You do not control that Hazard objective marker"}
        # Must be within range of this hazard marker
        if self._unit_within_range_of_objective(unit) is not hazard_objective:
            return {"valid": False, "reason": "Unit must be within range of that Hazard objective marker"}
        try:
            nx, ny = float(new_xy[0]), float(new_xy[1])
        except Exception:
            return {"valid": False, "reason": "Invalid destination"}
        dx = nx - float(loc.x)
        dy = ny - float(loc.y)
        if (dx * dx + dy * dy) ** 0.5 > 6.0 + 1e-6:
            return {"valid": False, "reason": "Hazard objective marker can only be moved up to 6\""}
        return {"valid": True, "reason": "Eligible", "hazard_objective": hazard_objective, "new_x": nx, "new_y": ny}

    def start_terraform_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_terraform(unit)
        if not check["valid"]:
            return check
        objective = check.get("objective")
        # Mark unit round state and add in-progress
        unit.round_state.performing_action_name = 'TERRAFORM'
        unit.round_state.action_locked_until_turn_end = True
        # Consumes the unit's shooting action for the turn
        unit.round_state.shot_this_round = True
        # Complete at end of this player's turn
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'TERRAFORM',
            'started_turn': self.turn,
            'completes_on_player_index': self.current_player_index,
            'metadata': {'objective': objective}
        })
        return {"valid": True, "reason": "Terraform started"}

    def start_sabotage_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_sabotage(unit)
        if not check["valid"]:
            return check
        unit.round_state.performing_action_name = 'SABOTAGE'
        unit.round_state.action_locked_until_turn_end = True
        # Consumes the unit's shooting action for the turn
        unit.round_state.shot_this_round = True
        # Completes at end of opponent's next turn
        opponent_index = (self.current_player_index + 1) % len(self.players)
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'SABOTAGE',
            'started_turn': self.turn,
            'completes_on_player_index': opponent_index,
            'metadata': {}
        })
        return {"valid": True, "reason": "Sabotage started"}

    def start_cleanse_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_cleanse(unit)
        if not check["valid"]:
            return check
        objective = check.get("objective")
        unit.round_state.performing_action_name = 'CLEANSE'
        unit.round_state.action_locked_until_turn_end = True
        unit.round_state.shot_this_round = True
        # Completes at end of this player's turn
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'CLEANSE',
            'started_turn': self.turn,
            'completes_on_player_index': self.current_player_index,
            'metadata': {'objective': objective}
        })
        return {"valid": True, "reason": "Cleanse started"}

    def start_establish_locus_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_establish_locus(unit)
        if not check["valid"]:
            return check
        unit.round_state.performing_action_name = 'ESTABLISH_LOCUS'
        unit.round_state.action_locked_until_turn_end = True
        unit.round_state.shot_this_round = True
        # Completes at end of this player's turn
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'ESTABLISH_LOCUS',
            'started_turn': self.turn,
            'completes_on_player_index': self.current_player_index,
            'metadata': {}
        })
        return {"valid": True, "reason": "Establish Locus started"}

    def start_the_ritual_action(self, unit: 'Unit', *, new_objective_xy: Tuple[float, float]) -> Dict[str, Any]:
        check = self.can_start_the_ritual(unit, new_objective_xy=new_objective_xy)
        if not check["valid"]:
            return check
        unit.round_state.performing_action_name = 'THE_RITUAL'
        unit.round_state.action_locked_until_turn_end = True
        unit.round_state.shot_this_round = True
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'THE_RITUAL',
            'started_turn': self.turn,
            'completes_on_player_index': self.current_player_index,
            'metadata': {'x': check["x"], 'y': check["y"]}
        })
        return {"valid": True, "reason": "The Ritual started"}

    def start_move_hazard_action(self, unit: 'Unit', *, hazard_objective: Objective, new_xy: Tuple[float, float]) -> Dict[str, Any]:
        check = self.can_start_move_hazard(unit, hazard_objective=hazard_objective, new_xy=new_xy)
        if not check["valid"]:
            return check
        unit.round_state.performing_action_name = 'MOVE_HAZARD'
        unit.round_state.action_locked_until_turn_end = True
        unit.round_state.shot_this_round = True
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'MOVE_HAZARD',
            'started_turn': self.turn,
            'completes_on_player_index': self.current_player_index,
            'metadata': {'hazard_objective': check["hazard_objective"], 'new_x': check["new_x"], 'new_y': check["new_y"]}
        })
        return {"valid": True, "reason": "Move Hazard started"}

    # Scorched Earth: Burn Objective (BR2+)
    def can_start_burn_objective(self, unit: 'Unit') -> Dict[str, Any]:
        # Only available if player's primary is Scorched Earth
        prim = getattr(unit.get_parent_army().player, 'primary_mission', None)
        from .mission_cards import ScorchedEarthPrimary
        if not isinstance(prim, ScorchedEarthPrimary):
            return {"valid": False, "reason": "Primary mission is not Scorched Earth"}
        if self.get_battle_round() < 2:
            return {"valid": False, "reason": "Burn Objective starts from the second battle round"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        obj = self._unit_within_range_of_objective(unit)
        if not obj:
            return {"valid": False, "reason": "Unit not within range of an objective"}
        # Not within your deployment zone
        if self._objective_in_player_deployment(unit.get_parent_army().player, obj.location):
            return {"valid": False, "reason": "Objective is within your deployment zone"}
        return {"valid": True, "reason": "Eligible", "objective": obj}

    def start_burn_objective_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_burn_objective(unit)
        if not check["valid"]:
            return check
        objective = check.get("objective")
        unit.round_state.performing_action_name = 'BURN_OBJECTIVE'
        unit.round_state.action_locked_until_turn_end = True
        # Consumes the unit's shooting action for the turn
        unit.round_state.shot_this_round = True
        opponent_index = (self.current_player_index + 1) % len(self.players)
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'BURN_OBJECTIVE',
            'started_turn': self.turn,
            'completes_on_player_index': opponent_index,
            'metadata': {'objective': objective}
        })
        return {"valid": True, "reason": "Burn Objective started"}

    def _complete_actions_for_turn_end(self, turn_ending_player: Player) -> None:
        # Evaluate any in-progress actions that complete at this player's turn end
        remaining = []
        for entry in self.in_progress_actions:
            completes_on = entry.get('completes_on_player_index')
            if completes_on != self.current_player_index:
                remaining.append(entry)
                continue
            unit = entry.get('unit')
            action_name = entry.get('action_name')
            actor = entry.get('player')
            # Validate unit still on battlefield
            if not unit or not unit.is_alive() or not unit.deployed:
                # Action fails silently
                if unit:
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                continue
            try:
                if action_name == 'TERRAFORM':
                    # Must still be within range of same objective and control it
                    objective = entry['metadata'].get('objective')
                    loc = getattr(objective, 'location', None)
                    if loc and hasattr(loc, 'update_control'):
                        loc.update_control(self)
                    # Check in-range
                    in_range = False
                    if objective:
                        in_range = (self._unit_within_range_of_objective(unit) == objective)
                    controls = loc and getattr(loc, 'controlling_player', None) is actor
                    if in_range and controls:
                        # Mark terraformed and record completed action
                        if loc:
                            loc.terraformed_by = actor
                        self.completed_actions_this_turn.append({
                            'player': actor,
                            'action_name': 'TERRAFORM',
                            'unit_location': unit.get_closest_model_position_to_target((loc.x, loc.y, loc.z)) if loc else None
                        })
                    # Clear unit state
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                elif action_name == 'SABOTAGE':
                    # Completes if the unit is on the battlefield
                    self.completed_actions_this_turn.append({
                        'player': actor,
                        'action_name': 'SABOTAGE',
                        'unit_location': unit.get_closest_model_position_to_target(unit.models[0].get_location() if unit.models else (0, 0, 0))
                    })
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                elif action_name == 'CLEANSE':
                    objective = entry['metadata'].get('objective')
                    loc = getattr(objective, 'location', None)
                    if loc and hasattr(loc, 'update_control'):
                        loc.update_control(self)
                    in_range = False
                    if objective:
                        in_range = (self._unit_within_range_of_objective(unit) == objective)
                    controls = loc and getattr(loc, 'controlling_player', None) is actor
                    if in_range and controls:
                        # Mark cleansed and record completed action
                        if loc:
                            setattr(loc, "cleansed_by", actor)
                        self.completed_actions_this_turn.append({
                            'player': actor,
                            'action_name': 'CLEANSE',
                            'objective': objective,
                            'unit_location': unit.get_closest_model_position_to_target((loc.x, loc.y, loc.z)) if loc else None
                        })
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                elif action_name == 'ESTABLISH_LOCUS':
                    # Completes if unit is within opponent DZ or within 6" of center
                    completes = False
                    try:
                        opp = [p for p in self.players if p is not actor][0]
                        zones = self.deployment_zones.get(opp.name, {})
                        zone = zones.get('zone') or zones.get('Attacker Zone') or zones.get('Defender Zone')
                        pos = unit.models[0].get_location() if unit.models else (0, 0, 0)
                        if zone and hasattr(zone, 'contains_point') and zone.contains_point(pos[0], pos[1]):
                            completes = True
                        else:
                            midx = float(self.map.width) / 2.0
                            midy = float(self.map.height) / 2.0
                            dx = float(pos[0]) - midx
                            dy = float(pos[1]) - midy
                            completes = (dx * dx + dy * dy) ** 0.5 <= 6.0 + 1e-6
                    except Exception:
                        completes = False
                    if completes:
                        self.completed_actions_this_turn.append({
                            'player': actor,
                            'action_name': 'ESTABLISH_LOCUS',
                            'unit_location': unit.models[0].get_location() if unit.models else (0, 0, 0),
                        })
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                elif action_name == 'THE_RITUAL':
                    # Place a new objective marker if still valid (best-effort: uses pre-validated coordinates).
                    x = entry['metadata'].get('x')
                    y = entry['metadata'].get('y')
                    try:
                        from .map import Objective, ObjectiveCategory, ObjectivePoint
                        op = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
                        obj = Objective(
                            name="Ritual Objective",
                            category=ObjectiveCategory.PRIMARY,
                            points=0,
                            description="Objective marker created by The Ritual.",
                            conditions=lambda g: False,
                            location=op,
                        )
                        self.map.add_objective(obj)
                    except Exception:
                        pass
                    self.completed_actions_this_turn.append({
                        'player': actor,
                        'action_name': 'THE_RITUAL',
                        'unit_location': unit.models[0].get_location() if unit.models else (0, 0, 0),
                    })
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                elif action_name == 'MOVE_HAZARD':
                    hazard_obj = entry['metadata'].get('hazard_objective')
                    nx = entry['metadata'].get('new_x')
                    ny = entry['metadata'].get('new_y')
                    try:
                        loc = getattr(hazard_obj, 'location', None)
                        if loc and hasattr(loc, 'update_control'):
                            loc.update_control(self)
                        # Still within range and controlled
                        in_range = (self._unit_within_range_of_objective(unit) == hazard_obj)
                        controls = loc and getattr(loc, 'controlling_player', None) is actor
                        if in_range and controls and loc and not getattr(loc, 'removed', False):
                            loc.x = float(nx)
                            loc.y = float(ny)
                            self.completed_actions_this_turn.append({
                                'player': actor,
                                'action_name': 'MOVE_HAZARD',
                                'objective': hazard_obj,
                                'unit_location': unit.models[0].get_location() if unit.models else (0, 0, 0),
                            })
                    except Exception:
                        pass
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                elif action_name == 'BURN_OBJECTIVE':
                    objective = entry['metadata'].get('objective')
                    loc = getattr(objective, 'location', None)
                    if loc and hasattr(loc, 'update_control'):
                        loc.update_control(self)
                    in_range = False
                    if objective:
                        in_range = (self._unit_within_range_of_objective(unit) == objective)
                    controls = loc and getattr(loc, 'controlling_player', None) is actor
                    if in_range and controls and not getattr(loc, 'removed', False):
                        # Determine zone of objective for VP
                        in_opponent_dz = False
                        try:
                            opponent = [p for p in self.players if p is not actor][0]
                            zones = self.deployment_zones.get(opponent.name, {})
                            zone = zones.get('zone') or zones.get('Attacker Zone') or zones.get('Defender Zone')
                            if zone and hasattr(zone, 'contains_point'):
                                in_opponent_dz = zone.contains_point(loc.x, loc.y)
                        except Exception:
                            in_opponent_dz = False
                        vp = 10 if in_opponent_dz else 5
                        # Remove the objective
                        loc.removed = True
                        print("🔥 Scorched Earth burned objective at ({:.1f}, {:.1f})".format(loc.x, loc.y))
                        # Immediate scoring per mission rules (Any time when burned)
                        details = [
                            f"Burned objective at ({loc.x:.1f}, {loc.y:.1f})",
                        ]
                        if in_opponent_dz:
                            details.append("Objective in opponent deployment zone")
                        added = self.award_vp(
                            actor,
                            vp,
                            source="primary",
                            card=getattr(actor, "primary_mission", None),
                            details=details,
                            timing="Action: Burn objective",
                        )
                        if added:
                            print(f"🎯 {actor.name} scored {added} VP for burning objective")
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                else:
                    remaining.append(entry)
            except Exception:
                # On error, keep the action to avoid data loss
                remaining.append(entry)
        self.in_progress_actions = remaining

    def is_game_over(self) -> bool:
        if self.turn > TOTAL_ROUNDS:
            return True
        return False

    def get_winner(self) -> Player | None:
        # Return the winning player or None if the game is not over
        if self.is_game_over():
            self.finalize_battle_scoring()
            if not self.players:
                return None
            max_vp = max((p.get_score() for p in self.players), default=0)
            winners = [p for p in self.players if p.get_score() == max_vp]
            if len(winners) != 1:
                return None  # Draw
            return winners[0]
        return None

    def get_loser(self) -> Player | None:
        if self.is_game_over():
            self.finalize_battle_scoring()
            if not self.players:
                return None
            min_vp = min((p.get_score() for p in self.players), default=0)
            losers = [p for p in self.players if p.get_score() == min_vp]
            if len(losers) != 1:
                return None  # Draw
            return losers[0]
        return None

    def get_state(self) -> Dict[str, Any]:
        # Return the current game state as a dictionary
        # TODO - might be overcome by the implementation of "extract_state_features()" in hrl_agent.py
        return {
            "players": self.players,
            "battlefield": self.battlefield,
            "map": self.map,
            "current_player": self.get_current_player(),
            "turn": self.turn,
            "phase": self.phase,
        }

    def declare_charge(self, charging_unit: 'Unit', target_unit: 'Unit', *, out_of_turn: bool = False) -> dict | None:
        """
        Single source of truth for charge declaration bookkeeping + rolling:

        - Validates eligibility (`Unit.can_declare_charge_against`)
        - Marks `attempted_charge_this_round` immediately (a declared charge is an attempt)
        - Rolls 2D6 (with detailed dice)
        - Offers a rule-based re-roll prompt (e.g. "re-roll Charge rolls") via map.roll_reroll_provider (UI hook)
        - Publishes `roll_made` for stratagem/telemetry consumers

        out_of_turn: allow declaring a charge outside the active player's turn (no attempted_charge_this_round mark).

        Returns a dict:
          { "base_roll": int, "dice": list[int], "reroll_used": bool }
        or None if the charge cannot be declared.
        """
        if not charging_unit.can_declare_charge_against(target_unit, self, out_of_turn=out_of_turn):
            return None

        try:
            self.event_system.publish("charge_declared", unit=charging_unit, target_unit=target_unit)
        except Exception:
            pass

        try:
            army = charging_unit.get_parent_army()
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            if mgr is not None:
                mgr.maybe_trigger_charge_maneuver(charging_unit, target_unit, self)
        except Exception:
            pass

        try:
            self._record_engaged_enemies_at_turn_start(self.get_current_player())
        except Exception:
            pass

        # Mark as attempted immediately (prevents multiple declarations).
        try:
            if not out_of_turn:
                charging_unit.round_state.attempted_charge_this_round = True
        except Exception:
            pass

        dice_collection = DiceCollection.from_string("2D6")
        base_roll = None
        dice = None
        miracle_used = False
        try:
            army = charging_unit.get_parent_army()
            mgr = getattr(army, "acts_of_faith", None) if army is not None else None
            if mgr is not None and mgr.can_use_act_of_faith(charging_unit, game=self):
                base_roll, dice, miracle_used = mgr.resolve_roll(
                    charging_unit,
                    roll_type="charge",
                    game=self,
                    dice_count=2,
                    die_faces=6,
                )
        except Exception:
            base_roll = None
            dice = None
            miracle_used = False
        if base_roll is None or dice is None:
            base_roll, dice = dice_collection.roll_detailed()

        player = None
        try:
            player = charging_unit.get_parent_army().player
        except Exception:
            player = None

        # Optional rule-based reroll (e.g. "No Prey Can Evade").
        reroll_used = False
        can_rule_reroll = False
        try:
            can_rule_reroll = bool(charging_unit.can_reroll_charge_roll(target_unit=target_unit, game_map=self.map, game=self))
        except Exception:
            can_rule_reroll = False
        try:
            army = charging_unit.get_parent_army()
            mgr = getattr(army, "templar_vows", None) if army is not None else None
            if mgr is not None and mgr.can_reroll_charge_against(charging_unit, target_unit):
                can_rule_reroll = True
        except Exception:
            pass

        # Always prompt humans via provider if available; provider will disable the reroll button if not allowed.
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
            provider = getattr(getattr(self, "map", None), "roll_reroll_provider", None)
            if is_human and callable(provider):
                want = bool(provider(
                    player=player,
                    unit=charging_unit,
                    roll_type="charge",
                    value=base_roll,
                    dice=list(dice),
                    allow_reroll=bool(can_rule_reroll),
                ))
                if want and can_rule_reroll:
                    base_roll, dice = dice_collection.roll_detailed()
                    reroll_used = True
        except Exception:
            pass

        # Store roll for UI/telemetry
        try:
            charging_unit.round_state.charge_roll = int(base_roll or 0)
        except Exception:
            pass

        # Publish roll event (best-effort); reroll_locked means "already rerolled".
        try:
            def _reroll():
                new_total, new_dice = DiceCollection.from_string("2D6").roll_detailed()
                # If a consumer uses this (e.g. Command Re-roll), keep unit state consistent.
                try:
                    charging_unit.round_state.charge_roll = int(new_total or 0)
                except Exception:
                    pass
                return new_total, new_dice

            from ..utility.reroll_tracker import prepare_reroll_event
            roll_id, reroll_cb, reroll_locked = prepare_reroll_event(
                self,
                _reroll,
                reroll_used=bool(reroll_used),
                used_result=(int(base_roll or 0), list(dice)),
            )
            self.event_system.publish(
                "roll_made",
                player=player,
                unit=charging_unit,
                roll_type="charge",
                value=int(base_roll or 0),
                dice=list(dice),
                reroll=reroll_cb,
                reroll_locked=bool(reroll_locked),
                roll_id=roll_id,
                miracle_used=bool(miracle_used),
            )
        except Exception:
            pass

        # Dice log (best-effort)
        try:
            from ..utility.event_bus import append_dice
            if player is not None:
                if miracle_used:
                    append_dice(player.name, f"Miracle die used for Charge roll: {int(base_roll or 0)} (dice {list(dice)}) for {charging_unit.name}")
                else:
                    append_dice(player.name, f"Charge roll: {int(base_roll or 0)} (dice {list(dice)}) for {charging_unit.name}")
        except Exception:
            pass
        return {
            "base_roll": int(base_roll or 0),
            "dice": list(dice),
            "reroll_used": bool(reroll_used),
            "miracle_used": bool(miracle_used),
        }

    def roll_blood_surge_distance(self, unit: 'Unit') -> int:
        """Roll Blood Surge distance (D6+2), optionally applying leader-provided rerolls."""
        if unit is None:
            return 0
        try:
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict):
                fixed = sr.get("blood_surge_fixed_distance", None)
                fixed_key = sr.get("blood_surge_fixed_distance_phase_key", None)
                if fixed is not None:
                    expected_key = unit._blood_surge_phase_key(self)
                    if str(fixed_key or "") == str(expected_key or ""):
                        sr.pop("blood_surge_fixed_distance", None)
                        sr.pop("blood_surge_fixed_distance_phase_key", None)
                        unit.special_rules = sr
                        try:
                            from ..utility.event_bus import append_dice
                            player = getattr(unit.get_parent_army(), "player", None)
                            if player is not None:
                                append_dice(player.name, f"Blood Surge fixed distance: {int(fixed)}\" for {unit.name}")
                        except Exception:
                            pass
                        return int(fixed)
                    sr.pop("blood_surge_fixed_distance", None)
                    sr.pop("blood_surge_fixed_distance_phase_key", None)
                    unit.special_rules = sr
        except Exception:
            pass
        try:
            from ..utility.dice import get_roll
        except Exception:
            def get_roll(_s):
                return 1

        base_roll = get_roll("D6")
        reroll_used = False

        player = None
        try:
            player = unit.get_parent_army().player
        except Exception:
            player = None

        can_reroll = False
        try:
            can_reroll = bool(unit.can_reroll_blood_surge_roll())
        except Exception:
            can_reroll = False

        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False

        if is_human:
            try:
                provider = getattr(getattr(self, "map", None), "roll_reroll_provider", None)
                if callable(provider):
                    want = bool(provider(
                        player=player,
                        unit=unit,
                        roll_type="blood_surge",
                        value=int(base_roll or 0),
                        dice=[int(base_roll or 0)],
                        allow_reroll=bool(can_reroll),
                    ))
                    if want and can_reroll:
                        base_roll = get_roll("D6")
                        reroll_used = True
            except Exception:
                pass
        elif can_reroll:
            try:
                import random
                if random.choice([True, False]):
                    base_roll = get_roll("D6")
                    reroll_used = True
            except Exception:
                pass

        max_distance = int(base_roll or 0) + 2

        try:
            from ..utility.event_bus import append_dice
            if player is not None:
                tag = "Blood Surge reroll" if reroll_used else "Blood Surge roll"
                append_dice(player.name, f"{tag}: {int(base_roll or 0)} (move {max_distance}\") for {unit.name}")
        except Exception:
            pass

        return int(max_distance)

    def attempt_charge(
        self,
        charging_unit: 'Unit',
        target_unit: 'Unit',
        *,
        out_of_turn: bool = False,
        count_as_charged: bool = True,
    ) -> bool:
        """Attempt a charge move with the given unit against the target.
        
        According to 10th edition rules, a successful charge requires at least one model
        of the charging unit to end their charge with edge-to-edge distance of 1" or less
        from at least one model in the target unit.
        
        CRITICAL: If the charge roll is insufficient to reach within 1" of the enemy,
        the charge fails completely and NO MODELS MOVE AT ALL.
        out_of_turn: allow charges outside the active player's turn.
        count_as_charged: if False, do not apply the charge bonus (e.g., Heroic Intervention).
        """
        declared = self.declare_charge(charging_unit, target_unit, out_of_turn=out_of_turn)
        if not declared:
            return False

        # Calculate current edge-to-edge distance between units
        current_distance = self.map.get_distance_between_units(charging_unit, target_unit)
        
        # For a successful charge, we need to achieve edge-to-edge distance of 1" or less
        # So we need to move: current_distance - 1.0 inches
        distance_needed = max(0, current_distance - 1.0)

        base_charge_roll = int(declared.get("base_roll", 0) or 0)
        individual_dice = list(declared.get("dice", []) or [])
        charge_roll = self._apply_charge_modifiers(charging_unit, base_charge_roll)
        
        print(f"⚔️ {charging_unit.name} charging {target_unit.name}")
        print(f"⚔️ Current edge-to-edge distance: {current_distance:.1f}\"")
        print(f"⚔️ Distance needed to achieve ≤1\" edge-to-edge: {distance_needed:.1f}\"")
        print(f"⚔️ Charge roll: {base_charge_roll} (rolled {individual_dice}) (modified: {charge_roll})")
        
        # CRITICAL RULE: If charge roll is insufficient, charge fails and no models move
        if charge_roll < distance_needed:
            print(f"❌ Charge failed: roll {charge_roll}\" insufficient to reach within 1\" (needed {distance_needed:.1f}\")")
            print(f"❌ No models move - charge failed completely")
            return False

        # Charge roll is sufficient - now attempt the movement
        # Find the closest models between the two units for accurate distance calculation
        charging_pos = None
        target_pos = None
        closest_distance = float('inf')

        for charging_model in charging_unit.models:
            if not charging_model.is_alive:
                continue
            for target_model in target_unit.models:
                if not target_model.is_alive:
                    continue

                from ..utility.aura_utils import distance_between_models_bases_3d
                distance = float(distance_between_models_bases_3d(charging_model, target_model))

                if distance < closest_distance:
                    closest_distance = distance
                    c_pos = charging_model.get_location()
                    t_pos = target_model.get_location()
                    charging_pos = c_pos
                    target_pos = t_pos

        if not charging_pos or not target_pos:
            print(f"❌ Charge failed: invalid positions")
            return False

        # CRITICAL: Store original model positions BEFORE attempting movement
        # This allows proper rollback if charge fails to achieve engagement range
        original_model_positions = []
        for model in charging_unit.models:
            original_model_positions.append(model.get_location())
        
        # Calculate direction vector from charging unit to target
        dx = target_pos[0] - charging_pos[0]
        dy = target_pos[1] - charging_pos[1]
        
        # Normalize the direction vector
        distance_to_target = (dx**2 + dy**2)**0.5
        if distance_to_target == 0:
            print(f"❌ Charge failed: units are at same position")
            return False
        
        dx /= distance_to_target
        dy /= distance_to_target
        
        # Move the charging unit towards the target up to the charge roll distance
        # Move as close as possible within the charge roll distance for better pile-in positioning
        movement_distance = min(charge_roll, current_distance - 0.1)  # Get as close as possible without overlapping
        new_x = charging_pos[0] + dx * movement_distance
        new_y = charging_pos[1] + dy * movement_distance
        new_z = self.map.get_height_at_point(new_x, new_y)
        
        # Attempt to move the unit with special charge movement logic
        # During charge, units should be able to move into engagement range
        success = charging_unit.charge_move((new_x, new_y, new_z), self.map, target_unit)
        if success:
            # Check if the charge actually achieved engagement range (≤1.0")
            final_distance = self.map.get_distance_between_units(charging_unit, target_unit)
            
            if final_distance <= 1.0:
                if count_as_charged:
                    charging_unit.round_state.charged_this_round = True
                try:
                    charging_unit._apply_charge_move_devastating_wounds()
                except Exception:
                    pass
                print(f"✅ Charge successful: {charging_unit.name} achieved {final_distance:.1f}\" edge-to-edge distance with {target_unit.name}")
                return True
            else:
                print(f"❌ Charge failed: {charging_unit.name} achieved {final_distance:.1f}\" edge-to-edge distance (not ≤1.0\") with {target_unit.name}")
                # CRITICAL: Revert all model positions if charge failed to achieve engagement range
                # This ensures that NO MODELS MOVE when a charge fails
                print(f"❌ Charge failed: Reverting all model positions - no models should move on failed charge")
                
                # Restore original positions
                for i, original_pos in enumerate(original_model_positions):
                    if i < len(charging_unit.models):
                        charging_unit.models[i].set_location(*original_pos)
                
                # Unit position is now derived from model positions, no need to restore
                
                return False
        else:
            print(f"❌ Charge failed: could not move unit")
            # CRITICAL: Restore original positions if charge_move failed completely
            print(f"❌ Charge failed: Reverting all model positions - no models should move on failed charge")
            
            # Restore original positions
            for i, original_pos in enumerate(original_model_positions):
                if i < len(charging_unit.models):
                    charging_unit.models[i].set_location(*original_pos)
            
            # Unit position is now derived from model positions, no need to restore
            
            return False
    
    def _apply_charge_modifiers(self, charging_unit: 'Unit', base_roll: int) -> int:
        """Apply charge roll modifiers based on unit abilities, stratagems, etc."""
        modified_roll = base_roll
        modifiers: list[tuple[int, str]] = []

        # Check for charge modifiers from abilities/enhancements
        # TODO: Implement ability-based charge modifiers
        # Examples:
        # - Shock Assault Stratagem: +1" to charge roll
        # - Swift and Deadly ability: re-roll one dice
        # - Relentless Advance trait: roll 3 dice and drop the lowest
        try:
            sr = getattr(charging_unit, "special_rules", None)
            battle_lust_bonus = int(sr.get("enhancement_battle_lust_bonus_if_unbridled", 0) or 0) if isinstance(sr, dict) else 0
            if battle_lust_bonus:
                army = charging_unit.get_parent_army()
                mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                if mgr is not None and mgr.is_blessing_active_for_unit("UNBRIDLED_BLOODLUST", charging_unit, battle_round=br):
                    modifiers.append((battle_lust_bonus, "Battle-lust (Unbridled Bloodlust)"))
        except Exception:
            pass
        try:
            sr = getattr(charging_unit, "special_rules", None)
            bonus = int(sr.get("code_chivalric_charge_bonus", 0) or 0) if isinstance(sr, dict) else 0
            if bonus:
                modifiers.append((bonus, "Code Chivalric"))
        except Exception:
            pass
        try:
            sr = getattr(charging_unit, "special_rules", None)
            if isinstance(sr, dict):
                extra = int(sr.get("charge_roll_modifier", 0) or 0)
                if extra:
                    modifiers.append((extra, "Charge roll modifier"))
                extra_list = sr.get("charge_roll_modifiers", None)
                if isinstance(extra_list, list):
                    for item in extra_list:
                        try:
                            if isinstance(item, (list, tuple)) and len(item) >= 1:
                                val = int(item[0] or 0)
                                source = str(item[1] if len(item) > 1 else "Charge roll modifier")
                            elif isinstance(item, dict):
                                val = int(item.get("value", 0) or 0)
                                source = str(item.get("source", "") or "Charge roll modifier")
                            else:
                                val = int(item or 0)
                                source = "Charge roll modifier"
                        except Exception:
                            continue
                        if val:
                            modifiers.append((val, source))
        except Exception:
            pass
        try:
            from ..utility.aura_effects import get_aura_advance_charge_roll_modifiers
            _adv_mods, aura_charge_mods = get_aura_advance_charge_roll_modifiers(charging_unit, game_map=self.map)
            for val, source in list(aura_charge_mods or []):
                if val:
                    modifiers.append((int(val), source))
        except Exception:
            pass

        try:
            modifiers = charging_unit._filter_internal_rivalries_roll_modifiers(modifiers, kind="charge")
        except Exception:
            modifiers = list(modifiers or [])
        try:
            modifiers = charging_unit._filter_driven_by_ultimate_rage_roll_modifiers(modifiers, kind="charge")
        except Exception:
            modifiers = list(modifiers or [])

        for val, source in modifiers:
            if not val:
                continue
            modified_roll += int(val)
            try:
                if val > 0:
                    print(f"⚔️ Charge bonus: +{val} ({source})")
                else:
                    print(f"⚔️ Charge penalty: {val} ({source})")
            except Exception:
                pass

        # For now, just return the modified roll
        return int(modified_roll)
    
    def get_eligible_charging_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that are eligible to declare charges."""
        eligible_units = []
        
        for unit in player.get_army().units:
            if not unit.is_alive() or not unit.deployed:
                continue
            
            # Check if unit has already attempted a charge this round
            if unit.round_state.attempted_charge_this_round:
                continue
            
            # Check if unit advanced this round (unless special abilities allow charging after advance)
            if unit.round_state.advanced_this_round and not unit.can_charge_after_advance():
                continue
            
            # Check if unit fell back this round (unless special abilities allow charging after fall back)
            if unit.round_state.fell_back_this_round and not unit.can_charge_after_fall_back():
                continue
            
            # Check if unit is already in engagement range
            enemy_units = self.get_enemy_units(player)
            is_engaged = any(self.map.is_within_engagement_range(unit, enemy) 
                           for enemy in enemy_units if enemy.is_alive())
            if is_engaged:
                continue
            
            # Check if there are any valid charge targets
            has_valid_targets = any(unit.can_declare_charge_against(target, self) 
                                  for target in enemy_units if target.is_alive())
            if has_valid_targets:
                eligible_units.append(unit)
        
        return eligible_units
    
    def is_charge_phase_complete(self, player: Player) -> bool:
        """Check if the charge phase is complete for the current player."""
        eligible_units = self.get_eligible_charging_units(player)
        return len(eligible_units) == 0

    ###########################################################################
    # Fight Phase
    ###########################################################################
    def get_eligible_fighting_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that are eligible to fight in the Fight Phase.
        
        A unit is eligible to fight if it:
        - Is alive and deployed
        - Is within engagement range of enemy units OR made a charge move this turn
        
        Args:
            player: The player whose units to check
            
        Returns:
            List of units eligible to fight
        """
        eligible_units = []
        
        for unit in player.get_army().units:
            if unit.is_eligible_to_fight(self.map):
                eligible_units.append(unit)
        
        return eligible_units
    
    def get_fight_first_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that should fight in the Fight First stage.
        
        Units fight first if they:
        - Charged this turn OR
        - Have an inherent Fight First ability
        
        Args:
            player: The player whose units to check
            
        Returns:
            List of units that should fight in the Fight First stage
        """
        fight_first_units = []
        eligible_units = self.get_eligible_fighting_units(player)
        
        for unit in eligible_units:
            if unit.should_fight_first():
                fight_first_units.append(unit)
        
        return fight_first_units
    
    def get_remaining_combatant_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that should fight in the Remaining Combatants stage.
        
        These are units that are eligible to fight but do not fight first.
        
        Args:
            player: The player whose units to check
            
        Returns:
            List of units that should fight in the Remaining Combatants stage
        """
        remaining_units = []
        eligible_units = self.get_eligible_fighting_units(player)
        
        for unit in eligible_units:
            if not unit.should_fight_first():
                remaining_units.append(unit)
        
        return remaining_units
    
    def get_fight_phase_units_by_stage(self, player: Player) -> dict:
        """Get all fighting units for a player categorized by fight stage.
        
        Args:
            player: The player whose units to categorize
            
        Returns:
            Dictionary with 'fight_first' and 'remaining_combatants' keys containing lists of units
        """
        return {
            'fight_first': self.get_fight_first_units(player),
            'remaining_combatants': self.get_remaining_combatant_units(player)
        }
    
    def is_fight_phase_complete(self, player: Player) -> bool:
        """Check if the fight phase is complete for the current player.
        
        The fight phase is complete when there are no more eligible fighting units.
        
        Args:
            player: The player to check
            
        Returns:
            True if the fight phase is complete for this player
        """
        eligible_units = self.get_eligible_fighting_units(player)
        return len(eligible_units) == 0

    ###########################################################################
    ### Reserves System
    ###########################################################################
    def get_units_in_reserves(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that are currently in reserves."""
        return [unit for unit in player.get_army().units if unit.is_in_reserves()]
    
    def get_units_that_can_arrive_from_reserves(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that can arrive from reserves this turn."""
        return [unit for unit in self.get_units_in_reserves(player) 
                if unit.can_arrive_from_reserves(self.turn)]
    
    def get_units_that_must_arrive_from_reserves(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that must arrive from reserves this turn or be destroyed."""
        return [unit for unit in self.get_units_in_reserves(player) 
                if unit.must_arrive_from_reserves(self.turn)]
    
    def destroy_units_not_arrived_from_reserves(self, player: Player) -> List['Unit']:
        """Destroy all units that did not arrive from reserves by the deadline."""
        units_to_destroy = []
        
        for unit in self.get_units_in_reserves(player):
            # NOTE: Chapter Approved: units still in reserves at the end of battle round 3 are destroyed.
            # This method is kept for backwards compatibility with older call sites, but should not be
            # the primary enforcement point anymore.
            try:
                started_in_reserves = bool(getattr(unit, "_started_in_reserves", False))
            except Exception:
                started_in_reserves = False
            if started_in_reserves and self.turn > 3:  # Legacy behavior (round 4+)
                units_to_destroy.append(unit)
                logger.warning(f"💀 {unit.name} destroyed - failed to arrive from reserves by turn 3")
        
        # Remove destroyed units from the army
        for unit in units_to_destroy:
            player.get_army().units.remove(unit)
        
        return units_to_destroy

    def _normalize_ability_text(self, text: str) -> str:
        raw = re.sub(r"<[^>]+>", " ", str(text or ""))
        raw = html.unescape(raw)
        raw = re.sub(r"\s+", " ", raw).strip().lower()
        return raw

    def _reserves_denial_ranges_for_unit(self, unit) -> list[dict]:
        ranges: list[dict] = []
        for ab in list(getattr(unit, "possible_abilities", []) or []):
            try:
                name = str(getattr(ab, "name", "") or "")
                desc = str(getattr(ab, "description", "") or "")
            except Exception:
                name = ""
                desc = ""
            text = self._normalize_ability_text(f"{name} {desc}")
            if not text:
                continue
            flat = re.sub(r"[^a-z0-9.]+", " ", text).strip()
            if "enemy" not in flat:
                continue
            has_reinforcement_terms = (
                ("reinforcement" in flat)
                or ("reserve" in flat)
                or ("deep strike" in flat)
                or ("deepstrike" in flat)
            )
            if ("cannot be set up" not in flat) and ("cannot set up" not in flat):
                continue
            horizontal_only = ("horizontally" in flat) or ("horizontal" in flat)
            distances = []
            for match in re.finditer(r"within\s+(\d+(?:\.\d+)?)\b", flat):
                try:
                    distances.append(float(match.group(1)))
                except Exception:
                    continue
            if not distances:
                continue
            ranges.append(
                {
                    "range": max(distances),
                    "horizontal_only": horizontal_only,
                }
            )
        return ranges

    def _reserves_denial_violated(self, unit, prospective: list[Tuple[float, float, float, float]]) -> bool:
        if unit is None or not prospective:
            return False
        try:
            player = unit.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return False
        enemy_units = self.get_enemy_units(player)
        if not enemy_units:
            return False

        from ..utility.aura_utils import (
            distance_between_bases_3d,
            horizontal_distance_between_bases_2d,
        )

        for enemy in enemy_units:
            try:
                if not getattr(enemy, "is_alive", lambda: True)():
                    continue
            except Exception:
                continue
            try:
                if not bool(getattr(enemy, "deployed", False)):
                    continue
                if str(getattr(enemy, "reserve_status", "deployed")) != "deployed":
                    continue
            except Exception:
                continue
            try:
                if getattr(enemy, "embarked_in", None) is not None:
                    continue
            except Exception:
                pass
            try:
                if bool(getattr(enemy, "is_embarked", False)):
                    continue
            except Exception:
                pass
            ranges = self._reserves_denial_ranges_for_unit(enemy)
            if not ranges:
                continue
            enemy_models = [m for m in list(getattr(enemy, "models", []) or []) if getattr(m, "is_alive", True)]
            if not enemy_models:
                continue
            for idx, (x, y, z, facing) in enumerate(prospective):
                if idx >= len(getattr(unit, "models", []) or []):
                    break
                base = unit._create_potential_base(x, y, z, facing, model=unit.models[idx])
                for em in enemy_models:
                    for rinfo in ranges:
                        horizontal_only = False
                        try:
                            if isinstance(rinfo, dict):
                                r = float(rinfo.get("range", 0) or 0)
                                horizontal_only = bool(rinfo.get("horizontal_only", False))
                            elif isinstance(rinfo, (list, tuple)) and rinfo:
                                r = float(rinfo[0])
                                if len(rinfo) > 1:
                                    horizontal_only = bool(rinfo[1])
                            else:
                                r = float(rinfo)
                        except Exception:
                            continue
                        if r <= 0:
                            continue
                        if horizontal_only:
                            dist = float(horizontal_distance_between_bases_2d(base, em.model_base))
                        else:
                            dist = float(distance_between_bases_3d(base, em.model_base))
                        if dist < r:
                            return True
        return False
    
    def can_place_unit_arriving_from_reserves(self, unit: 'Unit', position: Tuple[float, float, float], 
                                              battlefield_edge: str = None) -> bool:
        """Check if a unit can be legally placed when arriving from reserves.
        
        Args:
            unit: The unit arriving from reserves
            position: (x, y, z) position where the unit would be placed
            battlefield_edge: For strategic reserves, which edge they're arriving from
                             ('own', 'left', 'right', 'enemy') 
        
        Returns:
            bool: True if the placement is legal
        """
        # Check if position is within battlefield bounds
        if (position[0] < 0 or position[0] >= self.battlefield.width or
            position[1] < 0 or position[1] >= self.battlefield.height):
            return False
        
        # Strategic Reserves vs Deep Strike choice:
        # If a unit with Deep Strike arrives from Strategic Reserves, it may be set up using either:
        # - Strategic Reserves rules (edge within 6", plus turn-based allowed edges), OR
        # - Deep Strike rules (anywhere, still respecting the 9" from enemies restriction).
        # Clear any prior pending edge-touch marker for this unit (best-effort).
        try:
            if hasattr(unit, "_pending_reserves_edge_touch"):
                delattr(unit, "_pending_reserves_edge_touch")
        except Exception:
            pass

        strategic_ok = True
        strategic_used_edge_touch = False
        if unit.is_in_strategic_reserves():
            strategic_ok = False
            # Determine which edge(s) to validate
            candidate_edges = []
            if battlefield_edge:
                candidate_edges = [battlefield_edge]
            else:
                candidate_edges = ["own", "left", "right", "enemy"]

            def _model_radius(m) -> float:
                try:
                    mb = getattr(m, "model_base", None)
                    if mb is None:
                        return 1.0
                    if hasattr(mb, "get_longest_radius"):
                        return float(mb.get_longest_radius())
                    if hasattr(mb, "get_radius"):
                        return float(mb.get_radius())
                    r = getattr(mb, "radius", None)
                    if isinstance(r, (list, tuple)) and r:
                        return float(r[0])
                    return float(r) if r is not None else 1.0
                except Exception:
                    return 1.0

            def _center_dist_to_edge(x: float, y: float, edge: str) -> float:
                # Uses existing coordinate conventions: own=y0, enemy=yH, left=x0, right=xW
                if edge == "own":
                    return float(y)
                if edge == "enemy":
                    return float(self.battlefield.height - y)
                if edge == "left":
                    return float(x)
                if edge == "right":
                    return float(self.battlefield.width - x)
                return float("inf")

            # We validate against the unit's *actual* prospective formation at this position.
            snapshot = [m.get_location() for m in unit.models]
            try:
                boundary_repulsors = self.map.get_battlefield_edge_repulsors() if self.map else []
                prospective = unit.calculate_model_positions(
                    position[0],
                    position[1],
                    self.map,
                    boundary_repulsors=boundary_repulsors,
                    avoid_friendly_units=True,
                )
            finally:
                for m, loc in zip(unit.models, snapshot):
                    if loc:
                        m.set_location(*loc)

            if not prospective:
                return False

            # Round 2 Strategic Reserves restriction: cannot be set up within the enemy deployment zone
            # (applies only when using Strategic Reserves edge placement, not Deep Strike alternative).
            player_name = None
            try:
                player_name = unit.get_parent_army().player.name
            except Exception:
                player_name = None

            for edge in candidate_edges:
                if not self.is_valid_strategic_reserves_edge(edge):
                    continue

                # Turn-based enemy deployment zone restriction (turn 2 only)
                if self.turn == 2 and player_name:
                    try:
                        any_in_enemy_dz = False
                        for (mx, my, _mz, _f) in prospective:
                            if self.is_position_in_enemy_deployment_zone(float(mx), float(my), player_name):
                                any_in_enemy_dz = True
                                break
                        if any_in_enemy_dz:
                            continue
                    except Exception:
                        # If we can't check, be conservative and reject strategic placement
                        continue

                # Strategic Reserves must be set up wholly within 6" of a single battlefield edge.
                # If a model is too large to fit wholly within 6", allow the base to touch the edge instead.
                used_touch = False
                ok_all = True
                for idx, (mx, my, mz, mf) in enumerate(prospective):
                    if idx >= len(unit.models):
                        break
                    r = _model_radius(unit.models[idx])
                    d = _center_dist_to_edge(float(mx), float(my), edge)

                    # "Wholly within 6" from that edge" means (center distance) <= 6 - radius.
                    max_center = 6.0 - float(r)
                    if max_center >= 0.0:
                        if d > max_center + 1e-6:
                            ok_all = False
                            break
                    else:
                        # Too big to fit wholly within 6": require base touches the edge.
                        # For circular approximation: center distance ~= radius.
                        if abs(d - float(r)) > 0.25:  # 1/4" tolerance
                            ok_all = False
                            break
                        used_touch = True

                if ok_all:
                    strategic_ok = True
                    strategic_used_edge_touch = bool(used_touch)
                    break
        
        # Check 9" restriction from enemy models using base-to-base closest-point distance.
        # We validate against the unit's *actual* prospective formation at this position.
        snapshot = [m.get_location() for m in unit.models]
        prospective = None
        min_enemy_distance = 9.0
        try:
            boundary_repulsors = self.map.get_battlefield_edge_repulsors() if self.map else []
            prospective = unit.calculate_model_positions(
                position[0],
                position[1],
                self.map,
                boundary_repulsors=boundary_repulsors,
                avoid_friendly_units=True,
            )
            if prospective:
                # Temporarily apply prospective positions for Warp Rifts checks.
                for m, loc in zip(unit.models, prospective):
                    try:
                        m.set_location(*loc)
                    except Exception:
                        pass
                try:
                    min_enemy_distance = float(self._warp_rifts_min_distance(unit) or 9.0)
                except Exception:
                    min_enemy_distance = 9.0
        finally:
            for m, loc in zip(unit.models, snapshot):
                if loc:
                    m.set_location(*loc)

        if battlefield_edge is None:
            try:
                sr = getattr(unit, "special_rules", None)
                pain_min = float(sr.get("pain_deep_strike_min_distance", 0) or 0) if isinstance(sr, dict) else 0.0
                if pain_min:
                    min_enemy_distance = min(float(min_enemy_distance), float(pain_min))
            except Exception:
                pass

        if not prospective:
            return False

        from ..utility.aura_utils import horizontal_distance_between_bases_2d
        enemy_units = self.get_enemy_units(unit.get_parent_army().player)
        enemy_models = [em for eu in enemy_units if eu.is_alive() and eu.deployed for em in eu.models if em.is_alive]

        for idx, (x, y, z, facing) in enumerate(prospective):
            if idx >= len(unit.models):
                break
            mb = unit._create_potential_base(x, y, z, facing, model=unit.models[idx])
            for em in enemy_models:
                if float(horizontal_distance_between_bases_2d(mb, em.model_base)) < float(min_enemy_distance):
                    return False

        if self._reserves_denial_violated(unit, prospective):
            return False

        if unit.is_in_strategic_reserves():
            deep_strike_ok = bool(unit.has_deep_strike())
            ok = bool(strategic_ok or deep_strike_ok)
            # If we are validating Strategic edge placement and it required the edge-touch exception,
            # mark it on the unit so `arrive_from_reserves` can apply additional restrictions this turn.
            if ok and strategic_ok and strategic_used_edge_touch:
                try:
                    setattr(unit, "_pending_reserves_edge_touch", True)
                except Exception:
                    pass
            if ok:
                try:
                    if battlefield_edge is None:
                        pending_deep_strike = bool(deep_strike_ok)
                    else:
                        pending_deep_strike = bool(deep_strike_ok and not strategic_ok)
                    setattr(unit, "_pending_reserves_deep_strike", pending_deep_strike)
                except Exception:
                    pass
            return ok

        try:
            setattr(unit, "_pending_reserves_deep_strike", True)
        except Exception:
            pass
        return True
    
    def is_valid_strategic_reserves_edge(self, battlefield_edge: str) -> bool:
        """Check if the specified battlefield edge is valid for strategic reserves arrival.
        
        Args:
            battlefield_edge: 'own', 'left', 'right', 'enemy'
        
        Returns:
            bool: True if the edge is valid for the current turn
        """
        # Chapter Approved: Strategic Reserves can arrive from ANY battlefield edge starting in battle round 2.
        if self.turn < 2:
            return False
        return battlefield_edge in ['own', 'left', 'right', 'enemy']
    
    def get_distance_to_battlefield_edge(self, position: Tuple[float, float, float], 
                                       battlefield_edge: str) -> float:
        """Calculate distance from a position to the specified battlefield edge.
        
        Args:
            position: (x, y, z) position
            battlefield_edge: 'own', 'left', 'right', 'enemy'
        
        Returns:
            float: Distance to the edge in inches
        """
        x, y, z = position
        
        if battlefield_edge == 'own':
            # Assuming own edge is at y=0 (bottom)
            return y
        elif battlefield_edge == 'enemy':
            # Assuming enemy edge is at y=battlefield.height (top)
            return self.battlefield.height - y
        elif battlefield_edge == 'left':
            # Left edge at x=0
            return x
        elif battlefield_edge == 'right':
            # Right edge at x=battlefield.width
            return self.battlefield.width - x
        else:
            return float('inf')  # Invalid edge
    
    def handle_reserves_arrival_phase(self) -> Dict[str, List['Unit']]:
        """Handle the reserves arrival phase at the end of movement phase.
        
        This should be called at the end of each player's movement phase.
        
        Returns:
            Dict mapping player names to lists of units that arrived from reserves
        """
        arrival_results = {}
        current_player = self.get_current_player()
        
        # Handle reserves arrivals for the current player
        units_arrived = self.process_player_reserves_arrivals(current_player)
        arrival_results[current_player.name] = units_arrived

        # Cult Ambush: opponent's reinforcements step (end of this player's Movement phase)
        try:
            self._handle_cult_ambush_reinforcements(current_player)
        except Exception:
            pass

        # Chapter Approved "destroy after battle round 3" is enforced at end-of-battle-round.
        
        return arrival_results

    def _handle_cult_ambush_reinforcements(self, current_player) -> None:
        try:
            players = list(getattr(self, "players", []) or [])
        except Exception:
            players = []
        for p in players:
            if p is None or p is current_player:
                continue
            try:
                army = p.get_army()
            except Exception:
                army = None
            mgr = getattr(army, "cult_ambush", None) if army is not None else None
            if mgr is None:
                continue
            try:
                mgr.handle_reinforcements(game=self, player=p)
            except Exception:
                continue
    
    def process_player_reserves_arrivals(self, player: Player) -> List['Unit']:
        """Process reserves arrivals for a specific player.
        
        This method should be extended or overridden to integrate with AI decision making.
        
        Args:
            player: The player whose reserves arrivals to process
        
        Returns:
            List of units that arrived from reserves
        """
        units_arrived = []
        units_that_can_arrive = self.get_units_that_can_arrive_from_reserves(player)
        units_that_must_arrive = self.get_units_that_must_arrive_from_reserves(player)
        
        # For now, this is a placeholder implementation
        # In the full implementation, this should integrate with AI agents to make decisions
        logger.info(f"🪂 {player.name} has {len(units_that_can_arrive)} units that can arrive from reserves")
        
        # Force arrival of units that must arrive
        for unit in units_that_must_arrive:
            # Try to find a valid placement position
            # Simple automatic deployment - AI agents handle their own deployment decisions
            valid_position = self.find_valid_reserves_position(unit)
            if valid_position:
                if unit.arrive_from_reserves(valid_position, self.turn, self.map):
                    units_arrived.append(unit)
                    self.map.units.append(unit)  # Add to map
                else:
                    logger.error(f"❌ Failed to deploy {unit.name} from reserves despite finding valid position")
            else:
                logger.warning(f"⚠️ No valid position found for {unit.name} - unit will be destroyed")
        
        return units_arrived
    
    def find_valid_reserves_position(self, unit: 'Unit') -> Optional[Tuple[float, float, float]]:
        """Find a valid position for a unit arriving from reserves.
        
        This is a basic implementation that tries to find any valid position.
        Should be enhanced with proper AI decision making.
        
        Args:
            unit: The unit arriving from reserves
        
        Returns:
            Valid position tuple or None if no valid position found
        """
        # Try multiple positions across the battlefield
        attempts = 100
        
        for _ in range(attempts):
            if unit.is_in_strategic_reserves():
                # If the unit also has Deep Strike, it may choose to arrive using Deep Strike rules instead.
                try:
                    if unit.has_deep_strike():
                        import random
                        x = random.uniform(9.0, self.battlefield.width - 9.0)
                        y = random.uniform(9.0, self.battlefield.height - 9.0)
                        z = self.map.get_height_at_point(x, y)
                        position = (x, y, z)
                        if self.can_place_unit_arriving_from_reserves(unit, position):
                            return position
                except Exception:
                    pass

                # For strategic reserves, try positions near random edges (any edge is allowed from battle round 2+).
                import random
                edge = random.choice(["own", "enemy", "left", "right"])
                # Sample a point in the 0-6" strip from that edge (will be validated precisely per-model).
                if edge == "own":
                    y = random.uniform(0.5, 5.5)
                    x = random.uniform(1.0, self.battlefield.width - 1.0)
                elif edge == "enemy":
                    y = self.battlefield.height - random.uniform(0.5, 5.5)
                    x = random.uniform(1.0, self.battlefield.width - 1.0)
                elif edge == "left":
                    x = random.uniform(0.5, 5.5)
                    y = random.uniform(1.0, self.battlefield.height - 1.0)
                elif edge == "right":
                    x = self.battlefield.width - random.uniform(0.5, 5.5)
                    y = random.uniform(1.0, self.battlefield.height - 1.0)
                else:
                    continue
                    
                z = self.map.get_height_at_point(x, y)
                position = (x, y, z)
                
                if self.can_place_unit_arriving_from_reserves(unit, position, edge):
                    return position
            else:
                # For standard reserves (Deep Strike), can arrive anywhere more than 9" from enemies
                import random
                x = random.uniform(9.0, self.battlefield.width - 9.0)
                y = random.uniform(9.0, self.battlefield.height - 9.0)
                z = self.map.get_height_at_point(x, y)
                position = (x, y, z)
                
                if self.can_place_unit_arriving_from_reserves(unit, position):
                    return position
        
        return None  # No valid position found

    def get_first_turn_player_index(self) -> int:
        """Get the index of player who goes first (will be set during DETERMINE_FIRST_TURN_ORDER)"""
        return self.first_turn_player_index
    
    def is_in_setup_phase(self) -> bool:
        """Check if we're still in the setup phase."""
        return not self.setup_complete
    
    def get_current_setup_phase(self) -> SetupPhase:
        """Get the current setup phase."""
        return self.setup_phase
    
    def advance_setup_phase(self) -> bool:
        """Advance to the next setup phase. Returns True if setup is complete."""
        if self.setup_complete:
            return True
        
        current_phase_value = self.setup_phase.value
        next_phase_value = current_phase_value + 1
        
        if next_phase_value >= len(SetupPhase):
            # Setup is complete, start battle rounds
            self.setup_complete = True
            # AIRCRAFT are treated as Strategic Reserves once the battle starts.
            try:
                for player in list(getattr(self, "players", []) or []):
                    if player is None:
                        continue
                    try:
                        units = list(getattr(player.get_army(), "units", []) or [])
                    except Exception:
                        units = []
                    for unit in units:
                        if unit is None:
                            continue
                        try:
                            if not bool(getattr(unit, "is_aircraft", False)):
                                continue
                            if bool(getattr(unit, "hover_mode", False)):
                                continue
                            if str(getattr(unit, "reserve_status", "deployed")) != "reserves":
                                continue
                            if hasattr(unit, "set_reserve_status"):
                                unit.set_reserve_status("strategic_reserves")
                            else:
                                unit.reserve_status = "strategic_reserves"
                        except Exception:
                            continue
            except Exception:
                pass
            # Set current player to first turn player
            if self.first_turn_player_index is not None:
                self.current_player_index = self.first_turn_player_index
            else:
                # Default: attacker goes first
                self.current_player_index = self.attacker_index if self.attacker_index is not None else 0
            
            # Set the battle round starting player to whoever goes first
            self.battle_round_starting_player_index = self.current_player_index
            self.phase = BattleRoundPhases.COMMAND_PHASE

            # BR1 start-of-battle-round hook:
            # At game start we haven't completed a full round cycle yet, so the normal
            # next_phase() logic won't publish battle_round_started until BR2.
            # Publish it now so "start of the first battle round" abilities trigger (e.g. Shalaxi quarry).
            try:
                for player in list(getattr(self, "players", []) or []):
                    if player is None:
                        continue
                    try:
                        for unit in list(getattr(player.get_army(), "units", []) or []):
                            try:
                                unit.initialize_round()
                            except Exception:
                                continue
                    except Exception:
                        pass
                    # Army-level battle round start hook (faction rules/buffs)
                    try:
                        player.get_army().on_battle_round_start(self.turn)
                    except Exception:
                        pass
                self.event_system.publish("battle_round_started", game=self, battle_round=self.turn)
            except Exception:
                pass

            # Start of Command phase for the first battle round.
            try:
                self.start_command_phase()
            except Exception:
                pass

            # Show detailed first turn information
            first_turn_player = self.get_current_player()
            if self.first_turn_player_index == self.attacker_index:
                role = "Attacker"
            elif self.first_turn_player_index == self.defender_index:
                role = "Defender"
            else:
                role = "Player"

            print(f"🎉 Setup complete! {first_turn_player.name} ({role}) goes first")
            return True
        else:
            self.setup_phase = SetupPhase(next_phase_value)
            print(f"📋 Advanced to setup phase: {self.setup_phase.name}")
            return False

    def execute_muster_armies_phase(
        self,
        player1_army_file: str = None,
        player2_army_file: str = None,
        player1_muster: "ArmyMusterRequest" = None,
        player2_muster: "ArmyMusterRequest" = None,
    ) -> None:
        """Phase 1: Muster Armies - Load army lists for both players."""
        print("📋 MUSTER ARMIES: Loading army lists...")
        
        if player1_muster is None or player2_muster is None:
            stored = getattr(self, "army_muster_requests", {}) or {}
            if player1_muster is None:
                player1_muster = stored.get("player1")
            if player2_muster is None:
                player2_muster = stored.get("player2")

        # Use army files from game.army_files if not provided as parameters
        if player1_army_file is None:
            player1_army_file = getattr(self, 'army_files', {}).get('player1', 'army_lists/warhammer_app_dump.txt')
        if player2_army_file is None:
            player2_army_file = getattr(self, 'army_files', {}).get('player2', 'army_lists/chaos_daemons_GT2023.txt')
        
        # Validate army files exist
        import os
        if player1_muster is None and not os.path.exists(player1_army_file):
            raise FileNotFoundError(f"Player 1 army file not found: {player1_army_file}")
        if player2_muster is None and not os.path.exists(player2_army_file):
            raise FileNotFoundError(f"Player 2 army file not found: {player2_army_file}")
        
        # Load armies for both players
        from ..classes.army import parse_army_list
        from ..classes.army_muster import ArmyMusterer
        from ..waha_helper import WahaHelper

        waha_helper = WahaHelper()
        muster = ArmyMusterer(waha_helper)
        
        if len(self.players) >= 2:
            # Load army for Player 1
            if player1_muster is not None:
                player1_army = muster.muster_army(player1_muster)
            else:
                player1_army = parse_army_list(player1_army_file, waha_helper)
            self.players[0].set_army(player1_army)
            
            # Load army for Player 2  
            if player2_muster is not None:
                player2_army = muster.muster_army(player2_muster)
            else:
                player2_army = parse_army_list(player2_army_file, waha_helper)
            self.players[1].set_army(player2_army)
            
            player1_units = len(self.players[0].get_army().units)
            player2_units = len(self.players[1].get_army().units)
            print(f"✅ {self.players[0].name}: {player1_units} units loaded from {player1_army_file}")
            print(f"✅ {self.players[1].name}: {player2_units} units loaded from {player2_army_file}")
        else:
            print("⚠️ Not enough players loaded")
    
    def execute_select_mission_objectives_phase(self) -> None:
        """Phase 2: Select Mission Objectives - Choose mission and objectives."""
        print("📋 SELECT MISSION OBJECTIVES: Setting up mission...")
        
        # Set up available commands for high-level strategy
        self.commands = ["attack", "defend", "move"]
        print(f"✅ Commands configured: {self.commands}")
        
        # Store selected mission info for use in CREATE_BATTLEFIELD phase
        # This will be set by the UI when the mission selection dialog is used
        if not hasattr(self, 'selected_mission_info'):
            # Use a valid default combination - M: Purge the Foe / Crucible of Battle / Layout 1
            self.selected_mission_info = {
                "combination_id": "M",
                "primary": "Purge the Foe",  # Valid with Crucible of Battle
                "deployment": "Crucible of Battle",   
                "layout": 1  # Valid layout for this combination
            }
            print(f"✅ Using default mission: {self.selected_mission_info}")
        else:
            print(f"✅ Mission selected: {self.selected_mission_info}")
        
        # Mission objectives will be placed during CREATE_BATTLEFIELD phase
        print("✅ Mission framework configured")

        # Imperial Knights: Code Chivalric selection (end of Read Mission Objectives step).
        try:
            for player in list(getattr(self, "players", []) or []):
                if player is None:
                    continue
                army = getattr(player, "get_army", lambda: None)()
                mgr = getattr(army, "code_chivalric", None) if army is not None else None
                if mgr is None:
                    continue
                mgr.on_read_mission_objectives(game=self, player=player)
                try:
                    is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
                except Exception:
                    is_human = False
                if is_human and getattr(self, "event_system", None) is not None:
                    self.event_system.publish("code_chivalric_prompt", player=player, game=self)
        except Exception:
            pass
    
    def execute_create_battlefield_phase(self, mission_name: str = None) -> None:
        """Phase 3: Create Battlefield - Set up map, terrain, deployment zones, and objectives."""
        print("📋 CREATE BATTLEFIELD: Setting up battlefield...")
        
        # Use selected mission info if available, otherwise use provided mission_name or default
        if hasattr(self, 'selected_mission_info'):
            deployment_mission = self.selected_mission_info["deployment"]
            terrain_layout = self.selected_mission_info["layout"]
            primary_mission = self.selected_mission_info["primary"]
        else:
            deployment_mission = mission_name or "Crucible of Battle"
            terrain_layout = 1
            primary_mission = "Take and Hold"
        
        # 1. Create the Map (already done in __init__)
        battlefield_width, battlefield_height = self.get_battlefield_size()
        print(f"✅ Map created: {battlefield_width}\" x {battlefield_height}\"")
        
        # 2. Terrain features based on selected terrain layout
        try:
            from .terrain_layouts import instantiate_layout
            terrain_features = instantiate_layout(terrain_layout)
            if terrain_features:
                self.map.add_terrain_features(terrain_features)
                print(f"✅ Terrain layout {terrain_layout} placed: {len(terrain_features)} features")
                # Debug: print RUINS footprints for verification
                try:
                    from .map import TerrainType
                    for idx, tf in enumerate(terrain_features):
                        if getattr(tf, 'terrain_type', None) == TerrainType.RUINS:
                            coords = list(tf.footprint.exterior.coords)[:-1]
                            pairs = [(round(float(x), 2), round(float(y), 2)) for (x, y) in coords]
                            print(f"   • RUINS #{idx+1} footprint: {pairs}")
                            # Floors detail (ground=0, first=1, second=2)
                            floors = getattr(tf, 'floors', []) or []
                            for fl in floors:
                                poly = fl.get('polygon')
                                elev = float(fl.get('elevation', 0.0))
                                try:
                                    from ..utility.constants import RUINS_FLOOR_HEIGHT
                                    level = int(round(elev / float(RUINS_FLOOR_HEIGHT)))
                                except Exception:
                                    level = 0
                                if hasattr(poly, 'exterior'):
                                    fcoords = list(poly.exterior.coords)[:-1]
                                    fpairs = [(round(float(x), 2), round(float(y), 2)) for (x, y) in fcoords]
                                    print(f"      - Floor L{level} (elev {elev:.1f}\"): {fpairs}")
                except Exception:
                    pass
            else:
                print(f"ℹ️ Terrain layout {terrain_layout} has no registered features")
        except Exception as e:
            print(f"⚠️ Failed to instantiate terrain layout {terrain_layout}: {e}")
        
        # 3. Set up mission-based deployment zones and objectives
        from .deployment import DeploymentManager
        deployment_manager = DeploymentManager(self, deployment_mission)
        
        # Set up deployment zones for the mission
        mission_zones = deployment_manager.create_deployment_zones()
        
        # Convert to the format expected by the game for visualization
        self.deployment_zones = {}
        for zone in mission_zones:
            if zone['zone_type'] == 'defender':
                # Assign to first player as defender (will be properly assigned later)
                self.deployment_zones[self.players[0].name] = zone
            elif zone['zone_type'] == 'attacker':
                # Assign to second player as attacker
                self.deployment_zones[self.players[1].name] = zone
        
        print(f"✅ Mission deployment zones created: {deployment_mission}")
        
        # 4. Set up mission objectives
        deployment_manager.setup_mission_objectives()
        print(f"✅ Mission objectives placed: {len(self.objectives)} objectives")
        print(f"✅ Primary Mission: {primary_mission}")

        # Apply primary-mission setup rules that modify objective markers (Chapter Approved 2025/26).
        try:
            self._apply_primary_mission_setup_rules()
        except Exception as e:
            print(f"⚠️ Failed to apply primary mission setup rules: {e}")
    
    def execute_determine_attacker_defender_phase(self) -> None:
        """Phase 4: Determine Attacker and Defender - Roll off to determine roles."""
        print("📋 DETERMINE ATTACKER AND DEFENDER: Rolling off...")
        
        import random
        from ..utility.dice import get_roll
        
        player1_roll = get_roll("1D6")
        player2_roll = get_roll("1D6")
        try:
            from ..utility.event_bus import append_dice
            append_dice(self.players[0].name, f"First turn roll: {player1_roll}")
            append_dice(self.players[1].name, f"First turn roll: {player2_roll}")
        except Exception:
            pass
        
        print(f"🎲 {self.players[0].name} rolled: {player1_roll}")
        print(f"🎲 {self.players[1].name} rolled: {player2_roll}")
        
        if player1_roll > player2_roll:
            self.attacker_index = 0
            self.defender_index = 1
            print(f"⚔️ {self.players[0].name} is the Attacker")
            print(f"🛡️ {self.players[1].name} is the Defender")
        elif player2_roll > player1_roll:
            self.attacker_index = 1
            self.defender_index = 0
            print(f"⚔️ {self.players[1].name} is the Attacker")
            print(f"🛡️ {self.players[0].name} is the Defender")
        else:
            # Tie - re-roll
            print("🎲 Tie! Re-rolling...")
            return self.execute_determine_attacker_defender_phase()
        
        # Set deployment turn to defender (defender deploys first)
        self.deployment_turn_index = self.defender_index
        # Reset deployment special-rule trackers for a fresh setup sequence
        self.deployment_skip_turns = {}

    def _apply_hover_declarations(self) -> None:
        """Declare Hover mode choices before Battle Formations steps."""
        players = list(getattr(self, "players", []) or [])
        if not players:
            return

        for player in players:
            army = getattr(player, "get_army", lambda: None)()
            if army is None:
                continue
            candidates = []
            for unit in list(getattr(army, "units", []) or []):
                try:
                    if bool(getattr(unit, "hover_declared", False)):
                        continue
                except Exception:
                    pass
                try:
                    if not bool(getattr(unit, "has_hover", lambda: False)()):
                        continue
                except Exception:
                    continue
                try:
                    if not bool(getattr(unit, "has_keyword", lambda *_a, **_k: False)("Aircraft")):
                        continue
                except Exception:
                    continue
                candidates.append(unit)

            if not candidates:
                continue

            options = [str(getattr(u, "_id", "")) for u in candidates]
            ctx = {
                "player": getattr(player, "name", ""),
                "units": [getattr(u, "name", "") for u in candidates],
                "unit_ids": list(options),
            }

            selection = None
            try:
                chooser = getattr(player, "_choose_optional_value", None)
                if callable(chooser):
                    selection = chooser("HOVER_MODE", list(options), ctx)
            except Exception:
                selection = None

            selected_ids: set[str] = set()
            selected_names: set[str] = set()

            if isinstance(selection, dict):
                for key, value in selection.items():
                    if not value:
                        continue
                    skey = str(key).strip()
                    if skey in options:
                        selected_ids.add(skey)
                    else:
                        selected_names.add(skey.lower())
            elif isinstance(selection, (list, tuple, set)):
                for item in selection:
                    skey = str(item).strip()
                    if skey in options:
                        selected_ids.add(skey)
                    else:
                        selected_names.add(skey.lower())
            elif isinstance(selection, str):
                skey = selection.strip()
                if skey in options:
                    selected_ids.add(skey)
                else:
                    selected_names.add(skey.lower())
            elif isinstance(selection, bool):
                if selection:
                    selected_ids.update(options)

            if selection is None:
                for unit in candidates:
                    ctx_unit = {
                        "player": getattr(player, "name", ""),
                        "unit": getattr(unit, "name", ""),
                        "unit_id": str(getattr(unit, "_id", "")),
                    }
                    try:
                        should = bool(player._should_use_optional_ability(f"HOVER_MODE:{unit._id}", ctx_unit))
                    except Exception:
                        should = False
                    if should:
                        selected_ids.add(str(getattr(unit, "_id", "")))

            for unit in candidates:
                try:
                    unit_id = str(getattr(unit, "_id", ""))
                    unit_name = str(getattr(unit, "name", "") or "").lower()
                except Exception:
                    unit_id = ""
                    unit_name = ""
                try:
                    if unit_id in selected_ids or (unit_name and unit_name in selected_names):
                        unit.set_hover_mode(True)
                except Exception:
                    pass
                try:
                    unit.hover_declared = True
                except Exception:
                    pass

    def execute_declare_battle_formations_phase(self) -> None:
        """Phase 5: Declare Battle Formations - Attach leaders, embark in transports, allocate reserves."""
        print("📋 DECLARE BATTLE FORMATIONS: Validating formations...")

        # Hover mode declarations must happen before any other formation steps.
        try:
            self._apply_hover_declarations()
        except Exception:
            pass

        # Validate leader attachment limits per army
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "get_army", lambda: None)()
            if army is None:
                continue
            try:
                army.validate_leaders()
            except Exception as e:
                raise RuntimeError(f"Leader attachment validation failed for {p.name}: {e}")

        # Nurgle's Gift (Aura): select a Plague during Declare Battle Formations.
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "get_army", lambda: None)()
            if army is None:
                continue
            try:
                mgr = getattr(army, "nurgles_gift", None)
            except Exception:
                mgr = None
            if mgr is None:
                continue
            try:
                mgr.on_declare_battle_formations_start(game=self)
            except Exception:
                pass

        print("✅ Battle formations declared")
    
    def execute_deploy_armies_phase(self, manual_phases: bool = False, decision_makers: dict = None) -> None:
        """Phase 6: Deploy Armies - Execute the deployment phase."""
        print("📋 DEPLOY ARMIES: Starting deployment sequence...")
        
        # Check if we have human players that need UI-based deployment
        has_human_players = any(player.type.name == 'HUMAN' for player in self.players)
        
        if has_human_players and manual_phases:
            # For human players in manual mode, set up deployment state but don't auto-deploy
            # The UI will handle the actual deployment decisions
            print("👤 Human deployment mode - use UI to deploy units")
            
            # Set up deployment zones if not already done
            if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
                # Always use mission polygon deployment zones (no rectangular legacy zones).
                try:
                    mission_name = None
                    try:
                        mission_name = (getattr(self, "selected_mission_info", None) or {}).get("deployment")
                    except Exception:
                        mission_name = None
                    mission_name = mission_name or "Crucible of Battle"

                    from .deployment import DeploymentManager
                    deployment_manager = DeploymentManager(self, mission_name=mission_name)
                    zones = deployment_manager.create_deployment_zones()
                    defender_zone = next(z for z in zones if z.get("zone_type") == "defender")
                    attacker_zone = next(z for z in zones if z.get("zone_type") == "attacker")

                    defender_idx = getattr(self, "defender_index", None)
                    attacker_idx = getattr(self, "attacker_index", None)
                    if defender_idx is None or attacker_idx is None:
                        defender_idx, attacker_idx = 0, 1

                    self.deployment_zones = {
                        self.players[defender_idx].name: defender_zone,
                        self.players[attacker_idx].name: attacker_zone,
                    }
                except Exception as e:
                    raise RuntimeError(f"Failed to initialize mission deployment zones: {e}")
            
            # Initialize deployment tracking
            if not hasattr(self, 'deployment_turn_index'):
                self.deployment_turn_index = getattr(self, 'defender_index', 0)
            # Reset / initialize TITANIC skip-turn tracker (safe for checkpoint-loaded games)
            self.deployment_skip_turns = {}
            
            # Mark that we're in deployment phase
            self.waiting_for_deployment_input = False
            print("✅ Deployment phase initialized - deploy units through UI")
        
        elif decision_makers:
            # Use the proper deployment manager with decision makers for AI vs AI
            from .deployment import DeploymentManager
            deployment_manager = DeploymentManager(self)
            deployment_results = deployment_manager.execute_deployment_sequence(decision_makers)
            
            # Store deployment results for reference
            self.deployment_results = deployment_results
            print("✅ Army deployment complete")
        else:
            # Use the existing complete_deployment_phase method for fallback
            self.complete_deployment_phase(manual_phases=manual_phases)
            
            # Only print completion message if not waiting for manual input
            if not getattr(self, 'waiting_for_deployment_input', False):
                print("✅ Army deployment complete")

    def execute_redeploy_units_phase(self) -> None:
        """Phase: Redeploy Units - Alternate resolving redeploy rules, Attacker first.

        Rules:
        - Some rules allow redeploying certain units after both armies are deployed.
        - Players alternate resolving such rules, starting with the Attacker.
        - Redeploy allows selecting a new valid deployment location for eligible units.
        """
        print("📋 REDEPLOY UNITS: Resolving redeploy abilities...")
        if self.attacker_index is None or self.defender_index is None:
            print("ℹ️ Attacker/Defender not set; skipping Redeploy Units phase")
            return

        players_in_order = [self.players[self.attacker_index], self.players[self.defender_index]]

        # Collect eligible units per convention: unit.has_redeploy() -> (has, count, can_place_in_reserves)
        redeploy_pool = {p: [] for p in players_in_order}
        for p in players_in_order:
            army = p.get_army()
            if not army:
                continue
            for u in army.units:
                try:
                    has_redeploy, count, can_place_in_reserves = u.has_redeploy()
                except Exception:
                    has_redeploy, count, can_place_in_reserves = (False, 0, False)
                if has_redeploy and u.deployed and u.reserve_status == 'deployed':
                    redeploy_pool[p].append((u, count, can_place_in_reserves))

        if not any(redeploy_pool.values()):
            print("✅ No units with Redeploy; skipping")
            return

        # Alternate between players until all redeploy options exhausted
        turn_idx = 0
        while any(redeploy_pool[p] for p in players_in_order):
            current_player = players_in_order[turn_idx % 2]
            options = redeploy_pool[current_player]
            if not options:
                turn_idx += 1
                continue
            # Pick the first available unit; in the future, UI/AI should decide
            unit, remaining, can_place_in_reserves = options.pop(0)
            print(f"🔄 {current_player.name} redeploys {unit.name}")
            # If the redeploy count was D3, print the stored roll result if available
            roll_info = getattr(unit, '_redeploy_d_roll', None)
            if roll_info:
                print(f"🎲 Redeploy count ({roll_info['expr']}) for {unit.name}: {roll_info['total']} (rolled {roll_info['rolls']})")
            # Simple random valid redeploy within current DZ for now
            # A proper UI should present valid positions; here we keep rules isolated
            pos = self._find_valid_redeploy_position(current_player, unit)
            if pos:
                # Use unit's deployment placement to set model positions
                try:
                    from shapely.geometry import Polygon as _Poly  # noqa: F401
                except Exception:
                    pass
                positions = unit.calculate_model_positions(
                    pos[0], pos[1], self.map,
                    boundary_repulsors=self.map.get_battlefield_edge_repulsors()
                )
                if positions:
                    print(f"✅ {unit.name} redeployed to ({pos[0]:.1f}, {pos[1]:.1f})")
                else:
                    print(f"⚠️ Redeploy failed to find valid formation for {unit.name}")
            else:
                print(f"⚠️ No valid redeploy position found for {unit.name}")
            # If multiple redeploy counts allowed, requeue
            if remaining > 1:
                options.insert(0, (unit, remaining - 1, can_place_in_reserves))
            turn_idx += 1

        print("✅ Redeploy phase complete")

    def _find_valid_redeploy_position(self, player: 'Player', unit: 'Unit') -> tuple | None:
        # Naive sampling within player's DZ; real impl should mirror deployment validation
        import random
        dz = self.deployment_zones.get(player.name, {})
        zone = dz.get('zone')
        for _ in range(200):
            x = random.uniform(0, self.battlefield.width)
            y = random.uniform(0, self.battlefield.height)
            if zone and hasattr(zone, 'contains_point') and not zone.contains_point(x, y):
                continue
            z = self.map.get_height_at_point(x, y)
            # Reuse arrival placement validation
            if self.can_place_unit_arriving_from_reserves(unit, (x, y, z)):
                return (x, y, z)
        return None
    
    def execute_determine_first_turn_order_phase(self) -> None:
        """Phase 7: Determine First Turn Order - Attacker rolls to see who goes first."""
        print("📋 DETERMINE FIRST TURN ORDER: Rolling for first turn (roll-off)...")

        from ..utility.dice import get_roll

        p1 = self.players[0]
        p2 = self.players[1]

        while True:
            roll1 = get_roll("1D6")
            roll2 = get_roll("1D6")
            try:
                from ..utility.event_bus import append_dice
                append_dice(p1.name, f"First turn roll-off: {roll1}")
                append_dice(p2.name, f"First turn roll-off: {roll2}")
            except Exception:
                pass
            print(f"🎲 {p1.name} rolled: {roll1}")
            print(f"🎲 {p2.name} rolled: {roll2}")
            if roll1 == roll2:
                print("🔁 Tie on roll-off - re-rolling...")
                continue
            if roll1 > roll2:
                self.first_turn_player_index = 0
                print(f"✅ {p1.name} wins the roll-off and takes the first turn")
            else:
                self.first_turn_player_index = 1
                print(f"✅ {p2.name} wins the roll-off and takes the first turn")
            break

        # Clear deployment actions since deployment phase is now complete
        self.clear_deployment_actions()
    
    def execute_resolve_prebattle_rules_phase(self) -> None:
        """Phase 8: Resolve Pre-battle Rules - Resolve any pre-battle rules, abilities, or stratagems."""
        print("📋 RESOLVE PREBATTLE RULES: Resolving pre-battle rules...")
        
        # Handle Scout moves for all players
        self._handle_scout_moves()

        # TODO - other pre-battle rules (e.g., Detachment stuff like WE dice rolls, etc.)
        
        print("✅ Pre-battle rules resolved")
    
    def _handle_scout_moves(self) -> None:
        """Handle scout moves for all players during pre-battle rules phase."""
        print("🔍 Processing Scout moves...")
        
        # Get all units with Scout ability from both players
        scout_units = []
        for player in self.players:
            if player.get_army():
                for unit in player.get_army().units:
                    has_scout, scout_distance = unit.has_scout()
                    if has_scout and unit.deployed and unit.reserve_status == 'deployed':
                        scout_units.append((player, unit, scout_distance))
        
        if not scout_units:
            print("✅ No units with Scout ability found")
            return
        
        print(f"🔍 Found {len(scout_units)} units with Scout ability")
        
        # Sort units by player (first turn player goes first)
        # During setup phase, use first_turn_player_index instead of current_player_index
        if self.first_turn_player_index is not None:
            first_turn_player = self.players[self.first_turn_player_index]
        else:
            # Fallback to attacker if first turn not determined yet
            first_turn_player = self.get_attacker() if self.attacker_index is not None else self.players[0]
        
        scout_units_by_player = {}
        
        for player, unit, scout_distance in scout_units:
            if player not in scout_units_by_player:
                scout_units_by_player[player] = []
            scout_units_by_player[player].append((unit, scout_distance))
        
        # Process scout moves in turn order (first turn player first)
        players_in_order = [first_turn_player]
        for player in self.players:
            if player != first_turn_player:
                players_in_order.append(player)
        
        # Check if we have human players that need UI-based scout moves
        has_human_players = any(player.type.name == 'HUMAN' for player in self.players)
        
        if has_human_players:
            # For human players, let the UI handle scout moves
            # The PreBattlePhaseHandler will manage the scout move sequence
            print("👤 Human scout moves will be handled by UI")
            print("✅ Scout phase initialized - use UI to make scout moves")
        else:
            # For AI-only games, auto-skip scout moves for now
            # In the future, this could integrate with AI decision making
            for player in players_in_order:
                if player in scout_units_by_player:
                    print(f"🔍 {player.name}'s Scout moves:")
                    for unit, scout_distance in scout_units_by_player[player]:
                        print(f"  - {unit.name} (Scout {scout_distance}\")")
                        print(f"    Skipping scout move (auto-skip for AI)")
                        unit.scout_move_made = True  # Mark as skipped
            
            print("✅ Scout moves processed (auto-skipped for AI)")
    
    def execute_current_setup_phase(self, **kwargs) -> None:
        """Execute the current setup phase with any necessary parameters."""
        if self.setup_phase == SetupPhase.MUSTER_ARMIES:
            self.execute_muster_armies_phase(
                kwargs.get('player1_army_file'), 
                kwargs.get('player2_army_file')
            )
        elif self.setup_phase == SetupPhase.SELECT_MISSION_OBJECTIVES:
            self.execute_select_mission_objectives_phase()
        elif self.setup_phase == SetupPhase.CREATE_BATTLEFIELD:
            self.execute_create_battlefield_phase()
        elif self.setup_phase == SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER:
            self.execute_determine_attacker_defender_phase()
        elif self.setup_phase == SetupPhase.DECLARE_BATTLE_FORMATIONS:
            self.execute_declare_battle_formations_phase()
        elif self.setup_phase == SetupPhase.DEPLOY_ARMIES:
            self.execute_deploy_armies_phase(
                manual_phases=kwargs.get('manual_phases', False),
                decision_makers=kwargs.get('decision_makers')
            )
        elif self.setup_phase == SetupPhase.REDEPLOY_UNITS:
            self.execute_redeploy_units_phase()
        elif self.setup_phase == SetupPhase.DETERMINE_FIRST_TURN_ORDER:
            self.execute_determine_first_turn_order_phase()
        elif self.setup_phase == SetupPhase.RESOLVE_PREBATTLE_RULES:
            self.execute_resolve_prebattle_rules_phase()
