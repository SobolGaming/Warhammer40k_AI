from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
import inspect
import hashlib
import html
import json
import re
import logging
import copy
import math
from .event.system import EventSystem
from .event_log import DeterministicEventLog
from ..battlefield.map import Map, Objective
from .mission_cards import PrimaryMissionCard, SecondaryMissionCard
from . import game_decision_runtime, game_scoring, game_serialization
from ..roster.player import Player
from ..units.unit import Unit
from ..units.model import Model
from .phase import SetupPhase, BattleRoundPhases
from .battlefield import Battlefield, BattlefieldSize
from .turn_manager import next_phase as _next_phase
from .commands import GameCommand
from .command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_NEXT_PHASE,
    CMD_RESOLVE_DECISION,
    CMD_SELECT_MISSION,
    CMD_START_COMMAND_PHASE,
    CMD_SET_DEPLOYMENT_WAITING,
)
from .decisions import CandidateAction, DecisionOption, DecisionQueue, DecisionRequest, DecisionResult
from .candidate_semantics import ensure_candidate_semantic_metadata
from .decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_CHOOSE_MISSION,
    DECISION_CHOOSE_PLEDGE,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_RESERVES,
    DECISION_DISEMBARK,
    DECISION_DECLARE_SHOTS,
    DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
    DECISION_CHOOSE_QUARRY,
    DECISION_CHOOSE_MISSION_TACTIC,
    DECISION_CHOOSE_CHIVALRIC_OATH,
    DECISION_CHOOSE_START_OF_BATTLE_KEYWORD,
    DECISION_MOVE_UNIT,
    DECISION_ALLOCATE_DAMAGE,
    DECISION_SCOUT_MOVE,
    DECISION_SELECT_SETUP_REACTIVE_TARGET,
    DECISION_SELECT_TARGET_MODEL,
    DECISION_SELECT_OVERWATCH_SHOOTER,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
    DECISION_SELECT_REALM_OF_CHAOS_UNITS,
    DECISION_SELECT_REVERBERATING_SUMMONS_UNIT,
)
from .random_source import RandomSource
from .decision_controller import DecisionController, DecisionControllerHub
from .decision_record import DecisionRecordStore
from .decision_port import DecisionPort, get_decision_provider
from .descriptor_compiler import compile_descriptor_bundle
from .reserve_metadata import ensure_reserve_start_metadata, set_reserve_start_metadata
from .ruleset import RulesetBundle
from .version_adapter import ensure_version_adapter_boundary
from .tier1_plan import Tier1Plan, build_heuristic_tier1_plan
from .tier2_orchestrator import Tier2TaskBundle, build_tier2_task_bundle
from .commander_plan import (
    BattleRoundPlan,
    CommanderDirtyFlags,
    PhaseExecutionReport,
)
from .deployment_plan import DeploymentDirtyFlags, DeploymentPlan
from .time_manager import TimeManager
from .deployment_intent import DeploymentIntent
from .deployment_solver import generate_deployment_candidates
from .movement_intent import MovementIntent
from .movement_solver import generate_move_unit_candidates
from .path_witness import PathWitnessStore
from .dice_rolls import DiceRollManager
from .game_charge import ChargeService
from .game_commands import GameCommandService
from .game_faction_state import FactionRuntimeState
from .game_fight import FightService
from .game_phase_handlers import PhaseHandlerService
from .game_reactive_rules import ReactiveRulesService
from .game_rule_events import GameRuleEventService
from .game_scoring import GameScoringService
from .game_setup_deployment import SetupDeploymentService
from .game_shooting import ShootingService
from .attack_resolution import AttackResolutionManager
from .ref_codec import encode_refs
from ..rules.lifecycle import AbilityLifecycle
from ..rules.registry import RuleRegistry
from ..rules.providers.default_rules import build_default_rule_providers
from ..rules.emperors_children import (
    INTERNAL_RIVALRIES_NAME,
    PLEDGES_TO_THE_DARK_PRINCE_NAME,
)
from ..utility.calcs import get_dist, clear_enemy_model_cache
from ..utility.charge_roll import ChargeRollResult, ChargeRollSpec
from ..utility.dice import DiceCollection, get_roll
from ..utility.constants import TOTAL_ROUNDS, ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
from ..utility.entity_ids import get_entity_id, maybe_entity_id
from ..utility.entity_registry import EntityRegistry, rebuild_registry_from_game
from ..utility.game_context import game_context
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..roster.army_muster import ArmyMusterRequest


def _charge_service_for(game) -> ChargeService:
    ensure = getattr(game, "_ensure_charge_service", None)
    return ensure() if callable(ensure) else ChargeService(game)


def _fight_service_for(game) -> FightService:
    ensure = getattr(game, "_ensure_fight_service", None)
    return ensure() if callable(ensure) else FightService(game)


def _command_service_for(game) -> GameCommandService:
    ensure = getattr(game, "_ensure_command_service", None)
    return ensure() if callable(ensure) else GameCommandService(game)


def _scoring_service_for(game) -> GameScoringService:
    ensure = getattr(game, "_ensure_scoring_service", None)
    return ensure() if callable(ensure) else GameScoringService(game)


_GAME_SERVICE_SPECS = (
    ("rule_events", GameRuleEventService),
    ("charge", ChargeService),
    ("fight", FightService),
    ("commands_service", GameCommandService),
    ("scoring", GameScoringService),
    ("setup_deployment", SetupDeploymentService),
    ("reactive_rules", ReactiveRulesService),
    ("shooting", ShootingService),
    ("phase_handlers", PhaseHandlerService),
)


def _service_class_has_method(service_cls, name: str) -> bool:
    value = inspect.getattr_static(service_cls, name, None)
    return inspect.isfunction(value) or isinstance(value, (staticmethod, classmethod))


def _get_or_create_service(game, attr_name: str, service_cls):
    game_attrs = object.__getattribute__(game, "__dict__")
    service = game_attrs.get(attr_name)
    if service is None:
        service = service_cls(game)
        setattr(game, attr_name, service)
    return service


def _resolve_service_method(game, name: str):
    for attr_name, service_cls in _GAME_SERVICE_SPECS:
        if not _service_class_has_method(service_cls, name):
            continue
        service = _get_or_create_service(game, attr_name, service_cls)
        method = getattr(service, name)
        if callable(method):
            return method
    return None


def _service_method_names(*, public_only: bool) -> set[str]:
    names: set[str] = set()
    for _, service_cls in _GAME_SERVICE_SPECS:
        for base in service_cls.__mro__:
            if base is object:
                continue
            for name, value in vars(base).items():
                if public_only and name.startswith("_"):
                    continue
                if inspect.isfunction(value) or isinstance(value, (staticmethod, classmethod)):
                    names.add(name)
    return names


_GAME_PUBLIC_SERVICE_METHODS = _service_method_names(public_only=True)
_GAME_ALL_SERVICE_METHODS = _service_method_names(public_only=False)
_PRIVATE_COMPATIBILITY_METHODS = {
    "_apply_charge_modifiers",
    "_collect_charge_modifiers",
    "_find_charge_destination",
    "_finalize_successful_charge_move",
    "_get_charge_roll_spec",
    "_record_engaged_enemies_at_turn_start",
}


def _make_facade_method(name: str):
    def _facade_method(self, *args, **kwargs):
        method = _resolve_service_method(self, name)
        if method is None:
            raise AttributeError(name)
        return method(*args, **kwargs)

    _facade_method.__name__ = name
    _facade_method.__qualname__ = f"Game.{name}"
    return _facade_method


class GameFacadeMeta(type):
    def __getattr__(cls, name: str):
        if name in _GAME_ALL_SERVICE_METHODS:
            return _make_facade_method(name)
        raise AttributeError(name)

    def __dir__(cls):
        return sorted(set(super().__dir__()) | _GAME_PUBLIC_SERVICE_METHODS)


class Game(metaclass=GameFacadeMeta):
    VP_MAX_TOTAL = GameScoringService.VP_MAX_TOTAL
    VP_MAX_PRIMARY = GameScoringService.VP_MAX_PRIMARY
    VP_MAX_SECONDARY = GameScoringService.VP_MAX_SECONDARY
    VP_MAX_BATTLE_READY = GameScoringService.VP_MAX_BATTLE_READY
    VP_MAX_PRIMARY_PLUS_SECONDARY = GameScoringService.VP_MAX_PRIMARY_PLUS_SECONDARY
    VP_MAX_PER_FIXED_SECONDARY_CARD = GameScoringService.VP_MAX_PER_FIXED_SECONDARY_CARD

    @property
    def map(self) -> Map:
        return self._map

    @map.setter
    def map(self, value: Map) -> None:
        self._map = value
        if value is None:
            return
        try:
            value.game = self
        except (AttributeError, TypeError):
            return

    def set_map(self, game_map: Map) -> None:
        self.map = game_map

    def get_current_player(self) -> Player:
        """Get the current player without reflective service dispatch."""
        return self.players[self.current_player_index]

    def install_decision_providers(self, **providers) -> None:
        self.decision_port.install(providers)

    def __init__(
        self,
        battlefield: Battlefield,
        players: List[Player] | None = None,
        *,
        ruleset_bundle: RulesetBundle | None = None,
        core_rules_id: str | None = None,
        rules_commentary_id: str | None = None,
        mission_pack_id: str | None = None,
        terrain_pack_id: str | None = None,
        dataslate_id: str | None = None,
        points_id: str | None = None,
        faction_pack_id: str | None = None,
        detachment_pack_id: str | None = None,
    ):
        self.battlefield = battlefield
        # Avoid mutable default arg: always create a fresh list per Game instance.
        self.players = list(players) if players else []
        self.turn = 1
        self.current_player_index = 0
        self.decision_port = DecisionPort()
        self.map = Map(battlefield.width, battlefield.height)
        self.event_system = EventSystem()
        self.event_log = DeterministicEventLog()
        self.event_log.attach(self)
        self.decision_controller_hub = DecisionControllerHub(self)
        self.decision_controller_hub.attach()
        self.decision_record_store = DecisionRecordStore(self)
        self._tier1_turn_plans: dict[tuple[int, str], Tier1Plan] = {}
        self._tier2_task_bundles: dict[tuple[int, str], Tier2TaskBundle] = {}
        self._battle_round_plans: dict[tuple[int, str], BattleRoundPlan] = {}
        self._commander_dirty_flags: dict[tuple[int, str], CommanderDirtyFlags] = {}
        self._commander_phase_reports: dict[tuple[int, str], list[PhaseExecutionReport]] = {}
        self._deployment_plans: dict[str, DeploymentPlan] = {}
        self._deployment_dirty_flags: dict[str, DeploymentDirtyFlags] = {}
        self.time_manager = TimeManager()
        self.path_witness_store = PathWitnessStore()
        self.objectives = []
        self.commands = []
        self.command_queue: list[GameCommand] = []
        self._command_context_depth = 0
        self.decision_queue = DecisionQueue()
        self.random_source = RandomSource()
        self._ruleset_bundle: RulesetBundle | None = None
        if ruleset_bundle is None:
            ruleset_bundle = RulesetBundle.from_values(
                core_rules_id=core_rules_id,
                rules_commentary_id=rules_commentary_id,
                mission_pack_id=mission_pack_id,
                terrain_pack_id=terrain_pack_id,
                dataslate_id=dataslate_id,
                points_id=points_id,
                faction_pack_id=faction_pack_id,
                detachment_pack_id=detachment_pack_id,
            )
        else:
            override = RulesetBundle.from_values(
                core_rules_id=core_rules_id,
                rules_commentary_id=rules_commentary_id,
                mission_pack_id=mission_pack_id,
                terrain_pack_id=terrain_pack_id,
                dataslate_id=dataslate_id,
                points_id=points_id,
                faction_pack_id=faction_pack_id,
                detachment_pack_id=detachment_pack_id,
            )
            if (
                (
                    core_rules_id
                    or rules_commentary_id
                    or mission_pack_id
                    or terrain_pack_id
                    or dataslate_id
                    or points_id
                    or faction_pack_id
                    or detachment_pack_id
                )
                and ruleset_bundle != override
            ):
                raise ValueError("Ruleset bundle values conflict with explicit ids.")
        self.ruleset_bundle = ruleset_bundle
        self.roll_manager = DiceRollManager()
        self.attack_manager = AttackResolutionManager()
        self.charge = ChargeService(self)
        self.fight = FightService(self)
        self.commands_service = GameCommandService(self)
        self.scoring = GameScoringService(self)
        self.rule_events = GameRuleEventService(self)
        self.setup_deployment = SetupDeploymentService(self)
        self.phase_handlers = PhaseHandlerService(self)
        self.reactive_rules = ReactiveRulesService(self)
        self.shooting = ShootingService(self)
        from ..rules.fates_in_flux import FatesInFluxManager
        self.fates_in_flux = FatesInFluxManager(self)
        # Headless/test default: auto-resolve dice roll decisions via headless agent.
        # Interactive UI or network server should disable this.
        self.auto_resolve_dice_rolls = True
        try:
            from .headless_decision_agent import HeadlessDecisionAgent
            self._headless_decision_agent = HeadlessDecisionAgent(self)
        except ImportError:
            self._headless_decision_agent = None
        self.ability_lifecycle = AbilityLifecycle(self)
        self.event_system.lifecycle = self.ability_lifecycle
        # Authoritative (server/local) vs client-replay gating for decision queues.
        self.is_authoritative = True
        self.phase = BattleRoundPhases.COMMAND_PHASE  # Initialize phase to COMMAND_PHASE
        # Command phase timing: True only during the Battle-shock step of the current player's Command phase.
        self.battle_shock_step_active = False
        
        # Wire game reference into any pre-supplied players
        for idx, p in enumerate(self.players):
            p.set_game(self)
            p.assign_default_ui_color(idx)

        # Install default rules subscribers (e.g. on-kill rewards)
        self._install_default_event_subscribers()
        # Server-authoritative decision hooks
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_monarch_of_the_hunt)

        # Setup phase tracking
        self.setup_phase = SetupPhase.MUSTER_ARMIES  # Start with first setup phase
        self.setup_complete = False  # Track when setup is finished
        
        # Deployment tracking
        self.deployment_turn_index = 0  # Track whose turn it is to deploy (0 = defender, 1 = attacker)
        self.attacker_index = None  # Index of the attacking player (will be set during DETERMINE_ATTACKER_AND_DEFENDER)
        self.defender_index = None  # Index of the defending player (will be set during DETERMINE_ATTACKER_AND_DEFENDER)
        self.deployment_zones = {}  # Store deployment zones for visualization {player_id: zone_dict}
        self.waiting_for_deployment_input = False  # Flag for manual phases during deployment
        self.deployment_actions = {}  # Track last deployment action for each player (by id)
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
        # Phase-scoped enemy unit destruction tracking (for phase-end Leadership CP abilities).
        self._phase_enemy_unit_destroyers: Dict[str, set[str]] = {}
        # Phase-scoped enemy model destruction tracking (for phase-end penalties like Daemonic Patrons).
        self._phase_enemy_model_destroyers: Dict[str, set[str]] = {}
        # Faction-specific transient state remains available through legacy private
        # compatibility properties below.
        self.faction_state = FactionRuntimeState()
        # Optional in-engine army mustering requests (player1/player2) for setup phase.
        self.army_muster_requests: Dict[str, Any] = {}
        self.entity_registry = EntityRegistry()
        self.rebuild_entity_registry()

    def _ensure_faction_state(self) -> FactionRuntimeState:
        state = getattr(self, "faction_state", None)
        if state is None:
            state = FactionRuntimeState()
            self.faction_state = state
        return state

    def _ensure_charge_service(self) -> ChargeService:
        service = getattr(self, "charge", None)
        if service is None:
            service = ChargeService(self)
            self.charge = service
        return service

    def _ensure_fight_service(self) -> FightService:
        service = getattr(self, "fight", None)
        if service is None:
            service = FightService(self)
            self.fight = service
        return service

    def _ensure_command_service(self) -> GameCommandService:
        service = getattr(self, "commands_service", None)
        if service is None:
            service = GameCommandService(self)
            self.commands_service = service
        return service

    def _ensure_scoring_service(self) -> GameScoringService:
        service = getattr(self, "scoring", None)
        if service is None:
            service = GameScoringService(self)
            self.scoring = service
        return service

    def _ensure_rule_events_service(self) -> GameRuleEventService:
        service = getattr(self, "rule_events", None)
        if service is None:
            service = GameRuleEventService(self)
            self.rule_events = service
        return service

    def _ensure_setup_deployment_service(self) -> SetupDeploymentService:
        service = getattr(self, "setup_deployment", None)
        if service is None:
            service = SetupDeploymentService(self)
            self.setup_deployment = service
        return service

    def _ensure_phase_handlers_service(self) -> PhaseHandlerService:
        service = getattr(self, "phase_handlers", None)
        if service is None:
            service = PhaseHandlerService(self)
            self.phase_handlers = service
        return service

    def _ensure_reactive_rules_service(self) -> ReactiveRulesService:
        service = getattr(self, "reactive_rules", None)
        if service is None:
            service = ReactiveRulesService(self)
            self.reactive_rules = service
        return service

    def _ensure_shooting_service(self) -> ShootingService:
        service = getattr(self, "shooting", None)
        if service is None:
            service = ShootingService(self)
            self.shooting = service
        return service

    def __getattr__(self, name: str):
        method = _resolve_service_method(self, name)
        if method is not None:
            return method
        raise AttributeError(name)

    @property
    def _adepta_sororitas_destroyers_by_army_id(self):
        return self._ensure_faction_state().adepta_sororitas_destroyers_by_army_id

    @_adepta_sororitas_destroyers_by_army_id.setter
    def _adepta_sororitas_destroyers_by_army_id(self, value) -> None:
        self._ensure_faction_state().adepta_sororitas_destroyers_by_army_id = value

    @property
    def _shadow_of_chaos_zone_overrides(self):
        return self._ensure_faction_state().shadow_of_chaos_zone_overrides

    @_shadow_of_chaos_zone_overrides.setter
    def _shadow_of_chaos_zone_overrides(self, value) -> None:
        self._ensure_faction_state().shadow_of_chaos_zone_overrides = value

    @property
    def _corrupt_realspace_check(self):
        return self._ensure_faction_state().corrupt_realspace_check

    @_corrupt_realspace_check.setter
    def _corrupt_realspace_check(self, value) -> None:
        self._ensure_faction_state().corrupt_realspace_check = value

    @property
    def _phoenix_gem_pending(self):
        return self._ensure_faction_state().phoenix_gem_pending

    @_phoenix_gem_pending.setter
    def _phoenix_gem_pending(self, value) -> None:
        self._ensure_faction_state().phoenix_gem_pending = value

    @property
    def _blood_surge_shooting_snapshot(self):
        return self._ensure_faction_state().blood_surge_shooting_snapshot

    @_blood_surge_shooting_snapshot.setter
    def _blood_surge_shooting_snapshot(self, value) -> None:
        self._ensure_faction_state().blood_surge_shooting_snapshot = value

    @property
    def _brazen_fury_shooting_snapshot(self):
        return self._ensure_faction_state().brazen_fury_shooting_snapshot

    @_brazen_fury_shooting_snapshot.setter
    def _brazen_fury_shooting_snapshot(self, value) -> None:
        self._ensure_faction_state().brazen_fury_shooting_snapshot = value

    @property
    def _horde_move_shooting_snapshot(self):
        return self._ensure_faction_state().horde_move_shooting_snapshot

    @_horde_move_shooting_snapshot.setter
    def _horde_move_shooting_snapshot(self, value) -> None:
        self._ensure_faction_state().horde_move_shooting_snapshot = value

    @property
    def _unhinged_vengeance_shooting_snapshot(self):
        return self._ensure_faction_state().unhinged_vengeance_shooting_snapshot

    @_unhinged_vengeance_shooting_snapshot.setter
    def _unhinged_vengeance_shooting_snapshot(self, value) -> None:
        self._ensure_faction_state().unhinged_vengeance_shooting_snapshot = value

    @property
    def _blistering_assault_shooting_snapshot(self):
        return self._ensure_faction_state().blistering_assault_shooting_snapshot

    @_blistering_assault_shooting_snapshot.setter
    def _blistering_assault_shooting_snapshot(self, value) -> None:
        self._ensure_faction_state().blistering_assault_shooting_snapshot = value

    @property
    def _aggressive_leader_beast_shooting_snapshot(self):
        return self._ensure_faction_state().aggressive_leader_beast_shooting_snapshot

    @_aggressive_leader_beast_shooting_snapshot.setter
    def _aggressive_leader_beast_shooting_snapshot(self, value) -> None:
        self._ensure_faction_state().aggressive_leader_beast_shooting_snapshot = value

    @property
    def _guns_blazing_shooting_targets(self):
        return self._ensure_faction_state().guns_blazing_shooting_targets

    @_guns_blazing_shooting_targets.setter
    def _guns_blazing_shooting_targets(self, value) -> None:
        self._ensure_faction_state().guns_blazing_shooting_targets = value

    @property
    def _frenzy_shooting_targets(self):
        return self._ensure_faction_state().frenzy_shooting_targets

    @_frenzy_shooting_targets.setter
    def _frenzy_shooting_targets(self, value) -> None:
        self._ensure_faction_state().frenzy_shooting_targets = value

    @property
    def _frenzy_fight_targets(self):
        return self._ensure_faction_state().frenzy_fight_targets

    @_frenzy_fight_targets.setter
    def _frenzy_fight_targets(self, value) -> None:
        self._ensure_faction_state().frenzy_fight_targets = value

    @property
    def _pain_parasite_shooting_snapshot(self):
        return self._ensure_faction_state().pain_parasite_shooting_snapshot

    @_pain_parasite_shooting_snapshot.setter
    def _pain_parasite_shooting_snapshot(self, value) -> None:
        self._ensure_faction_state().pain_parasite_shooting_snapshot = value

    @property
    def _pain_parasite_fight_snapshot(self):
        return self._ensure_faction_state().pain_parasite_fight_snapshot

    @_pain_parasite_fight_snapshot.setter
    def _pain_parasite_fight_snapshot(self, value) -> None:
        self._ensure_faction_state().pain_parasite_fight_snapshot = value

    @property
    def _repair_barge_shooting_snapshot(self):
        return self._ensure_faction_state().repair_barge_shooting_snapshot

    @_repair_barge_shooting_snapshot.setter
    def _repair_barge_shooting_snapshot(self, value) -> None:
        self._ensure_faction_state().repair_barge_shooting_snapshot = value

    @property
    def _repair_barge_fight_snapshot(self):
        return self._ensure_faction_state().repair_barge_fight_snapshot

    @_repair_barge_fight_snapshot.setter
    def _repair_barge_fight_snapshot(self, value) -> None:
        self._ensure_faction_state().repair_barge_fight_snapshot = value



    @property
    def ruleset_bundle(self) -> RulesetBundle | None:
        return self._ruleset_bundle

    @ruleset_bundle.setter
    def ruleset_bundle(self, bundle: RulesetBundle) -> None:
        if bundle is None:
            raise ValueError("Ruleset bundle cannot be None.")
        existing = getattr(self, "_ruleset_bundle", None)
        if existing is not None and existing != bundle:
            allow_replace = getattr(existing, "is_placeholder", lambda: False)()
            has_events = bool(getattr(getattr(self, "event_log", None), "events", []))
            if not allow_replace or has_events:
                raise ValueError("Ruleset bundle already set for this game.")
        self._ruleset_bundle = bundle

    def get_ruleset_context(self) -> dict:
        bundle = getattr(self, "ruleset_bundle", None)
        if bundle is None:
            return {}
        to_dict = getattr(bundle, "to_dict", None)
        if callable(to_dict):
            return dict(to_dict() or {})
        return {}

































































































































































































    def add_command(self, command: str) -> None:
        """Add a command to the game."""
        self.commands.append(command)
















































































    def get_winner(self) -> Player | None:
        return game_scoring.get_winner(self)

    def get_loser(self) -> Player | None:
        return game_scoring.get_loser(self)

    def get_state(self) -> Dict[str, Any]:
        return game_serialization.get_state(self)

    def save_snapshot(self) -> dict:
        return game_serialization.save_snapshot(self)

    @staticmethod
    def load_snapshot(snapshot: dict) -> "Game":
        return game_serialization.load_snapshot(snapshot)

    ###########################################################################
    # Charge Phase
    ###########################################################################































    ###########################################################################
    # Fight Phase
    ###########################################################################






    ###########################################################################
    ### Reserves System
    ###########################################################################
