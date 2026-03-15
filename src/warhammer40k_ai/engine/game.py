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
from .descriptor_compiler import compile_descriptor_bundle
from .ruleset import RulesetBundle
from .version_adapter import ensure_version_adapter_boundary
from .tier1_plan import Tier1Plan, build_heuristic_tier1_plan
from .tier2_orchestrator import Tier2TaskBundle, build_tier2_task_bundle
from .time_manager import TimeManager
from .deployment_intent import DeploymentIntent
from .deployment_solver import generate_deployment_candidates
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
        # Adepta Sororitas datasheet tracking:
        # army_id -> enemy unit ids that destroyed one or more ADEPTA SORORITAS units from that army.
        self._adepta_sororitas_destroyers_by_army_id: Dict[str, set[str]] = {}
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
        # Tyranids: Blistering Assault snapshots (attacker -> {target: total_alive_wounds_before_attacks})
        self._blistering_assault_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        # Tyranids: Aggressive Leader-beast snapshots (attacker -> {target: model_count_before_attacks})
        self._aggressive_leader_beast_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        # CSM: Guns Blazing trigger snapshots (attacker -> [reactive shooters])
        self._guns_blazing_shooting_targets: Dict['Unit', List['Unit']] = {}
        # World Eaters: Frenzy (Helbrute) target snapshots (attacker -> [targets])
        self._frenzy_shooting_targets: Dict['Unit', List['Unit']] = {}
        self._frenzy_fight_targets: Dict['Unit', List['Unit']] = {}
        # Drukhari: Pain Parasite snapshots (attacker -> {target: model_count})
        self._pain_parasite_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        self._pain_parasite_fight_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        # Necrons: Repair Barge snapshots (attacker -> {target: total_alive_wounds_before_attacks})
        self._repair_barge_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        self._repair_barge_fight_snapshot: Dict['Unit', Dict['Unit', int]] = {}
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
        return {}

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
                        allow_skip = bool(rule.get("optional_repick_on_destroyed", False)) if isinstance(rule, dict) else False
                        req = request_builder(
                            game=self,
                            source_unit=source_unit,
                            enemy_units=list(self.get_enemy_units(player)),
                            ability_name=str(rule.get("source", "") or "") or None,
                            allow_skip=allow_skip,
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

        def _monarch_request_builder(game, source_unit, enemy_units, ability_name=None, allow_skip=False):
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

        def _methodical_request_builder(game, source_unit, enemy_units, ability_name=None, allow_skip=False):
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

        def _exemplar_rule(u):
            getter = getattr(u, "get_exemplar_of_the_code_rule", None)
            rule = getter() if callable(getter) else None
            if not rule:
                return None
            if not bool(rule.get("repick_on_destroyed", False)):
                return None
            return rule

        def _exemplar_request_builder(game, source_unit, enemy_units, ability_name=None, allow_skip=False):
            army = _resolve_unit_parent_army(source_unit)
            if army is None:
                return None
            get_rule = getattr(source_unit, "get_exemplar_of_the_code_rule", None)
            rule = get_rule() if callable(get_rule) else None
            build_request = getattr(army, "_build_exemplar_of_the_code_request", None)
            if not callable(build_request):
                return None
            return build_request(
                game=game,
                source_unit=source_unit,
                enemy_units=enemy_units,
                rule=rule,
                allow_skip=bool(allow_skip),
            )

        _handle_quarry_repick(_exemplar_rule, "_exemplar_of_the_code_quarry_ids", _exemplar_request_builder)

        def _prey_rule(u):
            getter = getattr(u, "get_prey_selection_rule", None)
            rule = getter() if callable(getter) else None
            if not rule:
                return None
            if not bool(rule.get("repick_on_destroyed", False)):
                return None
            return rule

        def _prey_request_builder(game, source_unit, enemy_units, ability_name=None, allow_skip=False):
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

    def _apply_death_guard_tallyband_entropic_knell_forced_tests(
        self,
        current_player,
        tested_ids: set[str],
    ) -> None:
        if current_player is None:
            return

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

        current_army = _get_army(current_player)
        if current_army is None:
            return

        for enemy_player in [p for p in (self.players or []) if p is not current_player]:
            army = _get_army(enemy_player)
            if army is None:
                continue
            mgr = getattr(army, "death_guard_detachments", None)
            if mgr is None:
                continue
            resolve_fn = getattr(mgr, "resolve_tallyband_entropic_knell_forced_tests", None)
            if not callable(resolve_fn):
                continue
            resolve_fn(
                game=self,
                opponent_player=current_player,
                tested_ids=tested_ids,
            )

    def _apply_csm_dread_talons_terror_descends_forced_tests(self, current_player, tested_ids: set[str]) -> None:
        if current_player is None:
            return

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

        current_army = _get_army(current_player)
        if current_army is None:
            return

        for enemy_player in [p for p in (self.players or []) if p is not current_player]:
            army = _get_army(enemy_player)
            if army is None:
                continue
            mgr = getattr(army, "chaos_space_marines_detachments", None)
            if mgr is None:
                continue
            is_dread_talons = bool(getattr(mgr, "is_dread_talons", lambda: False)())
            is_nightmare_hunt = bool(getattr(mgr, "is_nightmare_hunt", lambda: False)())
            if not (is_dread_talons or is_nightmare_hunt):
                continue
            in_range_fn = getattr(mgr, "terror_descends_target_in_range", None)
            suppress_fn = getattr(mgr, "terror_descends_apply_test_suppression", None)
            test_modifier_fn = getattr(mgr, "csm_terror_forced_battleshock_test_modifier", None)
            if not callable(in_range_fn) or not callable(suppress_fn):
                continue

            seen_targets: set[str] = set()
            for unit in list(getattr(current_army, "units", []) or []):
                if unit is None:
                    continue
                get_root = getattr(unit, "get_attached_unit_root", None)
                root = get_root() if callable(get_root) else unit
                if root is None:
                    continue
                unit_id = str(get_entity_id(root) or "")
                if not unit_id or unit_id in seen_targets:
                    continue
                seen_targets.add(unit_id)

                is_alive = getattr(root, "is_alive", None)
                if callable(is_alive) and not bool(is_alive()):
                    continue
                if not bool(getattr(root, "deployed", True)):
                    continue
                reserve_status = str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower()
                if reserve_status != "deployed":
                    continue
                is_in_reserves = getattr(root, "is_in_reserves", None)
                if callable(is_in_reserves) and bool(is_in_reserves()):
                    continue
                if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
                    continue

                below_starting = getattr(root, "is_below_starting_strength", None)
                if not callable(below_starting) or not bool(below_starting()):
                    continue
                if not bool(in_range_fn(root)):
                    continue

                already_tested = unit_id in tested_ids
                suppress_fn(
                    root,
                    phase_name="COMMAND_PHASE",
                    allow_current_test=not already_tested,
                )
                if already_tested:
                    continue

                if callable(test_modifier_fn):
                    test_modifier, source = test_modifier_fn(root)
                    if int(test_modifier or 0):
                        target_sr = getattr(root, "special_rules", None)
                        if not isinstance(target_sr, dict):
                            target_sr = {}
                        target_sr = dict(target_sr)
                        current = int(target_sr.get("battle_shock_test_modifier", 0) or 0)
                        target_sr["battle_shock_test_modifier"] = int(current + int(test_modifier))
                        source_name = str(source or "").strip()
                        if source_name:
                            reasons = list(target_sr.get("battle_shock_test_modifier_reasons", []) or [])
                            reasons.append(source_name)
                            target_sr["battle_shock_test_modifier_reasons"] = reasons
                        root.special_rules = target_sr

                take_test = getattr(root, "take_battle_shock_test", None)
                if callable(take_test):
                    take_test(int(getattr(self, "turn", 0) or 0))
                tested_ids.add(unit_id)

    def _apply_space_marines_the_angelic_host_visage_of_death_forced_tests(
        self,
        current_player,
        tested_ids: set[str],
    ) -> None:
        if current_player is None:
            return

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

        current_army = _get_army(current_player)
        if current_army is None:
            return

        seen_targets: set[str] = set()
        for enemy_player in [p for p in (self.players or []) if p is not current_player]:
            army = _get_army(enemy_player)
            if army is None:
                continue
            mgr = getattr(army, "space_marines_detachments", None)
            if mgr is None:
                continue
            is_angelic_host = bool(getattr(mgr, "is_the_angelic_host", lambda: False)())
            if not is_angelic_host:
                continue
            get_sources = getattr(mgr, "the_angelic_host_visage_of_death_sources", None)
            if not callable(get_sources):
                continue
            sources = list(get_sources() or [])
            if not sources:
                continue

            for unit in list(getattr(current_army, "units", []) or []):
                if unit is None:
                    continue
                get_root = getattr(unit, "get_attached_unit_root", None)
                root = get_root() if callable(get_root) else unit
                if root is None:
                    continue
                unit_id = str(get_entity_id(root) or "")
                if not unit_id or unit_id in seen_targets:
                    continue
                seen_targets.add(unit_id)
                if unit_id in tested_ids:
                    continue

                is_alive = getattr(root, "is_alive", None)
                if callable(is_alive) and not bool(is_alive()):
                    continue
                if not bool(getattr(root, "deployed", True)):
                    continue
                reserve_status = str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower()
                if reserve_status != "deployed":
                    continue
                is_in_reserves = getattr(root, "is_in_reserves", None)
                if callable(is_in_reserves) and bool(is_in_reserves()):
                    continue
                if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
                    continue

                in_any_engagement = False
                for source in list(sources or []):
                    if not isinstance(source, dict):
                        continue
                    source_unit = source.get("unit")
                    bearer_model = source.get("bearer_model")
                    if source_unit is None or bearer_model is None:
                        continue

                    excluded = {
                        str(v or "").strip().upper()
                        for v in list(source.get("exclude_keywords_any", ()) or ())
                        if str(v or "").strip()
                    }
                    if excluded:
                        has_keyword = getattr(root, "has_any_keyword", None)
                        if callable(has_keyword):
                            if any(bool(has_keyword(keyword)) for keyword in sorted(excluded)):
                                continue
                        else:
                            all_keywords = {
                                str(v or "").strip().upper()
                                for v in list(getattr(root, "keywords", []) or [])
                                if str(v or "").strip()
                            }
                            all_keywords.update(
                                str(v or "").strip().upper()
                                for v in list(getattr(root, "faction_keywords", []) or [])
                                if str(v or "").strip()
                            )
                            if all_keywords & excluded:
                                continue

                    in_range = False
                    in_range_fn = getattr(source_unit, "_model_within_engagement_range_of_unit", None)
                    if callable(in_range_fn):
                        try:
                            in_range = bool(in_range_fn(bearer_model, root))
                        except Exception:
                            in_range = False
                    if not in_range:
                        game_map = getattr(self, "map", None)
                        if game_map is not None:
                            try:
                                in_range = bool(game_map.is_within_engagement_range(source_unit, root))
                            except Exception:
                                in_range = False
                    if in_range:
                        in_any_engagement = True
                        break

                if not in_any_engagement:
                    continue
                take_test = getattr(root, "take_battle_shock_test", None)
                if callable(take_test):
                    take_test(int(getattr(self, "turn", 0) or 0))
                tested_ids.add(unit_id)

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

    def _on_battle_shock_test_resolved_enemy_failed_battleshock_aura(self, unit=None, passed: bool = False, **_kwargs) -> None:
        if unit is None or passed:
            return

        from ..utility.aura_utils import unit_within_range_of_unit
        from ..utility.event_bus import append_action, append_dice

        root_fn = getattr(unit, "get_attached_unit_root", None)
        target_root = root_fn() if callable(root_fn) else unit
        if target_root is None:
            return
        target_army_fn = getattr(target_root, "get_parent_army", None)
        target_army = target_army_fn() if callable(target_army_fn) else getattr(target_root, "parent_army", None)

        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            source_army = self._get_player_army(player)
            if source_army is None or source_army is target_army:
                continue
            seen_source_ids: set[str] = set()
            for source in list(getattr(source_army, "units", []) or []):
                if source is None:
                    continue
                source_root_fn = getattr(source, "get_attached_unit_root", None)
                source_root = source_root_fn() if callable(source_root_fn) else source
                if source_root is None:
                    continue
                source_id = str(get_entity_id(source_root) or "") or str(id(source_root))
                if source_id in seen_source_ids:
                    continue
                seen_source_ids.add(source_id)
                if not bool(getattr(source_root, "deployed", True)):
                    continue
                if str(getattr(source_root, "reserve_status", "deployed") or "deployed") != "deployed":
                    continue
                in_reserves_fn = getattr(source_root, "is_in_reserves", None)
                if callable(in_reserves_fn) and bool(in_reserves_fn()):
                    continue
                is_alive_fn = getattr(source_root, "is_alive", None)
                if callable(is_alive_fn) and not bool(is_alive_fn()):
                    continue
                specs_fn = getattr(source_root, "unit_enemy_failed_battleshock_mortal_heal_aura_specs", None)
                if not callable(specs_fn):
                    continue
                specs = list(specs_fn() or [])
                if not specs:
                    continue

                for spec in specs:
                    required_model_name = str(spec.get("required_model_name", "") or "").strip()
                    if required_model_name:
                        contains_fn = getattr(source_root, "_attached_unit_contains_model_named", None)
                        if callable(contains_fn):
                            if not bool(contains_fn(required_model_name)):
                                continue
                        else:
                            fallback_contains_fn = getattr(source_root, "_unit_contains_model_named", None)
                            if not callable(fallback_contains_fn):
                                continue
                            if not bool(fallback_contains_fn(required_model_name)):
                                continue
                    try:
                        range_value = float(spec.get("range", 0.0) or 0.0)
                    except (TypeError, ValueError):
                        range_value = 0.0
                    if range_value <= 0.0:
                        continue
                    if not unit_within_range_of_unit(
                        source_root,
                        target_root,
                        range_value,
                        use_attached_aggregate=True,
                    ):
                        continue

                    mortal_expr = str(spec.get("mortal_wounds_roll", "") or "").strip().upper()
                    heal_expr = str(spec.get("heal_roll", "") or "").strip().upper()
                    if not mortal_expr or not heal_expr:
                        continue

                    mortal = int(get_roll(mortal_expr) or 0)
                    if mortal > 0:
                        apply_mortal_fn = getattr(target_root, "_apply_mortal_wounds_to_unit", None)
                        if callable(apply_mortal_fn):
                            apply_mortal_fn(target_root, mortal, game_map=getattr(self, "map", None))

                    heal_roll = int(get_roll(heal_expr) or 0)
                    healed = 0
                    healed_model_name = ""
                    if heal_roll > 0:
                        get_models_fn = getattr(source_root, "get_attached_unit_models", None)
                        if callable(get_models_fn):
                            source_models = list(get_models_fn() or [])
                        else:
                            source_models = list(getattr(source_root, "models", []) or [])

                        candidates: list[tuple[int, str, str, object, int, int]] = []
                        for model in source_models:
                            if not bool(getattr(model, "is_alive", True)):
                                continue
                            base_wounds = int(
                                getattr(
                                    model,
                                    "_base_wounds",
                                    getattr(model, "base_wounds", getattr(model, "wounds", 0)),
                                )
                                or 0
                            )
                            current_wounds = int(getattr(model, "wounds", 0) or 0)
                            missing = int(base_wounds - current_wounds)
                            if missing <= 0:
                                continue
                            candidates.append(
                                (
                                    missing,
                                    str(get_entity_id(model) or ""),
                                    str(getattr(model, "name", "") or ""),
                                    model,
                                    base_wounds,
                                    current_wounds,
                                )
                            )

                        if candidates:
                            candidates.sort(key=lambda item: (-int(item[0]), item[1], item[2]))
                            _missing, _model_id, _model_name, heal_model, base_wounds, current_wounds = candidates[0]
                            healed_model_name = str(getattr(heal_model, "name", "Model") or "Model")
                            before = int(getattr(heal_model, "wounds", 0) or 0)
                            heal_fn = getattr(heal_model, "heal", None)
                            if callable(heal_fn):
                                heal_fn(int(heal_roll))
                            else:
                                heal_model.wounds = int(min(int(base_wounds), int(current_wounds + heal_roll)))
                                check_profile_fn = getattr(heal_model, "_check_damaged_profile", None)
                                if callable(check_profile_fn):
                                    check_profile_fn()
                            after = int(getattr(heal_model, "wounds", 0) or 0)
                            healed = max(0, int(after - before))

                    ability_name = str(spec.get("source", "") or "Failed Battle-shock aura").strip() or "Failed Battle-shock aura"
                    append_dice(
                        player,
                        (
                            f"{ability_name}: {getattr(target_root, 'name', 'Unit')} failed Battle-shock; "
                            f"{mortal_expr}={int(mortal)}, {heal_expr}={int(heal_roll)}."
                        ),
                    )
                    outcome_parts: list[str] = []
                    if mortal > 0:
                        outcome_parts.append(f"{getattr(target_root, 'name', 'Unit')} suffers {int(mortal)} mortal wounds")
                    else:
                        outcome_parts.append(f"{getattr(target_root, 'name', 'Unit')} suffers no mortal wounds")
                    if healed > 0:
                        outcome_parts.append(f"{healed_model_name} regains {int(healed)} wound(s)")
                    else:
                        outcome_parts.append("no wounds are regained")
                    append_action(player, f"{ability_name}: {'; '.join(outcome_parts)}.")

    def _on_battle_shock_test_resolved_acts_of_faith(self, unit=None, passed: bool = False, **_kwargs) -> None:
        if unit is None:
            return
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            army = self._get_player_army(player)
            if army is None:
                continue
            mgr = getattr(army, "adepta_sororitas_detachments", None)
            if mgr is None:
                continue
            on_resolved = getattr(mgr, "on_divine_aspect_battle_shock_resolved", None)
            if not callable(on_resolved):
                continue
            on_resolved(unit, passed=bool(passed), game=self)

    def _on_battle_shock_test_resolved_voice_of_command(self, unit=None, passed: bool = False, **_kwargs) -> None:
        if unit is None or passed:
            return
        root_fn = getattr(unit, "get_attached_unit_root", None)
        root = root_fn() if callable(root_fn) else unit
        if root is None:
            return
        persist_fn = getattr(root, "orders_persist_while_battle_shocked", None)
        if callable(persist_fn):
            try:
                if bool(persist_fn()):
                    return
            except Exception:
                pass

        army_fn = getattr(root, "get_parent_army", None)
        army = army_fn() if callable(army_fn) else getattr(root, "parent_army", None)
        if army is None:
            return
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None:
            try:
                from ..rules.voice_of_command import VoiceOfCommandManager

                mgr = VoiceOfCommandManager(army)
                army.voice_of_command = mgr
            except Exception:
                return
        clear_order = getattr(mgr, "clear_order", None)
        if not callable(clear_order):
            return
        clear_order(root)
        members = []
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            try:
                members = list(get_members() or [])
            except Exception:
                members = []
        if not members:
            members = [root]
        for member in list(members or []):
            if member is None or member is root:
                continue
            clear_order(member)
        for leader in list(getattr(root, "attached_leaders", []) or []):
            if leader is None:
                continue
            clear_order(leader)

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
            root.apply_reanimation_protocols(
                d3,
                game_map=game_map,
                is_human=is_human,
                provider=provider,
                roll_expr="D3",
            )

    def _apply_command_phase_regain_wounds(self, current_player, *, timing: str = "start") -> None:
        if current_player is None:
            raise RuntimeError("Command phase regain wounds requires a current player.")
        army = current_player.get_army()
        if army is None:
            raise RuntimeError("Command phase regain wounds requires an army.")
        timing_key = str(timing or "start").strip().lower()
        if timing_key not in {"start", "end"}:
            raise RuntimeError("Command phase regain wounds timing must be 'start' or 'end'.")

        def _matches_command_phase_regain_timing(low: str) -> bool:
            plain = re.sub(r"[^a-z0-9]+", " ", str(low or "")).strip()
            if not plain:
                return False
            explicit_end = bool(
                re.search(
                    r"(?:at\s+the\s+)?end\s+of\s+(?:(?:each|either)\s+player\s+s|(?:each\s+of\s+)?your)\s+command\s+phases?",
                    plain,
                )
            )
            explicit_start = bool(
                re.search(
                    r"(?:at\s+the\s+)?start\s+of\s+(?:(?:each|either)\s+player\s+s|(?:each\s+of\s+)?your)\s+command\s+phases?",
                    plain,
                )
            )
            generic_in = bool(
                re.search(
                    r"in\s+(?:(?:each|either)\s+player\s+s|(?:each\s+of\s+)?your)\s+command\s+phases?",
                    plain,
                )
            )
            if timing_key == "end":
                return explicit_end
            if explicit_end and not explicit_start:
                return False
            return explicit_start or generic_in

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
                if "command phase" not in low or "regains" not in low or "wound" not in low:
                    continue
                if not _matches_command_phase_regain_timing(low):
                    continue
                m_single = re.search(
                    r"one model in this unit regains(?:\s+up\s+to)?\s+(\d+|d3)\s+lost wounds?",
                    low,
                )
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
                    if "command phase" not in low or "regains" not in low or "wound" not in low:
                        continue
                    if not _matches_command_phase_regain_timing(low):
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
                    m = re.search(r"regains?\s+(?:up\s+to\s+)?(\d+|d3)\s+lost wounds?", low)
                    if not m:
                        continue
                    token = str(m.group(1) or "").strip().lower()
                    if token == "d3":
                        amount = int(get_roll("D3") or 0)
                    else:
                        amount = int(token or 0)
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
        next_scope = str(getattr(mgr, "next_call_scope", lambda **_k: "all")(game=self, player=player) or "all").strip().lower()
        is_second_call = next_scope == "bully_boyz_restricted"
        call_number = int(getattr(mgr, "calls_this_battle", 0) or 0) + 1
        ability_label = "Waaagh! (Bully Boyz second call)" if is_second_call else "Waaagh!"
        ctx = {
            "ability_name": ability_label,
            "phase": "Command phase",
            "waaagh_call_number": int(call_number),
            "waaagh_scope": next_scope,
        }
        if is_second_call:
            message = "Call second Waaagh!? (Bully Boyz: WARBOSS, Nobz, and Meganobz units only)"
        else:
            message = "Call Waaagh!? (First call this battle)"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="waaagh",
            ability_name=ability_label,
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

    def _maybe_prompt_mission_tactics(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Mission Tactics prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Mission Tactics prompt requires an army.")
        sm_mgr = getattr(army, "space_marines_detachments", None)
        if sm_mgr is None:
            return
        can_select = getattr(sm_mgr, "can_select_mission_tactic", None)
        if not callable(can_select) or not bool(can_select(game=self)):
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        options = list(getattr(sm_mgr, "get_available_mission_tactics", lambda: [])() or [])
        if not options:
            return

        army_id = str(get_entity_id(army) or "")
        battle_round = int(getattr(self, "turn", 0) or 0)
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_MISSION_TACTIC:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("army_id", "")) == army_id and int(ctx.get("battle_round", battle_round) or battle_round) == battle_round:
                    return

        req_options = [
            DecisionOption.create(
                "None",
                payload={"skip": True, "summary": "Do not select a Mission Tactic this Command phase.", "army_id": army_id},
            )
        ]
        for opt in options:
            key = str(opt or "").strip()
            if not key:
                continue
            label = str(getattr(sm_mgr, "mission_tactic_label", lambda _k: _k)(key) or key)
            req_options.append(
                DecisionOption.create(
                    label,
                    payload={"choice_key": key, "summary": label, "army_id": army_id},
                )
            )
        if not req_options:
            return
        req = DecisionRequest.create(
            DECISION_CHOOSE_MISSION_TACTIC,
            "Select Mission Tactic.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"army_id": army_id, "battle_round": battle_round},
        )
        if hasattr(self, "request_decision"):
            self.request_decision(req)

    def _maybe_prompt_angelic_legacy(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Angelic Legacy prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Angelic Legacy prompt requires an army.")
        sm_mgr = getattr(army, "space_marines_detachments", None)
        if sm_mgr is None:
            return
        if not getattr(sm_mgr, "can_select_angelic_legacy", lambda **_k: False)(game=self):
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        options = list(getattr(sm_mgr, "get_angelic_legacy_pair_options", lambda: [])() or [])
        if not options:
            return
        from ..engine.decision_kinds import DECISION_CHOOSE_ANGELIC_LEGACY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        army_id = get_entity_id(army)
        battle_round = int(getattr(self, "turn", 0) or 0)
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_ANGELIC_LEGACY:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if (
                    str(ctx.get("army_id", "")) == str(army_id)
                    and int(ctx.get("battle_round", battle_round) or battle_round) == battle_round
                ):
                    return
        req_options = []
        for pair in list(options or []):
            keys = [str(v or "").strip().upper() for v in list(pair or []) if str(v or "").strip()]
            if len(keys) != 2:
                continue
            labels = [str(getattr(sm_mgr, "angelic_legacy_label", lambda _k: _k)(key) or key) for key in keys]
            req_options.append(
                DecisionOption.create(
                    " + ".join(labels),
                    payload={
                        "choice_keys": list(keys),
                        "summary": f"{labels[0]} and {labels[1]}",
                        "army_id": army_id,
                    },
                )
            )
        if not req_options:
            return
        req = DecisionRequest.create(
            DECISION_CHOOSE_ANGELIC_LEGACY,
            "Select two Angelic Legacy abilities.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"army_id": army_id, "battle_round": battle_round},
        )
        if hasattr(self, "request_decision"):
            self.request_decision(req)

    def _maybe_prompt_grim_resolve(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Grim Resolve prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Grim Resolve prompt requires an army.")
        sm_mgr = getattr(army, "space_marines_detachments", None)
        if sm_mgr is None:
            return
        can_select = getattr(sm_mgr, "can_select_grim_resolve_target", None)
        if not callable(can_select) or not bool(can_select(game=self)):
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        targets = list(getattr(sm_mgr, "get_grim_resolve_target_units", lambda **_k: [])(game=self) or [])
        if not targets:
            return

        army_id = str(get_entity_id(army) or "")
        battle_round = int(getattr(self, "turn", 0) or 0)
        player_id = str(getattr(player, "id", "") or "")
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "grim_resolve_target":
                    continue
                if str(ctx.get("army_id", "") or "") != army_id:
                    continue
                if str(ctx.get("player_id", "") or "") != player_id:
                    continue
                if int(ctx.get("battle_round", battle_round) or battle_round) != battle_round:
                    continue
                return

        options = []
        for unit in list(targets):
            unit_id = str(get_entity_id(unit) or "")
            if not unit_id:
                continue
            unit_name = str(getattr(unit, "name", "Unit") or "Unit")
            options.append(
                DecisionOption.create(
                    unit_name,
                    payload={"target_unit_id": unit_id, "unit_id": unit_id, "army_id": army_id},
                )
            )
        if not options:
            return
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Grim Resolve: select one ADEPTUS ASTARTES unit to gain +1 Objective Control until your next Command phase.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "grim_resolve_target",
                "ability_name": "Grim Resolve",
                "phase": "Command phase",
                "army_id": army_id,
                "player_id": player_id,
                "battle_round": battle_round,
            },
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

    def _maybe_prompt_csm_experimental_augmentations(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Experimental Augmentations prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Experimental Augmentations prompt requires an army.")
        mgr = getattr(army, "chaos_space_marines_detachments", None)
        battle_round = int(getattr(self, "turn", 0) or 0)
        can_select = getattr(mgr, "can_select_experimental_augmentations", None) if mgr is not None else None
        if not callable(can_select) or not bool(can_select(game=self, battle_round=battle_round)):
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        options = list(getattr(mgr, "experimental_augmentations_catalog", lambda: [])() or [])
        army_id = get_entity_id(army)
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "experimental_augmentations_choice":
                    continue
                if str(ctx.get("army_id", "") or "") != str(army_id):
                    continue
                if int(ctx.get("battle_round", battle_round) or battle_round) == battle_round:
                    return
        req_options = [
            DecisionOption.create(
                "Roll 2D6 (randomly select two)",
                payload={
                    "mode": "random",
                    "choice_key": "ROLL",
                    "random": True,
                    "summary": "Roll two dice and apply both results; duplicates have no additional effect.",
                    "army_id": army_id,
                },
            )
        ]
        available_keys = []
        for opt in options:
            key = getattr(opt, "key", None)
            if not key:
                continue
            available_keys.append(str(key))
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or ""
            req_options.append(
                DecisionOption.create(
                    name,
                    payload={
                        "mode": "manual",
                        "choice_key": str(key),
                        "summary": summary,
                        "army_id": army_id,
                    },
                )
            )
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Experimental Augmentations: select one augmentation or roll 2D6.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={
                "ability": "experimental_augmentations_choice",
                "ability_name": "Experimental Augmentations",
                "army_id": army_id,
                "battle_round": battle_round,
                "available_choice_keys": list(available_keys),
            },
        )
        self.request_decision(req)

    def _maybe_prompt_csm_tyrannical_motivation(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Tyrannical Motivation prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Tyrannical Motivation prompt requires an army.")
        mgr = getattr(army, "chaos_space_marines_detachments", None)
        queue_fn = getattr(mgr, "queue_tyrannical_motivation_choice_request", None) if mgr is not None else None
        if callable(queue_fn):
            queue_fn(game=self, player=player)

    def _maybe_prompt_csm_vendetta(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Vendetta prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Vendetta prompt requires an army.")
        mgr = getattr(army, "chaos_space_marines_detachments", None)
        queue_fn = getattr(mgr, "queue_renegade_warband_vendetta_choice_request", None) if mgr is not None else None
        if callable(queue_fn):
            queue_fn(game=self, player=player)

    def _maybe_prompt_csm_focus_of_hatred(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Focus of Hatred prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Focus of Hatred prompt requires an army.")
        mgr = getattr(army, "chaos_space_marines_detachments", None)
        queue_fn = getattr(mgr, "queue_veterans_focus_of_hatred_choice_request", None) if mgr is not None else None
        if callable(queue_fn):
            queue_fn(game=self, player=player)

    def _maybe_prompt_csm_soul_link(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Soul Link prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Soul Link prompt requires an army.")
        mgr = getattr(army, "chaos_space_marines_detachments", None)
        queue_fn = getattr(mgr, "queue_deceptors_soul_link_choice_request", None) if mgr is not None else None
        if callable(queue_fn):
            queue_fn(game=self, player=player)

    def _maybe_prompt_csm_forges_blessing(self) -> None:
        player = self.get_current_player()
        if player is None:
            raise RuntimeError("Forge's Blessing prompt requires current player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError("Forge's Blessing prompt requires an army.")
        mgr = getattr(army, "chaos_space_marines_detachments", None)
        queue_fn = getattr(mgr, "queue_soulforged_forges_blessing_choice_request", None) if mgr is not None else None
        if callable(queue_fn):
            queue_fn(game=self, player=player)

    def _refresh_csm_tyrannical_motivation_phase_state(self) -> None:
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            army = player.get_army()
            if army is None:
                continue
            mgr = getattr(army, "chaos_space_marines_detachments", None)
            refresh_fn = getattr(mgr, "refresh_tyrannical_motivation_phase_state", None) if mgr is not None else None
            if callable(refresh_fn):
                refresh_fn(game=self)

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
        turn_ending_player_id = str(getattr(turn_ending_player, "id", "") or "")
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

            ae_mgr = getattr(army, "aeldari_detachments", None)
            ride_candidates_fn = (
                getattr(ae_mgr, "ride_the_wind_end_of_opponent_turn_candidates", None)
                if ae_mgr is not None else None
            )
            ride_max_units_fn = (
                getattr(ae_mgr, "ride_the_wind_end_of_opponent_turn_max_units", None)
                if ae_mgr is not None else None
            )
            ride_resolved_fn = (
                getattr(ae_mgr, "ride_the_wind_phase_already_resolved", None)
                if ae_mgr is not None else None
            )
            if callable(ride_candidates_fn):
                resolved = False
                if callable(ride_resolved_fn):
                    resolved = bool(ride_resolved_fn(game=self, turn_ending_player_id=turn_ending_player_id))
                if not resolved:
                    ride_candidates = list(
                        ride_candidates_fn(
                            game=self,
                            turn_ending_player=turn_ending_player,
                            game_map=game_map,
                        ) or []
                    )
                    max_units = int(ride_max_units_fn(game=self) or 0) if callable(ride_max_units_fn) else 0
                    max_units = max(0, min(int(max_units), len(ride_candidates)))
                    candidate_ids = [
                        str(get_entity_id(unit) or "")
                        for unit in list(ride_candidates or [])
                        if str(get_entity_id(unit) or "").strip()
                    ]
                    candidate_ids = sorted(set(candidate_ids))
                    if candidate_ids and max_units > 0:
                        phase_key = f"{int(getattr(self, 'turn', 0) or 0)}:{turn_ending_player_id}"
                        pending = False
                        queue = getattr(self, "decision_queue", None)
                        if queue is not None and hasattr(queue, "list"):
                            for req in list(queue.list() or []):
                                if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
                                    continue
                                if str(getattr(req, "player_id", "") or "") != str(getattr(opp, "id", "") or ""):
                                    continue
                                req_ctx = dict(getattr(req, "context", {}) or {})
                                if str(req_ctx.get("ability", "") or "").strip().lower() != "ride_the_wind_end_of_opponent_turn":
                                    continue
                                if str(req_ctx.get("turn_key", "") or "") != phase_key:
                                    continue
                                pending = True
                                break
                        if not pending:
                            request = DecisionRequest.create(
                                DECISION_SELECT_REALM_OF_CHAOS_UNITS,
                                "Ride the Wind: select units to place into Strategic Reserves.",
                                player_id=getattr(opp, "id", None),
                                options=[
                                    DecisionOption.create("Confirm selection", payload={"action": "confirm"}),
                                    DecisionOption.create("Do not use", payload={"action": "skip"}),
                                ],
                                context={
                                    "ability": "ride_the_wind_end_of_opponent_turn",
                                    "ability_name": "Ride the Wind",
                                    "allowed_unit_ids": list(candidate_ids),
                                    "outside_shadow_unit_ids": [],
                                    "max_units": int(max_units),
                                    "selection_effect": "enter_strategic_reserves",
                                    "selection_effect_reason": "Ride the Wind",
                                    "turn_key": phase_key,
                                    "turn_ending_player_id": turn_ending_player_id,
                                    "title": "Ride the Wind",
                                    "subtitle": f"Select up to {int(max_units)} ASURYANI MOUNTED or VYPER unit(s)",
                                    "instruction": (
                                        "Choose units to remove from the battlefield and place into Strategic Reserves, "
                                        "or select None to skip."
                                    ),
                                    "skip_label": "None (do not use this ability)",
                                },
                            )
                            self.request_decision(request)

            sm_mgr = getattr(army, "space_marines_detachments", None)
            wings_candidates_fn = (
                getattr(sm_mgr, "upon_wings_of_fire_end_of_opponent_turn_candidates", None)
                if sm_mgr is not None else None
            )
            wings_max_units_fn = (
                getattr(sm_mgr, "upon_wings_of_fire_end_of_opponent_turn_max_units", None)
                if sm_mgr is not None else None
            )
            wings_resolved_fn = (
                getattr(sm_mgr, "upon_wings_of_fire_phase_already_resolved", None)
                if sm_mgr is not None else None
            )
            if callable(wings_candidates_fn):
                resolved = False
                if callable(wings_resolved_fn):
                    resolved = bool(
                        wings_resolved_fn(
                            game=self,
                            turn_ending_player_id=turn_ending_player_id,
                        )
                    )
                if not resolved:
                    wings_candidates = list(
                        wings_candidates_fn(
                            game=self,
                            turn_ending_player=turn_ending_player,
                            game_map=game_map,
                        ) or []
                    )
                    max_units = int(wings_max_units_fn(game=self) or 0) if callable(wings_max_units_fn) else 0
                    max_units = max(0, min(int(max_units), len(wings_candidates)))
                    candidate_ids = [
                        str(get_entity_id(unit) or "")
                        for unit in list(wings_candidates or [])
                        if str(get_entity_id(unit) or "").strip()
                    ]
                    candidate_ids = sorted(set(candidate_ids))
                    if candidate_ids and max_units > 0:
                        phase_key = f"{int(getattr(self, 'turn', 0) or 0)}:{turn_ending_player_id}"
                        pending = False
                        queue = getattr(self, "decision_queue", None)
                        if queue is not None and hasattr(queue, "list"):
                            for req in list(queue.list() or []):
                                if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
                                    continue
                                if str(getattr(req, "player_id", "") or "") != str(getattr(opp, "id", "") or ""):
                                    continue
                                req_ctx = dict(getattr(req, "context", {}) or {})
                                if str(req_ctx.get("ability", "") or "").strip().lower() != "upon_wings_of_fire_end_of_opponent_turn":
                                    continue
                                if str(req_ctx.get("turn_key", "") or "") != phase_key:
                                    continue
                                pending = True
                                break
                        if not pending:
                            request = DecisionRequest.create(
                                DECISION_SELECT_REALM_OF_CHAOS_UNITS,
                                "Upon Wings of Fire: select units to place into Strategic Reserves.",
                                player_id=getattr(opp, "id", None),
                                options=[
                                    DecisionOption.create("Confirm selection", payload={"action": "confirm"}),
                                    DecisionOption.create("Do not use", payload={"action": "skip"}),
                                ],
                                context={
                                    "ability": "upon_wings_of_fire_end_of_opponent_turn",
                                    "ability_name": "Upon Wings of Fire",
                                    "allowed_unit_ids": list(candidate_ids),
                                    "outside_shadow_unit_ids": [],
                                    "max_units": int(max_units),
                                    "selection_effect": "enter_strategic_reserves",
                                    "selection_effect_reason": "Upon Wings of Fire",
                                    "turn_key": phase_key,
                                    "turn_ending_player_id": turn_ending_player_id,
                                    "title": "Upon Wings of Fire",
                                    "subtitle": f"Select up to {int(max_units)} ADEPTUS ASTARTES JUMP PACK unit(s)",
                                    "instruction": (
                                        "Choose units to remove from the battlefield and place into Strategic Reserves, "
                                        "or select None to skip."
                                    ),
                                    "skip_label": "None (do not use this ability)",
                                },
                            )
                            self.request_decision(request)

            ne_mgr = getattr(army, "necrons_detachments", None)
            hyper_candidates_fn = (
                getattr(ne_mgr, "hyperphasing_end_of_opponent_turn_candidates", None)
                if ne_mgr is not None else None
            )
            hyper_max_units_fn = (
                getattr(ne_mgr, "hyperphasing_end_of_opponent_turn_max_units", None)
                if ne_mgr is not None else None
            )
            hyper_resolved_fn = (
                getattr(ne_mgr, "hyperphasing_phase_already_resolved", None)
                if ne_mgr is not None else None
            )
            if callable(hyper_candidates_fn):
                resolved = False
                if callable(hyper_resolved_fn):
                    resolved = bool(
                        hyper_resolved_fn(
                            game=self,
                            turn_ending_player_id=turn_ending_player_id,
                        )
                    )
                if not resolved:
                    hyper_candidates = list(
                        hyper_candidates_fn(
                            game=self,
                            turn_ending_player=turn_ending_player,
                            game_map=game_map,
                        ) or []
                    )
                    max_units = int(hyper_max_units_fn(game=self) or 0) if callable(hyper_max_units_fn) else 0
                    max_units = max(0, min(int(max_units), len(hyper_candidates)))
                    candidate_ids = [
                        str(get_entity_id(unit) or "")
                        for unit in list(hyper_candidates or [])
                        if str(get_entity_id(unit) or "").strip()
                    ]
                    candidate_ids = sorted(set(candidate_ids))
                    if candidate_ids and max_units > 0:
                        phase_key = f"{int(getattr(self, 'turn', 0) or 0)}:{turn_ending_player_id}"
                        pending = False
                        queue = getattr(self, "decision_queue", None)
                        if queue is not None and hasattr(queue, "list"):
                            for req in list(queue.list() or []):
                                if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
                                    continue
                                if str(getattr(req, "player_id", "") or "") != str(getattr(opp, "id", "") or ""):
                                    continue
                                req_ctx = dict(getattr(req, "context", {}) or {})
                                if str(req_ctx.get("ability", "") or "").strip().lower() != "hyperphasing_end_of_opponent_turn":
                                    continue
                                if str(req_ctx.get("turn_key", "") or "") != phase_key:
                                    continue
                                pending = True
                                break
                        if not pending:
                            request = DecisionRequest.create(
                                DECISION_SELECT_REALM_OF_CHAOS_UNITS,
                                "Hyperphasing: select units to place into Strategic Reserves.",
                                player_id=getattr(opp, "id", None),
                                options=[
                                    DecisionOption.create("Confirm selection", payload={"action": "confirm"}),
                                    DecisionOption.create("Do not use", payload={"action": "skip"}),
                                ],
                                context={
                                    "ability": "hyperphasing_end_of_opponent_turn",
                                    "ability_name": "Hyperphasing",
                                    "allowed_unit_ids": list(candidate_ids),
                                    "outside_shadow_unit_ids": [],
                                    "max_units": int(max_units),
                                    "selection_effect": "enter_strategic_reserves",
                                    "selection_effect_reason": "Hyperphasing",
                                    "turn_key": phase_key,
                                    "turn_ending_player_id": turn_ending_player_id,
                                    "title": "Hyperphasing",
                                    "subtitle": f"Select up to {int(max_units)} NECRONS unit(s)",
                                    "instruction": (
                                        "Choose units to remove from the battlefield and place into Strategic Reserves, "
                                        "or select None to skip."
                                    ),
                                    "skip_label": "None (do not use this ability)",
                                },
                            )
                            self.request_decision(request)

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
                trigger_phase = str(ability.get("trigger_phase", "") or "OPPONENT_TURN_END").strip().upper()
                if not trigger_phase:
                    trigger_phase = "OPPONENT_TURN_END"
                if trigger_phase != "OPPONENT_TURN_END":
                    continue
                if ability_key == "dedicated_gunship":
                    continue
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
                    "trigger_phase": trigger_phase,
                    "once_per_battle": bool(ability.get("once_per_battle")),
                    "return_as_deep_strike": bool(ability.get("return_as_deep_strike", False)),
                    "return_setup_min_enemy_distance_horiz": float(
                        ability.get("return_setup_min_enemy_distance_horiz", 0.0) or 0.0
                    ),
                    "must_arrive_next_movement_phase": bool(
                        ability.get("must_arrive_next_movement_phase", False)
                    ),
                    "turn_ending_player_id": turn_ending_player_id,
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
                    payload={
                        "unit_id": unit_id,
                        "ability_key": ability_key,
                        "once_per_battle": bool(ability.get("once_per_battle")),
                        "return_as_deep_strike": bool(ability.get("return_as_deep_strike", False)),
                        "return_setup_min_enemy_distance_horiz": float(
                            ability.get("return_setup_min_enemy_distance_horiz", 0.0) or 0.0
                        ),
                        "must_arrive_next_movement_phase": bool(
                            ability.get("must_arrive_next_movement_phase", False)
                        ),
                        "turn_ending_player_id": turn_ending_player_id,
                    },
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

    def _get_floating_death_pending_state(self, unit) -> Optional[dict]:
        if unit is None:
            return None
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        pending = sr.get("floating_death_pending", None)
        if not isinstance(pending, dict):
            return None
        return dict(pending)

    def _set_floating_death_pending_state(self, unit, pending: Optional[dict]) -> None:
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if pending is None:
            sr.pop("floating_death_pending", None)
        else:
            sr["floating_death_pending"] = dict(pending)
        unit.special_rules = sr

    def _run_floating_death_sequence(
        self,
        *,
        unit,
        spec: dict,
        model_ids: Optional[list[str]] = None,
    ) -> None:
        if unit is None or not isinstance(spec, dict):
            return
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return
        is_alive = getattr(root, "is_alive", None)
        root_alive = bool(is_alive()) if callable(is_alive) else bool(is_alive)
        if not root_alive:
            self._set_floating_death_pending_state(root, None)
            return
        if not bool(getattr(root, "deployed", True)):
            self._set_floating_death_pending_state(root, None)
            return
        is_in_reserves = getattr(root, "is_in_reserves", None)
        in_reserves = bool(is_in_reserves()) if callable(is_in_reserves) else False
        if in_reserves or bool(getattr(root, "is_embarked", False)):
            self._set_floating_death_pending_state(root, None)
            return
        parent_army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        player = getattr(parent_army, "player", None)
        if player is None:
            self._set_floating_death_pending_state(root, None)
            return

        try:
            range_value = int(spec.get("range", 0) or 0)
        except (TypeError, ValueError):
            range_value = 0
        if range_value <= 0:
            range_value = 3

        enemy_roots = self._collect_enemy_unit_roots(player)
        if not enemy_roots:
            self._set_floating_death_pending_state(root, None)
            return

        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        alive_models = [m for m in list(models or []) if getattr(m, "is_alive", True)]
        if not alive_models:
            self._set_floating_death_pending_state(root, None)
            return

        model_by_id = {}
        for model in alive_models:
            mid = str(get_entity_id(model) or "")
            if mid:
                model_by_id[mid] = model

        if model_ids is None:
            ordered_model_ids = sorted(list(model_by_id.keys()))
        else:
            seen_ids = set()
            ordered_model_ids = []
            for model_id in list(model_ids or []):
                mid = str(model_id or "")
                if not mid or mid in seen_ids:
                    continue
                seen_ids.add(mid)
                if mid in model_by_id:
                    ordered_model_ids.append(mid)

        if not ordered_model_ids:
            self._set_floating_death_pending_state(root, None)
            return

        for index, model_id in enumerate(ordered_model_ids):
            model = model_by_id.get(str(model_id))
            if model is None or not getattr(model, "is_alive", True):
                continue
            candidates = self._enemy_candidates_within_range_of_model(
                model=model,
                enemy_roots=enemy_roots,
                range_value=float(range_value),
            )
            if not candidates:
                continue
            ordered_candidates = sorted(
                [candidate for candidate in list(candidates or []) if candidate is not None],
                key=lambda candidate: str(get_entity_id(candidate) or ""),
            )
            if not ordered_candidates:
                continue
            if len(ordered_candidates) == 1:
                self.resolve_floating_death_mortal_wounds(root, model, ordered_candidates[0], spec)
                enemy_roots = self._collect_enemy_unit_roots(player)
                if not enemy_roots:
                    break
                continue

            remaining_model_ids = [
                str(mid)
                for mid in list(ordered_model_ids[index + 1:] or [])
                if str(mid or "")
            ]
            self._set_floating_death_pending_state(
                root,
                {
                    "spec": dict(spec),
                    "remaining_model_ids": list(remaining_model_ids),
                },
            )
            request = self._queue_mortal_wounds_target_decision(
                player=player,
                unit=root,
                model=model,
                candidates=list(ordered_candidates),
                spec=dict(spec),
                kind="floating_death",
                allow_skip=False,
                phase="Movement phase",
            )
            if request is None:
                self._set_floating_death_pending_state(root, None)
            return

        self._set_floating_death_pending_state(root, None)

    def _continue_floating_death_pending(self, unit=None) -> None:
        if unit is None:
            return
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return
        pending = self._get_floating_death_pending_state(root)
        if not pending:
            return
        spec = dict(pending.get("spec", {}) or {})
        remaining_model_ids = [
            str(model_id or "")
            for model_id in list(pending.get("remaining_model_ids", []) or [])
            if str(model_id or "")
        ]
        self._set_floating_death_pending_state(root, None)
        if not spec:
            get_specs = getattr(root, "unit_floating_death_specs", None)
            specs = list(get_specs() or []) if callable(get_specs) else []
            if not specs:
                return
            spec = dict(specs[0] or {})
        self._run_floating_death_sequence(
            unit=root,
            spec=spec,
            model_ids=list(remaining_model_ids),
        )

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
                tactica_battleline_mode = False
                tactica_battleline_distance = 0
                tactica_battleline_range = 0
                try:
                    tactica_battleline_distance = int(rule.get("battleline_wholly_within_max_distance", 0) or 0)
                except Exception:
                    tactica_battleline_distance = 0
                try:
                    tactica_battleline_range = int(rule.get("battleline_wholly_within_range", 0) or 0)
                except Exception:
                    tactica_battleline_range = 0
                can_tactica_mode = getattr(root, "can_tactica_obliqua_battleline_move", None)
                if (
                    tactica_battleline_distance > 0
                    and tactica_battleline_range > 0
                    and callable(can_tactica_mode)
                ):
                    tactica_battleline_mode = bool(
                        can_tactica_mode(
                            game=self,
                            game_map=self.map,
                            moving_unit=moving_root,
                            range_override=rng,
                        )
                    )

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
                if tactica_battleline_mode:
                    reacting_unit_id = str(maybe_entity_id(root) or "")
                    moving_unit_id = str(maybe_entity_id(moving_root) or "")
                    if not reacting_unit_id or not moving_unit_id:
                        continue
                    message = (
                        f"{getattr(moving_root, 'name', 'Enemy unit')} ended a move within {int(rng)}\" of "
                        f"{getattr(root, 'name', 'unit')}.\n\n"
                        f"{source}: Choose one option:\n"
                        f"- Make a Normal move of up to {move_label}\".\n"
                        f"- Make a Normal move of up to {int(tactica_battleline_distance)}\", provided every model in this unit "
                        f"ends that move wholly within {int(tactica_battleline_range)}\" of one or more friendly ADEPTUS MECHANICUS BATTLELINE units."
                    )
                    request = DecisionRequest.create(
                        DECISION_CONFIRM_YES_NO,
                        source,
                        player_id=getattr(p, "id", None),
                        options=[
                            DecisionOption.create("D6 Move", payload={"choice": True, "tactica_obliqua_mode": "d6"}),
                            DecisionOption.create(
                                f"{int(tactica_battleline_distance)}\" Battleline Move",
                                payload={"choice": True, "tactica_obliqua_mode": "battleline_6"},
                            ),
                            DecisionOption.create("Skip", payload={"choice": False}),
                        ],
                        context={
                            **self._reactive_move_context(
                                kind="tactica_obliqua",
                                unit_id=reacting_unit_id,
                                movement_type="loping_speed",
                                source=source,
                                moving_unit_id=moving_unit_id,
                                range_value=rng,
                            ),
                            "message": message,
                            "tactica_obliqua_battleline_range": int(tactica_battleline_range),
                            "tactica_obliqua_battleline_max_distance": int(tactica_battleline_distance),
                        },
                    )
                    self.request_decision(request)
                else:
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

    def _on_unit_move_ended_floating_death(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key not in ("move", "advance", "fall_back", "charge", "pile_in", "consolidate"):
            return

        get_moving_root = getattr(unit, "get_attached_unit_root", None)
        moving_root = get_moving_root() if callable(get_moving_root) else unit
        if moving_root is None:
            return
        moving_army = moving_root.get_parent_army() if hasattr(moving_root, "get_parent_army") else None

        for player in list(self.players or []):
            if player is None:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            seen: set[str] = set()
            for candidate in list(getattr(army, "units", []) or []):
                if candidate is None:
                    continue
                get_root = getattr(candidate, "get_attached_unit_root", None)
                root = get_root() if callable(get_root) else candidate
                if root is None:
                    continue
                root_id = str(maybe_entity_id(root) or "")
                if not root_id or root_id in seen:
                    continue
                seen.add(root_id)
                if not bool(getattr(root, "deployed", True)):
                    continue
                is_alive = getattr(root, "is_alive", None)
                root_alive = bool(is_alive()) if callable(is_alive) else bool(is_alive)
                if not root_alive:
                    continue
                is_in_reserves = getattr(root, "is_in_reserves", None)
                in_reserves = bool(is_in_reserves()) if callable(is_in_reserves) else False
                if in_reserves or bool(getattr(root, "is_embarked", False)):
                    continue
                if self._get_floating_death_pending_state(root):
                    continue
                get_specs = getattr(root, "unit_floating_death_specs", None)
                if not callable(get_specs):
                    continue
                specs = list(get_specs() or [])
                if not specs:
                    continue

                source_army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                if moving_root is not root and source_army is moving_army:
                    # Floating Death triggers from this unit moving, or enemy units moving.
                    continue

                spec = dict(specs[0] or {})
                self._run_floating_death_sequence(unit=root, spec=spec)

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

    def _queue_chaos_cult_desperate_devotion(self, *, unit=None, action: str | None = None) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "charge"}:
            return
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                resolved = get_root()
            except (AttributeError, RuntimeError, TypeError):
                resolved = None
            if resolved is not None:
                root = resolved
        if root is None:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        if army is None:
            return
        mgr = getattr(army, "chaos_space_marines_detachments", None)
        can_trigger = getattr(mgr, "desperate_devotion_can_trigger", None) if mgr is not None else None
        if not callable(can_trigger):
            return
        if not bool(can_trigger(root, action=action_key, game=self)):
            return
        player = getattr(army, "player", None)
        if player is None:
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        unit_id = str(maybe_entity_id(root) or "")
        if not unit_id:
            return
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        turn = int(getattr(self, "turn", 0) or 0)
        current_player = self.get_current_player()
        owner_id = str(getattr(current_player, "id", "") or "")
        if action_key == "charge":
            message = f"Use Desperate Devotion for {getattr(root, 'name', 'Unit')}? (+2 Charge this phase)"
        else:
            message = (
                f"Use Desperate Devotion for {getattr(root, 'name', 'Unit')}? "
                "(+2 Move and +2 Charge this phase)"
            )
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="desperate_devotion",
            ability_name="Desperate Devotion",
            message=message,
            context={
                "unit_id": unit_id,
                "trigger_action": action_key,
                "phase": phase_name,
                "turn": turn,
                "turn_owner_id": owner_id,
            },
            payload={
                "unit_id": unit_id,
                "trigger_action": action_key,
                "phase": phase_name,
                "turn": turn,
                "turn_owner_id": owner_id,
            },
            instance_key=f"{unit_id}:{turn}:{phase_name}:{owner_id}:desperate_devotion:{action_key}",
        )

    def _queue_csm_twisted_doctrine(
        self,
        *,
        unit=None,
        action: str | None = None,
        set_up_as_reinforcements: bool = False,
    ) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "fall_back", "set_up"}:
            return
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                resolved = get_root()
            except (AttributeError, RuntimeError, TypeError):
                resolved = None
            if resolved is not None:
                root = resolved
        if root is None:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        if army is None:
            return
        mgr = getattr(army, "chaos_space_marines_detachments", None)
        queue_fn = getattr(mgr, "queue_twisted_doctrine_choice_request", None) if mgr is not None else None
        if not callable(queue_fn):
            return
        player = getattr(army, "player", None)
        if player is None:
            return
        queue_fn(
            root,
            action=action_key,
            game=self,
            player=player,
            set_up_as_reinforcements=bool(set_up_as_reinforcements),
        )

    def _on_unit_move_started_detachment_rules(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "fall_back"}:
            return
        if action_key in {"move", "advance"}:
            self._queue_chaos_cult_desperate_devotion(unit=unit, action=action_key)
        self._queue_csm_twisted_doctrine(unit=unit, action=action_key)

    def _on_unit_set_up_csm_detachment_rules(
        self,
        unit=None,
        set_up_as_reinforcements: bool = False,
        used_deep_strike: bool = False,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        self._queue_csm_twisted_doctrine(
            unit=unit,
            action="set_up",
            set_up_as_reinforcements=bool(set_up_as_reinforcements),
        )
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else None
        if army is None:
            return
        mgr = getattr(army, "chaos_space_marines_detachments", None)
        if mgr is None:
            return
        on_unit_set_up = getattr(mgr, "on_unit_set_up", None)
        if not callable(on_unit_set_up):
            return
        on_unit_set_up(
            unit=root,
            game=self,
            set_up_as_reinforcements=bool(set_up_as_reinforcements),
            used_deep_strike=bool(used_deep_strike),
            set_up_from_disembark=False,
        )

    def _on_unit_disembarked_csm_detachment_rules(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None or root is not unit:
            return
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else None
        if army is None:
            return
        mgr = getattr(army, "chaos_space_marines_detachments", None)
        if mgr is None:
            return
        on_unit_set_up = getattr(mgr, "on_unit_set_up", None)
        if not callable(on_unit_set_up):
            return
        on_unit_set_up(
            unit=root,
            game=self,
            set_up_as_reinforcements=False,
            used_deep_strike=False,
            set_up_from_disembark=True,
        )

    def _on_charge_declared_detachment_rules(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        self._queue_chaos_cult_desperate_devotion(unit=unit, action="charge")

    def _on_unit_move_ended_detachment_rules(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key not in ("move", "advance", "fall_back", "charge"):
            return
        try:
            moving_root = unit.get_attached_unit_root()
        except Exception:
            moving_root = unit
        if moving_root is None:
            return
        army = moving_root.get_parent_army()
        if army is None:
            raise RuntimeError("Detachment rule resolution requires a parent army.")

        if action_key == "charge":
            we_mgr = getattr(army, "world_eaters_detachments", None)
            if we_mgr is not None and callable(getattr(we_mgr, "relentless_rage_applies", None)):
                if bool(we_mgr.relentless_rage_applies(moving_root)):
                    # Relentless Rage applies only to WORLD EATERS units.
                    sr = getattr(moving_root, "special_rules", None)
                    if not isinstance(sr, dict):
                        sr = {}
                    sr["relentless_rage_melee_attacks_bonus"] = 1
                    sr["relentless_rage_melee_strength_bonus"] = 2
                    sr["relentless_rage_expires_phase"] = "FIGHT_PHASE"
                    moving_root.special_rules = sr

            cd_mgr = getattr(army, "chaos_daemons_detachments", None)
            if cd_mgr is not None and callable(getattr(cd_mgr, "seductive_gambit_applies", None)):
                if bool(cd_mgr.seductive_gambit_applies(moving_root)):
                    # Seductive Gambit applies only to LEGIONES DAEMONICA SLAANESH units.
                    player = moving_root.get_parent_army().player
                    if player is None:
                        raise RuntimeError("Seductive Gambit requires a player.")
                    unit_id = maybe_entity_id(moving_root)
                    ctx = {
                        "unit": getattr(moving_root, "name", "") or "",
                        "ability_name": "Seductive Gambit",
                        "phase": "Charge phase",
                        "unit_id": unit_id,
                    }
                    message = f"Use Seductive Gambit for {getattr(moving_root, 'name', 'Unit')}?"
                    self._queue_optional_ability_confirmation(
                        player=player,
                        ability_key="seductive_gambit",
                        ability_name="Seductive Gambit",
                        message=message,
                        context=ctx,
                        payload={"unit_id": unit_id},
                        instance_key=str(unit_id or ""),
                    )

        game_map = getattr(self, "map", None)
        from ..utility.event_bus import append_action, append_dice
        from ..utility.aura_utils import unit_within_range_of_unit

        moving_is_aircraft = False
        has_any_keyword = getattr(moving_root, "has_any_keyword", None)
        if callable(has_any_keyword):
            moving_is_aircraft = bool(has_any_keyword("AIRCRAFT"))

        for reacting_player in list(getattr(self, "players", []) or []):
            if reacting_player is None:
                continue
            reacting_army = self._get_player_army(reacting_player)
            if reacting_army is None or reacting_army is army:
                continue

            if action_key in ("move", "advance") and not moving_is_aircraft:
                cd_mgr = getattr(reacting_army, "chaos_daemons_detachments", None)
                if cd_mgr is not None and callable(getattr(cd_mgr, "is_blood_legion_detachment", None)):
                    if bool(cd_mgr.is_blood_legion_detachment()):
                        mover_id = str(get_entity_id(moving_root) or "")
                        turn = int(getattr(self, "turn", 0) or 0)
                        turn_owner = self.get_current_player()
                        turn_owner_id = str(getattr(turn_owner, "id", "") or "")
                        should_queue = True
                        queue = getattr(self, "decision_queue", None)
                        if queue is not None and hasattr(queue, "list"):
                            for req in list(queue.list() or []):
                                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                                    continue
                                ctx = dict(getattr(req, "context", {}) or {})
                                if str(ctx.get("ability", "") or "") != "murdercall":
                                    continue
                                if str(ctx.get("moving_unit_id", "") or "") != mover_id:
                                    continue
                                if int(ctx.get("turn", 0) or 0) != int(turn):
                                    continue
                                if str(ctx.get("turn_owner_id", "") or "") != turn_owner_id:
                                    continue
                                if str(getattr(req, "player_id", "") or "") != str(getattr(reacting_player, "id", "") or ""):
                                    continue
                                should_queue = False
                                break
                        if should_queue:
                            candidates = []
                            seen: set[str] = set()
                            for unit_candidate in list(getattr(reacting_army, "units", []) or []):
                                if unit_candidate is None:
                                    continue
                                try:
                                    root = unit_candidate.get_attached_unit_root()
                                except Exception:
                                    root = unit_candidate
                                if root is None:
                                    continue
                                rid = str(get_entity_id(root) or "")
                                if not rid or rid in seen:
                                    continue
                                seen.add(rid)
                                try:
                                    if not root.is_alive():
                                        continue
                                except Exception:
                                    continue
                                if not bool(getattr(root, "deployed", True)):
                                    continue
                                try:
                                    if root.is_in_reserves() or root.is_embarked:
                                        continue
                                except Exception:
                                    pass
                                applies_fn = getattr(cd_mgr, "murdercall_applies", None)
                                if not callable(applies_fn) or not bool(applies_fn(root)):
                                    continue
                                if bool(self._unit_is_engaged_with_enemy(root)):
                                    continue
                                if not bool(
                                    unit_within_range_of_unit(
                                        root,
                                        moving_root,
                                        6.0,
                                        use_attached_aggregate=True,
                                    )
                                ):
                                    continue
                                candidates.append(root)
                            if candidates:
                                candidates = sorted(candidates, key=lambda u: str(get_entity_id(u) or ""))
                                options = [DecisionOption.create("None", payload={"action": "skip"})]
                                for candidate in candidates:
                                    options.append(
                                        DecisionOption.create(
                                            str(getattr(candidate, "name", "Unit") or "Unit"),
                                            payload={"target_unit_id": get_entity_id(candidate)},
                                        )
                                    )
                                request = DecisionRequest.create(
                                    DECISION_CHOOSE_QUARRY,
                                    f"Murdercall: select a unit to Surge toward {getattr(moving_root, 'name', 'Unit')}.",
                                    player_id=getattr(reacting_player, "id", None),
                                    options=options,
                                    context={
                                        "ability": "murdercall",
                                        "ability_name": "Murdercall",
                                        "phase": "Movement phase",
                                        "moving_unit_id": mover_id,
                                        "moving_unit_name": str(getattr(moving_root, "name", "Unit") or "Unit"),
                                        "trigger_action": str(action_key),
                                        "range": 6,
                                        "turn": int(turn),
                                        "turn_owner_id": turn_owner_id,
                                        "candidate_unit_ids": [str(get_entity_id(c) or "") for c in candidates],
                                    },
                                )
                                self.request_decision(request)

            tyr_mgr = getattr(reacting_army, "tyranids_detachments", None)
            if tyr_mgr is not None:
                on_enemy_move_fn = getattr(tyr_mgr, "on_enemy_unit_move_ended", None)
                if callable(on_enemy_move_fn):
                    on_enemy_move_fn(moving_root, game=self)

            sm_mgr = getattr(reacting_army, "space_marines_detachments", None)
            if sm_mgr is not None:
                rule_fn = getattr(sm_mgr, "librarius_prescience_reactive_rule", None)
                can_trigger_fn = getattr(sm_mgr, "librarius_prescience_can_trigger", None)
                queue_confirmation = getattr(self, "_queue_reactive_move_confirmation", None)
                if callable(rule_fn) and callable(can_trigger_fn) and callable(queue_confirmation):
                    seen_reactors: set[str] = set()
                    for candidate in list(getattr(reacting_army, "units", []) or []):
                        if candidate is None:
                            continue
                        try:
                            reacting_root = candidate.get_attached_unit_root()
                        except Exception:
                            reacting_root = candidate
                        if reacting_root is None:
                            continue
                        reacting_id = str(get_entity_id(reacting_root) or "")
                        if not reacting_id or reacting_id in seen_reactors:
                            continue
                        seen_reactors.add(reacting_id)
                        rule = rule_fn(reacting_root, game=self)
                        if not isinstance(rule, dict):
                            continue
                        try:
                            trigger_range = int(rule.get("range", 9) or 9)
                        except Exception:
                            trigger_range = 9
                        if not can_trigger_fn(
                            reacting_root,
                            game=self,
                            game_map=game_map,
                            moving_unit=moving_root,
                            range_override=trigger_range,
                        ):
                            continue
                        source = str(rule.get("source", "") or "Prescience").strip() or "Prescience"
                        move_label = "D6"
                        try:
                            fixed_distance = int(rule.get("max_distance", 0) or 0)
                        except Exception:
                            fixed_distance = 0
                        if fixed_distance > 0:
                            move_label = str(int(fixed_distance))
                        else:
                            roll_spec = str(rule.get("distance_roll", "") or "").strip().upper()
                            if roll_spec:
                                move_label = roll_spec
                        message = (
                            f"{getattr(moving_root, 'name', 'Enemy unit')} ended a move within {int(trigger_range)}\" of "
                            f"{getattr(reacting_root, 'name', 'unit')}.\n\n"
                            f"{source}: Make a Normal move of up to {move_label}\"?"
                        )
                        queue_confirmation(
                            player=reacting_player,
                            unit=reacting_root,
                            kind="librarius_prescience",
                            movement_type="librarius_prescience",
                            source=source,
                            message=message,
                            moving_unit=moving_root,
                            range_value=int(trigger_range),
                        )
                rule_fn = getattr(sm_mgr, "the_angelic_host_gleaming_pinions_reactive_rule", None)
                can_trigger_fn = getattr(sm_mgr, "the_angelic_host_gleaming_pinions_can_trigger", None)
                if callable(rule_fn) and callable(can_trigger_fn) and callable(queue_confirmation):
                    seen_reactors: set[str] = set()
                    for candidate in list(getattr(reacting_army, "units", []) or []):
                        if candidate is None:
                            continue
                        try:
                            reacting_root = candidate.get_attached_unit_root()
                        except Exception:
                            reacting_root = candidate
                        if reacting_root is None:
                            continue
                        reacting_id = str(get_entity_id(reacting_root) or "")
                        if not reacting_id or reacting_id in seen_reactors:
                            continue
                        seen_reactors.add(reacting_id)
                        rule = rule_fn(reacting_root, game=self)
                        if not isinstance(rule, dict):
                            continue
                        try:
                            trigger_range = int(rule.get("range", 9) or 9)
                        except Exception:
                            trigger_range = 9
                        if not can_trigger_fn(
                            reacting_root,
                            game=self,
                            game_map=game_map,
                            moving_unit=moving_root,
                            action=action_key,
                        ):
                            continue
                        source = str(rule.get("source", "") or "Gleaming Pinions").strip() or "Gleaming Pinions"
                        try:
                            max_distance = int(rule.get("max_distance", 6) or 6)
                        except Exception:
                            max_distance = 6
                        message = (
                            f"{getattr(moving_root, 'name', 'Enemy unit')} ended a {action_key.replace('_', ' ')} move within "
                            f"{int(trigger_range)}\" of {getattr(reacting_root, 'name', 'unit')}.\n\n"
                            f"{source}: Make a Normal move of up to {int(max(1, max_distance))}\"?"
                        )
                        queue_confirmation(
                            player=reacting_player,
                            unit=reacting_root,
                            kind="gleaming_pinions",
                            movement_type="gleaming_pinions",
                            source=source,
                            message=message,
                            moving_unit=moving_root,
                            range_value=int(trigger_range),
                        )

            ac_mgr = getattr(reacting_army, "adeptus_custodes_detachments", None)
            if ac_mgr is not None and action_key in ("move", "advance", "fall_back"):
                rule_fn = getattr(ac_mgr, "martial_philosopher_reactive_rule", None)
                can_trigger_fn = getattr(ac_mgr, "martial_philosopher_can_trigger", None)
                queue_confirmation = getattr(self, "_queue_reactive_move_confirmation", None)
                if callable(rule_fn) and callable(can_trigger_fn) and callable(queue_confirmation):
                    seen_reactors: set[str] = set()
                    for candidate in list(getattr(reacting_army, "units", []) or []):
                        if candidate is None:
                            continue
                        try:
                            reacting_root = candidate.get_attached_unit_root()
                        except Exception:
                            reacting_root = candidate
                        if reacting_root is None:
                            continue
                        reacting_id = str(get_entity_id(reacting_root) or "")
                        if not reacting_id or reacting_id in seen_reactors:
                            continue
                        seen_reactors.add(reacting_id)
                        rule = rule_fn(reacting_root, game=self)
                        if not isinstance(rule, dict):
                            continue
                        trigger_actions = {
                            str(v or "").strip().lower()
                            for v in list(rule.get("trigger_actions", ()) or ())
                            if str(v or "").strip()
                        }
                        if trigger_actions and action_key not in trigger_actions:
                            continue
                        try:
                            trigger_range = int(rule.get("range", 9) or 9)
                        except Exception:
                            trigger_range = 9
                        if not can_trigger_fn(
                            reacting_root,
                            game=self,
                            game_map=game_map,
                            moving_unit=moving_root,
                            action=action_key,
                            range_override=trigger_range,
                        ):
                            continue
                        source = str(rule.get("source", "") or "Martial Philosopher").strip() or "Martial Philosopher"
                        try:
                            max_distance = int(rule.get("max_distance", 6) or 6)
                        except Exception:
                            max_distance = 6
                        message = (
                            f"{getattr(moving_root, 'name', 'Enemy unit')} ended a {action_key.replace('_', ' ')} move within "
                            f"{int(trigger_range)}\" of {getattr(reacting_root, 'name', 'unit')}.\n\n"
                            f"{source}: Make a Normal move of up to {int(max(1, max_distance))}\"?"
                        )
                        queue_confirmation(
                            player=reacting_player,
                            unit=reacting_root,
                            kind="martial_philosopher",
                            movement_type="martial_philosopher",
                            source=source,
                            message=message,
                            moving_unit=moving_root,
                            range_value=int(trigger_range),
                        )

            am_mgr = getattr(reacting_army, "astra_militarum_detachments", None)
            if am_mgr is not None:
                tripwires_fn = getattr(am_mgr, "recon_element_tripwires_on_enemy_move_ended", None)
                if callable(tripwires_fn):
                    outcomes = list(
                        tripwires_fn(
                            moving_root,
                            action=action_key,
                            game=self,
                            player=reacting_player,
                        )
                        or []
                    )
                    if outcomes:
                        mover_name = str(getattr(moving_root, "name", "Unit") or "Unit")
                        for outcome in outcomes:
                            source_name = str(outcome.get("source_name", "") or "Tripwires").strip() or "Tripwires"
                            roll = int(outcome.get("roll", 0) or 0)
                            success_on = int(outcome.get("success_on", 4) or 4)
                            append_dice(
                                reacting_player,
                                f"{source_name}: {mover_name} triggered Tripwires, rolled {roll} (need {success_on}+).",
                            )
                            if bool(outcome.get("applied", False)):
                                append_action(
                                    reacting_player,
                                    f"{source_name}: {mover_name} is stunned and suffers -1 to hit until your next Command phase.",
                                )
                            else:
                                append_action(
                                    reacting_player,
                                    f"{source_name}: no effect on {mover_name}.",
                                )

            ae_mgr = getattr(reacting_army, "aeldari_detachments", None)
            if ae_mgr is None:
                continue
            resolve_fn = getattr(ae_mgr, "resolve_relentless_raiders_enemy_move", None)
            if not callable(resolve_fn):
                continue
            outcomes = list(
                resolve_fn(
                    moving_root,
                    action=action_key,
                    game=self,
                    game_map=game_map,
                )
                or []
            )
            if not outcomes:
                continue
            mover_name = str(getattr(moving_root, "name", "Unit") or "Unit")
            for outcome in outcomes:
                objective_id = str(outcome.get("objective_id", "") or "")
                roll = int(outcome.get("roll", 0) or 0)
                mortal_wounds = int(outcome.get("mortal_wounds", 0) or 0)
                objective_label = f"objective {objective_id}" if objective_id else "an objective marker"
                append_dice(
                    reacting_player,
                    f"Relentless Raiders: {mover_name} near {objective_label}, rolled {roll} (2+).",
                )
                if mortal_wounds > 0:
                    append_action(
                        reacting_player,
                        f"Relentless Raiders: {mover_name} suffers {mortal_wounds} mortal wound(s).",
                    )
                else:
                    append_action(
                        reacting_player,
                        f"Relentless Raiders: no mortal wounds dealt to {mover_name}.",
                    )

    def _unit_started_move_within_friendly_keyword_unit(
        self,
        unit,
        *,
        range_value: float,
        required_keyword: str = "BATTLELINE",
        required_faction_keyword: str = "",
    ) -> bool:
        if unit is None or float(range_value or 0.0) <= 0.0:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False

        try:
            from ..utility.aura_utils import distance_between_bases_3d
        except Exception:
            return False

        start_bases = []
        create_base_fn = getattr(root, "_create_potential_base", None)
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in models:
            if model is None:
                continue
            try:
                alive_attr = getattr(model, "is_alive", True)
                alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                alive = False
            if not alive:
                continue
            start_base = None
            path = getattr(model, "last_move_path", None)
            if isinstance(path, list) and path:
                node = path[0]
                if isinstance(node, (list, tuple)) and len(node) >= 2:
                    try:
                        x = float(node[0])
                        y = float(node[1])
                        z = float(node[2]) if len(node) > 2 else float(getattr(model.model_base, "z", 0.0))
                        facing = float(node[3]) if len(node) > 3 else float(getattr(model.model_base, "facing", 0.0))
                    except Exception:
                        x = y = z = facing = None
                    if x is not None and callable(create_base_fn):
                        try:
                            start_base = create_base_fn(x, y, z, facing, model=model)
                        except Exception:
                            start_base = None
            if start_base is None:
                start_base = getattr(model, "model_base", None)
            if start_base is None:
                continue
            start_bases.append(start_base)
        if not start_bases:
            return False

        keyword = str(required_keyword or "").strip()
        faction_keyword = str(required_faction_keyword or "").strip()
        seen: set[str] = set()
        for candidate in list(getattr(army, "units", []) or []):
            if candidate is None:
                continue
            try:
                cand_root = candidate.get_attached_unit_root()
            except Exception:
                cand_root = candidate
            if cand_root is None or cand_root is root:
                continue
            cid = str(get_entity_id(cand_root) or "")
            if cid and cid in seen:
                continue
            if cid:
                seen.add(cid)
            try:
                if not cand_root.is_alive() or not bool(getattr(cand_root, "deployed", False)):
                    continue
            except Exception:
                continue
            try:
                if cand_root.is_in_reserves():
                    continue
            except Exception:
                pass
            try:
                if bool(getattr(cand_root, "is_embarked", False)) or bool(getattr(cand_root, "embarked_in", None)):
                    continue
            except Exception:
                pass
            try:
                if keyword and not bool(cand_root.has_any_keyword(keyword)):
                    continue
            except Exception:
                continue
            if faction_keyword:
                try:
                    if not bool(cand_root.has_any_keyword(faction_keyword)):
                        continue
                except Exception:
                    continue
            try:
                candidate_models = list(cand_root.get_attached_unit_models() or [])
            except Exception:
                candidate_models = list(getattr(cand_root, "models", []) or [])
            for cand_model in candidate_models:
                if cand_model is None:
                    continue
                try:
                    alive_attr = getattr(cand_model, "is_alive", True)
                    alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                except Exception:
                    alive = False
                if not alive:
                    continue
                cand_base = getattr(cand_model, "model_base", None)
                if cand_base is None:
                    continue
                for start_base in start_bases:
                    try:
                        if float(distance_between_bases_3d(start_base, cand_base)) <= float(range_value) + 1e-6:
                            return True
                    except Exception:
                        continue
        return False

    def resolve_charge_end_mortal_wounds(self, unit, target_unit, spec) -> None:
        if unit is None or target_unit is None or not isinstance(spec, dict):
            return
        kind = str(spec.get("kind", "") or "").strip().lower()
        if not kind:
            return
        game_map = getattr(self, "map", None)
        ability_name = str(spec.get("name", "") or "Charge Mortals").strip() or "Charge Mortals"

        from ..utility.dice import get_roll

        try:
            start_charge_bonus = int(spec.get("start_charge_bonus", 0) or 0)
        except Exception:
            start_charge_bonus = 0
        try:
            start_charge_range = int(spec.get("start_charge_range", 0) or 0)
        except Exception:
            start_charge_range = 0
        started_within_required = False
        if start_charge_bonus > 0 and start_charge_range > 0:
            started_within_required = bool(
                self._unit_started_move_within_friendly_keyword_unit(
                    unit,
                    range_value=float(start_charge_range),
                    required_keyword=str(spec.get("start_charge_required_keyword", "") or "BATTLELINE"),
                    required_faction_keyword=str(spec.get("start_charge_required_faction_keyword", "") or ""),
                )
            )

        engagement_only = bool(spec.get("engagement_only", False))
        model_within_engagement_range_of_unit = None
        if engagement_only:
            try:
                from ..utility.aura_utils import model_within_engagement_range_of_unit as _model_within_engagement_range_of_unit

                model_within_engagement_range_of_unit = _model_within_engagement_range_of_unit
            except Exception:
                model_within_engagement_range_of_unit = None

        total_mw = 0
        roll_summary = ""
        if kind == "per_model_4plus_d3":
            models = list(unit.get_attached_unit_models() or [])
            rolls = []
            modified_rolls = []
            d3_rolls = []
            for m in models:
                if not getattr(m, "is_alive", False):
                    continue
                if engagement_only and callable(model_within_engagement_range_of_unit):
                    try:
                        if not bool(model_within_engagement_range_of_unit(m, target_unit)):
                            continue
                    except Exception:
                        continue
                r = int(get_roll("D6") or 0)
                r_mod = int(r)
                if started_within_required and start_charge_bonus:
                    r_mod = int(r_mod + int(start_charge_bonus))
                rolls.append(r)
                modified_rolls.append(r_mod)
                if r_mod >= 4:
                    d3 = int(get_roll("D3") or 0)
                    d3_rolls.append(d3)
                    total_mw += d3
            if rolls:
                if started_within_required and start_charge_bonus:
                    roll_summary = f"rolls={rolls} (+{int(start_charge_bonus)} -> {modified_rolls})"
                else:
                    roll_summary = f"rolls={rolls}"
                if d3_rolls:
                    roll_summary += f", d3={d3_rolls}"
        elif kind == "per_model_4plus_1":
            models = list(unit.get_attached_unit_models() or [])
            rolls = []
            modified_rolls = []
            for m in models:
                if not getattr(m, "is_alive", False):
                    continue
                if engagement_only and callable(model_within_engagement_range_of_unit):
                    try:
                        if not bool(model_within_engagement_range_of_unit(m, target_unit)):
                            continue
                    except Exception:
                        continue
                r = int(get_roll("D6") or 0)
                r_mod = int(r)
                if started_within_required and start_charge_bonus:
                    r_mod = int(r_mod + int(start_charge_bonus))
                rolls.append(r)
                modified_rolls.append(r_mod)
                if r_mod >= 4:
                    total_mw += 1
            if rolls:
                if started_within_required and start_charge_bonus:
                    roll_summary = f"rolls={rolls} (+{int(start_charge_bonus)} -> {modified_rolls})"
                else:
                    roll_summary = f"rolls={rolls}"
        elif kind == "per_model_engagement_flat_cap":
            from ..utility.aura_utils import model_within_engagement_range_of_unit

            models = list(unit.get_attached_unit_models() or [])
            threshold = int(spec.get("threshold", 4) or 4)
            mortal_per_success = int(spec.get("mortal_per_success", 1) or 1)
            max_mortal_wounds = int(spec.get("max_mortal_wounds", 6) or 6)
            threshold = max(2, min(6, threshold))
            mortal_per_success = max(1, mortal_per_success)
            max_mortal_wounds = max(1, max_mortal_wounds)

            rolls = []
            engaged_models = 0
            for model in models:
                if model is None:
                    continue
                try:
                    alive_attr = getattr(model, "is_alive", True)
                    alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                except Exception:
                    alive = False
                if not alive:
                    continue
                if not bool(model_within_engagement_range_of_unit(model, target_unit)):
                    continue
                engaged_models += 1
                roll = int(get_roll("D6") or 0)
                rolls.append(roll)
                if roll >= threshold:
                    total_mw += mortal_per_success
            if total_mw > max_mortal_wounds:
                total_mw = max_mortal_wounds
            if rolls:
                roll_summary = f"rolls={rolls}, engaged_models={engaged_models}"
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
        elif kind == "table_d6_2_5_6_flat3":
            roll = int(get_roll("D6") or 0)
            if 2 <= roll <= 5:
                total_mw = int(get_roll("D3") or 0)
            elif roll >= 6:
                total_mw = 3
            roll_summary = f"roll={roll}"
        elif kind == "single_4plus_die":
            try:
                threshold = int(spec.get("threshold", 4) or 4)
            except Exception:
                threshold = 4
            threshold = max(2, min(6, threshold))
            success_die = str(spec.get("success_die", "") or "D3").strip().upper() or "D3"
            roll = int(get_roll("D6") or 0)
            modified_roll = int(roll)
            if started_within_required and start_charge_bonus:
                modified_roll = int(modified_roll + int(start_charge_bonus))
            if modified_roll >= threshold:
                total_mw = int(get_roll(success_die) or 0)
            if started_within_required and start_charge_bonus:
                roll_summary = f"roll={roll} (+{int(start_charge_bonus)} -> {int(modified_roll)})"
            else:
                roll_summary = f"roll={roll}"
        else:
            return

        logger.info(f"{ability_name}: {getattr(unit, 'name', 'Unit')} -> "
            f"{getattr(target_unit, 'name', 'Target')} ({roll_summary}) => {total_mw} mortal wounds")

        models_destroyed = 0
        if total_mw > 0:
            models_destroyed = int(
                unit._apply_mortal_wounds_to_unit(target_unit, int(total_mw), game_map=game_map)
                or 0
            )
        from ..utility.event_bus import append_action
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_action(
                player,
                f"{ability_name}: {getattr(unit, 'name', 'Unit')} dealt {int(total_mw)} mortal wounds to {getattr(target_unit, 'name', 'Target')}.",
            )
            if bool(spec.get("battle_shock_on_models_destroyed", False)) and models_destroyed > 0:
                append_action(
                    player,
                    f"{ability_name}: {getattr(target_unit, 'name', 'Target')} takes a Battle-shock test (models destroyed by mortal wounds).",
                )
        if bool(spec.get("battle_shock_on_models_destroyed", False)) and models_destroyed > 0 and target_unit.is_alive():
            target_unit.take_battle_shock_test(int(getattr(self, "turn", 0) or 1))

    def resolve_floating_death_mortal_wounds(self, unit, model, target_unit, spec) -> None:
        if unit is None or model is None or target_unit is None or not isinstance(spec, dict):
            return
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return
        model_is_alive = getattr(model, "is_alive", False)
        model_alive = bool(model_is_alive()) if callable(model_is_alive) else bool(model_is_alive)
        if not model_alive:
            return
        if getattr(model, "parent_unit", None) is not root:
            return

        ability_name = str(spec.get("source", "") or "Floating Death").strip() or "Floating Death"
        source_name = str(getattr(model, "name", "") or "Model")

        model.die(game_map=getattr(self, "map", None))

        from ..utility.dice import get_roll
        roll = int(get_roll("D6") or 0)
        mortal_wounds = 0
        if 2 <= roll <= 5:
            mid_die = str(spec.get("on_mid_die", "") or "").strip().upper()
            if mid_die:
                mortal_wounds = int(get_roll(mid_die) or 0)
            else:
                try:
                    mortal_wounds = int(spec.get("on_mid_flat", 0) or 0)
                except (TypeError, ValueError):
                    mortal_wounds = 0
        elif roll >= 6:
            high_die = str(spec.get("on_high_die", "") or "").strip().upper()
            if high_die:
                mortal_wounds = int(get_roll(high_die) or 0)

        target_is_alive = getattr(target_unit, "is_alive", False)
        target_alive = bool(target_is_alive()) if callable(target_is_alive) else bool(target_is_alive)
        if mortal_wounds > 0 and target_alive:
            root._apply_mortal_wounds_to_unit(target_unit, int(mortal_wounds), game_map=getattr(self, "map", None))

        from ..utility.event_bus import append_action, append_dice
        parent_army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        player = getattr(parent_army, "player", None)
        if player is not None:
            append_dice(
                player,
                f"{ability_name}: {source_name} roll={int(roll)} -> {int(mortal_wounds)} mortal wounds to {getattr(target_unit, 'name', 'Target')}.",
            )
            append_action(
                player,
                f"{ability_name}: {source_name} was destroyed and dealt {int(mortal_wounds)} mortal wounds to {getattr(target_unit, 'name', 'Target')}.",
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
        if not unique_engaged:
            return

        player = root.get_parent_army().player
        if player is None:
            return
        for spec in specs:
            candidates = list(unique_engaged)
            if bool(spec.get("target_must_be_engaged_with_bearer", False)):
                from ..utility.aura_utils import model_within_engagement_range_of_unit

                bearer_id = str(spec.get("bearer_model_id", "") or "").strip()
                try:
                    models = list(root.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(root, "models", []) or [])
                bearer_model = None
                if bearer_id:
                    for model in models:
                        if str(get_entity_id(model) or "") != bearer_id:
                            continue
                        alive_attr = getattr(model, "is_alive", True)
                        if bool(alive_attr() if callable(alive_attr) else alive_attr):
                            bearer_model = model
                            break
                if bearer_model is None:
                    get_bearer = getattr(root, "_get_enhancement_bearer_model", None)
                    candidate = get_bearer() if callable(get_bearer) else None
                    if candidate is not None:
                        alive_attr = getattr(candidate, "is_alive", True)
                        if bool(alive_attr() if callable(alive_attr) else alive_attr):
                            bearer_model = candidate
                if bearer_model is None:
                    continue
                filtered = []
                for enemy in list(candidates):
                    if enemy is None:
                        continue
                    try:
                        in_engagement = bool(model_within_engagement_range_of_unit(bearer_model, enemy))
                    except Exception:
                        in_engagement = False
                    if in_engagement:
                        filtered.append(enemy)
                candidates = filtered
            if not candidates:
                continue
            if len(candidates) == 1:
                self.resolve_charge_end_mortal_wounds(root, candidates[0], spec)
                continue
            self._queue_mortal_wounds_target_decision(
                player=player,
                unit=root,
                candidates=list(candidates),
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

        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("enhancement_blade_imperator")):
            once_key = str(sr.get("enhancement_blade_imperator_battleshock_once_key", "blade_imperator_battleshock") or "blade_imperator_battleshock").strip().lower()
            if not once_key:
                once_key = "blade_imperator_battleshock"
            has_used = getattr(root, "has_used_unit_once_per_battle", None)
            if not callable(has_used) or not bool(has_used(once_key)):
                try:
                    aura_range = int(sr.get("enhancement_blade_imperator_battleshock_range", 6) or 6)
                except Exception:
                    aura_range = 6
                aura_range = max(1, int(aura_range))
                bearer_id = str(
                    sr.get("enhancement_blade_imperator_bearer_model_id", "")
                    or sr.get("enhancement_bearer_model_id", "")
                    or ""
                ).strip()
                try:
                    models = list(root.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(root, "models", []) or [])
                bearer_model = None
                if bearer_id:
                    for model in models:
                        if str(get_entity_id(model) or "") != bearer_id:
                            continue
                        alive_attr = getattr(model, "is_alive", True)
                        if bool(alive_attr() if callable(alive_attr) else alive_attr):
                            bearer_model = model
                            break
                if bearer_model is None:
                    get_bearer = getattr(root, "_get_enhancement_bearer_model", None)
                    candidate = get_bearer() if callable(get_bearer) else None
                    if candidate is not None:
                        alive_attr = getattr(candidate, "is_alive", True)
                        if bool(alive_attr() if callable(alive_attr) else alive_attr):
                            bearer_model = candidate
                if bearer_model is not None:
                    from ..utility.aura_utils import model_within_range_of_unit

                    enemies = list(game_map.get_enemy_units(root) or [])
                    aura_targets = []
                    seen: set[str] = set()
                    for enemy in enemies:
                        if enemy is None:
                            continue
                        try:
                            enemy_root = enemy.get_attached_unit_root()
                        except Exception:
                            enemy_root = enemy
                        if enemy_root is None:
                            continue
                        enemy_id = str(get_entity_id(enemy_root) or "")
                        if not enemy_id or enemy_id in seen:
                            continue
                        seen.add(enemy_id)
                        if not enemy_root.is_alive():
                            continue
                        if not bool(getattr(enemy_root, "deployed", True)):
                            continue
                        if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                            continue
                        if not bool(
                            model_within_range_of_unit(
                                bearer_model,
                                enemy_root,
                                float(aura_range),
                                use_attached_aggregate=True,
                            )
                        ):
                            continue
                        aura_targets.append(enemy_root)
                    if aura_targets:
                        try:
                            turn = int(getattr(self, "turn", 0) or 1)
                        except Exception:
                            turn = 1
                        for enemy_root in aura_targets:
                            take_test = getattr(enemy_root, "take_battle_shock_test", None)
                            if callable(take_test):
                                take_test(turn)
                        mark_used = getattr(root, "mark_unit_once_per_battle_used", None)
                        if callable(mark_used):
                            ability_name = str(sr.get("enhancement_blade_imperator_source", "") or "Blade Imperator").strip() or "Blade Imperator"
                            mark_used(once_key, ability_name=ability_name)

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

    def _stasis_bomb_model_used_once_per_battle(self, model, *, ability_key: str) -> bool:
        if model is None:
            return True
        key = str(ability_key or "stasis_bomb").strip().lower() or "stasis_bomb"
        has_used = getattr(model, "has_used_once_per_battle", None)
        if callable(has_used):
            return bool(has_used(key))
        sr = getattr(model, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        return bool(sr.get(f"{key}_used_once_per_battle", False))

    def _mark_stasis_bomb_model_used_once_per_battle(self, model, *, ability_key: str, ability_name: str) -> None:
        if model is None:
            return
        key = str(ability_key or "stasis_bomb").strip().lower() or "stasis_bomb"
        mark_used = getattr(model, "mark_used_once_per_battle", None)
        if callable(mark_used):
            mark_used(key, ability_name=ability_name, source="datasheet")
            return
        sr = getattr(model, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{key}_used_once_per_battle"] = True
        model.special_rules = sr

    def _stasis_bomb_army_used_this_turn(self, player) -> bool:
        if player is None:
            return False
        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        army = player.get_army() if callable(getattr(player, "get_army", None)) else getattr(player, "army", None)
        if army is None:
            return False
        for unit in list(getattr(army, "units", []) or []):
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("stasis_bomb_army_used_this_turn", False)):
                continue
            sr_owner = str(sr.get("stasis_bomb_army_used_turn_owner", "") or "")
            if owner_id and sr_owner and owner_id != sr_owner:
                continue
            try:
                sr_turn = int(sr.get("stasis_bomb_army_used_turn", 0) or 0)
            except Exception:
                sr_turn = 0
            if turn and sr_turn and turn != sr_turn:
                continue
            return True
        return False

    def _mark_stasis_bomb_army_used_this_turn(self, player, *, source_unit=None, source: str = "Stasis Bomb") -> None:
        if player is None:
            return
        root = None
        if source_unit is not None:
            try:
                root = source_unit.get_attached_unit_root()
            except Exception:
                root = source_unit
        if root is None:
            army = player.get_army() if callable(getattr(player, "get_army", None)) else getattr(player, "army", None)
            if army is not None:
                units = list(getattr(army, "units", []) or [])
                if units:
                    try:
                        root = units[0].get_attached_unit_root()
                    except Exception:
                        root = units[0]
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["stasis_bomb_army_used_this_turn"] = True
        sr["stasis_bomb_army_used_source"] = str(source or "Stasis Bomb").strip() or "Stasis Bomb"
        owner_id = str(getattr(player, "id", "") or "")
        if owner_id:
            sr["stasis_bomb_army_used_turn_owner"] = owner_id
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        if turn:
            sr["stasis_bomb_army_used_turn"] = int(turn)
        root.special_rules = sr

    def resolve_stasis_bomb(self, unit, model, target_unit, spec) -> None:
        if unit is None or model is None or target_unit is None or not isinstance(spec, dict):
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        ability_name = str(spec.get("source", "") or "Stasis Bomb").strip() or "Stasis Bomb"
        ability_key = str(spec.get("ability_key", "") or "stasis_bomb").strip().lower() or "stasis_bomb"
        if bool(spec.get("once_per_battle_per_model", False)):
            if self._stasis_bomb_model_used_once_per_battle(model, ability_key=ability_key):
                return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return
        if bool(spec.get("once_per_turn_army", False)) and self._stasis_bomb_army_used_this_turn(player):
            return

        unit_id = str(get_entity_id(root) or "")
        model_id = str(get_entity_id(model) or "")
        target_id = str(get_entity_id(target_unit) or "")
        if not unit_id or not model_id or not target_id:
            return

        self._mark_stasis_bomb_army_used_this_turn(player, source_unit=root, source=ability_name)
        if bool(spec.get("once_per_battle_per_model", False)):
            self._mark_stasis_bomb_model_used_once_per_battle(model, ability_key=ability_key, ability_name=ability_name)

        mortal_die = str(spec.get("mortal_wounds_die", "") or "D3").strip().upper() or "D3"
        roll_spec = {
            "dice_count": 1,
            "faces": 3 if mortal_die == "D3" else 6,
            "reason": f"{ability_name}: {getattr(root, 'name', 'Unit')} -> {getattr(target_unit, 'name', 'Target')} mortal wounds",
            "roll_type": "stasis_bomb_mortal_wounds",
            "handler_key": "stasis_bomb_mortal_wounds",
            "ability_name": ability_name,
            "ability_key": ability_key,
            "unit_id": unit_id,
            "model_id": model_id,
            "target_unit_id": target_id,
            "restriction_roll_die": str(spec.get("restriction_roll_die", "") or "D6").strip().upper() or "D6",
            "restriction_low_max": int(spec.get("restriction_low_max", 3) or 3),
            "restriction_on_low": str(spec.get("restriction_on_low", "") or "no_advance_fall_back"),
            "restriction_on_high": str(spec.get("restriction_on_high", "") or "remain_stationary"),
        }
        if bool(getattr(self, "auto_resolve_dice_rolls", False)):
            try:
                from ..utility.dice import get_roll
                roll_spec["fixed_dice"] = [int(get_roll(mortal_die) or 0)]
            except Exception:
                pass
        try:
            self.request_dice_roll(player_id=getattr(player, "id", None), spec=roll_spec, prompt=roll_spec["reason"])
        except Exception:
            pass

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
        if bool(spec.get("dice_per_target_model", False)):
            try:
                target_models = list(target_unit.get_attached_unit_models() or [])
            except Exception:
                target_models = list(getattr(target_unit, "models", []) or [])
            dice_count = len([m for m in list(target_models or []) if getattr(m, "is_alive", True)])
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
        if not bool(spec.get("disable_move_over_rerolls", False)):
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

        roll_type = str(spec.get("roll_type", "") or "move_over_mortal_wounds").strip() or "move_over_mortal_wounds"
        handler_key = str(spec.get("handler_key", "") or "move_over_mortal_wounds").strip() or "move_over_mortal_wounds"
        reason = f"{ability_name}: {getattr(root, 'name', 'Unit')} -> {getattr(target_unit, 'name', 'Target')}"
        roll_spec = {
            "dice_count": int(dice_count),
            "faces": 6,
            "reason": reason,
            "roll_type": roll_type,
            "unit_id": unit_id,
            "model_id": model_id,
            "target_unit_id": target_id,
            "target_unit_ids": [target_id] if target_id else [],
            "handler_key": handler_key,
            "ability_name": ability_name,
            "threshold": int(threshold),
            "effective_threshold": int(effective_threshold),
            "mortal_per_success": int(mortal_per),
            "mortal_per_success_die": str(mortal_die or ""),
            "fly_bonus": int(fly_bonus or 0),
            "apply_fly_bonus": int(apply_fly_bonus),
            "target": int(effective_threshold),
            "target_base": int(threshold),
            "target_op": "gte",
        }
        if int(apply_fly_bonus or 0):
            roll_spec["target_modifier_reasons"] = [f"Target has FLY ({-int(apply_fly_bonus):+d} threshold)"]
            roll_spec["target_modifier_breakdown"] = [
                {
                    "source": "Target has FLY",
                    "value": -int(apply_fly_bonus),
                    "reason": f"Target has FLY ({-int(apply_fly_bonus):+d} threshold)",
                    "contributor_type": "core_rule",
                }
            ]
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
        if bool(spec.get("apply_no_cover_until_end_of_turn", False)):
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(self, "turn", 0) or 0)
            except Exception:
                turn = 0
            sr["move_over_no_cover_active"] = True
            sr["move_over_no_cover_owner"] = owner_id
            sr["move_over_no_cover_turn"] = int(turn or 0)
            sr["move_over_no_cover_source"] = ability_name
            target_root.special_rules = sr
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
        allow_existing_passengers = bool(spec.get("allow_existing_passengers", False))
        if not allow_existing_passengers and list(getattr(transport, "transport_passengers", []) or []):
            return False
        keyword = str(spec.get("keyword", "") or "").strip()
        if keyword and not passenger.has_any_keyword(keyword):
            return False
        exclude_keywords_any = [
            str(value or "").strip().upper()
            for value in list(spec.get("exclude_keywords_any", []) or [])
            if str(value or "").strip()
        ]
        if exclude_keywords_any and any(bool(passenger.has_any_keyword(keyword_value)) for keyword_value in exclude_keywords_any):
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

    def _on_unit_move_ended_plunder(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key != "move":
            return
        if not bool(getattr(self, "is_authoritative", True)):
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
            specs = list(root.unit_plunder_specs() or [])
        except Exception:
            specs = []
        if not specs:
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return

        unit_id = str(get_entity_id(root) or "")
        if unit_id:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if not bool(ctx.get("engine_flow", False)):
                        continue
                    if str(ctx.get("mortal_wounds_kind", "") or "").strip().lower() != "plunder":
                        continue
                    if str(ctx.get("unit_id", "") or "") == unit_id:
                        return

        sorted_specs = sorted(
            list(specs),
            key=lambda s: str(s.get("source", "") or "").strip().lower(),
        )
        for base_spec in sorted_specs:
            spec = dict(base_spec or {})
            move_types = set(spec.get("move_types") or ["move"])
            if action_key not in move_types:
                continue
            if spec.get("once_per_battle"):
                ability_key = str(spec.get("ability_key") or "").strip().lower()
                if ability_key and root.has_used_unit_once_per_battle(ability_key):
                    continue
            try:
                range_value = int(spec.get("range", 0) or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            candidates = self._collect_grenade_pack_flyover_candidates(root, {"range": int(range_value)}, game_map)
            if not candidates:
                continue
            self._queue_mortal_wounds_target_decision(
                player=player,
                unit=root,
                candidates=list(candidates),
                spec=spec,
                kind="plunder",
                allow_skip=True,
                phase="Movement phase",
            )
            return

    def _on_unit_move_ended_bomb_squigs(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if action_key != "move":
            return
        if not bool(getattr(self, "is_authoritative", True)):
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
            specs = list(root.unit_bomb_squigs_specs() or [])
        except Exception:
            specs = []
        if not specs:
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return

        unit_id = str(get_entity_id(root) or "")
        if unit_id:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if not bool(ctx.get("engine_flow", False)):
                        continue
                    if str(ctx.get("mortal_wounds_kind", "") or "").strip().lower() != "bomb_squigs":
                        continue
                    if str(ctx.get("unit_id", "") or "") == unit_id:
                        return

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        phase_key = ""
        phase_key_fn = getattr(self, "_current_turn_phase_key", None)
        if callable(phase_key_fn):
            phase_key = str(phase_key_fn() or "")
        if phase_key and str(sr.get("bomb_squig_last_use_phase_key", "") or "") == phase_key:
            return
        try:
            used = int(sr.get("bomb_squig_uses", 0) or 0)
        except Exception:
            used = 0
        has_explicit_total = "bomb_squig_token_total" in sr

        def _count_bomb_squigs(unit_obj) -> int:
            count = 0
            try:
                models = list(unit_obj._get_bodyguard_support_models() or [])
            except Exception:
                models = list(getattr(unit_obj, "models", []) or [])
            for model in models:
                if model is None or not getattr(model, "is_alive", False):
                    continue
                try:
                    for wg in list(getattr(model, "wargear", []) or []):
                        if wg is None:
                            continue
                        if Unit._norm_wargear_name(getattr(wg, "name", "")) == "bomb squig":
                            count += 1
                except Exception:
                    pass
                try:
                    for ow in list(getattr(model, "optional_wargear", []) or []):
                        if Unit._norm_wargear_name(str(ow or "")) == "bomb squig":
                            count += 1
                except Exception:
                    continue
            return max(0, int(count))

        sorted_specs = sorted(
            list(specs),
            key=lambda s: str(s.get("source", "") or "").strip().lower(),
        )
        for base_spec in sorted_specs:
            spec = dict(base_spec or {})
            token_mode = str(spec.get("token_mode", "") or "").strip().lower()
            if token_mode == "fixed":
                try:
                    max_uses = max(0, int(spec.get("fixed_uses", 0) or 0))
                except Exception:
                    max_uses = 0
            elif has_explicit_total:
                try:
                    max_uses = max(0, int(sr.get("bomb_squig_token_total", 0) or 0))
                except Exception:
                    max_uses = 0
            else:
                max_uses = _count_bomb_squigs(root)
                if max_uses <= 0:
                    # Fallback for roster contexts that omit explicit token equipment.
                    max_uses = 1
            if max_uses <= 0 or used >= max_uses:
                continue

            try:
                range_value = int(spec.get("range", 0) or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue

            candidates = self._collect_grenade_pack_flyover_candidates(root, {"range": int(range_value)}, game_map)
            if not candidates:
                continue

            spec["max_uses"] = int(max_uses)
            spec["remaining_uses"] = int(max(0, max_uses - used))
            if phase_key:
                spec["phase_key"] = phase_key
            self._queue_mortal_wounds_target_decision(
                player=player,
                unit=root,
                candidates=list(candidates),
                spec=spec,
                kind="bomb_squigs",
                allow_skip=True,
                phase="Movement phase",
            )
            return

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

        from ..utility.calcs import get_enemy_models_moved_over, get_enemy_units_moved_over

        # Void Mine (Voidraven Bomber): once per battle after a Normal move.
        if action_key == "move":
            has_void_mine = False
            void_mine_name = "Void Mine"
            try:
                for name, desc in root._iter_ability_entries_for_rules(model=None):
                    text = f"{name or ''} {desc or ''}".lower()
                    if "void mine" in text:
                        has_void_mine = True
                        void_mine_name = str(name or "Void Mine").strip() or "Void Mine"
                        break
            except Exception:
                has_void_mine = False

            if has_void_mine and not root.has_used_unit_once_per_battle("void_mine"):
                root_id = str(get_entity_id(root) or "")
                pending = False
                queue = getattr(self, "decision_queue", None)
                if queue is not None and hasattr(queue, "list"):
                    for req in list(queue.list() or []):
                        if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                            continue
                        ctx = dict(getattr(req, "context", {}) or {})
                        if str(ctx.get("ability", "") or "") != "void_mine":
                            continue
                        if str(ctx.get("source_unit_id", "") or "") == root_id:
                            pending = True
                            break
                if not pending:
                    moved_over_models = []
                    seen_models: set[str] = set()
                    for model in models:
                        if not bool(getattr(model, "is_alive", False)):
                            continue
                        path = getattr(model, "last_move_path", None)
                        for enemy_model in list(
                            get_enemy_models_moved_over(model, path, game_map, require_vertical_overlap=True) or []
                        ):
                            enemy_model_id = str(get_entity_id(enemy_model) or "")
                            if not enemy_model_id or enemy_model_id in seen_models:
                                continue
                            seen_models.add(enemy_model_id)
                            moved_over_models.append(enemy_model)
                    if moved_over_models:
                        try:
                            player = root.get_parent_army().player
                        except Exception:
                            player = None
                        if player is not None:
                            sorted_models = sorted(
                                list(moved_over_models),
                                key=lambda m: str(get_entity_id(m) or ""),
                            )
                            options = [DecisionOption.create("None", payload={"action": "skip", "skip": True})]
                            used_labels: set[str] = set()
                            candidate_ids: list[str] = []
                            for enemy_model in sorted_models:
                                enemy_model_id = str(get_entity_id(enemy_model) or "")
                                if not enemy_model_id:
                                    continue
                                candidate_ids.append(enemy_model_id)
                                model_label = str(getattr(enemy_model, "name", "") or "Enemy model")
                                enemy_unit = getattr(enemy_model, "parent_unit", None)
                                unit_label = str(getattr(enemy_unit, "name", "") or "")
                                label = f"{model_label} ({unit_label})" if unit_label else model_label
                                base_label = label
                                suffix = 2
                                while label in used_labels:
                                    label = f"{base_label} ({suffix})"
                                    suffix += 1
                                used_labels.add(label)
                                options.append(
                                    DecisionOption.create(
                                        label,
                                        payload={"target_model_id": enemy_model_id},
                                    )
                                )
                            if len(options) > 1:
                                request = DecisionRequest.create(
                                    DECISION_CHOOSE_QUARRY,
                                    f"{void_mine_name}: select one enemy model moved over (or None).",
                                    player_id=getattr(player, "id", None),
                                    options=options,
                                    context={
                                        "ability": "void_mine",
                                        "ability_name": void_mine_name,
                                        "phase": "Movement phase",
                                        "source_unit_id": root_id,
                                        "unit_id": root_id,
                                        "optional": True,
                                        "allow_skip": True,
                                        "candidate_model_ids": sorted(list(candidate_ids)),
                                        "ability_key": "void_mine",
                                    },
                                )
                                self.request_decision(request)

        # Stasis Bomb: after a Normal move, one model from your army can use this ability each turn;
        # each model can do so only once per battle.
        if action_key == "move":
            try:
                stasis_specs = list(root.unit_stasis_bomb_specs() or [])
            except Exception:
                stasis_specs = []
            if stasis_specs:
                try:
                    player = root.get_parent_army().player
                except Exception:
                    player = None
                if player is not None and not self._stasis_bomb_army_used_this_turn(player):
                    root_id = str(get_entity_id(root) or "")
                    pending = False
                    queue = getattr(self, "decision_queue", None)
                    if queue is not None and hasattr(queue, "list"):
                        for req in list(queue.list() or []):
                            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                                continue
                            ctx = dict(getattr(req, "context", {}) or {})
                            if str(ctx.get("mortal_wounds_kind", "") or "").strip().lower() != "stasis_bomb":
                                continue
                            if str(ctx.get("unit_id", "") or "") == root_id:
                                pending = True
                                break
                    if not pending:
                        for spec in list(stasis_specs or []):
                            if not bool(spec.get("once_per_turn_army", False)):
                                continue
                            target_to_model_ids: dict[str, list[str]] = {}
                            target_by_id: dict[str, Any] = {}
                            for model in list(models or []):
                                if not getattr(model, "is_alive", False):
                                    continue
                                ability_key = str(spec.get("ability_key", "") or "stasis_bomb").strip().lower()
                                if ability_key and self._stasis_bomb_model_used_once_per_battle(model, ability_key=ability_key):
                                    continue
                                path = getattr(model, "last_move_path", None)
                                moved_over = get_enemy_units_moved_over(model, path, game_map, require_vertical_overlap=True)
                                for cand in list(moved_over or []):
                                    if cand is None:
                                        continue
                                    if bool(spec.get("exclude_aircraft", False)):
                                        try:
                                            if bool(cand.has_keyword("AIRCRAFT") or cand.has_any_keyword("AIRCRAFT")):
                                                continue
                                        except Exception:
                                            continue
                                    cid = str(get_entity_id(cand) or "")
                                    mid = str(get_entity_id(model) or "")
                                    if not cid or not mid:
                                        continue
                                    target_by_id[cid] = cand
                                    target_to_model_ids.setdefault(cid, [])
                                    if mid not in target_to_model_ids[cid]:
                                        target_to_model_ids[cid].append(mid)
                            if not target_by_id:
                                continue
                            candidates = [target_by_id[k] for k in sorted(target_by_id.keys())]
                            queued_spec = dict(spec or {})
                            queued_spec["source_model_ids_by_target"] = {
                                str(k): sorted(list(v or [])) for k, v in dict(target_to_model_ids or {}).items()
                            }
                            self._queue_mortal_wounds_target_decision(
                                player=player,
                                unit=root,
                                candidates=list(candidates),
                                spec=queued_spec,
                                kind="stasis_bomb",
                                allow_skip=True,
                                phase="Movement phase",
                            )
                            break

        # Spore Mine Cysts (Harpy): after a Normal move, choose one moved-over enemy unit
        # for six D6 mortal-wound rolls, or spawn Spore Mines (once per turn shared option).
        if action_key == "move":
            try:
                spore_specs = list(root.unit_spore_mine_cysts_specs() or [])
            except Exception:
                spore_specs = []
            if spore_specs:
                try:
                    player = root.get_parent_army().player
                except Exception:
                    player = None
                if player is not None:
                    try:
                        owner_id = str(getattr(player, "id", "") or "")
                    except Exception:
                        owner_id = ""
                    try:
                        turn = int(getattr(self, "turn", 0) or 0)
                    except Exception:
                        turn = 0
                    root_id = str(get_entity_id(root) or "")
                    pending = False
                    queue = getattr(self, "decision_queue", None)
                    if queue is not None and hasattr(queue, "list"):
                        for req in list(queue.list() or []):
                            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                                continue
                            ctx = dict(getattr(req, "context", {}) or {})
                            if str(ctx.get("ability", "") or "").strip().lower() != "spore_mine_cysts":
                                continue
                            if str(ctx.get("unit_id", "") or "") != root_id:
                                continue
                            try:
                                req_turn = int(ctx.get("turn", 0) or 0)
                            except Exception:
                                req_turn = 0
                            if req_turn != int(turn or 0):
                                continue
                            pending = True
                            break
                    if not pending:
                        source_model = next((m for m in list(models or []) if bool(getattr(m, "is_alive", False))), None)
                        source_model_id = str(get_entity_id(source_model) or "") if source_model is not None else ""
                        target_by_id: dict[str, Any] = {}
                        from ..utility.calcs import get_enemy_units_moved_over

                        for model in list(models or []):
                            if not getattr(model, "is_alive", False):
                                continue
                            path = getattr(model, "last_move_path", None)
                            moved_over = get_enemy_units_moved_over(model, path, game_map, require_vertical_overlap=True)
                            for cand in list(moved_over or []):
                                if cand is None:
                                    continue
                                cid = str(get_entity_id(cand) or "")
                                if not cid:
                                    continue
                                target_by_id[cid] = cand

                        for spec in list(spore_specs or []):
                            move_types = set(spec.get("move_types") or [])
                            if action_key not in move_types:
                                continue

                            spawn_available = True
                            if bool(spec.get("spawn_once_per_turn_shared", False)):
                                spawn_available = False
                                army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                                if army is not None:
                                    iter_roots = getattr(self, "_iter_unique_army_roots", None)
                                    army_roots = list(iter_roots(army) or []) if callable(iter_roots) else list(getattr(army, "units", []) or [])
                                    already_used = False
                                    for army_root in list(army_roots or []):
                                        if army_root is None:
                                            continue
                                        sr_army_root = getattr(army_root, "special_rules", None)
                                        if not isinstance(sr_army_root, dict):
                                            continue
                                        if not bool(sr_army_root.get("spore_mine_cysts_spawn_used_this_turn", False)):
                                            continue
                                        if str(sr_army_root.get("spore_mine_cysts_spawn_turn_owner", "") or "") != str(owner_id or ""):
                                            continue
                                        try:
                                            used_turn = int(sr_army_root.get("spore_mine_cysts_spawn_turn", 0) or 0)
                                        except Exception:
                                            used_turn = 0
                                        if int(used_turn or 0) == int(turn or 0):
                                            already_used = True
                                            break
                                    spawn_available = not bool(already_used)

                            options = [DecisionOption.create("None", payload={"action": "skip"})]
                            for cid in sorted(target_by_id.keys()):
                                target_unit = target_by_id[cid]
                                label = str(getattr(target_unit, "name", "") or "Enemy unit")
                                options.append(
                                    DecisionOption.create(
                                        label,
                                        payload={"action": "mortal_target", "target_unit_id": str(cid)},
                                    )
                                )
                            if spawn_available and source_model_id:
                                options.append(DecisionOption.create("Spawn Spore Mines", payload={"action": "spawn_spore_mines"}))

                            if len(options) <= 1:
                                continue

                            ability_name = str(spec.get("source", "") or "Spore Mine Cysts").strip() or "Spore Mine Cysts"
                            request = DecisionRequest.create(
                                DECISION_CHOOSE_QUARRY,
                                f"{ability_name}: choose a moved-over target, spawn Spore Mines, or None.",
                                player_id=getattr(player, "id", None),
                                options=options,
                                context={
                                    "ability": "spore_mine_cysts",
                                    "ability_name": ability_name,
                                    "phase": "Movement phase",
                                    "unit_id": root_id,
                                    "source_unit_id": root_id,
                                    "source_model_id": source_model_id,
                                    "owner_id": str(owner_id or ""),
                                    "turn": int(turn or 0),
                                    "spec": dict(spec or {}),
                                },
                            )
                            self.request_decision(request)
                            break

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

    def _on_unit_move_ended_gravitic_pulse(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        action_key = str(action or "").strip().lower()
        if not action_key:
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
        if not isinstance(sr, dict) or not bool(sr.get("necrons_gravitic_pulse_fly_mortal_active", False)):
            return

        source_owner_id = str(sr.get("necrons_gravitic_pulse_fly_mortal_source_owner", "") or "")
        try:
            source_turn = int(sr.get("necrons_gravitic_pulse_fly_mortal_source_turn", 0) or 0)
        except (TypeError, ValueError):
            source_turn = 0
        current_player = self.get_current_player() if hasattr(self, "get_current_player") else None
        current_owner_id = str(getattr(current_player, "id", "") or "")
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if (
            source_owner_id
            and current_owner_id
            and source_owner_id == current_owner_id
            and source_turn
            and current_turn >= source_turn
        ):
            return

        from ..utility.dice import get_roll
        from ..utility.event_bus import append_action, append_dice

        ability_name = str(sr.get("necrons_gravitic_pulse_fly_mortal_source", "") or "Gravitic Pulse").strip() or "Gravitic Pulse"
        try:
            threshold = int(sr.get("necrons_gravitic_pulse_fly_mortal_threshold", 4) or 4)
        except (TypeError, ValueError):
            threshold = 4
        threshold = max(2, min(6, int(threshold)))
        mortal_spec = str(sr.get("necrons_gravitic_pulse_fly_mortal_wounds", "") or "D3").strip().upper()
        roll = int(get_roll("D6") or 0)
        total_mw = 0
        if int(roll) >= int(threshold):
            if mortal_spec == "D3":
                total_mw = int(get_roll("D3") or 0)
            elif mortal_spec == "D6":
                total_mw = int(get_roll("D6") or 0)
            else:
                try:
                    total_mw = int(mortal_spec or 0)
                except (TypeError, ValueError):
                    total_mw = 0
        if int(total_mw) > 0:
            root._apply_mortal_wounds_to_unit(root, int(total_mw), game_map=getattr(self, "map", None))

        owner = self._resolve_player_by_id(source_owner_id) if source_owner_id else None
        if owner is not None:
            append_dice(
                owner,
                (
                    f"{ability_name}: {getattr(root, 'name', 'Unit')} ended a {action_key} move; "
                    f"roll {int(roll)} (needs {int(threshold)}+) => {int(total_mw)} mortal wounds."
                ),
            )
            if int(total_mw) > 0:
                append_action(
                    owner,
                    f"{ability_name}: {getattr(root, 'name', 'Unit')} suffered {int(total_mw)} mortal wounds after moving.",
                )
            else:
                append_action(
                    owner,
                    f"{ability_name}: {getattr(root, 'name', 'Unit')} was unaffected after moving.",
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
        logger.info(f"{ability_name}: {getattr(model, 'name', 'Model')} -> {getattr(target_unit, 'name', 'Target')} "
            f"(rolls={rolls}) => {total_mw} mortal wounds")

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

    def _on_unit_set_up_deep_strike_enemy_range_mortal_wounds_battleshock(
        self,
        unit=None,
        set_up_as_reinforcements: bool = False,
        used_deep_strike: bool = False,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        if not bool(set_up_as_reinforcements) or not bool(used_deep_strike):
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
        if root is None:
            return
        if not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", False)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass

        try:
            owner = root.get_parent_army().player
        except Exception:
            owner = None
        if owner is None:
            return
        if owner is not self.get_current_player():
            return

        spec_fn = getattr(root, "model_deep_strike_setup_enemy_within_range_mortal_table_battleshock_specs", None)
        if not callable(spec_fn):
            return

        def _resolve_mortal(raw_value):
            token = str(raw_value or "").strip().lower()
            if token == "d3":
                return int(get_roll("D3") or 0), "D3"
            if token == "d6":
                return int(get_roll("D6") or 0), "D6"
            try:
                val = int(raw_value or 0)
            except (TypeError, ValueError):
                val = 0
            if val <= 0:
                return 0, ""
            return int(val), str(int(val))

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        from ..utility.event_bus import append_action, append_dice

        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        alive_models = [m for m in list(models or []) if getattr(m, "is_alive", False)]
        if not alive_models:
            return

        seen_enemy_ids: set[str] = set()
        enemy_roots = []
        for enemy in sorted(list(game_map.get_enemy_units(root) or []), key=_unit_sort_key):
            if enemy is None:
                continue
            try:
                enemy_root = enemy.get_attached_unit_root()
            except Exception:
                enemy_root = enemy
            if enemy_root is None:
                continue
            enemy_id = str(get_entity_id(enemy_root) or "")
            if not enemy_id or enemy_id in seen_enemy_ids:
                continue
            seen_enemy_ids.add(enemy_id)
            if not bool(getattr(enemy_root, "is_alive", lambda: False)()):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            try:
                if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                    continue
            except Exception:
                pass
            enemy_roots.append(enemy_root)
        if not enemy_roots:
            return

        for model in sorted(alive_models, key=lambda m: str(get_entity_id(m) or "")):
            specs = list(spec_fn(model) or [])
            if not specs:
                continue
            for spec in specs:
                try:
                    range_value = float(spec.get("range", 0) or 0)
                    threshold_low_min = int(spec.get("threshold_low_min", 0) or 0)
                    threshold_low_max = int(spec.get("threshold_low_max", 0) or 0)
                    threshold_high = int(spec.get("threshold_high", 0) or 0)
                except (TypeError, ValueError):
                    continue
                if (
                    range_value <= 0.0
                    or threshold_low_min <= 0
                    or threshold_low_max < threshold_low_min
                    or threshold_high <= 0
                ):
                    continue
                source_name = str(spec.get("source", "") or "Deep Strike mortals").strip() or "Deep Strike mortals"
                mortal_low = spec.get("mortal_low")
                mortal_high = spec.get("mortal_high")
                high_triggers_battleshock = bool(spec.get("high_triggers_battleshock", False))

                for enemy_root in enemy_roots:
                    try:
                        in_range = bool(root._model_within_range_of_unit(model, enemy_root, float(range_value)))
                    except Exception:
                        in_range = False
                    if not in_range:
                        continue

                    trigger_roll = int(get_roll("D6") or 0)
                    mortal_wounds = 0
                    mortal_note = ""
                    forced_battleshock = False

                    if threshold_low_min <= trigger_roll <= threshold_low_max:
                        mortal_wounds, mortal_note = _resolve_mortal(mortal_low)
                    elif trigger_roll >= threshold_high:
                        mortal_wounds, mortal_note = _resolve_mortal(mortal_high)
                        forced_battleshock = bool(high_triggers_battleshock)

                    if mortal_wounds > 0:
                        apply_mw = getattr(root, "_apply_mortal_wounds_to_unit", None)
                        if callable(apply_mw):
                            apply_mw(enemy_root, int(mortal_wounds), game_map=game_map)

                    tname = str(getattr(enemy_root, "name", "Unit") or "Unit")
                    if mortal_wounds > 0 and mortal_note:
                        append_dice(
                            owner,
                            f"{source_name}: {tname} roll {int(trigger_roll)} -> {mortal_note} = {int(mortal_wounds)} mortal wounds.",
                        )
                    elif mortal_wounds > 0:
                        append_dice(
                            owner,
                            f"{source_name}: {tname} roll {int(trigger_roll)} -> {int(mortal_wounds)} mortal wounds.",
                        )
                    else:
                        append_dice(owner, f"{source_name}: {tname} roll {int(trigger_roll)} -> no effect.")

                    if mortal_wounds > 0:
                        append_action(owner, f"{source_name}: {tname} suffers {int(mortal_wounds)} mortal wounds.")
                    else:
                        append_action(owner, f"{source_name}: {tname} suffers no mortal wounds.")

                    if forced_battleshock and bool(getattr(enemy_root, "is_alive", lambda: False)()):
                        enemy_root.take_battle_shock_test(int(getattr(self, "turn", 0) or 1))
                        append_action(owner, f"{source_name}: {tname} takes a Battle-shock test.")

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

    def _on_unit_set_up_a_foot_in_the_future(
        self,
        unit=None,
        set_up_as_reinforcements: bool = False,
        **_kwargs,
    ) -> None:
        if unit is None or not bool(set_up_as_reinforcements):
            return
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return
        if not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", False)):
            return
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            return
        if bool(getattr(root, "is_in_reserves", lambda: False)()):
            return

        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        if army is None:
            return
        player = getattr(army, "player", None)
        if player is None:
            return
        current_player = self.get_current_player()
        if current_player is None or current_player is not player:
            return
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "MOVEMENT_PHASE":
            return

        root_id = str(get_entity_id(root) or "")
        if not root_id:
            return
        owner_id = str(getattr(current_player, "id", "") or "")
        turn = int(getattr(self, "turn", 0) or 0)

        members = list(getattr(root, "get_attached_unit_members", lambda: [root])() or [root])
        if not members:
            members = [root]
        enhancement_source = None
        enhancement_sr = None
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_a_foot_in_the_future", False)):
                continue
            enhancement_source = member
            enhancement_sr = sr
            break
        if enhancement_source is None or not isinstance(enhancement_sr, dict):
            return

        requires_bearer_alive = bool(enhancement_sr.get("enhancement_a_foot_in_the_future_requires_bearer_alive", True))
        bearer_model_id = str(
            enhancement_sr.get("enhancement_a_foot_in_the_future_bearer_model_id")
            or enhancement_sr.get("enhancement_bearer_model_id")
            or ""
        ).strip()
        if requires_bearer_alive:
            bearer_alive = False
            if bearer_model_id:
                for model in list(getattr(enhancement_source, "models", []) or []):
                    if str(get_entity_id(model) or "") != bearer_model_id:
                        continue
                    model_alive_attr = getattr(model, "is_alive", True)
                    bearer_alive = bool(model_alive_attr() if callable(model_alive_attr) else model_alive_attr)
                    break
            else:
                get_bearer = getattr(enhancement_source, "_get_enhancement_bearer_model", None)
                bearer_model = get_bearer() if callable(get_bearer) else None
                if bearer_model is not None:
                    model_alive_attr = getattr(bearer_model, "is_alive", True)
                    bearer_alive = bool(model_alive_attr() if callable(model_alive_attr) else model_alive_attr)
                    resolved_id = str(get_entity_id(bearer_model) or "")
                    if resolved_id:
                        bearer_model_id = resolved_id
            if not bearer_alive:
                return

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for pending in list(queue.list() or []):
                if str(getattr(pending, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                pending_ctx = dict(getattr(pending, "context", {}) or {})
                if str(pending_ctx.get("ability", "") or "") != "a_foot_in_the_future":
                    continue
                if str(pending_ctx.get("target_unit_id", "") or "") != root_id:
                    continue
                if str(pending_ctx.get("turn_owner_id", "") or "") != owner_id:
                    continue
                if int(pending_ctx.get("turn", 0) or 0) != int(turn):
                    continue
                return

        source_unit_id = str(get_entity_id(enhancement_source) or root_id)
        move_roll = str(enhancement_sr.get("enhancement_a_foot_in_the_future_move_roll", "D6") or "D6").strip().upper() or "D6"
        no_charge_this_turn = bool(enhancement_sr.get("enhancement_a_foot_in_the_future_no_charge_this_turn", True))

        options = [
            DecisionOption.create(
                "Use A Foot in the Future",
                payload={"target_unit_id": root_id},
            ),
            DecisionOption.create(
                "None",
                payload={"skip": True},
            ),
        ]
        self.request_decision(
            DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"A Foot in the Future: choose whether {getattr(root, 'name', 'Unit')} makes a Normal move of up to {move_roll}\".",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "a_foot_in_the_future",
                    "ability_name": "A Foot in the Future",
                    "source_unit_id": source_unit_id,
                    "target_unit_id": root_id,
                    "unit_id": root_id,
                    "candidate_unit_ids": [root_id],
                    "move_roll": move_roll,
                    "no_charge_this_turn": bool(no_charge_this_turn),
                    "requires_bearer_alive": bool(requires_bearer_alive),
                    "bearer_model_id": bearer_model_id,
                    "optional": True,
                    "phase": "Movement phase",
                    "turn_owner_id": owner_id,
                    "turn": int(turn),
                },
            )
        )

    def _on_unit_set_up_drukhari_detachments(
        self,
        unit=None,
        set_up_as_reinforcements: bool = False,
        used_deep_strike: bool = False,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else None
        if army is None:
            return
        mgr = getattr(army, "drukhari_detachments", None)
        if mgr is None:
            return
        on_unit_set_up = getattr(mgr, "on_unit_set_up", None)
        if not callable(on_unit_set_up):
            return
        on_unit_set_up(
            unit=root,
            game=self,
            set_up_as_reinforcements=bool(set_up_as_reinforcements),
            used_deep_strike=bool(used_deep_strike),
        )

    def _on_fight_targets_selected_drukhari_detachments(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None:
            return
        get_root = getattr(attacking_unit, "get_attached_unit_root", None)
        source_root = get_root() if callable(get_root) else attacking_unit
        if source_root is None:
            return
        get_parent_army = getattr(source_root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else None
        if army is None:
            return
        mgr = getattr(army, "drukhari_detachments", None)
        if mgr is None:
            return
        on_selected = getattr(mgr, "on_fight_targets_selected", None)
        if not callable(on_selected):
            return
        on_selected(
            attacking_unit=source_root,
            target_units=list(target_units or []),
            game=self,
        )

    def _on_unit_set_up_genestealer_cults_detachments(
        self,
        unit=None,
        set_up_as_reinforcements: bool = False,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else None
        if army is None:
            return
        mgr = getattr(army, "genestealer_cults_detachments", None)
        if mgr is None:
            return
        on_unit_set_up = getattr(mgr, "on_unit_set_up", None)
        if not callable(on_unit_set_up):
            return
        on_unit_set_up(
            unit=root,
            game=self,
            set_up_as_reinforcements=bool(set_up_as_reinforcements),
        )

    def _on_unit_set_up_tyranids_detachments(
        self,
        unit=None,
        set_up_as_reinforcements: bool = False,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return
        managers = []
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else None
            if army is None:
                continue
            mgr = getattr(army, "tyranids_detachments", None)
            if mgr is None:
                continue
            on_unit_set_up = getattr(mgr, "on_unit_set_up", None)
            if not callable(on_unit_set_up):
                continue
            managers.append(on_unit_set_up)
        for on_unit_set_up in managers:
            on_unit_set_up(
                unit=root,
                game=self,
                set_up_as_reinforcements=bool(set_up_as_reinforcements),
            )

    def _on_unit_set_up_orks_detachments(
        self,
        unit=None,
        set_up_as_reinforcements: bool = False,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else None
        if army is None:
            return
        mgr = getattr(army, "orks_detachments", None)
        if mgr is None:
            return
        on_unit_set_up = getattr(mgr, "on_unit_set_up", None)
        if not callable(on_unit_set_up):
            return
        on_unit_set_up(
            unit=root,
            game=self,
            set_up_as_reinforcements=bool(set_up_as_reinforcements),
        )

    def _on_unit_set_up_setup_reactive_shoot_or_charge(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        self._record_setup_reactive_shoot_or_charge_candidate(unit)

    def _on_unit_set_up_hyperspace_hunters(
        self,
        unit=None,
        set_up_as_reinforcements: bool = False,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        self._record_hyperspace_hunters_candidate(
            unit,
            set_up_as_reinforcements=bool(set_up_as_reinforcements),
        )

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

    def _apply_kill_reward_objective_control_bonus(
        self,
        *,
        attacker_unit=None,
        spec: Optional[dict] = None,
    ) -> None:
        """Apply persistent Objective Control bonuses granted by on-destroy kill-reward specs."""
        if attacker_unit is None or not isinstance(spec, dict):
            return
        try:
            oc_bonus = int(spec.get("objective_control_bonus", 0) or 0)
        except Exception:
            oc_bonus = 0
        if oc_bonus <= 0:
            return

        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        if root is None:
            return

        source = str(spec.get("source_ability", "") or "Kill reward").strip() or "Kill reward"
        source_norm = str(source).replace("\u2019", "'").replace("\u2018", "'").lower()
        source_norm = re.sub(r"[^a-z0-9]+", " ", source_norm)
        source_norm = re.sub(r"\s+", " ", source_norm).strip()
        if not source_norm:
            source_norm = "kill reward"

        first_time = bool(spec.get("first_time", False))
        requires_not_battle_shocked = bool(spec.get("requires_not_battle_shocked", False))

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}

        entries_raw = list(sr.get("kill_reward_objective_control_bonus_entries", []) or [])
        entries: list[dict] = [e for e in entries_raw if isinstance(e, dict)]

        existing_entry: Optional[dict] = None
        for entry in entries:
            entry_norm = str(entry.get("source_norm", "") or "").strip().lower()
            if entry_norm and entry_norm == source_norm:
                existing_entry = entry
                break

        if existing_entry is not None:
            if first_time:
                return
            try:
                stacks = int(existing_entry.get("stacks", 1) or 1)
            except Exception:
                stacks = 1
            existing_entry["stacks"] = int(max(1, stacks + 1))
            existing_entry["bonus"] = int(oc_bonus)
            existing_entry["source"] = source
            existing_entry["source_norm"] = source_norm
            existing_entry["requires_not_battle_shocked"] = bool(requires_not_battle_shocked)
        else:
            entries.append(
                {
                    "source": source,
                    "source_norm": source_norm,
                    "bonus": int(oc_bonus),
                    "stacks": 1,
                    "requires_not_battle_shocked": bool(requires_not_battle_shocked),
                }
            )

        entries.sort(key=lambda e: str(e.get("source_norm", "") or ""))
        sr["kill_reward_objective_control_bonus_entries"] = entries
        root.special_rules = sr

    def _on_model_destroyed_rules(self, attacker_model=None, attacker_unit=None, target_model=None, target_unit=None, **_kwargs) -> None:
        # Space Marines (The Lost Brethren): Vengeful Onslaught.
        try:
            if target_model is not None and target_unit is not None:
                try:
                    target_root = target_unit.get_attached_unit_root()
                except Exception:
                    target_root = target_unit
                source_member = None
                source_sr = {}
                find_source = getattr(self, "_attached_member_with_enhancement_flag", None)
                if callable(find_source):
                    _src_root, source_member, source_sr = find_source(
                        target_root,
                        "enhancement_vengeful_onslaught",
                    )
                if source_member is not None and isinstance(source_sr, dict):
                    alive_attr = getattr(target_model, "is_alive", False)
                    target_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    if not target_alive:
                        bearer_id = str(
                            source_sr.get("enhancement_vengeful_onslaught_bearer_model_id", "")
                            or source_sr.get("enhancement_bearer_model_id", "")
                            or ""
                        ).strip()
                        target_model_id = str(get_entity_id(target_model) or "").strip()
                        if bearer_id and target_model_id and bearer_id == target_model_id:
                            owner_army = target_root.get_parent_army() if target_root is not None else None
                            sm_mgr = getattr(owner_army, "space_marines_detachments", None) if owner_army is not None else None
                            if sm_mgr is not None and bool(getattr(sm_mgr, "is_the_lost_brethren", lambda: False)()):
                                owner_player = getattr(owner_army, "player", None)
                                owner_id = str(getattr(owner_player, "id", "") or "")
                                current_player = self.get_current_player()
                                current_player_id = str(getattr(current_player, "id", "") or "")
                                turn_now = int(getattr(self, "turn", 0) or 0)
                                expires_turn = int(turn_now + 1) if (owner_id and current_player_id == owner_id) else int(turn_now)
                                source_name = str(
                                    source_sr.get("enhancement_vengeful_onslaught_source", "")
                                    or "Vengeful Onslaught"
                                ).strip() or "Vengeful Onslaught"
                                try:
                                    hit_bonus = int(source_sr.get("enhancement_vengeful_onslaught_hit_bonus", 1) or 1)
                                except Exception:
                                    hit_bonus = 1
                                seen_roots: set[str] = set()
                                for unit in list(getattr(owner_army, "units", []) or []):
                                    if unit is None:
                                        continue
                                    try:
                                        root = unit.get_attached_unit_root()
                                    except Exception:
                                        root = unit
                                    if root is None:
                                        continue
                                    rid = str(get_entity_id(root) or "")
                                    if rid and rid in seen_roots:
                                        continue
                                    if rid:
                                        seen_roots.add(rid)
                                    if not bool(getattr(sm_mgr, "_unit_is_death_company", lambda _u: False)(root)):
                                        continue
                                    rsr = getattr(root, "special_rules", None)
                                    if not isinstance(rsr, dict):
                                        rsr = {}
                                    rsr["lost_brethren_vengeful_onslaught_active"] = True
                                    rsr["lost_brethren_vengeful_onslaught_owner_id"] = str(owner_id or "")
                                    rsr["lost_brethren_vengeful_onslaught_expires_turn"] = int(expires_turn)
                                    rsr["lost_brethren_vengeful_onslaught_hit_bonus"] = int(max(0, hit_bonus))
                                    rsr["lost_brethren_vengeful_onslaught_source"] = source_name
                                    root.special_rules = rsr
        except Exception:
            pass

        # Generic partial support for "gain CP when this model destroys an enemy KEYWORD unit/model".
        if attacker_unit is None or target_unit is None:
            return

        # Must be an enemy destroy event
        if attacker_unit.get_parent_army() == target_unit.get_parent_army():
            return

        def _norm_ability_name(value: str) -> str:
            text = str(value or "").replace("\u2019", "'").replace("\u2018", "'").lower()
            text = re.sub(r"[^a-z0-9]+", " ", text)
            return re.sub(r"\s+", " ", text).strip()

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
                    source_norm = _norm_ability_name(spec.get("source_ability", ""))
                    if source_norm == "eyes of the oracle":
                        is_character_model = bool(getattr(target_model, "is_character", False))
                        if not is_character_model and target_model is not None:
                            has_any = getattr(target_model, "has_any_keyword", None)
                            if callable(has_any):
                                is_character_model = bool(has_any("CHARACTER"))
                        if not is_character_model:
                            continue

                        try:
                            attacker_root = attacker_unit.get_attached_unit_root()
                        except Exception:
                            attacker_root = attacker_unit
                        try:
                            source_members = list(attacker_root.get_attached_unit_members() or [])
                        except Exception:
                            source_members = []
                        if not source_members:
                            source_members = [attacker_root]
                        source_members = sorted(
                            [member for member in list(source_members or []) if member is not None],
                            key=lambda member: str(get_entity_id(member) or ""),
                        )

                        active_source_sr = None
                        for source_member in source_members:
                            source_sr = getattr(source_member, "special_rules", None)
                            if not (
                                isinstance(source_sr, dict)
                                and bool(source_sr.get("enhancement_eyes_of_the_oracle", False))
                            ):
                                continue

                            bearer_id = str(
                                source_sr.get("enhancement_eyes_of_the_oracle_bearer_model_id", "")
                                or source_sr.get("enhancement_bearer_model_id", "")
                                or ""
                            ).strip()
                            bearer_alive = False
                            for model in list(getattr(source_member, "models", []) or []):
                                if bearer_id and str(get_entity_id(model) or "") != bearer_id:
                                    continue
                                alive_attr = getattr(model, "is_alive", True)
                                bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                                if bearer_alive:
                                    break
                            if not bearer_alive:
                                get_bearer = getattr(source_member, "_get_enhancement_bearer_model", None)
                                bearer_model = get_bearer() if callable(get_bearer) else None
                                if bearer_model is not None and bearer_id and str(get_entity_id(bearer_model) or "") != bearer_id:
                                    bearer_model = None
                                if bearer_model is not None:
                                    alive_attr = getattr(bearer_model, "is_alive", True)
                                    bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                            if not bearer_alive:
                                continue
                            active_source_sr = source_sr
                            break

                        if active_source_sr is None:
                            continue
                        try:
                            cp = int(active_source_sr.get("enhancement_eyes_of_the_oracle_cp_gain", cp) or cp)
                        except (TypeError, ValueError):
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

                if spec.get("type") == "objective_control_bonus_on_destroy":
                    self._apply_kill_reward_objective_control_bonus(
                        attacker_unit=attacker_unit,
                        spec=spec,
                    )

        # Drukhari: Soul Trap (first melee kill marks pending; applied after attacks resolve).
        try:
            if attacker_model is not None:
                root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
                if root is not None and hasattr(root, "model_has_soul_trap_ability"):
                    if root.model_has_soul_trap_ability(attacker_model):
                        is_melee_kill = False
                        wp = _kwargs.get("weapon_profile", None)
                        pw = getattr(wp, "parent_wargear", None)
                        if wp is not None and pw is not None and callable(getattr(pw, "is_melee", None)):
                            is_melee_kill = bool(pw.is_melee())
                        if is_melee_kill:
                            has_empowerment = False
                            if hasattr(root, "model_has_soul_trap_empowerment"):
                                has_empowerment = bool(root.model_has_soul_trap_empowerment(attacker_model))
                            if not has_empowerment and hasattr(root, "mark_model_soul_trap_pending"):
                                root.mark_model_soul_trap_pending(attacker_model)
        except Exception:
            pass

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

        if isinstance(sr, dict) and sr.get("enhancement_soul_glutton"):
            if attacker_model is not None:
                bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
                attacker_id = str(getattr(attacker_model, "id", getattr(attacker_model, "_id", "")) or "")
                if not bearer_id or attacker_id == bearer_id:
                    wp = _kwargs.get("weapon_profile", None)
                    pw = getattr(wp, "parent_wargear", None)
                    is_melee_attack = bool(wp is not None and pw is not None and pw.is_melee())
                    phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
                    if is_melee_attack and phase_name == "FIGHT_PHASE":
                        try:
                            current_player = self.get_current_player()
                        except Exception:
                            current_player = None
                        owner = str(getattr(current_player, "id", "") or "")
                        try:
                            kills = int(sr.get("enhancement_soul_glutton_phase_kills", 0) or 0)
                        except Exception:
                            kills = 0
                        sr["enhancement_soul_glutton_phase_kills"] = int(max(0, kills) + 1)
                        sr["enhancement_soul_glutton_phase"] = "FIGHT_PHASE"
                        sr["enhancement_soul_glutton_turn"] = int(getattr(self, "turn", 0) or 0)
                        sr["enhancement_soul_glutton_turn_owner"] = owner
                        attacker_unit.special_rules = sr

        if isinstance(sr, dict) and attacker_model is not None:
            get_atomic_rule = getattr(attacker_unit, "get_atomic_energy_manipulator_rule", None)
            atomic_rule = get_atomic_rule(attacker_model) if callable(get_atomic_rule) else None
            if isinstance(atomic_rule, dict):
                wp = _kwargs.get("weapon_profile", None)
                pw = getattr(wp, "parent_wargear", None)
                is_melee_attack = bool(wp is not None and pw is not None and pw.is_melee())
                phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
                if is_melee_attack and phase_name == "FIGHT_PHASE":
                    try:
                        current_player = self.get_current_player()
                    except Exception:
                        current_player = None
                    owner = str(getattr(current_player, "id", "") or "")
                    model_id = str(get_entity_id(attacker_model) or "")
                    if model_id:
                        kills_by_model = sr.get("atomic_energy_manipulator_phase_kills")
                        if not isinstance(kills_by_model, dict):
                            kills_by_model = {}
                        try:
                            prev = int(kills_by_model.get(model_id, 0) or 0)
                        except Exception:
                            prev = 0
                        kills_by_model[model_id] = int(max(0, prev) + 1)
                        sr["atomic_energy_manipulator_phase_kills"] = kills_by_model
                        sr["atomic_energy_manipulator_phase"] = "FIGHT_PHASE"
                        sr["atomic_energy_manipulator_turn"] = int(getattr(self, "turn", 0) or 0)
                        sr["atomic_energy_manipulator_turn_owner"] = owner
                        attacker_unit.special_rules = sr

        if isinstance(sr, dict) and sr.get("enhancement_thief_of_secrets"):
            if attacker_model is not None:
                bearer_id = str(
                    sr.get("enhancement_thief_of_secrets_bearer_model_id", "")
                    or sr.get("enhancement_bearer_model_id", "")
                    or ""
                )
                attacker_id = str(getattr(attacker_model, "id", getattr(attacker_model, "_id", "")) or "")
                if not bearer_id or attacker_id == bearer_id:
                    wp = _kwargs.get("weapon_profile", None)
                    pw = getattr(wp, "parent_wargear", None)
                    is_melee_attack = bool(wp is not None and pw is not None and pw.is_melee())
                    phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
                    if is_melee_attack and phase_name == "FIGHT_PHASE":
                        try:
                            current_player = self.get_current_player()
                        except Exception:
                            current_player = None
                        owner = str(getattr(current_player, "id", "") or "")
                        try:
                            kills = int(sr.get("enhancement_thief_of_secrets_phase_kills", 0) or 0)
                        except Exception:
                            kills = 0
                        sr["enhancement_thief_of_secrets_phase_kills"] = int(max(0, kills) + 1)
                        sr["enhancement_thief_of_secrets_pending_upgrade"] = True
                        sr["enhancement_thief_of_secrets_pending_phase"] = "FIGHT_PHASE"
                        sr["enhancement_thief_of_secrets_pending_turn"] = int(getattr(self, "turn", 0) or 0)
                        sr["enhancement_thief_of_secrets_pending_turn_owner"] = owner
                        attacker_unit.special_rules = sr

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

    def _on_fight_attacks_resolved_soul_trap(self, unit=None, **_kwargs) -> None:
        """Promote pending Soul Trap kills once the attacking unit has resolved all of its fight attacks."""
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        except Exception:
            root = unit
        if root is None:
            return
        promote_fn = getattr(root, "promote_pending_soul_trap_models", None)
        if callable(promote_fn):
            promote_fn()
        return

    def _on_model_destroyed_friendly_destroyed_model_weapon_attacks_override(
        self,
        target_model=None,
        target_unit=None,
        **_kwargs,
    ) -> None:
        """
        Apply model attack overrides for rules that trigger when a friendly model is destroyed nearby.

        Example supported rule text:
        "If a friendly ADEPTUS MECHANICUS VEHICLE model is destroyed within 12\" of this model,
        until the end of the battle, this model's Omnissian axe has an Attacks characteristic of 6."
        """
        if target_model is None or target_unit is None:
            return

        try:
            destroyed_root = target_unit.get_attached_unit_root()
        except (AttributeError, TypeError, ValueError):
            destroyed_root = target_unit
        if destroyed_root is None:
            return

        try:
            owner_army = destroyed_root.get_parent_army()
        except (AttributeError, TypeError, ValueError):
            owner_army = None
        if owner_army is None:
            return

        try:
            from ..utility.aura_utils import distance_between_models_bases_3d
        except ImportError:
            return

        def _normalize_weapon_name(value: str) -> str:
            text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
            return re.sub(r"\s+", " ", text).strip()

        processed_unit_ids: set[str] = set()
        for candidate in list(getattr(owner_army, "units", []) or []):
            if candidate is None:
                continue
            try:
                root = candidate.get_attached_unit_root()
            except (AttributeError, TypeError, ValueError):
                root = candidate
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if root_id:
                if root_id in processed_unit_ids:
                    continue
                processed_unit_ids.add(root_id)

            get_ability = getattr(root, "get_friendly_destroyed_model_weapon_attacks_override_ability", None)
            if not callable(get_ability):
                continue
            ability = get_ability()
            if not isinstance(ability, dict):
                continue
            if str(ability.get("destroyed_kind", "model") or "model").strip().lower() != "model":
                continue
            if not self._unit_on_battlefield_for_reposition(root):
                continue

            friendly_keyword = str(ability.get("friendly_keyword", "") or "").strip()
            if friendly_keyword:
                match_keywords = getattr(root, "_unit_matches_keyword_phrase", None)
                if not callable(match_keywords):
                    continue
                try:
                    if not bool(match_keywords(destroyed_root, friendly_keyword, use_effective=False)):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue

            try:
                trigger_range = float(ability.get("range", 0) or 0)
            except (TypeError, ValueError):
                trigger_range = 0.0
            if trigger_range <= 0.0:
                continue

            try:
                attacks_value = int(ability.get("attacks_value", 0) or 0)
            except (TypeError, ValueError):
                attacks_value = 0
            if attacks_value <= 0:
                continue

            weapon_name = str(ability.get("weapon_name", "") or "").strip()
            if not weapon_name:
                continue

            try:
                source_models = list(root.get_attached_unit_models() or [])
            except (AttributeError, TypeError, ValueError):
                source_models = list(getattr(root, "models", []) or [])
            if not source_models:
                continue

            in_range_models: list[Model] = []
            for source_model in source_models:
                if source_model is None:
                    continue
                try:
                    alive_attr = getattr(source_model, "is_alive", True)
                    is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                except (TypeError, ValueError):
                    is_alive = False
                if not is_alive:
                    continue
                try:
                    distance = float(distance_between_models_bases_3d(source_model, target_model))
                except (AttributeError, TypeError, ValueError):
                    continue
                if distance <= trigger_range + 1e-6:
                    in_range_models.append(source_model)
            if not in_range_models:
                continue

            ability_name = str(ability.get("name", "") or "Friendly destroyed model attacks override").strip()
            if not ability_name:
                ability_name = "Friendly destroyed model attacks override"
            source_label = ability_name
            normalized_source = _normalize_weapon_name(ability_name) or "friendly_destroyed_model_attacks_override"

            # Add a coarse alias (last token) to handle weapon naming variants across datasheets
            # while still preferring the exact parsed weapon phrase.
            alias_candidates = [weapon_name]
            normalized_weapon = _normalize_weapon_name(weapon_name)
            if normalized_weapon:
                tokens = [tok for tok in normalized_weapon.split(" ") if tok]
                if len(tokens) > 1:
                    last_token = tokens[-1]
                    if last_token not in ("weapon", "weapons"):
                        alias_candidates.append(last_token)
            seen_aliases: set[str] = set()
            weapon_aliases: list[str] = []
            for candidate_name in alias_candidates:
                norm = _normalize_weapon_name(candidate_name)
                if not norm or norm in seen_aliases:
                    continue
                seen_aliases.add(norm)
                weapon_aliases.append(candidate_name)
            if not weapon_aliases:
                continue

            for source_model in in_range_models:
                model_id = str(get_entity_id(source_model) or "")
                set_override = getattr(source_model, "set_temporary_weapon_attacks_override", None)
                if not callable(set_override):
                    continue
                for idx, alias in enumerate(weapon_aliases):
                    key = f"{normalized_source}:{model_id}:{idx}"
                    set_override(
                        key=key,
                        weapon_name=str(alias),
                        attacks_value=int(attacks_value),
                        source=source_label,
                        expires_phase="",
                    )

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

    def _on_model_destroyed_spirit_conclave_shepherds(
        self,
        attacker_unit=None,
        target_model=None,
        target_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or target_model is None or target_unit is None:
            return
        try:
            owner_army = target_unit.get_parent_army()
        except Exception:
            owner_army = None
        if owner_army is None:
            return
        mgr = getattr(owner_army, "aeldari_detachments", None)
        if mgr is None:
            return
        should_award = getattr(mgr, "spirit_conclave_destroyed_psyker_awards_vengeful_dead", None)
        if not callable(should_award):
            return
        if not bool(
            should_award(
                destroyed_model=target_model,
                destroyed_unit=target_unit,
                destroyed_by_unit=attacker_unit,
            )
        ):
            return
        apply_tokens = getattr(mgr, "spirit_conclave_add_vengeful_dead_tokens", None)
        if not callable(apply_tokens):
            return
        apply_tokens(attacker_unit, count=1)

    def _on_unit_destroyed_phase_kill_tracking(
        self,
        unit=None,
        destroyed_by_unit=None,
        destroyed_by_model=None,
        **_kwargs,
    ) -> None:
        """Track units that destroyed enemy units during Shooting/Fight phases."""
        if unit is None or destroyed_by_unit is None:
            return
        if destroyed_by_unit.get_parent_army() == unit.get_parent_army():
            return
        phase = getattr(self, "phase", None)
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        try:
            root = destroyed_by_unit.get_attached_unit_root()
        except Exception:
            root = destroyed_by_unit
        if root is None:
            return

        if pname == "FIGHT_PHASE":
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            for member in members:
                if member is None:
                    continue
                member_sr = getattr(member, "special_rules", None)
                if not isinstance(member_sr, dict):
                    continue
                upgrade_entries = list(member_sr.get("fight_phase_destroy_enemy_fnp_upgrade_entries", []) or [])
                if not upgrade_entries:
                    continue
                member_sr["fight_phase_destroy_enemy_fnp_upgrade_active"] = True
                member.special_rules = member_sr

        # Blood Legion enhancement: Gateway Unto Damnation kill tracking.
        attacker_model_id = str(get_entity_id(destroyed_by_model) or "") if destroyed_by_model is not None else ""
        if attacker_model_id:
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            try:
                members = sorted(members, key=lambda u: str(get_entity_id(u) or ""))
            except Exception:
                members = list(members)
            for member in members:
                if member is None:
                    continue
                member_sr = getattr(member, "special_rules", None)
                if not isinstance(member_sr, dict) or not bool(member_sr.get("enhancement_gateway_unto_damnation")):
                    continue
                bearer_model_id = str(member_sr.get("enhancement_bearer_model_id", "") or "")
                if bearer_model_id and bearer_model_id != attacker_model_id:
                    continue
                try:
                    current = int(
                        member_sr.get(
                            "enhancement_gateway_unto_damnation_destroyed_enemy_units_this_battle",
                            0,
                        )
                        or 0
                    )
                except Exception:
                    current = 0
                member_sr["enhancement_gateway_unto_damnation_destroyed_enemy_units_this_battle"] = int(current + 1)
                member.special_rules = member_sr
                break

        turn = int(getattr(self, "turn", 0) or 0)
        turn_owner = self.get_current_player()
        turn_owner_id = str(getattr(turn_owner, "id", "") or "")

        # Blood Legion: Blood Tainted objective sticky tracking.
        attacker_army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        cd_mgr = getattr(attacker_army, "chaos_daemons_detachments", None) if attacker_army is not None else None
        if cd_mgr is not None and callable(getattr(cd_mgr, "blood_tainted_applies", None)):
            if bool(cd_mgr.blood_tainted_applies(root)):
                try:
                    destroyed_root = unit.get_attached_unit_root()
                except Exception:
                    destroyed_root = unit
                destroyed_sr = getattr(destroyed_root, "special_rules", None) if destroyed_root is not None else None
                if isinstance(destroyed_sr, dict):
                    snap_phase = str(destroyed_sr.get("blood_tainted_phase_snapshot_phase", "") or "").strip().upper()
                    try:
                        snap_turn = int(destroyed_sr.get("blood_tainted_phase_snapshot_turn", 0) or 0)
                    except Exception:
                        snap_turn = 0
                    snap_owner = str(destroyed_sr.get("blood_tainted_phase_snapshot_turn_owner", "") or "")
                    snap_objective_ids = [
                        str(value or "")
                        for value in list(destroyed_sr.get("blood_tainted_phase_snapshot_objective_ids", []) or [])
                        if str(value or "")
                    ]
                    if (
                        snap_phase
                        and snap_phase == pname
                        and snap_turn == turn
                        and snap_owner == turn_owner_id
                        and snap_objective_ids
                    ):
                        attacker_sr = getattr(root, "special_rules", None)
                        if not isinstance(attacker_sr, dict):
                            attacker_sr = {}
                        pending = dict(attacker_sr.get("blood_tainted_pending", {}) or {})
                        phase_key = f"{pname}|{int(turn)}|{turn_owner_id}"
                        existing = {
                            str(value or "")
                            for value in list(pending.get(phase_key, []) or [])
                            if str(value or "")
                        }
                        existing.update(snap_objective_ids)
                        pending[phase_key] = sorted(existing)
                        attacker_sr["blood_tainted_pending"] = pending
                        root.special_rules = attacker_sr

        if pname not in ("SHOOTING_PHASE", "FIGHT_PHASE"):
            return
        try:
            owner = destroyed_by_unit.get_parent_army().player
        except Exception:
            owner = None
        if owner is None:
            return
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
        if unit is None:
            return
        destroyed_unit_id = str(get_entity_id(unit) or getattr(unit, "_id", "") or "").strip()

        # Chaos Space Marines: Renegade Warband (Weaponised Hatred)
        # If the current Vendetta target is destroyed, queue reactive retarget selection.
        if destroyed_unit_id:
            try:
                for maybe_player in list(getattr(self, "players", []) or []):
                    if maybe_player is None:
                        continue
                    maybe_army = maybe_player.get_army() if hasattr(maybe_player, "get_army") else None
                    if maybe_army is None:
                        continue
                    csm_mgr = getattr(maybe_army, "chaos_space_marines_detachments", None)
                    promote_fn = getattr(csm_mgr, "_promote_weaponised_hatred_target_if_needed", None) if csm_mgr is not None else None
                    if not callable(promote_fn):
                        continue
                    promote_fn(destroyed_unit_id)
            except Exception:
                pass

        # Chaos Space Marines: Soulforged Warpack (Soul Harvester).
        try:
            for maybe_player in list(getattr(self, "players", []) or []):
                if maybe_player is None:
                    continue
                maybe_army = maybe_player.get_army() if hasattr(maybe_player, "get_army") else None
                if maybe_army is None:
                    continue
                csm_mgr = getattr(maybe_army, "chaos_space_marines_detachments", None)
                harvester_fn = (
                    getattr(csm_mgr, "soulforged_soul_harvester_on_enemy_unit_destroyed", None)
                    if csm_mgr is not None
                    else None
                )
                if not callable(harvester_fn):
                    continue
                for outcome in list(harvester_fn(unit, game=self) or []):
                    if not isinstance(outcome, dict) or not bool(outcome.get("triggered", False)):
                        continue
                    self.event_system.publish(
                        "command_points_gained",
                        player=maybe_player,
                        amount=int(outcome.get("gained", 0) or 0),
                        reason=str(outcome.get("source", "") or "Soul Harvester"),
                        attacker_unit=destroyed_by_unit,
                        target_unit=unit,
                        attacker_model=destroyed_by_model,
                        roll=int(outcome.get("roll", 0) or 0),
                        success_on=int(outcome.get("success_on", 5) or 5),
                        cp_gain=int(outcome.get("cp_gain", 1) or 1),
                    )
        except Exception:
            pass

        if destroyed_by_unit is None:
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

        # Adepta Sororitas datasheet support:
        # enemy units that destroyed one or more friendly ADEPTA SORORITAS units this battle.
        destroyed_army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
        destroyed_is_adepta_sororitas = False
        if destroyed_army is not None:
            faction_id = str(getattr(destroyed_army, "faction_id", "") or "").strip().upper()
            destroyed_is_adepta_sororitas = faction_id == "AS"
        if not destroyed_is_adepta_sororitas:
            has_any_keyword = getattr(unit, "has_any_keyword", None)
            if callable(has_any_keyword):
                destroyed_is_adepta_sororitas = bool(has_any_keyword("ADEPTA SORORITAS"))
        if destroyed_is_adepta_sororitas and destroyed_army is not None and attacker_root is not None:
            destroyed_army_id = str(get_entity_id(destroyed_army) or getattr(destroyed_army, "_id", "") or "")
            attacker_root_id = str(get_entity_id(attacker_root) or getattr(attacker_root, "_id", "") or "")
            if destroyed_army_id and attacker_root_id:
                tracked = self._adepta_sororitas_destroyers_by_army_id.setdefault(destroyed_army_id, set())
                tracked.add(attacker_root_id)

        # Chaos Space Marines: Veterans of the Long War (Eye of Abaddon).
        try:
            attacker_army = attacker_root.get_parent_army() if attacker_root is not None else None
            csm_mgr = getattr(attacker_army, "chaos_space_marines_detachments", None) if attacker_army is not None else None
            eye_fn = getattr(csm_mgr, "veterans_eye_of_abaddon_on_focus_destroyed", None) if csm_mgr is not None else None
            if callable(eye_fn):
                eye_result = eye_fn(unit, game=self)
                if isinstance(eye_result, dict) and bool(eye_result.get("triggered", False)):
                    player = getattr(attacker_army, "player", None)
                    if player is not None:
                        self.event_system.publish(
                            "command_points_gained",
                            player=player,
                            amount=int(eye_result.get("gained", 0) or 0),
                            reason=str(eye_result.get("source", "") or "Eye of Abaddon"),
                            attacker_unit=attacker_root,
                            target_unit=unit,
                            attacker_model=destroyed_by_model,
                            roll=int(eye_result.get("roll", 0) or 0),
                            success_on=int(eye_result.get("success_on", 4) or 4),
                            cp_gain=int(eye_result.get("cp_gain", 1) or 1),
                        )
        except Exception:
            pass

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

        # Necrons: Prophet of Destruction (Nekrosor Ammentar).
        # Each time this model destroys an enemy unit, select one other friendly DESTROYER CULT unit
        # within 9"; that unit re-rolls Wound rolls of 1 until end of phase.
        if bool(getattr(self, "is_authoritative", True)) and attacker_root is not None:
            get_specs = getattr(attacker_root, "unit_prophet_of_destruction_specs", None)
            prophet_specs = list(get_specs() or []) if callable(get_specs) else []
            attacker_army = attacker_root.get_parent_army() if hasattr(attacker_root, "get_parent_army") else None
            attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
            if prophet_specs and attacker_army is not None and attacker_player is not None:
                try:
                    phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
                except Exception:
                    phase_name = ""
                try:
                    turn_value = int(getattr(self, "turn", 0) or 0)
                except (TypeError, ValueError):
                    turn_value = 0
                current_player = getattr(self, "get_current_player", lambda: None)()
                turn_owner_id = str(getattr(current_player, "id", "") or "")
                source_id = str(get_entity_id(attacker_root) or "")
                queue = getattr(self, "decision_queue", None)

                from ..utility.aura_utils import unit_within_range_of_unit

                for spec in list(prophet_specs or []):
                    try:
                        range_inches = float(spec.get("range", 9) or 9)
                    except (TypeError, ValueError):
                        range_inches = 9.0
                    if range_inches <= 0.0:
                        range_inches = 9.0
                    ability_name = str(spec.get("source", "") or "Prophet of Destruction").strip() or "Prophet of Destruction"

                    seen_ids: set[str] = set()
                    candidates: list[object] = []
                    for maybe_unit in list(getattr(attacker_army, "units", []) or []):
                        if maybe_unit is None:
                            continue
                        try:
                            candidate_root = maybe_unit.get_attached_unit_root()
                        except Exception:
                            candidate_root = maybe_unit
                        if candidate_root is None:
                            continue
                        candidate_id = str(get_entity_id(candidate_root) or "")
                        if not candidate_id or candidate_id in seen_ids:
                            continue
                        seen_ids.add(candidate_id)
                        if source_id and candidate_id == source_id:
                            continue
                        if not bool(getattr(self, "_unit_on_battlefield_for_reposition", lambda _u: False)(candidate_root)):
                            continue
                        has_any_keyword = getattr(candidate_root, "has_any_keyword", None)
                        if not callable(has_any_keyword) or not bool(has_any_keyword("DESTROYER CULT")):
                            continue
                        if not bool(
                            unit_within_range_of_unit(
                                attacker_root,
                                candidate_root,
                                float(range_inches),
                                use_attached_aggregate=True,
                            )
                        ):
                            continue
                        candidates.append(candidate_root)
                    if not candidates:
                        continue

                    candidates = sorted(candidates, key=lambda value: str(get_entity_id(value) or ""))
                    candidate_ids = [str(get_entity_id(value) or "") for value in list(candidates or []) if str(get_entity_id(value) or "")]
                    if not candidate_ids:
                        continue

                    has_pending = False
                    if queue is not None and hasattr(queue, "list"):
                        for req in list(queue.list() or []):
                            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                                continue
                            req_ctx = dict(getattr(req, "context", {}) or {})
                            if str(req_ctx.get("ability", "") or "") != "prophet_of_destruction_target":
                                continue
                            if str(req_ctx.get("source_unit_id", "") or "") != source_id:
                                continue
                            if str(req_ctx.get("destroyed_unit_id", "") or "") != destroyed_unit_id:
                                continue
                            if int(req_ctx.get("turn", turn_value) or turn_value) != int(turn_value):
                                continue
                            if str(req_ctx.get("expires_phase", "") or "") != phase_name:
                                continue
                            has_pending = True
                            break
                    if has_pending:
                        continue

                    options = [
                        DecisionOption.create(
                            str(getattr(candidate, "name", "Unit") or "Unit"),
                            payload={
                                "source_unit_id": source_id,
                                "target_unit_id": str(get_entity_id(candidate) or ""),
                            },
                        )
                        for candidate in list(candidates or [])
                    ]
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_QUARRY,
                        f"{ability_name}: select one other friendly DESTROYER CULT unit within {int(range_inches)}\".",
                        player_id=getattr(attacker_player, "id", None),
                        options=options,
                        context={
                            "ability": "prophet_of_destruction_target",
                            "ability_name": ability_name,
                            "phase": phase_name or "Current phase",
                            "source_unit_id": source_id,
                            "destroyed_unit_id": destroyed_unit_id,
                            "candidate_unit_ids": list(candidate_ids),
                            "range": float(range_inches),
                            "turn_owner_id": str(turn_owner_id or ""),
                            "turn": int(turn_value),
                            "expires_phase": phase_name,
                        },
                    )
                    self.request_decision(request)

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

                if spec.get("type") == "objective_control_bonus_on_destroy":
                    self._apply_kill_reward_objective_control_bonus(
                        attacker_unit=destroyed_by_unit,
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
            if bool(getattr(self, "is_authoritative", True)) and br == 1:
                if getattr(mgr, "is_carnival_of_excess", lambda: False)():
                    queue = getattr(self, "decision_queue", None)
                    pending = list(queue.list() or []) if queue is not None else []

                    def _has_pending_possessed_blade_choice(model_id: str) -> bool:
                        for req in pending:
                            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                                continue
                            ctx = dict(getattr(req, "context", {}) or {})
                            if str(ctx.get("ability", "") or "") != "possessed_blade":
                                continue
                            if str(ctx.get("model_id", "") or "") != str(model_id):
                                continue
                            return True
                        return False

                    units = list(getattr(army, "units", []) or []) if army is not None else []
                    try:
                        units = sorted(units, key=lambda u: str(get_entity_id(u) or ""))
                    except Exception:
                        units = list(units)
                    for unit in units:
                        sr = getattr(unit, "special_rules", None)
                        if not isinstance(sr, dict) or not sr.get("enhancement_possessed_blade"):
                            continue
                        selected_weapon = str(sr.get("enhancement_possessed_blade_weapon_name", "") or "").strip()
                        if selected_weapon:
                            continue
                        bearer = getattr(unit, "_get_enhancement_bearer_model", lambda: None)()
                        if bearer is None or not bool(getattr(bearer, "is_alive", True)):
                            continue
                        unit_id = str(get_entity_id(unit) or "")
                        model_id = str(get_entity_id(bearer) or "")
                        if not unit_id or not model_id:
                            continue
                        if _has_pending_possessed_blade_choice(model_id):
                            continue
                        weapon_names: list[str] = []
                        for wargear in list(getattr(bearer, "wargear", []) or []):
                            if wargear is None:
                                continue
                            is_melee = bool(getattr(wargear, "is_melee", lambda: False)())
                            if not is_melee:
                                continue
                            weapon_name = str(getattr(wargear, "name", "") or "").strip()
                            if weapon_name and weapon_name not in weapon_names:
                                weapon_names.append(weapon_name)
                        if not weapon_names:
                            continue
                        weapon_names.sort(key=lambda name: name.lower())
                        options = [
                            DecisionOption.create(
                                weapon_name,
                                payload={
                                    "weapon_name": weapon_name,
                                    "unit_id": unit_id,
                                    "model_id": model_id,
                                },
                            )
                            for weapon_name in weapon_names
                        ]
                        request = DecisionRequest.create(
                            DECISION_CHOOSE_QUARRY,
                            "Possessed Blade: select one melee weapon equipped by the bearer.",
                            player_id=player.id,
                            options=options,
                            context={
                                "ability": "possessed_blade",
                                "ability_name": "Possessed Blade",
                                "phase": "Start of battle",
                                "unit_id": unit_id,
                                "model_id": model_id,
                            },
                        )
                        self.request_decision(request)
                        pending.append(request)

            if getattr(mgr, "is_coterie_of_conceited", lambda: False)():
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

    def _on_battle_round_started_adeptus_custodes(self, game=None, battle_round: int = 0, **_kwargs) -> None:
        br = int(battle_round or getattr(self, "turn", 0) or 0)
        if br <= 0:
            return
        for player in list(getattr(self, "players", []) or []):
            army = self._get_player_army(player)
            if army is None:
                continue
            mgr = getattr(army, "adeptus_custodes_detachments", None)
            on_start = getattr(mgr, "on_battle_round_start", None) if mgr is not None else None
            if callable(on_start):
                on_start(br, game=self)

    def _on_battle_round_started_drukhari(self, game=None, battle_round: int = 0, **_kwargs) -> None:
        br = int(battle_round or getattr(self, "turn", 0) or 0)
        if br <= 0:
            return
        for player in list(getattr(self, "players", []) or []):
            army = self._get_player_army(player)
            if army is None:
                continue
            mgr = getattr(army, "drukhari_detachments", None)
            on_start = getattr(mgr, "on_battle_round_start", None) if mgr is not None else None
            if callable(on_start):
                on_start(battle_round=br, game=self, player=player)

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

    def _on_battle_round_started_enhancement_start_of_battle_rolls(
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
        from ..rules.enhancement import resolve_enhancement_start_of_battle_roll_specs
        from ..utility.event_bus import append_action, append_dice

        for player in list(getattr(self, "players", []) or []):
            army = self._get_player_army(player)
            if army is None:
                continue
            seen_roots: set[str] = set()
            roots: list[Unit] = []
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
                root_id = str(get_entity_id(root) or "")
                if not root_id or root_id in seen_roots:
                    continue
                seen_roots.add(root_id)
                roots.append(root)
            roots.sort(key=lambda unit: str(get_entity_id(unit) or ""))
            for root in list(roots or []):
                with game_context(self):
                    outcomes = list(resolve_enhancement_start_of_battle_roll_specs(root, player=player, game=self) or [])
                for outcome in list(outcomes or []):
                    if not bool(outcome.get("triggered", False)):
                        continue
                    source_name = str(outcome.get("source", "") or "Enhancement").strip() or "Enhancement"
                    roll_expr = str(outcome.get("roll_expr", "") or "").strip().upper()
                    roll = int(outcome.get("roll", 0) or 0)
                    branch_label = str(outcome.get("branch_label", "") or "").strip()
                    append_dice(player, f"{source_name}: rolled {roll_expr} -> {int(roll)}.")
                    if bool(outcome.get("applied", False)) and branch_label:
                        append_action(
                            player,
                            f"{source_name}: {getattr(root, 'name', 'Unit')} gains {branch_label} until the end of the battle.",
                        )
                    elif branch_label:
                        append_action(
                            player,
                            f"{source_name}: {getattr(root, 'name', 'Unit')} rolled {branch_label}, but the effect was not applied.",
                        )

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

    def _alive_model_wounds_total(self, unit) -> int:
        if unit is None:
            return 0
        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        total = 0
        for model in list(models or []):
            if model is None:
                continue
            alive_attr = getattr(model, "is_alive", True)
            alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not alive:
                continue
            try:
                wounds = int(getattr(model, "wounds", 0) or 0)
            except Exception:
                wounds = 0
            total += max(0, int(wounds))
        return int(total)

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
            if not isinstance(sr, dict):
                continue
            has_rise_to_challenge = bool(sr.get("enhancement_rise_to_challenge"))
            has_sanguinius_grace = bool(sr.get("enhancement_sanguinius_grace"))
            if not (has_rise_to_challenge or has_sanguinius_grace):
                continue
            if has_rise_to_challenge and bool(sr.get("enhancement_rise_to_challenge_used")):
                continue
            if has_sanguinius_grace and bool(sr.get("enhancement_sanguinius_grace_used")):
                continue
            if has_sanguinius_grace:
                once_key = str(
                    sr.get("enhancement_sanguinius_grace_once_key", "sanguinius_grace")
                    or "sanguinius_grace"
                ).strip().lower()
                if once_key and bool(getattr(unit, "has_used_unit_once_per_battle", lambda _k: False)(once_key)):
                    continue
            try:
                min_enemy_models = int(
                    sr.get("enhancement_sanguinius_grace_min_enemy_models_in_engagement_range", 3)
                    or 3
                )
            except Exception:
                min_enemy_models = 3
            min_enemy_models = int(max(1, min_enemy_models))
            try:
                bearer_id = str(
                    sr.get("enhancement_sanguinius_grace_bearer_model_id", "")
                    or sr.get("enhancement_bearer_model_id", "")
                    or ""
                ).strip()
            except Exception:
                bearer_id = ""
            if has_sanguinius_grace and not bearer_id:
                get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
                bearer_model = get_bearer() if callable(get_bearer) else None
                if bearer_model is not None:
                    bearer_id = str(get_entity_id(bearer_model) or "").strip()
            if has_rise_to_challenge and bool(sr.get("enhancement_rise_to_challenge_used")):
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
            if bearer_id:
                for model in models:
                    if str(get_entity_id(model) or "") != bearer_id:
                        continue
                    alive = getattr(model, "is_alive", True)
                    if callable(alive):
                        alive = alive()
                    if alive:
                        bearer = model
                        break
            for model in models:
                if bearer is not None:
                    break
                alive = getattr(model, "is_alive", True)
                if callable(alive):
                    alive = alive()
                if alive:
                    bearer = model
                    break
            if bearer is None:
                continue
            if self._count_enemy_models_in_engagement_range(unit, bearer) < int(min_enemy_models):
                continue
            candidates.append(unit)
        return candidates

    def _on_unit_destroyed_power_from_pain(self, unit=None, destroyed_by_unit=None, **_kwargs) -> None:
        if unit is None:
            return
        destroyed_by_model = _kwargs.get("destroyed_by_model")
        last_model = _kwargs.get("last_model")
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Power from Pain requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Power from Pain requires an army for {p.name}.")
            mgr = getattr(army, "power_from_pain", None)
            if mgr is None:
                pass
            else:
                mgr.on_enemy_unit_destroyed(unit, destroyed_by_unit=destroyed_by_unit)
            detachment_mgr = getattr(army, "drukhari_detachments", None)
            if detachment_mgr is None:
                continue
            on_destroyed = getattr(detachment_mgr, "on_enemy_unit_destroyed", None)
            if callable(on_destroyed):
                on_destroyed(
                    unit,
                    destroyed_by_unit=destroyed_by_unit,
                    destroyed_by_model=destroyed_by_model,
                    game=self,
                )
            on_friendly_destroyed = getattr(detachment_mgr, "on_friendly_unit_destroyed", None)
            if callable(on_friendly_destroyed):
                on_friendly_destroyed(
                    unit,
                    last_model=last_model,
                    game=self,
                )

    def _on_battle_shock_test_resolved_power_from_pain(self, unit=None, passed: bool = False, **_kwargs) -> None:
        del _kwargs
        if unit is None:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Power from Pain requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Power from Pain requires an army for {p.name}.")
            mgr = getattr(army, "power_from_pain", None)
            if mgr is not None and not bool(passed):
                mgr.on_enemy_battle_shock_failed(unit)
            detachment_mgr = getattr(army, "drukhari_detachments", None)
            if detachment_mgr is None:
                continue
            on_resolved = getattr(detachment_mgr, "on_battle_shock_test_resolved", None)
            if callable(on_resolved):
                on_resolved(unit, passed=bool(passed), game=self)

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
        if unit is None:
            return
        try:
            destroyed_root = unit.get_attached_unit_root()
        except Exception:
            destroyed_root = unit
        if destroyed_root is None:
            return
        army = destroyed_root.get_parent_army()
        if army is None:
            return
        owner = getattr(army, "player", None)
        if owner is None:
            return
        current_player = self.get_current_player()
        if current_player is owner:
            return
        current_player_id = getattr(current_player, "id", None)
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()

        # Devoted of Ynnead (Strength from Death): track Lethal Intent candidates
        # during the opponent's Shooting phase when a friendly YNNARI unit is destroyed.
        if phase_name == "SHOOTING_PHASE":
            ae_mgr = getattr(army, "aeldari_detachments", None)
            if ae_mgr is not None and bool(getattr(ae_mgr, "is_devoted_of_ynnead", lambda: False)()):
                destroyed_counts_as_ynnari = bool(
                    getattr(ae_mgr, "devoted_of_ynnead_unit_counts_as_ynnari", lambda *_a, **_k: False)(destroyed_root)
                )
                if destroyed_counts_as_ynnari:
                    candidate_ids: list[str] = []
                    seen_candidate_ids: set[str] = set()
                    for candidate in list(getattr(army, "units", []) or []):
                        if candidate is None:
                            continue
                        try:
                            root = candidate.get_attached_unit_root()
                        except Exception:
                            root = candidate
                        if root is None or root is destroyed_root:
                            continue
                        rid = str(get_entity_id(root) or "")
                        if not rid or rid in seen_candidate_ids:
                            continue
                        seen_candidate_ids.add(rid)
                        if not bool(getattr(ae_mgr, "devoted_of_ynnead_unit_counts_as_ynnari", lambda *_a, **_k: False)(root)):
                            continue
                        if not bool(getattr(ae_mgr, "devoted_of_ynnead_is_infantry_or_mounted", lambda *_a, **_k: False)(root)):
                            continue
                        try:
                            if not root.is_alive() or not bool(getattr(root, "deployed", False)):
                                continue
                        except Exception:
                            continue
                        try:
                            if root.is_in_reserves() or root.is_embarked:
                                continue
                        except Exception:
                            pass
                        in_range = False
                        if last_model is not None and bool(getattr(last_model, "model_base", None) is not None):
                            try:
                                in_range = bool(root._model_within_range_of_unit(last_model, root, 6.0))
                            except Exception:
                                in_range = False
                        if not in_range:
                            try:
                                from ..utility.aura_utils import unit_within_range_of_unit

                                in_range = bool(
                                    unit_within_range_of_unit(root, destroyed_root, 6.0, use_attached_aggregate=True)
                                )
                            except Exception:
                                in_range = False
                        if not in_range:
                            continue
                        candidate_ids.append(rid)
                    if candidate_ids:
                        getattr(ae_mgr, "record_devoted_of_ynnead_lethal_intent_candidates", lambda **_kw: None)(
                            game=self,
                            candidate_unit_ids=sorted(set(candidate_ids)),
                            turn_owner_id=str(current_player_id or ""),
                            phase_name=phase_name,
                        )

        pos = None
        if hasattr(last_model, "get_location"):
            pos = last_model.get_location()
        if pos is None:
            try:
                pos = destroyed_root.position
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
            if root is destroyed_root:
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
                    if not root._unit_matches_keyword_phrase(destroyed_root, keyword, use_effective=False):
                        continue
                except Exception:
                    continue
            placement = self._find_closest_valid_reposition_position(root, pos, game_map=game_map)
            if placement is None:
                continue
            unit_id = maybe_entity_id(root)
            destroyed_unit_id = maybe_entity_id(destroyed_root)
            ability_name = str(ability.get("name") or "Reposition").strip()
            ctx = {
                "ability_name": ability_name,
                "phase": "Opponent's turn",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "destroyed_unit": getattr(destroyed_root, "name", "") or "",
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
        seen_armies: set[str] = set()
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            army = self._get_player_army(player)
            if army is None:
                continue
            army_id = str(get_entity_id(army) or "")
            if army_id and army_id in seen_armies:
                continue
            if army_id:
                seen_armies.add(army_id)
            mgr = getattr(army, "acts_of_faith", None)
            if mgr is None:
                continue
            mgr.on_unit_destroyed(
                unit,
                game=self,
                game_map=self.map,
                last_model=last_model,
                destroyed_by_unit=_kwargs.get("destroyed_by_unit"),
                destroyed_by_model=_kwargs.get("destroyed_by_model"),
                destroyed_by_weapon_profile=_kwargs.get("destroyed_by_weapon_profile"),
            )

    def _on_fight_unit_selected_acts_of_faith(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        army = unit.get_parent_army()
        mgr = getattr(army, "acts_of_faith", None) if army is not None else None
        if mgr is None:
            return
        on_select = getattr(mgr, "on_fight_unit_selected", None)
        if not callable(on_select):
            return
        on_select(unit, game=self, selecting_player=selecting_player)

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
        depth = int(getattr(self, "_command_context_depth", 0) or 0)
        self._command_context_depth = depth + 1

    def _exit_command_context(self) -> None:
        depth = int(getattr(self, "_command_context_depth", 0) or 0)
        self._command_context_depth = max(0, depth - 1)

    def in_command_context(self) -> bool:
        return int(getattr(self, "_command_context_depth", 0) or 0) > 0

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
        if "rules_bundle" not in ctx:
            ctx["rules_bundle"] = dict(ruleset_ctx or {})
        elif dict(ctx.get("rules_bundle", {}) or {}) != dict(ruleset_ctx or {}):
            raise ValueError("Decision context rules_bundle mismatch with game rules bundle.")
        for key, value in ruleset_ctx.items():
            if key not in ctx:
                ctx[key] = value
            elif ctx.get(key) != value:
                raise ValueError(f"Decision context ruleset mismatch for {key}: {ctx.get(key)} != {value}")
        rules_bundle = getattr(self, "ruleset_bundle", None)
        rules_bundle_id = str(getattr(rules_bundle, "rules_bundle_id", "") or "")
        if rules_bundle_id and "rules_bundle_id" not in ctx:
            ctx["rules_bundle_id"] = rules_bundle_id
        descriptor_bundle = compile_descriptor_bundle(self)
        if "descriptor_ids" not in ctx or not isinstance(ctx.get("descriptor_ids"), dict):
            ctx["descriptor_ids"] = descriptor_bundle.descriptor_ids()
        else:
            descriptor_ids = dict(ctx.get("descriptor_ids", {}) or {})
            expected_descriptor_ids = descriptor_bundle.descriptor_ids()
            for key, value in expected_descriptor_ids.items():
                existing_value = descriptor_ids.get(key)
                if existing_value in (None, "", []):
                    descriptor_ids[key] = value
            ctx["descriptor_ids"] = descriptor_ids
        if "descriptor_bundle_id" not in ctx:
            ctx["descriptor_bundle_id"] = str(descriptor_bundle.bundle_id)
        ctx = ensure_version_adapter_boundary(ctx)
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
            if "score_window_state" not in ctx:
                ctx["score_window_state"] = {
                    "windows": [window.to_dict() for window in list(plan.scoring_windows or [])],
                    "battle_round": int(getattr(plan, "battle_round", 0) or 0),
                }
            if "opportunity_catalog" not in ctx:
                ctx["opportunity_catalog"] = {
                    "priority": [opp.to_dict() for opp in list(plan.priority_opportunities or [])],
                    "denial": [opp.to_dict() for opp in list(plan.denial_opportunities or [])],
                }
            if "mission_state" not in ctx:
                ctx["mission_state"] = {
                    "selected_mission_info": dict(getattr(self, "selected_mission_info", {}) or {}),
                    "secondary_mission_mode": str(getattr(self, "secondary_mission_mode", "") or ""),
                }
            if "terrain_state_summary" not in ctx:
                map_obj = getattr(self, "map", None)
                terrain_features = list(getattr(map_obj, "terrain_features", []) or [])
                terrain_ids = sorted(str(getattr(feature, "id", "") or "") for feature in terrain_features)
                ctx["terrain_state_summary"] = {
                    "terrain_count": int(len(terrain_features)),
                    "terrain_ids": terrain_ids,
                }
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
        if request.decision_type in (
            DECISION_CHOOSE_DEPLOYMENT_ZONE,
            DECISION_SELECT_NEXT_DEPLOY_UNIT,
            DECISION_DECLARE_RESERVES,
            DECISION_SCOUT_MOVE,
        ):
            deployment_intent = DeploymentIntent.from_context(ctx)
            ctx["deployment_intent"] = deployment_intent.to_dict()
            request.context = ctx
            deployment_candidates, deployment_mask, solver_ms, fallback_mode = generate_deployment_candidates(
                self,
                request,
                deployment_intent,
            )
            if deployment_candidates:
                normalized_candidates: list[CandidateAction] = []
                for candidate in list(deployment_candidates or []):
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
                request.mask = [bool(value) for value in list(deployment_mask or [])]
                if len(request.mask) != len(request.candidates):
                    request.mask = [True] * len(request.candidates)
                request.mask_reasons = [None if val else "masked_as_illegal" for val in request.mask]
        if request.decision_type == DECISION_MOVE_UNIT:
            placement_kind = str(ctx.get("placement_kind", "") or "").strip().lower()
            if placement_kind == "deployment":
                deployment_intent = DeploymentIntent.from_context(ctx)
                ctx["deployment_intent"] = deployment_intent.to_dict()
                request.context = ctx
                deployment_candidates, deployment_mask, solver_ms, fallback_mode = generate_deployment_candidates(
                    self,
                    request,
                    deployment_intent,
                )
                if deployment_candidates:
                    normalized_candidates: list[CandidateAction] = []
                    for candidate in list(deployment_candidates or []):
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
                    request.mask = [bool(value) for value in list(deployment_mask or [])]
                    if len(request.mask) != len(request.candidates):
                        request.mask = [True] * len(request.candidates)
                    request.mask_reasons = [None if val else "masked_as_illegal" for val in request.mask]
            else:
                # Placement-style move decisions are resolved via explicit model_positions payloads.
                # Skip generic move candidate generation for these to avoid expensive unused solver work.
                if placement_kind not in ("advance_redeploy_9h", "normal_move_redeploy_9h"):
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
        semantic_rules_bundle_id = str(ctx.get("rules_bundle_id", "") or "")
        ensure_candidate_semantic_metadata(
            request,
            rules_bundle_id=semantic_rules_bundle_id,
        )
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
        if not bool(getattr(self, "is_authoritative", True)):
            raise RuntimeError("Mission selection requests can only be queued by the authoritative game.")
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for pending in list(queue.list() or []):
                if str(getattr(pending, "decision_type", "")) == DECISION_CHOOSE_MISSION:
                    return pending
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
                            logger.info(f"{root.name} must start in Reserves")
                        decision = "reserves"
                except Exception:
                    pass
                applied_decision = decision
                ae_mgr = getattr(army, "aeldari_detachments", None)
                status_fn = getattr(ae_mgr, "ride_the_wind_reserve_status_for_decision", None) if ae_mgr is not None else None
                if callable(status_fn):
                    applied_decision = str(status_fn(root, decision) or decision)
                started = applied_decision in ("reserves", "strategic_reserves")
                if applied_decision == "deploy":
                    root.set_reserve_status("deployed")
                    root.deployed = False
                elif applied_decision == "reserves":
                    root.set_reserve_status("reserves")
                    root.deployed = True
                elif applied_decision == "strategic_reserves":
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
                if is_transport and must_reserves and applied_decision in ("reserves", "strategic_reserves"):
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
        accepted = bool(getattr(apply_result, "ok", False))
        if apply_result.ok:
            self.decision_queue.pop(result.decision_id)
            self.event_system.publish("decision_resolved", result=result, request=request, game=self)
            self._maybe_queue_reactive_move_followup(request, result)
            self._maybe_queue_setup_reactive_followup(request, result)
            self._maybe_queue_reverberating_summons_followup(request, result)
            self._maybe_apply_optional_ability_confirmation(request, result)
            self._maybe_queue_bodyguard_return_followup(request, result)
            self._maybe_apply_choice_samples_followup(request, result)
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
                logger.error(f"ERROR: Decision rejected ({dtype}) for player {pid}: {err_list}")
            except Exception:
                logger.exception(f"ERROR: Unexpected Decision Failure for {request} with {apply_result}")

        self.event_system.publish(
            "decision_settled",
            result=result,
            request=request,
            game=self,
            apply_result=apply_result,
            accepted=accepted,
        )
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
                            from .decision_kinds import (
                                DECISION_CHOOSE_DEPLOYMENT_ZONE,
                                DECISION_MOVE_UNIT,
                                DECISION_SELECT_NEXT_DEPLOY_UNIT,
                            )
                            decision_type = getattr(req, "decision_type", None)
                            if decision_type not in (
                                DECISION_MOVE_UNIT,
                                DECISION_CHOOSE_DEPLOYMENT_ZONE,
                                DECISION_SELECT_NEXT_DEPLOY_UNIT,
                            ):
                                pid = None
                            elif decision_type == DECISION_MOVE_UNIT:
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
        if not self.in_command_context():
            player_id = None
            try:
                player_id = self.get_current_player().id
            except Exception:
                player_id = None
            cmd = GameCommand.create(CMD_START_COMMAND_PHASE, player_id=player_id)
            self.apply_command(cmd)
            return
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
        self._maybe_prompt_csm_tyrannical_motivation()
        self._maybe_prompt_csm_vendetta()
        self._maybe_prompt_csm_focus_of_hatred()
        self._maybe_prompt_csm_soul_link()
        self._maybe_prompt_csm_forges_blessing()
        self._maybe_prompt_csm_experimental_augmentations()
        self._refresh_csm_tyrannical_motivation_phase_state()

        # Space Marines: Oath of Moment target selection at the start of your Command phase.
        mgr = getattr(army, "oath_of_moment", None)
        if mgr is not None:
            mgr.on_command_phase_start(game=self, player=current_player)
            self.event_system.publish("oath_of_moment_prompt", player=current_player, game=self)

        # Space Marines: Combat Doctrines selection at the start of your Command phase.
        mgr = getattr(army, "combat_doctrines", None)
        if mgr is not None:
            self._maybe_prompt_combat_doctrines()

        # Space Marines: Angelic Legacy selection at the start of the first battle round.
        sm_mgr = getattr(army, "space_marines_detachments", None)
        if sm_mgr is not None:
            clear_mission_tactic = getattr(sm_mgr, "clear_active_mission_tactic", None)
            if callable(clear_mission_tactic):
                clear_mission_tactic(game=self)
            clear_grim_resolve = getattr(sm_mgr, "clear_grim_resolve_bonus", None)
            if callable(clear_grim_resolve):
                clear_grim_resolve(game=self)
            self._maybe_prompt_mission_tactics()
            self._maybe_prompt_angelic_legacy()
            self._maybe_prompt_grim_resolve()

        # Thousand Sons: Grand Coven (Kindred Sorcery) selection at the start of your Command phase.
        mgr = getattr(army, "thousand_sons_detachments", None)
        if mgr is not None:
            self._maybe_prompt_grand_coven()

        # Drukhari: Combat Drugs selection at the start of your Command phase.
        mgr = getattr(army, "drukhari_detachments", None)
        if mgr is not None:
            on_start = getattr(mgr, "on_command_phase_start", None)
            if callable(on_start):
                on_start(game=self, player=current_player)
            self._maybe_prompt_combat_drugs()

        # Chaos Knights: command-phase hooks (e.g., Marked Prey, Malefic Surge).
        mgr = getattr(army, "chaos_knights_detachments", None)
        if mgr is not None and hasattr(mgr, "on_command_phase_start"):
            mgr.on_command_phase_start(game=self, player=current_player)

        # Imperial Knights detachments: command-phase hooks (e.g., Questor Forgepact Sacristan Pledge).
        mgr = getattr(army, "imperial_knights_detachments", None)
        if mgr is not None and hasattr(mgr, "on_command_phase_start"):
            mgr.on_command_phase_start(game=self, player=current_player)

        # Imperial Agents detachments: command-phase hooks (e.g., Imperialis Fleet At all Costs).
        mgr = getattr(army, "imperial_agents_detachments", None)
        if mgr is not None and hasattr(mgr, "on_command_phase_start"):
            mgr.on_command_phase_start(game=self, player=current_player)

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
        # Necrons datasheets: command-phase optional model replacement (Surrogate Hosts).
        self._on_phase_start_surrogate_hosts(player=current_player, phase=self.phase)

        # Adeptus Custodes detachments: command-phase target selection (e.g. Auric Champions).
        mgr = getattr(army, "adeptus_custodes_detachments", None)
        if mgr is not None and hasattr(mgr, "on_command_phase_start"):
            mgr.on_command_phase_start(game=self, player=current_player)

        # Orks detachments: command-phase state resets and mandatory prey selection (Da Big Hunt).
        mgr = getattr(army, "orks_detachments", None)
        if mgr is not None and hasattr(mgr, "on_command_phase_start"):
            mgr.on_command_phase_start(game=self, player=current_player)
            build_prey_request = getattr(mgr, "build_da_big_hunt_prey_request", None)
            if callable(build_prey_request):
                prey_request = build_prey_request(game=self, player=current_player)
                if prey_request is not None:
                    self.request_decision(prey_request)

        # Orks: Waaagh! (expires at your next Command phase; prompt to call).
        mgr = getattr(army, "waaagh", None)
        if mgr is not None:
            mgr.on_command_phase_start(game=self, player=current_player)

        # World Eaters: Blood Tithe spending at the start of your Command phase.
        mgr = getattr(army, "world_eaters_detachments", None)
        if mgr is not None and hasattr(mgr, "on_command_phase_start"):
            mgr.on_command_phase_start(game=self, player=current_player)

        # Death Guard detachments: command-phase hooks (e.g., Numberless Horde).
        mgr = getattr(army, "death_guard_detachments", None)
        if mgr is not None and hasattr(mgr, "on_command_phase_start"):
            mgr.on_command_phase_start(game=self, player=current_player)

        # Adeptus Mechanicus: Rad-bombardment Fallout (Rad-Zone Corps).
        mgr = getattr(army, "adeptus_mechanicus_detachments", None)
        if mgr is not None and hasattr(mgr, "on_command_phase_start"):
            mgr.on_command_phase_start(game=self, player=current_player)

        # Adepta Sororitas: Champions of Faith (Righteous Purpose) command-phase selection.
        mgr = getattr(army, "adepta_sororitas_detachments", None)
        if mgr is not None and hasattr(mgr, "on_command_phase_start"):
            mgr.on_command_phase_start(game=self, player=current_player)
        mgr = getattr(army, "acts_of_faith", None)
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
        self._apply_command_phase_regain_wounds(current_player, timing="start")

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
            logger.info(f"{current_player.name} active Secondaries: {', '.join(after)}")

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
            is_below_half = False
            fn = getattr(unit, "is_below_half_strength", None)
            if callable(fn):
                try:
                    is_below_half = bool(fn())
                except Exception:
                    is_below_half = False
            if is_below_half:
                logger.warning(f"WARN: {unit.name} is below half strength - taking Battle-Shock test")
                unit.take_battle_shock_test(self.turn)
                uid = get_entity_id(unit)
                tested_ids.add(uid)

        # Space Marines (The Angelic Host): Visage of Death forces additional Battle-shock tests
        # for enemy non-MONSTER/non-VEHICLE units within Engagement Range of the bearer model.
        self._apply_space_marines_the_angelic_host_visage_of_death_forced_tests(current_player, tested_ids)
        # Chaos Space Marines terror detachments: Dread Talons/Nightmare Hunt force tests for
        # in-range enemy units and mark affected units to suppress additional tests this phase.
        self._apply_csm_dread_talons_terror_descends_forced_tests(current_player, tested_ids)
        # Belakor: Pall of Despair can force additional tests for eligible enemy units.
        self._apply_pall_of_despair_forced_tests(current_player, tested_ids)
        # Chaos Knights: Dismay can force additional tests for eligible enemy units.
        self._apply_harbingers_dismay_forced_tests(current_player, tested_ids)
        # Death Guard (Tallyband Summoners): Entropic Knell can force additional tests.
        self._apply_death_guard_tallyband_entropic_knell_forced_tests(current_player, tested_ids)
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
                    logger.info(f"{current_player.name} scored {added} VP from Primary: {primary.name}")

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
        sycophantic_active_fn = getattr(charging_unit, "_carnival_sycophantic_surge_active_for_charge", None)
        sycophantic_target_fn = getattr(charging_unit, "_carnival_sycophantic_target_condition_met", None)
        if callable(sycophantic_active_fn) and bool(sycophantic_active_fn(game=self)):
            if not callable(sycophantic_target_fn):
                return None
            if not any(bool(sycophantic_target_fn(tgt, self)) for tgt in list(targets or [])):
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

        try:
            charge_root = charging_unit.get_attached_unit_root()
        except Exception:
            charge_root = charging_unit
        root_sr = getattr(charge_root, "special_rules", None)
        if isinstance(root_sr, dict) and bool(root_sr.get("enhancement_our_time_is_nigh")):
            once_key = str(root_sr.get("enhancement_our_time_is_nigh_once_key", "our_time_is_nigh") or "our_time_is_nigh").strip().lower()
            has_used = getattr(charge_root, "has_used_unit_once_per_battle", None)
            already_used = bool(callable(has_used) and has_used(once_key))
            if not already_used and not bool(root_sr.get("enhancement_our_time_is_nigh_active")):
                owner_player = getattr(army, "player", None) if army is not None else None
                current_player = self.get_current_player()
                phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() or "CHARGE_PHASE"
                phase_owner_id = str(getattr(current_player, "id", "") or "")
                charge_root_id = str(get_entity_id(charge_root) or "")
                self._queue_optional_ability_confirmation(
                    player=owner_player,
                    ability_key="our_time_is_nigh",
                    ability_name="Our Time Is Nigh",
                    message="Use Our Time Is Nigh for +2 to Charge rolls made for this unit until end of phase?",
                    context={
                        "ability_name": "Our Time Is Nigh",
                        "unit_id": charge_root_id,
                        "turn": int(getattr(self, "turn", 0) or 0),
                        "turn_owner_id": phase_owner_id,
                        "phase": phase_name,
                    },
                    payload={
                        "unit_id": charge_root_id,
                        "turn": int(getattr(self, "turn", 0) or 0),
                        "turn_owner_id": phase_owner_id,
                        "phase": phase_name,
                    },
                    instance_key=f"{charge_root_id}:{int(getattr(self, 'turn', 0) or 0)}:{phase_name}:{phase_owner_id}:our_time_is_nigh",
                )

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
        from ..rules.perfectly_adapted import build_perfectly_adapted_reroll_rule
        pa_rule = build_perfectly_adapted_reroll_rule(
            unit=charging_unit,
            game=self,
            roll_type="charge",
        )
        if pa_rule:
            reroll_rules.append(pa_rule)

        from ..engine.roll_utils import command_reroll_available
        from ..engine.roll_explanation import infer_modifier_contributor_type
        command_reroll_ok = command_reroll_available(self, player, roll_type="charge", unit=charging_unit)
        charge_modifiers = list(self._collect_charge_modifiers(charging_unit, target_unit=targets[0]) or [])
        charge_sum_modifier = 0
        charge_modifier_breakdown: list[dict] = []
        for raw_val, raw_source in list(charge_modifiers or []):
            try:
                val = int(raw_val or 0)
            except (TypeError, ValueError):
                continue
            if not val:
                continue
            source = str(raw_source or "Charge roll modifier").strip() or "Charge roll modifier"
            reason = f"{source} ({val:+d})"
            charge_sum_modifier += int(val)
            charge_modifier_breakdown.append(
                {
                    "source": source,
                    "value": int(val),
                    "reason": reason,
                    "contributor_type": infer_modifier_contributor_type(reason=reason, source=source),
                }
            )
        roll_spec = {
            "dice_count": dice_count,
            "faces": 6,
            "reason": f"Charge roll for {charging_unit.name}",
            "roll_type": "charge",
            "unit_id": get_entity_id(charging_unit),
            "target_unit_ids": [get_entity_id(t) for t in targets],
            "handler_key": "charge_roll",
            "charge_spec": {"dice_count": dice_count, "keep_highest": keep_highest},
            "show_sum": True,
            "sum_modifier": int(charge_sum_modifier),
            "sum_modifier_reasons": [str(item.get("reason", "") or "") for item in list(charge_modifier_breakdown)],
            "sum_modifier_breakdown": list(charge_modifier_breakdown),
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

    def roll_blistering_assault_distance(self, unit: 'Unit') -> int:
        """Roll Blistering Assault distance (D6+2)."""
        if unit is None:
            return 0
        from ..utility.dice import get_roll
        base_roll = int(get_roll("D6") or 0)
        max_distance = int(base_roll + 2)
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(player, f"Blistering Assault roll: {int(base_roll or 0)} (move {max_distance}\") for {unit.name}")
        return int(max_distance)

    def roll_aggressive_leader_beast_distance(self, unit: 'Unit') -> int:
        """Roll Aggressive Leader-beast distance (D6)."""
        if unit is None:
            return 0
        from ..utility.dice import get_roll
        base_roll = int(get_roll("D6") or 0)
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(
                player,
                f"Aggressive Leader-beast roll: {int(base_roll or 0)}\" for {unit.name}",
            )
        return int(base_roll or 0)

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
        rule_fn = getattr(unit, "get_horde_move_rule", None)
        rule = rule_fn(game=self) if callable(rule_fn) else None
        if not isinstance(rule, dict):
            rule = {}
        distance_bonus = int(rule.get("distance_bonus", 0) or 0)
        can_reroll = bool(rule.get("distance_reroll"))
        source = str(rule.get("source", "") or "Horde Move").strip() or "Horde Move"
        reroll_used = False
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
        if is_human and can_reroll:
            provider = getattr(getattr(self, "map", None), "roll_reroll_provider", None)
            if callable(provider):
                want = bool(
                    provider(
                        player=player,
                        unit=unit,
                        roll_type="horde_move",
                        value=int(base_roll or 0),
                        dice=[int(base_roll or 0)],
                        allow_reroll=True,
                        source=source,
                    )
                )
                if want:
                    base_roll = int(get_roll("D6") or 0)
                    reroll_used = True
        max_distance = int(base_roll + distance_bonus)
        if player is not None:
            if distance_bonus:
                tag = f"{source} reroll" if reroll_used else f"{source} roll"
                append_dice(player, f"{tag}: {int(base_roll or 0)} (move {int(max_distance or 0)}\") for {unit.name}")
            else:
                tag = f"{source} reroll" if reroll_used else f"{source} roll"
                append_dice(player, f"{tag}: {int(base_roll or 0)}\" for {unit.name}")
        return int(max_distance or 0)

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

        logger.info(f"Charge: {charging_unit.name} charging {target_unit.name}")
        logger.info(f"Charge: Current edge-to-edge distance: {current_distance:.1f}\"")
        logger.info(f"Charge: Distance needed to achieve <= 1\" edge-to-edge: {distance_needed:.1f}\"")
        logger.info(f"Charge: Roll {base_charge_roll} (rolled {individual_dice}) (modified: {charge_roll})")

        # CRITICAL RULE: If charge roll is insufficient, charge fails and no models move
        if charge_roll < distance_needed:
            logger.error(f"Charge failed: roll {charge_roll}\" insufficient to reach within 1\" "
                f"(needed {distance_needed:.1f}\")")
            logger.error("Charge failed: no models move")
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
            logger.error("Charge failed: invalid positions")
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
            logger.error("Charge failed: units are at same position")
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
                    target_unit.round_state.was_charged_this_round = True
                except Exception:
                    pass
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
                charging_unit._apply_charge_end_model_melee_strength_ap_bonuses()
                charging_unit._apply_charge_move_model_weapon_profile_attacks_bonuses()
                charging_unit._apply_charge_move_weapon_keyword_bonuses()
                logger.info(f"Charge successful: {charging_unit.name} achieved {final_distance:.1f}\" "
                    f"edge-to-edge distance with {target_unit.name}")
                return True
            logger.error(f"Charge failed: {charging_unit.name} achieved {final_distance:.1f}\" edge-to-edge "
                f"distance (not <= 1.0\") with {target_unit.name}")
            # CRITICAL: Revert all model positions if charge failed to achieve engagement range
            # This ensures that NO MODELS MOVE when a charge fails
            logger.error("Charge failed: reverting all model positions - no models should move on failed charge")

            # Restore original positions
            for i, original_pos in enumerate(original_model_positions):
                if i < len(charging_unit.models):
                    charging_unit.models[i].set_location(*original_pos)

            # Unit position is now derived from model positions, no need to restore

            return False
        logger.error("Charge failed: could not move unit")
        # CRITICAL: Restore original positions if charge_move failed completely
        logger.error("Charge failed: reverting all model positions - no models should move on failed charge")

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
        modifiers: list[tuple[int, str]] = []

        # Check for charge modifiers from abilities/enhancements.
        sr = getattr(charging_unit, "special_rules", None)
        if isinstance(sr, dict):
            our_time_active = False
            try:
                our_time_bonus = int(sr.get("enhancement_our_time_is_nigh_bonus", 0) or 0)
            except Exception:
                our_time_bonus = 0
            our_time_source = str(sr.get("enhancement_our_time_is_nigh_source", "") or "Our Time Is Nigh").strip() or "Our Time Is Nigh"
            if sr.get("enhancement_our_time_is_nigh_active"):
                our_time_active = True
                expected_phase = str(sr.get("enhancement_our_time_is_nigh_phase", "") or "CHARGE_PHASE").strip().upper()
                expected_owner = str(sr.get("enhancement_our_time_is_nigh_turn_owner", "") or "")
                try:
                    expected_turn = int(sr.get("enhancement_our_time_is_nigh_turn", 0) or 0)
                except Exception:
                    expected_turn = 0
                current_phase = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
                current_turn = int(getattr(self, "turn", 0) or 0)
                current_player = self.get_current_player()
                current_owner = str(getattr(current_player, "id", "") or "")
                if expected_phase and current_phase and expected_phase != current_phase:
                    our_time_active = False
                if expected_owner and current_owner and expected_owner != current_owner:
                    our_time_active = False
                if expected_turn and expected_turn != current_turn:
                    our_time_active = False
                if not our_time_active:
                    for key in (
                        "enhancement_our_time_is_nigh_active",
                        "enhancement_our_time_is_nigh_turn_owner",
                        "enhancement_our_time_is_nigh_turn",
                        "enhancement_our_time_is_nigh_phase",
                        "enhancement_our_time_is_nigh_source",
                    ):
                        sr.pop(key, None)
                    charging_unit.special_rules = sr

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
                target_ids: set[str] = set()
                if target_unit is not None:
                    try:
                        if isinstance(target_unit, (list, tuple, set)):
                            targets_for_filter = [t for t in list(target_unit or []) if t is not None]
                        else:
                            targets_for_filter = [target_unit]
                    except Exception:
                        targets_for_filter = [target_unit]
                    for tgt in list(targets_for_filter or []):
                        try:
                            root = tgt.get_attached_unit_root() if hasattr(tgt, "get_attached_unit_root") else tgt
                        except Exception:
                            root = tgt
                        if root is None:
                            continue
                        try:
                            tid = str(get_entity_id(root) or "")
                        except Exception:
                            tid = ""
                        if tid:
                            target_ids.add(tid)
                for item in extra_list:
                    val = 0
                    source = "Charge roll modifier"
                    if isinstance(item, (list, tuple)) and len(item) >= 1:
                        val = int(item[0] or 0)
                        source = str(item[1] if len(item) > 1 else source)
                    elif isinstance(item, dict):
                        target_filter_ids = {
                            str(v).strip()
                            for v in list(item.get("target_unit_ids", []) or [])
                            if str(v).strip()
                        }
                        if not target_filter_ids:
                            single_target = str(item.get("target_unit_id", "") or "").strip()
                            if single_target:
                                target_filter_ids = {single_target}
                        if target_filter_ids:
                            if not target_ids:
                                continue
                            if not (target_filter_ids & target_ids):
                                continue
                        val = int(item.get("value", 0) or 0)
                        source = str(item.get("source", "") or source)
                    else:
                        val = int(item or 0)
                    normalized_source = str(source or "").replace("\u2019", "'").strip().lower()
                    if "our time is nigh" in normalized_source:
                        continue
                    if val:
                        modifiers.append((val, source))

            battleline_specs = list(sr.get("admech_optimised_gait_battleline_bonus", []) or [])
            if battleline_specs:
                within_fn = getattr(charging_unit, "_within_friendly_adeptus_mechanicus_battleline", None)
                seen_specs: set[tuple[str, int, int]] = set()
                for spec in battleline_specs:
                    if not isinstance(spec, dict):
                        continue
                    source = str(spec.get("source", "") or "Optimised Gait").strip() or "Optimised Gait"
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    try:
                        bonus_value = int(spec.get("value", 0) or 0)
                    except Exception:
                        bonus_value = 0
                    if range_value <= 0 or bonus_value <= 0:
                        continue
                    key = (source.lower(), int(range_value), int(bonus_value))
                    if key in seen_specs:
                        continue
                    seen_specs.add(key)
                    applies = False
                    if callable(within_fn):
                        try:
                            applies = bool(
                                within_fn(
                                    range_value=float(range_value),
                                    game_map=getattr(self, "map", None),
                                    include_self=False,
                                )
                            )
                        except Exception:
                            applies = False
                    if not applies:
                        continue
                    modifiers.append(
                        (
                            int(bonus_value),
                            f"{source}: +{int(bonus_value)} while within {int(range_value)}\" of friendly ADEPTUS MECHANICUS BATTLELINE",
                        )
                    )

            if our_time_active and our_time_bonus:
                modifiers.append((int(our_time_bonus), our_time_source))

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

        try:
            army = charging_unit.get_parent_army()
        except Exception:
            army = None
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        desperate_charge_bonus_fn = getattr(csm_mgr, "desperate_devotion_charge_roll_bonus", None) if csm_mgr is not None else None
        if callable(desperate_charge_bonus_fn):
            bonus, source = desperate_charge_bonus_fn(charging_unit, game=self)
            if int(bonus or 0):
                modifiers.append((int(bonus), str(source or "Desperate Devotion").strip() or "Desperate Devotion"))
        eager_charge_bonus_fn = (
            getattr(csm_mgr, "veterans_eager_for_vengeance_charge_roll_bonus", None) if csm_mgr is not None else None
        )
        if callable(eager_charge_bonus_fn):
            bonus, source = eager_charge_bonus_fn(
                charging_unit,
                target_units=target_unit,
                game=self,
            )
            if int(bonus or 0):
                modifiers.append((int(bonus), str(source or "Eager for Vengeance").strip() or "Eager for Vengeance"))
        tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
        synaptic_charge_bonus_fn = getattr(tyr_mgr, "synaptic_imperatives_charge_roll_bonus", None) if tyr_mgr is not None else None
        if callable(synaptic_charge_bonus_fn):
            bonus, source = synaptic_charge_bonus_fn(charging_unit, game=self)
            if int(bonus or 0):
                modifiers.append((int(bonus), str(source or "Synaptic Imperatives").strip() or "Synaptic Imperatives"))
        ac_mgr = getattr(army, "adeptus_custodes_detachments", None) if army is not None else None
        auric_charge_bonus_fn = getattr(ac_mgr, "auric_armour_charge_roll_bonus", None) if ac_mgr is not None else None
        if callable(auric_charge_bonus_fn):
            bonus, source = auric_charge_bonus_fn(charging_unit, target_units=target_unit, game=self)
            if int(bonus or 0):
                modifiers.append((int(bonus), str(source or "Auric Armour").strip() or "Auric Armour"))

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

        temp_effect_iter = getattr(charging_unit, "iter_active_orks_temp_effects", None)
        if callable(temp_effect_iter):
            targets_for_match = []
            if target_unit is None:
                targets_for_match = [None]
            elif isinstance(target_unit, (list, tuple, set)):
                targets_for_match = [tgt for tgt in list(target_unit or []) if tgt is not None]
                if not targets_for_match:
                    targets_for_match = [None]
            else:
                targets_for_match = [target_unit]
            seen_temp_effects: set[str] = set()
            for tgt in targets_for_match:
                require_target_match = tgt is not None
                for effect in list(
                    temp_effect_iter(
                        effect_type="charge_roll_bonus",
                        attack_type="any",
                        target=tgt,
                        game_map=getattr(self, "map", None),
                        require_target_match=require_target_match,
                    )
                    or []
                ):
                    effect_id = str(effect.get("id", "") or "").strip()
                    if effect_id:
                        if effect_id in seen_temp_effects:
                            continue
                        seen_temp_effects.add(effect_id)
                    try:
                        bonus_val = int(effect.get("value", 0) or 0)
                    except (TypeError, ValueError):
                        bonus_val = 0
                    if not bonus_val:
                        continue
                    source = str(effect.get("source", "") or "Orks temporary effect").strip() or "Orks temporary effect"
                    modifiers.append((int(bonus_val), source))

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
        filt = getattr(charging_unit, "_filter_preternatural_agility_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")
        filt = getattr(charging_unit, "_filter_avatar_of_perfection_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")
        filt = getattr(charging_unit, "_filter_diabolical_resilience_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")
        filt = getattr(charging_unit, "_filter_firestorm_champion_of_humanity_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")
        filt = getattr(charging_unit, "_filter_move_advance_charge_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")

        # IMPEDING FIRE / IMPERIALIS OF THE ETERNAL CRUSADE:
        # these are not cumulative with other negative charge modifiers.
        has_non_cumulative_negative = False
        for _val, source in list(modifiers or []):
            norm_source = str(source or "").replace("\u2019", "'").strip().upper()
            if "IMPEDING FIRE" in norm_source or "IMPERIALIS OF THE ETERNAL CRUSADE" in norm_source:
                has_non_cumulative_negative = True
                break
        if has_non_cumulative_negative:
            strongest_negative = None
            keep_positive = []
            for val, source in list(modifiers or []):
                try:
                    ival = int(val or 0)
                except Exception:
                    ival = 0
                if ival < 0:
                    if strongest_negative is None or int(ival) < int(strongest_negative[0]):
                        strongest_negative = (int(ival), source)
                else:
                    keep_positive.append((int(ival), source))
            modifiers = list(keep_positive)
            if strongest_negative is not None:
                modifiers.append((int(strongest_negative[0]), strongest_negative[1]))

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
        distance = max(0.0, base_max + float(total))
        divisor = 1
        source_name = ""
        divisor_fn = getattr(charging_unit, "_gravitic_pulse_roll_divisor", None)
        if callable(divisor_fn):
            try:
                divisor, source_name = divisor_fn(game=self, roll_kind="charge")
            except Exception:
                divisor = 1
                source_name = ""
        if int(divisor or 1) > 1:
            distance = float(max(0, math.ceil(float(distance) / float(divisor))))
            if source_name:
                logger.info(
                    f"Charge distance halved by {source_name} (x{int(divisor)} divisor): max distance {distance}\""
                )
        return float(distance)

    def _apply_charge_modifiers(self, charging_unit: 'Unit', base_roll: int, *, target_unit: Optional['Unit'] = None) -> int:
        """Apply charge roll modifiers based on unit abilities, stratagems, etc."""
        modified_roll = base_roll
        modifiers = self._collect_charge_modifiers(charging_unit, target_unit=target_unit)

        for val, source in modifiers:
            if not val:
                continue
            modified_roll += int(val)
            if val > 0:
                logger.info(f"Charge bonus: +{val} ({source})")
            else:
                logger.info(f"Charge penalty: {val} ({source})")

        divisor = 1
        source_name = ""
        divisor_fn = getattr(charging_unit, "_gravitic_pulse_roll_divisor", None)
        if callable(divisor_fn):
            try:
                divisor, source_name = divisor_fn(game=self, roll_kind="charge")
            except Exception:
                divisor = 1
                source_name = ""
        if int(divisor or 1) > 1:
            modified_roll = max(0, math.ceil(float(modified_roll) / float(divisor)))
            if source_name:
                logger.info(
                    f"Charge roll halved by {source_name} (x{int(divisor)} divisor): {int(modified_roll)}"
                )

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
