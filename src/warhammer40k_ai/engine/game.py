from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
import html
import re
import logging
import copy
import math
from .event.system import EventSystem
from .event_log import DeterministicEventLog
from ..battlefield.map import Map, Objective
from .mission_cards import PrimaryMissionCard, SecondaryMissionCard
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
    CMD_SELECT_MISSION,
    CMD_SET_DEPLOYMENT_WAITING,
)
from .decisions import CandidateAction, DecisionOption, DecisionQueue, DecisionRequest, DecisionResult
from .decision_kinds import (
    DECISION_CHOOSE_MISSION,
    DECISION_CHOOSE_PLEDGE,
    DECISION_CONFIRM_YES_NO,
    DECISION_DISEMBARK,
    DECISION_DECLARE_SHOTS,
    DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
    DECISION_CHOOSE_QUARRY,
    DECISION_CHOOSE_CHIVALRIC_OATH,
    DECISION_CHOOSE_START_OF_BATTLE_KEYWORD,
    DECISION_MOVE_UNIT,
    DECISION_ALLOCATE_DAMAGE,
    DECISION_SELECT_SETUP_REACTIVE_TARGET,
    DECISION_SELECT_TARGET_MODEL,
    DECISION_SELECT_OVERWATCH_SHOOTER,
    DECISION_SELECT_REVERBERATING_SUMMONS_UNIT,
)
from .random_source import RandomSource
from .decision_controller import DecisionController, DecisionControllerHub
from .decision_record import DecisionRecordStore
from .ruleset import RulesetBundle
from .tier1_plan import Tier1Plan, build_heuristic_tier1_plan
from .tier2_orchestrator import Tier2TaskBundle, build_tier2_task_bundle
from .time_manager import TimeManager
from .movement_intent import MovementIntent
from .movement_solver import generate_move_unit_candidates
from .path_witness import PathWitnessStore
from .dice_rolls import DiceRollManager
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
from .game_mixins import (
    GameMissionsScoringActionsMixin,
    GamePhaseHandlersMixin,
    GameReactiveDecisionsMixin,
    GameSetupDeploymentReservesMixin,
    GameShootingFightHandlersMixin,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..roster.army_muster import ArmyMusterRequest

class Game(
    GameSetupDeploymentReservesMixin,
    GameMissionsScoringActionsMixin,
    GameReactiveDecisionsMixin,
    GameShootingFightHandlersMixin,
    GamePhaseHandlersMixin,
):
    def __init__(
        self,
        battlefield: Battlefield,
        players: List[Player] | None = None,
        *,
        ruleset_bundle: RulesetBundle | None = None,
        ruleset_id: str | None = None,
        dataslate_id: str | None = None,
        points_id: str | None = None,
    ):
        self.battlefield = battlefield
        # Avoid mutable default arg: always create a fresh list per Game instance.
        self.players = list(players) if players else []
        self.turn = 1
        self.current_player_index = 0
        self.map = Map(battlefield.width, battlefield.height)
        self.event_system = EventSystem()
        self.event_log = DeterministicEventLog()
        self.event_log.attach(self)
        self.decision_controller_hub = DecisionControllerHub(self)
        self.decision_controller_hub.attach()
        self.decision_record_store = DecisionRecordStore(self)
        self._tier1_turn_plans: dict[tuple[int, str], Tier1Plan] = {}
        self._tier2_task_bundles: dict[tuple[int, str], Tier2TaskBundle] = {}
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
                ruleset_id=ruleset_id,
                dataslate_id=dataslate_id,
                points_id=points_id,
            )
        else:
            override = RulesetBundle.from_values(
                ruleset_id=ruleset_id,
                dataslate_id=dataslate_id,
                points_id=points_id,
            )
            if (
                (ruleset_id or dataslate_id or points_id)
                and ruleset_bundle != override
            ):
                raise ValueError("Ruleset bundle values conflict with explicit ids.")
        self.ruleset_bundle = ruleset_bundle
        self.roll_manager = DiceRollManager()
        self.attack_manager = AttackResolutionManager()
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
        for p in self.players:
            p.set_game(self)

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
        # Temporary Shadow of Chaos zone overrides (e.g., Impossible Eclipse).
        self._shadow_of_chaos_zone_overrides: Dict[str, set[str]] = {}
        # Corrupt Realspace: allow sticky break only at start/end of turn.
        self._corrupt_realspace_check: bool = False
        # Return-on-death pending returns (processed at end of the phase they were destroyed in)
        self._phoenix_gem_pending: List[Dict[str, Any]] = []
        # World Eaters: Blood Surge shooting snapshots (attacker -> {target: model_count})
        self._blood_surge_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        # World Eaters: Brazen Fury shooting snapshots (attacker -> {target: model_count})
        self._brazen_fury_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        # Horde Move shooting snapshots (attacker -> {target: model_count})
        self._horde_move_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        # Leagues of Votann: Unhinged Vengeance snapshots (attacker -> {target: tracked_model_wounds})
        self._unhinged_vengeance_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        # CSM: Guns Blazing trigger snapshots (attacker -> [reactive shooters])
        self._guns_blazing_shooting_targets: Dict['Unit', List['Unit']] = {}
        # World Eaters: Frenzy (Helbrute) target snapshots (attacker -> [targets])
        self._frenzy_shooting_targets: Dict['Unit', List['Unit']] = {}
        self._frenzy_fight_targets: Dict['Unit', List['Unit']] = {}
        # Drukhari: Pain Parasite snapshots (attacker -> {target: model_count})
        self._pain_parasite_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        self._pain_parasite_fight_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        # Optional in-engine army mustering requests (player1/player2) for setup phase.
        self.army_muster_requests: Dict[str, Any] = {}
        self.entity_registry = EntityRegistry()
        self.rebuild_entity_registry()

    def add_decision_controller(self, controller: DecisionController) -> None:
        if controller is None:
            return
        hub = getattr(self, "decision_controller_hub", None)
        if hub is None:
            return
        hub.add_controller(controller)

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
        return {
            "ruleset_id": getattr(bundle, "ruleset_id", None),
            "dataslate_id": getattr(bundle, "dataslate_id", None),
            "points_id": getattr(bundle, "points_id", None),
        }

    def _current_battle_round(self) -> int:
        getter = getattr(self, "get_battle_round", None)
        if callable(getter):
            return int(getter() or 0)
        return int(getattr(self, "turn", 0) or 0)

    def _tier1_plan_key(self, player_id: str) -> tuple[int, str]:
        return (self._current_battle_round(), str(player_id or ""))

    def get_or_create_tier1_plan(self, player_id: str) -> Tier1Plan:
        pid = str(player_id or "")
        if not pid:
            raise ValueError("Tier1 plan requires player_id.")
        if not hasattr(self, "_tier1_turn_plans") or not isinstance(self._tier1_turn_plans, dict):
            self._tier1_turn_plans = {}
        key = self._tier1_plan_key(pid)
        existing = self._tier1_turn_plans.get(key)
        if existing is not None:
            return existing
        plan = build_heuristic_tier1_plan(self, pid)
        self._tier1_turn_plans[key] = plan
        return plan

    def get_or_create_tier2_task_bundle(self, player_id: str) -> Tier2TaskBundle:
        pid = str(player_id or "")
        if not pid:
            raise ValueError("Tier2 task bundle requires player_id.")
        if not hasattr(self, "_tier2_task_bundles") or not isinstance(self._tier2_task_bundles, dict):
            self._tier2_task_bundles = {}
        key = self._tier1_plan_key(pid)
        existing = self._tier2_task_bundles.get(key)
        if existing is not None:
            return existing
        plan = self.get_or_create_tier1_plan(pid)
        bundle = build_tier2_task_bundle(self, plan)
        self._tier2_task_bundles[key] = bundle
        return bundle

    def _install_default_event_subscribers(self) -> None:
        """Install non-UI rule subscribers that operate off the event system."""
        registry = RuleRegistry(build_default_rule_providers())
        registry.apply(self)
        self.rule_registry = registry

    def _on_unit_destroyed_monarch_of_the_hunt(self, unit=None, **_kwargs) -> None:
        if unit is None or not bool(getattr(self, "is_authoritative", True)):
            return

        def _resolve_player_army(player):
            if player is None:
                return None
            getter = getattr(player, "get_army", None)
            if callable(getter):
                return getter()
            return getattr(player, "army", None)

        def _resolve_unit_parent_army(source_unit):
            if source_unit is None:
                return None
            getter = getattr(source_unit, "get_parent_army", None)
            if callable(getter):
                return getter()
            return getattr(source_unit, "parent_army", None)

        def _unit_is_alive_or_unknown(source_unit) -> bool:
            if source_unit is None:
                return False
            alive_fn = getattr(source_unit, "is_alive", None)
            if callable(alive_fn):
                return bool(alive_fn())
            alive_attr = getattr(source_unit, "is_alive", None)
            if alive_attr is None:
                return True
            return bool(alive_attr)

        destroyed_army = _resolve_unit_parent_army(unit)
        destroyed_owner = getattr(destroyed_army, "player", None)

        def _handle_quarry_repick(rule_getter, attr_name: str, request_builder) -> None:
            for player in list(getattr(self, "players", []) or []):
                army = _resolve_player_army(player)
                if army is None:
                    continue
                for source_unit in list(getattr(army, "units", []) or []):
                    rule = rule_getter(source_unit)
                    if not rule:
                        continue
                    quarry_ids = getattr(source_unit, attr_name, None)
                    if not quarry_ids:
                        continue
                    unit_id = getattr(unit, "_id", None)
                    if unit_id is None or unit_id not in quarry_ids:
                        continue

                    alive_ids = set()
                    enemy_army = _resolve_player_army(destroyed_owner)
                    if enemy_army is not None:
                        by_id = {getattr(u2, "_id", None): u2 for u2 in list(getattr(enemy_army, "units", []) or [])}
                        for qid in list(quarry_ids):
                            u2 = by_id.get(qid)
                            if u2 is None:
                                continue
                            if _unit_is_alive_or_unknown(u2):
                                alive_ids.add(qid)
                    setattr(source_unit, attr_name, alive_ids)

                    if not alive_ids:
                        req = request_builder(
                            game=self,
                            source_unit=source_unit,
                            enemy_units=list(self.get_enemy_units(player)),
                            ability_name=str(rule.get("source", "") or "") or None,
                        )
                        request_decision = getattr(self, "request_decision", None)
                        if req is not None and callable(request_decision):
                            request_decision(req)

        def _monarch_rule(u):
            finder = getattr(u, "_find_ability_with_patterns", None)
            if not callable(finder):
                return None
            found, _ = finder(["monarch of the hunt"])
            if not found:
                return None
            return {"source": "Monarch of the Hunt"}

        def _monarch_request_builder(game, source_unit, enemy_units, ability_name=None):
            army = _resolve_unit_parent_army(source_unit)
            if army is None:
                return None
            build_request = getattr(army, "_build_monarch_of_the_hunt_request", None)
            if not callable(build_request):
                return None
            return build_request(
                game=game,
                source_unit=source_unit,
                enemy_units=enemy_units,
                ability_name=ability_name,
            )

        _handle_quarry_repick(_monarch_rule, "_monarch_of_the_hunt_quarry_ids", _monarch_request_builder)

        def _methodical_rule(u):
            getter = getattr(u, "get_victim_selection_rule", None)
            return getter() if callable(getter) else None

        def _methodical_request_builder(game, source_unit, enemy_units, ability_name=None):
            army = _resolve_unit_parent_army(source_unit)
            if army is None:
                return None
            build_request = getattr(army, "_build_methodical_destruction_request", None)
            if not callable(build_request):
                return None
            return build_request(
                game=game,
                source_unit=source_unit,
                enemy_units=enemy_units,
                ability_name=ability_name,
            )

        _handle_quarry_repick(_methodical_rule, "_methodical_destruction_victim_ids", _methodical_request_builder)

        def _prey_rule(u):
            getter = getattr(u, "get_prey_selection_rule", None)
            rule = getter() if callable(getter) else None
            if not rule:
                return None
            if not bool(rule.get("repick_on_destroyed", False)):
                return None
            return rule

        def _prey_request_builder(game, source_unit, enemy_units, ability_name=None):
            army = _resolve_unit_parent_army(source_unit)
            if army is None:
                return None
            get_rule = getattr(source_unit, "get_prey_selection_rule", None)
            rule = get_rule() if callable(get_rule) else None
            build_request = getattr(army, "_build_prey_selection_request", None)
            if not callable(build_request):
                return None
            return build_request(
                game=game,
                source_unit=source_unit,
                enemy_units=enemy_units,
                rule=rule,
            )

        _handle_quarry_repick(_prey_rule, "_prey_selection_prey_ids", _prey_request_builder)

    def rebuild_entity_registry(self) -> None:
        rebuild_registry_from_game(self.entity_registry, self)

    def refresh_rule_subscribers(self) -> None:
        """Re-apply rule providers after armies are updated."""
        registry = getattr(self, "rule_registry", None)
        if registry is None:
            registry = RuleRegistry(build_default_rule_providers())
            self.rule_registry = registry
        registry.apply(self)
        self.ability_lifecycle.refresh()

    def _on_unit_set_up_lifecycle(self, unit=None, **_kwargs) -> None:
        self.ability_lifecycle.on_unit_set_up(unit=unit)

    def _on_unit_destroyed_lifecycle(self, unit=None, **_kwargs) -> None:
        self.ability_lifecycle.on_unit_destroyed(unit=unit)

    def _on_unit_state_changed_lifecycle(self, unit=None, **_kwargs) -> None:
        self.ability_lifecycle.on_unit_state_changed(unit=unit)

    def _apply_pall_of_despair_forced_tests(self, current_player, tested_ids: set[str]) -> None:
        if current_player is None:
            return
        from ..rules.shadow_form import shadow_form_sources_with_active_key, KEY_PALL
        from ..utility.aura_utils import unit_within_range_of_unit

        def _get_army(player):
            getter = getattr(self, "_get_player_army", None)
            if callable(getter):
                return getter(player)
            if player is None:
                return None
            getter = getattr(player, "get_army", None)
            if callable(getter):
                return getter()
            return getattr(player, "army", None)

        enemies = [p for p in (self.players or []) if p is not current_player]
        current_army = _get_army(current_player)
        if current_army is None:
            return
        for enemy_player in enemies:
            army = _get_army(enemy_player)
            if army is None:
                continue
            sources = shadow_form_sources_with_active_key(army, KEY_PALL, game=self)
            if not sources:
                continue
            for unit in list(current_army.units):
                if unit is None:
                    continue
                if not unit.is_alive():
                    continue
                if not bool(getattr(unit, "deployed", True)):
                    continue
                uid = get_entity_id(unit)
                if uid in tested_ids:
                    continue
                if not unit.is_below_starting_strength():
                    continue
                for source in sources:
                    if unit_within_range_of_unit(source, unit, 9.0, use_attached_aggregate=True):
                        unit.take_battle_shock_test(self.turn)
                        tested_ids.add(uid)
                        break

    def _apply_harbingers_dismay_forced_tests(self, current_player, tested_ids: set[str]) -> None:
        if current_player is None:
            return
        from ..rules.harbingers_of_dread import DISMAY
        from ..utility.aura_utils import unit_within_range_of_unit

        def _get_army(player):
            getter = getattr(self, "_get_player_army", None)
            if callable(getter):
                return getter(player)
            if player is None:
                return None
            getter = getattr(player, "get_army", None)
            if callable(getter):
                return getter()
            return getattr(player, "army", None)

        enemies = [p for p in (self.players or []) if p is not current_player]
        current_army = _get_army(current_player)
        if current_army is None:
            return

        for enemy_player in enemies:
            army = _get_army(enemy_player)
            if army is None:
                continue
            mgr = getattr(army, "harbingers_of_dread", None)
            if mgr is None or not getattr(mgr, "_army_has_harbingers", lambda: False)():
                continue
            if not mgr.is_dread_active(DISMAY.key):
                continue
            aura_range = float(mgr.get_aura_range())
            sources = [u for u in list(army.units) if mgr._unit_is_valid_source(u)]
            if not sources:
                continue

            for unit in list(current_army.units):
                if unit is None:
                    continue
                if not unit.is_alive():
                    continue
                if not bool(getattr(unit, "deployed", True)):
                    continue
                uid = get_entity_id(unit)
                if uid in tested_ids:
                    continue
                if not unit.is_below_starting_strength():
                    continue

                for source in sources:
                    if unit_within_range_of_unit(source, unit, aura_range, use_attached_aggregate=True):
                        unit.take_battle_shock_test(self.turn)
                        tested_ids.add(uid)
                        break

    def _on_battle_shock_test_resolved_shadow_form(self, unit=None, passed: bool = False, **_kwargs) -> None:
        if unit is None or passed:
            return
        from ..rules.shadow_form import shadow_form_sources_with_active_key, KEY_PALL, apply_pall_of_despair_heal
        from ..utility.aura_utils import unit_within_range_of_unit

        def _get_army(player):
            getter = getattr(self, "_get_player_army", None)
            if callable(getter):
                return getter(player)
            if player is None:
                return None
            getter = getattr(player, "get_army", None)
            if callable(getter):
                return getter()
            return getattr(player, "army", None)

        is_below_starting = True
        fn = getattr(unit, "is_below_starting_strength", None)
        if callable(fn):
            try:
                is_below_starting = bool(fn())
            except TypeError:
                is_below_starting = True
        if not is_below_starting:
            return

        get_parent_army = getattr(unit, "get_parent_army", None)
        unit_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)

        for player in list(getattr(self, "players", []) or []):
            army = _get_army(player)
            if army is None or army is unit_army:
                continue
            sources = shadow_form_sources_with_active_key(army, KEY_PALL, game=self)
            if not sources:
                continue
            for source in sources:
                if unit_within_range_of_unit(source, unit, 9.0, use_attached_aggregate=True):
                    apply_pall_of_despair_heal(source)

    def _on_battle_shock_test_resolved_harbingers(self, unit=None, passed: bool = False, **_kwargs) -> None:
        if unit is None or passed:
            return
        is_below_half = False
        fn = getattr(unit, "is_below_half_strength", None)
        if callable(fn):
            try:
                is_below_half = bool(fn())
            except TypeError:
                is_below_half = False
        if not is_below_half:
            return

        from ..rules.harbingers_of_dread import DELIRIUM
        from ..utility.aura_utils import unit_within_range_of_unit
        from ..utility.dice import get_roll

        def _get_army(player):
            getter = getattr(self, "_get_player_army", None)
            if callable(getter):
                return getter(player)
            if player is None:
                return None
            getter = getattr(player, "get_army", None)
            if callable(getter):
                return getter()
            return getattr(player, "army", None)

        get_parent_army = getattr(unit, "get_parent_army", None)
        unit_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)

        for player in list(getattr(self, "players", []) or []):
            army = _get_army(player)
            if army is None or army is unit_army:
                continue
            mgr = getattr(army, "harbingers_of_dread", None)
            if mgr is None or not getattr(mgr, "_army_has_harbingers", lambda: False)():
                continue
            if not mgr.is_dread_active(DELIRIUM.key):
                continue
            aura_range = float(mgr.get_aura_range())
            sources = [u for u in list(getattr(army, "units", []) or []) if mgr._unit_is_valid_source(u)]
            if not sources:
                continue

            for source in sources:
                if unit_within_range_of_unit(source, unit, aura_range, use_attached_aggregate=True):
                    mortal = int(get_roll("D3") or 0)
                    if mortal > 0:
                        unit._apply_mortal_wounds_to_unit(unit, mortal, game_map=getattr(self, "map", None))
                    return

    def _on_battle_shock_test_resolved_maggot_maws(self, unit=None, passed: bool = False, **_kwargs) -> None:
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return
        pending = sr.get("maggot_maws_pending")
        if not isinstance(pending, dict):
            return
        sr.pop("maggot_maws_pending", None)
        unit.special_rules = sr

        from ..utility.dice import get_roll
        from ..utility.event_bus import append_action, append_dice

        roll_d6 = int(get_roll("D6") or 0)
        mortal = 0
        roll_d3 = None
        if roll_d6 >= 3:
            roll_d3 = int(get_roll("D3") or 0)
            mortal = int(roll_d3 or 0)
        if mortal > 0:
            unit._apply_mortal_wounds_to_unit(unit, mortal, game_map=getattr(self, "map", None))

        ability_name = str(pending.get("ability_name", "") or "Maggot Maws").strip() or "Maggot Maws"
        owner_id = str(pending.get("owner_id", "") or "")
        player = self._resolve_player_by_id(owner_id) if owner_id else None
        if player is not None:
            desc = f"{ability_name}: roll D6={roll_d6}"
            if roll_d3 is not None:
                desc = f"{desc}, D3={int(roll_d3)}"
            append_dice(player, f"{desc}.")
            if mortal > 0:
                append_action(
                    player,
                    f"{ability_name}: {getattr(unit, 'name', 'Unit')} suffers {int(mortal)} mortal wounds.",
                )
            else:
                append_action(
                    player,
                    f"{ability_name}: {getattr(unit, 'name', 'Unit')} suffers no mortal wounds.",
                )

    def _apply_reanimation_protocols_end_command_phase(self, current_player) -> None:
        if current_player is None:
            raise RuntimeError("Reanimation protocols require a current player.")
        army = current_player.get_army()
        if army is None:
            raise RuntimeError("Reanimation protocols require an army.")
        game_map = getattr(self, "map", None)
        provider = getattr(game_map, "reanimation_allocation_provider", None) if game_map is not None else None
        is_human = bool(getattr(current_player, "has_control", lambda: False)())

        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            root_fn = getattr(unit, "get_attached_unit_root", None)
            root = root_fn() if callable(root_fn) else unit
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)

            if not getattr(root, "deployed", True):
                continue
            if str(getattr(root, "reserve_status", "deployed")) != "deployed":
                continue
            in_reserves = False
            fn = getattr(root, "is_in_reserves", None)
            if callable(fn):
                in_reserves = bool(fn())
            else:
                in_reserves = str(getattr(root, "reserve_status", "deployed")) in ("reserves", "strategic_reserves")
            if in_reserves:
                continue
            if bool(getattr(root, "embarked_in", None)) or bool(getattr(root, "is_embarked", False)):
                continue
            is_alive_fn = getattr(root, "is_alive", None)
            if callable(is_alive_fn):
                if not is_alive_fn():
                    continue
            elif not bool(getattr(root, "is_alive", True)):
                continue
            has_reanimate = getattr(root, "attached_unit_has_reanimation_protocols", None)
            if not callable(has_reanimate) or not has_reanimate():
                continue

            d3 = int(get_roll("D3") or 0)
            if d3 <= 0:
                continue
            root.apply_reanimation_protocols(d3, game_map=game_map, is_human=is_human, provider=provider)

    def _apply_command_phase_regain_wounds(self, current_player) -> None:
        if current_player is None:
            raise RuntimeError("Command phase regain wounds requires a current player.")
        army = current_player.get_army()
        if army is None:
            raise RuntimeError("Command phase regain wounds requires an army.")

        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            if not unit.is_alive():
                continue
            if not bool(getattr(unit, "deployed", True)):
                continue
            if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                continue
            in_reserves = False
            fn = getattr(unit, "is_in_reserves", None)
            if callable(fn):
                in_reserves = bool(fn())
            else:
                in_reserves = str(getattr(unit, "reserve_status", "deployed")) in ("reserves", "strategic_reserves")
            if in_reserves:
                continue

            models = list(getattr(unit, "models", []) or [])
            if not models:
                continue
            single_model_regain_texts: set[str] = set()
            for ab in list(getattr(unit, "possible_abilities", []) or []):
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
                text = str(desc or "")
                low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
                if "command phase" not in low or "regains" not in low or "wounds" not in low:
                    continue
                m_single = re.search(r"one model in this unit regains up to (\d+|d3) lost wounds", low)
                if not m_single:
                    continue
                single_model_regain_texts.add(low)
                token = str(m_single.group(1) or "").strip().lower()
                if token == "d3":
                    amount = int(get_roll("D3") or 0)
                else:
                    amount = int(token or 0)
                if amount <= 0:
                    continue
                alive_models = [m for m in list(models or []) if bool(getattr(m, "is_alive", True))]
                if not alive_models:
                    continue
                damaged = []
                for model in list(alive_models):
                    base_wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)) or 0)
                    current_wounds = int(getattr(model, "wounds", 0) or 0)
                    if base_wounds > current_wounds:
                        damaged.append((base_wounds - current_wounds, model, base_wounds, current_wounds))
                if not damaged:
                    continue
                damaged.sort(key=lambda item: item[0], reverse=True)
                _missing, target_model, base_wounds, current_wounds = damaged[0]
                target_model.wounds = min(base_wounds, current_wounds + amount)
            for model in models:
                if not bool(getattr(model, "is_alive", True)):
                    continue
                for ab in list(getattr(unit, "possible_abilities", []) or []):
                    desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
                    text = str(desc or "")
                    low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
                    if low in single_model_regain_texts:
                        continue
                    if "command phase" not in low or "regains" not in low or "wounds" not in low:
                        continue
                    # Targeted support abilities (e.g., "select one friendly ... that model regains ...")
                    # are handled through explicit decision flows and should not self-heal here.
                    if "select one friendly" in low and "that model regains" in low:
                        continue
                    if (
                        "that model regains" in low
                        and "this model regains" not in low
                        and "the bearer regains" not in low
                        and "this unit regains" not in low
                    ):
                        continue
                    m = re.search(r"regains\s+(\d+|d3)", low)
                    if not m:
                        continue
                    token = m.group(1)
                    if token == "d3":
                        amount = int(get_roll("D3") or 0)
                    else:
                        amount = int(token)
                    if amount <= 0:
                        continue
                    base_wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)) or 0)
                    current_wounds = int(getattr(model, "wounds", 0) or 0)
                    model.wounds = min(base_wounds, current_wounds + amount)

    def _maybe_prompt_shadow_in_the_warp(self) -> None:
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            army = player.get_army()
            if army is None:
                continue
            mgr = getattr(army, "shadow_in_the_warp", None)
            if mgr is None:
                continue
            if not mgr.can_use_now(game=self, player=player):
                continue
            ctx = {
                "ability_name": "Shadow in the Warp",
                "phase": "Command phase",
            }
            message = "Use Shadow in the Warp? (Once per battle)"
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="shadow_in_the_warp",
                ability_name="Shadow in the Warp",
                message=message,
                context=ctx,
            )

    def _maybe_prompt_daemon_primarch_slaanesh(self, current_player) -> None:
        if current_player is None:
            return
        for player in list(getattr(self, "players", []) or []):
            if player is None or player is current_player:
                continue
            army = self._get_player_army(player)
            if army is None:
                continue
            mgr = getattr(army, "daemon_primarch_slaanesh", None)
            if mgr is None:
                continue
            mgr.on_opponent_command_phase_start(current_player, game=self)
            publish = getattr(self.event_system, "publish", None)
            if callable(publish):
                publish(
                    "daemon_primarch_slaanesh_prompt",
                    player=player,
                    opponent_player=current_player,
                    game=self,
                )

    def _maybe_prompt_csm_warmaster(self, current_player) -> None:
        if current_player is None:
            return
        army = self._get_player_army(current_player)
        if army is None:
            return
        mgr = getattr(army, "csm_warmaster", None)
        if mgr is None:
            return
        mgr.on_command_phase_start(current_player, game=self)
        publish = getattr(self.event_system, "publish", None)
        if callable(publish):
            publish("csm_warmaster_prompt", player=current_player, game=self)

    def _maybe_prompt_waaagh(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Waaagh prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Waaagh prompt requires an army.")
        mgr = getattr(army, "waaagh", None)
        if mgr is None:
            return
        if not mgr.can_call_now(game=self, player=player):
            return
        ctx = {
            "ability_name": "Waaagh!",
            "phase": "Command phase",
        }
        message = "Call Waaagh!? (Once per battle)"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="waaagh",
            ability_name="Waaagh!",
            message=message,
            context=ctx,
        )

    def _maybe_prompt_combat_doctrines(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Combat Doctrines prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Combat Doctrines prompt requires an army.")
        mgr = getattr(army, "combat_doctrines", None)
        if mgr is None:
            return
        if not getattr(mgr, "can_select_now", lambda **_k: False)(game=self):
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        options = list(getattr(mgr, "get_available_doctrines", lambda: [])() or [])
        if not options:
            return
        from ..engine.decision_kinds import DECISION_CHOOSE_COMBAT_DOCTRINE
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id
        army_id = get_entity_id(army)
        battle_round = int(getattr(self, "turn", 0) or 0)
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_COMBAT_DOCTRINE:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("army_id", "")) == str(army_id) and int(ctx.get("battle_round", battle_round) or battle_round) == battle_round:
                    return
        req_options = [
            DecisionOption.create(
                "None",
                payload={"skip": True, "summary": "Do not select a Combat Doctrine this Command phase.", "army_id": army_id},
            )
        ]
        for opt in options:
            key = getattr(opt, "key", None)
            if not key:
                continue
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or getattr(opt, "effect", "")
            req_options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                )
            )
        if not req_options:
            return
        req = DecisionRequest.create(
            DECISION_CHOOSE_COMBAT_DOCTRINE,
            "Select Combat Doctrine.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"army_id": army_id, "battle_round": battle_round},
        )
        if hasattr(self, "request_decision"):
            self.request_decision(req)

    def _maybe_prompt_grand_coven(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Grand Coven prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Grand Coven prompt requires an army.")
        mgr = getattr(army, "thousand_sons_detachments", None)
        if mgr is None or not getattr(mgr, "can_select_grand_coven", lambda **_k: False)(game=self):
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        options = list(getattr(mgr, "get_available_grand_coven_abilities", lambda: [])() or [])
        if not options:
            return
        from ..engine.decision_kinds import DECISION_CHOOSE_GRAND_COVEN
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id
        army_id = get_entity_id(army)
        battle_round = int(getattr(self, "turn", 0) or 0)
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_GRAND_COVEN:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("army_id", "")) == str(army_id) and int(ctx.get("battle_round", battle_round) or battle_round) == battle_round:
                    return
        req_options = [
            DecisionOption.create(
                "None",
                payload={"skip": True, "summary": "Do not select a Kindred Sorcery ability this Command phase.", "army_id": army_id},
            )
        ]
        for opt in options:
            key = getattr(opt, "key", None)
            if not key:
                continue
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or ""
            req_options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                )
            )
        if not req_options:
            return
        req = DecisionRequest.create(
            DECISION_CHOOSE_GRAND_COVEN,
            "Select a Kindred Sorcery ability.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"army_id": army_id, "battle_round": battle_round},
        )
        if hasattr(self, "request_decision"):
            self.request_decision(req)

    def _maybe_prompt_combat_drugs(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Combat Drugs prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Combat Drugs prompt requires an army.")
        mgr = getattr(army, "drukhari_detachments", None)
        if mgr is None or not getattr(mgr, "can_select_combat_drugs", lambda **_k: False)(game=self):
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        options = list(getattr(mgr, "get_available_combat_drugs", lambda: [])() or [])
        from ..engine.decision_kinds import DECISION_CHOOSE_COMBAT_DRUGS
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id
        army_id = get_entity_id(army)
        battle_round = int(getattr(self, "turn", 0) or 0)
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_COMBAT_DRUGS:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("army_id", "")) == str(army_id) and int(ctx.get("battle_round", battle_round) or battle_round) == battle_round:
                    return
        req_options = [
            DecisionOption.create(
                "Roll 2D6 (randomly select two)",
                payload={
                    "choice_key": "ROLL",
                    "random": True,
                    "summary": "Apply both results; duplicates have no additional effect.",
                    "army_id": army_id,
                },
            )
        ]
        for opt in options:
            key = getattr(opt, "key", None)
            if not key:
                continue
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or getattr(opt, "effect", "")
            req_options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                )
            )
        if not req_options:
            return
        req = DecisionRequest.create(
            DECISION_CHOOSE_COMBAT_DRUGS,
            "Select Combat Drugs.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"army_id": army_id, "battle_round": battle_round},
        )
        if hasattr(self, "request_decision"):
            self.request_decision(req)

    def _maybe_prompt_power_from_pain_command_phase(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Power from Pain prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Power from Pain prompt requires an army.")
        mgr = getattr(army, "power_from_pain", None)
        if mgr is None:
            return
        if not mgr.has_command_phase_action(game=self, player=player):
            return
        ctx = {
            "ability_name": "Power from Pain",
            "phase": "Command phase",
        }
        message = "Use Power from Pain? (Command phase)"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="power_from_pain_command",
            ability_name="Power from Pain",
            message=message,
            context=ctx,
            instance_key="command_phase",
        )

    def _cleanup_movement_phase_visible_bonus(self, player=None, phase=None, *, kind: str) -> None:
        """Clear movement-phase hit/wound bonus markers at the start of the owner's Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        kind_key = str(kind or "").strip().lower()
        if kind_key not in ("hit", "wound"):
            return
        active_key = f"movement_phase_visible_{kind_key}_bonus_active"
        owner_key = f"movement_phase_visible_{kind_key}_bonus_owner"
        turn_key = f"movement_phase_visible_{kind_key}_bonus_turn"
        source_key = f"movement_phase_visible_{kind_key}_bonus_source"
        keyword_key = f"movement_phase_visible_{kind_key}_bonus_keyword"
        value_key = f"movement_phase_visible_{kind_key}_bonus_value"
        model_key = f"movement_phase_visible_{kind_key}_bonus_model_id"
        clear_method = f"clear_movement_phase_visible_{kind_key}_bonus"
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Movement phase bonus cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Movement phase bonus cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get(owner_key, "") or "") != owner_id:
                    continue
                if sr.get(active_key):
                    clear_fn = getattr(unit, clear_method, None)
                    if callable(clear_fn):
                        clear_fn()
                    else:
                        for key in (
                            active_key,
                            owner_key,
                            turn_key,
                            source_key,
                            keyword_key,
                            value_key,
                            model_key,
                        ):
                            sr.pop(key, None)
                        unit.special_rules = sr

    def _maybe_prompt_end_of_opponent_turn_strategic_reserves(self, turn_ending_player=None) -> None:
        """Optional end-of-opponent-turn: remove eligible units to Strategic Reserves."""
        if turn_ending_player is None:
            return
        game_map = self.map
        if game_map is None:
            raise RuntimeError("Strategic reserves prompt requires a game map.")
        edge_zones_by_distance: dict[float, object] = {}

        for opp in list(self.players or []):
            if opp is None:
                raise RuntimeError("Strategic reserves prompt requires players.")
            if opp is turn_ending_player:
                continue
            army = opp.get_army()
            if army is None:
                raise RuntimeError(f"Strategic reserves prompt requires an army for {opp.name}.")

            eligible = []
            seen = set()
            for unit in list(army.units):
                root = unit.get_attached_unit_root()
                if root is None:
                    continue
                rid = get_entity_id(root)
                if rid in seen:
                    continue
                seen.add(rid)
                if not root.is_alive():
                    continue
                if not getattr(root, "deployed", False):
                    continue
                if str(getattr(root, "reserve_status", "deployed")) != "deployed":
                    continue
                if bool(getattr(root, "embarked_in", None)) or root.is_embarked:
                    continue
                ability = root.get_end_of_opponent_turn_strategic_reserves_ability()
                if not ability:
                    continue
                ability_key = str(ability.get("ability_key") or "opponent_turn_strategic_reserves").strip().lower()
                if ability.get("once_per_battle") and ability_key:
                    if root.has_used_unit_once_per_battle(ability_key):
                        continue
                engaged = False
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if not enemy.is_alive():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if game_map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
                if engaged:
                    continue
                min_edge_distance = float(ability.get("min_battlefield_edge_distance_horiz", 0) or 0)
                if min_edge_distance > 0:
                    try:
                        from shapely.geometry import box
                        from shapely.ops import unary_union
                    except Exception:
                        continue
                    edge_zone = edge_zones_by_distance.get(float(min_edge_distance))
                    if edge_zone is None:
                        try:
                            width = float(getattr(game_map, "width", 0.0) or 0.0)
                            height = float(getattr(game_map, "height", 0.0) or 0.0)
                        except Exception:
                            width = 0.0
                            height = 0.0
                        if width <= 0 or height <= 0:
                            continue
                        d = float(max(0.0, min_edge_distance))
                        left = box(0.0, 0.0, min(d, width), height)
                        right = box(max(0.0, width - d), 0.0, width, height)
                        bottom = box(0.0, 0.0, width, min(d, height))
                        top = box(0.0, max(0.0, height - d), width, height)
                        edge_zone = unary_union([left, right, bottom, top])
                        edge_zones_by_distance[float(min_edge_distance)] = edge_zone
                    try:
                        root_models = list(root.get_attached_unit_models() or [])
                    except Exception:
                        root_models = list(getattr(root, "models", []) or [])
                    root_models = [m for m in list(root_models or []) if bool(getattr(m, "is_alive", True))]
                    if not root_models:
                        continue
                    all_within_edge = True
                    for model in list(root_models or []):
                        base = getattr(model, "model_base", None)
                        if base is None:
                            all_within_edge = False
                            break
                        shape = None
                        try:
                            shape = base.get_base_shape()
                        except Exception:
                            shape = None
                        if shape is None or not edge_zone.covers(shape):
                            all_within_edge = False
                            break
                    if not all_within_edge:
                        continue
                min_enemy_distance = float(ability.get("min_enemy_distance_horiz", 0) or 0)
                if min_enemy_distance > 0:
                    from ..utility.aura_utils import horizontal_distance_between_bases_2d

                    too_close = False
                    try:
                        root_models = list(root.get_attached_unit_models() or [])
                    except Exception:
                        root_models = list(getattr(root, "models", []) or [])
                    root_models = [m for m in list(root_models or []) if bool(getattr(m, "is_alive", True))]
                    for enemy in list(game_map.get_enemy_units(root) or []):
                        if enemy is None or not enemy.is_alive():
                            continue
                        if not getattr(enemy, "deployed", True):
                            continue
                        try:
                            enemy_models = list(enemy.get_attached_unit_models() or [])
                        except Exception:
                            enemy_models = list(getattr(enemy, "models", []) or [])
                        enemy_models = [m for m in list(enemy_models or []) if bool(getattr(m, "is_alive", True))]
                        for model in list(root_models or []):
                            if too_close:
                                break
                            base_a = getattr(model, "model_base", None)
                            if base_a is None:
                                continue
                            for enemy_model in list(enemy_models or []):
                                base_b = getattr(enemy_model, "model_base", None)
                                if base_b is None:
                                    continue
                                dist = float(horizontal_distance_between_bases_2d(base_a, base_b))
                                if dist <= float(min_enemy_distance) + 1e-6:
                                    too_close = True
                                    break
                        if too_close:
                            break
                    if too_close:
                        continue
                eligible.append({"unit": root, "ability": ability})

            if not eligible:
                continue

            for entry in eligible:
                unit = entry.get("unit")
                ability = entry.get("ability") or {}
                if unit is None:
                    continue
                unit_id = maybe_entity_id(unit)
                ability_key = str(ability.get("ability_key") or "opponent_turn_strategic_reserves").strip().lower()
                ctx = {
                    "ability_name": ability.get("name", "") or "",
                    "unit": getattr(unit, "name", "") or "",
                    "phase": "End of opponent's turn",
                    "unit_id": unit_id,
                    "ability_key": ability_key,
                    "once_per_battle": bool(ability.get("once_per_battle")),
                }
                message = (
                    f"{getattr(unit, 'name', 'Unit')} can enter Strategic Reserves at the end of the opponent's turn.\n\n"
                    "Use this ability?"
                )
                self._queue_optional_ability_confirmation(
                    player=opp,
                    ability_key="opponent_turn_strategic_reserves",
                    ability_name=ctx["ability_name"] or "Strategic Reserves",
                    message=message,
                    context=ctx,
                    payload={"unit_id": unit_id, "ability_key": ability_key, "once_per_battle": bool(ability.get("once_per_battle"))},
                    instance_key=str(unit_id or ""),
                )

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def _resolve_phoenix_gem_wounds(self, model, spec: dict[str, Any]) -> int:
        base_wounds = self._coerce_int(
            getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)),
            0,
        )
        if base_wounds <= 0:
            base_wounds = 1

        wounds_spec = spec.get("wounds", "full")
        wounds = base_wounds
        if isinstance(wounds_spec, str):
            key = wounds_spec.strip().lower()
            if key == "full":
                wounds = base_wounds
            elif key == "d3":
                wounds = self._coerce_int(get_roll("D3"), 0)
            elif key == "d6":
                wounds = self._coerce_int(get_roll("D6"), 0)
            else:
                wounds = self._coerce_int(key, base_wounds)
        else:
            wounds = self._coerce_int(wounds_spec, base_wounds)

        if wounds <= 0:
            wounds = 1
        if wounds > base_wounds:
            wounds = base_wounds
        return wounds

    @staticmethod
    def _phoenix_gem_attach_model_to_unit(model, unit) -> None:
        set_parent = getattr(model, "set_parent_unit", None)
        if callable(set_parent):
            set_parent(unit)
            return
        if hasattr(model, "parent_unit"):
            model.parent_unit = unit

    @staticmethod
    def _phoenix_gem_set_model_wounds(model, wounds: int) -> None:
        if hasattr(model, "wounds"):
            model.wounds = int(wounds)
            return
        if hasattr(model, "_wounds"):
            model._wounds = int(wounds)

    @staticmethod
    def _phoenix_gem_restore_model_membership(unit, model) -> None:
        models_lost = getattr(unit, "models_lost", None)
        if isinstance(models_lost, list) and model in models_lost:
            models_lost.remove(model)

        models = getattr(unit, "models", None)
        if isinstance(models, list) and model not in models:
            models.append(model)

    @staticmethod
    def _phoenix_gem_restore_model_position(model, position) -> None:
        if position is None:
            return
        set_location = getattr(model, "set_location", None)
        if not callable(set_location):
            return
        if isinstance(position, (tuple, list)) and len(position) >= 3:
            set_location(*position[:4] if len(position) >= 4 else position[:3])

    @staticmethod
    def _phoenix_gem_refresh_unit_state(unit) -> None:
        invalidate = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()
        update_coherency = getattr(unit, "update_coherency", None)
        if callable(update_coherency):
            update_coherency()
        if hasattr(unit, "deployed"):
            unit.deployed = True
        if hasattr(unit, "reserve_status"):
            unit.reserve_status = "deployed"

    @staticmethod
    def _phoenix_gem_add_unit_to_map(game_map, unit) -> None:
        if game_map is None:
            return
        units = getattr(game_map, "units", None)
        if isinstance(units, list) and unit not in units:
            units.append(unit)

    @staticmethod
    def _phoenix_gem_bodyguard_is_valid(bodyguard) -> bool:
        if bodyguard is None:
            return False
        try:
            if not bodyguard.is_alive() or not getattr(bodyguard, "deployed", False):
                return False
        except Exception:
            return False
        try:
            if bodyguard.is_in_reserves() or bodyguard.is_embarked:
                return False
        except Exception:
            pass
        return True

    def _resolve_phoenix_gem_return(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        unit = payload.get("unit")
        model = payload.get("model")
        if unit is None or model is None:
            return
        spec = payload.get("spec") or {}
        if bool(spec.get("requires_leadership_test", False)):
            passed = True
            pass_for_model = getattr(unit, "pass_leadership_check_for_model", None)
            if callable(pass_for_model):
                try:
                    passed = bool(pass_for_model(model))
                except Exception:
                    passed = False
            else:
                pass_for_unit = getattr(unit, "pass_leadership_check", None)
                if callable(pass_for_unit):
                    try:
                        passed = bool(pass_for_unit())
                    except Exception:
                        passed = False
            if not passed:
                return
        roll_min = self._coerce_int(spec.get("roll_min", 2), 2)
        roll = self._coerce_int(get_roll("D6"), 0)
        if roll < roll_min:
            return

        reattach_target = payload.get("reattach_bodyguard_unit")
        was_attached = bool(payload.get("was_attached_when_destroyed", False))
        require_reattach = bool(spec.get("must_reattach_if_attached", False) and was_attached)
        if require_reattach:
            if not self._phoenix_gem_bodyguard_is_valid(reattach_target):
                return
            can_attach = getattr(unit, "can_attach_to", None)
            if callable(can_attach):
                try:
                    if not bool(can_attach(reattach_target)):
                        return
                except Exception:
                    return
            attach_to_unit = getattr(unit, "attach_to_unit", None)
            if callable(attach_to_unit):
                try:
                    attach_to_unit(reattach_target)
                except Exception:
                    return

        wounds = self._resolve_phoenix_gem_wounds(model, spec)
        self._phoenix_gem_attach_model_to_unit(model, unit)
        self._phoenix_gem_set_model_wounds(model, wounds)
        self._phoenix_gem_restore_model_membership(unit, model)
        self._phoenix_gem_restore_model_position(model, payload.get("position"))
        self._phoenix_gem_refresh_unit_state(unit)
        game_map = payload.get("game_map") or getattr(self, "map", None)
        self._phoenix_gem_add_unit_to_map(game_map, unit)

    def _on_unit_move_started_battle_focus(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        if (action or "").strip().lower() != "fall_back":
            return
        owner = unit.get_parent_army().player
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Battle Focus requires players.")
            if p is owner:
                continue
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Battle Focus requires an army for {p.name}.")
            mgr = getattr(army, "battle_focus", None)
            if mgr is None:
                continue
            mgr.record_enemy_fall_back_start(unit, self)

    def _on_unit_move_ended_battle_focus(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        if (action or "").strip().lower() != "fall_back":
            return
        owner = unit.get_parent_army().player
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Battle Focus requires players.")
            if p is owner:
                continue
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Battle Focus requires an army for {p.name}.")
            mgr = getattr(army, "battle_focus", None)
            if mgr is None:
                continue
            if p.has_control():
                candidates = mgr.consume_opportunity_seized_candidates(unit, self)
                if not candidates:
                    continue
                es = getattr(self, "event_system", None)
                if es is None or not hasattr(es, "subscribers"):
                    raise RuntimeError("Event system missing for Battle Focus prompt.")
                subs = getattr(es, "subscribers", None)
                if not isinstance(subs, dict):
                    raise RuntimeError("Event system subscribers not configured.")
                if subs.get("battle_focus_opportunity_prompt"):
                    es.publish(
                        "battle_focus_opportunity_prompt",
                        player=p,
                        moving_unit=unit,
                        candidates=list(candidates),
                        manager=mgr,
                    )
            else:
                candidates = mgr.consume_opportunity_seized_candidates(unit, self)
                if not candidates:
                    continue
                self._queue_battle_focus_reactive_selection(
                    player=p,
                    candidates=list(candidates),
                    manager=mgr,
                    maneuver="opportunity",
                    moving_unit=unit,
                )

    @staticmethod
    def _entity_is_alive(entity, *, default: bool = True) -> bool:
        if entity is None:
            return False
        alive_attr = getattr(entity, "is_alive", default)
        if callable(alive_attr):
            try:
                return bool(alive_attr())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(alive_attr)

    @staticmethod
    def _attached_unit_root_or_self(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                return get_root()
            except (AttributeError, TypeError, ValueError):
                return unit
        return unit

    @staticmethod
    def _unit_has_keyword_safe(unit, keyword: str) -> bool:
        if unit is None:
            return False
        kw = str(keyword or "").strip()
        if not kw:
            return True
        kw_u = kw.upper()

        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any(kw)):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass

        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            try:
                if bool(has_keyword(kw)):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass

        keys = list(getattr(unit, "keywords", []) or []) + list(getattr(unit, "faction_keywords", []) or [])
        return any(str(entry or "").strip().upper() == kw_u for entry in keys)

    def _on_unit_move_started_spirit_mark(self, unit=None, action: str | None = None, **_kwargs) -> None:
        self._maybe_queue_spirit_mark(unit=unit, action=action)

    def _on_unit_move_ended_spirit_mark(self, unit=None, action: str | None = None, **_kwargs) -> None:
        self._maybe_queue_spirit_mark(unit=unit, action=action)

    def _visible_enemy_candidates_for_model(
        self,
        *,
        source_unit,
        model,
        enemy_roots: list,
        range_value: float,
        game_map,
    ) -> list:
        """Return visible enemy units within range of a source model."""
        if source_unit is None or model is None or game_map is None:
            return []
        try:
            max_range = float(range_value or 0.0)
        except Exception:
            max_range = 0.0
        if max_range <= 0:
            return []
        from ..utility.aura_utils import distance_between_models_bases_3d

        candidates = []
        for enemy_root in list(enemy_roots or []):
            try:
                target_models = list(enemy_root.get_models_for_collision() or [])
            except Exception:
                target_models = list(getattr(enemy_root, "models", []) or [])
            target_models = [tm for tm in target_models if getattr(tm, "is_alive", True)]
            if not target_models:
                continue
            min_dist = float("inf")
            for tm in target_models:
                try:
                    dist = float(distance_between_models_bases_3d(model, tm))
                except Exception:
                    dist = float("inf")
                if dist < min_dist:
                    min_dist = dist
            if min_dist > max_range:
                continue
            has_los = False
            try:
                has_los = bool(source_unit._has_line_of_sight_to_target(model, enemy_root, game_map))
            except Exception:
                has_los = False
            if not has_los:
                continue
            candidates.append(enemy_root)
        return candidates

    def _enemy_candidates_within_range_of_model(
        self,
        *,
        model,
        enemy_roots: list,
        range_value: float,
    ) -> list:
        """Return enemy units within range of a source model (no line-of-sight check)."""
        if model is None:
            return []
        try:
            max_range = float(range_value or 0.0)
        except Exception:
            max_range = 0.0
        if max_range <= 0:
            return []
        from ..utility.aura_utils import distance_between_models_bases_3d

        candidates = []
        for enemy_root in list(enemy_roots or []):
            try:
                target_models = list(enemy_root.get_models_for_collision() or [])
            except Exception:
                target_models = list(getattr(enemy_root, "models", []) or [])
            target_models = [tm for tm in target_models if getattr(tm, "is_alive", True)]
            if not target_models:
                continue
            for tm in target_models:
                try:
                    dist = float(distance_between_models_bases_3d(model, tm))
                except Exception:
                    continue
                if dist <= max_range:
                    candidates.append(enemy_root)
                    break
        return candidates

    def _collect_enemy_unit_roots(self, player) -> list:
        if player is None:
            return []
        try:
            enemy_units = list(self.get_enemy_units(player) or [])
        except Exception:
            enemy_units = []
        enemy_roots = []
        seen = set()
        from ..utility.entity_ids import get_entity_id
        for enemy in enemy_units:
            if enemy is None:
                continue
            try:
                root = enemy.get_attached_unit_root()
            except Exception:
                root = enemy
            if root is None:
                continue
            try:
                if not getattr(root, "is_alive", lambda: False)():
                    continue
            except Exception:
                continue
            if not getattr(root, "deployed", True):
                continue
            try:
                if root.is_in_reserves() or root.is_embarked:
                    continue
            except Exception:
                pass
            try:
                rid = str(get_entity_id(root))
            except Exception:
                rid = ""
            if not rid or rid in seen:
                continue
            seen.add(rid)
            enemy_roots.append(root)
        return enemy_roots

    def _collect_grenade_pack_flyover_candidates(self, unit, spec: dict, game_map) -> list:
        if unit is None or game_map is None:
            return []
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        if range_value <= 0:
            return []
        try:
            enemies = list(game_map.get_enemy_units(unit) or [])
        except Exception:
            enemies = []
        candidates = []
        seen = set()
        for enemy in enemies:
            if enemy is None:
                continue
            try:
                root = enemy.get_attached_unit_root()
            except Exception:
                root = enemy
            if root is None or not getattr(root, "is_alive", lambda: False)():
                continue
            if not getattr(root, "deployed", True):
                continue
            try:
                if root.is_in_reserves() or root.is_embarked:
                    continue
            except Exception:
                pass
            rid = str(maybe_entity_id(root) or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            try:
                dist = float(game_map.get_distance_between_units(unit, root))
            except Exception:
                dist = float("inf")
            if dist > float(range_value):
                continue
            try:
                if not unit._attacking_unit_has_any_los_to_target_unit(root, game_map):
                    continue
            except Exception:
                continue
            candidates.append(root)
        return list(candidates)

    def _unit_within_range_of_model(self, model, unit, *, range_value: float, allow_destroyed_source: bool = False) -> bool:
        if model is None or unit is None:
            return False
        try:
            from ..utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return False
        try:
            if not getattr(model, "is_alive", True) and not allow_destroyed_source:
                return False
        except Exception:
            pass
        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        if not models:
            return False
        for tm in models:
            try:
                if not getattr(tm, "is_alive", True):
                    continue
            except Exception:
                continue
            try:
                if distance_between_models_bases_3d(model, tm) <= float(range_value) + 1e-6:
                    return True
            except Exception:
                continue
        return False

    def _model_can_see_unit(self, model, unit, *, game_map=None) -> bool:
        if model is None or unit is None:
            return False
        if game_map is None:
            game_map = getattr(self, "map", None)
        can_see_fn = getattr(game_map, "can_model_see_model", None) if game_map is not None else None
        if not callable(can_see_fn):
            return False
        try:
            targets = list(unit.get_attached_unit_models() or [])
        except Exception:
            targets = list(getattr(unit, "models", []) or [])
        if not targets:
            return False
        for tm in targets:
            try:
                if not getattr(tm, "is_alive", True):
                    continue
            except Exception:
                continue
            try:
                if can_see_fn(model, tm):
                    return True
            except Exception:
                continue
        return False

    def _on_unit_move_ended_loping_speed(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key not in ("move", "advance", "fall_back"):
            return
        if self.map is None:
            raise RuntimeError("Loping Speed requires a game map.")
        moving_owner = unit.get_parent_army().player
        moving_root = unit.get_attached_unit_root()
        if moving_root is None:
            return

        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Loping Speed requires players.")
            if p is moving_owner:
                continue
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Loping Speed requires an army for {p.name}.")
            is_human = p.has_control()
            seen = set()
            for candidate in list(army.units):
                if candidate is None:
                    continue
                root = candidate.get_attached_unit_root()
                if root is None:
                    continue
                rid = get_entity_id(root)
                if rid in seen:
                    continue
                seen.add(rid)

                rule = root.get_loping_speed_rule()
                if not rule:
                    continue
                rng = int(rule.get("range", 9) or 9)
                if not root.can_loping_speed(game=self, game_map=self.map, moving_unit=moving_root, range_override=rng):
                    continue

                if is_human:
                    es = getattr(self, "event_system", None)
                    if es is None or not hasattr(es, "subscribers"):
                        raise RuntimeError("Event system missing for Loping Speed prompt.")
                    subs = getattr(es, "subscribers", None)
                    if not isinstance(subs, dict):
                        raise RuntimeError("Event system subscribers not configured.")
                    if subs.get("loping_speed_prompt"):
                        es.publish(
                            "loping_speed_prompt",
                            player=p,
                            unit=root,
                            moving_unit=moving_root,
                            rule=rule,
                            game=self,
                        )
                        continue
                source = str((rule or {}).get("source", "") or "Reactive Move").strip() or "Reactive Move"
                move_label = "D6"
                try:
                    fixed = (rule or {}).get("max_distance")
                    if fixed is not None:
                        move_label = str(int(fixed))
                    else:
                        roll_spec = str((rule or {}).get("distance_roll", "") or "").strip()
                        if roll_spec:
                            move_label = roll_spec.upper()
                except Exception:
                    move_label = "D6"
                message = (
                    f"{getattr(moving_root, 'name', 'Enemy unit')} ended a move within {int(rng)}\" of "
                    f"{getattr(root, 'name', 'unit')}.\n\n"
                    f"{source}: Make a Normal move of up to {move_label}\"?"
                )
                request = self._queue_reactive_move_confirmation(
                    player=p,
                    unit=root,
                    kind="loping_speed",
                    movement_type="loping_speed",
                    source=source,
                    message=message,
                    moving_unit=moving_root,
                    range_value=rng,
                )
                if request is None:
                    continue

    def _maybe_trigger_daemonic_poisons(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        *,
        phase: str,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        phase_key = str(phase or "").strip().lower()
        if phase_key == "shooting":
            if not self.is_shooting_phase():
                return
        elif phase_key == "fight":
            if not self.is_fight_phase():
                return
        else:
            return

        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Daemonic Poisons requires an attacker player.")
        if phase_key == "shooting" and attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target(model, target) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return True
            hit_models = hit_models_by_target.get(target)
            if not hit_models:
                return False
            return model in hit_models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_daemonic_poisons_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                seen_targets: set[str] = set()
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    try:
                        target_root = target_unit.get_attached_unit_root()
                    except Exception:
                        target_root = target_unit
                    if not _is_enemy_unit(target_root):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    target_id = get_entity_id(target_root)
                    if target_id in seen_targets:
                        continue
                    seen_targets.add(target_id)
                    candidates.append(target_root)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..rules.daemonic_poisons import apply_daemonic_poisons, DAEMONIC_POISONS_NAME
        from ..utility.event_bus import append_action
        from .decision_kinds import DECISION_CHOOSE_DAEMONIC_POISONS_TARGET

        for model, spec, candidates in triggers:
            ability_name = str(spec.get("source", "") or DAEMONIC_POISONS_NAME).strip() or DAEMONIC_POISONS_NAME
            model_name = str(getattr(model, "name", "") or "")
            if len(candidates) == 1:
                target = candidates[0]
                apply_daemonic_poisons(
                    target,
                    source_unit=attacker_unit,
                    ability_name=ability_name,
                    game=self,
                    player=attacker_player,
                )
                if model_name:
                    append_action(attacker_player, f"{model_name} poisoned {getattr(target, 'name', 'Unit')} ({ability_name}).")
                else:
                    append_action(attacker_player, f"{getattr(attacker_unit, 'name', 'Unit')} poisoned {getattr(target, 'name', 'Unit')} ({ability_name}).")
                continue
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_DAEMONIC_POISONS_TARGET,
                f"{ability_name}: select a unit to poison.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability_name": ability_name,
                    "phase": "Shooting phase" if phase_key == "shooting" else "Fight phase",
                },
            )
            self.request_decision(request)

    def _apply_gift_of_chaos(
        self,
        *,
        source_unit,
        model,
        target_unit,
        ability_name: str,
        player,
    ) -> None:
        if source_unit is None or model is None or target_unit is None:
            return
        if not target_unit.is_alive():
            return
        passed = False
        if hasattr(target_unit, "pass_leadership_check"):
            passed = bool(target_unit.pass_leadership_check())
        from ..utility.event_bus import append_action
        if passed:
            if player is not None:
                append_action(player, f"{ability_name}: {getattr(target_unit, 'name', 'Unit')} passed its Leadership test.")
            return
        from ..utility.dice import DiceCollection
        roll_val, _dice = DiceCollection.from_string("D3").roll_detailed()
        total_mw = int(roll_val or 0)
        if total_mw > 0 and hasattr(source_unit, "_apply_mortal_wounds_to_unit"):
            source_unit._apply_mortal_wounds_to_unit(
                target_unit,
                int(total_mw),
                game_map=getattr(self, "map", None),
                is_psychic_attack=True,
            )
        if player is not None:
            append_action(
                player,
                f"{ability_name}: {getattr(target_unit, 'name', 'Unit')} failed its Leadership test and suffered {int(total_mw)} mortal wound(s).",
            )

    def _maybe_trigger_gift_of_chaos(
        self,
        attacker_unit=None,
        hit_models_by_target_psychic=None,
        *,
        phase: str,
    ) -> None:
        if attacker_unit is None or not hit_models_by_target_psychic:
            return
        phase_key = str(phase or "").strip().lower()
        if phase_key == "shooting":
            if not self.is_shooting_phase():
                return
        elif phase_key == "fight":
            if not self.is_fight_phase():
                return
        else:
            return

        root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
        if root is None:
            return
        attacker_player = root.get_parent_army().player
        if attacker_player is None:
            return
        if phase_key == "shooting" and attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == root.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        triggers: list[tuple[Any, str, list[Any]]] = []
        for entry in list(root.iter_gift_of_chaos_models() or []):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            candidates: list[Any] = []
            seen_targets: set[str] = set()
            for target_unit, models in (hit_models_by_target_psychic or {}).items():
                if target_unit is None:
                    continue
                if not isinstance(models, (list, set, tuple)) or model not in models:
                    continue
                target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
                if not _is_enemy_unit(target_root):
                    continue
                tid = get_entity_id(target_root)
                if tid in seen_targets:
                    continue
                seen_targets.add(tid)
                candidates.append(target_root)
            if candidates:
                triggers.append(
                    (
                        model,
                        str(entry.get("source", "") or "Gift of Chaos").strip() or "Gift of Chaos",
                        candidates,
                    )
                )

        if not triggers:
            return

        from .decision_kinds import DECISION_CHOOSE_GIFT_OF_CHAOS_TARGET
        from .decisions import DecisionOption, DecisionRequest

        for model, ability_name, candidates in triggers:
            if len(candidates) == 1:
                self._apply_gift_of_chaos(
                    source_unit=root,
                    model=model,
                    target_unit=candidates[0],
                    ability_name=ability_name,
                    player=attacker_player,
                )
                continue
            options = []
            for cand in sorted(list(candidates), key=lambda u: str(get_entity_id(u))):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={
                            "target_unit_id": get_entity_id(cand),
                            "model_id": get_entity_id(model),
                            "attacker_unit_id": get_entity_id(root),
                        },
                    )
                )
            if not options:
                continue
            # Avoid duplicate pending decisions for the same model in this phase.
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                pending = False
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_GIFT_OF_CHAOS_TARGET:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("model_id", "") or "") == str(get_entity_id(model) or ""):
                        pending = True
                        break
                if pending:
                    continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_GIFT_OF_CHAOS_TARGET,
                f"{ability_name}: select a target.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "ability": "gift_of_chaos",
                    "ability_name": ability_name,
                    "model_id": get_entity_id(model),
                    "attacker_unit_id": get_entity_id(root),
                    "phase": "Shooting phase" if phase_key == "shooting" else "Fight phase",
                },
            )
            self.request_decision(request)

    def _on_fight_sequence_complete_aspect_shrine(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        root = unit.get_attached_unit_root()
        clear_fn = getattr(root, "clear_aspect_shrine_prompt_suppression", None)
        if callable(clear_fn):
            clear_fn()

    def _on_fight_sequence_complete_gift_of_chaos(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None:
            return
        hit_map = getattr(root, "_gift_of_chaos_hit_models_by_target_psychic", None)
        if not isinstance(hit_map, dict) or not hit_map:
            hit_map = getattr(unit, "_gift_of_chaos_hit_models_by_target_psychic", None)
        if isinstance(hit_map, dict) and hit_map:
            self._maybe_trigger_gift_of_chaos(
                attacker_unit=root,
                hit_models_by_target_psychic=hit_map,
                phase="fight",
            )
        for obj in (root, unit):
            if obj is not None and hasattr(obj, "_gift_of_chaos_hit_models_by_target_psychic"):
                delattr(obj, "_gift_of_chaos_hit_models_by_target_psychic")

    def _on_unit_move_ended_detachment_rules(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        if (action or "").strip().lower() != "charge":
            return
        army = unit.get_parent_army()
        if army is None:
            raise RuntimeError("Detachment rule resolution requires a parent army.")
        we_mgr = getattr(army, "world_eaters_detachments", None)
        if we_mgr is not None and callable(getattr(we_mgr, "relentless_rage_applies", None)):
            if bool(we_mgr.relentless_rage_applies(unit)):
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
        if cd_mgr is not None and callable(getattr(cd_mgr, "seductive_gambit_applies", None)):
            if bool(cd_mgr.seductive_gambit_applies(unit)):
                # Seductive Gambit applies only to LEGIONES DAEMONICA SLAANESH units.
                player = unit.get_parent_army().player
                if player is None:
                    raise RuntimeError("Seductive Gambit requires a player.")
                unit_id = maybe_entity_id(unit)
                ctx = {
                    "unit": getattr(unit, "name", "") or "",
                    "ability_name": "Seductive Gambit",
                    "phase": "Charge phase",
                    "unit_id": unit_id,
                }
                message = f"Use Seductive Gambit for {getattr(unit, 'name', 'Unit')}?"
                self._queue_optional_ability_confirmation(
                    player=player,
                    ability_key="seductive_gambit",
                    ability_name="Seductive Gambit",
                    message=message,
                    context=ctx,
                    payload={"unit_id": unit_id},
                    instance_key=str(unit_id or ""),
                )

    def resolve_charge_end_mortal_wounds(self, unit, target_unit, spec) -> None:
        if unit is None or target_unit is None or not isinstance(spec, dict):
            return
        kind = str(spec.get("kind", "") or "").strip().lower()
        if not kind:
            return
        game_map = getattr(self, "map", None)
        ability_name = str(spec.get("name", "") or "Charge Mortals").strip() or "Charge Mortals"

        from ..utility.dice import get_roll

        total_mw = 0
        roll_summary = ""
        if kind == "per_model_4plus_d3":
            models = list(unit.get_attached_unit_models() or [])
            rolls = []
            d3_rolls = []
            for m in models:
                if not getattr(m, "is_alive", False):
                    continue
                r = int(get_roll("D6") or 0)
                rolls.append(r)
                if r >= 4:
                    d3 = int(get_roll("D3") or 0)
                    d3_rolls.append(d3)
                    total_mw += d3
            if rolls:
                roll_summary = f"rolls={rolls}"
                if d3_rolls:
                    roll_summary += f", d3={d3_rolls}"
        elif kind == "per_model_4plus_1":
            models = list(unit.get_attached_unit_models() or [])
            rolls = []
            for m in models:
                if not getattr(m, "is_alive", False):
                    continue
                r = int(get_roll("D6") or 0)
                rolls.append(r)
                if r >= 4:
                    total_mw += 1
            if rolls:
                roll_summary = f"rolls={rolls}"
        elif kind == "per_remaining_wounds_4plus_1_max6":
            models = list(unit.get_attached_unit_models() or [])
            alive = [m for m in models if getattr(m, "is_alive", False)]
            model = None
            if len(alive) == 1:
                model = alive[0]
            else:
                try:
                    model = unit._get_enhancement_bearer_model()
                except Exception:
                    model = None
                if model not in alive:
                    model = alive[0] if alive else None
            remaining = int(getattr(model, "wounds", 0) or 0) if model is not None else 0
            rolls = []
            for _ in range(max(0, remaining)):
                r = int(get_roll("D6") or 0)
                rolls.append(r)
                if r >= 4:
                    total_mw += 1
            if total_mw > 6:
                total_mw = 6
            if rolls:
                roll_summary = f"rolls={rolls}, remaining_wounds={remaining}"
        elif kind == "table_d6_2_3_4_5_6":
            roll = int(get_roll("D6") or 0)
            if 2 <= roll <= 3:
                total_mw = 1
            elif 4 <= roll <= 5:
                total_mw = int(get_roll("D3") or 0)
            elif roll >= 6:
                total_mw = int(get_roll("D3") or 0) + 3
            roll_summary = f"roll={roll}"
        elif kind == "table_d6_2_5_6":
            roll = int(get_roll("D6") or 0)
            if 2 <= roll <= 5:
                total_mw = int(get_roll("D3") or 0)
            elif roll >= 6:
                total_mw = int(get_roll("D3") or 0) + 3
            roll_summary = f"roll={roll}"
        else:
            return

        print(
            f"{ability_name}: {getattr(unit, 'name', 'Unit')} -> "
            f"{getattr(target_unit, 'name', 'Target')} ({roll_summary}) => {total_mw} mortal wounds"
        )

        if total_mw > 0:
            unit._apply_mortal_wounds_to_unit(target_unit, int(total_mw), game_map=game_map)
        from ..utility.event_bus import append_action
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_action(
                player,
                f"{ability_name}: {getattr(unit, 'name', 'Unit')} dealt {int(total_mw)} mortal wounds to {getattr(target_unit, 'name', 'Target')}.",
            )

    def _on_unit_move_ended_charge_mortal_wounds(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        if (action or "").strip().lower() != "charge":
            return
        game_map = self.map
        if game_map is None:
            return
        root = unit.get_attached_unit_root()
        if root is None:
            return
        if not root.is_alive():
            return

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        specs = list(sr.get("charge_end_mortal_wounds", []) or [])
        if not specs:
            return

        enemies = list(game_map.get_enemy_units(root) or [])
        engaged = []
        for enemy in enemies:
            if enemy is None:
                continue
            if not getattr(enemy, "deployed", True):
                continue
            if not enemy.is_alive():
                continue
            if not game_map.is_within_engagement_range(root, enemy):
                continue
            engaged.append(enemy)

        if not engaged:
            return

        player = root.get_parent_army().player
        if player is None:
            return
        for spec in specs:
            if len(engaged) == 1:
                self.resolve_charge_end_mortal_wounds(root, engaged[0], spec)
                continue
            self._queue_mortal_wounds_target_decision(
                player=player,
                unit=root,
                candidates=list(engaged),
                spec=spec,
                kind="charge_end",
                allow_skip=False,
                phase="Charge phase",
            )

    def _on_unit_move_ended_charge_battleshock(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        if (action or "").strip().lower() != "charge":
            return
        game_map = self.map
        if game_map is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not root.is_alive():
            return

        specs = []
        try:
            specs = list(root.unit_charge_end_engagement_battleshock_specs() or [])
        except Exception:
            specs = []
        if not specs:
            return

        enemies = list(game_map.get_enemy_units(root) or [])
        engaged = []
        for enemy in enemies:
            if enemy is None:
                continue
            try:
                if not getattr(enemy, "deployed", True):
                    continue
            except Exception:
                continue
            if not enemy.is_alive():
                continue
            if enemy.is_in_reserves() or enemy.is_embarked:
                continue
            if not game_map.is_within_engagement_range(root, enemy):
                continue
            try:
                enemy_root = enemy.get_attached_unit_root()
            except Exception:
                enemy_root = enemy
            if enemy_root is None or not enemy_root.is_alive():
                continue
            engaged.append(enemy_root)

        if not engaged:
            return
        unique_engaged = []
        seen_engaged: set[str] = set()
        for enemy_root in list(engaged):
            rid = str(get_entity_id(enemy_root) or "")
            if not rid or rid in seen_engaged:
                continue
            seen_engaged.add(rid)
            unique_engaged.append(enemy_root)
        engaged = unique_engaged

        tested: set[tuple[str, str]] = set()
        for spec in specs:
            source = str(spec.get("source", "") or "Charge end Battle-shock").strip() or "Charge end Battle-shock"
            try:
                test_modifier = int(spec.get("test_modifier", 0) or 0)
            except Exception:
                test_modifier = 0
            if bool(spec.get("select_one", False)):
                if len(engaged) == 1:
                    target = engaged[0]
                    if target is not None:
                        if test_modifier:
                            target_sr = getattr(target, "special_rules", None)
                            if not isinstance(target_sr, dict):
                                target_sr = {}
                            current = int(target_sr.get("battle_shock_test_modifier", 0) or 0)
                            target_sr["battle_shock_test_modifier"] = int(current + test_modifier)
                            reasons = list(target_sr.get("battle_shock_test_modifier_reasons", []) or [])
                            reasons.append(source)
                            target_sr["battle_shock_test_modifier_reasons"] = reasons
                            target.special_rules = target_sr
                        try:
                            target.take_battle_shock_test(int(getattr(self, "turn", 0) or 1))
                        except Exception:
                            pass
                        from ..utility.event_bus import append_action
                        player = root.get_parent_army().player if root.get_parent_army() is not None else None
                        if player is not None:
                            append_action(
                                player,
                                f"{source}: {getattr(target, 'name', 'Unit')} takes a Battle-shock test.",
                            )
                    continue

                root_id = str(get_entity_id(root) or "")
                queue = getattr(self, "decision_queue", None)
                if queue is not None and hasattr(queue, "list"):
                    duplicate = False
                    for req in list(queue.list() or []):
                        if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                            continue
                        ctx = dict(getattr(req, "context", {}) or {})
                        if str(ctx.get("ability", "") or "") != "charge_end_select_one_battleshock":
                            continue
                        if str(ctx.get("source_unit_id", "") or "") != root_id:
                            continue
                        if str(ctx.get("ability_name", "") or "") != source:
                            continue
                        duplicate = True
                        break
                    if duplicate:
                        continue

                sorted_targets = sorted(
                    list(engaged),
                    key=lambda u: str(get_entity_id(u) or ""),
                )
                options = [
                    DecisionOption.create(
                        str(getattr(target, "name", "Unit") or "Unit"),
                        payload={
                            "target_unit_id": str(get_entity_id(target) or ""),
                            "source_unit_id": root_id,
                        },
                    )
                    for target in sorted_targets
                    if target is not None and str(get_entity_id(target) or "")
                ]
                if not options:
                    continue
                request = DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    f"{source}: select one enemy unit to take a Battle-shock test.",
                    player_id=getattr(getattr(root.get_parent_army(), "player", None), "id", None),
                    options=options,
                    context={
                        "ability": "charge_end_select_one_battleshock",
                        "ability_name": source,
                        "source_unit_id": root_id,
                        "test_modifier": int(test_modifier),
                    },
                )
                self.request_decision(request)
                continue

            for enemy_root in engaged:
                key = (str(get_entity_id(enemy_root)), source.lower())
                if key in tested:
                    continue
                tested.add(key)
                try:
                    enemy_root.take_battle_shock_test(int(getattr(self, "turn", 0) or 1))
                except Exception:
                    pass
                from ..utility.event_bus import append_action
                player = root.get_parent_army().player if root.get_parent_army() is not None else None
                if player is not None:
                    append_action(
                        player,
                        f"{source}: {getattr(enemy_root, 'name', 'Unit')} takes a Battle-shock test.",
                    )

    def resolve_move_over_mortal_wounds(self, unit, model, target_unit, spec) -> None:
        if unit is None or target_unit is None or not isinstance(spec, dict):
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        dice_count = int(spec.get("dice", 0) or 0)
        dice_per_model = bool(spec.get("dice_per_model", False))
        if dice_per_model:
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            dice_count = len([m for m in list(models or []) if getattr(m, "is_alive", True)])
        threshold = int(spec.get("threshold", 0) or 0)
        mortal_per = int(spec.get("mortal_per_success", 1) or 0)
        mortal_die = str(spec.get("mortal_per_success_die", "") or "").strip().upper()
        fly_bonus = int(spec.get("fly_bonus", 0) or 0)
        if dice_count <= 0 or threshold <= 0 or (mortal_per <= 0 and not mortal_die):
            return

        def _target_has_fly(target) -> bool:
            if target is None:
                return False
            try:
                if bool(getattr(target, "is_flying", False)):
                    return True
            except Exception:
                pass
            try:
                has_kw = getattr(target, "has_keyword", None)
                if callable(has_kw) and has_kw("FLY"):
                    return True
            except Exception:
                pass
            try:
                has_any_kw = getattr(target, "has_any_keyword", None)
                if callable(has_any_kw) and has_any_kw("FLY"):
                    return True
            except Exception:
                pass
            return False

        apply_fly_bonus = int(fly_bonus) if (fly_bonus and _target_has_fly(target_unit)) else 0
        effective_threshold = max(1, int(threshold) - int(apply_fly_bonus))

        ability_name = str(spec.get("source", "") or "Move-over mortals").strip() or "Move-over mortals"

        reroll_rules: list[dict] = []
        reroll_count = 0
        try:
            reroll_count = int(root.move_over_mortal_wounds_reroll_count() or 0)
        except Exception:
            reroll_count = 0
        if reroll_count > 0:
            reroll_count = min(int(reroll_count), int(dice_count))
            label = "Re-roll move-over die" if reroll_count == 1 else f"Re-roll up to {reroll_count} move-over dice"
            reroll_rules.append(
                {
                    "action_id": "reroll_move_over",
                    "label": label,
                    "mode": "any",
                    "max_select": int(reroll_count),
                    "allow_success": True,
                    "source": "Move-over reroll",
                }
            )

        try:
            from ..utility.entity_ids import get_entity_id
        except Exception:
            get_entity_id = None

        unit_id = get_entity_id(root) if callable(get_entity_id) else None
        target_id = get_entity_id(target_unit) if callable(get_entity_id) else None
        model_id = get_entity_id(model) if (model is not None and callable(get_entity_id)) else None

        reason = f"{ability_name}: {getattr(root, 'name', 'Unit')} -> {getattr(target_unit, 'name', 'Target')}"
        roll_spec = {
            "dice_count": int(dice_count),
            "faces": 6,
            "reason": reason,
            "roll_type": "move_over_mortal_wounds",
            "unit_id": unit_id,
            "model_id": model_id,
            "target_unit_id": target_id,
            "target_unit_ids": [target_id] if target_id else [],
            "handler_key": "move_over_mortal_wounds",
            "ability_name": ability_name,
            "threshold": int(threshold),
            "effective_threshold": int(effective_threshold),
            "mortal_per_success": int(mortal_per),
            "mortal_per_success_die": str(mortal_die or ""),
            "fly_bonus": int(fly_bonus or 0),
            "apply_fly_bonus": int(apply_fly_bonus),
            "target": int(effective_threshold),
            "target_op": "gte",
        }
        if reroll_rules:
            roll_spec["reroll_rules"] = list(reroll_rules)
        if bool(getattr(self, "auto_resolve_dice_rolls", False)):
            try:
                from ..utility.dice import get_roll

                roll_spec["fixed_dice"] = [int(get_roll("D6") or 0) for _ in range(int(dice_count))]
                if reroll_rules:
                    roll_spec["roll_sequence"] = [int(get_roll("D6") or 0) for _ in range(int(reroll_count))]
            except Exception:
                pass
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return
        try:
            self.request_dice_roll(player_id=getattr(player, "id", None), spec=roll_spec, prompt=roll_spec["reason"])
        except Exception:
            pass

    def resolve_end_of_fight_embark(self, transport, passenger, spec) -> bool:
        if transport is None or passenger is None or not isinstance(spec, dict):
            return False
        game_map = getattr(self, "map", None)
        if game_map is None:
            return False
        if not getattr(transport, "is_alive", lambda: False)():
            return False
        if not getattr(transport, "deployed", True):
            return False
        try:
            if transport.is_in_reserves() or transport.is_embarked:
                return False
        except Exception:
            pass
        if not getattr(passenger, "is_alive", lambda: False)():
            return False
        if not getattr(passenger, "deployed", True):
            return False
        try:
            if passenger.is_in_reserves() or passenger.is_embarked:
                return False
        except Exception:
            pass
        if passenger is transport:
            return False
        if list(getattr(transport, "transport_passengers", []) or []):
            return False
        keyword = str(spec.get("keyword", "") or "").strip()
        if keyword and not passenger.has_any_keyword(keyword):
            return False
        try:
            max_models = int(spec.get("max_models", 0) or 0)
        except Exception:
            max_models = 0
        if max_models > 0:
            try:
                models = list(passenger.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(passenger, "models", []) or [])
            alive = [m for m in models if getattr(m, "is_alive", True)]
            if len(alive) > max_models:
                return False
        try:
            range_value = float(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0.0
        if range_value <= 0:
            return False
        try:
            from ..utility.aura_utils import unit_wholly_within_range_of_unit
            if not unit_wholly_within_range_of_unit(transport, passenger, range_value):
                return False
        except Exception:
            return False
        # Must not be within Engagement Range of any enemy units.
        try:
            enemies = list(game_map.get_enemy_units(passenger) or [])
        except Exception:
            enemies = []
        for enemy in enemies:
            if enemy is None or not getattr(enemy, "is_alive", lambda: False)():
                continue
            if game_map.is_within_engagement_range(passenger, enemy):
                return False
        # Cannot embark after disembarking this turn.
        if getattr(passenger.round_state, "disembarked_this_round", False):
            return False
        # Fire and Fade: cannot embark until end of turn.
        try:
            sr = getattr(passenger, "special_rules", None)
        except Exception:
            sr = None
        if isinstance(sr, dict) and sr.get("fire_and_fade_no_embark_turn_owner"):
            owner = str(sr.get("fire_and_fade_no_embark_turn_owner") or "")
            turn = int(sr.get("fire_and_fade_no_embark_turn", 0) or 0)
            current = self.get_current_player()
            if owner and current is not None:
                if owner == str(getattr(current, "id", "") or "") and int(getattr(self, "turn", 0) or 0) == turn:
                    return False
        try:
            if not transport.can_transport(passenger):
                return False
        except Exception:
            return False

        ok = False
        try:
            ok = bool(transport.add_passenger(passenger, game_map=game_map))
        except Exception:
            ok = False
        if ok:
            try:
                from ..utility.event_bus import append_action
                player = getattr(transport.get_parent_army(), "player", None)
                ability_name = str(spec.get("source", "") or "End of fight embark").strip() or "End of fight embark"
                if player is not None:
                    append_action(
                        player,
                        f"{ability_name}: {getattr(passenger, 'name', 'Unit')} embarked in {getattr(transport, 'name', 'Transport')}.",
                    )
            except Exception:
                pass
        return bool(ok)

    def resolve_grenade_pack_flyover(self, unit, target_unit, spec) -> None:
        if unit is None or target_unit is None or not isinstance(spec, dict):
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            models = list(getattr(root, "models", []) or [])
        except Exception:
            models = []
        models = [m for m in models if getattr(m, "is_alive", True)]
        model_keyword = str(spec.get("model_keyword", "") or "").strip()
        if model_keyword:
            key_norm = re.sub(r"[^a-z0-9]+", " ", model_keyword.lower()).strip()
            key_singular = key_norm[:-1] if key_norm.endswith("s") else key_norm

            def _matches_keyword(model_obj) -> bool:
                try:
                    name = str(getattr(model_obj, "name", "") or "").lower()
                except Exception:
                    name = ""
                if not name:
                    return False
                name_norm = re.sub(r"[^a-z0-9]+", " ", name).strip()
                if not name_norm:
                    return False
                if key_norm and (key_norm in name_norm or name_norm in key_norm):
                    return True
                if key_singular and (key_singular in name_norm or name_norm in key_singular):
                    return True
                return False

            try:
                models = [m for m in models if _matches_keyword(m)]
            except Exception:
                pass
        dice_count = len(models)
        try:
            threshold = int(spec.get("threshold", 0) or 0)
        except Exception:
            threshold = 0
        try:
            mortal_per = int(spec.get("mortal_per_success", 1) or 0)
        except Exception:
            mortal_per = 0
        try:
            max_mortal = int(spec.get("max_mortal", 0) or 0)
        except Exception:
            max_mortal = 0
        if dice_count <= 0 or threshold <= 0 or mortal_per <= 0:
            return

        ability_name = str(spec.get("source", "") or "Grenade Pack Flyover").strip() or "Grenade Pack Flyover"

        try:
            from ..utility.entity_ids import get_entity_id
        except Exception:
            get_entity_id = None

        unit_id = get_entity_id(root) if callable(get_entity_id) else None
        target_id = get_entity_id(target_unit) if callable(get_entity_id) else None

        reason = f"{ability_name}: {getattr(root, 'name', 'Unit')} -> {getattr(target_unit, 'name', 'Target')}"
        roll_spec = {
            "dice_count": int(dice_count),
            "faces": 6,
            "reason": reason,
            "roll_type": "grenade_pack_flyover",
            "unit_id": unit_id,
            "target_unit_id": target_id,
            "target_unit_ids": [target_id] if target_id else [],
            "handler_key": "grenade_pack_flyover",
            "ability_name": ability_name,
            "threshold": int(threshold),
            "mortal_per_success": int(mortal_per),
            "max_mortal": int(max_mortal),
        }
        if bool(getattr(self, "auto_resolve_dice_rolls", False)):
            try:
                from ..utility.dice import get_roll
                roll_spec["fixed_dice"] = [int(get_roll("D6") or 0) for _ in range(int(dice_count))]
            except Exception:
                pass
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return
        try:
            self.request_dice_roll(player_id=getattr(player, "id", None), spec=roll_spec, prompt=roll_spec["reason"])
        except Exception:
            pass

    def _on_unit_move_ended_move_over_mortal_wounds(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key not in ("move", "advance"):
            return

        game_map = self.map
        if game_map is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not root.is_alive() or not getattr(root, "deployed", True):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass

        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])

        if not models:
            return

        from ..utility.calcs import get_enemy_units_moved_over

        for model in models:
            if not getattr(model, "is_alive", False):
                continue
            model_unit = getattr(model, "parent_unit", None) or root
            if not bool(getattr(model_unit, "is_flying", False)):
                continue
            specs = model_unit.model_move_over_mortal_wounds_specs(model) or []
            if not specs:
                continue
            path = getattr(model, "last_move_path", None)
            candidates = get_enemy_units_moved_over(model, path, game_map, require_vertical_overlap=True)
            if not candidates:
                continue

            player = model_unit.get_parent_army().player
            if player is None:
                continue
            for spec in specs:
                move_types = set(spec.get("move_types") or [])
                if action_key not in move_types:
                    continue
                filtered = list(candidates)
                if spec.get("exclude_monster_vehicle"):
                    filtered = [
                        cand for cand in filtered
                        if not (cand.has_any_keyword("MONSTER") or cand.has_any_keyword("VEHICLE"))
                    ]
                if not filtered:
                    continue
                self._queue_mortal_wounds_target_decision(
                    player=player,
                    unit=model_unit,
                    model=model,
                    candidates=list(filtered),
                    spec=spec,
                    kind="move_over",
                    allow_skip=True,
                    phase="Movement phase",
                )

        # Unit-level move-over mortal wounds (roll per model in unit).
        try:
            if not bool(getattr(root, "is_flying", False)):
                return
        except Exception:
            return
        try:
            unit_specs = list(root.unit_move_over_mortal_wounds_specs() or [])
        except Exception:
            unit_specs = []
        if not unit_specs:
            return
        candidates = []
        seen_ids = set()
        for model in models:
            if not getattr(model, "is_alive", False):
                continue
            path = getattr(model, "last_move_path", None)
            moved_over = get_enemy_units_moved_over(model, path, game_map, require_vertical_overlap=True)
            for cand in list(moved_over or []):
                try:
                    cid = get_entity_id(cand)
                except Exception:
                    cid = None
                if cid and cid in seen_ids:
                    continue
                if cid:
                    seen_ids.add(cid)
                candidates.append(cand)
        if not candidates:
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return
        for spec in list(unit_specs or []):
            move_types = set(spec.get("move_types") or [])
            if action_key not in move_types:
                continue
            if spec.get("once_per_battle"):
                ability_key = str(spec.get("ability_key") or "").strip().lower()
                if ability_key and root.has_used_unit_once_per_battle(ability_key):
                    continue
            filtered = list(candidates)
            if spec.get("exclude_monster_vehicle"):
                filtered = [
                    cand for cand in filtered
                    if not (cand.has_any_keyword("MONSTER") or cand.has_any_keyword("VEHICLE"))
                ]
            if not filtered:
                continue
            self._queue_mortal_wounds_target_decision(
                player=player,
                unit=root,
                candidates=list(filtered),
                spec=spec,
                kind="move_over",
                allow_skip=True,
                phase="Movement phase",
            )

    def _on_unit_move_ended_move_over_battleshock(self, unit=None, action: str | None = None, **_kwargs) -> None:
        """Resolve move-over Battle-shock triggers after Normal/Advance moves."""
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key not in ("move", "advance"):
            return

        game_map = self.map
        if game_map is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not root.is_alive() or not getattr(root, "deployed", True):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass

        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        if not models:
            return

        from ..utility.calcs import get_enemy_units_moved_over

        for model in models:
            if not getattr(model, "is_alive", False):
                continue
            model_unit = getattr(model, "parent_unit", None) or root
            spec_fn = getattr(model_unit, "model_move_over_battleshock_specs", None)
            if not callable(spec_fn):
                continue
            specs = list(spec_fn(model) or [])
            if not specs:
                continue
            path = getattr(model, "last_move_path", None)
            candidates = get_enemy_units_moved_over(model, path, game_map, require_vertical_overlap=True)
            if not candidates:
                continue
            try:
                player = model_unit.get_parent_army().player
            except Exception:
                player = None
            if player is None:
                continue
            for spec in specs:
                move_types = set(spec.get("move_types") or [])
                if action_key not in move_types:
                    continue
                queue_fn = getattr(self, "_queue_move_over_battleshock_decision", None)
                if not callable(queue_fn):
                    continue
                queue_fn(
                    player=player,
                    unit=model_unit,
                    model=model,
                    candidates=list(candidates),
                    spec=spec,
                    allow_skip=bool(spec.get("optional", False)),
                )

    def _on_unit_move_ended_move_over_no_cover(self, unit=None, action: str | None = None, **_kwargs) -> None:
        """Resolve move-over no-cover target selection after Normal moves."""
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key != "move":
            return

        game_map = self.map
        if game_map is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not root.is_alive() or not getattr(root, "deployed", True):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass

        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        if not models:
            return

        from ..utility.calcs import get_enemy_units_moved_over

        for model in models:
            if not getattr(model, "is_alive", False):
                continue
            model_unit = getattr(model, "parent_unit", None) or root
            spec_fn = getattr(model_unit, "model_move_over_no_cover_specs", None)
            if not callable(spec_fn):
                continue
            specs = list(spec_fn(model) or [])
            if not specs:
                continue
            path = getattr(model, "last_move_path", None)
            candidates = get_enemy_units_moved_over(model, path, game_map, require_vertical_overlap=True)
            if not candidates:
                continue
            try:
                player = model_unit.get_parent_army().player
            except Exception:
                player = None
            if player is None:
                continue
            queue_fn = getattr(self, "_queue_move_over_no_cover_decision", None)
            if not callable(queue_fn):
                continue
            for spec in specs:
                move_types = set(spec.get("move_types") or [])
                if action_key not in move_types:
                    continue
                queue_fn(
                    player=player,
                    unit=model_unit,
                    model=model,
                    candidates=list(candidates),
                    spec=spec,
                )

    def _on_unit_move_ended_grenade_pack_flyover(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key not in ("move", "advance", "fall_back"):
            return
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "MOVEMENT_PHASE":
            return
        game_map = self.map
        if game_map is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not root.is_alive() or not getattr(root, "deployed", True):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        try:
            specs = list(root.unit_grenade_pack_flyover_specs() or [])
        except Exception:
            specs = []
        if not specs:
            return
        for spec in specs:
            move_types = set(spec.get("move_types") or [])
            if action_key not in move_types:
                continue
            sr = getattr(root, "special_rules", None)
            if spec.get("once_per_turn") and isinstance(sr, dict):
                owner = str(sr.get("grenade_pack_flyover_used_turn_owner", "") or "")
                turn = int(sr.get("grenade_pack_flyover_used_turn", 0) or 0)
                if owner and owner == str(getattr(player, "id", "") or "") and int(getattr(self, "turn", 0) or 0) == turn:
                    continue
            candidates = self._collect_grenade_pack_flyover_candidates(root, spec, game_map)
            if not candidates:
                continue
            self._queue_grenade_pack_flyover_target_decision(
                player=player,
                unit=root,
                candidates=candidates,
                spec=spec,
            )

    def _on_unit_move_ended_snared_mortal_wounds(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key not in ("move", "advance", "fall_back"):
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not root.is_alive() or not getattr(root, "deployed", True):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("snared_active"):
            return

        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        models = [m for m in models if getattr(m, "is_alive", True)]
        if not models:
            return

        from ..utility.dice import get_roll
        from ..utility.event_bus import append_action, append_dice

        rolls = []
        ones = 0
        for _m in models:
            r = int(get_roll("D6") or 0)
            rolls.append(r)
            if r == 1:
                ones += 1

        if ones > 0:
            root._apply_mortal_wounds_to_unit(root, int(ones), game_map=getattr(self, "map", None))

        owner = self._resolve_player_by_id(str(sr.get("snared_owner", "") or ""))
        ability_name = str(sr.get("snared_source", "") or "Snared").strip() or "Snared"
        if owner is not None:
            append_dice(
                owner,
                f"{ability_name}: rolls {rolls} => {int(ones)} mortal wounds to {getattr(root, 'name', 'Unit')}.",
            )
            append_action(
                owner,
                f"{ability_name}: {getattr(root, 'name', 'Unit')} suffered {int(ones)} mortal wounds.",
            )

    def _resolve_charge_phase_bodyguard_loss(self, leader_unit, bodyguard, model, ability):
        if model is None:
            return
        ability_name = str((ability or {}).get("name", "") or "Leadership Test").strip() or "Leadership Test"
        model.die(game_map=getattr(self, "map", None))
        from ..utility.event_bus import append_action
        player = getattr(leader_unit.get_parent_army(), "player", None)
        if player is not None:
            append_action(
                player,
                f"{ability_name}: {getattr(model, 'name', 'Bodyguard model')} destroyed in {getattr(bodyguard, 'name', 'Unit')}.",
            )

    def resolve_fight_phase_end_mortal_wounds(self, unit, model, target_unit, spec) -> None:
        if unit is None or target_unit is None or not isinstance(spec, dict):
            return
        dice_count = int(spec.get("dice", 8) or 0)
        threshold = int(spec.get("threshold", 4) or 0)
        mortal_per = int(spec.get("mortal_per_success", 1) or 0)
        if dice_count <= 0 or threshold <= 0 or mortal_per <= 0:
            return

        from ..utility.dice import get_roll

        rolls = []
        successes = 0
        for _ in range(dice_count):
            r = int(get_roll("D6") or 0)
            rolls.append(r)
            if r >= threshold:
                successes += 1
        total_mw = int(successes * mortal_per)

        ability_name = str(spec.get("source", "") or "Fight phase mortals").strip() or "Fight phase mortals"
        print(
            f"{ability_name}: {getattr(model, 'name', 'Model')} -> {getattr(target_unit, 'name', 'Target')} "
            f"(rolls={rolls}) => {total_mw} mortal wounds"
        )

        if total_mw > 0:
            unit._apply_mortal_wounds_to_unit(target_unit, total_mw, game_map=getattr(self, "map", None))
        from ..utility.event_bus import append_action, append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(
                player,
                f"{ability_name}: rolls {rolls} => {int(total_mw)} mortal wounds to {getattr(target_unit, 'name', 'Target')}.",
            )
            append_action(
                player,
                f"{ability_name}: {getattr(model, 'name', 'Model')} dealt {int(total_mw)} mortal wounds to {getattr(target_unit, 'name', 'Target')}.",
            )

    def _maybe_prompt_transport_reactive_disembark(self, unit=None, *, trigger: str | None = None) -> None:
        if unit is None:
            return
        if not self.is_movement_phase():
            return

        game_map = self.map
        if game_map is None:
            raise RuntimeError("Transport reactive disembark requires a game map.")

        if not unit.is_alive():
            return
        if not getattr(unit, "deployed", True):
            return

        current_player = self.get_current_player()
        moving_army = unit.get_parent_army()

        if current_player is not None and moving_army is not None:
            if current_player.get_army() != moving_army:
                return

        from ..utility.aura_utils import unit_within_range_of_unit

        transports = list(getattr(game_map, "units", []) or [])
        for transport in transports:
            if transport is None:
                continue
            if not getattr(transport, "is_transport", False):
                continue
            if not transport.is_alive():
                continue
            if not getattr(transport, "deployed", True):
                continue
            if moving_army is not None and transport.get_parent_army() == moving_army:
                continue

            ability = transport.get_transport_reactive_disembark_ability()
            if not isinstance(ability, dict):
                continue

            passengers = list(getattr(transport, "transport_passengers", []) or [])
            if not passengers:
                continue

            rng = float(ability.get("range", 0) or 0)
            if rng <= 0:
                continue

            if not unit_within_range_of_unit(transport, unit, rng):
                continue

            player = transport.get_parent_army().player
            if player is None:
                raise RuntimeError("Transport reactive disembark requires a player.")
            if bool(getattr(player, "has_control", lambda: False)()):
                es = getattr(self, "event_system", None)
                if es is None or not hasattr(es, "subscribers"):
                    raise RuntimeError("Event system missing for transport reactive disembark prompt.")
                subs = getattr(es, "subscribers", None)
                if not isinstance(subs, dict):
                    raise RuntimeError("Event system subscribers not configured.")
                if subs.get("transport_reactive_disembark_prompt"):
                    es.publish(
                        "transport_reactive_disembark_prompt",
                        player=player,
                        transport=transport,
                        enemy_unit=unit,
                        ability=ability,
                        game=self,
                    )
            else:
                self._queue_transport_reactive_disembark_decisions(
                    player=player,
                    transport=transport,
                    enemy_unit=unit,
                    ability=ability,
                    trigger=trigger,
                )

    def _on_unit_move_ended_transport_reactive_disembark(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        action_name = (action or "").strip().lower()
        if action_name not in ("move", "advance", "fall_back"):
            return
        self._maybe_prompt_transport_reactive_disembark(unit, trigger=action_name)

    def _on_unit_set_up_transport_reactive_disembark(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        self._maybe_prompt_transport_reactive_disembark(unit, trigger="set_up")

    def _on_unit_set_up_grenade_pack_flyover(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "MOVEMENT_PHASE":
            return
        game_map = self.map
        if game_map is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or root is not unit:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        try:
            specs = list(root.unit_grenade_pack_flyover_specs() or [])
        except Exception:
            specs = []
        if not specs:
            return
        for spec in specs:
            if not spec.get("trigger_on_setup"):
                continue
            sr = getattr(root, "special_rules", None)
            if spec.get("once_per_turn") and isinstance(sr, dict):
                owner = str(sr.get("grenade_pack_flyover_used_turn_owner", "") or "")
                turn = int(sr.get("grenade_pack_flyover_used_turn", 0) or 0)
                if owner and owner == str(getattr(player, "id", "") or "") and int(getattr(self, "turn", 0) or 0) == turn:
                    continue
            candidates = self._collect_grenade_pack_flyover_candidates(root, spec, game_map)
            if not candidates:
                continue
            self._queue_grenade_pack_flyover_target_decision(
                player=player,
                unit=root,
                candidates=candidates,
                spec=spec,
            )

    def _on_unit_set_up_cry_of_the_wind(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not getattr(root, "is_alive", lambda: True)():
            return
        try:
            entries = list(root.iter_cry_of_the_wind_models() or [])
        except Exception:
            entries = []
        if not entries:
            return
        current_player = self.get_current_player()
        owner_id = str(getattr(current_player, "id", "") or "")
        turn = int(getattr(self, "turn", 0) or 0)
        for entry in list(entries):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            source = str(entry.get("source", "") or "Cry of the Wind").strip() or "Cry of the Wind"
            key = f"cry_of_the_wind:{get_entity_id(model)}:{turn}:{owner_id}"
            try:
                model.set_temporary_crit_on_successful_hit(
                    key=key,
                    source=source,
                    expires_turn=turn,
                    expires_turn_owner=owner_id,
                )
            except Exception:
                continue

    def _on_unit_set_up_setup_reactive_shoot_or_charge(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        self._record_setup_reactive_shoot_or_charge_candidate(unit)

    def _on_unit_disembarked_setup_reactive_shoot_or_charge(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        self._record_setup_reactive_shoot_or_charge_candidate(unit)

    def _kill_reward_spec_is_active_for_phase(self, spec: dict) -> bool:
        """Return True when a kill-reward spec is active in the current phase context."""
        if not isinstance(spec, dict):
            return False
        if not bool(spec.get("requires_fight_phase", False)):
            return True
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        return phase_name == "FIGHT_PHASE"

    def _apply_kill_reward_weapon_attacks_bonus(
        self,
        *,
        attacker_model=None,
        attacker_unit=None,
        target_unit=None,
        target_model=None,
        spec: Optional[dict] = None,
    ) -> None:
        """Apply persistent weapon Attacks bonuses granted by on-destroy kill-reward specs."""
        if attacker_model is None or not isinstance(spec, dict):
            return
        try:
            attacks_bonus = int(spec.get("attacks_bonus", 0) or 0)
        except Exception:
            attacks_bonus = 0
        if attacks_bonus <= 0:
            return
        weapon_name = str(spec.get("weapon_name", "") or "").strip()
        if not weapon_name:
            return
        set_bonus = getattr(attacker_model, "set_temporary_weapon_bonus", None)
        if not callable(set_bonus):
            return

        source = str(spec.get("source_ability", "") or "Kill reward").strip() or "Kill reward"
        attacker_id = str(get_entity_id(attacker_model) or "")
        target_id = str(get_entity_id(target_model) or get_entity_id(target_unit) or "")
        turn = int(getattr(self, "turn", 0) or 0)
        key = f"kill_reward_weapon_attacks:{attacker_id}:{target_id}:{turn}:{source}:{weapon_name}"
        key = re.sub(r"[^a-zA-Z0-9:_\\-]+", "_", key).strip("_")
        set_bonus(
            key=key,
            weapon_name=weapon_name,
            attacks_bonus=int(attacks_bonus),
            source=source,
            expires_phase="",
        )
        self.event_system.publish(
            "model_temporary_effect_applied",
            model=attacker_model,
            unit=attacker_unit,
            target_unit=target_unit,
            target_model=target_model,
            effect="weapon_attacks_bonus_on_destroy",
            weapon_name=weapon_name,
            attacks_bonus=int(attacks_bonus),
            reason=source,
        )

    def _on_model_destroyed_rules(self, attacker_model=None, attacker_unit=None, target_model=None, target_unit=None, **_kwargs) -> None:
        # Generic partial support for "gain CP when this model destroys an enemy KEYWORD unit/model".
        if attacker_unit is None or target_unit is None:
            return

        # Must be an enemy destroy event
        if attacker_unit.get_parent_army() == target_unit.get_parent_army():
            return

        specs = attacker_unit.get_kill_reward_specs(model=attacker_model) or []

        if specs:
            target_keywords = {str(k).upper() for k in getattr(target_unit, "keywords", []) or []}

            for spec in specs:
                if spec.get("trigger") != "model_destroyed":
                    continue

                if not self._kill_reward_spec_is_active_for_phase(spec):
                    continue

                # Optional restriction: melee only (Feared Interrogator)
                if spec.get("requires_melee", False):
                    wp = _kwargs.get("weapon_profile", None)
                    pw = getattr(wp, "parent_wargear", None)
                    if wp is None or pw is None or not pw.is_melee():
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
                    player = attacker_unit.get_parent_army().player
                    if player is None:
                        continue
                    gained = int(player.gain_command_points(cp, reason=spec.get("source_ability", "")) or 0)
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

                if spec.get("type") == "heal_on_destroy":
                    # Heal the destroying model (if present)
                    if attacker_model is None:
                        continue
                    heal_expr = spec.get("heal_expr")
                    if not heal_expr:
                        continue
                    from warhammer40k_ai.utility.dice import get_roll
                    amount = get_roll(heal_expr)
                    attacker_model.heal(amount)
                    self.event_system.publish(
                        "model_healed",
                        model=attacker_model,
                        unit=attacker_unit,
                        amount=amount,
                        reason=spec.get("source_ability", ""),
                    )

                if spec.get("type") == "weapon_attacks_bonus_on_destroy":
                    self._apply_kill_reward_weapon_attacks_bonus(
                        attacker_model=attacker_model,
                        attacker_unit=attacker_unit,
                        target_unit=target_unit,
                        target_model=target_model,
                        spec=spec,
                    )

        try:
            sr = getattr(attacker_unit, "special_rules", None)
        except Exception:
            sr = None
        if isinstance(sr, dict) and sr.get("enhancement_soulstealer"):
            if attacker_model is not None:
                bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
                attacker_id = str(getattr(attacker_model, "id", getattr(attacker_model, "_id", "")) or "")
                if not bearer_id or attacker_id == bearer_id:
                    wp = _kwargs.get("weapon_profile", None)
                    pw = getattr(wp, "parent_wargear", None)
                    if wp is not None and pw is not None and pw.is_melee():
                        from warhammer40k_ai.utility.dice import get_roll
                        roll = int(get_roll("D6") or 0)
                        bonus = 0
                        try:
                            army = attacker_unit.get_parent_army()
                        except Exception:
                            army = None
                        try:
                            mgr = getattr(army, "shadow_of_chaos", None) if army is not None else None
                            if mgr is not None and hasattr(mgr, "is_unit_within_shadow"):
                                game = getattr(getattr(army, "player", None), "game", None)
                                if mgr.is_unit_within_shadow(attacker_unit, game=game):
                                    bonus = 1
                        except Exception:
                            bonus = 0
                        total = int(roll) + int(bonus)
                        if total >= 4:
                            attacker_model.heal(1)
                            self.event_system.publish(
                                "model_healed",
                                model=attacker_model,
                                unit=attacker_unit,
                                amount=1,
                                reason="Soulstealer",
                            )

        from ..rules.reverberating_summons import (
            ABILITY_NAME,
            get_reverberating_summons_candidates,
            weapon_profile_has_reverberating_summons,
        )

        wp = _kwargs.get("weapon_profile", None)
        if not weapon_profile_has_reverberating_summons(wp):
            return
        if attacker_model is None:
            return
        player = attacker_unit.get_parent_army().player
        if player is None:
            return
        candidates = get_reverberating_summons_candidates(
            attacker_model,
            game_map=getattr(self, "map", None),
        )
        if not candidates:
            return

        if bool(getattr(player, "has_control", lambda: False)()):
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            if es is not None and isinstance(subs, dict) and subs.get("reverberating_summons_prompt"):
                es.publish(
                    "reverberating_summons_prompt",
                    player=player,
                    attacker_model=attacker_model,
                    candidates=list(candidates),
                    ability_name=ABILITY_NAME,
                    game=self,
                )
            return

        from .decisions import DecisionOption, DecisionRequest

        options = []
        for unit in candidates:
            options.append(
                DecisionOption.create(
                    str(getattr(unit, "name", "Unit") or "Unit"),
                    payload={"unit_id": get_entity_id(unit)},
                )
            )
        options.append(DecisionOption.create("None", payload={"action": "skip"}))
        req = DecisionRequest.create(
            DECISION_SELECT_REVERBERATING_SUMMONS_UNIT,
            "Select Plaguebearers unit for Reverberating Summons.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "engine_flow": True,
                "ability_name": ABILITY_NAME,
                "bearer_model_id": get_entity_id(attacker_model),
            },
        )
        self.request_decision(req)
        return

    def _on_model_destroyed_spirit_snare(
        self,
        attacker_model=None,
        attacker_unit=None,
        target_model=None,
        target_unit=None,
        game_map=None,
        **_kwargs,
    ) -> None:
        if target_model is None or target_unit is None:
            return
        try:
            owner_army = target_unit.get_parent_army()
        except Exception:
            owner_army = None
        if owner_army is None:
            return
        owner_player = getattr(owner_army, "player", None)
        if owner_player is None:
            return
        try:
            if not target_unit.has_any_keyword("THOUSAND SONS"):
                return
        except Exception:
            return
        model_has_psyker = False
        try:
            has_keyword = getattr(target_model, "has_keyword", None)
            if callable(has_keyword):
                model_has_psyker = bool(has_keyword("PSYKER"))
        except Exception:
            model_has_psyker = False
        if not model_has_psyker:
            try:
                model_keywords = [str(k).upper() for k in list(getattr(target_model, "keywords", []) or [])]
            except Exception:
                model_keywords = []
            model_has_psyker = "PSYKER" in model_keywords
        if not model_has_psyker:
            return

        cabal_mgr = getattr(owner_army, "cabal_of_sorcerers", None)
        unit_has_cabal = False
        if cabal_mgr is not None:
            unit_has_cabal = bool(getattr(cabal_mgr, "_unit_has_cabal", lambda _u: False)(target_unit))
        if not unit_has_cabal:
            return

        if game_map is None:
            game_map = getattr(self, "map", None)
        if game_map is None:
            return
        try:
            from ..utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return

        candidates = []
        seen = set()
        for unit in list(getattr(owner_army, "units", []) or []):
            if unit is None or not unit.is_alive():
                continue
            try:
                if not getattr(unit, "deployed", True):
                    continue
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                continue
            for model in list(getattr(unit, "models", []) or []):
                if not getattr(model, "is_alive", True):
                    continue
                model_id = str(get_entity_id(model) or "")
                if not model_id or model_id in seen:
                    continue
                if cabal_mgr is None or not bool(getattr(cabal_mgr, "_model_has_named_ability", lambda *_a: False)(model, "Spirit Snare")):
                    continue
                try:
                    if float(distance_between_models_bases_3d(model, target_model)) > 9.0 + 1e-6:
                        continue
                except Exception:
                    continue
                seen.add(model_id)
                candidates.append(model)

        if not candidates:
            return
        if len(candidates) == 1:
            self._apply_spirit_snare_bonus_to_model(
                model=candidates[0],
                player=owner_player,
                destroyed_model=target_model,
                ability_name="Spirit Snare",
            )
            return
        self._queue_spirit_snare_recipient_decision(
            player=owner_player,
            candidates=candidates,
            destroyed_model=target_model,
            ability_name="Spirit Snare",
        )

    def _on_unit_destroyed_phase_kill_tracking(self, unit=None, destroyed_by_unit=None, **_kwargs) -> None:
        """Track units that destroyed enemy units during Shooting/Fight phases."""
        if unit is None or destroyed_by_unit is None:
            return
        if destroyed_by_unit.get_parent_army() == unit.get_parent_army():
            return
        phase = getattr(self, "phase", None)
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname not in ("SHOOTING_PHASE", "FIGHT_PHASE"):
            return
        try:
            owner = destroyed_by_unit.get_parent_army().player
        except Exception:
            owner = None
        if owner is None:
            return
        try:
            root = destroyed_by_unit.get_attached_unit_root()
        except Exception:
            root = destroyed_by_unit
        uid = get_entity_id(root)
        if not uid:
            return
        tracked = self._phase_enemy_unit_destroyers.setdefault(pname, set())
        tracked.add(uid)

    def _on_model_destroyed_tally_of_pestilence(
        self,
        attacker_model=None,
        attacker_unit=None,
        target_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None and attacker_model is not None:
            attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None or target_unit is None:
            return
        if attacker_unit.get_parent_army() == target_unit.get_parent_army():
            return
        army = attacker_unit.get_parent_army()
        if army is None:
            return
        has_tally = getattr(army, "has_tally_of_pestilence", None)
        if not callable(has_tally) or not has_tally():
            return
        has_any_kw = getattr(attacker_unit, "has_any_keyword", None)
        if callable(has_any_kw):
            if not (has_any_kw("NURGLE") and has_any_kw("LEGIONES DAEMONICA")):
                return
        else:
            keywords = [
                str(k).upper()
                for k in list(getattr(attacker_unit, "keywords", []) or [])
                + list(getattr(attacker_unit, "faction_keywords", []) or [])
            ]
            if "NURGLE" not in keywords or "LEGIONES DAEMONICA" not in keywords:
                return
        current = int(getattr(army, "tally_of_pestilence", 0) or 0)
        army.tally_of_pestilence = current + 1

    def _on_model_destroyed_phase_kill_tracking(
        self,
        attacker_unit=None,
        target_unit=None,
        **_kwargs,
    ) -> None:
        """Track units that destroyed enemy models during the Fight phase."""
        if attacker_unit is None or target_unit is None:
            return
        if attacker_unit.get_parent_army() == target_unit.get_parent_army():
            return
        phase = getattr(self, "phase", None)
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        uid = get_entity_id(root)
        if not uid:
            return
        tracked = self._phase_enemy_model_destroyers.setdefault(pname, set())
        tracked.add(uid)

    def _on_unit_destroyed_rules(self, unit=None, destroyed_by_unit=None, destroyed_by_model=None, destroyed_by_weapon_profile=None, **_kwargs) -> None:
        # Generic partial support for "... destroys an enemy <KEYWORD> unit, gain X CP".
        if unit is None or destroyed_by_unit is None:
            return

        if destroyed_by_unit.get_parent_army() == unit.get_parent_army():
            return

        def _norm_ability_name(value: str) -> str:
            text = str(value or "").replace("\u2019", "'").replace("\u2018", "'").lower()
            text = re.sub(r"[^a-z0-9]+", " ", text)
            return re.sub(r"\s+", " ", text).strip()

        try:
            attacker_root = destroyed_by_unit.get_attached_unit_root()
        except Exception:
            attacker_root = destroyed_by_unit

        # Custom: Vox-diabolus (Vessels of Wrath) has a conditional D6 roll gate.
        # Skip the generic gain-CP parser for this named source to avoid incorrect auto-grants.
        skip_cp_sources: set[str] = set()
        vox_sources: list = []
        killing_clarity_sources: list = []
        try:
            members = list(attacker_root.get_attached_unit_members() or [])
        except Exception:
            members = [attacker_root]
        for member in list(members or []):
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_vox_diabolus"):
                vox_sources.append(member)
            if isinstance(sr, dict) and sr.get("enhancement_killing_clarity"):
                killing_clarity_sources.append(member)
        if vox_sources:
            skip_cp_sources.add("vox diabolus")
            wp = destroyed_by_weapon_profile
            pw = getattr(wp, "parent_wargear", None)
            is_melee = bool(wp is not None and pw is not None and pw.is_melee())
            if is_melee:
                army = attacker_root.get_parent_army()
                we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                if we_mgr is not None and we_mgr.is_vessels_of_wrath():
                    player = getattr(army, "player", None)
                    for source in vox_sources:
                        if player is None:
                            break
                        source_sr = getattr(source, "special_rules", None)
                        if not isinstance(source_sr, dict):
                            continue
                        bearer = None
                        bearer_id = str(source_sr.get("enhancement_bearer_model_id", "") or "")
                        if bearer_id:
                            for model in list(getattr(source, "models", []) or []):
                                model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                                if model_id and model_id == bearer_id:
                                    bearer = model
                                    break
                        if bearer is None:
                            get_bearer = getattr(source, "_get_enhancement_bearer_model", None)
                            if callable(get_bearer):
                                bearer = get_bearer()
                        is_vessel = False
                        if bearer is not None:
                            try:
                                is_vessel = bool(getattr(bearer, "has_keyword", lambda _k: False)("VESSEL OF WRATH"))
                            except Exception:
                                is_vessel = False
                        roll = int(get_roll("D6"))
                        total = int(roll + (1 if is_vessel else 0))
                        if total < 4:
                            continue
                        gained = int(player.gain_command_points(1, reason="Vox-diabolus") or 0)
                        self.event_system.publish(
                            "command_points_gained",
                            player=player,
                            amount=gained,
                            reason="Vox-diabolus",
                            attacker_unit=attacker_root,
                            target_unit=unit,
                            attacker_model=destroyed_by_model,
                            roll=int(roll),
                            modified_roll=int(total),
                        )
        if killing_clarity_sources:
            skip_cp_sources.add("killing clarity")
            army = attacker_root.get_parent_army()
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is not None and we_mgr.is_possessed_slaughterband():
                player = getattr(army, "player", None)
                for source in killing_clarity_sources:
                    if player is None:
                        break
                    source_sr = getattr(source, "special_rules", None)
                    if not isinstance(source_sr, dict):
                        continue
                    threshold = int(source_sr.get("enhancement_killing_clarity_success_on", 4) or 4)
                    roll = int(get_roll("D6"))
                    if roll < threshold:
                        continue
                    gained = int(player.gain_command_points(1, reason="Killing Clarity") or 0)
                    self.event_system.publish(
                        "command_points_gained",
                        player=player,
                        amount=gained,
                        reason="Killing Clarity",
                        attacker_unit=attacker_root,
                        target_unit=unit,
                        attacker_model=destroyed_by_model,
                        roll=int(roll),
                    )

        specs = destroyed_by_unit.get_kill_reward_specs(model=destroyed_by_model) or []
        target_keywords = {str(k).upper() for k in getattr(unit, "keywords", []) or []}

        if specs:
            for spec in specs:
                if spec.get("trigger") != "unit_destroyed":
                    continue

                if not self._kill_reward_spec_is_active_for_phase(spec):
                    continue

                # Optional restriction: melee only
                if spec.get("requires_melee", False):
                    wp = destroyed_by_weapon_profile
                    pw = getattr(wp, "parent_wargear", None)
                    if wp is None or pw is None or not pw.is_melee():
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
                    source_norm = _norm_ability_name(spec.get("source_ability", ""))
                    if source_norm in skip_cp_sources:
                        continue
                    cp = int(spec.get("cp", 1) or 1)
                    player = destroyed_by_unit.get_parent_army().player
                    if player is None:
                        continue
                    gained = int(player.gain_command_points(cp, reason=spec.get("source_ability", "")) or 0)
                    self.event_system.publish(
                        "command_points_gained",
                        player=player,
                        amount=gained,
                        reason=spec.get("source_ability", ""),
                        attacker_unit=destroyed_by_unit,
                        target_unit=unit,
                        attacker_model=destroyed_by_model,
                    )

                if spec.get("type") == "heal_on_destroy":
                    if destroyed_by_model is None:
                        continue
                    heal_expr = spec.get("heal_expr")
                    if not heal_expr:
                        continue
                    amount = get_roll(heal_expr)
                    destroyed_by_model.heal(amount)
                    self.event_system.publish(
                        "model_healed",
                        model=destroyed_by_model,
                        unit=destroyed_by_unit,
                        amount=amount,
                        reason=spec.get("source_ability", ""),
                    )

                if spec.get("type") == "weapon_attacks_bonus_on_destroy":
                    self._apply_kill_reward_weapon_attacks_bonus(
                        attacker_model=destroyed_by_model,
                        attacker_unit=destroyed_by_unit,
                        target_unit=unit,
                        target_model=None,
                        spec=spec,
                    )

        hunter_rule = None
        if destroyed_by_model is not None:
            get_rule = getattr(destroyed_by_unit, "get_hunter_of_souls_rule", None)
            if callable(get_rule):
                hunter_rule = get_rule(destroyed_by_model)
        if hunter_rule and destroyed_by_model is not None:
            try:
                is_character = bool(unit.has_any_keyword("CHARACTER"))
            except Exception:
                is_character = False
            if is_character:
                try:
                    is_psyker = bool(unit.has_any_keyword("PSYKER"))
                except Exception:
                    is_psyker = False
                if is_psyker:
                    amount = int(hunter_rule.get("heal_if_target_psyker", 0) or 0)
                else:
                    heal_expr = str(hunter_rule.get("heal_expr", "") or "").strip().upper()
                    amount = int(get_roll(heal_expr) or 0) if heal_expr else 0
                if amount > 0:
                    destroyed_by_model.heal(int(amount))
                    self.event_system.publish(
                        "model_healed",
                        model=destroyed_by_model,
                        unit=destroyed_by_unit,
                        amount=int(amount),
                        reason=str(hunter_rule.get("source", "") or "Hunter of Souls"),
                    )

    def _on_unit_destroyed_battleshock_on_kill(
        self,
        unit=None,
        destroyed_by_unit=None,
        destroyed_by_model=None,
        last_model=None,
        game_map=None,
        **_kwargs,
    ) -> None:
        """On-kill: enemy units within range of the destroyed unit take Battle-shock tests."""
        if unit is None:
            return

        attacker_unit = destroyed_by_unit
        if attacker_unit is None and destroyed_by_model is not None:
            attacker_unit = getattr(destroyed_by_model, "parent_unit", None)
        if attacker_unit is None:
            return

        try:
            if attacker_unit.get_parent_army() == unit.get_parent_army():
                return
        except Exception:
            return

        if game_map is None:
            game_map = getattr(self, "map", None)
        if game_map is None or last_model is None:
            return

        specs: list[dict] = []
        try:
            if destroyed_by_model is not None:
                specs.extend(attacker_unit.model_on_kill_battleshock_specs(destroyed_by_model) or [])
        except Exception:
            specs = []
        try:
            specs.extend(attacker_unit.unit_on_kill_battleshock_specs() or [])
        except Exception:
            pass
        if not specs:
            return

        unique_specs: list[dict] = []
        seen_specs: set[tuple[str, int]] = set()
        for spec in specs:
            try:
                rng = int(spec.get("range", 0) or 0)
            except Exception:
                rng = 0
            if rng <= 0:
                continue
            source = str(spec.get("source", "") or "").strip().lower()
            key = (source, int(rng))
            if key in seen_specs:
                continue
            seen_specs.add(key)
            unique_specs.append({"range": int(rng), "source": spec.get("source", "")})

        if not unique_specs:
            return

        try:
            enemies = list(game_map.get_enemy_units(attacker_unit) or [])
        except Exception:
            enemies = []
        if not enemies:
            return

        enemy_roots: list[Unit] = []
        seen_ids: set[str] = set()
        for enemy in enemies:
            if enemy is None:
                continue
            try:
                root = enemy.get_attached_unit_root()
            except Exception:
                root = enemy
            if root is None or not root.is_alive():
                continue
            if root is unit:
                continue
            try:
                if not getattr(root, "deployed", True):
                    continue
                if root.is_in_reserves() or root.is_embarked:
                    continue
            except Exception:
                pass
            rid = str(get_entity_id(root) or "")
            if rid:
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
            enemy_roots.append(root)

        if not enemy_roots:
            return

        for spec in unique_specs:
            try:
                rng = float(spec.get("range", 0) or 0)
            except Exception:
                rng = 0.0
            if rng <= 0:
                continue
            for enemy_root in enemy_roots:
                try:
                    if not self._unit_within_range_of_model(
                        last_model,
                        enemy_root,
                        range_value=rng,
                        allow_destroyed_source=True,
                    ):
                        continue
                except Exception:
                    continue
                enemy_root.take_battle_shock_test(int(getattr(self, "turn", 0) or 1))

    def _on_unit_destroyed_bloodshed_points(self, unit=None, destroyed_by_unit=None, **_kwargs) -> None:
        """World Eaters: Icon of Khorne grants Bloodshed points on enemy unit destruction."""
        if unit is None or destroyed_by_unit is None:
            return
        if destroyed_by_unit.get_parent_army() == unit.get_parent_army():
            return
        root = destroyed_by_unit.get_attached_unit_root()
        if not root.attached_unit_has_icon_of_khorne():
            return
        army = root.get_parent_army()
        if army is None:
            raise RuntimeError("Bloodshed points require an army.")
        fid = str(getattr(army, "faction_id", "") or "").strip().upper()
        if fid and fid != "WE":
            return
        mgr = getattr(army, "blessings_of_khorne", None)
        if mgr is None:
            return
        mgr.bloodshed_points = int(getattr(mgr, "bloodshed_points", 0) or 0) + 1
        self.event_system.publish(
            "bloodshed_points_gained",
            player=army.player,
            amount=1,
            total=int(getattr(mgr, "bloodshed_points", 0) or 0),
            attacker_unit=root,
            target_unit=unit,
        )

    def _on_unit_destroyed_blood_tithe(self, unit=None, destroyed_by_unit=None, **_kwargs) -> None:
        """World Eaters: Blood Tithe points (Khorne Daemonkin detachment)."""
        if unit is None:
            return

        def _publish_btp_update(*, player, total, amount, attacker_unit=None, target_unit=None, roll=None, source=""):
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

        # Enhancement: Blood-forged Armour (bearer destroyed -> gain 1 BTP).
        bearer_army = unit.get_parent_army()
        we_mgr = getattr(bearer_army, "world_eaters_detachments", None) if bearer_army is not None else None
        if we_mgr is not None and we_mgr.is_khorne_daemonkin():
            sr = getattr(unit, "special_rules", None)
            has_blood_forged = isinstance(sr, dict) and sr.get("enhancement_blood_forged_armour", False)
            if has_blood_forged:
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

        if destroyed_by_unit is None:
            return
        if destroyed_by_unit.get_parent_army() == unit.get_parent_army():
            return
        root = destroyed_by_unit.get_attached_unit_root()
        army = root.get_parent_army()
        if army is None:
            raise RuntimeError("Blood Tithe requires an army.")
        we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if we_mgr is None or not we_mgr.is_khorne_daemonkin():
            return
        if not we_mgr.unit_is_blood_tithe_eligible(root):
            return

        def _attached_unit_has_rule(u, key: str) -> bool:
            root_unit = u.get_attached_unit_root()
            members = list(root_unit.get_attached_unit_members() or [])
            if not members:
                members = [root_unit]
            for member in members:
                sr = getattr(member, "special_rules", None)
                if isinstance(sr, dict) and sr.get(key, False):
                    return True
            return False

        # Enhancement: Blade of Endless Bloodshed (melee kill -> auto gain 1 BTP).
        wp = _kwargs.get("destroyed_by_weapon_profile", None)
        is_melee = False
        parent = getattr(wp, "parent_wargear", None)
        if parent is not None and parent.is_melee():
            is_melee = True
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

        from warhammer40k_ai.utility.dice import get_roll
        roll = int(get_roll("D6"))
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

    def _get_emperors_children_manager(self, army):
        if army is None:
            return None
        mgr = getattr(army, "emperors_children", None)
        if mgr is not None:
            return mgr
        return getattr(army, "emperors_children_detachments", None)

    def _on_battle_round_started_emperors_children(self, game=None, battle_round: int = 0, **_kwargs) -> None:
        br = int(battle_round or getattr(self, "turn", 0) or 0)
        if br <= 0:
            return
        for player in list(getattr(self, "players", []) or []):
            army = self._get_player_army(player)
            mgr = self._get_emperors_children_manager(army)
            if mgr is None:
                continue
            mgr.on_battle_round_start(self)
            if not getattr(mgr, "is_coterie_of_conceited", lambda: False)():
                continue
            if not getattr(mgr, "warlord_on_battlefield", lambda: False)():
                continue
            if not bool(getattr(self, "is_authoritative", True)):
                continue

            army_id = get_entity_id(army)
            existing = [
                req
                for req in self.decision_queue.list()
                if req.decision_type == DECISION_CHOOSE_PLEDGE
                and str(req.context.get("army_id", "") or "") == army_id
            ]
            if existing:
                continue

            alive_enemies = [
                u
                for u in self.get_enemy_units(player)
                if hasattr(u, "is_alive") and bool(u.is_alive())
            ]
            max_value = max(1, len(alive_enemies))
            default_value = int(getattr(mgr, "pledge_target", 0) or 0)
            if default_value <= 0 or default_value > max_value:
                default_value = 1

            options = [
                DecisionOption.create(
                    label=str(value),
                    payload={"pledge_value": int(value), "army_id": army_id},
                )
                for value in range(1, max_value + 1)
            ]
            context = {
                "army_id": army_id,
                "battle_round": br,
                "max_value": max_value,
                "ability_name": PLEDGES_TO_THE_DARK_PRINCE_NAME,
            }
            request = DecisionRequest.create(
                DECISION_CHOOSE_PLEDGE,
                "Pledges to the Dark Prince: select your pledge value.",
                player_id=player.id,
                options=options,
                context=context,
            )
            self.request_decision(request)
            if getattr(self, "event_system", None) is not None:
                self.event_system.publish(
                    "emperors_children_pledge_prompt",
                    player=player,
                    game=self,
                    battle_round=br,
                    max_value=max_value,
                    default_value=default_value,
                    manager=mgr,
                )

    def _on_battle_round_started_start_of_battle_keyword_rerolls(
        self,
        game=None,
        battle_round: int = 0,
        **_kwargs,
    ) -> None:
        br = int(battle_round or getattr(self, "turn", 0) or 0)
        if br != 1:
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return

        queue = getattr(self, "decision_queue", None)

        def _has_pending(model_id: str, ability_key: str) -> bool:
            if queue is None:
                return False
            for req in list(getattr(queue, "list", lambda: [])() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_START_OF_BATTLE_KEYWORD:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("model_id", "") or "") != str(model_id):
                    continue
                if str(ctx.get("ability_key", "") or "") != str(ability_key):
                    continue
                return True
            return False

        for player in list(getattr(self, "players", []) or []):
            army = self._get_player_army(player)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                for model in list(getattr(unit, "models", []) or []):
                    if model is None or not bool(getattr(model, "is_alive", True)):
                        continue
                    specs = unit.model_start_of_battle_keyword_reroll_ones_specs(model) or []
                    if not specs:
                        continue
                    unit_id = get_entity_id(unit)
                    model_id = get_entity_id(model)
                    for spec in list(specs or []):
                        ability_key = str(spec.get("ability_key", "") or spec.get("source", "") or "").strip().lower()
                        if not ability_key:
                            ability_key = f"{model_id}:start_of_battle_keyword_rerolls"
                        if unit.get_start_of_battle_keyword_reroll_choice(model, ability_key=ability_key):
                            continue
                        if _has_pending(model_id, ability_key):
                            continue
                        keywords = list(spec.get("keywords", []) or [])
                        if not keywords:
                            continue
                        options = [
                            DecisionOption.create(
                                kw,
                                payload={
                                    "keyword": kw,
                                    "unit_id": unit_id,
                                    "model_id": model_id,
                                    "ability_key": ability_key,
                                    "ability_name": spec.get("source", ""),
                                },
                            )
                            for kw in keywords
                        ]
                        if not options:
                            continue
                        prompt = f"Select keyword for {getattr(model, 'name', 'Model')}."
                        context = {
                            "ability": "start_of_battle_keyword_reroll",
                            "ability_name": spec.get("source", ""),
                            "ability_key": ability_key,
                            "unit_id": unit_id,
                            "model_id": model_id,
                            "battle_round": br,
                        }
                        request = DecisionRequest.create(
                            DECISION_CHOOSE_START_OF_BATTLE_KEYWORD,
                            prompt,
                            player_id=getattr(player, "id", None),
                            options=options,
                            context=context,
                        )
                        self.request_decision(request)

    def _on_unit_destroyed_emperors_children(self, unit=None, destroyed_by_unit=None, **_kwargs) -> None:
        if unit is None or destroyed_by_unit is None:
            return
        attacker_army = destroyed_by_unit.get_parent_army() if hasattr(destroyed_by_unit, "get_parent_army") else None
        mgr = self._get_emperors_children_manager(attacker_army)
        if mgr is None:
            return
        mgr.record_enemy_unit_destroyed(unit, destroyed_by_unit, game=self)

    def _alive_model_count(self, unit) -> int:
        if unit is None:
            return 0
        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        count = 0
        for m in models:
            alive = getattr(m, "is_alive", True)
            if callable(alive):
                alive = alive()
            if alive:
                count += 1
        return int(count)

    def _count_enemy_models_in_engagement_range(self, unit, model) -> int:
        if unit is None or model is None:
            return 0
        game_map = getattr(self, "map", None)
        if game_map is None:
            return 0
        try:
            enemy_units = list(game_map.get_enemy_units(unit) or [])
        except Exception:
            enemy_units = []
        if not enemy_units:
            return 0
        from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
        from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL

        count = 0
        for enemy in enemy_units:
            if enemy is None:
                continue
            try:
                if not enemy.is_alive() or not getattr(enemy, "deployed", True):
                    continue
            except Exception:
                continue
            try:
                if enemy.is_in_reserves() or enemy.is_embarked:
                    continue
            except Exception:
                pass
            get_models = getattr(enemy, "get_models_for_collision", None)
            if callable(get_models):
                e_models = list(get_models() or [])
            else:
                e_models = list(getattr(enemy, "models", []) or [])
            for e_model in e_models:
                alive = getattr(e_model, "is_alive", True)
                if callable(alive):
                    alive = alive()
                if not alive:
                    continue
                try:
                    h = float(horizontal_distance_between_bases_2d(model.model_base, e_model.model_base))
                    v = float(vertical_distance_between_bases(model.model_base, e_model.model_base))
                except Exception:
                    continue
                if h <= ENGAGEMENT_RANGE_HORIZONTAL and v <= ENGAGEMENT_RANGE_VERTICAL:
                    count += 1
        return int(count)

    def _rise_to_challenge_candidates(self, player) -> list:
        if player is None:
            return []
        game_map = getattr(self, "map", None)
        if game_map is None:
            return []
        army = self._get_player_army(player)
        if army is None:
            return []
        candidates = []
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
            except Exception:
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_rise_to_challenge"):
                continue
            if sr.get("enhancement_rise_to_challenge_used"):
                continue
            try:
                if not self._unit_has_keyword(unit, "INFANTRY"):
                    continue
            except Exception:
                continue
            get_models = getattr(unit, "get_models_for_collision", None)
            if callable(get_models):
                models = list(get_models() or [])
            else:
                models = list(getattr(unit, "models", []) or [])
            bearer = None
            for model in models:
                alive = getattr(model, "is_alive", True)
                if callable(alive):
                    alive = alive()
                if alive:
                    bearer = model
                    break
            if bearer is None:
                continue
            if self._count_enemy_models_in_engagement_range(unit, bearer) < 3:
                continue
            candidates.append(unit)
        return candidates

    def _on_unit_destroyed_power_from_pain(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Power from Pain requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Power from Pain requires an army for {p.name}.")
            mgr = getattr(army, "power_from_pain", None)
            if mgr is None:
                continue
            mgr.on_enemy_unit_destroyed(unit)

    def _on_unit_destroyed_martial_leverage(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        for p in list(self.players or []):
            if p is None:
                continue
            army = p.get_army()
            if army is None:
                continue
            mgr = getattr(army, "leagues_of_votann_detachments", None)
            if mgr is None:
                continue
            delta = int(mgr.martial_leverage_on_unit_destroyed(unit, game=self) or 0)
            if not delta:
                continue
            pe = getattr(army, "prioritised_efficiency", None)
            if pe is None:
                continue
            try:
                self.event_system.publish(
                    "prioritised_efficiency_updated",
                    player=p,
                    game=self,
                    delta=int(delta or 0),
                    mode=getattr(pe, "mode", None),
                    yield_points=int(getattr(pe, "yield_points", 0) or 0),
                    reason="Martial Leverage",
                )
            except Exception:
                continue

    def _on_unit_destroyed_seized_opportunity(self, unit=None, destroyed_by_unit=None, **_kwargs) -> None:
        if unit is None or destroyed_by_unit is None:
            return
        try:
            if destroyed_by_unit.get_parent_army() is unit.get_parent_army():
                return
        except Exception:
            return
        try:
            source_root = destroyed_by_unit.get_attached_unit_root()
        except Exception:
            source_root = destroyed_by_unit
        if source_root is None:
            return
        has_rule = getattr(source_root, "has_seized_opportunity", None)
        if not callable(has_rule) or not bool(has_rule()):
            return
        source_army = source_root.get_parent_army()
        if source_army is None:
            return
        player = getattr(source_army, "player", None)
        if player is None:
            return
        pe = getattr(source_army, "prioritised_efficiency", None)
        if pe is None:
            return
        used_this_phase = getattr(player, "_ability_used_this_phase", None)
        if callable(used_this_phase) and bool(used_this_phase("seized_opportunity")):
            return
        phase_fn = getattr(player, "_phase_key", None)
        phase_key = ""
        if callable(phase_fn):
            try:
                phase_key = ":".join(str(v) for v in tuple(phase_fn()))
            except Exception:
                phase_key = ""
        if not phase_key:
            phase_obj = getattr(self, "phase", None)
            phase_name = str(getattr(phase_obj, "name", "") or phase_obj or "").strip().upper()
            phase_key = f"{int(getattr(self, 'turn', 0) or 0)}:{phase_name}:{int(getattr(self, 'current_player_index', -1) or -1)}"
        source_unit_id = str(get_entity_id(source_root) or "")
        destroyed_unit_id = str(get_entity_id(unit) or "")
        ability_name = "Seized Opportunity"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="seized_opportunity",
            ability_name=ability_name,
            message=f"{ability_name}: gain 1 YP?",
            context={
                "ability_name": ability_name,
                "phase": str(getattr(getattr(self, "phase", None), "name", "") or ""),
                "unit_id": source_unit_id,
                "source_unit_id": source_unit_id,
                "destroyed_unit_id": destroyed_unit_id,
                "destroyed_unit": str(getattr(unit, "name", "") or "Unit"),
            },
            payload={
                "unit_id": source_unit_id,
                "source_unit_id": source_unit_id,
                "destroyed_unit_id": destroyed_unit_id,
            },
            instance_key=f"{phase_key}:seized_opportunity",
        )

    def _on_unit_destroyed_cult_ambush(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        army = unit.get_parent_army()
        mgr = getattr(army, "cult_ambush", None) if army is not None else None
        if mgr is None:
            return
        if not mgr.can_spend_for_unit(unit):
            return
        player = getattr(army, "player", None)
        if player is None:
            raise RuntimeError("Cult Ambush requires a player.")
        unit_id = maybe_entity_id(unit)
        ctx = {
            "ability_name": "Cult Ambush",
            "unit": getattr(unit, "name", "") or "",
            "unit_id": unit_id,
            "cost": mgr.resurgence_cost_for_unit(unit),
            "points": int(getattr(mgr, "resurgence_points", 0) or 0),
        }
        message = (
            f"Use Cult Ambush to return {getattr(unit, 'name', 'Unit')} to Cult Ambush?"
        )
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="cult_ambush",
            ability_name="Cult Ambush",
            message=message,
            context=ctx,
            payload={"unit_id": unit_id},
            instance_key=str(unit_id or ""),
        )

    def _on_unit_destroyed_friendly_unit_destroyed_reposition(self, unit=None, last_model=None, **_kwargs) -> None:
        if unit is None or last_model is None:
            return
        army = unit.get_parent_army()
        if army is None:
            return
        owner = getattr(army, "player", None)
        if owner is None:
            return
        current_player = self.get_current_player()
        if current_player is owner:
            return
        current_player_id = getattr(current_player, "id", None)

        pos = None
        if hasattr(last_model, "get_location"):
            pos = last_model.get_location()
        if pos is None:
            try:
                pos = unit.position
            except Exception:
                pos = None
        if pos is None:
            return

        game_map = getattr(self, "map", None)
        for candidate in list(getattr(army, "units", []) or []):
            if candidate is None:
                continue
            try:
                root = candidate.get_attached_unit_root()
            except Exception:
                root = candidate
            if root is None:
                continue
            if root is unit:
                continue
            ability = root.get_opponent_turn_friendly_unit_destroyed_reposition_ability()
            if not ability:
                continue
            if not self._unit_on_battlefield_for_reposition(root):
                continue
            if self._opponent_turn_destroyed_reposition_used(root, turn_owner_id=current_player_id):
                continue
            keyword = str(ability.get("keyword") or "").strip()
            if keyword:
                try:
                    if not root._unit_matches_keyword_phrase(unit, keyword, use_effective=False):
                        continue
                except Exception:
                    continue
            placement = self._find_closest_valid_reposition_position(root, pos, game_map=game_map)
            if placement is None:
                continue
            unit_id = maybe_entity_id(root)
            destroyed_unit_id = maybe_entity_id(unit)
            ability_name = str(ability.get("name") or "Reposition").strip()
            ctx = {
                "ability_name": ability_name,
                "phase": "Opponent's turn",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "destroyed_unit": getattr(unit, "name", "") or "",
                "destroyed_unit_id": destroyed_unit_id,
                "destroyed_position": list(pos) if isinstance(pos, (list, tuple)) else None,
                "placement_position": list(placement),
                "turn_owner_id": str(current_player_id or ""),
                "turn": int(getattr(self, "turn", 0) or 0),
            }
            message = (
                f"{getattr(root, 'name', 'Model')} can reposition after a friendly unit was destroyed.\n\n"
                "Use this ability?"
            )
            self._queue_optional_ability_confirmation(
                player=owner,
                ability_key="opponent_turn_destroyed_reposition",
                ability_name=ability_name or "Reposition",
                message=message,
                context=ctx,
                payload={
                    "unit_id": unit_id,
                    "destroyed_unit_id": destroyed_unit_id,
                },
                instance_key=f"{unit_id}:{destroyed_unit_id}:{ctx['turn']}:{ctx['turn_owner_id']}",
            )

    def _on_unit_move_ended_cult_ambush(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Cult Ambush requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Cult Ambush requires an army for {p.name}.")
            mgr = getattr(army, "cult_ambush", None)
            if mgr is None:
                continue
            mgr.on_enemy_unit_move_ended(unit, game=self)

    def _on_unit_destroyed_acts_of_faith(self, unit=None, last_model=None, **_kwargs) -> None:
        if unit is None:
            return
        army = unit.get_parent_army()
        mgr = getattr(army, "acts_of_faith", None) if army is not None else None
        if mgr is None:
            return
        mgr.on_unit_destroyed(unit, game=self, game_map=self.map, last_model=last_model)

    def _on_model_destroyed_acts_of_faith(self, unit=None, model=None, **_kwargs) -> None:
        if unit is None or model is None:
            return
        army = unit.get_parent_army()
        mgr = getattr(army, "acts_of_faith", None) if army is not None else None
        if mgr is None:
            return
        mgr.on_model_destroyed(unit, model, game=self, game_map=self.map)

    def _on_unit_destroyed_transport_rules(self, unit=None, last_model=None, game_map=None, **_kwargs) -> None:
        """
        10th edition core Transport rule: when a Transport is destroyed, any embarked units must
        immediately disembark (or emergency disembark), take mortal wounds, and become battle-shocked.
        """
        if unit is None or game_map is None:
            return
        if not getattr(unit, "is_transport", False):
            return

        # ORKS: CAREEN! defers emergency disembark until after the move/explosion resolves.
        try:
            if bool(getattr(unit, "_careen_pending_destroyed", False)):
                unit._careen_pending_transport_disembark = True
                return
        except Exception:
            pass

        passengers = list(getattr(unit, "transport_passengers", []) or [])
        if not passengers:
            return

        # Capture last known transport base for disembark distance checks.
        if last_model is not None and getattr(last_model, "model_base", None) is not None:
            unit._last_known_base = copy.deepcopy(last_model.model_base)

        for p in passengers:
            # Ensure passenger is not still in map list before disembarking (avoid duplicates)
            if hasattr(game_map, "units") and p in game_map.units:
                game_map.units.remove(p)
            p.disembark(
                game_map=game_map,
                transport_unit=unit,
                destroyed_transport=True,
                emergency=False,
                current_turn=self.turn,
            )

        # Clear passengers list (disembark() should already remove them, but be defensive)
        unit.transport_passengers = []

    def add_command(self, command: str) -> None:
        """Add a command to the game."""
        self.commands.append(command)

    def enqueue_command(self, command: GameCommand) -> None:
        """Queue a structured command for later processing."""
        if command is None:
            return
        self.command_queue.append(command)

    def _enter_command_context(self) -> None:
        self._command_context_depth += 1

    def _exit_command_context(self) -> None:
        self._command_context_depth = max(0, self._command_context_depth - 1)

    def in_command_context(self) -> bool:
        return self._command_context_depth > 0

    def apply_command(self, command: GameCommand):
        """Validate and apply a command; returns CommandResult."""
        from .command_dispatcher import dispatch_command

        with game_context(self):
            result = dispatch_command(self, command)
        event_log = getattr(self, "event_log", None)
        if event_log is not None and command is not None:
            payload = {
                "command_id": getattr(command, "command_id", ""),
                "kind": getattr(command, "kind", ""),
                "player_id": getattr(command, "player_id", None),
                "payload": encode_refs(getattr(command, "payload", {}) or {}),
                "metadata": encode_refs(getattr(command, "metadata", {}) or {}),
            }
            event_type = "command_applied" if getattr(result, "ok", False) else "command_rejected"
            event_log.record(
                event_type,
                actor_id=payload.get("player_id"),
                payload=payload,
                validate_payload=False,
            )
        return result

    def process_command_queue(self, *, limit: int | None = None):
        """Process queued commands in order; returns list of CommandResult."""
        results = []
        remaining = None if limit is None else int(limit)
        while self.command_queue and (remaining is None or remaining > 0):
            cmd = self.next_command()
            if cmd is None:
                break
            results.append(self.apply_command(cmd))
            if remaining is not None:
                remaining -= 1
        return results

    def next_command(self) -> GameCommand | None:
        """Pop the next queued command, if any."""
        if not self.command_queue:
            return None
        return self.command_queue.pop(0)

    def request_decision(self, request: DecisionRequest) -> None:
        """Queue a decision request (interrupt window)."""
        if request is None:
            return
        request.finalize_candidates()
        # Ensure dice roll state exists on clients for dice roll decisions.
        try:
            from .decision_kinds import DECISION_REQUEST_DICE_ROLL, DECISION_SELECT_DICE_REROLL
            if request.decision_type in (DECISION_REQUEST_DICE_ROLL, DECISION_SELECT_DICE_REROLL):
                ctx = dict(getattr(request, "context", {}) or {})
                roll_id = ctx.get("roll_id")
                if roll_id is not None and self.roll_manager is not None:
                    if self.roll_manager.get_roll(int(roll_id)) is None:
                        from .dice_rolls import DiceRollState
                        spec = dict(ctx.get("roll_spec", {}) or {})
                        self.roll_manager.rolls[int(roll_id)] = DiceRollState(
                            roll_id=int(roll_id),
                            player_id=request.player_id,
                            spec=spec,
                            status="pending",
                        )
        except Exception:
            pass
        ctx = dict(getattr(request, "context", {}) or {})
        ruleset_ctx = self.get_ruleset_context()
        for key, value in ruleset_ctx.items():
            if key not in ctx:
                ctx[key] = value
            elif ctx.get(key) != value:
                raise ValueError(f"Decision context ruleset mismatch for {key}: {ctx.get(key)} != {value}")
        plan_player_id = str(getattr(request, "player_id", "") or "")
        if not plan_player_id:
            current_player = self.get_current_player() if self.players else None
            plan_player_id = str(getattr(current_player, "id", "") or "")
        if plan_player_id:
            plan = self.get_or_create_tier1_plan(plan_player_id)
            tier2_bundle = self.get_or_create_tier2_task_bundle(plan_player_id)
            if "plan_id" not in ctx:
                ctx["plan_id"] = plan.plan_id
            if "turn_plan" not in ctx:
                ctx["turn_plan"] = plan.to_dict()
            if "cp_reserve_policy" not in ctx:
                ctx["cp_reserve_policy"] = dict(tier2_bundle.cp_reserve_policy or {})
            unit_id = str(ctx.get("unit_id", "") or "")
            task = tier2_bundle.tasks_by_unit_id.get(unit_id) if unit_id else None
            if task is not None:
                if "tier2_task" not in ctx:
                    ctx["tier2_task"] = task.to_dict()
                if "movement_intent" not in ctx:
                    ctx["movement_intent"] = task.movement_intent.to_dict()
                if "compute_tier" not in ctx:
                    ctx["compute_tier"] = str(task.compute_tier)
            if "compute_tier" not in ctx:
                ctx["compute_tier"] = "P1"
        time_manager = getattr(self, "time_manager", None)
        if time_manager is None:
            time_manager = TimeManager()
            self.time_manager = time_manager
        ctx = time_manager.decorate_context(request.decision_type, ctx)
        if request.decision_type == DECISION_MOVE_UNIT:
            if getattr(self, "path_witness_store", None) is None:
                self.path_witness_store = PathWitnessStore()
            intent = MovementIntent.from_context(ctx)
            ctx["movement_intent"] = intent.to_dict()
            request.context = ctx
            move_candidates, move_mask, solver_ms, fallback_mode = generate_move_unit_candidates(self, request, intent)
            if move_candidates:
                normalized_candidates: list[CandidateAction] = []
                for candidate in list(move_candidates or []):
                    metadata = dict(candidate.metadata or {})
                    metadata["solver_ms"] = int(max(0, solver_ms))
                    metadata["fallback_mode"] = bool(fallback_mode or metadata.get("fallback_mode", False))
                    normalized_candidates.append(
                        CandidateAction(
                            action_id=str(candidate.action_id),
                            params=dict(candidate.params or {}),
                            metadata=metadata,
                        )
                    )
                request.candidates = normalized_candidates
                request.mask = [bool(value) for value in list(move_mask or [])]
                if len(request.mask) != len(request.candidates):
                    request.mask = [True] * len(request.candidates)
                request.mask_reasons = [None if val else "masked_as_illegal" for val in request.mask]
        request.context = ctx
        self.decision_queue.add(request)
        self.event_system.publish("decision_requested", request=request, game=self)

    def request_dice_roll(self, *, player_id: Optional[str], spec: dict, prompt: Optional[str] = None) -> DecisionRequest:
        """Create and queue a dice roll decision via the roll manager."""
        if self.roll_manager is None:
            raise RuntimeError("Roll manager missing.")
        return self.roll_manager.request_roll(self, player_id=player_id, spec=dict(spec or {}), prompt=prompt)

    def request_mission_selection(self) -> DecisionRequest:
        """Queue a mission selection decision request and return it."""
        from .mission_selection import iter_mission_combinations

        combos = iter_mission_combinations()
        options = []
        for combo in combos:
            label = f"{combo.get('id')} - {combo.get('primary')} / {combo.get('deployment')}"
            options.append(DecisionOption.create(label, payload={"combination": dict(combo)}))
        player_id = None
        try:
            player_id = self.get_current_player().id
        except Exception:
            player_id = None
        request = DecisionRequest.create(
            DECISION_CHOOSE_MISSION,
            "Select mission combination and terrain layout.",
            player_id=player_id,
            options=options,
        )
        self.request_decision(request)
        return request

    def apply_transport_assignments(self, army, units, assignments) -> bool:
        """Apply pre-battle transport assignments for an army."""
        if army is None:
            return False
        # Clear any previous start-embarked assignments for this army.
        for unit in list(units or []):
            if getattr(unit, "is_transport", False):
                continue
            if getattr(unit, "embarked_in", None) is not None and (not getattr(unit, "deployed", False)):
                try:
                    transport = unit.embarked_in
                    if transport is not None:
                        transport.remove_passenger(unit)
                except Exception:
                    pass

        for transport, passengers in (assignments or {}).items():
            for passenger in list(passengers or []):
                try:
                    passenger.embark(transport, game_map=self.map)
                except Exception:
                    return False
                try:
                    passenger.deployed = True
                except Exception:
                    pass
                try:
                    for leader in list(getattr(passenger, "attached_leaders", []) or []):
                        leader.deployed = True
                except Exception:
                    pass
        return True

    def apply_reserves_decisions(self, army, decisions: dict) -> bool:
        """Apply reserves decisions to an army."""
        if army is None:
            return False
        try:
            try:
                roots = list(getattr(army, "_reserve_group_roots")() or [])
            except Exception:
                roots = [
                    u for u in getattr(army, "units", []) or []
                    if not getattr(u, "is_attached_leader", False)
                    and not bool(getattr(u, "is_joined_support", False))
                ]

            for root in roots:
                rid = str(getattr(root, "_id", None) or "")
                decision = str(decisions.get(rid, "deploy") or "deploy")
                try:
                    if bool(getattr(root, "must_start_in_reserves", lambda: False)()):
                        if decision != "reserves":
                            print(f"{root.name} must start in Reserves (AIRCRAFT)")
                        decision = "reserves"
                except Exception:
                    pass
                started = decision in ("reserves", "strategic_reserves")
                if decision == "deploy":
                    root.set_reserve_status("deployed")
                    root.deployed = False
                elif decision == "reserves":
                    root.set_reserve_status("reserves")
                    root.deployed = True
                elif decision == "strategic_reserves":
                    root.set_reserve_status("strategic_reserves")
                    root.deployed = True
                else:
                    root.set_reserve_status("deployed")
                    root.deployed = False

                # AIRCRAFT TRANSPORT rule: passengers must also start in Reserves.
                try:
                    is_transport = bool(getattr(root, "is_transport", False))
                    must_reserves = bool(getattr(root, "must_start_in_reserves", lambda: False)())
                except Exception:
                    is_transport = False
                    must_reserves = False
                if is_transport and must_reserves and decision in ("reserves", "strategic_reserves"):
                    try:
                        passengers = list(getattr(root, "transport_passengers", []) or [])
                    except Exception:
                        passengers = []
                    for passenger in passengers:
                        try:
                            passenger.set_reserve_status("reserves")
                        except Exception:
                            try:
                                passenger.reserve_status = "reserves"
                            except Exception:
                                pass
                        try:
                            passenger.deployed = True
                        except Exception:
                            pass
                        try:
                            setattr(passenger, "_started_in_reserves", True)
                        except Exception:
                            pass
                        try:
                            for leader in list(getattr(passenger, "attached_leaders", []) or []):
                                setattr(leader, "_started_in_reserves", True)
                        except Exception:
                            pass

                try:
                    members = list(getattr(army, "_reserve_group_members")(root) or [])
                except Exception:
                    members = [root]
                # Mark which units started the game in reserves (Chapter Approved round-3 destruction applies only to these).
                for member in members:
                    try:
                        setattr(member, "_started_in_reserves", bool(started))
                    except Exception:
                        pass
                for member in members:
                    if member is root:
                        continue
                    try:
                        member.set_reserve_status(getattr(root, "reserve_status", "deployed"))
                    except Exception:
                        try:
                            member.reserve_status = getattr(root, "reserve_status", "deployed")
                        except Exception:
                            pass
                    try:
                        member.deployed = True
                    except Exception:
                        pass
        except Exception:
            return False
        return True

    def resolve_decision(self, result: DecisionResult):
        """Resolve and remove a pending decision."""
        if result is None:
            return None
        request = self.decision_queue.get(result.decision_id)
        if request is None:
            return None
        from .decision_dispatcher import dispatch_decision
        with game_context(self):
            apply_result = dispatch_decision(self, request, result)
        self.decision_record_store.record_resolution(
            request,
            result,
            ok=bool(getattr(apply_result, "ok", False)),
            errors=list(getattr(apply_result, "errors", ()) or ()),
            value=getattr(apply_result, "value", None),
        )
        if apply_result.ok:
            self.decision_queue.pop(result.decision_id)
            self.event_system.publish("decision_resolved", result=result, request=request, game=self)
            self._maybe_queue_reactive_move_followup(request, result)
            self._maybe_queue_setup_reactive_followup(request, result)
            self._maybe_queue_reverberating_summons_followup(request, result)
            self._maybe_apply_optional_ability_confirmation(request, result)
            self._maybe_queue_bodyguard_return_followup(request, result)
            self._maybe_apply_spirit_snare_followup(request, result)
            self._maybe_apply_mortal_wounds_followup(request, result)
            self._maybe_apply_bodyguard_loss_followup(request, result)
            self._maybe_apply_daemonic_patrons_loss_followup(request, result)
            self._maybe_apply_cult_ambush_followup(request, result)
            self._maybe_queue_code_chivalric_followup(request, result)
        else:
            try:
                dtype = getattr(request, "decision_type", "")
                pid = getattr(request, "player_id", None)
                err_list = list(getattr(apply_result, "errors", ()) or ())
                print(f"ERROR: Decision rejected ({dtype}) for player {pid}: {err_list}")
            except Exception:
                print(f"ERROR: Unexpected Decision Failure for {request} with {apply_result}")
 
        return apply_result

    def get_current_player(self) -> Player:
        """Get the current player."""
        return self.players[self.current_player_index]

    def get_waiting_player_id(self) -> str | None:
        """Return the single player id the game is currently waiting on for input."""
        queue = getattr(self, "decision_queue", None)
        if queue is not None:
            req = queue.peek()
            pid = getattr(req, "player_id", None) if req is not None else None
            if pid:
                try:
                    if self.is_in_setup_phase():
                        phase = self.get_current_setup_phase()
                        if getattr(phase, "name", None) == "DEPLOY_ARMIES":
                            from .decision_kinds import DECISION_MOVE_UNIT
                            if getattr(req, "decision_type", None) != DECISION_MOVE_UNIT:
                                pid = None
                            else:
                                ctx = dict(getattr(req, "context", {}) or {})
                                placement_kind = str(ctx.get("placement_kind", "") or "")
                                if placement_kind not in ("deployment", "reserves_arrival"):
                                    pid = None
                except Exception:
                    pass
            if pid:
                return str(pid)

        try:
            if self.is_in_setup_phase():
                phase = self.get_current_setup_phase()
                if getattr(phase, "name", None) == "DEPLOY_ARMIES":
                    player = self.get_current_deployment_player()
                else:
                    player = self.get_current_player()
            elif self.is_deployment_phase():
                player = self.get_current_deployment_player()
            else:
                player = self.get_current_player()
            return str(player.id) if player is not None else None
        except Exception:
            return None

    def get_waiting_player_ids(self) -> set[str]:
        """Return player ids the game is currently waiting on for input."""
        pid = self.get_waiting_player_id()
        return {pid} if pid else set()

    def get_opponent(self) -> Player:
        """Get the opponent of the current player."""
        return self.players[(self.current_player_index + 1) % len(self.players)]

    def get_enemy_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to the opponent of the given player."""
        # Get their opponent (skip players without armies to avoid crashes in partial test setups).
        for p in self.players:
            if p is player:
                continue
            army = self._get_player_army(p)
            if army is not None:
                return list(getattr(army, "units", []) or [])
        return []

    def get_distance_between_units(self, unit1: 'Unit', unit2: 'Unit') -> float:
        """Calculate the shortest distance between any two models in the units."""
        shortest_distance = float('inf')
        for model1 in unit1.models:
            closest_model, distance = model1.return_closest_model_in_unit(unit2)
            shortest_distance = min(shortest_distance, distance)
        return shortest_distance

    def next_phase(self):
        """Advance to the next phase."""
        if self.in_command_context():
            _next_phase(self)
            return
        player_id = None
        try:
            player_id = self.get_current_player().id
        except Exception:
            player_id = None
        cmd = GameCommand.create(CMD_NEXT_PHASE, player_id=player_id)
        self.apply_command(cmd)

    def is_command_phase(self) -> bool:
        return self.phase == BattleRoundPhases.COMMAND_PHASE

    def _record_engaged_enemies_at_turn_start(self, player) -> None:
        if player is None:
            return
        game_map = self.map
        if game_map is None:
            return
        army = getattr(player, "army", None)
        if army is None:
            return
        for unit in list(getattr(army, "units", []) or []):
            if not unit.is_alive() or not unit.deployed:
                continue
            engaged_ids = set()
            enemies = game_map.get_enemy_units(unit) or []
            for enemy in enemies:
                if not enemy.is_alive() or not enemy.deployed:
                    continue
                if game_map.is_within_engagement_range(unit, enemy):
                    root = enemy.get_attached_unit_root()
                    engaged_ids.add(get_entity_id(root))
            unit.round_state.engaged_enemies_at_turn_start = engaged_ids

    def _shadow_of_chaos_zones(self, player) -> set[str]:
        zones = {"own"}
        if player is None:
            return zones
        opponent = next((p for p in (self.players or []) if p is not player), None)
        objectives = list(getattr(self.map, "objectives", []) or [])
        nml_total = 0
        nml_controlled = 0
        enemy_total = 0
        enemy_controlled = 0
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            loc.update_control(self)
            in_own = self.is_position_in_deployment_zone(loc.x, loc.y, player.id)
            in_enemy = self.is_position_in_deployment_zone(loc.x, loc.y, opponent.id) if opponent is not None else False
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
        try:
            overrides = getattr(self, "_shadow_of_chaos_zone_overrides", None)
        except Exception:
            overrides = None
        if isinstance(overrides, dict):
            try:
                pid = str(getattr(player, "id", "") or "")
            except Exception:
                pid = ""
            extra = overrides.get(pid) if pid else None
            if extra:
                try:
                    zones.update(str(z).strip().lower() for z in (extra or []) if str(z).strip())
                except Exception:
                    pass
        return zones

    def _unit_wholly_within_shadow_of_chaos(self, unit: Unit) -> bool:
        army = unit.get_parent_army()
        if army is None or army.player is None:
            return False
        player = army.player
        mgr = getattr(army, "shadow_of_chaos", None)
        if mgr is not None and mgr.army_has_shadow():
            if mgr.unit_wholly_within_dark_master_aura(unit, army, game=self):
                return True
        zones = self._shadow_of_chaos_zones(player)
        opponent = next((p for p in (self.players or []) if p is not player), None)
        for model in list(getattr(unit, "models", []) or []):
            if not getattr(model, "is_alive", True):
                continue
            x, y, *_rest = model.get_location()
            base = getattr(model, "model_base", None)
            if base is None:
                continue
            in_own = self.is_position_wholly_in_deployment_zone(float(x), float(y), base, player.id)
            in_enemy = (
                self.is_position_wholly_in_deployment_zone(float(x), float(y), base, opponent.id)
                if opponent is not None
                else False
            )
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
        army = unit.get_parent_army()
        if army is None or army.player is None:
            return False
        player = army.player
        zones = self._shadow_of_chaos_zones(player)
        opponent = next((p for p in (self.players or []) if p is not player), None)
        for model in list(getattr(unit, "models", []) or []):
            if not getattr(model, "is_alive", True):
                continue
            x, y, *_rest = model.get_location()
            base = getattr(model, "model_base", None)
            if base is None:
                continue
            in_own = self.is_position_wholly_in_deployment_zone(float(x), float(y), base, player.id)
            in_enemy = (
                self.is_position_wholly_in_deployment_zone(float(x), float(y), base, opponent.id)
                if opponent is not None
                else False
            )
            if in_own:
                zone = "own"
            elif in_enemy:
                zone = "enemy"
            else:
                zone = "nml"
            if zone not in zones:
                return False
        return True

    def _unit_has_keyword(self, unit: Unit, keyword: str) -> bool:
        if unit is None:
            return False
        fn = getattr(unit, "has_any_keyword", None)
        if callable(fn):
            return bool(fn(keyword))
        kw = str(keyword or "").strip().upper()
        if not kw:
            return False
        keywords = [
            str(k).strip().upper()
            for k in (getattr(unit, "keywords", []) or [])
            if str(k).strip()
        ]
        faction_keywords = [
            str(k).strip().upper()
            for k in (getattr(unit, "faction_keywords", []) or [])
            if str(k).strip()
        ]
        return kw in set(keywords + faction_keywords)

    def _get_player_army(self, player):
        if player is None:
            return None
        getter = getattr(player, "get_army", None)
        if callable(getter):
            return getter()
        return getattr(player, "army", None)

    def _apply_adaptive_biology_turn_start(self) -> None:
        from ..rules.enhancement import maybe_upgrade_adaptive_biology

        for player in list(self.players or []):
            army = self._get_player_army(player)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                maybe_upgrade_adaptive_biology(unit)

    def _evaluate_corrupt_realspace_turn_boundary(self, *, timing: str, player: Player | None = None) -> None:
        """Check Corrupt Realspace sticky objectives at the start/end of any turn."""
        game_map = getattr(self, "map", None)
        if game_map is None:
            return
        objectives = list(getattr(game_map, "objectives", []) or [])
        if not objectives:
            return
        has_corrupt = False
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            if str(getattr(loc, "sticky_source", "") or "") == "corrupt_realspace":
                has_corrupt = True
                break
        if not has_corrupt:
            return
        self._corrupt_realspace_check = True
        try:
            for obj in objectives:
                loc = getattr(obj, "location", None)
                if loc is None or getattr(loc, "removed", False):
                    continue
                if str(getattr(loc, "sticky_source", "") or "") != "corrupt_realspace":
                    continue
                if hasattr(loc, "update_control"):
                    loc.update_control(self)
        finally:
            self._corrupt_realspace_check = False

    def _warp_rifts_min_distance(self, unit: Unit) -> float:
        if unit is None or not self._unit_has_keyword(unit, "LEGIONES DAEMONICA"):
            return 9.0
        if not unit._is_daemonic_incursion_detachment():
            return 9.0
        if not unit.has_deep_strike():
            return 9.0

        if self._unit_wholly_within_shadow_of_chaos_zones(unit):
            return 6.0

        army = unit.get_parent_army()

        # Warp Rifts cannot bootstrap off the arriving unit's own aura.
        from ..rules.shadow_of_chaos import ShadowOfChaosManager
        from ..utility.aura_utils import unit_wholly_within_range_of_unit

        if army is not None:
            for source in ShadowOfChaosManager._army_dark_master_units(army):
                if source is unit:
                    continue
                if unit_wholly_within_range_of_unit(source, unit, 6.0, use_attached_aggregate=True):
                    return 6.0

            god_keywords = {"KHORNE", "TZEENTCH", "NURGLE", "SLAANESH"}
            for source in ShadowOfChaosManager._army_greater_daemon_units(army):
                if source is unit:
                    continue
                if not any(self._unit_has_keyword(unit, kw) and self._unit_has_keyword(source, kw) for kw in god_keywords):
                    continue
                if unit_wholly_within_range_of_unit(source, unit, 6.0, use_attached_aggregate=True):
                    return 6.0

        return 9.0

    def _resolve_daemonic_poisons_command_phase(self, player: Player) -> None:
        if player is None:
            return
        army = self._get_player_army(player)
        if army is None:
            return
        from ..rules.daemonic_poisons import unit_is_poisoned, DAEMONIC_POISONS_NAME

        poisoned_units: list[Unit] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid in seen:
                continue
            seen.add(rid)
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue
            if not bool(getattr(root, "deployed", True)):
                continue
            if str(getattr(root, "reserve_status", "deployed")) != "deployed":
                continue
            if not unit_is_poisoned(root):
                continue
            poisoned_units.append(root)

        if not poisoned_units:
            return

        for unit in list(poisoned_units):
            roll_spec = {
                "dice_count": 1,
                "faces": 6,
                "reason": f"{DAEMONIC_POISONS_NAME}: {getattr(unit, 'name', 'Unit')}",
                "roll_type": "daemonic_poisons",
                "unit_id": get_entity_id(unit),
                "handler_key": "daemonic_poisons",
                "handler_payload": {"ability_name": DAEMONIC_POISONS_NAME},
            }
            self.request_dice_roll(player_id=getattr(player, "id", None), spec=roll_spec, prompt=roll_spec["reason"])

    @staticmethod
    def _model_within_objective_marker(model, objective_point) -> bool:
        if model is None or objective_point is None:
            return False
        try:
            from shapely.geometry import Point as _ShPoint
            area = _ShPoint(objective_point.x, objective_point.y).buffer(
                float(getattr(objective_point, "control_radius", 0.0) or 0.0)
            )
        except Exception:
            area = None
        try:
            if area is not None:
                base = model.model_base.get_base_shape()
                if base.intersects(area):
                    return True
        except Exception:
            pass
        try:
            pos = model.get_location()
        except Exception:
            pos = None
        if not pos:
            return False
        try:
            dx = float(pos[0]) - float(getattr(objective_point, "x", 0.0))
            dy = float(pos[1]) - float(getattr(objective_point, "y", 0.0))
            radius = float(getattr(objective_point, "control_radius", 0.0) or 0.0)
            base_r = float(getattr(model.model_base, "get_radius", lambda: 1.0)())
            return (dx * dx + dy * dy) ** 0.5 <= (radius + base_r)
        except Exception:
            return False

    def _resolve_computational_mastermind_before_mode(self, player: Player) -> int:
        if player is None or player is not self.get_current_player():
            return 0
        phase_obj = getattr(self, "phase", None)
        phase_name = str(getattr(phase_obj, "name", "") or phase_obj or "").strip().upper()
        if phase_name != "COMMAND_PHASE":
            return 0
        army = self._get_player_army(player)
        if army is None:
            return 0
        pe = getattr(army, "prioritised_efficiency", None)
        if pe is None:
            return 0
        game_map = getattr(self, "map", None)
        if game_map is None:
            return 0
        objectives = list(getattr(game_map, "objectives", []) or [])
        if not objectives:
            return 0

        def _unit_sort_key(unit_obj) -> str:
            try:
                return str(get_entity_id(unit_obj) or "")
            except Exception:
                return str(getattr(unit_obj, "name", "") or "")

        def _model_sort_key(model_obj) -> str:
            try:
                return str(get_entity_id(model_obj) or "")
            except Exception:
                return str(getattr(model_obj, "name", "") or "")

        ability_models_by_root: dict = {}
        seen_roots: set[str] = set()
        for unit in sorted(list(getattr(army, "units", []) or []), key=_unit_sort_key):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if not root_id or root_id in seen_roots:
                continue
            seen_roots.add(root_id)
            if not bool(getattr(root, "is_alive", lambda: False)()):
                continue
            if not bool(getattr(root, "deployed", True)):
                continue
            try:
                if root.is_in_reserves() or root.is_embarked:
                    continue
            except Exception:
                pass
            has_fn = getattr(root, "has_computational_mastermind", None)
            if not callable(has_fn) or not bool(has_fn()):
                continue
            get_models = getattr(root, "get_computational_mastermind_models", None)
            if not callable(get_models):
                continue
            models = [m for m in list(get_models() or []) if m is not None and getattr(m, "is_alive", True)]
            if not models:
                continue
            models.sort(key=_model_sort_key)
            ability_models_by_root[root] = list(models)

        if not ability_models_by_root:
            return 0

        entries: list[tuple[int, object, object, object, object]] = []
        for idx, objective in enumerate(objectives):
            loc = getattr(objective, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            update_control = getattr(loc, "update_control", None)
            if callable(update_control):
                update_control(self)
            if getattr(loc, "controlling_player", None) is not player:
                continue
            selected_root = None
            selected_model = None
            for root, models in ability_models_by_root.items():
                found = None
                for model in list(models):
                    if self._model_within_objective_marker(model, loc):
                        found = model
                        break
                if found is None:
                    continue
                selected_root = root
                selected_model = found
                break
            if selected_root is None or selected_model is None:
                continue
            entries.append((idx, objective, loc, selected_root, selected_model))

        if not entries:
            return 0

        from ..utility.decision_utils import resolve_decision_value

        def _choice_from_overrides(objective_key: str) -> str:
            selections = getattr(player, "_next_optional_selections", None)
            if not isinstance(selections, dict):
                return ""
            raw_key = None
            if "COMPUTATIONAL_MASTERMIND" in selections:
                raw_key = "COMPUTATIONAL_MASTERMIND"
            elif "computational_mastermind" in selections:
                raw_key = "computational_mastermind"
            if raw_key is None:
                return ""
            raw = selections.get(raw_key)
            chosen = ""
            if isinstance(raw, dict):
                chosen = str(raw.get(objective_key) or raw.get("*") or "").strip().lower()
            elif isinstance(raw, list):
                if raw:
                    chosen = str(raw.pop(0) or "").strip().lower()
                if not raw:
                    selections.pop(raw_key, None)
            else:
                chosen = str(raw or "").strip().lower()
            if chosen in ("gain", "spend", "skip", "none"):
                return "skip" if chosen == "none" else chosen
            return ""

        total_delta = 0
        owner_id = str(getattr(player, "id", "") or "")
        turn = int(getattr(self, "turn", 0) or 0)
        for idx, objective, _loc, source_root, source_model in list(entries):
            objective_id = str(get_entity_id(objective) or f"objective_{idx}")
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                already_pending = False
                for pending in list(queue.list() or []):
                    if str(getattr(pending, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    pctx = dict(getattr(pending, "context", {}) or {})
                    if str(pctx.get("ability", "") or "") != "computational_mastermind":
                        continue
                    if str(pctx.get("objective_id", "") or "") != objective_id:
                        continue
                    if str(pctx.get("turn_owner", "") or "") != owner_id:
                        continue
                    if int(pctx.get("turn", 0) or 0) != turn:
                        continue
                    already_pending = True
                    break
                if already_pending:
                    continue

            options = [DecisionOption.create("None", payload={"action": "skip"})]
            options.append(DecisionOption.create("Gain 1 YP", payload={"action": "gain", "amount": 1}))
            if int(getattr(pe, "yield_points", 0) or 0) >= 1:
                options.append(DecisionOption.create("Spend 1 YP", payload={"action": "spend", "amount": 1}))
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Computational Mastermind: choose Spend 1 YP, Gain 1 YP, or None.",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "computational_mastermind",
                    "ability_name": "Computational Mastermind",
                    "phase": "Command phase",
                    "optional": True,
                    "source_unit_id": str(get_entity_id(source_root) or ""),
                    "unit_id": str(get_entity_id(source_root) or ""),
                    "model_id": str(get_entity_id(source_model) or ""),
                    "objective_id": objective_id,
                    "objective_index": int(idx),
                    "turn_owner": owner_id,
                    "turn": int(turn),
                },
            )
            self.request_decision(request)
            desired = _choice_from_overrides(objective_id)
            if not desired:
                desired = "gain"
            option_id = None
            for opt in list(getattr(request, "options", []) or []):
                action = str((getattr(opt, "payload", {}) or {}).get("action", "") or "").strip().lower()
                if action == desired:
                    option_id = getattr(opt, "option_id", None)
                    break
            if option_id is None:
                for opt in list(getattr(request, "options", []) or []):
                    action = str((getattr(opt, "payload", {}) or {}).get("action", "") or "").strip().lower()
                    if action == "skip":
                        option_id = getattr(opt, "option_id", None)
                        break
            if option_id is None:
                continue
            value, apply_result = resolve_decision_value(
                self,
                request,
                option_id,
                player_id=getattr(player, "id", None),
            )
            if apply_result is not None and getattr(apply_result, "ok", False):
                try:
                    total_delta += int(value or 0)
                except Exception:
                    pass
        return int(total_delta)

    def start_command_phase(self) -> None:
        """Start the command phase: active player gains normal CP, then resolves any bonus CP sources."""
        # Battle-shock expires at the start of *your* next Command phase (even if the unit was later destroyed).
        # Clear it before doing anything else in the Command phase.
        self.battle_shock_step_active = False
        current_player = self.get_current_player()
        if current_player is None:
            return
        current_player_id = getattr(current_player, "id", "")
        self.get_or_create_tier1_plan(current_player_id)
        self.get_or_create_tier2_task_bundle(current_player_id)
        army = self._get_player_army(current_player)
        if army is None:
            return

        mgr = getattr(self, "fates_in_flux", None)
        if mgr is not None:
            mgr.on_command_phase_start(game=self, player=current_player)

        # Corrupt Realspace: check at the start of any turn.
        self._evaluate_corrupt_realspace_turn_boundary(timing="start", player=current_player)

        # Adaptive Biology (Tyranids enhancement): check at the start of any turn.
        self._apply_adaptive_biology_turn_start()

        for unit in list(getattr(army, "units", []) or []):
            fn = getattr(unit, "clear_battle_shock", None)
            if callable(fn):
                fn()

        # Fulgrim: Daemonic Poisons (Command phase rolls for poisoned units).
        self._resolve_daemonic_poisons_command_phase(current_player)

        # Fulgrim: Daemon Primarch of Slaanesh selection at the start of the opponent's Command phase.
        self._maybe_prompt_daemon_primarch_slaanesh(current_player)

        # Abaddon: The Warmaster selection at the start of your Command phase.
        self._maybe_prompt_csm_warmaster(current_player)

        # Space Marines: Oath of Moment target selection at the start of your Command phase.
        mgr = getattr(army, "oath_of_moment", None)
        if mgr is not None:
            mgr.on_command_phase_start(game=self, player=current_player)
            self.event_system.publish("oath_of_moment_prompt", player=current_player, game=self)

        # Space Marines: Combat Doctrines selection at the start of your Command phase.
        mgr = getattr(army, "combat_doctrines", None)
        if mgr is not None:
            self._maybe_prompt_combat_doctrines()

        # Thousand Sons: Grand Coven (Kindred Sorcery) selection at the start of your Command phase.
        mgr = getattr(army, "thousand_sons_detachments", None)
        if mgr is not None:
            self._maybe_prompt_grand_coven()

        # Drukhari: Combat Drugs selection at the start of your Command phase.
        mgr = getattr(army, "drukhari_detachments", None)
        if mgr is not None:
            self._maybe_prompt_combat_drugs()

        # Chaos Knights: Malefic Surge selection (Infernal Lance).
        mgr = getattr(army, "chaos_knights_detachments", None)
        if mgr is not None:
            try:
                mgr.clear_empowered_at_command_phase_start(game=self, player=current_player)
            except Exception:
                pass
            try:
                mgr.prompt_malefic_surge_selection(game=self, player=current_player)
            except Exception:
                pass

        # Imperial Knights: Bondsman selection at the start of your Command phase.
        mgr = getattr(army, "bondsman", None)
        if mgr is not None:
            mgr.on_command_phase_start(game=self, player=current_player)
            self.event_system.publish("bondsman_prompt", player=current_player, game=self)

        # Necrons enhancements: command phase bearer target selection.
        mgr = getattr(army, "necrons_detachments", None)
        if mgr is not None and hasattr(mgr, "on_command_phase_start"):
            mgr.on_command_phase_start(game=self, player=current_player)
            self.event_system.publish("necrons_command_phase_enhancement_prompt", player=current_player, game=self)

        # Orks: Waaagh! (expires at your next Command phase; prompt to call).
        mgr = getattr(army, "waaagh", None)
        if mgr is not None:
            mgr.on_command_phase_start(game=self, player=current_player)

        # World Eaters: Blood Tithe spending at the start of your Command phase.
        mgr = getattr(army, "world_eaters_detachments", None)
        if mgr is not None and hasattr(mgr, "on_command_phase_start"):
            mgr.on_command_phase_start(game=self, player=current_player)

        # Core (per official app wording): at the start of your Command phase, before doing anything else,
        # BOTH players gain the normal Command phase CP. This normal CP does not count toward the
        # per-battle-round "bonus CP" guardrail.
        for p in list(self.players):
            if p is None:
                continue
            if not hasattr(p, "gain_normal_command_phase_cp"):
                pname = getattr(p, "name", "Unknown player")
                raise RuntimeError(f"Player missing gain_normal_command_phase_cp: {pname}")
            p.gain_normal_command_phase_cp()

        # Bonus CP sources that trigger in *your* Command phase (e.g., character alive -> gain 1CP).
        # This is NOT the normal command phase CP, so it is subject to the per-battle-round guardrail.
        if not (hasattr(current_player, "get_command_phase_bonus_cp_gain") and hasattr(current_player, "gain_command_points")):
            pname = getattr(current_player, "name", "Unknown player")
            raise RuntimeError(f"Player missing command phase CP methods: {pname}")
        bonus = int(current_player.get_command_phase_bonus_cp_gain() or 0)
        if bonus > 0:
            current_player.gain_command_points(bonus, reason="Command phase bonus CP")

        # Datasheet abilities: start of your Command phase regain lost wounds.
        self._apply_command_phase_regain_wounds(current_player)

        # Drukhari: Power from Pain tokens at start of your Command phase.
        mgr = getattr(army, "power_from_pain", None)
        if mgr is not None:
            mgr.on_command_phase_start(game=self, player=current_player)

        # Explicit phase start publish for command phase entry
        self.event_system.publish("phase_start", player=current_player, phase=self.phase)

        # Drukhari: command phase Pain abilities (e.g., Fleshcraft).
        self._maybe_prompt_power_from_pain_command_phase()
        # Tyranids: Shadow in the Warp (once per battle, either player's Command phase).
        self._maybe_prompt_shadow_in_the_warp()
        # Orks: Waaagh! prompt (once per battle, start of your Command phase).
        self._maybe_prompt_waaagh()

        # Execute command actions for current player's units (without resetting round state)
        current_player = self.get_current_player()
        # Burden of Trust: guards last until the start of your next turn
        self._clear_expired_guards_for_player(current_player)

        # Secondary Missions: draw up to two at the start of your Command phase
        before = [getattr(c, 'name', 'Unknown') for c in getattr(current_player, 'active_secondaries', [])]
        current_player.draw_secondary_until_two(self)
        after = [getattr(c, 'name', 'Unknown') for c in getattr(current_player, 'active_secondaries', [])]
        newly_drawn = [name for name in after if name not in before]
        if newly_drawn:
            print(f"{current_player.name} active Secondaries: {', '.join(after)}")

        # Notify active secondaries about start-of-turn (for cards that snapshot start-of-turn state).
        for card in list(getattr(current_player, "active_secondaries", []) or []):
            fn = getattr(card, "on_turn_start", None)
            if callable(fn):
                fn(self, current_player)

        # If in fifth battle round and going second, primary scoring is at end of turn, not here
        tested_ids: set[str] = set()
        self.battle_shock_step_active = True
        for unit in list(getattr(army, "units", []) or []):
            # Do battle shock tests and other command phase actions without resetting round state
            if not unit.is_alive():
                continue
            # If forced to test for being Below Starting Strength, do not also test for being Below Half-strength
            # unless explicitly stated.
            is_below_starting = False
            fn = getattr(unit, "is_below_starting_strength", None)
            if callable(fn):
                try:
                    is_below_starting = bool(fn())
                except Exception:
                    is_below_starting = False
            if is_below_starting:
                print(f"WARN: {unit.name} is below starting strength - taking Battle-Shock test")
                unit.take_battle_shock_test(self.turn)
                uid = get_entity_id(unit)
                tested_ids.add(uid)
                continue
            is_below_half = False
            fn = getattr(unit, "is_below_half_strength", None)
            if callable(fn):
                try:
                    is_below_half = bool(fn())
                except Exception:
                    is_below_half = False
            if is_below_half:
                print(f"WARN: {unit.name} is below half strength - taking Battle-Shock test")
                unit.take_battle_shock_test(self.turn)
                uid = get_entity_id(unit)
                tested_ids.add(uid)

        # Belakor: Pall of Despair can force additional tests for eligible enemy units.
        self._apply_pall_of_despair_forced_tests(current_player, tested_ids)
        # Chaos Knights: Dismay can force additional tests for eligible enemy units.
        self._apply_harbingers_dismay_forced_tests(current_player, tested_ids)
        self.battle_shock_step_active = False

        # Necrons: Reanimation Protocols at end of Command phase (resolve before scoring).
        self._apply_reanimation_protocols_end_command_phase(current_player)

        # Primary mission scoring at command phase (2nd battle round onwards)
        primary = getattr(current_player, "primary_mission", None)
        if isinstance(primary, PrimaryMissionCard):
            vp = primary.score_at_command_phase(self, current_player)
            if vp:
                added = self.award_vp(
                    current_player,
                    vp,
                    source="primary",
                    card=primary,
                    timing="End of Command phase",
                )
                if added:
                    print(f"{current_player.name} scored {added} VP from Primary: {primary.name}")

        # Leagues of Votann: Prioritised Efficiency (Yield Points + mode updates).
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "army", None)
            mgr = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if mgr is None:
                continue
            delta = mgr.gain_yield_points(self)
            mode_changed = False
            if p is current_player:
                self._resolve_computational_mastermind_before_mode(p)
                mode_changed = mgr.update_mode_for_player(self, p)
            if delta or mode_changed:
                self.event_system.publish(
                    "prioritised_efficiency_updated",
                    player=p,
                    game=self,
                    delta=int(delta or 0),
                    mode=getattr(mgr, "mode", None),
                    yield_points=int(getattr(mgr, "yield_points", 0) or 0),
                )

        # Burden of Trust: assign guards at the end of the Command phase.
        self._assign_burden_of_trust_guards(current_player)

    def is_movement_phase(self) -> bool:
        return self.phase == BattleRoundPhases.MOVEMENT_PHASE

    def is_shooting_phase(self) -> bool:
        return self.phase == BattleRoundPhases.SHOOTING_PHASE

    def is_charge_phase(self) -> bool:
        return self.phase == BattleRoundPhases.CHARGE_PHASE

    def is_fight_phase(self) -> bool:
        return self.phase == BattleRoundPhases.FIGHT_PHASE

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
        # Return the current game state as a dictionary.
        # TODO: refine for serialization and network transport.
        return {
            "players": self.players,
            "battlefield": self.battlefield,
            "map": self.map,
            "current_player": self.get_current_player(),
            "turn": self.turn,
            "phase": self.phase,
        }

    def save_snapshot(self) -> dict:
        """Serialize the current game state into a snapshot payload."""
        from .snapshot import snapshot_game

        return snapshot_game(self)

    @staticmethod
    def load_snapshot(snapshot: dict) -> "Game":
        """Load a game instance from a snapshot payload."""
        from .snapshot import load_game_snapshot

        return load_game_snapshot(snapshot)

    def declare_charge(
        self,
        charging_unit: 'Unit',
        target_units: list['Unit'],
        *,
        out_of_turn: bool = False,
    ) -> dict | None:
        """
        Single source of truth for charge declaration bookkeeping + rolling:

        - Validates eligibility (`Unit.can_declare_charge_against`)
        - Marks `attempted_charge_this_round` immediately (a declared charge is an attempt)
        - Rolls charge dice (default 2D6; supports non-additive mechanics like 3D6 drop lowest)
        - Offers a rule-based re-roll prompt (e.g. "re-roll Charge rolls") via map.roll_reroll_provider (UI hook)
        - Publishes `roll_made` for stratagem/telemetry consumers

        out_of_turn: allow declaring a charge outside the active player's turn (no attempted_charge_this_round mark).

        Returns a dict:
          { "base_roll": int, "dice": list[int], "reroll_used": bool, "target_unit_ids": list[str] }
        or None if the charge cannot be declared.
        """
        if target_units is None:
            targets = []
        elif isinstance(target_units, (list, tuple, set)):
            targets = list(target_units)
        else:
            targets = [target_units]
        if not targets:
            return None
        if not charging_unit._can_declare_charge_base(self, out_of_turn=out_of_turn):
            return None
        for tgt in targets:
            if tgt is None:
                return None
            if not charging_unit.can_declare_charge_against(tgt, self, out_of_turn=True):
                return None

        if not out_of_turn and getattr(charging_unit.round_state, "advanced_this_round", False):
            try:
                always_ok = charging_unit._advance_and_charge_always_available()
            except Exception:
                always_ok = False
            if not always_ok:
                spec = None
                try:
                    spec = charging_unit._advance_and_charge_once_per_battle_spec()
                except Exception:
                    spec = None
                if isinstance(spec, dict):
                    ability_key = str(spec.get("ability_key") or "").strip().lower()
                    if ability_key:
                        ability_name = str(spec.get("source", "") or "Advance and Charge").strip() or "Advance and Charge"
                        charging_unit.mark_unit_once_per_battle_used(ability_key, ability_name=ability_name)

        if not hasattr(self, "event_system") or not hasattr(self.event_system, "publish"):
            raise RuntimeError("Event system missing for charge_declared event.")
        self.event_system.publish("charge_declared", unit=charging_unit, target_units=list(targets))

        army = charging_unit.get_parent_army()
        mgr = getattr(army, "battle_focus", None) if army is not None else None
        if mgr is not None:
            mgr.maybe_trigger_charge_maneuver(charging_unit, targets[0], self)

        self._record_engaged_enemies_at_turn_start(self.get_current_player())

        # Mark as attempted immediately (prevents multiple declarations).
        if not out_of_turn:
            charging_unit.round_state.attempted_charge_this_round = True
        charging_unit.round_state.charge_target_ids = {get_entity_id(t) for t in targets}
        for tgt in targets:
            tgt_id = get_entity_id(tgt)
            chargers = self.phase_charge_targets.get(tgt_id, set()) or set()
            chargers.add(get_entity_id(charging_unit))
            self.phase_charge_targets[tgt_id] = chargers

        is_authoritative = bool(getattr(self, "is_authoritative", True))
        if not is_authoritative:
            return {
                "roll_id": None,
                "target_unit_ids": [get_entity_id(t) for t in targets],
                "miracle_used": False,
            }

        spec = self._get_charge_roll_spec(charging_unit, target_unit=targets[0])
        player = charging_unit.get_parent_army().player
        dice_count = int(getattr(spec, "dice_count", 2) or 2)
        keep_highest = int(getattr(spec, "keep_highest", dice_count) or dice_count)
        fixed_dice = []
        miracle_used = False
        use_aof_rolls = False
        auto_resolve = bool(getattr(self, "auto_resolve_dice_rolls", False))
        if auto_resolve:
            try:
                mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                if mgr is not None and mgr.can_use_act_of_faith(charging_unit, game=self):
                    try:
                        _total, dice_vals, used = mgr.resolve_roll(
                            charging_unit,
                            roll_type="charge",
                            game=self,
                            dice_count=dice_count,
                            die_faces=6,
                        )
                        fixed_dice = list(dice_vals or [])
                        miracle_used = bool(used)
                        use_aof_rolls = True
                    except Exception:
                        fixed_dice = []
                        miracle_used = False
                        use_aof_rolls = False
            except Exception:
                fixed_dice = []
                miracle_used = False
                use_aof_rolls = False
            if not fixed_dice:
                try:
                    from ..utility.dice import get_dice_roll
                    fixed_dice = [int(get_dice_roll(6) or 0) for _ in range(dice_count)]
                except Exception:
                    fixed_dice = []
        else:
            try:
                mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                if mgr is not None and mgr.can_use_act_of_faith(charging_unit, game=self):
                    chosen = mgr.maybe_use_miracle_die(
                        charging_unit,
                        roll_type="charge",
                        dice_count=dice_count,
                        die_faces=6,
                        game=self,
                    )
                    if chosen is not None:
                        fixed_dice = [int(chosen)] + [None] * max(0, dice_count - 1)
                        miracle_used = True
            except Exception:
                fixed_dice = []
                miracle_used = False

        reroll_rules = []
        try:
            can_rule_reroll = bool(
                charging_unit.can_reroll_charge_roll(target_unit=list(targets), game_map=self.map, game=self)
            )
            mgr = getattr(army, "templar_vows", None) if army is not None else None
            if mgr is not None and mgr.can_reroll_charge_against(charging_unit, targets[0]):
                can_rule_reroll = True
            if can_rule_reroll:
                reroll_rules.append(
                    {
                        "action_id": "reroll_charge",
                        "label": "Re-roll Charge roll",
                        "mode": "all",
                        "source": "rule",
                    }
                )
        except Exception:
            pass

        from ..engine.roll_utils import command_reroll_available
        command_reroll_ok = command_reroll_available(self, player, roll_type="charge")
        roll_spec = {
            "dice_count": dice_count,
            "faces": 6,
            "reason": f"Charge roll for {charging_unit.name}",
            "roll_type": "charge",
            "unit_id": get_entity_id(charging_unit),
            "target_unit_ids": [get_entity_id(t) for t in targets],
            "handler_key": "charge_roll",
            "charge_spec": {"dice_count": dice_count, "keep_highest": keep_highest},
            "reroll_rules": reroll_rules,
            "command_reroll_allowed": command_reroll_ok,
            "command_reroll_mode": "whole",
        }
        if fixed_dice:
            roll_spec["fixed_dice"] = list(fixed_dice)
            roll_spec["miracle_used"] = bool(miracle_used)
        if auto_resolve and (reroll_rules or command_reroll_ok):
            try:
                if use_aof_rolls:
                    from ..rules import acts_of_faith as aof
                    roll_spec["roll_sequence"] = [int(aof.get_dice_roll(6) or 0) for _ in range(dice_count)]
                else:
                    from ..utility.dice import get_dice_roll
                    roll_spec["roll_sequence"] = [int(get_dice_roll(6) or 0) for _ in range(dice_count)]
            except Exception:
                pass
        req = self.request_dice_roll(player_id=getattr(player, "id", None), spec=roll_spec, prompt=roll_spec["reason"])
        try:
            roll_id = getattr(req, "context", {}).get("roll_id")
            charging_unit.round_state.charge_roll_id = roll_id
        except Exception:
            roll_id = getattr(req, "context", {}).get("roll_id") if req is not None else None
        result = {
            "roll_id": roll_id,
            "target_unit_ids": [get_entity_id(t) for t in targets],
            "miracle_used": bool(miracle_used),
        }
        if auto_resolve:
            try:
                roll_id = result.get("roll_id")
                state = None
                if roll_id is not None and self.roll_manager is not None:
                    state = self.roll_manager.get_roll(int(roll_id))
                dice_vals = list(getattr(charging_unit.round_state, "charge_dice", []) or [])
                if not dice_vals and state is not None:
                    dice_vals = [int(d.get("value", 0) or 0) for d in list(state.dice or []) if not bool(d.get("is_derived", False))]
                base_roll = int(getattr(charging_unit.round_state, "charge_roll", 0) or 0)
                if not base_roll and state is not None:
                    base_roll = int(state.total or 0)
                if dice_vals:
                    result["dice"] = list(dice_vals)
                if base_roll:
                    result["base_roll"] = int(base_roll)
                if state is not None:
                    kept = state.spec.get("kept_indices", None)
                    dropped = state.spec.get("dropped_indices", None)
                    if kept is not None:
                        result["kept_indices"] = list(kept or [])
                    if dropped is not None:
                        result["dropped_indices"] = list(dropped or [])
            except Exception:
                pass
        return result

    def roll_blood_surge_distance(self, unit: 'Unit') -> int:
        """Roll Blood Surge distance (D6+2), optionally applying leader-provided rerolls."""
        if unit is None:
            return 0
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
                    from ..utility.event_bus import append_dice
                    player = getattr(unit.get_parent_army(), "player", None)
                    if player is not None:
                        append_dice(player, f"Blood Surge fixed distance: {int(fixed)}\" for {unit.name}")
                    return int(fixed)
                sr.pop("blood_surge_fixed_distance", None)
                sr.pop("blood_surge_fixed_distance_phase_key", None)
                unit.special_rules = sr

        from ..utility.dice import get_roll

        base_roll = get_roll("D6")
        reroll_used = False

        parent_army = unit.get_parent_army()
        player = parent_army.player if parent_army is not None else None

        can_reroll = bool(unit.can_reroll_blood_surge_roll())
        is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False

        if is_human:
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
        max_distance = int(base_roll or 0) + 2

        from ..utility.event_bus import append_dice
        if player is not None:
            tag = "Blood Surge reroll" if reroll_used else "Blood Surge roll"
            append_dice(player, f"{tag}: {int(base_roll or 0)} (move {max_distance}\") for {unit.name}")

        return int(max_distance)

    def roll_unhinged_vengeance_distance(self, unit: 'Unit') -> int:
        """Roll Unhinged Vengeance distance (D6+2)."""
        if unit is None:
            return 0
        from ..utility.dice import get_roll
        base_roll = int(get_roll("D6") or 0)
        max_distance = int(base_roll + 2)
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(player, f"Unhinged Vengeance roll: {int(base_roll or 0)} (move {max_distance}\") for {unit.name}")
        return int(max_distance)

    def roll_brazen_fury_distance(self, unit: 'Unit') -> int:
        """Roll Brazen Fury distance (D6)."""
        if unit is None:
            return 0
        fixed_distance = None
        try:
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in list(members or []):
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_malicious_vigour"):
                continue
            fixed_distance = int(sr.get("enhancement_malicious_vigour_brazen_fury_distance", 6) or 6)
            break
        from ..utility.dice import get_roll
        base_roll = int(fixed_distance if fixed_distance is not None else (get_roll("D6") or 0))
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            if fixed_distance is not None:
                append_dice(player, f"Brazen Fury fixed distance: {int(base_roll or 0)}\" for {unit.name}")
            else:
                append_dice(player, f"Brazen Fury roll: {int(base_roll or 0)}\" for {unit.name}")
        return int(base_roll or 0)

    def roll_horde_move_distance(self, unit: 'Unit') -> int:
        """Roll Horde Move distance (D6)."""
        if unit is None:
            return 0
        from ..utility.dice import get_roll
        base_roll = int(get_roll("D6") or 0)
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(player, f"Horde Move roll: {int(base_roll or 0)}\" for {unit.name}")
        return int(base_roll or 0)

    def roll_loping_speed_distance(self, unit: 'Unit') -> int:
        """Resolve distance for a reactive Normal move (fixed or rolled)."""
        if unit is None:
            return 0
        try:
            rule = unit.get_loping_speed_rule()
        except Exception:
            rule = None
        source = str((rule or {}).get("source", "") or "Reactive Move").strip() or "Reactive Move"
        fixed = (rule or {}).get("max_distance")
        if fixed is not None:
            try:
                fixed_val = int(fixed)
            except Exception:
                fixed_val = 0
            if fixed_val > 0:
                from ..utility.event_bus import append_dice
                player = getattr(unit.get_parent_army(), "player", None)
                if player is not None:
                    append_dice(player, f"{source} fixed distance: {fixed_val}\" for {unit.name}")
                return int(fixed_val)

        roll_spec = str((rule or {}).get("distance_roll", "") or "D6").strip().upper() or "D6"
        from ..utility.dice import get_roll
        base_roll = int(get_roll(roll_spec) or 0)
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(player, f"{source} roll: {int(base_roll)}\" for {unit.name}")
        return int(base_roll)

    def attempt_charge(
        self,
        charging_unit: 'Unit',
        target_unit: 'Unit',
        *,
        out_of_turn: bool = False,
        count_as_charged: bool = True,
    ) -> Optional[bool]:
        """Attempt a charge move with the given unit against the target.

        According to 10th edition rules, a successful charge requires at least one model
        of the charging unit to end their charge with edge-to-edge distance of 1" or less
        from at least one model in the target unit.

        CRITICAL: If the charge roll is insufficient to reach within 1" of the enemy,
        the charge fails completely and NO MODELS MOVE AT ALL.
        out_of_turn: allow charges outside the active player's turn.
        count_as_charged: if False, do not apply the charge bonus (e.g., Heroic Intervention).
        """
        declared = self.declare_charge(charging_unit, [target_unit], out_of_turn=out_of_turn)
        if not declared:
            return False

        # Calculate current edge-to-edge distance between units
        current_distance = self.map.get_distance_between_units(charging_unit, target_unit)

        # For a successful charge, we need to achieve edge-to-edge distance of 1" or less
        # So we need to move: current_distance - 1.0 inches
        distance_needed = max(0, current_distance - 1.0)

        base_charge_roll = int(getattr(charging_unit.round_state, "charge_roll", 0) or 0)
        if not base_charge_roll:
            return None
        individual_dice = list(getattr(charging_unit.round_state, "charge_dice", []) or [])
        charge_roll = self._apply_charge_modifiers(charging_unit, base_charge_roll, target_unit=target_unit)

        print(f"Charge: {charging_unit.name} charging {target_unit.name}")
        print(f"Charge: Current edge-to-edge distance: {current_distance:.1f}\"")
        print(f"Charge: Distance needed to achieve <= 1\" edge-to-edge: {distance_needed:.1f}\"")
        print(f"Charge: Roll {base_charge_roll} (rolled {individual_dice}) (modified: {charge_roll})")

        # CRITICAL RULE: If charge roll is insufficient, charge fails and no models move
        if charge_roll < distance_needed:
            print(
                f"Charge failed: roll {charge_roll}\" insufficient to reach within 1\" "
                f"(needed {distance_needed:.1f}\")"
            )
            print("Charge failed: no models move")
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
            print("Charge failed: invalid positions")
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
        distance_to_target = (dx ** 2 + dy ** 2) ** 0.5
        if distance_to_target == 0:
            print("Charge failed: units are at same position")
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
            # Check if the charge actually achieved engagement range (<= 1.0")
            final_distance = self.map.get_distance_between_units(charging_unit, target_unit)

            if final_distance <= 1.0:
                charging_unit.round_state.charged_this_round = True
                try:
                    charging_unit.round_state.charged_turn = int(getattr(self, "turn", 0) or 0)
                except Exception:
                    charging_unit.round_state.charged_turn = int(getattr(self, "turn", 0) or 0)
                try:
                    current_player = self.get_current_player()
                    charging_unit.round_state.charged_turn_owner = str(getattr(current_player, "id", "") or "")
                except Exception:
                    charging_unit.round_state.charged_turn_owner = ""
                if not count_as_charged:
                    try:
                        charging_unit.mark_charge_bonus_suppressed(self)
                    except Exception:
                        pass
                charging_unit._apply_charge_move_devastating_wounds()
                charging_unit._apply_charge_move_weapon_keyword_bonuses()
                print(
                    f"Charge successful: {charging_unit.name} achieved {final_distance:.1f}\" "
                    f"edge-to-edge distance with {target_unit.name}"
                )
                return True
            print(
                f"Charge failed: {charging_unit.name} achieved {final_distance:.1f}\" edge-to-edge "
                f"distance (not <= 1.0\") with {target_unit.name}"
            )
            # CRITICAL: Revert all model positions if charge failed to achieve engagement range
            # This ensures that NO MODELS MOVE when a charge fails
            print("Charge failed: reverting all model positions - no models should move on failed charge")

            # Restore original positions
            for i, original_pos in enumerate(original_model_positions):
                if i < len(charging_unit.models):
                    charging_unit.models[i].set_location(*original_pos)

            # Unit position is now derived from model positions, no need to restore

            return False
        print("Charge failed: could not move unit")
        # CRITICAL: Restore original positions if charge_move failed completely
        print("Charge failed: reverting all model positions - no models should move on failed charge")

        # Restore original positions
        for i, original_pos in enumerate(original_model_positions):
            if i < len(charging_unit.models):
                charging_unit.models[i].set_location(*original_pos)

        # Unit position is now derived from model positions, no need to restore

        return False

    def _collect_charge_modifiers(
        self,
        charging_unit: 'Unit',
        *,
        target_unit: Optional['Unit'] = None,
    ) -> list[tuple[int, str]]:
        has_siege_crawler = getattr(charging_unit, "has_siege_crawler", None)
        if callable(has_siege_crawler):
            try:
                if bool(has_siege_crawler()):
                    return []
            except Exception:
                pass
        modifiers: list[tuple[int, str]] = []

        # Check for charge modifiers from abilities/enhancements.
        sr = getattr(charging_unit, "special_rules", None)
        if isinstance(sr, dict):
            battle_lust_bonus = int(sr.get("enhancement_battle_lust_bonus_if_unbridled", 0) or 0)
            if battle_lust_bonus:
                army = charging_unit.get_parent_army()
                mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                if mgr is not None and mgr.is_blessing_active_for_unit(
                    "UNBRIDLED_BLOODLUST", charging_unit, battle_round=br
                ):
                    modifiers.append((battle_lust_bonus, "Battle-lust (Unbridled Bloodlust)"))

            bonus = int(sr.get("code_chivalric_charge_bonus", 0) or 0)
            if bonus:
                modifiers.append((bonus, "Code Chivalric"))

            extra = int(sr.get("charge_roll_modifier", 0) or 0)
            if extra:
                modifiers.append((extra, "Charge roll modifier"))

            extra_list = sr.get("charge_roll_modifiers", None)
            if isinstance(extra_list, list):
                for item in extra_list:
                    val = 0
                    source = "Charge roll modifier"
                    if isinstance(item, (list, tuple)) and len(item) >= 1:
                        val = int(item[0] or 0)
                        source = str(item[1] if len(item) > 1 else source)
                    elif isinstance(item, dict):
                        val = int(item.get("value", 0) or 0)
                        source = str(item.get("source", "") or source)
                    else:
                        val = int(item or 0)
                    if val:
                        modifiers.append((val, source))

            if sr.get("ere_we_go_active") is True:
                ere_active = True
                owner = str(sr.get("ere_we_go_turn_owner", "") or "")
                turn = int(sr.get("ere_we_go_turn", 0) or 0)
                if owner or turn:
                    cur_turn = int(getattr(self, "turn", 0) or 0)
                    cur_player = self.get_current_player()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    if owner and owner != cur_owner:
                        ere_active = False
                    if turn and turn != cur_turn:
                        ere_active = False
                if ere_active:
                    modifiers.append((2, "Ere We Go"))

            if sr.get("goretrack_onslaught_active") is True:
                goretrack_active = True
                owner = str(sr.get("goretrack_onslaught_turn_owner", "") or "")
                turn = int(sr.get("goretrack_onslaught_turn", 0) or 0)
                if owner or turn:
                    cur_turn = int(getattr(self, "turn", 0) or 0)
                    cur_player = self.get_current_player()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    if owner and owner != cur_owner:
                        goretrack_active = False
                    if turn and turn != cur_turn:
                        goretrack_active = False
                if goretrack_active:
                    modifiers.append((1, "Goretrack Onslaught"))

        from ..utility.aura_effects import get_aura_advance_charge_roll_modifiers
        _adv_mods, aura_charge_mods = get_aura_advance_charge_roll_modifiers(charging_unit, game_map=self.map)
        for val, source in list(aura_charge_mods or []):
            if val:
                modifiers.append((int(val), source))

        get_mods = getattr(charging_unit, "get_charge_roll_target_strength_modifiers", None)
        if callable(get_mods):
            for val, source in get_mods(target_unit):
                if val:
                    modifiers.append((int(val), source))

        get_kw_mods = getattr(charging_unit, "get_wargear_charge_keyword_modifiers", None)
        if callable(get_kw_mods):
            for val, source in get_kw_mods(target_unit, game=self):
                if val:
                    modifiers.append((int(val), source))

        try:
            targets = []
            if target_unit is None:
                targets = []
            elif isinstance(target_unit, (list, tuple, set)):
                targets = [t for t in list(target_unit or []) if t is not None]
            else:
                targets = [target_unit]
        except Exception:
            targets = [target_unit] if target_unit is not None else []
        for tgt in targets:
            try:
                get_def = getattr(tgt, "get_defensive_charge_roll_modifiers", None)
                if callable(get_def):
                    for val, source in get_def():
                        if val:
                            modifiers.append((int(val), source))
            except Exception:
                continue

        filt = getattr(charging_unit, "_filter_internal_rivalries_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")
        filt = getattr(charging_unit, "_filter_driven_by_ultimate_rage_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")

        return modifiers

    def _get_charge_roll_spec(
        self,
        charging_unit: 'Unit',
        *,
        target_unit: Optional['Unit'] = None,
    ) -> ChargeRollSpec:
        dice_count = 2
        keep_highest = 2
        sr = getattr(charging_unit, "special_rules", None)
        if isinstance(sr, dict):
            try:
                dice_count = int(sr.get("charge_roll_dice_count", dice_count) or dice_count)
            except Exception:
                dice_count = 2
            try:
                keep_highest = int(sr.get("charge_roll_keep_highest", keep_highest) or keep_highest)
            except Exception:
                keep_highest = 2
        dice_count = max(1, int(dice_count or 1))
        keep_highest = max(1, int(keep_highest or 1))
        if keep_highest > dice_count:
            keep_highest = dice_count
        spec = ChargeRollSpec(dice_count=dice_count, keep_highest=keep_highest)
        return spec

    def get_charge_roll_modifiers(
        self,
        charging_unit: 'Unit',
        *,
        target_unit: Optional['Unit'] = None,
    ) -> list[tuple[int, str]]:
        return self._collect_charge_modifiers(charging_unit, target_unit=target_unit)

    def get_max_charge_distance(
        self,
        charging_unit: 'Unit',
        *,
        target_unit: Optional['Unit'] = None,
    ) -> float:
        spec = self._get_charge_roll_spec(charging_unit, target_unit=target_unit)
        base_max = float(max(1, int(spec.keep_highest or spec.dice_count)) * 6)
        mods = self._collect_charge_modifiers(charging_unit, target_unit=target_unit)
        total = 0
        for val, _source in mods:
            try:
                total += int(val)
            except Exception:
                continue
        return max(0.0, base_max + float(total))

    def _apply_charge_modifiers(self, charging_unit: 'Unit', base_roll: int, *, target_unit: Optional['Unit'] = None) -> int:
        """Apply charge roll modifiers based on unit abilities, stratagems, etc."""
        modified_roll = base_roll
        modifiers = self._collect_charge_modifiers(charging_unit, target_unit=target_unit)

        for val, source in modifiers:
            if not val:
                continue
            modified_roll += int(val)
            if val > 0:
                print(f"Charge bonus: +{val} ({source})")
            else:
                print(f"Charge penalty: {val} ({source})")

        return int(modified_roll)

    def get_eligible_charging_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that are eligible to declare charges."""
        eligible_units = []
        
        for unit in player.get_army().units:
            if not unit.is_alive() or not unit.deployed:
                continue
            if not unit.can_declare_charge(self):
                continue

            enemy_units = self.get_enemy_units(player)
            has_valid_targets = any(
                unit.can_declare_charge_against(target, self)
                for target in enemy_units if target.is_alive()
            )
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
