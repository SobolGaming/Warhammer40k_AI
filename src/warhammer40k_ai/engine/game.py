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
from .decisions import DecisionOption, DecisionQueue, DecisionRequest, DecisionResult
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
from .ruleset import RulesetBundle
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

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..roster.army_muster import ArmyMusterRequest

class Game:
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
        # Headless/test default: auto-resolve dice roll decisions via headless agent.
        # Interactive UI or network server should disable this.
        self.auto_resolve_dice_rolls = True
        try:
            from .headless_decision_agent import HeadlessDecisionAgent
            self._headless_decision_agent = HeadlessDecisionAgent(self)
        except Exception:
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
        try:
            self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_monarch_of_the_hunt)
        except Exception:
            pass

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
        # Return-on-death pending returns (processed at end of the phase they were destroyed in)
        self._phoenix_gem_pending: List[Dict[str, Any]] = []
        # World Eaters: Blood Surge shooting snapshots (attacker -> {target: model_count})
        self._blood_surge_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
        # World Eaters: Brazen Fury shooting snapshots (attacker -> {target: model_count})
        self._brazen_fury_shooting_snapshot: Dict['Unit', Dict['Unit', int]] = {}
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

    def _install_default_event_subscribers(self) -> None:
        """Install non-UI rule subscribers that operate off the event system."""
        registry = RuleRegistry(build_default_rule_providers())
        registry.apply(self)
        self.rule_registry = registry

    def _on_unit_destroyed_monarch_of_the_hunt(self, unit=None, **_kwargs) -> None:
        if unit is None or not bool(getattr(self, "is_authoritative", True)):
            return
        try:
            destroyed_owner = unit.get_parent_army().player
        except Exception:
            destroyed_owner = None

        for player in list(getattr(self, "players", []) or []):
            try:
                army = player.get_army()
            except Exception:
                army = None
            if army is None:
                continue
            for shalaxi_unit in list(getattr(army, "units", []) or []):
                try:
                    found, _ = shalaxi_unit._find_ability_with_patterns(["monarch of the hunt"])
                except Exception:
                    found = False
                if not found:
                    continue
                quarry_ids = getattr(shalaxi_unit, "_monarch_of_the_hunt_quarry_ids", None)
                if not quarry_ids:
                    continue
                try:
                    if getattr(unit, "_id", None) not in quarry_ids:
                        continue
                except Exception:
                    continue

                alive_ids = set()
                enemy_army = None
                try:
                    enemy_army = destroyed_owner.get_army() if destroyed_owner is not None else None
                except Exception:
                    enemy_army = None
                if enemy_army is not None:
                    by_id = {getattr(u2, "_id", None): u2 for u2 in list(getattr(enemy_army, "units", []) or [])}
                    for qid in list(quarry_ids):
                        u2 = by_id.get(qid)
                        if u2 is None:
                            continue
                        try:
                            if u2.is_alive():
                                alive_ids.add(qid)
                        except Exception:
                            continue
                setattr(shalaxi_unit, "_monarch_of_the_hunt_quarry_ids", alive_ids)

                if not alive_ids:
                    try:
                        req = army._build_monarch_of_the_hunt_request(
                            game=self,
                            source_unit=shalaxi_unit,
                            enemy_units=list(self.get_enemy_units(player)),
                        )
                    except Exception:
                        req = None
                    if req is not None and hasattr(self, "request_decision"):
                        self.request_decision(req)

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
            except Exception:
                is_below_starting = True
        if not is_below_starting:
            return

        try:
            unit_army = unit.get_parent_army()
        except Exception:
            unit_army = None

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
            except Exception:
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

        unit_army = None
        try:
            unit_army = unit.get_parent_army()
        except Exception:
            unit_army = None

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
            for model in models:
                if not bool(getattr(model, "is_alive", True)):
                    continue
                for ab in list(getattr(unit, "possible_abilities", []) or []):
                    desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
                    text = str(desc or "")
                    if "command phase" not in text.lower() or "regains" not in text.lower() or "wounds" not in text.lower():
                        continue
                    m = re.search(r"regains\s+(\d+|d3)", text.lower())
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
            try:
                self.event_system.publish(
                    "daemon_primarch_slaanesh_prompt",
                    player=player,
                    opponent_player=current_player,
                    game=self,
                )
            except Exception:
                pass

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
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_COMBAT_DOCTRINE
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import get_entity_id
        except Exception:
            return
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
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_GRAND_COVEN
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import get_entity_id
        except Exception:
            return
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
        options = []
        try:
            options = list(getattr(mgr, "get_available_combat_drugs", lambda: [])() or [])
        except Exception:
            options = []
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_COMBAT_DRUGS
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import get_entity_id
        except Exception:
            return
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

    def _on_phase_start_optional_abilities(self, player=None, phase=None, **_kwargs) -> None:
        """
        Hook point for optional, player-decided abilities that trigger at specific timing windows.

        Currently supported:
        - Possessed Lord (Once per battle, start of Fight phase): prompt to activate.
        - Fight phase melee AP boost (Once per battle, start of Fight phase): +3 Attacks and +1 AP for bearer.
        - Enhancements that grant Fight First (Once per battle, start of Fight phase).
        """
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname:
            for p in list(getattr(self, "players", []) or []):
                if p is None:
                    continue
                army = p.get_army()
                if army is None:
                    continue
                for unit in list(army.units):
                    if unit is None:
                        continue
                    try:
                        root = unit.get_attached_unit_root()
                    except Exception:
                        root = unit
                    if root is None or root is not unit:
                        continue
                    if not root.is_alive():
                        continue
                    try:
                        if not getattr(root, "deployed", True):
                            continue
                        if root.is_in_reserves() or root.is_embarked:
                            continue
                    except Exception:
                        pass

                    # Model-level: start-of-any-phase damage set to 1 (once per battle).
                    try:
                        models = list(root.get_attached_unit_models() or [])
                    except Exception:
                        models = list(getattr(root, "models", []) or [])
                    for model in list(models or []):
                        if not getattr(model, "is_alive", False):
                            continue
                        specs = []
                        try:
                            specs = list(root.model_start_any_phase_damage_set_one_specs(model) or [])
                        except Exception:
                            specs = []
                        if not specs:
                            continue
                        for spec in specs:
                            key = str(spec.get("key") or "start_any_phase_damage_set_one").strip().lower()
                            if not key:
                                key = "start_any_phase_damage_set_one"
                            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                                continue
                            unit_id = maybe_entity_id(root)
                            model_id = maybe_entity_id(model)
                            ability_name = str(spec.get("source", "") or "Start of phase damage set to 1").strip()
                            ctx = {
                                "ability_name": ability_name,
                                "unit": getattr(root, "name", "") or "",
                                "model": getattr(model, "name", "") or "",
                                "phase": pname.replace("_", " ").title(),
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "buff_key": key,
                            }
                            message = (
                                f"Activate {ability_name} for {getattr(model, 'name', 'Model')} "
                                f"({getattr(root, 'name', 'Unit')})?"
                            )
                            self._queue_optional_ability_confirmation(
                                player=p,
                                ability_key="start_any_phase_damage_set_one",
                                ability_name=ability_name,
                                message=message,
                                context=ctx,
                                payload={"unit_id": unit_id, "model_id": model_id, "buff_key": key},
                                instance_key=f"{model_id}:{key}",
                            )

                    # Unit-level: start-of-any-phase FNP (once per battle).
                    try:
                        specs = list(root.unit_start_any_phase_fnp_specs() or [])
                    except Exception:
                        specs = []
                    for spec in specs:
                        ability_key = str(spec.get("ability_key") or "start_any_phase_fnp").strip().lower()
                        if not ability_key:
                            ability_key = "start_any_phase_fnp"
                        if root.has_used_unit_once_per_battle(ability_key):
                            continue
                        unit_id = maybe_entity_id(root)
                        ability_name = str(spec.get("source", "") or "Start of phase FNP").strip()
                        ctx = {
                            "ability_name": ability_name,
                            "unit": getattr(root, "name", "") or "",
                            "phase": pname.replace("_", " ").title(),
                            "unit_id": unit_id,
                            "ability_key": ability_key,
                            "fnp_value": int(spec.get("value", 0) or 0),
                        }
                        message = f"Activate {ability_name} for {getattr(root, 'name', 'Unit')}?"
                        self._queue_optional_ability_confirmation(
                            player=p,
                            ability_key="start_any_phase_fnp",
                            ability_name=ability_name,
                            message=message,
                            context=ctx,
                            payload={"unit_id": unit_id, "ability_key": ability_key},
                            instance_key=f"{unit_id}:{ability_key}",
                        )
        if pname == "FIGHT_PHASE":
            if player is None:
                return

            # Only prompt the current player for their own optional activations at the start of this Fight phase.
            if player is not self.get_current_player():
                return

            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Optional abilities require an army for {player.name}.")

            for unit in list(army.units):
                if not unit.is_alive():
                    continue
                # Check unit has Possessed Lord ability text (datasheet ability list)
                has_possessed_lord = False
                for ab in (getattr(unit, "possible_abilities", []) or []):
                    nm = str(getattr(ab, "name", "") or "").strip().lower()
                    if nm == "possessed lord":
                        has_possessed_lord = True
                        break
                if not has_possessed_lord:
                    continue

                # Apply to the first alive model in the unit (typical for character datasheets).
                models = list(unit.models or [])
                for m in models:
                    if not getattr(m, "is_alive", True):
                        continue
                    # If already used, skip.
                    if m.has_used_once_per_battle("possessed_lord"):
                        break

                    unit_id = maybe_entity_id(unit)
                    model_id = maybe_entity_id(m)
                    ctx = {
                        "ability_name": "Possessed Lord",
                        "unit": getattr(unit, "name", "") or "",
                        "model": getattr(m, "name", "") or "",
                        "phase": "Fight phase",
                        "unit_id": unit_id,
                        "model_id": model_id,
                    }
                    message = (
                        f"Activate Possessed Lord for {getattr(m, 'name', 'Model')} "
                        f"({getattr(unit, 'name', 'Unit')})?"
                    )
                    self._queue_optional_ability_confirmation(
                        player=player,
                        ability_key="possessed_lord",
                        ability_name="Possessed Lord",
                        message=message,
                        context=ctx,
                        payload={"unit_id": unit_id, "model_id": model_id},
                    )
                    break
            # Once per battle: start of Fight phase -> +3 Attacks and +1 AP (melee) for this model.
            for unit in list(army.units):
                if not unit.is_alive():
                    continue
                models = list(getattr(unit, "models", []) or [])
                for m in models:
                    if not getattr(m, "is_alive", True):
                        continue
                    specs = []
                    try:
                        specs = list(unit.model_start_fight_phase_melee_attacks_ap_boost_specs(m) or [])
                    except Exception:
                        specs = []
                    if not specs:
                        continue
                    for spec in specs:
                        key = str(spec.get("key") or "fight_phase_melee_ap_boost").strip().lower()
                        if not key:
                            key = "fight_phase_melee_ap_boost"
                        if getattr(m, "has_used_once_per_battle", lambda _k: False)(key):
                            continue
                        unit_id = maybe_entity_id(unit)
                        model_id = maybe_entity_id(m)
                        ability_name = str(spec.get("source", "") or "Fight phase melee boost").strip()
                        ctx = {
                            "ability_name": ability_name,
                            "unit": getattr(unit, "name", "") or "",
                            "model": getattr(m, "name", "") or "",
                            "phase": "Fight phase",
                            "unit_id": unit_id,
                            "model_id": model_id,
                        }
                        message = (
                            f"Activate {ability_name} for {getattr(m, 'name', 'Model')} "
                            f"({getattr(unit, 'name', 'Unit')})?"
                        )
                        self._queue_optional_ability_confirmation(
                            player=player,
                            ability_key="fight_phase_melee_ap_boost",
                            ability_name=ability_name,
                            message=message,
                            context=ctx,
                            payload={"unit_id": unit_id, "model_id": model_id, "buff_key": key},
                            instance_key=f"{model_id}:{key}",
                        )
            # Enhancement: once per battle, start of Fight phase -> Fight First for bearer's unit.
            for unit in list(army.units):
                if not unit.is_alive():
                    continue
                if not unit.has_enhancement_fight_first_once_per_battle():
                    continue
                if not unit.can_use_enhancement_fight_first():
                    continue
                enh_name = str(getattr(getattr(unit, "enhancement", None), "name", "") or "")
                ctx = {
                    "ability_name": enh_name or "Fight First Enhancement",
                    "unit": getattr(unit, "name", "") or "",
                    "phase": "Fight phase",
                    "unit_id": maybe_entity_id(unit),
                }
                message = f"Activate {ctx['ability_name']} for {getattr(unit, 'name', 'Unit')}?"
                self._queue_optional_ability_confirmation(
                    player=player,
                    ability_key="enhancement_fight_first",
                    ability_name=ctx["ability_name"],
                    message=message,
                    context=ctx,
                    payload={"unit_id": ctx.get("unit_id")},
                    instance_key=str(ctx.get("unit_id") or ""),
                )

            # Moment Shackle: once per battle, start of Fight phase, choose one effect.
            from .decision_kinds import DECISION_CHOOSE_MOMENT_SHACKLE
            from .decisions import DecisionOption, DecisionRequest

            pending_models = set()
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if getattr(req, "decision_type", None) != DECISION_CHOOSE_MOMENT_SHACKLE:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)

            for unit in list(army.units):
                if not unit.is_alive():
                    continue
                try:
                    if not getattr(unit, "deployed", True):
                        continue
                    if unit.is_in_reserves() or unit.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    models = list(unit.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(unit, "models", []) or [])
                for model in list(models or []):
                    if not getattr(model, "is_alive", False):
                        continue
                    spec = None
                    try:
                        spec = unit.model_moment_shackle_spec(model)
                    except Exception:
                        spec = None
                    if not spec:
                        continue
                    ability_key = str(spec.get("ability_key") or "moment_shackle").strip().lower() or "moment_shackle"
                    if getattr(model, "has_used_once_per_battle", lambda _k: False)(ability_key):
                        continue
                    unit_id = maybe_entity_id(unit)
                    model_id = maybe_entity_id(model)
                    if model_id and str(model_id) in pending_models:
                        continue
                    ability_name = str(spec.get("source") or "Moment Shackle").strip() or "Moment Shackle"
                    weapon_name = str(spec.get("weapon_name") or "Watcher's Axe").strip() or "Watcher's Axe"
                    try:
                        attacks = int(spec.get("attacks", 12) or 12)
                    except Exception:
                        attacks = 12
                    try:
                        invuln = int(spec.get("invuln", 2) or 2)
                    except Exception:
                        invuln = 2
                    ctx = {
                        "ability_name": ability_name,
                        "unit": getattr(unit, "name", "") or "",
                        "model": getattr(model, "name", "") or "",
                        "phase": "Fight phase",
                        "unit_id": unit_id,
                        "model_id": model_id,
                        "ability_key": ability_key,
                    }
                    options = [
                        DecisionOption.create(
                            "Do not use",
                            payload={
                                "action": "skip",
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "ability_key": ability_key,
                                "summary": "Do not use Moment Shackle this phase.",
                            },
                        ),
                        DecisionOption.create(
                            f"{weapon_name} Attacks {int(attacks)}",
                            payload={
                                "choice": "attacks",
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "ability_key": ability_key,
                                "weapon_name": weapon_name,
                                "attacks": int(attacks),
                                "summary": f"{weapon_name} Attacks set to {int(attacks)} until end of phase.",
                            },
                        ),
                        DecisionOption.create(
                            f"Invulnerable Save {int(invuln)}+",
                            payload={
                                "choice": "invuln",
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "ability_key": ability_key,
                                "invuln": int(invuln),
                                "summary": f"Gain a {int(invuln)}+ invulnerable save until end of phase.",
                            },
                        ),
                    ]
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_MOMENT_SHACKLE,
                        f"{ability_name}: select one effect.",
                        player_id=getattr(player, "id", None),
                        options=options,
                        context=ctx,
                    )
                    self.request_decision(request)
            return

        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        if player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Optional abilities require an army for {player.name}.")

        for unit in list(army.units):
            if not unit.is_alive():
                continue
            if not unit.is_attached_leader:
                continue

            ability = unit.get_command_phase_bodyguard_return_ability()
            if not ability:
                continue
            bodyguard = unit.get_attached_unit_root()
            if bodyguard is None or bodyguard is unit:
                continue
            if not getattr(bodyguard, "deployed", True):
                continue
            if str(getattr(bodyguard, "reserve_status", "deployed")) != "deployed":
                continue
            if bodyguard.is_in_reserves():
                continue
            if bool(getattr(bodyguard, "embarked_in", None)):
                continue
            if bodyguard.is_embarked:
                continue
            if len(bodyguard.models or []) <= 0:
                continue
            if not list(bodyguard.models_lost or []):
                continue

            amount = int(ability.get("amount", 0) or 0)
            if amount <= 0:
                continue
            self._queue_bodyguard_return_decision(
                player=player,
                leader_unit=unit,
                bodyguard_unit=bodyguard,
                ability=ability,
                remaining=amount,
            )

    def _on_phase_start_dance_of_death(self, player=None, phase=None, **_kwargs) -> None:
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        from .decision_kinds import DECISION_CHOOSE_DANCE_OF_DEATH
        from .decisions import DecisionOption, DecisionRequest

        pending_units = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_DANCE_OF_DEATH:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    uid = str(ctx.get("unit_id", "") or "")
                    if uid:
                        pending_units.add(uid)
        except Exception:
            pending_units = set()

        for p in list(getattr(self, "players", []) or []):
            if p is None:
                continue
            army = p.get_army()
            if army is None:
                continue
            for unit in list(army.units or []):
                if unit is None or not unit.is_alive():
                    continue
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None or not root.is_alive():
                    continue
                try:
                    if not root.has_dance_of_death():
                        continue
                except Exception:
                    continue
                try:
                    choice_fn = getattr(root, "_dance_of_death_choice", None)
                    if callable(choice_fn) and choice_fn(game=self):
                        continue
                except Exception:
                    pass
                unit_id = str(get_entity_id(root) or "")
                if unit_id and unit_id in pending_units:
                    continue
                options = [
                    DecisionOption.create(
                        "Hero's Prowess",
                        payload={"choice": "HERO", "summary": "Re-roll Hit rolls of 1 for this unit."},
                    ),
                    DecisionOption.create(
                        "Villain's Doom",
                        payload={"choice": "VILLAIN", "summary": "Add 1 to Wound rolls for this unit."},
                    ),
                    DecisionOption.create(
                        "Trickster's Grace",
                        payload={"choice": "TRICKSTER", "summary": "Attacks against this unit suffer -1 to hit."},
                    ),
                ]
                ctx = {
                    "unit_id": unit_id,
                    "ability_name": "Dance of Death",
                    "phase_name": pname,
                }
                req = DecisionRequest.create(
                    DECISION_CHOOSE_DANCE_OF_DEATH,
                    "Dance of Death: select a performance.",
                    player_id=getattr(p, "id", None),
                    options=options,
                    context=ctx,
                )
                self.request_decision(req)

    def _on_phase_start_post_shoot_leadership_debuff_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear post-shoot Leadership/Battle-shock debuffs at the start of the owner's Shooting phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Post-shoot debuff cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Post-shoot debuff cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("post_shoot_leadership_debuff_owner", "") or "") != owner_id:
                    continue
                if sr.get("post_shoot_leadership_debuff_active"):
                    unit.clear_post_shoot_leadership_debuff()

    def _on_phase_start_wracked_with_agonies_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Wracked with Agonies effects at the start of the owner's Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Wracked with Agonies cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Wracked with Agonies cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("wracked_with_agonies_owner", "") or "") != owner_id:
                    continue
                if sr.get("wracked_with_agonies_active"):
                    clear_fn = getattr(unit, "clear_wracked_with_agonies", None)
                    if callable(clear_fn):
                        clear_fn()
                    else:
                        for key in (
                            "wracked_with_agonies_active",
                            "wracked_with_agonies_owner",
                            "wracked_with_agonies_turn",
                            "wracked_with_agonies_source",
                            "wracked_with_agonies_move_penalty",
                            "wracked_with_agonies_charge_penalty",
                        ):
                            sr.pop(key, None)
                        unit.special_rules = sr

    def _on_phase_start_snared_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Snared effects at the start of the owner's Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Snared cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Snared cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("snared_owner", "") or "") != owner_id:
                    continue
                if sr.get("snared_active"):
                    clear_fn = getattr(unit, "clear_snared", None)
                    if callable(clear_fn):
                        clear_fn()
                    else:
                        for key in (
                            "snared_active",
                            "snared_owner",
                            "snared_turn",
                            "snared_source",
                            "snared_weapon_key",
                            "snared_weapon_name",
                        ):
                            sr.pop(key, None)
                        unit.special_rules = sr

    def _on_phase_start_pinned_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Pinned effects at the start of the owner's Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Pinned cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Pinned cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("pinned_owner", "") or "") != owner_id:
                    continue
                if sr.get("pinned_active"):
                    clear_fn = getattr(unit, "clear_pinned", None)
                    if callable(clear_fn):
                        clear_fn()
                    else:
                        for key in (
                            "pinned_active",
                            "pinned_owner",
                            "pinned_turn",
                            "pinned_source",
                            "pinned_move_penalty",
                            "pinned_charge_penalty",
                        ):
                            sr.pop(key, None)
                        unit.special_rules = sr

    def _on_phase_start_misfortune_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Misfortune effects at the start of the owner's Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Misfortune cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Misfortune cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("misfortune_owner", "") or "") != owner_id:
                    continue
                if sr.get("misfortune_active") or sr.get("misfortune_selected_turn"):
                    for key in (
                        "misfortune_active",
                        "misfortune_owner",
                        "misfortune_turn",
                        "misfortune_source",
                        "misfortune_penalty",
                        "misfortune_selected_owner",
                        "misfortune_selected_turn",
                    ):
                        sr.pop(key, None)
                    unit.special_rules = sr

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

    def _on_phase_start_movement_phase_visible_wound_bonus_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear movement-phase wound bonus markers at the start of the owner's Command phase."""
        self._cleanup_movement_phase_visible_bonus(player=player, phase=phase, kind="wound")

    def _on_phase_start_movement_phase_visible_hit_bonus_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear movement-phase hit bonus markers at the start of the owner's Command phase."""
        self._cleanup_movement_phase_visible_bonus(player=player, phase=phase, kind="hit")

    def _on_phase_start_spirit_mark_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Spirit Mark effects at the start of the owner's Movement phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Spirit Mark cleanup requires an army for {getattr(player, 'name', 'player')}.")
        for unit in list(getattr(army, "units", []) or []):
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not sr.get("spirit_mark_active"):
                continue
            if str(sr.get("spirit_mark_owner", "") or "") != owner_id:
                continue
            try:
                mark_turn = int(sr.get("spirit_mark_turn", 0) or 0)
            except Exception:
                mark_turn = 0
            if mark_turn == int(turn or 0):
                continue
            for key in (
                "spirit_mark_active",
                "spirit_mark_owner",
                "spirit_mark_turn",
                "spirit_mark_source",
                "spirit_mark_target_id",
                "spirit_mark_sustained_hits_value",
                "spirit_mark_keyword",
            ):
                sr.pop(key, None)
            unit.special_rules = sr

    def _on_phase_start_engagement_battleshock(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase: enemy units within Engagement Range of a model must take Battle-shock tests."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        game_map = self.map
        if game_map is None:
            raise RuntimeError("Engagement Battle-shock requires a game map.")

        from ..utility.aura_utils import model_within_engagement_range_of_unit

        def _apply_battleshock(target_unit, *, modifier: int = 0, reason: str = "") -> None:
            if target_unit is None:
                return
            sr = getattr(target_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if modifier:
                current = int(sr.get("battle_shock_test_modifier", 0) or 0)
                sr["battle_shock_test_modifier"] = current + int(modifier)
                if reason:
                    reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
                    reasons.append(reason)
                    sr["battle_shock_test_modifier_reasons"] = reasons
            target_unit.special_rules = sr
            target_unit.take_battle_shock_test(int(getattr(self, "turn", 0) or 1))

        def _unit_in_engagement_with_unit(source_unit, target_unit) -> bool:
            if source_unit is None or target_unit is None:
                return False
            within_fn = getattr(game_map, "is_within_engagement_range", None)
            if callable(within_fn):
                try:
                    return bool(within_fn(source_unit, target_unit))
                except Exception:
                    return False
            for model in list(getattr(source_unit, "models", []) or []):
                try:
                    if model_within_engagement_range_of_unit(model, target_unit):
                        return True
                except Exception:
                    continue
            return False

        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Engagement Battle-shock requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Engagement Battle-shock requires an army for {p.name}.")
            tested_units: set[tuple[str, str]] = set()
            for unit in list(army.units):
                if unit is None:
                    continue
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
                if unit.is_in_reserves():
                    continue
                if unit.is_embarked:
                    continue

                enemy_roots = []
                seen_enemy = set()
                for enemy in game_map.get_enemy_units(unit):
                    if enemy is None:
                        continue
                    root = enemy.get_attached_unit_root()
                    key = get_entity_id(root)
                    if key in seen_enemy:
                        continue
                    seen_enemy.add(key)
                    if not root.is_alive() or not getattr(root, "deployed", True):
                        continue
                    if root.is_in_reserves():
                        continue
                    if root.is_embarked:
                        continue
                    enemy_roots.append(root)

                if not enemy_roots:
                    continue

                unit_specs = unit.unit_start_fight_phase_engagement_battleshock_specs() or []
                for spec in unit_specs:
                    source = str(spec.get("source", "") or "Fight phase Battle-shock").strip()
                    penalty = 0
                    try:
                        penalty = int(spec.get("penalty", 0) or 0)
                    except Exception:
                        penalty = 0
                    for enemy_root in enemy_roots:
                        if not _unit_in_engagement_with_unit(unit, enemy_root):
                            continue
                        key = (str(get_entity_id(enemy_root)), source.lower())
                        if key in tested_units:
                            continue
                        tested_units.add(key)
                        mod = 0
                        reason = ""
                        if penalty and enemy_root.is_below_half_strength():
                            mod = -penalty
                            reason = "Below Half-strength"
                        _apply_battleshock(enemy_root, modifier=mod, reason=reason)
                        from ..utility.event_bus import append_action
                        if p is not None:
                            label = f"{getattr(unit, 'name', 'Unit')} {source}".strip()
                            append_action(
                                p,
                                f"{label}: {getattr(enemy_root, 'name', 'Unit')} takes a Battle-shock test.",
                            )

                for model in list(unit.models or []):
                    if not getattr(model, "is_alive", False):
                        continue
                    specs = unit.model_start_fight_phase_engagement_battleshock_specs(model)
                    if not specs:
                        continue
                    for spec in specs:
                        source = str(spec.get("source", "") or "Fight phase Battle-shock").strip()
                        penalty = 0
                        try:
                            penalty = int(spec.get("penalty", 0) or 0)
                        except Exception:
                            penalty = 0
                        for enemy_root in enemy_roots:
                            if not model_within_engagement_range_of_unit(model, enemy_root):
                                continue
                            mod = 0
                            reason = ""
                            if penalty and enemy_root.is_below_half_strength():
                                mod = -penalty
                                reason = "Below Half-strength"
                            _apply_battleshock(enemy_root, modifier=mod, reason=reason)
                            from ..utility.event_bus import append_action
                            if p is not None:
                                label = f"{getattr(model, 'name', 'Model')} {source}".strip()
                                append_action(
                                    p,
                                    f"{label}: {getattr(enemy_root, 'name', 'Unit')} takes a Battle-shock test.",
                                )

    def _on_phase_start_empowered_by_death(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase: below Starting Strength units with Empowered by Death gain Fight First until end of phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        for p in list(getattr(self, "players", []) or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            processed: set[str] = set()
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
                except Exception:
                    root = unit
                root_id = str(get_entity_id(root) or "")
                if root_id and root_id in processed:
                    continue
                try:
                    if not getattr(unit, "has_empowered_by_death", lambda: False)():
                        continue
                except Exception:
                    continue
                try:
                    if not root.is_alive() or not getattr(root, "deployed", True):
                        continue
                except Exception:
                    continue
                try:
                    if root.is_in_reserves() or root.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    if not root.is_below_starting_strength():
                        continue
                except Exception:
                    continue
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["empowered_by_death_active"] = True
                sr["empowered_by_death_expires_phase"] = "FIGHT_PHASE"
                try:
                    sources = list(unit.empowered_by_death_sources() or [])
                    if sources:
                        sr["empowered_by_death_source"] = sources[0]
                except Exception:
                    pass
                root.special_rules = sr
                if root_id:
                    processed.add(root_id)

    def _on_phase_start_herald_of_ynnead(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase start: select an engaged enemy unit to mark for wound reroll 1s (Herald of Ynnead)."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        game_map = self.map
        if game_map is None:
            return
        from ..utility.aura_utils import model_within_engagement_range_of_unit

        pending_models = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("ability", "") or "") != "herald_of_ynnead":
                        continue
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)
        except Exception:
            pending_models = set()

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        def _model_sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return str(getattr(m, "name", "") or "")

        for p in list(getattr(self, "players", []) or []):
            if p is None:
                continue
            army = p.get_army()
            if army is None:
                continue
            for unit in sorted(list(army.units or []), key=_unit_sort_key):
                if unit is None:
                    continue
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
                try:
                    if unit.is_in_reserves() or unit.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None or not root.is_alive():
                    continue
                try:
                    models = list(root.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(root, "models", []) or [])
                if not models:
                    continue
                for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                    model_id = str(get_entity_id(model) or "")
                    if model_id and model_id in pending_models:
                        continue
                    specs = root.model_start_fight_phase_engagement_wound_reroll_ones_specs(model) or []
                    if not specs:
                        continue
                    spec = specs[0]
                    ability_name = str(spec.get("source", "") or "Herald of Ynnead").strip() or "Herald of Ynnead"
                    keyword = str(spec.get("keyword", "") or "aeldari").strip().lower() or "aeldari"

                    candidates = []
                    seen_enemy = set()
                    for enemy in list(game_map.get_enemy_units(root) or []):
                        if enemy is None:
                            continue
                        try:
                            enemy_root = enemy.get_attached_unit_root()
                        except Exception:
                            enemy_root = enemy
                        if enemy_root is None or not enemy_root.is_alive():
                            continue
                        try:
                            if not getattr(enemy_root, "deployed", True):
                                continue
                            if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                                continue
                        except Exception:
                            pass
                        eid = str(get_entity_id(enemy_root) or "")
                        if not eid or eid in seen_enemy:
                            continue
                        seen_enemy.add(eid)
                        if not model_within_engagement_range_of_unit(model, enemy_root):
                            continue
                        candidates.append(enemy_root)

                    if not candidates:
                        continue
                    try:
                        candidates = sorted(candidates, key=_unit_sort_key)
                    except Exception:
                        pass
                    options = []
                    for cand in candidates:
                        options.append(
                            DecisionOption.create(
                                str(getattr(cand, "name", "Unit") or "Unit"),
                                payload={"target_unit_id": get_entity_id(cand)},
                            )
                        )
                    if not options:
                        continue
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_QUARRY,
                        f"{ability_name}: select a target.",
                        player_id=getattr(p, "id", None),
                        options=options,
                        context={
                            "ability": "herald_of_ynnead",
                            "ability_name": ability_name,
                            "attacker_unit_id": get_entity_id(root),
                            "model_id": model_id,
                            "keyword": keyword,
                        },
                    )
                    self.request_decision(request)

    def _on_phase_start_hallowed_ground(self, player=None, phase=None, **_kwargs) -> None:
        if phase is None:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Hallowed Ground phase start requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Hallowed Ground requires an army for {p.name}.")
            mgr = getattr(army, "grey_knights_detachments", None)
            if mgr is None or not hasattr(mgr, "on_phase_start"):
                continue
            mgr.on_phase_start(game=self)

    def _on_phase_start_cabal_of_sorcerers(self, player=None, phase=None, **_kwargs) -> None:
        """Reset Cabal of Sorcerers usage at the start of the active player's Shooting phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            raise RuntimeError("Cabal of Sorcerers requires an active player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Cabal of Sorcerers requires an army for {player.name}.")
        mgr = getattr(army, "cabal_of_sorcerers", None)
        if mgr is None:
            return
        mgr.on_shooting_phase_start(game=self, player=player)

    def _on_phase_start_for_the_greater_good(self, player=None, phase=None, **_kwargs) -> None:
        """Prompt Observer selection at the start of the active player's Shooting phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            raise RuntimeError("For the Greater Good requires an active player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"For the Greater Good requires an army for {player.name}.")
        mgr = getattr(army, "for_the_greater_good", None)
        if mgr is None:
            return
        mgr.on_shooting_phase_start(game=self, player=player)
        es = getattr(self, "event_system", None)
        if es is None or not hasattr(es, "subscribers"):
            raise RuntimeError("Event system missing for For the Greater Good prompt.")
        subs = getattr(es, "subscribers", None)
        if not isinstance(subs, dict):
            raise RuntimeError("Event system subscribers not configured.")
        if subs.get("for_the_greater_good_prompt"):
            es.publish("for_the_greater_good_prompt", player=player, game=self)

    def _on_phase_start_aeldari_enhancements(self, player=None, phase=None, **_kwargs) -> None:
        """Aeldari enhancements that trigger at the start of Command or Shooting phases."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname not in ("COMMAND_PHASE", "SHOOTING_PHASE"):
            return
        if player is None or player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Aeldari enhancement hooks require an army for {player.name}.")
        game_map = getattr(self, "map", None)
        if game_map is None:
            raise RuntimeError("Aeldari enhancement hooks require a game map.")

        from ..utility.aura_utils import distance_between_models_bases_3d
        from ..utility.dice import get_roll
        from ..utility.entity_ids import get_entity_id
        from ..utility.event_bus import append_action, append_dice

        def _unit_active(unit, *, allow_embarked: bool = False) -> bool:
            if unit is None:
                return False
            try:
                if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                    return False
            except Exception:
                return False
            try:
                if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", False)):
                    return False
            except Exception:
                return False
            try:
                if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
                    return False
            except Exception:
                pass
            try:
                if hasattr(unit, "is_in_reserves") and callable(unit.is_in_reserves):
                    if bool(unit.is_in_reserves()):
                        return False
            except Exception:
                pass
            if not allow_embarked:
                try:
                    if bool(getattr(unit, "is_embarked", False)):
                        return False
                except Exception:
                    pass
                try:
                    if getattr(unit, "embarked_in", None) is not None:
                        return False
                except Exception:
                    pass
            return True

        def _iter_unique_roots(units):
            seen = set()
            for u in list(units or []):
                try:
                    root = u.get_attached_unit_root()
                except Exception:
                    root = u
                if root is None:
                    continue
                uid = get_entity_id(root) or id(root)
                if uid in seen:
                    continue
                seen.add(uid)
                yield root

        def _model_in_unit_range(model, target_unit, range_inches: float) -> bool:
            try:
                target_models = list(target_unit.get_attached_unit_models() or [])
            except Exception:
                target_models = list(getattr(target_unit, "models", []) or [])
            target_models = [m for m in target_models if getattr(m, "is_alive", True)]
            if not target_models:
                return False
            for tm in target_models:
                try:
                    if distance_between_models_bases_3d(model, tm) <= float(range_inches) + 1e-6:
                        return True
                except Exception:
                    continue
            return False

        def _model_within_objective(model, objective_point) -> bool:
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

        def _within_controlled_objective(bearer_model, unit) -> bool:
            if bearer_model is None:
                return False
            objectives = list(getattr(game_map, "objectives", []) or [])
            for obj in objectives:
                loc = getattr(obj, "location", None)
                if loc is None or getattr(loc, "removed", False):
                    continue
                loc.update_control(self)
                if getattr(loc, "controlling_player", None) is not player:
                    continue
                if _model_within_objective(bearer_model, loc):
                    return True
                transport = getattr(unit, "embarked_in", None)
                if transport is not None:
                    try:
                        if transport.is_within_objective_range(loc):
                            return True
                    except Exception:
                        continue
            return False

        if pname == "SHOOTING_PHASE":
            for unit in list(getattr(army, "units", []) or []):
                sr = getattr(unit, "special_rules", None)
                if not (isinstance(sr, dict) and sr.get("enhancement_guiding_presence")):
                    continue
                if not _unit_active(unit):
                    continue
                bearer = getattr(unit, "_get_enhancement_bearer_model", None)
                bearer = bearer() if callable(bearer) else None
                if bearer is None or not getattr(bearer, "is_alive", True):
                    continue
                candidates = []
                for root in _iter_unique_roots(getattr(army, "units", []) or []):
                    if not _unit_active(root):
                        continue
                    try:
                        if not root.has_any_keyword("AELDARI"):
                            continue
                        if not root.has_any_keyword("VEHICLE"):
                            continue
                    except Exception:
                        continue
                    if not _model_in_unit_range(bearer, root, 9.0):
                        continue
                    candidates.append(root)

                if not candidates:
                    continue
                ability_name = str(getattr(getattr(unit, "enhancement", None), "name", "") or "Guiding Presence").strip()
                if len(candidates) == 1:
                    target = candidates[0]
                    tsr = getattr(target, "special_rules", None)
                    if not isinstance(tsr, dict):
                        tsr = {}
                    tsr["guiding_presence_active"] = True
                    tsr["guiding_presence_bonus"] = 1
                    tsr["guiding_presence_expires_phase"] = "SHOOTING_PHASE"
                    tsr["guiding_presence_source"] = ability_name
                    tsr["guiding_presence_owner"] = str(getattr(player, "id", "") or "")
                    target.special_rules = tsr
                    try:
                        tname = str(getattr(target, "name", "Unit") or "Unit")
                        append_action(player, f"{ability_name}: {tname} gains +1 to hit this phase.")
                    except Exception:
                        pass
                    continue

                self._queue_aeldari_guiding_presence(
                    player=player,
                    source_unit=unit,
                    model=bearer,
                    candidates=candidates,
                    ability_name=ability_name,
                    range_inches=9,
                    hit_bonus=1,
                )

        if pname == "COMMAND_PHASE":
            for unit in list(getattr(army, "units", []) or []):
                sr = getattr(unit, "special_rules", None)
                if not (isinstance(sr, dict) and sr.get("enhancement_harmonisation_matrix")):
                    continue
                if not _unit_active(unit, allow_embarked=True):
                    continue
                bearer = getattr(unit, "_get_enhancement_bearer_model", None)
                bearer = bearer() if callable(bearer) else None
                if bearer is None or not getattr(bearer, "is_alive", True):
                    continue
                if not _within_controlled_objective(bearer, unit):
                    continue
                ability_name = str(getattr(getattr(unit, "enhancement", None), "name", "") or "Harmonisation Matrix").strip()
                roll = int(get_roll("D6") or 0)
                append_dice(player, f"{ability_name} roll: {roll}")
                if roll >= 3:
                    gained = int(player.gain_command_points(1, reason=ability_name) or 0)
                    if gained:
                        append_action(player, f"{ability_name}: gained {gained} CP.")

            for unit in list(getattr(army, "units", []) or []):
                sr = getattr(unit, "special_rules", None)
                if not (isinstance(sr, dict) and sr.get("enhancement_spirit_stone_of_raelyth")):
                    continue
                if not _unit_active(unit):
                    continue
                bearer = getattr(unit, "_get_enhancement_bearer_model", None)
                bearer = bearer() if callable(bearer) else None
                if bearer is None or not getattr(bearer, "is_alive", True):
                    continue
                candidates = []
                for root in _iter_unique_roots(getattr(army, "units", []) or []):
                    if not _unit_active(root):
                        continue
                    try:
                        if not root.has_any_keyword("AELDARI"):
                            continue
                        if not root.has_any_keyword("VEHICLE"):
                            continue
                    except Exception:
                        continue
                    if not _model_in_unit_range(bearer, root, 3.0):
                        continue
                    candidates.append(root)

                if not candidates:
                    continue
                ability_name = str(getattr(getattr(unit, "enhancement", None), "name", "") or "Spirit Stone of Raelyth").strip()
                self._queue_aeldari_spirit_stone_heal(
                    player=player,
                    source_unit=unit,
                    model=bearer,
                    candidates=candidates,
                    ability_name=ability_name,
                    range_inches=3,
                    allow_skip=True,
                )

    def _on_phase_start_tears_of_isha(self, player=None, phase=None, **_kwargs) -> None:
        """Spiritseer: Tears of Isha selection at start of Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Tears of Isha requires an army for {player.name}.")
        game_map = getattr(self, "map", None)
        if game_map is None:
            raise RuntimeError("Tears of Isha requires a game map.")

        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0

        queue = getattr(self, "decision_queue", None)
        pending_model_ids = set()
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "tears_of_isha_target":
                    continue
                mid = str(ctx.get("model_id", "") or "")
                if mid:
                    pending_model_ids.add(mid)

        def _unit_has_keyword(root, keyword: str) -> bool:
            if not keyword:
                return True
            try:
                return bool(root.has_any_keyword(keyword) or root.has_keyword(keyword))
            except Exception:
                pass
            try:
                keys = list(getattr(root, "keywords", []) or []) + list(getattr(root, "faction_keywords", []) or [])
            except Exception:
                keys = []
            return any(str(k or "").strip().upper() == str(keyword).strip().upper() for k in keys)

        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                if not getattr(unit, "deployed", True):
                    continue
            except Exception:
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            for model in list(getattr(unit, "models", []) or []):
                if model is None:
                    continue
                try:
                    if not getattr(model, "is_alive", True):
                        continue
                except Exception:
                    continue
                mid = str(get_entity_id(model) or "")
                if mid and mid in pending_model_ids:
                    continue
                specs = unit.model_tears_of_isha_specs(model) or []
                if not specs:
                    continue
                seen_specs = set()
                for spec in list(specs or []):
                    ability_name = str(spec.get("source", "") or "Tears of Isha").strip() or "Tears of Isha"
                    key = (mid, ability_name.lower())
                    if key in seen_specs:
                        continue
                    seen_specs.add(key)
                    keyword = str(spec.get("keyword", "") or "").strip()
                    try:
                        rng = int(spec.get("range", 0) or 0)
                    except Exception:
                        rng = 0
                    if rng <= 0:
                        continue
                    candidates = []
                    seen_units = set()
                    for cand in list(getattr(army, "units", []) or []):
                        if cand is None:
                            continue
                        try:
                            root = cand.get_attached_unit_root()
                        except Exception:
                            root = cand
                        rid = str(get_entity_id(root) or "")
                        if not rid or rid in seen_units:
                            continue
                        seen_units.add(rid)
                        try:
                            if not getattr(root, "is_alive", lambda: False)():
                                continue
                        except Exception:
                            continue
                        try:
                            if not getattr(root, "deployed", True):
                                continue
                        except Exception:
                            continue
                        try:
                            if root.is_in_reserves() or root.is_embarked:
                                continue
                        except Exception:
                            pass
                        if not _unit_has_keyword(root, keyword):
                            continue
                        sr = getattr(root, "special_rules", None)
                        if isinstance(sr, dict):
                            if str(sr.get("tears_of_isha_selected_turn_owner", "") or "") == owner_id:
                                try:
                                    selected_turn = int(sr.get("tears_of_isha_selected_turn", 0) or 0)
                                except Exception:
                                    selected_turn = 0
                                if selected_turn == int(turn or 0):
                                    continue
                        if not self._unit_within_range_of_model(model, root, range_value=float(rng)):
                            continue
                        candidates.append(root)
                    if not candidates:
                        continue
                    try:
                        candidates = sorted(candidates, key=lambda u: str(get_entity_id(u) or ""))
                    except Exception:
                        candidates = list(candidates)
                    options = [
                        DecisionOption.create(
                            str(getattr(cand, "name", "Unit") or "Unit"),
                            payload={"target_unit_id": get_entity_id(cand)},
                        )
                        for cand in list(candidates)
                    ]
                    if not options:
                        continue
                    ctx = {
                        "ability": "tears_of_isha_target",
                        "ability_name": ability_name,
                        "phase": "Command phase",
                        "unit": getattr(unit, "name", "") or "",
                        "unit_id": get_entity_id(unit),
                        "source_unit_id": get_entity_id(unit),
                        "model": getattr(model, "name", "") or "",
                        "model_id": mid,
                        "range": int(rng),
                        "keyword": keyword,
                    }
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_QUARRY,
                        f"{ability_name}: select a unit.",
                        player_id=getattr(player, "id", None),
                        options=options,
                        context=ctx,
                    )
                    self.request_decision(request)

    def _on_phase_start_word_of_phoenix(self, player=None, phase=None, **_kwargs) -> None:
        """Word of the Phoenix (Psychic): return destroyed bodyguard models on a 2+."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Word of the Phoenix requires an army for {player.name}.")

        from ..utility.event_bus import append_dice

        seen_roots = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            rid = str(get_entity_id(root) or "")
            if not rid or rid in seen_roots:
                continue
            seen_roots.add(rid)
            try:
                if not getattr(root, "deployed", True):
                    continue
            except Exception:
                continue
            try:
                if root.is_in_reserves() or root.is_embarked:
                    continue
            except Exception:
                pass

            specs = root.leading_word_of_phoenix_specs() or []
            if not specs:
                continue
            for spec in list(specs or []):
                leader = spec.get("leader")
                if leader is None:
                    continue
                try:
                    if not getattr(leader, "is_alive", lambda: False)():
                        continue
                except Exception:
                    continue
                try:
                    if leader.get_attached_unit_root() is not root:
                        continue
                except Exception:
                    pass
                ability_name = str(spec.get("source", "") or "Word of the Phoenix").strip() or "Word of the Phoenix"
                roll = int(get_roll("D6") or 0)
                if append_dice and player is not None:
                    append_dice(player, f"{ability_name} roll: {roll}")
                if roll < 2:
                    continue
                amount = int(get_roll("D3") or 0) + 1
                if amount <= 0:
                    continue
                destroyed = list(getattr(root, "models_lost", []) or [])
                if destroyed:
                    filtered = []
                    for m in destroyed:
                        try:
                            pu = getattr(m, "parent_unit", None)
                            if pu is not None and hasattr(pu, "has_support_weapon_ability"):
                                if pu.has_support_weapon_ability():
                                    continue
                        except Exception:
                            pass
                        filtered.append(m)
                    destroyed = filtered
                if not destroyed:
                    continue
                allowed_ids = [get_entity_id(m) for m in destroyed if get_entity_id(m)]
                self._queue_bodyguard_return_decision(
                    player=player,
                    leader_unit=leader,
                    bodyguard_unit=root,
                    ability={"name": ability_name},
                    remaining=int(amount),
                    allowed_model_ids=allowed_ids,
                    allow_skip=False,
                )

    def _on_phase_start_voice_of_command(self, player=None, phase=None, **_kwargs) -> None:
        """Astra Militarum: issue Orders at the start of the Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            raise RuntimeError("Voice of Command requires an active player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Voice of Command requires an army for {player.name}.")
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None or not mgr._army_has_voice():
            return

        mgr.clear_orders_for_player(player)

        officers = mgr.get_eligible_officers(game=self, player=player, phase_name=pname, trigger="command_phase_start")
        if not officers:
            return
        if player.has_control():
            es = getattr(self, "event_system", None)
            if es is None or not hasattr(es, "subscribers"):
                raise RuntimeError("Event system missing for Voice of Command prompt.")
            subs = getattr(es, "subscribers", None)
            if not isinstance(subs, dict):
                raise RuntimeError("Event system subscribers not configured.")
            if subs.get("voice_of_command_prompt"):
                es.publish(
                    "voice_of_command_prompt",
                    player=player,
                    game=self,
                    phase_name=pname,
                    trigger="command_phase_start",
                )
                return
        return

    def _on_phase_end_voice_of_command(self, player=None, phase=None, **_kwargs) -> None:
        """Astra Militarum: issue Orders at end of phase if an Officer disembarked or was set up."""
        if player is None:
            raise RuntimeError("Voice of Command phase end requires an active player.")
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if not pname:
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Voice of Command phase end requires an army for {player.name}.")
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None or not mgr._army_has_voice():
            return
        officers = mgr.get_eligible_officers(game=self, player=player, phase_name=pname, trigger="phase_end")
        if not officers:
            return
        if player.has_control():
            es = getattr(self, "event_system", None)
            if es is None or not hasattr(es, "subscribers"):
                raise RuntimeError("Event system missing for Voice of Command prompt.")
            subs = getattr(es, "subscribers", None)
            if not isinstance(subs, dict):
                raise RuntimeError("Event system subscribers not configured.")
            if subs.get("voice_of_command_prompt"):
                es.publish(
                    "voice_of_command_prompt",
                    player=player,
                    game=self,
                    phase_name=pname,
                    trigger="phase_end",
                )
                return
        return

    def _on_phase_start_custodes_enhancements(self, player=None, phase=None, **_kwargs) -> None:
        """Lions of the Emperor enhancements that trigger at the start of the Fight phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Custodes enhancement hooks require an army for {player.name}.")
        mgr = getattr(army, "adeptus_custodes_detachments", None)
        if mgr is None or not mgr.is_lions_of_the_emperor():
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            raise RuntimeError("Custodes enhancement hooks require a game map.")

        from ..utility.aura_utils import count_enemy_models_within_range

        for unit in list(army.units):
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_fierce_conqueror"):
                continue
            bearer_id = sr.get("enhancement_fierce_conqueror_bearer_id") or sr.get("enhancement_bearer_model_id")
            if not bearer_id:
                continue
            bearer_model = None
            for model in list(getattr(unit, "models", []) or []):
                if str(getattr(model, "id", "") or "") != str(bearer_id):
                    continue
                if not getattr(model, "is_alive", True):
                    continue
                bearer_model = model
                break
            if bearer_model is None:
                continue
            enemy_models = count_enemy_models_within_range(bearer_model, 6.0, game=self, game_map=game_map)
            attacks_bonus = int(enemy_models // 5) * 2
            sr["enhancement_bearer_melee_attacks_bonus"] = int(attacks_bonus)
            sr["enhancement_bearer_melee_attacks_bonus_expires_phase"] = "FIGHT_PHASE"
            sr["enhancement_fierce_conqueror_enemy_models"] = int(enemy_models)
            unit.special_rules = sr

    def _on_phase_end_gate_of_infinity(self, player=None, phase=None, **_kwargs) -> None:
        """Grey Knights: Gate of Infinity at the end of the opponent's Fight phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if player is None:
            raise RuntimeError("Gate of Infinity prompt requires a player.")
        opponents = [p for p in (self.players or []) if p is not None and p is not player]
        if not opponents:
            return
        for opp in opponents:
            if opp is None:
                continue
            army = opp.get_army()
            if army is None:
                raise RuntimeError(f"Gate of Infinity requires an army for {opp.name}.")
            mgr = getattr(army, "gate_of_infinity", None)
            if mgr is None or not mgr._army_has_gate():
                continue
            max_units = int(mgr.get_max_units_for_battlefield(self))
            if max_units <= 0:
                continue
            eligible = list(mgr.get_eligible_units(game=self, player=opp) or [])
            if not eligible:
                continue
            if opp.has_control():
                es = getattr(self, "event_system", None)
                if es is None or not hasattr(es, "subscribers"):
                    raise RuntimeError("Event system missing for Gate of Infinity prompt.")
                subs = getattr(es, "subscribers", None)
                if not isinstance(subs, dict):
                    raise RuntimeError("Event system subscribers not configured.")
                if subs.get("gate_of_infinity_prompt"):
                    es.publish(
                        "gate_of_infinity_prompt",
                        player=opp,
                        game=self,
                        max_units=max_units,
                    )
                continue
            continue

    def _maybe_prompt_end_of_opponent_turn_strategic_reserves(self, turn_ending_player=None) -> None:
        """Optional end-of-opponent-turn: remove eligible units to Strategic Reserves."""
        if turn_ending_player is None:
            return
        game_map = self.map
        if game_map is None:
            raise RuntimeError("Strategic reserves prompt requires a game map.")

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

    def _on_phase_end_for_the_greater_good(self, player=None, phase=None, **_kwargs) -> None:
        """Clear For the Greater Good state at the end of the Shooting phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            raise RuntimeError("For the Greater Good requires an active player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"For the Greater Good requires an army for {player.name}.")
        mgr = getattr(army, "for_the_greater_good", None)
        if mgr is None:
            return
        mgr.on_shooting_phase_end(game=self, player=player)

    def _on_phase_end_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Best-effort cleanup for model-level temporary effects that expire at end of a phase."""
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Phase-end cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Phase-end cleanup requires an army for {p.name}.")
            for u in list(army.units):
                for m in list(u.models):
                    fn = getattr(m, "on_phase_end", None)
                    if callable(fn):
                        fn(phase)
        # Unit-level temporary effects (e.g. detachment abilities that last until end of turn)
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        active_name = str(getattr(player, "id", "") or "") if player is not None else ""
        if not pname:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Phase-end cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Phase-end cleanup requires an army for {p.name}.")
            if pname == "SHOOTING_PHASE":
                deathstrike_mgr = getattr(army, "deathstrike", None)
                if deathstrike_mgr is not None:
                    deathstrike_mgr.clear_phase_usage()
            for u in list(army.units):
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
                exp = str(sr.get("maddened_ferocity_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "maddened_ferocity_melee_attacks_bonus",
                        "maddened_ferocity_expires_phase",
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
                exp = str(sr.get("path_of_warrior_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("path_of_warrior_choice", "path_of_warrior_expires_phase"):
                        sr.pop(k, None)
                exp = str(sr.get("post_shoot_no_cover_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "post_shoot_no_cover_active",
                        "post_shoot_no_cover_expires_phase",
                        "post_shoot_no_cover_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("guiding_presence_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "guiding_presence_active",
                        "guiding_presence_bonus",
                        "guiding_presence_expires_phase",
                        "guiding_presence_source",
                        "guiding_presence_owner",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("post_shoot_ap_bonus_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "post_shoot_ap_bonus_active",
                        "post_shoot_ap_bonus_expires_phase",
                        "post_shoot_ap_bonus_source",
                        "post_shoot_ap_bonus_value",
                        "post_shoot_ap_bonus_keyword",
                        "post_shoot_ap_bonus_attack_type",
                        "post_shoot_ap_bonus_owner",
                        "post_shoot_ap_bonus_turn",
                    ):
                        sr.pop(k, None)
                    selected_scope = str(sr.get("post_shoot_ap_bonus_selected_scope", "") or "").strip().lower()
                    if selected_scope == "phase":
                        selected_phase = str(sr.get("post_shoot_ap_bonus_selected_phase", "") or "").strip().upper()
                        if not selected_phase or selected_phase == pname:
                            for k in (
                                "post_shoot_ap_bonus_selected_owner",
                                "post_shoot_ap_bonus_selected_turn",
                                "post_shoot_ap_bonus_selected_scope",
                                "post_shoot_ap_bonus_selected_phase",
                            ):
                                sr.pop(k, None)
                exp = str(sr.get("post_shoot_disembark_wound_reroll_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "post_shoot_disembark_wound_reroll_active",
                        "post_shoot_disembark_wound_reroll_expires_phase",
                        "post_shoot_disembark_wound_reroll_source",
                        "post_shoot_disembark_wound_reroll_target_id",
                        "post_shoot_disembark_wound_reroll_owner",
                        "post_shoot_disembark_wound_reroll_turn",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("herald_of_ynnead_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "herald_of_ynnead_active",
                        "herald_of_ynnead_expires_phase",
                        "herald_of_ynnead_source",
                        "herald_of_ynnead_keyword",
                        "herald_of_ynnead_owner",
                        "herald_of_ynnead_turn",
                    ):
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
                exp = str(sr.get("daemonic_patrons_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "daemonic_patrons_active",
                        "daemonic_patrons_called",
                        "daemonic_patrons_expires_phase",
                        "daemonic_patrons_crit_wound_threshold",
                        "daemonic_patrons_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("enhancement_fight_first_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "enhancement_fight_first_active",
                        "enhancement_fight_first_expires_phase",
                        "enhancement_fight_first_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("empowered_by_death_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "empowered_by_death_active",
                        "empowered_by_death_expires_phase",
                        "empowered_by_death_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("enhancement_bearer_melee_attacks_bonus_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "enhancement_bearer_melee_attacks_bonus",
                        "enhancement_bearer_melee_attacks_bonus_expires_phase",
                        "enhancement_fierce_conqueror_enemy_models",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("seductive_gambit_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("seductive_gambit_active", "seductive_gambit_expires_phase"):
                        sr.pop(k, None)
                effects = sr.get("advance_no_roll_effects")
                if isinstance(effects, list) and effects:
                    kept = []
                    for eff in effects:
                        if not isinstance(eff, dict):
                            kept.append(eff)
                            continue
                        exp = str(eff.get("expires_phase", "") or "").strip().upper()
                        if exp and exp == pname:
                            continue
                        kept.append(eff)
                    if kept:
                        sr["advance_no_roll_effects"] = kept
                    else:
                        sr.pop("advance_no_roll_effects", None)
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
                if pname == "FIGHT_PHASE" and active_name:
                    owner = str(sr.get("wargear_charge_keyword_hits_turn_owner", "") or "")
                    if owner and owner == active_name:
                        for k in (
                            "wargear_charge_keyword_hits",
                            "wargear_charge_keyword_hits_turn_owner",
                            "wargear_charge_keyword_hits_turn",
                        ):
                            sr.pop(k, None)
                    owner = str(sr.get("post_shoot_crit_hit_threshold_owner", "") or "")
                    try:
                        turn = int(sr.get("post_shoot_crit_hit_threshold_turn", 0) or 0)
                    except Exception:
                        turn = 0
                    if owner and owner == active_name:
                        if int(turn or 0) == int(getattr(self, "turn", 0) or 0):
                            for k in (
                                "post_shoot_crit_hit_threshold_active",
                                "post_shoot_crit_hit_threshold_owner",
                                "post_shoot_crit_hit_threshold_turn",
                                "post_shoot_crit_hit_threshold_source",
                                "post_shoot_crit_hit_threshold_keyword",
                                "post_shoot_crit_hit_threshold_value",
                                "post_shoot_crit_hit_threshold_expires_phase",
                            ):
                                sr.pop(k, None)
                    owner = str(sr.get("tactical_acumen_no_charge_turn_owner", "") or "")
                    try:
                        turn = int(sr.get("tactical_acumen_no_charge_turn", 0) or 0)
                    except Exception:
                        turn = 0
                    if owner and owner == active_name:
                        if int(turn or 0) == int(getattr(self, "turn", 0) or 0):
                            for k in (
                                "tactical_acumen_no_charge_turn_owner",
                                "tactical_acumen_no_charge_turn",
                            ):
                                sr.pop(k, None)
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Phase-end cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Phase-end cleanup requires an army for {p.name}.")
            mgr = getattr(army, "battle_focus", None)
            if mgr is not None:
                mgr.cleanup_on_phase_end(phase, p)

        # Templar Vows: Uphold the Honour of the Emperor sticky objectives at end of your Command phase.
        if pname == "COMMAND_PHASE":
            if player is None:
                raise RuntimeError("Templar Vows cleanup requires an active player.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Templar Vows cleanup requires an army for {player.name}.")
            mgr = getattr(army, "templar_vows", None)
            if mgr is not None:
                mgr.on_command_phase_end(game=self, player=player)
            # Datasheet abilities: sticky objectives at end of your Command phase.
            game_map = getattr(self, "map", None)
            if game_map is None:
                raise RuntimeError("Command-phase sticky objectives require a game map.")
            objectives = list(getattr(game_map, "objectives", []) or [])
            if objectives:
                for obj in objectives:
                    loc = getattr(obj, "location", None)
                    if loc is None or getattr(loc, "removed", False):
                        continue
                    if hasattr(loc, "update_control"):
                        loc.update_control(self)
                dg_mgr = getattr(army, "death_guard_detachments", None)
                if dg_mgr is not None:
                    dg_mgr.on_command_phase_end(game=self, player=player)
                seen = set()
                for unit in list(army.units):
                    root = unit.get_attached_unit_root()
                    uid = get_entity_id(root)
                    if uid in seen:
                        continue
                    seen.add(uid)
                    if not root.attached_unit_has_command_phase_sticky_objective():
                        continue
                    for obj in objectives:
                        loc = getattr(obj, "location", None)
                        if loc is None or getattr(loc, "removed", False):
                            continue
                        if getattr(loc, "controlling_player", None) is not player:
                            continue
                        if not root.is_within_objective_range(loc):
                            sr = getattr(root, "special_rules", None)
                            allow_transport = bool(isinstance(sr, dict) and sr.get("sticky_objectives_allow_embarked_transport"))
                            if not allow_transport:
                                continue
                            transport = getattr(root, "embarked_in", None)
                            if transport is None or not transport.is_within_objective_range(loc):
                                continue
                        if hasattr(loc, "set_sticky_control"):
                            loc.set_sticky_control(player, source="unit_sticky_objective")
                        else:
                            loc.sticky_controller = player
                            loc.sticky_source = "unit_sticky_objective"
                            loc.controlling_player = player

        # Cabal of Sorcerers: Temporal Surge charge restriction ends at the end of the turn.
        if pname == "FIGHT_PHASE":
            if player is None:
                raise RuntimeError("Phase-end cleanup requires an active player.")
            owner_id = player.id
            for p in list(self.players or []):
                if p is None:
                    raise RuntimeError("Phase-end cleanup requires players.")
                army = p.get_army()
                if army is None:
                    raise RuntimeError(f"Phase-end cleanup requires an army for {p.name}.")
                for u in list(army.units):
                    sr = getattr(u, "special_rules", None)
                    if not isinstance(sr, dict):
                        continue
                    exp = str(sr.get("dance_of_death_expires_phase", "") or "").strip().upper()
                    if exp == pname:
                        for k in ("dance_of_death_choice", "dance_of_death_expires_phase"):
                            sr.pop(k, None)
                    if str(sr.get("cabal_temporal_surge_no_charge_turn_owner", "") or "") == owner_id:
                        for k in ("cabal_temporal_surge_no_charge_turn_owner", "cabal_temporal_surge_no_charge_turn"):
                            sr.pop(k, None)
                    if str(sr.get("pain_swooping_descent_no_charge_turn_owner", "") or "") == owner_id:
                        for k in ("pain_swooping_descent_no_charge_turn_owner", "pain_swooping_descent_no_charge_turn"):
                            sr.pop(k, None)
                    if str(sr.get("cloudstrider_no_charge_turn_owner", "") or "") == owner_id:
                        for k in (
                            "cloudstrider_no_charge_turn_owner",
                            "cloudstrider_no_charge_turn",
                            "cloudstrider_choice_turn_owner",
                            "cloudstrider_choice_turn",
                            "cloudstrider_deep_strike_min_distance",
                            "cloudstrider_source",
                        ):
                            sr.pop(k, None)
                    if str(sr.get("feigned_retreat_turn_owner", "") or "") == owner_id:
                        for k in ("feigned_retreat_active", "feigned_retreat_turn_owner", "feigned_retreat_turn"):
                            sr.pop(k, None)
                    if str(sr.get("manoeuvre_and_fire_turn_owner", "") or "") == owner_id:
                        for k in (
                            "manoeuvre_and_fire_active",
                            "manoeuvre_and_fire_turn_owner",
                            "manoeuvre_and_fire_turn",
                            "manoeuvre_and_fire_source",
                        ):
                            sr.pop(k, None)
                    if str(sr.get("fire_and_fade_no_charge_turn_owner", "") or "") == owner_id:
                        for k in ("fire_and_fade_no_charge_turn_owner", "fire_and_fade_no_charge_turn"):
                            sr.pop(k, None)
                    if str(sr.get("fire_and_fade_no_embark_turn_owner", "") or "") == owner_id:
                        for k in ("fire_and_fade_no_embark_turn_owner", "fire_and_fade_no_embark_turn"):
                            sr.pop(k, None)
                    if str(sr.get("grenade_pack_flyover_used_turn_owner", "") or "") == owner_id:
                        for k in (
                            "grenade_pack_flyover_used_turn_owner",
                            "grenade_pack_flyover_used_turn",
                            "grenade_pack_flyover_source",
                        ):
                            sr.pop(k, None)
                    if str(sr.get("grenade_pack_flyover_no_grenade_turn_owner", "") or "") == owner_id:
                        for k in ("grenade_pack_flyover_no_grenade_turn_owner", "grenade_pack_flyover_no_grenade_turn"):
                            sr.pop(k, None)
                    if str(sr.get("flickerjump_no_charge_turn_owner", "") or "") == owner_id:
                        for k in ("flickerjump_no_charge_turn_owner", "flickerjump_no_charge_turn"):
                            sr.pop(k, None)
                    if str(sr.get("flickerjump_move_set_turn_owner", "") or "") == owner_id:
                        for k in ("flickerjump_move_set_turn_owner", "flickerjump_move_set_turn", "flickerjump_move_set_value"):
                            sr.pop(k, None)
                    if str(sr.get("flickerjump_pending_uses_owner", "") or "") == owner_id:
                        for k in (
                            "flickerjump_pending_uses_owner",
                            "flickerjump_pending_uses_turn",
                            "flickerjump_pending_uses",
                            "flickerjump_source",
                        ):
                            sr.pop(k, None)
                    if str(sr.get("goretrack_onslaught_turn_owner", "") or "") == owner_id:
                        for k in ("goretrack_onslaught_active", "goretrack_onslaught_turn_owner", "goretrack_onslaught_turn"):
                            sr.pop(k, None)
                    if str(sr.get("ere_we_go_turn_owner", "") or "") == owner_id:
                        for k in ("ere_we_go_active", "ere_we_go_turn_owner", "ere_we_go_turn", "ere_we_go_source"):
                            sr.pop(k, None)

        # Snapshot objective control at end of each phase for "previous phase" rules.
        game_map = self.map
        if game_map is None:
            raise RuntimeError("Objective control snapshot requires a game map.")
        snapshot = {}
        for obj in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            if hasattr(loc, "update_control"):
                loc.update_control(self)
            snapshot[loc] = getattr(loc, "controlling_player", None)
        self._objective_control_snapshot = snapshot

        # Phoenix Gem: resolve pending returns at end of the phase they were destroyed in.
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname:
            pending = list(getattr(self, "_phoenix_gem_pending", []) or [])
            if pending:
                remaining = []
                for payload in pending:
                    if str(payload.get("phase_name", "") or "").strip().upper() != pname:
                        remaining.append(payload)
                        continue
                    self._resolve_phoenix_gem_return(payload)
                self._phoenix_gem_pending = remaining

    def queue_phoenix_gem_return(self, *, unit=None, model=None, position=None, phase_name=None, game_map=None, spec=None) -> None:
        if unit is None or model is None:
            return
        payload = {
            "unit": unit,
            "model": model,
            "position": position,
            "phase_name": phase_name,
            "game_map": game_map,
            "spec": spec or {},
        }
        pending = list(getattr(self, "_phoenix_gem_pending", []) or [])
        pending.append(payload)
        self._phoenix_gem_pending = pending

    def _resolve_phoenix_gem_return(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        unit = payload.get("unit")
        model = payload.get("model")
        if unit is None or model is None:
            return
        spec = payload.get("spec") or {}
        try:
            roll_min = int(spec.get("roll_min", 2) or 2)
        except Exception:
            roll_min = 2
        roll = int(get_roll("D6") or 0)
        if roll < roll_min:
            return

        try:
            base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
        except Exception:
            base_wounds = 0
        if base_wounds <= 0:
            base_wounds = 1
        wounds_spec = spec.get("wounds", "full")
        wounds = base_wounds
        if isinstance(wounds_spec, str):
            key = wounds_spec.strip().lower()
            if key == "full":
                wounds = base_wounds
            elif key == "d3":
                wounds = int(get_roll("D3") or 0)
            elif key == "d6":
                wounds = int(get_roll("D6") or 0)
            else:
                try:
                    wounds = int(key)
                except Exception:
                    wounds = base_wounds
        else:
            try:
                wounds = int(wounds_spec)
            except Exception:
                wounds = base_wounds
        if wounds <= 0:
            wounds = 1
        if wounds > base_wounds:
            wounds = base_wounds

        try:
            if hasattr(model, "set_parent_unit"):
                model.set_parent_unit(unit)
            else:
                model.parent_unit = unit
        except Exception:
            pass
        try:
            model.wounds = int(wounds)
        except Exception:
            try:
                model._wounds = int(wounds)
            except Exception:
                pass

        try:
            if hasattr(unit, "models_lost") and model in unit.models_lost:
                unit.models_lost.remove(model)
        except Exception:
            pass
        try:
            if hasattr(unit, "models") and model not in unit.models:
                unit.models.append(model)
        except Exception:
            pass

        pos = payload.get("position")
        if pos is not None:
            try:
                if hasattr(model, "set_location"):
                    model.set_location(*pos)
            except Exception:
                pass

        try:
            if hasattr(unit, "_invalidate_ability_cache"):
                unit._invalidate_ability_cache()
        except Exception:
            pass
        try:
            if hasattr(unit, "update_coherency"):
                unit.update_coherency()
        except Exception:
            pass
        try:
            unit.deployed = True
            unit.reserve_status = "deployed"
        except Exception:
            pass
        game_map = payload.get("game_map") or getattr(self, "map", None)
        if game_map is not None and hasattr(game_map, "units") and unit not in game_map.units:
            try:
                game_map.units.append(unit)
            except Exception:
                pass

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

    def _maybe_queue_spirit_mark(self, unit=None, action: str | None = None) -> None:
        if unit is None:
            return
        if not self.is_movement_phase():
            return
        action_key = str(action or "").strip().lower()
        if action_key not in ("move", "advance", "fall_back"):
            return
        try:
            if not getattr(unit, "is_alive", lambda: False)():
                return
        except Exception:
            return
        try:
            if not getattr(unit, "deployed", True):
                return
        except Exception:
            return
        try:
            if unit.is_in_reserves() or unit.is_embarked:
                return
        except Exception:
            pass
        owner = None
        try:
            owner = unit.get_parent_army().player
        except Exception:
            owner = None
        if owner is None or owner is not self.get_current_player():
            return
        try:
            army = owner.get_army()
        except Exception:
            army = None
        if army is None:
            return

        def _unit_has_keyword(root, keyword: str) -> bool:
            if not keyword:
                return True
            try:
                return bool(root.has_any_keyword(keyword) or root.has_keyword(keyword))
            except Exception:
                pass
            try:
                keys = list(getattr(root, "keywords", []) or []) + list(getattr(root, "faction_keywords", []) or [])
            except Exception:
                keys = []
            return any(str(k or "").strip().upper() == str(keyword).strip().upper() for k in keys)

        for model in list(getattr(unit, "models", []) or []):
            if model is None:
                continue
            try:
                if not getattr(model, "is_alive", True):
                    continue
            except Exception:
                continue
            specs = unit.model_spirit_mark_specs(model) or []
            if not specs:
                continue
            for spec in list(specs or []):
                keyword = str(spec.get("keyword", "") or "").strip()
                try:
                    rng = int(spec.get("range", 0) or 0)
                except Exception:
                    rng = 0
                if rng <= 0:
                    continue
                candidates = []
                seen = set()
                for cand in list(getattr(army, "units", []) or []):
                    if cand is None:
                        continue
                    try:
                        root = cand.get_attached_unit_root()
                    except Exception:
                        root = cand
                    rid = str(get_entity_id(root) or "")
                    if not rid or rid in seen:
                        continue
                    seen.add(rid)
                    try:
                        if not getattr(root, "is_alive", lambda: False)():
                            continue
                    except Exception:
                        continue
                    try:
                        if not getattr(root, "deployed", True):
                            continue
                    except Exception:
                        continue
                    try:
                        if root.is_in_reserves() or root.is_embarked:
                            continue
                    except Exception:
                        pass
                    if not _unit_has_keyword(root, keyword):
                        continue
                    try:
                        if root.has_any_keyword("TITANIC") or root.has_keyword("TITANIC"):
                            continue
                    except Exception:
                        pass
                    if not self._unit_within_range_of_model(model, root, range_value=float(rng)):
                        continue
                    candidates.append(root)
                if not candidates:
                    continue
                self._queue_spirit_mark_friendly_selection(
                    player=owner,
                    source_unit=unit,
                    model=model,
                    candidates=candidates,
                    spec=spec,
                )

    def _on_unit_move_started_spirit_mark(self, unit=None, action: str | None = None, **_kwargs) -> None:
        self._maybe_queue_spirit_mark(unit=unit, action=action)

    def _on_unit_move_ended_spirit_mark(self, unit=None, action: str | None = None, **_kwargs) -> None:
        self._maybe_queue_spirit_mark(unit=unit, action=action)

    def _player_has_optional_decision_hook(self, player, key: str) -> bool:
        if player is None:
            return False
        k = str(key or "").strip().upper()
        if not k:
            return False
        overrides = getattr(player, "_next_optional_decisions", None)
        if isinstance(overrides, dict) and k in overrides:
            return True
        return callable(getattr(player, "decision_hook", None))

    def _resolve_player_by_id(self, player_id: str | None):
        if not player_id:
            return None
        for p in list(self.players or []):
            pid = maybe_entity_id(p)
            if pid and str(pid) == str(player_id):
                return p
        return None

    def _resolve_unit_by_id(self, unit_id: str | None):
        if not unit_id:
            return None
        registry = getattr(self, "entity_registry", None)
        if registry is not None:
            unit = registry.get(str(unit_id), kind="unit")
            if unit is not None:
                return unit
        for p in list(self.players or []):
            army = p.get_army()
            if army is None:
                continue
            for u in list(getattr(army, "units", []) or []):
                uid = maybe_entity_id(u)
                if uid and str(uid) == str(unit_id):
                    return u
        return None

    def _resolve_model_by_id(self, model_id: str | None):
        if not model_id:
            return None
        registry = getattr(self, "entity_registry", None)
        if registry is not None:
            model = registry.get(str(model_id), kind="model")
            if model is not None:
                return model
        for p in list(self.players or []):
            army = p.get_army()
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                for model in list(getattr(unit, "models", []) or []):
                    mid = maybe_entity_id(model)
                    if mid and str(mid) == str(model_id):
                        return model
        return None

    def _option_id_for_payload(self, request: DecisionRequest, key: str, value: object) -> str | None:
        if request is None:
            return None
        for opt in list(getattr(request, "options", []) or []):
            payload = getattr(opt, "payload", {}) or {}
            if payload.get(key) == value:
                return opt.option_id
        return None

    def _decision_option_payload(self, request: DecisionRequest | None, result: DecisionResult | None) -> dict:
        if request is None or result is None:
            return {}
        for opt in list(getattr(request, "options", []) or []):
            if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
                return dict(getattr(opt, "payload", {}) or {})
        return {}

    def _decision_is_skip(self, request: DecisionRequest | None, result: DecisionResult | None) -> bool:
        if result is None:
            return False
        payload = dict(getattr(result, "payload", {}) or {})
        if bool(payload.get("skipped", False)):
            return True
        if str(payload.get("action", "") or "") == "skip":
            return True
        opt_payload = self._decision_option_payload(request, result)
        if bool(opt_payload.get("skip", False)):
            return True
        return str(opt_payload.get("action", "") or "") == "skip"

    def _reactive_move_context(
        self,
        *,
        kind: str,
        unit_id: str,
        movement_type: str,
        source: str,
        moving_unit_id: str | None = None,
        attacker_unit_id: str | None = None,
        range_value: int | None = None,
        allow_engagement_range: bool | None = None,
    ) -> dict:
        ctx = {
            "reactive_move_kind": str(kind or "").strip(),
            "reactive_move_unit_id": unit_id,
            "reactive_move_source": str(source or "").strip() or "Reactive Move",
            "reactive_move_movement_type": str(movement_type or "").strip(),
        }
        if moving_unit_id:
            ctx["reactive_move_moving_unit_id"] = moving_unit_id
        if attacker_unit_id:
            ctx["reactive_move_attacker_unit_id"] = attacker_unit_id
        if range_value is not None:
            ctx["reactive_move_range"] = int(range_value)
        if allow_engagement_range is not None:
            ctx["reactive_move_allow_engagement_range"] = bool(allow_engagement_range)
        return ctx

    def _queue_optional_ability_confirmation(
        self,
        *,
        player,
        ability_key: str,
        ability_name: str,
        message: str | None = None,
        context: dict | None = None,
        payload: dict | None = None,
        instance_key: str | None = None,
    ) -> DecisionRequest | None:
        if player is None:
            return None
        key = str(ability_key or "").strip().lower()
        if not key:
            return None
        instance = str(instance_key or "").strip().lower()
        existing = None
        queue = getattr(self, "decision_queue", None)
        if queue is not None:
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                req_key = str(ctx.get("ability", "") or ctx.get("ability_key", "") or "").strip().lower()
                if req_key != key:
                    continue
                if instance:
                    req_instance = str(ctx.get("ability_instance", "") or "").strip().lower()
                    if req_instance != instance:
                        continue
                if getattr(req, "player_id", None) == getattr(player, "id", None):
                    existing = req
                    break
        if existing is not None:
            return existing
        ctx = dict(context or {})
        ctx["ability"] = key
        ctx["ability_name"] = str(ability_name or "").strip() or key.replace("_", " ").title()
        if message:
            ctx["message"] = message
        if instance:
            ctx["ability_instance"] = instance
        payload = dict(payload or {})
        options = [
            DecisionOption.create("Use", payload=dict(payload, choice=True)),
            DecisionOption.create("Skip", payload=dict(payload, choice=False)),
        ]
        request = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            ctx["ability_name"],
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _unit_on_battlefield_for_reposition(self, unit) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not is_alive():
            return False
        if not getattr(unit, "deployed", True):
            return False
        if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
            return False
        if bool(getattr(unit, "embarked_in", None)) or bool(getattr(unit, "is_embarked", False)):
            return False
        is_in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(is_in_reserves) and is_in_reserves():
            return False
        return True

    def _opponent_turn_destroyed_reposition_used(self, unit, *, turn_owner_id: str | None) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        used_turn = sr.get("opponent_turn_destroyed_reposition_turn")
        if used_turn is None:
            return False
        try:
            if int(used_turn) != int(turn):
                return False
        except Exception:
            return False
        owner = str(sr.get("opponent_turn_destroyed_reposition_turn_owner", "") or "")
        if turn_owner_id:
            return owner == str(turn_owner_id)
        return bool(owner)

    def _mark_opponent_turn_destroyed_reposition_used(self, unit, *, turn_owner_id: str | None) -> None:
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            sr["opponent_turn_destroyed_reposition_turn"] = int(getattr(self, "turn", 0) or 0)
        except Exception:
            sr["opponent_turn_destroyed_reposition_turn"] = 0
        if turn_owner_id:
            sr["opponent_turn_destroyed_reposition_turn_owner"] = str(turn_owner_id)
        unit.special_rules = sr

    def _find_closest_valid_reposition_position(
        self,
        unit,
        anchor_pos,
        *,
        game_map: Map | None = None,
        radius_step: float = 0.5,
        angle_step: int = 15,
    ) -> tuple | None:
        if unit is None or anchor_pos is None:
            return None
        if game_map is None:
            game_map = getattr(self, "map", None)
        if game_map is None:
            return None
        try:
            ax = float(anchor_pos[0])
            ay = float(anchor_pos[1])
            az = float(anchor_pos[2]) if len(anchor_pos) > 2 else 0.0
        except (TypeError, ValueError, IndexError):
            return None

        try:
            models = [m for m in list(getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)]
        except Exception:
            models = []
        if len(models) != 1:
            return None
        model = models[0]
        facing = float(getattr(getattr(model, "model_base", None), "facing", 0.0) or 0.0)

        collision_fn = getattr(game_map, "check_collision_with_obstacles", None)
        if not callable(collision_fn):
            collision_fn = getattr(game_map, "check_collision_with_terrain", None)

        from ..battlefield.map import validate_ruins_placement
        from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases

        def _position_valid(x: float, y: float, z: float) -> bool:
            if hasattr(game_map, "is_within_boundary") and not game_map.is_within_boundary(model, destination=(x, y)):
                return False
            if callable(collision_fn) and collision_fn(model, destination=(x, y)):
                return False
            ruins_validation = validate_ruins_placement(unit, (x, y, z), game_map.terrain_features, moving_model=model)
            if not ruins_validation.get("valid", False):
                return False
            if hasattr(game_map, "check_collision_with_other_friendly_units"):
                if game_map.check_collision_with_other_friendly_units(model, destination=(x, y)):
                    return False
            if hasattr(game_map, "check_collision_with_other_enemy_units"):
                if game_map.check_collision_with_other_enemy_units(model, destination=(x, y)):
                    return False
            test_base = model.model_base
            if hasattr(unit, "_create_potential_base"):
                test_base = unit._create_potential_base(x, y, z, facing, model=model)
            for enemy in list(getattr(game_map, "get_enemy_units", lambda _u: [])(unit) or []):
                if hasattr(enemy, "is_alive") and callable(enemy.is_alive) and not enemy.is_alive():
                    continue
                if not getattr(enemy, "deployed", True):
                    continue
                try:
                    enemy_models = list(enemy.get_models_for_collision() or [])
                except Exception:
                    enemy_models = list(getattr(enemy, "models", []) or [])
                for em in enemy_models:
                    if not getattr(em, "is_alive", True):
                        continue
                    horiz = float(horizontal_distance_between_bases_2d(test_base, em.model_base))
                    vert = float(vertical_distance_between_bases(test_base, em.model_base))
                    if horiz <= ENGAGEMENT_RANGE_HORIZONTAL and vert <= ENGAGEMENT_RANGE_VERTICAL:
                        return False
            return True

        max_radius = float(math.hypot(float(game_map.width), float(game_map.height)))
        if max_radius <= 0:
            return None
        step = max(0.1, float(radius_step))
        deg_step = max(5, int(angle_step))

        best = None
        best_dist = None
        radius = 0.0
        while radius <= max_radius + 1e-6:
            if radius <= 1e-6:
                angles = (0,)
            else:
                angles = range(0, 360, deg_step)
            for deg in angles:
                ang = math.radians(float(deg))
                x = ax + math.cos(ang) * radius
                y = ay + math.sin(ang) * radius
                height_fn = getattr(game_map, "get_height_at_point", None)
                if callable(height_fn):
                    height = height_fn(x, y)
                    z = float(height) if height is not None else float(az)
                else:
                    z = float(az)
                if not _position_valid(x, y, z):
                    continue
                dist = float(get_dist(x - ax, y - ay, z - az))
                if best_dist is None or dist < best_dist - 1e-6:
                    best = (float(x), float(y), float(z), float(facing))
                    best_dist = dist
            if best_dist is not None and radius > best_dist + 1e-6:
                break
            radius += step
        return best

    def _queue_movement_phase_normal_move_weapon_attacks_bonus(
        self,
        *,
        player,
        unit,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        phase = getattr(self, "phase", None)
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname and pname != "MOVEMENT_PHASE":
            return None
        if player is not self.get_current_player():
            return None
        if not getattr(unit, "is_alive", lambda: False)():
            return None
        if not getattr(unit, "deployed", True):
            return None
        try:
            if unit.is_in_reserves() or unit.is_embarked:
                return None
        except Exception:
            pass

        try:
            models = list(getattr(unit, "models", []) or [])
        except Exception:
            models = []
        if not models:
            return None

        for m in models:
            if not getattr(m, "is_alive", True):
                continue
            try:
                specs = list(unit.model_movement_phase_normal_move_weapon_attacks_bonus_specs(m) or [])
            except Exception:
                specs = []
            if not specs:
                continue
            for spec in specs:
                key = str(spec.get("key") or "movement_phase_normal_move_bonus").strip().lower()
                if not key:
                    key = "movement_phase_normal_move_bonus"
                if getattr(m, "has_used_once_per_battle", lambda _k: False)(key):
                    continue
                unit_id = maybe_entity_id(unit)
                model_id = maybe_entity_id(m)
                if not unit_id or not model_id:
                    continue
                ability_name = str(spec.get("source", "") or "Movement phase normal move boost").strip()
                ctx = {
                    "ability_name": ability_name,
                    "phase": "Movement phase",
                    "unit": getattr(unit, "name", "") or "",
                    "model": getattr(m, "name", "") or "",
                    "unit_id": unit_id,
                    "model_id": model_id,
                    "move_bonus_dice": str(spec.get("move_bonus_dice", "") or ""),
                    "attacks_bonus": int(spec.get("attacks_bonus", 0) or 0),
                    "weapon_name": str(spec.get("weapon_name", "") or ""),
                    "buff_key": key,
                }
                message = (
                    f"Activate {ability_name} for {getattr(m, 'name', 'Model')} "
                    f"({getattr(unit, 'name', 'Unit')}) before Normal move?"
                )
                return self._queue_optional_ability_confirmation(
                    player=player,
                    ability_key="movement_phase_move_weapon_bonus",
                    ability_name=ability_name,
                    message=message,
                    context=ctx,
                    payload={
                        "unit_id": unit_id,
                        "model_id": model_id,
                        "move_bonus_dice": ctx["move_bonus_dice"],
                        "attacks_bonus": ctx["attacks_bonus"],
                        "weapon_name": ctx["weapon_name"],
                        "buff_key": key,
                    },
                    instance_key=f"{model_id}:{key}",
                )
        return None

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

    def _queue_movement_phase_flickerjump(
        self,
        *,
        player,
        unit,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        phase = getattr(self, "phase", None)
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname and pname != "MOVEMENT_PHASE":
            return None
        if player is not self.get_current_player():
            return None
        if not getattr(unit, "is_alive", lambda: False)():
            return None
        if not getattr(unit, "deployed", True):
            return None
        try:
            if unit.is_in_reserves() or unit.is_embarked:
                return None
        except Exception:
            pass

        try:
            specs = list(unit.unit_movement_phase_normal_move_speed_mortal_wounds_specs() or [])
        except Exception:
            specs = []
        if not specs:
            return None

        for spec in specs:
            move_value = int(spec.get("move_value", 0) or 0)
            if move_value <= 0:
                continue
            unit_id = maybe_entity_id(unit)
            if not unit_id:
                continue
            ability_name = str(spec.get("source", "") or "Flickerjump").strip()
            ctx = {
                "ability_name": ability_name,
                "phase": "Movement phase",
                "unit": getattr(unit, "name", "") or "",
                "unit_id": unit_id,
                "move_value": int(move_value),
            }
            message = (
                f"Activate {ability_name} for {getattr(unit, 'name', 'Unit')} before Normal move?"
            )
            return self._queue_optional_ability_confirmation(
                player=player,
                ability_key="flickerjump",
                ability_name=ability_name,
                message=message,
                context=ctx,
                payload={
                    "unit_id": unit_id,
                    "move_value": int(move_value),
                },
                instance_key=f"{unit_id}:flickerjump",
            )
        return None

    def _queue_movement_phase_visible_bonus(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
        bonus_kind: str,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        kind_key = str(bonus_kind or "").strip().lower()
        if kind_key not in ("hit", "wound"):
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        ability_key = f"movement_phase_visible_{kind_key}_bonus"
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != ability_key:
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        limit_once = bool(spec.get("limit_once_per_turn")) if isinstance(spec, dict) else False
        filtered = []
        for cand in sorted(list(candidates), key=_cand_sort_key):
            if limit_once:
                sr = getattr(cand, "special_rules", None)
                if isinstance(sr, dict) and sr.get(f"{ability_key}_active"):
                    if str(sr.get(f"{ability_key}_owner", "") or "") == owner_id and int(sr.get(f"{ability_key}_turn", 0) or 0) == turn:
                        continue
            filtered.append(cand)

        options = []
        for cand in filtered:
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(cand)},
                )
            )
        if not options:
            return None
        ability_name = str(spec.get("source", "") or f"Movement phase {kind_key} bonus").strip() or f"Movement phase {kind_key} bonus"
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        keyword = str(spec.get("keyword", "") or "").strip()
        try:
            bonus = int(spec.get("bonus", 0) or 0)
        except Exception:
            bonus = 0
        ctx = {
            "ability": ability_key,
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_value),
            "keyword": keyword,
            "bonus": int(bonus),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_movement_phase_visible_wound_bonus(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        return self._queue_movement_phase_visible_bonus(
            player=player,
            source_unit=source_unit,
            model=model,
            candidates=candidates,
            spec=spec,
            bonus_kind="wound",
        )

    def _queue_movement_phase_visible_hit_bonus(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        return self._queue_movement_phase_visible_bonus(
            player=player,
            source_unit=source_unit,
            model=model,
            candidates=candidates,
            spec=spec,
            bonus_kind="hit",
        )

    def _queue_movement_phase_end_misfortune(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "misfortune":
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        limit_once = bool(spec.get("limit_once_per_turn")) if isinstance(spec, dict) else False
        filtered = []
        for cand in sorted(list(candidates), key=_cand_sort_key):
            if limit_once:
                sr = getattr(cand, "special_rules", None)
                if isinstance(sr, dict):
                    if str(sr.get("misfortune_selected_owner", "") or "") == owner_id and int(sr.get("misfortune_selected_turn", 0) or 0) == int(turn or 0):
                        continue
            filtered.append(cand)
        if not filtered:
            return None

        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(cand)},
            )
            for cand in filtered
        ]
        if not options:
            return None
        ability_name = str(spec.get("source", "") or "Misfortune").strip() or "Misfortune"
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        try:
            penalty = int(spec.get("penalty", -1) or -1)
        except Exception:
            penalty = -1
        ctx = {
            "ability": "misfortune",
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_value),
            "penalty": int(penalty),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_aeldari_guiding_presence(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        ability_name: str,
        range_inches: int,
        hit_bonus: int,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "aeldari_guiding_presence":
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(cand)},
            )
            for cand in sorted(list(candidates), key=_cand_sort_key)
        ]
        if not options:
            return None
        ctx = {
            "ability": "aeldari_guiding_presence",
            "ability_name": str(ability_name or "Guiding Presence").strip(),
            "phase": "Shooting phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_inches),
            "bonus": int(hit_bonus),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ctx['ability_name']}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_aeldari_spirit_stone_heal(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        ability_name: str,
        range_inches: int,
        allow_skip: bool = True,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "aeldari_spirit_stone_heal":
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = []
        if allow_skip:
            options.append(DecisionOption.create("None", payload={"action": "skip"}))
        for cand in sorted(list(candidates), key=_cand_sort_key):
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(cand)},
                )
            )
        if not options:
            return None
        ctx = {
            "ability": "aeldari_spirit_stone_heal",
            "ability_name": str(ability_name or "Spirit Stone of Raelyth").strip(),
            "phase": "Command phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_inches),
            "allow_skip": bool(allow_skip),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ctx['ability_name']}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_spirit_mark_friendly_selection(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) not in ("spirit_mark_friendly", "spirit_mark_enemy"):
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        sr = getattr(source_unit, "special_rules", None)
        if isinstance(sr, dict):
            used_owner = str(sr.get("spirit_mark_used_turn_owner", "") or "")
            try:
                used_turn = int(sr.get("spirit_mark_used_turn", 0) or 0)
            except Exception:
                used_turn = 0
            used_ids = list(sr.get("spirit_mark_used_model_ids", []) or [])
            if owner_id and used_owner == owner_id and used_turn == int(turn or 0):
                if str(model_id) in [str(v) for v in used_ids if v]:
                    return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        for cand in sorted(list(candidates), key=_cand_sort_key):
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(cand)},
                )
            )
        if not options:
            return None
        ability_name = str(spec.get("source", "") or "Spirit Mark").strip() or "Spirit Mark"
        ctx = {
            "ability": "spirit_mark_friendly",
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(spec.get("range", 0) or 0),
            "keyword": str(spec.get("keyword", "") or "").strip(),
            "sustained_hits_value": int(spec.get("sustained_hits_value", 1) or 1),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a friendly unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_spirit_mark_enemy_selection(
        self,
        *,
        player,
        source_unit,
        model,
        friendly_unit,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None or friendly_unit is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        friendly_id = get_entity_id(friendly_unit)
        if not model_id or not unit_id or not friendly_id:
            return None

        try:
            enemies = list(getattr(self.map, "get_enemy_units")(source_unit) or [])
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
            rid = str(get_entity_id(root) or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            if not self._model_can_see_unit(model, root, game_map=getattr(self, "map", None)):
                continue
            candidates.append(root)

        if not candidates:
            return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(cand)},
            )
            for cand in sorted(list(candidates), key=_cand_sort_key)
        ]
        if not options:
            return None
        ability_name = str(spec.get("source", "") or "Spirit Mark").strip() or "Spirit Mark"
        ctx = {
            "ability": "spirit_mark_enemy",
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "friendly_unit_id": friendly_id,
            "sustained_hits_value": int(spec.get("sustained_hits_value", 1) or 1),
            "keyword": str(spec.get("keyword", "") or "").strip(),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select an enemy unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_mortal_wounds_target_decision(
        self,
        *,
        player,
        unit,
        candidates: list,
        spec: dict,
        kind: str,
        model=None,
        allow_skip: bool = False,
        phase: str | None = None,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        if not candidates:
            return None
        kind_key = str(kind or "").strip().lower()
        if kind_key not in ("charge_end", "move_over", "fight_phase_end"):
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        ability_name = str((spec or {}).get("name", "") or (spec or {}).get("source", "") or "Mortal Wounds").strip()
        if not ability_name:
            ability_name = "Mortal Wounds"

        options = []
        if allow_skip:
            options.append(DecisionOption.create("Skip", payload={"action": "skip"}))

        sorted_candidates = [c for c in candidates if c is not None]
        sorted_candidates.sort(key=lambda c: str(maybe_entity_id(c) or ""))
        used_labels = set()
        candidate_ids = []
        for enemy in sorted_candidates:
            enemy_id = maybe_entity_id(enemy)
            if not enemy_id:
                continue
            candidate_ids.append(str(enemy_id))
            label = str(getattr(enemy, "name", "") or "Enemy unit")
            base = label
            idx = 2
            while label in used_labels:
                label = f"{base} ({idx})"
                idx += 1
            used_labels.add(label)
            options.append(DecisionOption.create(label, payload={"target_unit_id": enemy_id}))

        if not options or (allow_skip and len(options) == 1):
            return None

        ctx = {
            "engine_flow": True,
            "mortal_wounds_kind": kind_key,
            "unit_id": unit_id,
            "ability_name": ability_name,
            "spec": dict(spec or {}),
            "candidate_ids": list(candidate_ids),
        }
        if model is not None:
            model_id = maybe_entity_id(model)
            if model_id:
                ctx["model_id"] = str(model_id)
        if phase:
            ctx["phase"] = str(phase)

        prompt = f"{ability_name}: Select target"
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

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

    def _unit_within_range_of_model(self, model, unit, *, range_value: float) -> bool:
        if model is None or unit is None:
            return False
        try:
            from ..utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return False
        try:
            if not getattr(model, "is_alive", True):
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

    def _queue_grenade_pack_flyover_target_decision(
        self,
        *,
        player,
        unit,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict):
            if str(sr.get("grenade_pack_flyover_used_turn_owner", "") or "") == owner_id and int(
                sr.get("grenade_pack_flyover_used_turn", 0) or 0
            ) == turn:
                return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "grenade_pack_flyover":
                    continue
                if str(ctx.get("unit_id", "")) == str(unit_id):
                    return None

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        sorted_candidates = [c for c in candidates if c is not None]
        sorted_candidates.sort(key=lambda c: str(maybe_entity_id(c) or ""))
        for enemy in sorted_candidates:
            enemy_id = maybe_entity_id(enemy)
            if not enemy_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(enemy, "name", "") or "Enemy unit"),
                    payload={"target_unit_id": enemy_id},
                )
            )
        if len(options) <= 1:
            return None

        ability_name = str(spec.get("source", "") or "Grenade Pack Flyover").strip() or "Grenade Pack Flyover"
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
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
        ctx = {
            "ability": "grenade_pack_flyover",
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "range": int(range_value),
            "threshold": int(threshold),
            "mortal_per_success": int(mortal_per),
            "max_mortal": int(max_mortal),
            "spec": dict(spec or {}),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_end_of_fight_embark_decision(
        self,
        *,
        player,
        transport,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or transport is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        transport_id = maybe_entity_id(transport)
        if not transport_id:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "end_of_fight_embark":
                    continue
                if str(ctx.get("transport_id", "")) == str(transport_id):
                    return None

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        sorted_candidates = [c for c in candidates if c is not None]
        sorted_candidates.sort(key=lambda c: str(maybe_entity_id(c) or ""))
        for unit in sorted_candidates:
            unit_id = maybe_entity_id(unit)
            if not unit_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(unit, "name", "") or "Unit"),
                    payload={"target_unit_id": unit_id},
                )
            )
        if len(options) <= 1:
            return None

        ability_name = str(spec.get("source", "") or "End of fight embark").strip() or "End of fight embark"
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        try:
            max_models = int(spec.get("max_models", 0) or 0)
        except Exception:
            max_models = 0
        keyword = str(spec.get("keyword", "") or "").strip()
        ctx = {
            "ability": "end_of_fight_embark",
            "ability_name": ability_name,
            "phase": "Fight phase",
            "unit": getattr(transport, "name", "") or "",
            "unit_id": transport_id,
            "transport_id": transport_id,
            "range": int(range_value),
            "max_models": int(max_models),
            "keyword": keyword,
            "spec": dict(spec or {}),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a unit to embark.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_reactive_move_confirmation(
        self,
        *,
        player,
        unit,
        kind: str,
        movement_type: str,
        source: str | None,
        message: str | None,
        moving_unit=None,
        attacker_unit=None,
        range_value: int | None = None,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        moving_unit_id = maybe_entity_id(moving_unit) if moving_unit is not None else None
        attacker_unit_id = maybe_entity_id(attacker_unit) if attacker_unit is not None else None
        source = str(source or "").strip() or "Reactive Move"
        if not message and moving_unit is not None and range_value is not None:
            enemy_name = getattr(moving_unit, "name", "Enemy unit")
            message = (
                f"{enemy_name} ended a move within {int(range_value)}\" of {getattr(unit, 'name', 'unit')}.\n\n"
                f"{source}: Make a Normal move of up to D6\"?"
            )
        options = [
            DecisionOption.create("Move", payload={"choice": True}),
            DecisionOption.create("Skip", payload={"choice": False}),
        ]
        ctx = self._reactive_move_context(
            kind=str(kind or "").strip() or "reactive",
            unit_id=unit_id,
            movement_type=movement_type,
            source=source,
            moving_unit_id=moving_unit_id,
            attacker_unit_id=attacker_unit_id,
            range_value=range_value,
        )
        if message:
            ctx["message"] = message
        request = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            source,
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_bodyguard_return_decision(
        self,
        *,
        player,
        leader_unit,
        bodyguard_unit,
        ability: dict,
        remaining: int,
        allowed_model_ids: list[str] | None = None,
        allow_skip: bool = True,
    ) -> DecisionRequest | None:
        if player is None or leader_unit is None or bodyguard_unit is None:
            return None
        if int(remaining or 0) <= 0:
            return None
        bodyguard_id = maybe_entity_id(bodyguard_unit)
        if not bodyguard_id:
            return None
        leader_id = maybe_entity_id(leader_unit)
        if not leader_id:
            return None
        destroyed = list(getattr(bodyguard_unit, "models_lost", []) or [])
        allowed_set = {str(v) for v in list(allowed_model_ids or []) if v}
        if allowed_set:
            destroyed = [m for m in destroyed if str(get_entity_id(m) or "") in allowed_set]
        if not destroyed:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None:
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_ALLOCATE_DAMAGE:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("selection_kind", "") or "") != "bodyguard_return":
                    continue
                if str(ctx.get("leader_unit_id", "") or "") != str(leader_id):
                    continue
                if str(ctx.get("bodyguard_unit_id", "") or "") != str(bodyguard_id):
                    continue
                return req
        try:
            destroyed_sorted = sorted(destroyed, key=lambda m: str(get_entity_id(m) or ""))
        except Exception:
            destroyed_sorted = list(destroyed)
        ability_name = str(ability.get("name", "") or "Bodyguard Return")
        options = []
        if allow_skip:
            options.append(DecisionOption.create("None", payload={"model_id": None, "action": "skip"}))
        used_labels = set()
        for model in destroyed_sorted:
            label = str(getattr(model, "name", "") or "Model")
            base = label
            idx = 2
            while label in used_labels:
                label = f"{base} [{idx}]"
                idx += 1
            used_labels.add(label)
            options.append(DecisionOption.create(label, payload={"model_id": get_entity_id(model)}))
        allowed_ids = [get_entity_id(m) for m in destroyed_sorted if get_entity_id(m)]
        ctx = {
            "selection_kind": "bodyguard_return",
            "ability_name": ability_name,
            "phase": "Command phase",
            "leader_unit_id": leader_id,
            "unit_id": bodyguard_id,
            "bodyguard_unit_id": bodyguard_id,
            "amount": int(remaining or 0),
            "remaining": int(remaining or 0),
            "reason": f"{ability_name}: Return bodyguard model",
            "allowed_model_ids": allowed_ids,
            "allow_skip": bool(allow_skip),
        }
        request = DecisionRequest.create(
            DECISION_ALLOCATE_DAMAGE,
            f"{ability_name}: Return bodyguard model",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_reactive_move_movement_decision(
        self,
        *,
        player,
        unit,
        max_distance: int,
        kind: str,
        movement_type: str,
        source: str | None,
        moving_unit=None,
        attacker_unit=None,
        range_value: int | None = None,
        allow_engagement_range: bool | None = None,
        allowed_model_ids: list[str] | None = None,
        allow_skip: bool | None = None,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        moving_unit_id = maybe_entity_id(moving_unit) if moving_unit is not None else None
        attacker_unit_id = maybe_entity_id(attacker_unit) if attacker_unit is not None else None
        source = str(source or "").strip() or "Reactive Move"
        options = [
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit_id, "movement_type": movement_type, "action": "confirm"},
            ),
            DecisionOption.create(
                "Skip",
                payload={"unit_id": unit_id, "movement_type": movement_type, "action": "skip"},
            ),
        ]
        ctx = self._reactive_move_context(
            kind=str(kind or "").strip() or "reactive",
            unit_id=unit_id,
            movement_type=movement_type,
            source=source,
            moving_unit_id=moving_unit_id,
            attacker_unit_id=attacker_unit_id,
            range_value=range_value,
            allow_engagement_range=allow_engagement_range,
        )
        ctx["unit_id"] = unit_id
        ctx["movement_type"] = movement_type
        ctx["max_distance"] = int(max_distance)
        if allowed_model_ids is not None:
            ctx["allowed_model_ids"] = list(allowed_model_ids)
        if allow_skip is not None:
            ctx["allow_skip"] = bool(allow_skip)
        request = DecisionRequest.create(
            DECISION_MOVE_UNIT,
            f"Move {getattr(unit, 'name', 'Unit')} ({movement_type})",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_battle_focus_reactive_selection(
        self,
        *,
        player,
        candidates: list,
        manager,
        maneuver: str,
        moving_unit=None,
        attacker_unit=None,
        hits_by_unit: dict | None = None,
    ) -> DecisionRequest | None:
        if player is None or not candidates:
            return None
        if manager is None:
            return None
        maneuver_key = str(maneuver or "").strip().lower()
        if maneuver_key not in ("opportunity", "fade_back"):
            return None
        try:
            sorted_candidates = sorted(
                [c for c in candidates if c is not None],
                key=lambda c: str(maybe_entity_id(c) or ""),
            )
        except Exception:
            sorted_candidates = [c for c in candidates if c is not None]
        prompt = "Select Battle Focus reactive unit." if maneuver_key == "opportunity" else "Select Battle Focus unit to fade back."
        options = [DecisionOption.create("Skip", payload={"action": "skip"})]
        used_labels = set()
        for unit in sorted_candidates:
            label = str(getattr(unit, "name", "") or "Unit")
            if maneuver_key == "fade_back":
                try:
                    hits = int((hits_by_unit or {}).get(unit, 0) or 0)
                except Exception:
                    hits = 0
                label = f"{label} (Hits: {hits})"
            base = label
            idx = 2
            while label in used_labels:
                label = f"{base} [{idx}]"
                idx += 1
            used_labels.add(label)
            options.append(
                DecisionOption.create(
                    label,
                    payload={"unit_id": get_entity_id(unit)},
                )
            )
        ctx = {
            "ability": "battle_focus",
            "maneuver": maneuver_key,
            "reactive_move_kind": "battle_focus",
            "reactive_move_movement_type": "reactive",
        }
        if moving_unit is not None:
            moving_unit_id = maybe_entity_id(moving_unit)
            if moving_unit_id:
                ctx["reactive_move_moving_unit_id"] = moving_unit_id
        if attacker_unit is not None:
            attacker_unit_id = maybe_entity_id(attacker_unit)
            if attacker_unit_id:
                ctx["reactive_move_attacker_unit_id"] = attacker_unit_id
        request = DecisionRequest.create(
            DECISION_SELECT_OVERWATCH_SHOOTER,
            prompt,
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _maybe_queue_reactive_move_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        decision_type = str(getattr(request, "decision_type", "") or "")
        if decision_type == DECISION_CONFIRM_YES_NO:
            ctx = dict(getattr(request, "context", {}) or {})
            kind = str(ctx.get("reactive_move_kind", "") or "").strip()
            if kind not in ("loping_speed", "blood_surge", "brazen_fury"):
                return
            opt = None
            for candidate in list(getattr(request, "options", []) or []):
                if getattr(candidate, "option_id", None) == getattr(result, "option_id", None):
                    opt = candidate
                    break
            if opt is None:
                return
            payload = getattr(opt, "payload", {}) or {}
            choice = bool(payload.get("choice", False))
            if not choice:
                return
            unit_id = str(ctx.get("reactive_move_unit_id") or ctx.get("unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id)
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if unit is None or player is None:
                return
            source = str(ctx.get("reactive_move_source", "") or "Reactive Move").strip() or "Reactive Move"
            movement_type = str(ctx.get("reactive_move_movement_type", "") or "")
            if kind == "loping_speed":
                moving_unit_id = str(ctx.get("reactive_move_moving_unit_id") or "")
                moving_unit = self._resolve_unit_by_id(moving_unit_id)
                if moving_unit is None:
                    return
                rng = int(ctx.get("reactive_move_range") or 9)
                if not unit.can_loping_speed(
                    game=self,
                    game_map=getattr(self, "map", None),
                    moving_unit=moving_unit,
                    range_override=rng,
                ):
                    return
                max_distance = int(self.roll_loping_speed_distance(unit) or 0)
                if max_distance <= 0:
                    return
                self._queue_reactive_move_movement_decision(
                    player=player,
                    unit=unit,
                    moving_unit=moving_unit,
                    max_distance=max_distance,
                    kind=kind,
                    movement_type=movement_type or "loping_speed",
                    source=source,
                    range_value=rng,
                )
                return
            if kind == "blood_surge":
                if not unit.can_blood_surge(game=self, game_map=getattr(self, "map", None)):
                    return
                max_distance = int(self.roll_blood_surge_distance(unit) or 0)
                if max_distance <= 0:
                    return
                attacker_unit_id = str(ctx.get("reactive_move_attacker_unit_id") or "")
                attacker_unit = self._resolve_unit_by_id(attacker_unit_id)
                self._queue_reactive_move_movement_decision(
                    player=player,
                    unit=unit,
                    attacker_unit=attacker_unit,
                    max_distance=max_distance,
                    kind=kind,
                    movement_type=movement_type or "blood_surge",
                    source=source,
                )
                return
            if kind == "brazen_fury":
                if not unit.can_brazen_fury(game=self, game_map=getattr(self, "map", None)):
                    return
                max_distance = int(self.roll_brazen_fury_distance(unit) or 0)
                if max_distance <= 0:
                    return
                attacker_unit_id = str(ctx.get("reactive_move_attacker_unit_id") or "")
                attacker_unit = self._resolve_unit_by_id(attacker_unit_id)
                self._queue_reactive_move_movement_decision(
                    player=player,
                    unit=unit,
                    attacker_unit=attacker_unit,
                    max_distance=max_distance,
                    kind=kind,
                    movement_type=movement_type or "brazen_fury",
                    source=source,
                )
                return
        if decision_type == DECISION_SELECT_OVERWATCH_SHOOTER:
            ctx = dict(getattr(request, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "battle_focus":
                return
            opt = None
            for candidate in list(getattr(request, "options", []) or []):
                if getattr(candidate, "option_id", None) == getattr(result, "option_id", None):
                    opt = candidate
                    break
            if opt is None:
                return
            payload = getattr(opt, "payload", {}) or {}
            if bool(result.payload.get("skipped", False)) or str(payload.get("action", "") or "") == "skip":
                return
            unit_id = str(payload.get("unit_id", "") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if unit is None or player is None:
                return
            army = player.get_army()
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            if mgr is None:
                return
            maneuver = str(ctx.get("maneuver", "") or "").strip().lower()
            moving_unit_id = str(ctx.get("reactive_move_moving_unit_id") or "")
            attacker_unit_id = str(ctx.get("reactive_move_attacker_unit_id") or "")
            moving_unit = self._resolve_unit_by_id(moving_unit_id) if moving_unit_id else None
            attacker_unit = self._resolve_unit_by_id(attacker_unit_id) if attacker_unit_id else None
            if maneuver == "opportunity":
                applied = bool(mgr.apply_reactive_maneuver(unit, mgr.MANEUVER_OPPORTUNITY, self, moving_unit=moving_unit))
            elif maneuver == "fade_back":
                applied = bool(mgr.apply_reactive_maneuver(unit, mgr.MANEUVER_FADE_BACK, self, attacker_unit=attacker_unit))
            else:
                return
            if not applied:
                return
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                return
            if sr.get("battle_focus_reactive_move_pending"):
                return
            try:
                max_distance = int(sr.get("battle_focus_reactive_move_max", 0) or 0)
            except Exception:
                max_distance = 0
            if max_distance <= 0:
                return
            source = str(sr.get("battle_focus_reactive_move_source", "") or "Battle Focus").strip() or "Battle Focus"
            self._queue_reactive_move_movement_decision(
                player=player,
                unit=unit,
                moving_unit=moving_unit,
                attacker_unit=attacker_unit,
                max_distance=max_distance,
                kind="battle_focus",
                movement_type="reactive",
                source=source,
            )
        if decision_type == DECISION_MOVE_UNIT:
            ctx = dict(getattr(request, "context", {}) or {})
            kind = str(ctx.get("reactive_move_kind", "") or "").strip()
            if kind != "careen":
                return
            opt = None
            for candidate in list(getattr(request, "options", []) or []):
                if getattr(candidate, "option_id", None) == getattr(result, "option_id", None):
                    opt = candidate
                    break
            payload = getattr(opt, "payload", {}) or {}
            skipped = bool(getattr(result, "payload", {}).get("skipped", False)) or bool(payload.get("skip", False)) or str(payload.get("action", "") or "") == "skip"
            unit_id = str(ctx.get("reactive_move_unit_id") or ctx.get("unit_id") or payload.get("unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            unit.resolve_careen_deadly_demise(game_map=getattr(self, "map", None), use_move=not skipped)
        return

    def _maybe_apply_optional_ability_confirmation(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        decision_type = str(getattr(request, "decision_type", "") or "")
        if decision_type != DECISION_CONFIRM_YES_NO:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        ability_key = str(ctx.get("ability", "") or ctx.get("ability_key", "") or "").strip().lower()
        if ability_key not in (
            "shadow_in_the_warp",
            "waaagh",
            "possessed_lord",
            "fight_phase_melee_ap_boost",
            "start_any_phase_damage_set_one",
            "start_any_phase_fnp",
            "movement_phase_move_weapon_bonus",
            "hand_of_asuryan",
            "flickerjump",
            "daemonic_patrons",
            "power_from_pain_command",
            "power_from_pain_empower",
            "enhancement_fight_first",
            "opponent_turn_strategic_reserves",
            "opponent_turn_destroyed_reposition",
            "cloudstrider",
            "seductive_gambit",
            "sensational_performance",
            "cult_ambush",
            "battle_focus_flitting_shadows",
            "battle_focus_sudden_strike",
            "battle_focus_fade_back",
            "sentinel_storm",
            "sweeping_advance",
        ):
            return
        selected = None
        for opt in list(getattr(request, "options", []) or []):
            if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
                selected = opt
                break
        payload = dict(getattr(selected, "payload", {}) or {}) if selected is not None else {}
        choice = None
        if "choice" in payload:
            choice = bool(payload.get("choice"))
        elif "choice" in getattr(result, "payload", {}):
            choice = bool(result.payload.get("choice"))
        if not choice:
            return

        if ability_key == "shadow_in_the_warp":
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            army = player.get_army()
            mgr = getattr(army, "shadow_in_the_warp", None) if army is not None else None
            if mgr is None:
                return
            if not mgr.can_use_now(game=self, player=player):
                return
            mgr.activate(game=self, player=player)
            return

        if ability_key == "waaagh":
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            army = player.get_army()
            mgr = getattr(army, "waaagh", None) if army is not None else None
            if mgr is None:
                return
            if not mgr.can_call_now(game=self, player=player):
                return
            mgr.call_waaagh(game=self, player=player)
            return

        if ability_key == "possessed_lord":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            if getattr(model, "has_used_once_per_battle", lambda _k: False)("possessed_lord"):
                return
            if not getattr(model, "is_alive", True):
                return
            model.activate_possessed_lord()
            return

        if ability_key == "fight_phase_melee_ap_boost":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            key = str(payload.get("buff_key") or ctx.get("buff_key") or "fight_phase_melee_ap_boost").strip().lower()
            if not key:
                key = "fight_phase_melee_ap_boost"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(ctx.get("ability_name", "") or "Fight phase melee boost").strip()
            model.activate_fight_phase_melee_ap_boost(key=key, ability_name=ability_name)
            return

        if ability_key == "start_any_phase_damage_set_one":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            key = str(payload.get("buff_key") or ctx.get("buff_key") or "start_any_phase_damage_set_one").strip().lower()
            if not key:
                key = "start_any_phase_damage_set_one"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(ctx.get("ability_name", "") or "Start of phase damage set to 1").strip()
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            if hasattr(model, "set_temporary_damage_taken_override"):
                model.set_temporary_damage_taken_override(
                    key=key,
                    value=1,
                    source=ability_name,
                    expires_phase=phase_name,
                )
            model.mark_used_once_per_battle(key, ability_name=ability_name, source="datasheet")
            return

        if ability_key == "start_any_phase_fnp":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            try:
                if not getattr(root, "deployed", True):
                    return
                if root.is_in_reserves() or root.is_embarked:
                    return
            except Exception:
                pass
            ability_name = str(ctx.get("ability_name", "") or "Start of phase FNP").strip()
            ability_key = str(payload.get("ability_key") or ctx.get("ability_key") or "start_any_phase_fnp").strip().lower()
            if not ability_key:
                ability_key = "start_any_phase_fnp"
            if root.has_used_unit_once_per_battle(ability_key):
                return
            try:
                fnp_val = int(ctx.get("fnp_value", 0) or 0)
            except Exception:
                fnp_val = 0
            if fnp_val <= 0:
                return
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            for m in list(models or []):
                if not getattr(m, "is_alive", False):
                    continue
                if hasattr(m, "set_temporary_fnp"):
                    m.set_temporary_fnp(
                        key=f"{ability_key}:{get_entity_id(m)}",
                        value=fnp_val,
                        source=ability_name,
                        expires_phase=phase_name,
                    )
            root.mark_unit_once_per_battle_used(ability_key, ability_name=ability_name)
            return

        if ability_key == "sweeping_advance":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not unit_id or not model_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            model = self._resolve_model_by_id(model_id)
            if unit is None or model is None:
                return
            if not unit.is_alive() or not getattr(unit, "deployed", True):
                return
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    return
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                    return
            except Exception:
                return
            key = str(payload.get("ability_key") or ctx.get("ability_key") or "sweeping_advance").strip().lower()
            if not key:
                key = "sweeping_advance"
            try:
                if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                    return
            except Exception:
                return
            ability_name = str(ctx.get("ability_name", "") or "Sweeping Advance").strip() or "Sweeping Advance"

            engaged = False
            try:
                enemies = list(getattr(self.map, "get_enemy_units", lambda _u: [])(root) or [])
            except Exception:
                enemies = []
            for enemy in list(enemies or []):
                if enemy is None or not enemy.is_alive():
                    continue
                try:
                    if self.map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
                except Exception:
                    continue

            movement_type = "fall_back" if engaged else "move"
            try:
                max_distance = int(root.get_effective_model_characteristic(model, "movement", game_map=self.map) or 0)
            except Exception:
                max_distance = 0
            if max_distance <= 0:
                try:
                    max_distance = int(getattr(root, "movement", 0) or 0)
                except Exception:
                    max_distance = 0
            if max_distance <= 0:
                return

            model.mark_used_once_per_battle(key, ability_name=ability_name, source="datasheet")
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            self._queue_reactive_move_movement_decision(
                player=player,
                unit=root,
                max_distance=max_distance,
                kind="sweeping_advance",
                movement_type=movement_type,
                source=ability_name,
                allow_skip=False,
            )
            return

        if ability_key == "movement_phase_move_weapon_bonus":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            key = str(payload.get("buff_key") or ctx.get("buff_key") or "movement_phase_normal_move_bonus").strip().lower()
            if not key:
                key = "movement_phase_normal_move_bonus"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Movement phase normal move boost").strip()
            move_bonus_dice = str(payload.get("move_bonus_dice") or ctx.get("move_bonus_dice") or "")
            weapon_name = str(payload.get("weapon_name") or ctx.get("weapon_name") or "")
            try:
                attacks_bonus = int(payload.get("attacks_bonus") or ctx.get("attacks_bonus") or 0)
            except Exception:
                attacks_bonus = 0
            model.activate_movement_phase_move_weapon_bonus(
                key=key,
                ability_name=ability_name,
                move_bonus_dice=move_bonus_dice,
                weapon_name=weapon_name,
                attacks_bonus=attacks_bonus,
            )
            return

        if ability_key == "hand_of_asuryan":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            if getattr(model, "has_used_once_per_battle", lambda _k: False)("hand_of_asuryan"):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Hand of Asuryan").strip()
            weapon_name = str(payload.get("weapon_name") or ctx.get("weapon_name") or "Bloody Twins").strip()
            model.activate_hand_of_asuryan(
                key="hand_of_asuryan",
                ability_name=ability_name,
                weapon_name=weapon_name,
            )
            return

        if ability_key == "flickerjump":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                move_value = int(payload.get("move_value") or ctx.get("move_value") or 0)
            except Exception:
                move_value = 0
            if move_value <= 0:
                return
            ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Flickerjump").strip()
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            owner_id = str(getattr(request, "player_id", "") or getattr(result, "player_id", "") or "")
            if not owner_id:
                try:
                    owner_id = str(unit.get_parent_army().player.id)
                except Exception:
                    owner_id = ""
            turn = int(getattr(self, "turn", 0) or 0)
            sr["flickerjump_move_set_value"] = int(move_value)
            sr["flickerjump_move_set_turn"] = int(turn)
            if owner_id:
                sr["flickerjump_move_set_turn_owner"] = owner_id
                sr["flickerjump_no_charge_turn_owner"] = owner_id
                sr["flickerjump_pending_uses_owner"] = owner_id
            sr["flickerjump_no_charge_turn"] = int(turn)
            sr["flickerjump_pending_uses_turn"] = int(turn)
            sr["flickerjump_pending_uses"] = int(sr.get("flickerjump_pending_uses", 0) or 0) + 1
            if ability_name:
                sr["flickerjump_source"] = ability_name
            unit.special_rules = sr
            return

        if ability_key == "sentinel_storm":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            try:
                if not getattr(root, "deployed", True):
                    return
                if root.is_in_reserves() or root.is_embarked:
                    return
            except Exception:
                pass
            ability_name = str(ctx.get("ability_name", "") or "Shoot again").strip()
            ability_key = str(payload.get("ability_key") or ctx.get("ability_key") or "post_shoot_shoot_again").strip().lower()
            if not ability_key:
                ability_key = "post_shoot_shoot_again"
            if root.has_used_unit_once_per_battle(ability_key):
                return
            root.mark_unit_once_per_battle_used(ability_key, ability_name=ability_name)
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            self._queue_shoot_again_decision(player=player, unit=root, source=ability_name)
            return

        if ability_key == "daemonic_patrons":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if sr.get("daemonic_patrons_active"):
                return
            try:
                threshold = int(payload.get("crit_wound_threshold") or ctx.get("crit_wound_threshold") or 3)
            except Exception:
                threshold = 3
            if threshold < 2 or threshold > 6:
                threshold = 3
            source = str(payload.get("ability_name") or ctx.get("ability_name") or "Daemonic Patrons").strip() or "Daemonic Patrons"
            sr["daemonic_patrons_active"] = True
            sr["daemonic_patrons_called"] = True
            sr["daemonic_patrons_expires_phase"] = "FIGHT_PHASE"
            sr["daemonic_patrons_crit_wound_threshold"] = int(threshold)
            sr["daemonic_patrons_source"] = source
            root.special_rules = sr
            try:
                from ..utility.event_bus import append_action
                player = getattr(root.get_parent_army(), "player", None)
                if player is not None:
                    append_action(
                        player,
                        f"{source}: {getattr(root, 'name', 'Unit')} called upon daemonic patrons.",
                    )
            except Exception:
                pass
            return

        if ability_key == "power_from_pain_command":
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            army = player.get_army()
            mgr = getattr(army, "power_from_pain", None) if army is not None else None
            if mgr is None:
                return
            can_fn = getattr(mgr, "has_command_phase_action", None)
            if callable(can_fn) and not bool(can_fn(game=self, player=player)):
                return
            resolve_fn = getattr(mgr, "resolve_command_phase_action", None)
            if callable(resolve_fn):
                resolve_fn(game=self, player=player)
            return

        if ability_key == "power_from_pain_empower":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            trigger = str(payload.get("trigger") or ctx.get("trigger") or "")
            if not unit_id or not trigger:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            army = unit.get_parent_army()
            mgr = getattr(army, "power_from_pain", None) if army is not None else None
            if mgr is None:
                return
            mgr.empower_unit_for_trigger(unit, trigger=trigger, game=self)
            return

        if ability_key == "enhancement_fight_first":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            can_use = getattr(unit, "can_use_enhancement_fight_first", None)
            if callable(can_use) and not bool(can_use()):
                return
            activate = getattr(unit, "activate_enhancement_fight_first", None)
            if callable(activate):
                activate()
            return

        if ability_key == "opponent_turn_strategic_reserves":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            per_battle = bool(payload.get("once_per_battle")) or bool(ctx.get("once_per_battle"))
            per_battle_key = str(payload.get("ability_key") or ctx.get("ability_key") or "opponent_turn_strategic_reserves").strip().lower()
            used = unit.enter_strategic_reserves_midgame(
                game=self,
                game_map=getattr(self, "map", None),
                reason="end of opponent turn",
            )
            if used:
                from ..utility.event_bus import append_action
                player = getattr(unit.get_parent_army(), "player", None)
                ability_name = str(ctx.get("ability_name", "") or "Strategic Reserves")
                if player is not None:
                    append_action(
                        player,
                        f"{ability_name}: {getattr(unit, 'name', 'Unit')} placed into Strategic Reserves.",
                    )
                if per_battle and per_battle_key:
                    unit.mark_unit_once_per_battle_used(per_battle_key, ability_name=ability_name)
            return

        if ability_key == "opponent_turn_destroyed_reposition":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            if not self._unit_on_battlefield_for_reposition(unit):
                return
            turn_owner_id = str(
                ctx.get("turn_owner_id")
                or getattr(getattr(self, "get_current_player", lambda: None)(), "id", "")
                or ""
            )
            if self._opponent_turn_destroyed_reposition_used(unit, turn_owner_id=turn_owner_id):
                return
            placement = ctx.get("placement_position")
            if isinstance(placement, (list, tuple)) and len(placement) >= 4:
                placement_pos = placement
            else:
                anchor = ctx.get("destroyed_position")
                placement_pos = self._find_closest_valid_reposition_position(
                    unit,
                    anchor,
                    game_map=getattr(self, "map", None),
                )
            if not placement_pos:
                return
            try:
                models = [m for m in list(getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)]
            except Exception:
                models = []
            if len(models) != 1:
                return
            model = models[0]
            model.set_location(
                float(placement_pos[0]),
                float(placement_pos[1]),
                float(placement_pos[2]),
                float(placement_pos[3]),
            )
            unit.position = (float(placement_pos[0]), float(placement_pos[1]), float(placement_pos[2]))
            if getattr(self, "map", None) is not None and hasattr(self.map, "units"):
                if unit not in self.map.units:
                    self.map.units.append(unit)
            self._mark_opponent_turn_destroyed_reposition_used(unit, turn_owner_id=turn_owner_id)
            try:
                if hasattr(self, "event_system"):
                    self.event_system.publish("unit_set_up", unit=unit)
            except Exception:
                pass
            try:
                from ..utility.event_bus import append_action
                player = getattr(unit.get_parent_army(), "player", None)
                ability_name = str(ctx.get("ability_name", "") or "Reposition")
                if player is not None:
                    append_action(
                        player,
                        f"{ability_name}: {getattr(unit, 'name', 'Unit')} repositioned after a friendly unit was destroyed.",
                    )
            except Exception:
                pass
            return

        if ability_key == "cloudstrider":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            owner_id = str(getattr(request, "player_id", "") or getattr(result, "player_id", "") or "")
            if not owner_id:
                try:
                    owner_id = str(root.get_parent_army().player.id)
                except Exception:
                    owner_id = ""
            turn = int(getattr(self, "turn", 0) or 0)
            sr["cloudstrider_deep_strike_min_distance"] = 6.0
            sr["cloudstrider_choice_turn"] = int(turn)
            if owner_id:
                sr["cloudstrider_choice_turn_owner"] = owner_id
                sr["cloudstrider_no_charge_turn_owner"] = owner_id
            sr["cloudstrider_no_charge_turn"] = int(turn)
            source = str(ctx.get("ability_name", "") or "Cloudstrider").strip() or "Cloudstrider"
            sr["cloudstrider_source"] = source
            root.special_rules = sr
            try:
                from ..utility.event_bus import append_action
                player = getattr(root.get_parent_army(), "player", None)
                if player is not None:
                    append_action(
                        player,
                        f"{source}: {getattr(root, 'name', 'Unit')} may Deep Strike more than 6\" away (no charge).",
                    )
            except Exception:
                pass
            return

        if ability_key == "seductive_gambit":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["seductive_gambit_active"] = True
            sr["seductive_gambit_expires_phase"] = "FIGHT_PHASE"
            unit.special_rules = sr
            return

        if ability_key == "sensational_performance":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if sr.get("sensational_performance_active"):
                return
            sr["sensational_performance_active"] = True
            sr["sensational_performance_expires_phase"] = "FIGHT_PHASE"
            sr["sensational_performance_strength_bonus"] = 1
            sr["sensational_performance_ap_bonus"] = 1
            unit.special_rules = sr
            try:
                from ..utility.event_bus import append_action
                player = getattr(unit.get_parent_army(), "player", None)
                if player is not None:
                    append_action(
                        player,
                        f"Sensational Performance: {getattr(unit, 'name', 'Unit')} gains bonuses this Fight phase.",
                    )
            except Exception:
                pass
            return

        if ability_key == "cult_ambush":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            army = unit.get_parent_army()
            mgr = getattr(army, "cult_ambush", None) if army is not None else None
            if mgr is None:
                return
            player = getattr(army, "player", None)
            mgr.handle_unit_destroyed(unit, game=self, player=player)
            return

        if ability_key in ("battle_focus_flitting_shadows", "battle_focus_sudden_strike", "battle_focus_fade_back"):
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            army = unit.get_parent_army()
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            if mgr is None:
                return
            if ability_key == "battle_focus_flitting_shadows":
                mgr._apply_maneuver(unit, mgr.MANEUVER_FLITTING, self)
                return
            if ability_key == "battle_focus_sudden_strike":
                mgr._apply_maneuver(unit, mgr.MANEUVER_SUDDEN_STRIKE, self)
                return
            if ability_key == "battle_focus_fade_back":
                mgr._apply_reactive_move(unit, mgr.MANEUVER_FADE_BACK, self)
                return

    def _setup_reactive_can_shoot_target(self, unit, target_unit) -> bool:
        if unit is None or target_unit is None:
            return False
        if not unit.is_alive() or not target_unit.is_alive():
            return False
        game_map = getattr(self, "map", None)
        if game_map is None:
            return False
        if bool(getattr(getattr(unit, "round_state", None), "action_locked_until_turn_end", False)):
            return False
        if bool(getattr(unit, "_reserves_edge_touch_this_turn", False)) and bool(
            getattr(unit, "arrived_from_reserves_this_turn", False)
        ):
            return False
        for model in list(getattr(unit, "models", []) or []):
            if not getattr(model, "is_alive", True):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                if not wargear.is_ranged():
                    continue
                profiles = getattr(wargear, "profiles", {}) or {}
                for profile in list(profiles.values()):
                    if profile is None:
                        continue
                    validation = unit._validate_shooting_declaration(profile, target_unit, [model], game_map)
                    if bool(validation.get("valid", False)):
                        return True
        return False

    def _setup_reactive_available_actions(self, unit, target_unit) -> list[str]:
        actions: list[str] = []
        if unit is None or target_unit is None:
            return actions
        if self._setup_reactive_can_shoot_target(unit, target_unit):
            actions.append("shoot")
        if unit.can_declare_charge_against(target_unit, self, out_of_turn=True):
            actions.append("charge")
        return actions

    def _queue_setup_reactive_target_decision(
        self,
        *,
        player,
        unit,
        candidates: list,
        rule: dict | None,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        if not candidates:
            return None
        sorted_candidates = [c for c in candidates if c is not None]
        sorted_candidates.sort(key=lambda c: str(maybe_entity_id(c) or ""))
        source = str((rule or {}).get("source", "") or "Reactive Response").strip() or "Reactive Response"
        rng = int((rule or {}).get("range", 12) or 12)
        options = [DecisionOption.create("None", payload={"action": "skip"})]
        used_labels = set()
        for enemy in sorted_candidates:
            enemy_id = maybe_entity_id(enemy)
            if not enemy_id:
                continue
            label = str(getattr(enemy, "name", "") or "Enemy unit")
            base = label
            idx = 2
            while label in used_labels:
                label = f"{base} ({idx})"
                idx += 1
            used_labels.add(label)
            options.append(DecisionOption.create(label, payload={"unit_id": enemy_id}))
        ctx = {
            "setup_reactive_flow": True,
            "setup_reactive_source": source,
            "setup_reactive_range": int(rng),
            "setup_reactive_unit_id": unit_id,
            "unit_id": unit_id,
            "setup_reactive_candidate_ids": [maybe_entity_id(c) for c in sorted_candidates if maybe_entity_id(c)],
        }
        request = DecisionRequest.create(
            DECISION_SELECT_SETUP_REACTIVE_TARGET,
            f"{source}: Select enemy unit",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_setup_reactive_action_decision(
        self,
        *,
        player,
        unit,
        target_unit,
        actions: list[str],
        source: str | None,
    ) -> DecisionRequest | None:
        if player is None or unit is None or target_unit is None:
            return None
        if not actions:
            return None
        unit_id = maybe_entity_id(unit)
        target_id = maybe_entity_id(target_unit)
        if not unit_id or not target_id:
            return None
        opts = []
        if "shoot" in actions:
            opts.append(DecisionOption.create("Shoot", payload={"action": "shoot"}))
        if "charge" in actions:
            opts.append(DecisionOption.create("Charge", payload={"action": "charge"}))
        if not opts:
            return None
        source = str(source or "Reactive Response").strip() or "Reactive Response"
        ctx = {
            "setup_reactive_flow": True,
            "setup_reactive_source": source,
            "setup_reactive_unit_id": unit_id,
            "unit_id": unit_id,
            "target_unit_id": target_id,
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
            f"{source}: Choose action",
            player_id=getattr(player, "id", None),
            options=opts,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_setup_reactive_shooting_decision(
        self,
        *,
        player,
        unit,
        target_unit,
        source: str | None,
    ) -> DecisionRequest | None:
        if player is None or unit is None or target_unit is None:
            return None
        unit_id = maybe_entity_id(unit)
        target_id = maybe_entity_id(target_unit)
        if not unit_id or not target_id:
            return None
        options = [
            DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": unit_id}),
            DecisionOption.create("Skip", payload={"action": "skip", "unit_id": unit_id}),
        ]
        source = str(source or "Reactive Response").strip() or "Reactive Response"
        ctx = {
            "unit_id": unit_id,
            "out_of_phase": True,
            "force_target_unit_id": target_id,
            "setup_reactive_source": source,
        }
        request = DecisionRequest.create(
            DECISION_DECLARE_SHOTS,
            f"{source}: Declare shots for {getattr(unit, 'name', 'Unit')}",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_shoot_again_decision(
        self,
        *,
        player,
        unit,
        source: str | None,
    ) -> DecisionRequest | None:
        """Queue a standard shooting declaration for a unit that can shoot again."""
        if player is None or unit is None:
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        options = [
            DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": unit_id}),
            DecisionOption.create("Skip", payload={"action": "skip", "unit_id": unit_id}),
        ]
        source = str(source or "Shoot again").strip() or "Shoot again"
        ctx = {
            "unit_id": unit_id,
            "out_of_phase": True,
            "shoot_again_source": source,
        }
        request = DecisionRequest.create(
            DECISION_DECLARE_SHOTS,
            f"{source}: Declare shots for {getattr(unit, 'name', 'Unit')}",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _maybe_queue_setup_reactive_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if not bool(ctx.get("setup_reactive_flow", False)):
            return
        decision_type = str(getattr(request, "decision_type", "") or "")

        def _get_payload():
            for opt in list(getattr(request, "options", []) or []):
                if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
                    return dict(getattr(opt, "payload", {}) or {})
            return {}

        def _is_skip(payload: dict) -> bool:
            if bool((getattr(result, "payload", {}) or {}).get("skipped", False)):
                return True
            if str((getattr(result, "payload", {}) or {}).get("action", "") or "") == "skip":
                return True
            return str(payload.get("action", "") or "") == "skip"

        if decision_type == DECISION_SELECT_SETUP_REACTIVE_TARGET:
            payload = _get_payload()
            if _is_skip(payload):
                unit_id = str(ctx.get("setup_reactive_unit_id") or ctx.get("unit_id") or "")
                unit = self._resolve_unit_by_id(unit_id)
                if unit is not None:
                    unit.clear_setup_reactive_shoot_or_charge_candidates(self)
                return
            target_id = str(payload.get("unit_id") or payload.get("target_unit_id") or "")
            unit_id = str(ctx.get("setup_reactive_unit_id") or ctx.get("unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id)
            target_unit = self._resolve_unit_by_id(target_id)
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if unit is None or target_unit is None or player is None:
                return
            actions = self._setup_reactive_available_actions(unit, target_unit)
            if not actions:
                unit.clear_setup_reactive_shoot_or_charge_candidates(self)
                return
            source = str(ctx.get("setup_reactive_source", "") or "Reactive Response").strip() or "Reactive Response"
            self._queue_setup_reactive_action_decision(
                player=player,
                unit=unit,
                target_unit=target_unit,
                actions=actions,
                source=source,
            )
            return

        if decision_type == DECISION_CHOOSE_SETUP_REACTIVE_ACTION:
            payload = _get_payload()
            if _is_skip(payload):
                unit_id = str(ctx.get("setup_reactive_unit_id") or ctx.get("unit_id") or "")
                unit = self._resolve_unit_by_id(unit_id)
                if unit is not None:
                    unit.clear_setup_reactive_shoot_or_charge_candidates(self)
                return
            action = str(payload.get("action", "") or "")
            if action not in ("shoot", "charge"):
                return
            unit_id = str(ctx.get("setup_reactive_unit_id") or ctx.get("unit_id") or "")
            target_id = str(ctx.get("target_unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id)
            target_unit = self._resolve_unit_by_id(target_id)
            if unit is None or target_unit is None:
                return
            unit.mark_setup_reactive_shoot_or_charge_used(self)
            unit.clear_setup_reactive_shoot_or_charge_candidates(self)
            source = str(ctx.get("setup_reactive_source", "") or "Reactive Response").strip() or "Reactive Response"
            if action == "shoot":
                if not self._setup_reactive_can_shoot_target(unit, target_unit):
                    return
                player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
                if player is None:
                    return
                self._queue_setup_reactive_shooting_decision(
                    player=player,
                    unit=unit,
                    target_unit=target_unit,
                    source=source,
                )
                return
            if action == "charge":
                if not unit.can_declare_charge_against(target_unit, self, out_of_turn=True):
                    return
                # Charge declaration/roll/move should be handled via decision flow (UI/headless).
                return
            return

    def _maybe_queue_reverberating_summons_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if not bool(ctx.get("engine_flow", False)):
            return
        decision_type = str(getattr(request, "decision_type", "") or "")

        def _get_payload():
            for opt in list(getattr(request, "options", []) or []):
                if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
                    return dict(getattr(opt, "payload", {}) or {})
            return {}

        def _is_skip(payload: dict) -> bool:
            if bool((getattr(result, "payload", {}) or {}).get("skipped", False)):
                return True
            if str((getattr(result, "payload", {}) or {}).get("action", "") or "") == "skip":
                return True
            return str(payload.get("action", "") or "") == "skip"

        if decision_type == DECISION_SELECT_REVERBERATING_SUMMONS_UNIT:
            payload = _get_payload()
            if _is_skip(payload):
                return
            unit_id = str(payload.get("unit_id") or payload.get("unit") or "")
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            destroyed = list(getattr(unit, "models_lost", []) or [])
            if not destroyed:
                return
            from .decisions import DecisionOption, DecisionRequest

            options = [DecisionOption.create("None", payload={"model_id": None, "action": "skip"})]
            for model in destroyed:
                options.append(
                    DecisionOption.create(
                        getattr(model, "name", "Model"),
                        payload={"model_id": get_entity_id(model)},
                    )
                )
            req = DecisionRequest.create(
                DECISION_ALLOCATE_DAMAGE,
                "Select destroyed Plaguebearer model to return.",
                player_id=getattr(request, "player_id", None),
                options=options,
                context={
                    "engine_flow": True,
                    "selection_kind": "reverberating_summons_return",
                    "unit_id": unit_id,
                    "ability_name": ctx.get("ability_name", "") or "Reverberating Summons",
                },
            )
            self.request_decision(req)
            return

        if decision_type == DECISION_ALLOCATE_DAMAGE:
            if str(ctx.get("selection_kind", "") or "") != "reverberating_summons_return":
                return
            payload = _get_payload()
            if _is_skip(payload):
                return
            unit_id = str(ctx.get("unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            model_id = payload.get("model_id")
            if model_id in (None, ""):
                return
            model = self.entity_registry.get(str(model_id), kind="model")
            if model is None:
                return
            unit.return_destroyed_bodyguard_models(
                1,
                game_map=getattr(self, "map", None),
                chosen_models=[model],
            )
            return

    def _maybe_queue_bodyguard_return_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_ALLOCATE_DAMAGE:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("selection_kind", "") or "") != "bodyguard_return":
            return

        def _get_payload():
            for opt in list(getattr(request, "options", []) or []):
                if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
                    return dict(getattr(opt, "payload", {}) or {})
            return {}

        def _is_skip(payload: dict) -> bool:
            if bool((getattr(result, "payload", {}) or {}).get("skipped", False)):
                return True
            if str((getattr(result, "payload", {}) or {}).get("action", "") or "") == "skip":
                return True
            if str(payload.get("action", "") or "") == "skip":
                return True
            return payload.get("model_id") in (None, "")

        payload = _get_payload()
        if _is_skip(payload):
            return
        model_id = payload.get("model_id")
        if model_id in (None, ""):
            return
        model = None
        registry = getattr(self, "entity_registry", None)
        if registry is not None:
            model = registry.get(str(model_id), kind="model")
        if model is None:
            for p in list(self.players or []):
                army = p.get_army()
                if army is None:
                    continue
                for unit in list(getattr(army, "units", []) or []):
                    for candidate in list(getattr(unit, "models_lost", []) or []):
                        if str(getattr(candidate, "_id", "")) == str(model_id):
                            model = candidate
                            break
                    if model is not None:
                        break
                if model is not None:
                    break
        if model is None:
            return

        leader_id = str(ctx.get("leader_unit_id", "") or "")
        bodyguard_id = str(ctx.get("bodyguard_unit_id", "") or ctx.get("unit_id", "") or "")
        leader = self._resolve_unit_by_id(leader_id) if leader_id else None
        bodyguard = self._resolve_unit_by_id(bodyguard_id) if bodyguard_id else None
        if leader is None and bodyguard is None:
            return
        caller = leader if leader is not None else bodyguard
        returned = caller.return_destroyed_bodyguard_models(
            1,
            game_map=getattr(self, "map", None),
            chosen_models=[model],
        )
        ability_name = str(ctx.get("ability_name", "") or "Bodyguard Return")
        if returned > 0:
            try:
                from ..utility.event_bus import append_action
                player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
                if player is not None and bodyguard is not None:
                    append_action(
                        player,
                        f"{ability_name}: returned {getattr(model, 'name', 'Model')} to {getattr(bodyguard, 'name', 'Unit')}.",
                    )
            except Exception:
                pass
        if returned <= 0:
            return

        remaining = int(ctx.get("remaining", 0) or 0)
        remaining = max(0, remaining - 1)
        if remaining <= 0:
            return
        if bodyguard is None:
            return
        if not list(getattr(bodyguard, "models_lost", []) or []):
            return
        self._queue_bodyguard_return_decision(
            player=self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None)),
            leader_unit=leader if leader is not None else caller,
            bodyguard_unit=bodyguard,
            ability={"name": ability_name},
            remaining=remaining,
            allowed_model_ids=list(ctx.get("allowed_model_ids") or []),
            allow_skip=bool(ctx.get("allow_skip", True)),
        )

    def _maybe_apply_mortal_wounds_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if not bool(ctx.get("engine_flow", False)):
            return
        kind = str(ctx.get("mortal_wounds_kind", "") or "").strip().lower()
        if kind not in ("charge_end", "move_over", "fight_phase_end"):
            return
        if self._decision_is_skip(request, result):
            return
        payload = self._decision_option_payload(request, result)
        target_id = payload.get("target_unit_id", payload.get("unit_id"))
        target_unit = self._resolve_unit_by_id(str(target_id or ""))
        if target_unit is None:
            return
        unit_id = str(ctx.get("unit_id", "") or "")
        unit = self._resolve_unit_by_id(unit_id)
        if unit is None:
            return
        spec = dict(ctx.get("spec", {}) or {})
        if kind == "charge_end":
            self.resolve_charge_end_mortal_wounds(unit, target_unit, spec)
            return
        model_id = str(ctx.get("model_id", "") or "")
        model = self._resolve_model_by_id(model_id) if model_id else None
        if kind == "move_over":
            self.resolve_move_over_mortal_wounds(unit, model, target_unit, spec)
            if spec.get("once_per_battle"):
                ability_key = str(spec.get("ability_key") or "").strip().lower()
                if ability_key:
                    try:
                        root = unit.get_attached_unit_root()
                    except Exception:
                        root = unit
                    if root is not None:
                        ability_name = str(spec.get("source", "") or "Move-over mortals").strip() or "Move-over mortals"
                        root.mark_unit_once_per_battle_used(ability_key, ability_name=ability_name)
            return
        if model is None:
            return
        if kind == "fight_phase_end":
            self.resolve_fight_phase_end_mortal_wounds(unit, model, target_unit, spec)
            return

    def _maybe_apply_bodyguard_loss_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_ALLOCATE_DAMAGE:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("selection_kind", "") or "") != "bodyguard_loss":
            return
        payload = self._decision_option_payload(request, result)
        model_id = payload.get("model_id", payload.get("model"))
        model = self._resolve_model_by_id(str(model_id or ""))
        if model is None:
            return
        leader_id = str(ctx.get("leader_unit_id", "") or "")
        bodyguard_id = str(ctx.get("bodyguard_unit_id", "") or ctx.get("unit_id", "") or "")
        leader_unit = self._resolve_unit_by_id(leader_id)
        bodyguard = self._resolve_unit_by_id(bodyguard_id)
        if leader_unit is None or bodyguard is None:
            return
        ability_name = str(ctx.get("ability_name", "") or "Leadership Test")
        self._resolve_charge_phase_bodyguard_loss(
            leader_unit,
            bodyguard,
            model,
            {"name": ability_name},
        )

    def _maybe_apply_daemonic_patrons_loss_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_ALLOCATE_DAMAGE:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("selection_kind", "") or "") != "daemonic_patrons_loss":
            return
        payload = self._decision_option_payload(request, result)
        model_id = payload.get("model_id", payload.get("model"))
        model = self._resolve_model_by_id(str(model_id or ""))
        if model is None:
            return
        try:
            alive = getattr(model, "is_alive", True)
            alive = alive() if callable(alive) else bool(alive)
        except Exception:
            alive = True
        if not alive:
            return
        try:
            model.die(game_map=getattr(self, "map", None))
        except Exception:
            return
        try:
            from ..utility.event_bus import append_action
            unit_id = str(ctx.get("unit_id", "") or "")
            unit = self._resolve_unit_by_id(unit_id) if unit_id else None
            ability_name = str(ctx.get("ability_name", "") or "Daemonic Patrons").strip() or "Daemonic Patrons"
            player = getattr(unit.get_parent_army(), "player", None) if unit is not None else None
            if player is not None:
                append_action(
                    player,
                    f"{ability_name}: {getattr(model, 'name', 'Model')} is destroyed.",
                )
        except Exception:
            pass

    def _maybe_apply_cult_ambush_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "")) != "cult_ambush_reinforcements":
            return
        marker_id = str(ctx.get("marker_id", "") or "")
        if not marker_id:
            return
        player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
        army = player.get_army() if player is not None else None
        mgr = getattr(army, "cult_ambush", None) if army is not None else None
        if mgr is None:
            return
        marker = None
        try:
            for entry in list(getattr(mgr, "markers", []) or []):
                if str(getattr(entry, "marker_id", "")) == marker_id:
                    marker = entry
                    break
        except Exception:
            marker = None
        if marker is None:
            return
        if not bool(getattr(marker, "active", False)):
            return

        chosen_unit = None
        if not self._decision_is_skip(request, result):
            payload = self._decision_option_payload(request, result)
            unit_id = payload.get("target_unit_id", payload.get("unit_id"))
            chosen_unit = self._resolve_unit_by_id(str(unit_id or ""))
            if chosen_unit is not None:
                try:
                    mgr.deploy_unit_from_marker(chosen_unit, marker, game=self)
                except Exception:
                    pass

        remaining_marker_ids = [str(m) for m in list(ctx.get("remaining_marker_ids") or []) if str(m or "")]
        available_unit_ids = [str(u) for u in list(ctx.get("available_unit_ids") or []) if str(u or "")]
        if chosen_unit is not None:
            try:
                used_id = str(get_entity_id(chosen_unit))
            except Exception:
                used_id = ""
            if used_id:
                available_unit_ids = [uid for uid in available_unit_ids if str(uid) != used_id]
        remaining_marker_ids = [mid for mid in remaining_marker_ids if str(mid) != marker_id]

        if not remaining_marker_ids or not available_unit_ids:
            return

        next_marker_id = ""
        for mid in list(remaining_marker_ids or []):
            next_marker_id = str(mid)
            try:
                found = False
                for entry in list(getattr(mgr, "markers", []) or []):
                    if str(getattr(entry, "marker_id", "")) == next_marker_id and bool(getattr(entry, "active", False)):
                        found = True
                        break
                if found:
                    break
            except Exception:
                break
        if not next_marker_id:
            return

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for pending in list(queue.list() or []):
                if str(getattr(pending, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                pctx = getattr(pending, "context", {}) or {}
                if str(pctx.get("ability", "")) == "cult_ambush_reinforcements" and str(pctx.get("marker_id", "")) == next_marker_id:
                    return

        from ..engine.decisions import DecisionOption, DecisionRequest

        req_options = [DecisionOption.create("Skip (leave marker)", payload={"action": "skip"})]
        for uid in list(available_unit_ids or []):
            unit = self._resolve_unit_by_id(str(uid))
            if unit is None:
                continue
            req_options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"target_unit_id": str(uid)},
                )
            )
        if not req_options:
            return
        next_remaining = [mid for mid in remaining_marker_ids if str(mid) != next_marker_id]
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select Cult Ambush unit.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={
                "ability": "cult_ambush_reinforcements",
                "marker_id": next_marker_id,
                "remaining_marker_ids": list(next_remaining),
                "available_unit_ids": list(available_unit_ids),
            },
        )
        if hasattr(self, "request_decision"):
            self.request_decision(req)

    def _queue_code_chivalric_target_decision(self, mgr, player) -> bool:
        if mgr is None or player is None:
            return False
        try:
            options = list(mgr.get_eligible_character_models(game=self, player=player) or [])
        except Exception:
            options = []
        if not options:
            return False
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_SELECT_TARGET_MODEL:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("selection_kind", "")) == "code_chivalric_target":
                    return True
        from ..engine.decisions import DecisionOption, DecisionRequest
        req_options = []
        for model in options:
            unit_name = getattr(getattr(model, "parent_unit", None), "name", "")
            label = f"{getattr(model, 'name', '')} ({unit_name})" if unit_name else str(getattr(model, "name", "Model"))
            req_options.append(DecisionOption.create(label, payload={"model_id": get_entity_id(model)}))
        if not req_options:
            return False
        req = DecisionRequest.create(
            DECISION_SELECT_TARGET_MODEL,
            "Select Code Chivalric target model.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"selection_kind": "code_chivalric_target"},
        )
        if hasattr(self, "request_decision"):
            self.request_decision(req)
        return True

    def _maybe_queue_code_chivalric_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        decision_type = str(getattr(request, "decision_type", "") or "")
        ctx = dict(getattr(request, "context", {}) or {})
        player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
        army = player.get_army() if player is not None else None
        mgr = getattr(army, "code_chivalric", None) if army is not None else None
        if mgr is None:
            return

        if decision_type == DECISION_CHOOSE_CHIVALRIC_OATH:
            oath_kind = str(ctx.get("oath_kind", "") or "").strip().lower()
            if oath_kind == "deed":
                if getattr(mgr, "deed_requires_character_target", lambda: False)() and not getattr(mgr, "deed_target_model_id", None):
                    if self._queue_code_chivalric_target_decision(mgr, player):
                        return
                if not getattr(mgr, "selected_quality_key", None):
                    mgr.on_read_mission_objectives(game=self, player=player)
            elif oath_kind == "quality":
                if getattr(mgr, "deed_requires_character_target", lambda: False)() and not getattr(mgr, "deed_target_model_id", None):
                    self._queue_code_chivalric_target_decision(mgr, player)
            return

        if decision_type == DECISION_SELECT_TARGET_MODEL and str(ctx.get("selection_kind", "")) == "code_chivalric_target":
            payload = self._decision_option_payload(request, result)
            model_id = payload.get("model_id", payload.get("model"))
            model = self._resolve_model_by_id(str(model_id or ""))
            if model is not None:
                try:
                    mgr.set_deed_target_model(model)
                except Exception:
                    pass
            if not getattr(mgr, "selected_quality_key", None):
                mgr.on_read_mission_objectives(game=self, player=player)

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
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Battle Focus shooting requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        hits_by_player: dict = {}
        for target_unit, hits in (hits_by_target or {}).items():
            if target_unit is None:
                continue
            hits = int(hits or 0)
            if hits <= 0:
                continue
            target_player = target_unit.get_parent_army().player
            if target_player is attacker_player:
                continue
            hits_by_player.setdefault(target_player, {})[target_unit] = hits

        for player, hits_map in hits_by_player.items():
            if player is None:
                raise RuntimeError("Battle Focus shooting requires target players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Battle Focus shooting requires an army for {player.name}.")
            mgr = getattr(army, "battle_focus", None)
            if mgr is None:
                continue
            hit_units = list(hits_map.keys())
            if player.has_control():
                candidates = mgr.get_fade_back_candidates(hit_units, self)
                if not candidates:
                    continue
                es = getattr(self, "event_system", None)
                if es is None or not hasattr(es, "subscribers"):
                    raise RuntimeError("Event system missing for Battle Focus prompt.")
                subs = getattr(es, "subscribers", None)
                if not isinstance(subs, dict):
                    raise RuntimeError("Event system subscribers not configured.")
                if subs.get("battle_focus_fade_back_prompt"):
                    es.publish(
                        "battle_focus_fade_back_prompt",
                        player=player,
                        attacker_unit=attacker_unit,
                        candidates=list(candidates),
                        hits_by_unit=dict(hits_map),
                        manager=mgr,
                    )
            else:
                candidates = mgr.get_fade_back_candidates(hit_units, self)
                if not candidates:
                    continue
                self._queue_battle_focus_reactive_selection(
                    player=player,
                    candidates=list(candidates),
                    manager=mgr,
                    maneuver="fade_back",
                    attacker_unit=attacker_unit,
                    hits_by_unit=dict(hits_map),
                )

    def _on_unit_shooting_resolved_tactical_acumen(
        self,
        attacker_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Tactical Acumen requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return
        try:
            if not getattr(attacker_unit, "deployed", True):
                return
        except Exception:
            return
        try:
            if attacker_unit.is_in_reserves() or attacker_unit.is_embarked:
                return
        except Exception:
            pass

        specs = attacker_unit.leading_tactical_acumen_specs() or []
        if not specs:
            return

        unit_id = maybe_entity_id(attacker_unit)
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_MOVE_UNIT:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("reactive_move_kind", "") or "") != "tactical_acumen":
                    continue
                if str(ctx.get("unit_id", "") or "") == str(unit_id or ""):
                    return

        for spec in specs:
            leader = spec.get("leader")
            if leader is None:
                continue
            try:
                if not getattr(leader, "is_alive", lambda: False)():
                    continue
            except Exception:
                continue
            try:
                if leader.get_attached_unit_root() is not attacker_unit.get_attached_unit_root():
                    continue
            except Exception:
                pass
            try:
                max_distance = int(spec.get("range", 0) or 0)
            except Exception:
                max_distance = 0
            if max_distance <= 0:
                continue
            source = str(spec.get("source", "") or "Tactical Acumen").strip() or "Tactical Acumen"
            self._queue_reactive_move_movement_decision(
                player=attacker_player,
                unit=attacker_unit,
                max_distance=max_distance,
                kind="tactical_acumen",
                movement_type="reactive",
                source=source,
            )

    def _on_unit_shooting_resolved_post_shoot_battleshock(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        killing_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot Battle-shock requires an attacker player.")
        if attacker_player is not self.get_current_player():
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

        def _is_monster_or_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_keyword("MONSTER") or unit.has_keyword("VEHICLE"))
            except Exception:
                pass
            try:
                return bool(unit.has_any_keyword("MONSTER") or unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _model_killed_target(model, target) -> bool:
            if not isinstance(killing_models_by_target, dict):
                return False
            killed_models = killing_models_by_target.get(target)
            if not killed_models:
                return False
            return model in killed_models

        def _unit_killed_target(target) -> bool:
            if not isinstance(killing_models_by_target, dict):
                return False
            killed_models = killing_models_by_target.get(target)
            return bool(killed_models)

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_battleshock_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                infantry_only = bool(spec.get("infantry_only", False))
                exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if infantry_only:
                        is_infantry_fn = getattr(target_unit, "is_infantry", None)
                        if callable(is_infantry_fn):
                            is_infantry = bool(is_infantry_fn())
                        else:
                            is_infantry = bool(getattr(target_unit, "is_infantry", False))
                        if not is_infantry:
                            continue
                    if exclude_mv and _is_monster_or_vehicle(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        unit_specs = attacker_unit.unit_post_shoot_battleshock_specs() or []
        for spec in unit_specs:
            infantry_only = bool(spec.get("infantry_only", False))
            exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                if infantry_only:
                    is_infantry_fn = getattr(target_unit, "is_infantry", None)
                    if callable(is_infantry_fn):
                        is_infantry = bool(is_infantry_fn())
                    else:
                        is_infantry = bool(getattr(target_unit, "is_infantry", False))
                    if not is_infantry:
                        continue
                if exclude_mv and _is_monster_or_vehicle(target_unit):
                    continue
                candidates.append(target_unit)
            if candidates:
                triggers.append((None, spec, candidates))

        if not triggers:
            return

        from .decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
            options = []
            for cand in list(candidates):
                modifier = 0
                try:
                    modifier = int(spec.get("test_modifier", 0) or 0)
                except Exception:
                    modifier = 0
                try:
                    if spec.get("test_modifier_on_kill"):
                        if model is None:
                            if _unit_killed_target(cand):
                                modifier += int(spec.get("test_modifier_on_kill", 0) or 0)
                        else:
                            if _model_killed_target(model, cand):
                                modifier += int(spec.get("test_modifier_on_kill", 0) or 0)
                except Exception:
                    pass
                payload = {"unit_id": get_entity_id(cand)}
                if modifier:
                    payload["battle_shock_test_modifier"] = int(modifier)
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload=payload,
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
                f"{ability_name}: select a unit to take a Battle-shock test.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model) if model is not None else None,
                    "ability_name": ability_name,
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_shoot_again(
        self,
        attacker_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Shoot-again abilities require an attacker player.")
        if attacker_player is not self.get_current_player():
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        if root is None or not root.is_alive():
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass

        specs = root.unit_post_shoot_shoot_again_specs() or []
        if not specs:
            return
        for spec in list(specs or []):
            ability_name = str(spec.get("source", "") or "Shoot again").strip() or "Shoot again"
            ability_key = str(spec.get("ability_key") or "post_shoot_shoot_again").strip().lower()
            if not ability_key:
                ability_key = "post_shoot_shoot_again"
            if root.has_used_unit_once_per_battle(ability_key):
                continue
            unit_id = maybe_entity_id(root)
            ctx = {
                "ability_name": ability_name,
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "ability_key": ability_key,
                "phase": "Shooting phase",
            }
            message = f"Use {ability_name} to shoot again for {getattr(root, 'name', 'Unit')}?"
            self._queue_optional_ability_confirmation(
                player=attacker_player,
                ability_key="sentinel_storm",
                ability_name=ability_name,
                message=message,
                context=ctx,
                payload={"unit_id": unit_id, "ability_key": ability_key},
                instance_key=f"{unit_id}:{ability_key}",
            )

    def _on_unit_shooting_resolved_post_shoot_disembark_wound_reroll(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Fire Support requires an attacker player.")
        if attacker_player is not self.get_current_player():
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
            specs = attacker_unit.model_post_shoot_disembark_wound_reroll_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from .decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Fire Support").strip() or "Fire Support"
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a target.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability": "post_shoot_disembark_wound_reroll",
                    "ability_name": ability_name,
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_mortal_wounds_battleshock(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot mortal wounds requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_mortal_wounds_battleshock_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    is_infantry_fn = getattr(target_unit, "is_infantry", None)
                    if callable(is_infantry_fn):
                        is_infantry = bool(is_infantry_fn())
                    else:
                        is_infantry = bool(getattr(target_unit, "is_infantry", False))
                    if not is_infantry:
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from .decision_kinds import DECISION_CHOOSE_POST_SHOOT_MORTAL_WOUNDS_TARGET

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot Mortals").strip() or "Post-shoot Mortals"
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
                DECISION_CHOOSE_POST_SHOOT_MORTAL_WOUNDS_TARGET,
                f"{ability_name}: select a unit to suffer mortal wounds.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability_name": ability_name,
                    "dice": int(spec.get("dice", 3) or 3),
                    "threshold": int(spec.get("threshold", 4) or 4),
                    "mortal_per_success": int(spec.get("mortal_per_success", 1) or 1),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_wracking_agonies(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Wracking Agonies requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target_with_weapon(model, target, weapon_key: str) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if not models:
                return False
            return model in models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_wracking_agonies_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                weapon_key = str(spec.get("weapon_key", "") or "")
                if not weapon_key:
                    continue
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    is_infantry_fn = getattr(target_unit, "is_infantry", None)
                    if callable(is_infantry_fn):
                        is_infantry = bool(is_infantry_fn())
                    else:
                        is_infantry = bool(getattr(target_unit, "is_infantry", False))
                    if not is_infantry:
                        continue
                    if not _model_hit_target_with_weapon(model, target_unit, weapon_key):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from .decision_kinds import DECISION_CHOOSE_POST_SHOOT_WRACKED_AGONIES_TARGET

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Wracking Agonies").strip() or "Wracking Agonies"
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
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
                DECISION_CHOOSE_POST_SHOOT_WRACKED_AGONIES_TARGET,
                f"{ability_name}: select a unit wracked with agonies.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability_name": ability_name,
                    "move_penalty": int(spec.get("move_penalty", -2) or -2),
                    "charge_penalty": int(spec.get("charge_penalty", -2) or -2),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_snare(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot snare requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target_with_weapon(model, target, weapon_key: str) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if not models and weapon_key.endswith("s"):
                models = target_map.get(weapon_key[:-1])
            if not models:
                return False
            return model in models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_snare_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                weapon_key = str(spec.get("weapon_key", "") or "")
                if not weapon_key:
                    continue
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target_with_weapon(model, target_unit, weapon_key):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from .decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Snare").strip() or "Snare"
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a snare target.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability": "post_shoot_snare",
                    "ability_name": ability_name,
                    "weapon_key": str(spec.get("weapon_key", "") or ""),
                    "weapon_name": str(spec.get("weapon_name", "") or ""),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_pinned(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Pinned requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target_with_weapon(model, target, weapon_key: str) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if not models and weapon_key.endswith("s"):
                models = target_map.get(weapon_key[:-1])
            if not models:
                return False
            return model in models

        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_pinned_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                weapon_key = str(spec.get("weapon_key", "") or "")
                if not weapon_key:
                    continue
                try:
                    move_penalty = int(spec.get("move_penalty", -2) or -2)
                except Exception:
                    move_penalty = -2
                try:
                    charge_penalty = int(spec.get("charge_penalty", -2) or -2)
                except Exception:
                    charge_penalty = -2
                source = str(spec.get("source", "") or "Pinned").strip() or "Pinned"
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target_with_weapon(model, target_unit, weapon_key):
                        continue
                    try:
                        target_root = target_unit.get_attached_unit_root()
                    except Exception:
                        target_root = target_unit
                    owner_id = str(getattr(attacker_player, "id", "") or "")
                    try:
                        turn = int(getattr(self, "turn", 0) or 0)
                    except Exception:
                        turn = 0
                    apply_fn = getattr(target_root, "apply_pinned", None)
                    if callable(apply_fn):
                        apply_fn(
                            owner_id=owner_id,
                            turn=turn,
                            source=source,
                            move_penalty=int(move_penalty),
                            charge_penalty=int(charge_penalty),
                        )
                    else:
                        sr = getattr(target_root, "special_rules", None)
                        if not isinstance(sr, dict):
                            sr = {}
                        sr["pinned_active"] = True
                        sr["pinned_owner"] = owner_id
                        sr["pinned_turn"] = int(turn or 0)
                        sr["pinned_source"] = source
                        sr["pinned_move_penalty"] = int(move_penalty)
                        sr["pinned_charge_penalty"] = int(charge_penalty)
                        target_root.special_rules = sr
                    try:
                        tname = str(getattr(target_root, "name", "Unit") or "Unit")
                        _log_action_for_players(self, attacker_player, f"{source}: {tname} is pinned until your next turn.")
                    except Exception:
                        pass

    def _on_unit_shooting_resolved_harvester_of_souls(
        self,
        attacker_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None:
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        pending = list(sr.get("harvester_of_souls_pending_ids", []) or [])
        if not pending:
            return
        try:
            marked_turn = int(sr.get("harvester_of_souls_turn", 0) or 0)
        except Exception:
            marked_turn = 0
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if marked_turn and current_turn and marked_turn != current_turn:
            pending = []
        ability_name = str(sr.get("harvester_of_souls_source", "") or "Harvester of Souls").strip() or "Harvester of Souls"
        for uid in list(pending or []):
            target_unit = self._resolve_unit_by_id(uid)
            if target_unit is None or not target_unit.is_alive():
                continue
            try:
                mortal = int(get_roll("D3") or 0)
            except Exception:
                mortal = 0
            if mortal <= 0:
                continue
            root._apply_mortal_wounds_to_unit(target_unit, int(mortal), game_map=getattr(self, "map", None))
            try:
                owner = self._resolve_player_by_id(str(sr.get("harvester_of_souls_owner", "") or ""))
                if owner is not None:
                    from ..utility.event_bus import append_action
                    append_action(owner, f"{ability_name}: {getattr(target_unit, 'name', 'Unit')} suffers {int(mortal)} mortal wounds.")
            except Exception:
                pass
        for key in (
            "harvester_of_souls_pending_ids",
            "harvester_of_souls_target_id",
            "harvester_of_souls_source",
            "harvester_of_souls_owner",
            "harvester_of_souls_turn",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _on_unit_shooting_resolved_post_shoot_suppression(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot suppression requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _is_monster_or_vehicle(unit) -> bool:
            if bool(getattr(unit, "is_monster", False)) or bool(getattr(unit, "is_vehicle", False)):
                return True
            has_keyword = getattr(unit, "has_keyword", None)
            if callable(has_keyword):
                return bool(has_keyword("Monster") or has_keyword("Vehicle"))
            return False

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
            specs = attacker_unit.model_post_shoot_suppression_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if exclude_mv and _is_monster_or_vehicle(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        unit_specs = attacker_unit.unit_post_shoot_suppression_specs() or []
        if unit_specs:
            seen_sources = {str(spec.get("source", "") or "").strip().lower() for _m, spec, _c in triggers}
            for spec in unit_specs:
                source_key = str(spec.get("source", "") or "").strip().lower()
                if source_key and source_key in seen_sources:
                    continue
                exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if exclude_mv and _is_monster_or_vehicle(target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((None, spec, candidates))
                    if source_key:
                        seen_sources.add(source_key)

        if not triggers:
            return

        from .decision_kinds import DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Suppressed").strip() or "Suppressed"
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
                DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
                f"{ability_name}: select a unit to suppress.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model) if model is not None else None,
                    "ability_name": ability_name,
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_no_cover(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot no-cover requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _target_hit_with_weapon(target, weapon_key: str) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if models:
                return True
            if weapon_key.endswith("s"):
                alt_key = weapon_key[:-1]
                models = target_map.get(alt_key)
                if models:
                    return True
            return False

        specs = attacker_unit.unit_post_shoot_no_cover_specs() or []
        if not specs:
            return

        from .decision_kinds import DECISION_CHOOSE_QUARRY

        for spec in specs:
            weapon_key = str(spec.get("weapon_key", "") or "")
            if not weapon_key:
                continue
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                if not _target_hit_with_weapon(target_unit, weapon_key):
                    continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "No Cover").strip() or "No Cover"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_no_cover",
                    "ability_name": ability_name,
                    "weapon_key": weapon_key,
                    "weapon_name": str(spec.get("weapon_name", "") or ""),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_ap_bonus(
        self,
        attacker_unit=None,
        hits_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot AP bonus requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _target_already_selected(unit, owner_id: str, turn: int, scope: str, phase_name: str) -> bool:
            if unit is None or not scope:
                return False
            try:
                target_root = unit.get_attached_unit_root()
            except Exception:
                target_root = unit
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                return False
            existing_scope = str(sr.get("post_shoot_ap_bonus_selected_scope", "") or "").strip().lower()
            if not existing_scope:
                return False
            if existing_scope not in ("turn", "phase"):
                return False
            selected_owner = str(sr.get("post_shoot_ap_bonus_selected_owner", "") or "")
            if selected_owner and owner_id and selected_owner != owner_id:
                return False
            selected_turn = int(sr.get("post_shoot_ap_bonus_selected_turn", 0) or 0)
            if selected_turn and turn and selected_turn != turn:
                return False
            if existing_scope == "phase":
                selected_phase = str(sr.get("post_shoot_ap_bonus_selected_phase", "") or "").strip().upper()
                if selected_phase and phase_name and selected_phase != phase_name:
                    return False
            return True

        specs = attacker_unit.unit_post_shoot_ap_bonus_specs() or []
        if not specs:
            return

        from .decision_kinds import DECISION_CHOOSE_QUARRY

        owner_id = str(getattr(attacker_player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()

        for spec in specs:
            keyword = str(spec.get("keyword", "") or "").strip()
            attack_type = str(spec.get("attack_type", "") or "any").strip().lower() or "any"
            try:
                ap_bonus = int(spec.get("value", 0) or 0)
            except Exception:
                ap_bonus = 0
            limit_scope = str(spec.get("limit_scope", "") or "").strip().lower()
            if not keyword or ap_bonus <= 0:
                continue
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                if limit_scope and _target_already_selected(target_unit, owner_id, turn, limit_scope, phase_name):
                    continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "AP Bonus").strip() or "AP Bonus"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_ap_bonus",
                    "ability_name": ability_name,
                    "keyword": keyword,
                    "attack_type": attack_type,
                    "ap_bonus": int(ap_bonus),
                    "limit_scope": limit_scope,
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_crit_hit_threshold(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot crit threshold requires an attacker player.")
        if attacker_player is not self.get_current_player():
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
            specs = attacker_unit.model_post_shoot_crit_hit_threshold_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from .decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot crit bonus").strip() or "Post-shoot crit bonus"
            keyword = str(spec.get("keyword", "") or "").strip()
            try:
                threshold = int(spec.get("threshold", 6) or 6)
            except Exception:
                threshold = 6
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_crit_hit_threshold",
                    "ability_name": ability_name,
                    "keyword": keyword,
                    "threshold": int(threshold),
                    "model_id": get_entity_id(model),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_leadership_debuff(
        self,
        attacker_unit=None,
        hits_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot Leadership debuff requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        specs = attacker_unit.unit_post_shoot_leadership_debuff_specs() or []
        if not specs:
            return

        candidates: list[Any] = []
        for target_unit, hits in (hits_by_target or {}).items():
            if target_unit is None:
                continue
            if int(hits or 0) <= 0:
                continue
            if not _is_enemy_unit(target_unit):
                continue
            candidates.append(target_unit)

        if not candidates:
            return

        from .decision_kinds import DECISION_CHOOSE_POST_SHOOT_LEADERSHIP_DEBUFF_TARGET

        for spec in specs:
            ability_name = (
                str(spec.get("source", "") or "Post-shoot Leadership debuff").strip() or "Post-shoot Leadership debuff"
            )
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
                DECISION_CHOOSE_POST_SHOOT_LEADERSHIP_DEBUFF_TARGET,
                f"{ability_name}: select a unit to suffer -1 to Leadership/Battle-shock tests.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability_name": ability_name,
                },
            )
            self.request_decision(request)

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

    def _on_unit_shooting_resolved_daemonic_poisons(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        self._maybe_trigger_daemonic_poisons(
            attacker_unit=attacker_unit,
            hits_by_target=hits_by_target,
            hit_models_by_target=hit_models_by_target,
            phase="shooting",
        )

    def _on_unit_shooting_resolved_aspect_shrine(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        root = attacker_unit.get_attached_unit_root()
        clear_fn = getattr(root, "clear_aspect_shrine_prompt_suppression", None)
        if callable(clear_fn):
            clear_fn()

    def _on_fight_sequence_complete_aspect_shrine(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        root = unit.get_attached_unit_root()
        clear_fn = getattr(root, "clear_aspect_shrine_prompt_suppression", None)
        if callable(clear_fn):
            clear_fn()

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

    def _on_phase_end_movement_phase_visible_bonus(
        self,
        *,
        player=None,
        phase=None,
        bonus_kind: str,
        spec_method: str,
    ) -> None:
        """Movement phase end: select a visible enemy unit to receive a temporary hit/wound bonus."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        kind_key = str(bonus_kind or "").strip().lower()
        if kind_key not in ("hit", "wound"):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        from ..utility.entity_ids import get_entity_id

        enemy_roots = self._collect_enemy_unit_roots(player)

        def _enemy_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        enemy_roots.sort(key=_enemy_sort_key)
        if not enemy_roots:
            return

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        queue_fn = self._queue_movement_phase_visible_hit_bonus if kind_key == "hit" else self._queue_movement_phase_visible_wound_bonus

        for unit in sorted(list(army.units or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue

            def _model_sort_key(m):
                try:
                    return str(get_entity_id(m))
                except Exception:
                    return str(getattr(m, "name", "") or "")

            for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                spec_fn = getattr(root, spec_method, None)
                if not callable(spec_fn):
                    continue
                specs = spec_fn(model) or []
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                for spec in specs:
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    if range_value <= 0:
                        continue
                    candidates = self._visible_enemy_candidates_for_model(
                        source_unit=source_unit,
                        model=model,
                        enemy_roots=enemy_roots,
                        range_value=float(range_value),
                        game_map=game_map,
                    )
                    if not candidates:
                        continue
                    queue_fn(
                        player=player,
                        source_unit=source_unit,
                        model=model,
                        candidates=candidates,
                        spec=spec,
                    )

    def _on_phase_end_movement_phase_visible_wound_bonus(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: select a visible enemy unit to receive a temporary wound bonus vs friendly keyword attacks."""
        self._on_phase_end_movement_phase_visible_bonus(
            player=player,
            phase=phase,
            bonus_kind="wound",
            spec_method="model_movement_phase_end_visible_wound_bonus_specs",
        )

    def _on_phase_end_movement_phase_visible_hit_bonus(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: select a visible enemy unit to receive a temporary hit bonus vs friendly keyword attacks."""
        self._on_phase_end_movement_phase_visible_bonus(
            player=player,
            phase=phase,
            bonus_kind="hit",
            spec_method="model_movement_phase_end_visible_hit_bonus_specs",
        )

    def _on_phase_end_misfortune(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: select a visible enemy unit to suffer -1 to wound rolls (Misfortune)."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        from ..utility.entity_ids import get_entity_id

        enemy_roots = self._collect_enemy_unit_roots(player)

        if not enemy_roots:
            return

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        enemy_roots.sort(key=_unit_sort_key)

        for unit in sorted(list(army.units or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue

            def _model_sort_key(m):
                try:
                    return str(get_entity_id(m))
                except Exception:
                    return str(getattr(m, "name", "") or "")

            for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                spec_fn = getattr(root, "model_movement_phase_end_misfortune_specs", None)
                if not callable(spec_fn):
                    continue
                specs = spec_fn(model) or []
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                for spec in specs:
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    if range_value <= 0:
                        continue
                    candidates = self._visible_enemy_candidates_for_model(
                        source_unit=source_unit,
                        model=model,
                        enemy_roots=enemy_roots,
                        range_value=float(range_value),
                        game_map=game_map,
                    )
                    if not candidates:
                        continue
                    self._queue_movement_phase_end_misfortune(
                        player=player,
                        source_unit=source_unit,
                        model=model,
                        candidates=candidates,
                        spec=spec,
                    )

    def _on_phase_end_movement_phase_mortal_table(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: roll a D6 for each enemy unit within range of this model; apply mortal wound table."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        enemy_roots = self._collect_enemy_unit_roots(player)
        if not enemy_roots:
            return
        game_map = getattr(self, "map", None)

        from ..utility.entity_ids import get_entity_id
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_action, append_dice

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        enemy_roots.sort(key=_unit_sort_key)

        for unit in sorted(list(army.units or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue

            def _model_sort_key(m):
                try:
                    return str(get_entity_id(m))
                except Exception:
                    return str(getattr(m, "name", "") or "")

            for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                spec_fn = getattr(root, "model_movement_phase_end_enemy_within_range_mortal_table_specs", None)
                if not callable(spec_fn):
                    continue
                specs = spec_fn(model) or []
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                for spec in specs:
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    if range_value <= 0:
                        continue
                    candidates = []
                    for enemy_root in enemy_roots:
                        if enemy_root is None:
                            continue
                        if not self._unit_within_range_of_model(model, enemy_root, range_value=float(range_value)):
                            continue
                        candidates.append(enemy_root)
                    if not candidates:
                        continue
                    candidates.sort(key=_unit_sort_key)
                    ability_name = str(spec.get("source", "") or "Movement phase mortals").strip() or "Movement phase mortals"
                    for target_unit in candidates:
                        roll = int(get_roll("D6") or 0)
                        total_mw = 0
                        d3_roll = None
                        d6_roll = None
                        if 2 <= roll <= 3:
                            total_mw = 1
                        elif 4 <= roll <= 5:
                            d3_roll = int(get_roll("D3") or 0)
                            total_mw = int(d3_roll or 0)
                        elif roll >= 6:
                            d6_roll = int(get_roll("D6") or 0)
                            total_mw = int(d6_roll or 0)
                        roll_note = f"roll={roll}"
                        if d3_roll is not None:
                            roll_note += f", d3={int(d3_roll)}"
                        if d6_roll is not None:
                            roll_note += f", d6={int(d6_roll)}"
                        if total_mw > 0 and hasattr(source_unit, "_apply_mortal_wounds_to_unit"):
                            source_unit._apply_mortal_wounds_to_unit(target_unit, int(total_mw), game_map=game_map)
                        append_dice(
                            player,
                            f"{ability_name}: {getattr(target_unit, 'name', 'Target')} ({roll_note}) => {int(total_mw)} mortal wounds.",
                        )
                        append_action(
                            player,
                            f"{ability_name}: {getattr(target_unit, 'name', 'Target')} suffered {int(total_mw)} mortal wounds.",
                        )

                    if bool(spec.get("battle_shock")):
                        for target_unit in candidates:
                            try:
                                target_unit.take_battle_shock_test(int(getattr(self, "turn", 0) or 1))
                            except Exception:
                                continue

    def _on_phase_end_transport_end_of_fight_embark(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase end: optional embark for empty transports with datasheet abilities."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        game_map = self.map
        if game_map is None:
            return
        try:
            from ..utility.aura_utils import unit_wholly_within_range_of_unit
        except Exception:
            return

        for p in list(self.players or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            for transport in list(army.units or []):
                if transport is None:
                    continue
                if not transport.is_alive() or not getattr(transport, "deployed", True):
                    continue
                try:
                    if transport.is_in_reserves() or transport.is_embarked:
                        continue
                except Exception:
                    pass
                if list(getattr(transport, "transport_passengers", []) or []):
                    continue
                try:
                    specs = list(transport.unit_end_of_fight_embark_specs() or [])
                except Exception:
                    specs = []
                if not specs:
                    continue
                for spec in specs:
                    try:
                        max_models = int(spec.get("max_models", 0) or 0)
                    except Exception:
                        max_models = 0
                    try:
                        range_value = float(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0.0
                    if range_value <= 0:
                        continue
                    keyword = str(spec.get("keyword", "") or "").strip()
                    candidates = []
                    for unit in list(army.units or []):
                        if unit is None or unit is transport:
                            continue
                        if not unit.is_alive() or not getattr(unit, "deployed", True):
                            continue
                        try:
                            if unit.is_in_reserves() or unit.is_embarked:
                                continue
                        except Exception:
                            pass
                        if not getattr(unit, "is_infantry", False):
                            continue
                        if keyword and not unit.has_any_keyword(keyword):
                            continue
                        if max_models > 0:
                            try:
                                models = list(unit.get_attached_unit_models() or [])
                            except Exception:
                                models = list(getattr(unit, "models", []) or [])
                            alive = [m for m in models if getattr(m, "is_alive", True)]
                            if len(alive) > max_models:
                                continue
                        if getattr(unit.round_state, "disembarked_this_round", False):
                            continue
                        sr = getattr(unit, "special_rules", None)
                        if isinstance(sr, dict) and sr.get("fire_and_fade_no_embark_turn_owner"):
                            owner = str(sr.get("fire_and_fade_no_embark_turn_owner") or "")
                            turn = int(sr.get("fire_and_fade_no_embark_turn", 0) or 0)
                            if owner and owner == str(getattr(p, "id", "") or "") and int(getattr(self, "turn", 0) or 0) == turn:
                                continue
                        try:
                            if not transport.can_transport(unit):
                                continue
                        except Exception:
                            continue
                        if not unit_wholly_within_range_of_unit(transport, unit, range_value):
                            continue
                        # Must not be within Engagement Range of any enemy units.
                        enemies = list(game_map.get_enemy_units(unit) or [])
                        engaged = False
                        for enemy in enemies:
                            if enemy is None or not enemy.is_alive():
                                continue
                            if game_map.is_within_engagement_range(unit, enemy):
                                engaged = True
                                break
                        if engaged:
                            continue
                        candidates.append(unit)
                    if not candidates:
                        continue
                    self._queue_end_of_fight_embark_decision(
                        player=p,
                        transport=transport,
                        candidates=candidates,
                        spec=spec,
                    )

    def _on_phase_end_sweeping_advance(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase end: optional Sweeping Advance move for eligible models."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        game_map = self.map
        if game_map is None:
            return

        for p in list(self.players or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            for unit in list(army.units or []):
                if unit is None:
                    continue
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
                try:
                    if unit.is_in_reserves() or unit.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None or not root.is_alive():
                    continue
                try:
                    if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                        continue
                except Exception:
                    continue
                try:
                    models = list(getattr(unit, "models", []) or [])
                except Exception:
                    models = []
                for model in list(models or []):
                    if not getattr(model, "is_alive", True):
                        continue
                    try:
                        specs = list(unit.model_end_of_fight_sweeping_advance_specs(model) or [])
                    except Exception:
                        specs = []
                    if not specs:
                        continue
                    for spec in specs:
                        key = str(spec.get("key") or "sweeping_advance").strip().lower()
                        if not key:
                            key = "sweeping_advance"
                        if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                            continue
                        unit_id = maybe_entity_id(root)
                        model_id = maybe_entity_id(model)
                        if not unit_id or not model_id:
                            continue
                        ability_name = str(spec.get("source", "") or "Sweeping Advance").strip() or "Sweeping Advance"
                        message = f"Use {ability_name} for {getattr(unit, 'name', 'Unit')}?"
                        ctx = {
                            "ability_name": ability_name,
                            "phase": "Fight phase",
                            "unit": getattr(unit, "name", "") or "",
                            "model": getattr(model, "name", "") or "",
                            "unit_id": unit_id,
                            "model_id": model_id,
                            "ability_key": key,
                        }
                        self._queue_optional_ability_confirmation(
                            player=p,
                            ability_key="sweeping_advance",
                            ability_name=ability_name,
                            message=message,
                            context=ctx,
                            payload={
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "ability_key": key,
                            },
                            instance_key=f"{unit_id}:{model_id}",
                        )
        return

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

    def _on_phase_end_charge_phase_bodyguard_loss(self, player=None, phase=None, **_kwargs) -> None:
        """Charge phase end: failed Leadership test can destroy a Bodyguard model while leading."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "CHARGE_PHASE":
            return
        if player is None:
            return
        if player is not self.get_current_player():
            return

        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        for unit in list(army.units):
            if unit is None:
                continue
            if not unit.is_alive() or not getattr(unit, "deployed", True):
                continue
            if not unit.is_attached_leader:
                continue
            ability = unit.get_charge_phase_bodyguard_loss_ability()
            if not ability:
                continue
            bodyguard = unit.get_attached_unit_root()
            if bodyguard is None or bodyguard is unit:
                continue
            if not getattr(bodyguard, "deployed", True):
                continue
            if str(getattr(bodyguard, "reserve_status", "deployed")) != "deployed":
                continue
            if bodyguard.is_in_reserves():
                continue
            if bool(getattr(bodyguard, "embarked_in", None)) or bodyguard.is_embarked:
                continue
            if len(bodyguard.models or []) <= 0:
                continue

            engaged = False
            enemies = list(game_map.get_enemy_units(bodyguard) or [])
            for enemy in enemies:
                if enemy is None:
                    continue
                if not getattr(enemy, "deployed", True):
                    continue
                if not enemy.is_alive():
                    continue
                if not game_map.is_within_engagement_range(bodyguard, enemy):
                    continue
                engaged = True
                break
            if engaged:
                continue

            leader_model = None
            for m in list(unit.models or []):
                if not getattr(m, "is_alive", True):
                    continue
                leader_model = m
                break
            if leader_model is None:
                continue

            passed = bool(unit.pass_leadership_check_for_model(leader_model))
            if passed:
                continue

            candidates = [m for m in (bodyguard.models or []) if getattr(m, "is_alive", True)]
            if not candidates:
                continue

            if len(candidates) == 1:
                self._resolve_charge_phase_bodyguard_loss(unit, bodyguard, candidates[0], ability)
                continue
            ability_name = str((ability or {}).get("name", "") or "Leadership Test").strip() or "Leadership Test"
            options = []
            sorted_candidates = [m for m in list(candidates) if m is not None]
            sorted_candidates.sort(key=lambda m: str(maybe_entity_id(m) or ""))
            for model in sorted_candidates:
                model_id = maybe_entity_id(model)
                if not model_id:
                    continue
                options.append(
                    DecisionOption.create(
                        getattr(model, "name", "Model"),
                        payload={"model_id": model_id},
                    )
                )
            if not options:
                continue
            leader_id = maybe_entity_id(unit)
            bodyguard_id = maybe_entity_id(bodyguard)
            if not leader_id or not bodyguard_id:
                continue
            ctx = {
                "engine_flow": True,
                "selection_kind": "bodyguard_loss",
                "leader_unit_id": leader_id,
                "bodyguard_unit_id": bodyguard_id,
                "unit_id": bodyguard_id,
                "ability_name": ability_name,
            }
            request = DecisionRequest.create(
                DECISION_ALLOCATE_DAMAGE,
                "Select Bodyguard model to destroy.",
                player_id=getattr(player, "id", None),
                options=options,
                context=ctx,
            )
            self.request_decision(request)

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

    def _on_phase_end_flickerjump_mortal_wounds(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: Flickerjump mortal wound rolls for units that used the ability."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None:
            return
        army = player.get_army() if player is not None else None
        if army is None:
            return
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_action, append_dice

        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            if not unit.is_alive() or not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            owner = str(sr.get("flickerjump_pending_uses_owner", "") or "")
            turn = int(sr.get("flickerjump_pending_uses_turn", 0) or 0)
            if owner and owner != str(getattr(player, "id", "") or ""):
                continue
            if int(getattr(self, "turn", 0) or 0) != turn:
                continue
            uses = int(sr.get("flickerjump_pending_uses", 0) or 0)
            if uses <= 0:
                continue
            ability_name = str(sr.get("flickerjump_source", "") or "Flickerjump").strip() or "Flickerjump"

            for _ in range(int(uses)):
                models = [m for m in list(getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)]
                if not models:
                    break
                rolls = []
                ones = 0
                for _m in models:
                    r = int(get_roll("D6") or 0)
                    rolls.append(r)
                    if r == 1:
                        ones += 1
                if ones > 0:
                    unit._apply_mortal_wounds_to_unit(unit, int(ones), game_map=getattr(self, "map", None))
                append_dice(
                    player,
                    f"{ability_name}: rolls {rolls} => {int(ones)} mortal wounds to {getattr(unit, 'name', 'Unit')}.",
                )
                append_action(
                    player,
                    f"{ability_name}: {getattr(unit, 'name', 'Unit')} suffered {int(ones)} mortal wounds.",
                )

            for k in (
                "flickerjump_pending_uses",
                "flickerjump_pending_uses_turn",
                "flickerjump_pending_uses_owner",
                "flickerjump_source",
            ):
                sr.pop(k, None)
            unit.special_rules = sr

    def _on_phase_end_fight_phase_mortal_wounds(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase end: optional mortal wounds against an engaged enemy unit."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        game_map = self.map
        if game_map is None:
            return
        from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases

        def _model_in_engagement_with_unit(model, target_unit) -> bool:
            if not getattr(model, "is_alive", False):
                return False
            get_collision = getattr(target_unit, "get_models_for_collision", None)
            if callable(get_collision):
                t_models = list(get_collision() or [])
            else:
                t_models = list(target_unit.models or [])
            for t_model in t_models:
                if not getattr(t_model, "is_alive", False):
                    continue
                horizontal = float(horizontal_distance_between_bases_2d(model.model_base, t_model.model_base))
                vertical = float(vertical_distance_between_bases(model.model_base, t_model.model_base))
                if horizontal <= ENGAGEMENT_RANGE_HORIZONTAL and vertical <= ENGAGEMENT_RANGE_VERTICAL:
                    return True
            return False

        for p in list(self.players or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            for unit in list(army.units):
                if unit is None:
                    continue
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
                if unit.is_in_reserves():
                    continue
                if unit.is_embarked:
                    continue

                enemies = list(game_map.get_enemy_units(unit) or [])
                if not enemies:
                    continue

                for model in list(unit.models or []):
                    if not getattr(model, "is_alive", False):
                        continue
                    specs = unit.model_end_fight_phase_engagement_mortal_wounds_specs(model) or []
                    if not specs:
                        continue

                    candidates = []
                    seen_enemy = set()
                    for enemy in enemies:
                        if enemy is None:
                            continue
                        root = enemy.get_attached_unit_root()
                        key = get_entity_id(root)
                        if key in seen_enemy:
                            continue
                        seen_enemy.add(key)
                        if not root.is_alive() or not getattr(root, "deployed", True):
                            continue
                        if root.is_in_reserves():
                            continue
                        if root.is_embarked:
                            continue
                        if _model_in_engagement_with_unit(model, root):
                            candidates.append(root)

                    if not candidates:
                        continue

                    for spec in specs:
                        self._queue_mortal_wounds_target_decision(
                            player=p,
                            unit=unit,
                            model=model,
                            candidates=list(candidates),
                            spec=spec,
                            kind="fight_phase_end",
                            allow_skip=True,
                            phase="Fight phase",
                        )

    def _on_phase_end_leadership_cp_gain(self, player=None, phase=None, **_kwargs) -> None:
        """End of Shooting/Fight phase: Leadership test to gain CP after destroying enemy units."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname not in ("SHOOTING_PHASE", "FIGHT_PHASE"):
            return
        if player is None:
            return
        if player is not self.get_current_player():
            return
        army = self._get_player_army(player)
        if army is None:
            return
        tracked = set(self._phase_enemy_unit_destroyers.get(pname, set()) or set())
        if not tracked:
            return

        processed: set[str] = set()
        for unit in list(army.units):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            uid = get_entity_id(root)
            if not uid or uid in processed:
                continue
            processed.add(uid)
            if uid not in tracked:
                continue
            if not root.is_alive() or not getattr(root, "deployed", True):
                continue
            if root.is_in_reserves() or root.is_embarked:
                continue

            specs = root.get_phase_end_leadership_cp_gain_specs() or []
            for spec in specs:
                if spec.get("type") != "phase_end_leadership_cp_gain":
                    continue
                cp = int(spec.get("cp", 1) or 1)
                if cp <= 0:
                    continue
                if not bool(root.pass_leadership_check()):
                    continue
                gained = int(player.gain_command_points(cp, reason=spec.get("source_ability", "")) or 0)
                self.event_system.publish(
                    "command_points_gained",
                    player=player,
                    amount=gained,
                    reason=spec.get("source_ability", ""),
                    unit=root,
                )

        self._phase_enemy_unit_destroyers[pname] = set()

    def _on_phase_end_daemonic_patrons(self, player=None, phase=None, **_kwargs) -> None:
        """End of Fight phase: destroy one model if Daemonic Patrons was called and no enemy models were destroyed."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        tracked = set(self._phase_enemy_model_destroyers.get(pname, set()) or set())
        seen: set[str] = set()

        for p in list(self.players or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None:
                    continue
                uid = get_entity_id(root)
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                if not root.is_alive() or not getattr(root, "deployed", True):
                    continue
                if root.is_in_reserves() or root.is_embarked:
                    continue
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict) or not sr.get("daemonic_patrons_active"):
                    continue
                if uid in tracked:
                    continue

                ability_name = str(sr.get("daemonic_patrons_source", "") or "Daemonic Patrons").strip() or "Daemonic Patrons"
                owner = getattr(root.get_parent_army(), "player", None)
                if owner is None:
                    continue

                existing = [
                    req
                    for req in list(self.decision_queue.list() or [])
                    if getattr(req, "decision_type", None) == DECISION_ALLOCATE_DAMAGE
                    and str(getattr(req, "context", {}).get("selection_kind", "") or "") == "daemonic_patrons_loss"
                    and str(getattr(req, "context", {}).get("unit_id", "") or "") == uid
                ]
                if existing:
                    continue

                try:
                    models = list(root.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(root, "models", []) or [])
                alive_models = []
                for m in models:
                    try:
                        alive = getattr(m, "is_alive", True)
                        alive = alive() if callable(alive) else bool(alive)
                    except Exception:
                        alive = True
                    if alive:
                        alive_models.append(m)
                if not alive_models:
                    continue
                try:
                    alive_models.sort(key=lambda m: str(get_entity_id(m) or ""))
                except Exception:
                    alive_models = list(alive_models)

                options = []
                used_labels = set()
                for model in alive_models:
                    label = str(getattr(model, "name", "") or "Model")
                    base = label
                    idx = 2
                    while label in used_labels:
                        label = f"{base} ({idx})"
                        idx += 1
                    used_labels.add(label)
                    options.append(DecisionOption.create(label, payload={"model_id": get_entity_id(model)}))
                allowed_ids = [get_entity_id(m) for m in alive_models if get_entity_id(m)]
                ctx = {
                    "selection_kind": "daemonic_patrons_loss",
                    "ability_name": ability_name,
                    "phase": "Fight phase",
                    "unit_id": uid,
                    "allowed_model_ids": allowed_ids,
                    "reason": f"{ability_name}: Destroy one model",
                }
                request = DecisionRequest.create(
                    DECISION_ALLOCATE_DAMAGE,
                    f"{ability_name}: Select model to destroy",
                    player_id=getattr(owner, "id", None),
                    options=options,
                    context=ctx,
                )
                self.request_decision(request)

        self._phase_enemy_model_destroyers[pname] = set()

    def _queue_transport_reactive_disembark_decisions(
        self,
        *,
        player,
        transport,
        enemy_unit=None,
        ability: dict | None = None,
        trigger: str | None = None,
    ) -> list[DecisionRequest]:
        if player is None or transport is None:
            return []
        transport_id = maybe_entity_id(transport)
        if not transport_id:
            return []
        enemy_unit_id = maybe_entity_id(enemy_unit) if enemy_unit is not None else None
        ability_name = str((ability or {}).get("name", "") or "Reactive Disembark").strip() or "Reactive Disembark"
        try:
            rng = int((ability or {}).get("range", 0) or 0)
        except Exception:
            rng = 0

        pending = [
            req
            for req in list(self.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_DISEMBARK
            and str(getattr(req, "context", {}).get("transport_id", "")) == transport_id
        ]
        pending_units = {
            str(getattr(req, "context", {}).get("unit_id", "") or "")
            for req in pending
            if str(getattr(req, "context", {}).get("unit_id", "") or "")
        }

        eligible = []
        seen = set()
        for passenger in list(getattr(transport, "transport_passengers", []) or []):
            if passenger is None:
                continue
            unit_id = maybe_entity_id(passenger)
            if not unit_id:
                continue
            if unit_id in seen or unit_id in pending_units:
                continue
            seen.add(unit_id)
            try:
                if getattr(passenger.round_state, "embarked_this_round", False):
                    continue
                if getattr(passenger.round_state, "disembarked_this_round", False):
                    continue
            except Exception:
                pass
            try:
                if getattr(passenger, "embarked_in", None) is not transport:
                    continue
            except Exception:
                pass
            eligible.append(passenger)
        if not eligible:
            return []

        requests: list[DecisionRequest] = []
        for passenger in eligible:
            unit_id = maybe_entity_id(passenger)
            if not unit_id:
                continue
            options = [
                DecisionOption.create(
                    "Disembark",
                    payload={"unit_id": unit_id, "transport_id": transport_id},
                ),
                DecisionOption.create(
                    "Remain embarked",
                    payload={"unit_id": unit_id, "transport_id": None},
                ),
            ]
            ctx = {
                "unit_id": unit_id,
                "transport_id": transport_id,
                "reactive_disembark": True,
                "reactive_disembark_source": ability_name,
            }
            if enemy_unit_id:
                ctx["reactive_disembark_enemy_unit_id"] = enemy_unit_id
            if rng:
                ctx["reactive_disembark_range"] = int(rng)
            if trigger:
                ctx["reactive_disembark_trigger"] = str(trigger)
            request = DecisionRequest.create(
                DECISION_DISEMBARK,
                f"Disembark {getattr(passenger, 'name', 'Unit')}",
                player_id=getattr(player, "id", None),
                options=options,
                context=ctx,
            )
            self.request_decision(request)
            requests.append(request)
        return requests

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

    def _record_setup_reactive_shoot_or_charge_candidate(self, enemy_unit) -> None:
        if enemy_unit is None:
            return
        if not self.is_movement_phase():
            return
        enemy_army = enemy_unit.get_parent_army()
        enemy_player = getattr(enemy_army, "player", None) if enemy_army is not None else None
        if enemy_player is None:
            return
        if self.get_current_player() is not enemy_player:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Setup reactive shoot/charge requires players.")
            if p is enemy_player:
                continue
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Setup reactive shoot/charge requires an army for {p.name}.")
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
                rule = root.get_setup_reactive_shoot_or_charge_rule()
                if not rule:
                    continue
                rng = int(rule.get("range", 12) or 12)
                if not root.can_setup_reactive_shoot_or_charge(
                    game=self,
                    game_map=game_map,
                    enemy_unit=enemy_unit,
                    range_override=rng,
                ):
                    continue
                root.record_setup_reactive_shoot_or_charge_candidate(enemy_unit, game=self)

    def _on_unit_set_up_setup_reactive_shoot_or_charge(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        self._record_setup_reactive_shoot_or_charge_candidate(unit)

    def _on_unit_disembarked_setup_reactive_shoot_or_charge(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        self._record_setup_reactive_shoot_or_charge_candidate(unit)

    def _on_phase_end_setup_reactive_shoot_or_charge(self, player=None, phase=None, **_kwargs) -> None:
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        current_player = self.get_current_player()
        if current_player is None:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Setup reactive shoot/charge requires players.")
            if p is current_player:
                continue
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Setup reactive shoot/charge requires an army for {p.name}.")
            seen = set()
            for unit in list(army.units):
                if unit is None:
                    continue
                root = unit.get_attached_unit_root()
                if root is None:
                    continue
                rid = get_entity_id(root)
                if rid in seen:
                    continue
                seen.add(rid)
                rule = root.get_setup_reactive_shoot_or_charge_rule()
                if not rule:
                    continue
                if root.setup_reactive_shoot_or_charge_used_this_phase(self):
                    continue
                if not root.can_setup_reactive_shoot_or_charge(game=self, game_map=game_map):
                    root.clear_setup_reactive_shoot_or_charge_candidates(self)
                    continue
                candidate_ids = root.get_setup_reactive_shoot_or_charge_candidates(self)
                if not candidate_ids:
                    continue
                candidates = []
                for cid in candidate_ids:
                    enemy = self._resolve_unit_by_id(str(cid))
                    if enemy is None:
                        continue
                    if not enemy.is_alive():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if enemy.get_parent_army() == root.get_parent_army():
                        continue
                    candidates.append(enemy)
                if not candidates:
                    root.clear_setup_reactive_shoot_or_charge_candidates(self)
                    continue
                actionable = []
                for enemy in candidates:
                    if self._setup_reactive_available_actions(root, enemy):
                        actionable.append(enemy)
                if not actionable:
                    root.clear_setup_reactive_shoot_or_charge_candidates(self)
                    continue
                if p.has_control():
                    es = getattr(self, "event_system", None)
                    if es is None or not hasattr(es, "subscribers"):
                        raise RuntimeError("Event system missing for setup reactive prompt.")
                    subs = getattr(es, "subscribers", None)
                    if not isinstance(subs, dict):
                        raise RuntimeError("Event system subscribers not configured.")
                    if subs.get("setup_reactive_shoot_charge_prompt"):
                        es.publish(
                            "setup_reactive_shoot_charge_prompt",
                            player=p,
                            unit=root,
                            candidates=list(actionable),
                            rule=rule,
                            game=self,
                        )
                else:
                    self._queue_setup_reactive_target_decision(
                        player=p,
                        unit=root,
                        candidates=list(actionable),
                        rule=rule,
                    )
                root.clear_setup_reactive_shoot_or_charge_candidates(self)

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
        current_player = None
        try:
            current_player = self.get_current_player()
        except Exception:
            current_player = None
        if current_player is None:
            return
        try:
            owner = destroyed_by_unit.get_parent_army().player
        except Exception:
            owner = None
        if owner is None or owner is not current_player:
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

        specs = destroyed_by_unit.get_kill_reward_specs(model=destroyed_by_model) or []

        if not specs:
            return

        target_keywords = {str(k).upper() for k in getattr(unit, "keywords", []) or []}

        for spec in specs:
            if spec.get("trigger") != "unit_destroyed":
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
                from warhammer40k_ai.utility.dice import get_roll
                amount = get_roll(heal_expr)
                destroyed_by_model.heal(amount)
                self.event_system.publish(
                    "model_healed",
                    model=destroyed_by_model,
                    unit=destroyed_by_unit,
                    amount=amount,
                    reason=spec.get("source_ability", ""),
                )

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

    def _on_shooting_targets_selected_dark_pacts(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        trigger_fn = getattr(root, "maybe_trigger_dark_pacts", None)
        if callable(trigger_fn):
            trigger_fn(self, phase_name=phase_name, trigger="shooting")

    def _on_shooting_targets_selected_path_of_warrior(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        trigger_fn = getattr(root, "maybe_trigger_path_of_warrior", None)
        if callable(trigger_fn):
            trigger_fn(self, phase_name=phase_name, trigger="shooting")

    def _on_shooting_targets_selected_cruel_amusement(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        try:
            entries = list(root.iter_cruel_amusement_models() or [])
        except Exception:
            entries = []
        if not entries:
            return
        from .decision_kinds import DECISION_CHOOSE_CRUEL_AMUSEMENT
        from .decisions import DecisionOption, DecisionRequest

        pending_models = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_CRUEL_AMUSEMENT:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)
        except Exception:
            pending_models = set()

        def _sort_key(entry):
            try:
                return str(get_entity_id(entry.get("model")))
            except Exception:
                return ""

        for entry in sorted(list(entries or []), key=_sort_key):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            weapon_name = str(entry.get("weapon_name", "") or "shrieker cannon")
            ability_name = str(entry.get("source", "") or "Cruel Amusement").strip() or "Cruel Amusement"
            options = [
                DecisionOption.create(
                    "Ignores Cover",
                    payload={"choice": "IGNORES_COVER", "summary": "Weapon gains [IGNORES COVER] until end of phase."},
                ),
                DecisionOption.create(
                    "Precision",
                    payload={"choice": "PRECISION", "summary": "Weapon gains [PRECISION] until end of phase."},
                ),
                DecisionOption.create(
                    "Sustained Hits 3",
                    payload={"choice": "SUSTAINED_HITS_3", "summary": "Weapon gains [SUSTAINED HITS 3] until end of phase."},
                ),
            ]
            ctx = {
                "unit_id": get_entity_id(root),
                "model_id": model_id,
                "weapon_name": weapon_name,
                "ability_name": ability_name,
                "phase_name": "SHOOTING_PHASE",
            }
            req = DecisionRequest.create(
                DECISION_CHOOSE_CRUEL_AMUSEMENT,
                f"{ability_name}: select a weapon ability.",
                player_id=getattr(player, "id", None),
                options=options,
                context=ctx,
            )
            self.request_decision(req)

    def _on_shooting_targets_selected_hand_of_asuryan(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return

        pending_models = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CONFIRM_YES_NO:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("ability", "") or "") != "hand_of_asuryan":
                        continue
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)
        except Exception:
            pending_models = set()

        def _sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return ""

        for model in sorted(list(getattr(root, "models", []) or []), key=_sort_key):
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            if getattr(model, "has_used_once_per_battle", lambda _k: False)("hand_of_asuryan"):
                continue
            specs = root.model_hand_of_asuryan_specs(model) or []
            if not specs:
                continue
            spec = specs[0]
            weapon_name = str(spec.get("weapon_name", "") or "Bloody Twins").strip() or "Bloody Twins"
            ability_name = str(spec.get("source", "") or "Hand of Asuryan").strip() or "Hand of Asuryan"
            unit_id = get_entity_id(root)
            if not unit_id or not model_id:
                continue
            ctx = {
                "ability": "hand_of_asuryan",
                "ability_name": ability_name,
                "phase": "Shooting phase",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "model": getattr(model, "name", "") or "",
                "model_id": model_id,
                "weapon_name": weapon_name,
            }
            message = f"Use {ability_name} for {getattr(model, 'name', 'Model')}?"
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="hand_of_asuryan",
                ability_name=ability_name,
                message=message,
                context=ctx,
                payload={"unit_id": unit_id, "model_id": model_id, "weapon_name": weapon_name},
                instance_key=f"{model_id}:hand_of_asuryan",
            )
            return

    def _on_shooting_targets_selected_harvester_of_souls(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        specs = root.leading_harvester_of_souls_specs() or []
        if not specs:
            return
        spec = specs[0]
        leader = spec.get("leader")
        if leader is not None and not getattr(leader, "is_alive", False):
            return
        unique_targets = []
        seen = set()
        for t in list(target_units or []):
            if t is None:
                continue
            try:
                target_root = t.get_attached_unit_root()
            except Exception:
                target_root = t
            if target_root is None:
                continue
            tid = str(get_entity_id(target_root) or "")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            unique_targets.append(target_root)
        if len(unique_targets) != 1:
            return
        target_root = unique_targets[0]
        if target_root.get_parent_army() == root.get_parent_army():
            return
        if not target_root.is_alive():
            return
        ability_name = str(spec.get("source", "") or "Harvester of Souls").strip() or "Harvester of Souls"
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return
        enemy_roots = []
        seen_enemy = set()
        for enemy in list(self.get_enemy_units(player) or []):
            if enemy is None:
                continue
            try:
                eroot = enemy.get_attached_unit_root()
            except Exception:
                eroot = enemy
            if eroot is None or not eroot.is_alive():
                continue
            try:
                if not getattr(eroot, "deployed", True):
                    continue
                if eroot.is_in_reserves() or eroot.is_embarked:
                    continue
            except Exception:
                pass
            eid = str(get_entity_id(eroot) or "")
            if not eid or eid in seen_enemy:
                continue
            seen_enemy.add(eid)
            enemy_roots.append(eroot)
        candidates = [target_root]
        for enemy_root in enemy_roots:
            if enemy_root is target_root:
                continue
            if unit_within_range_of_unit(target_root, enemy_root, 3.0):
                candidates.append(enemy_root)
        if not candidates:
            return
        try:
            owner_id = str(getattr(player, "id", "") or "")
        except Exception:
            owner_id = ""
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        marked_ids: list[str] = []
        for cand in list(candidates):
            try:
                roll = int(get_roll("D6") or 0)
            except Exception:
                roll = 0
            if roll >= 5:
                cid = str(get_entity_id(cand) or "")
                if cid and cid not in marked_ids:
                    marked_ids.append(cid)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        for key in (
            "harvester_of_souls_pending_ids",
            "harvester_of_souls_target_id",
            "harvester_of_souls_source",
            "harvester_of_souls_owner",
            "harvester_of_souls_turn",
        ):
            sr.pop(key, None)
        if marked_ids:
            sr["harvester_of_souls_pending_ids"] = list(marked_ids)
            sr["harvester_of_souls_target_id"] = str(get_entity_id(target_root) or "")
            sr["harvester_of_souls_source"] = ability_name
            sr["harvester_of_souls_owner"] = owner_id
            sr["harvester_of_souls_turn"] = int(turn or 0)
        root.special_rules = sr

    def _on_fight_unit_selected_dark_pacts(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        trigger_fn = getattr(root, "maybe_trigger_dark_pacts", None)
        if callable(trigger_fn):
            trigger_fn(self, phase_name=phase_name, trigger="fight")

    def _on_fight_unit_selected_path_of_warrior(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        trigger_fn = getattr(root, "maybe_trigger_path_of_warrior", None)
        if callable(trigger_fn):
            trigger_fn(self, phase_name=phase_name, trigger="fight")

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

    def _on_unit_shooting_resolved_emperors_children(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        mgr = self._get_emperors_children_manager(army)
        if mgr is None:
            return
        if not mgr.resolve_pending_favoured_champions(root, game=self):
            return
        from ..utility.event_bus import append_action

        message = f"{INTERNAL_RIVALRIES_NAME}: {getattr(root, 'name', 'Unit')} are now Favoured Champions."
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            append_action(player, message)
        if getattr(self, "event_system", None) is not None:
            self.event_system.publish(
                "emperors_children_favoured_champions_updated",
                game=self,
                manager=mgr,
                unit=root,
            )

    def _on_fight_attacks_resolved_emperors_children(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        mgr = self._get_emperors_children_manager(army)
        if mgr is None:
            return
        if not mgr.resolve_pending_favoured_champions(root, game=self):
            return
        from ..utility.event_bus import append_action

        message = f"{INTERNAL_RIVALRIES_NAME}: {getattr(root, 'name', 'Unit')} are now Favoured Champions."
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            append_action(player, message)
        if getattr(self, "event_system", None) is not None:
            self.event_system.publish(
                "emperors_children_favoured_champions_updated",
                game=self,
                manager=mgr,
                unit=root,
            )

    def _on_fight_unit_selected_emperors_children(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "emperors_children_detachments", None) if army is not None else None
        if mgr is None or not getattr(mgr, "sensational_performance_applies", lambda _u: False)(unit):
            return
        if not bool(getattr(getattr(unit, "round_state", None), "charged_this_round", False)):
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if sr.get("sensational_performance_active"):
            return

        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        unit_id = maybe_entity_id(unit)
        ctx = {
            "ability_name": "Sensational Performance",
            "phase": "Fight phase",
            "unit": getattr(unit, "name", ""),
            "unit_id": unit_id,
        }
        message = f"Use Sensational Performance for {getattr(unit, 'name', 'Unit')}?"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="sensational_performance",
            ability_name="Sensational Performance",
            message=message,
            context=ctx,
            payload={"unit_id": unit_id},
            instance_key=str(unit_id or ""),
        )
        
    def _on_fight_unit_selected_daemonic_patrons(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        specs = root.unit_fight_selected_daemonic_patrons_specs() or []
        if not specs:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if sr.get("daemonic_patrons_active"):
            return
        try:
            specs = sorted(specs, key=lambda s: str((s or {}).get("source", "") or ""))
        except Exception:
            specs = list(specs)
        spec = specs[0] if specs else {}
        try:
            threshold = int((spec or {}).get("crit_wound_threshold", 3) or 3)
        except Exception:
            threshold = 3
        if threshold < 2 or threshold > 6:
            threshold = 3
        source = str((spec or {}).get("source", "") or "Daemonic Patrons").strip() or "Daemonic Patrons"
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        unit_id = maybe_entity_id(root)
        if not unit_id:
            return
        ctx = {
            "ability_name": source,
            "phase": "Fight phase",
            "unit": getattr(root, "name", ""),
            "unit_id": unit_id,
            "crit_wound_threshold": int(threshold),
        }
        message = f"Call upon {source} for {getattr(root, 'name', 'Unit')}?"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="daemonic_patrons",
            ability_name=source,
            message=message,
            context=ctx,
            payload={
                "unit_id": unit_id,
                "crit_wound_threshold": int(threshold),
                "ability_name": source,
            },
            instance_key=str(unit_id or ""),
        )

    def _on_fight_unit_selected_maddened_ferocity(self, unit=None, **_kwargs) -> None:
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
        mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        if mgr is None or not getattr(mgr, "maddened_ferocity_applies", lambda _u: False)(root):
            return

        bonus = 0
        try:
            if root.is_battle_shocked():
                bonus = 2
            elif bool(getattr(getattr(root, "round_state", None), "charged_this_round", False)):
                bonus = 1
        except Exception:
            bonus = 0

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if bonus:
                sr["maddened_ferocity_melee_attacks_bonus"] = int(bonus)
                sr["maddened_ferocity_expires_phase"] = "FIGHT_PHASE"
            else:
                sr.pop("maddened_ferocity_melee_attacks_bonus", None)
                sr.pop("maddened_ferocity_expires_phase", None)
            member.special_rules = sr

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

    def _on_shooting_targets_selected_blood_surge(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        snapshot = dict(self._blood_surge_shooting_snapshot.get(attacking_unit, {}) or {})
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            try:
                if not root.has_blood_surge():
                    continue
            except Exception:
                continue
            count = self._alive_model_count(root)
            if count <= 0:
                continue
            snapshot[root] = count
        if snapshot:
            self._blood_surge_shooting_snapshot[attacking_unit] = snapshot

    def _on_unit_shooting_resolved_blood_surge(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        snapshot = self._blood_surge_shooting_snapshot.pop(attacker_unit, {})
        if not snapshot:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        for target, before in snapshot.items():
            if target is None:
                continue
            after = self._alive_model_count(target)
            if after >= int(before or 0):
                continue
            try:
                if not target.has_blood_surge():
                    continue
            except Exception:
                continue
            can_fn = getattr(target, "can_blood_surge", None)
            if callable(can_fn):
                if not can_fn(game=self, game_map=getattr(self, "map", None)):
                    continue
            player = None
            try:
                player = target.get_parent_army().player
            except Exception:
                player = None
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("blood_surge_prompt"))
            if is_human and es is not None:
                es.publish(
                    "blood_surge_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    game=self,
                )
                if has_sub:
                    continue
            if not is_human:
                msg = (
                    "Blood Surge: Move D6+2\" as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                    "This unit cannot Blood Surge while Battle-shocked or within Engagement Range."
                )
                request = self._queue_reactive_move_confirmation(
                    player=player,
                    unit=target,
                    kind="blood_surge",
                    movement_type="blood_surge",
                    source="Blood Surge",
                    message=msg,
                    attacker_unit=attacker_unit,
                )
                continue
            move_fn = getattr(target, "auto_blood_surge_move", None)
            if callable(move_fn):
                max_dist = int(self.roll_blood_surge_distance(target) or 0)
                move_fn(getattr(self, "map", None), max_dist)
                target.mark_blood_surge_used(self)

    def _on_shooting_targets_selected_brazen_fury(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        snapshot = dict(self._brazen_fury_shooting_snapshot.get(attacking_unit, {}) or {})
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            try:
                if not root.has_brazen_fury():
                    continue
            except Exception:
                continue
            count = self._alive_model_count(root)
            if count <= 0:
                continue
            snapshot[root] = count
        if snapshot:
            self._brazen_fury_shooting_snapshot[attacking_unit] = snapshot

    def _on_unit_shooting_resolved_brazen_fury(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        snapshot = self._brazen_fury_shooting_snapshot.pop(attacker_unit, {})
        if not snapshot:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        if "SHOOT" not in phase_name.upper():
            return
        current_player = None
        try:
            current_player = self.get_current_player()
        except Exception:
            current_player = None
        for target, before in snapshot.items():
            if target is None:
                continue
            after = self._alive_model_count(target)
            if after >= int(before or 0):
                continue
            try:
                if not target.has_brazen_fury():
                    continue
            except Exception:
                continue
            try:
                target_player = target.get_parent_army().player
            except Exception:
                target_player = None
            if target_player is None or current_player is None:
                continue
            if target_player is current_player:
                continue
            can_fn = getattr(target, "can_brazen_fury", None)
            if callable(can_fn):
                if not can_fn(game=self, game_map=getattr(self, "map", None)):
                    continue
            player = target_player
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("brazen_fury_prompt"))
            if is_human and es is not None:
                es.publish(
                    "brazen_fury_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    game=self,
                )
                if has_sub:
                    continue
            msg = (
                "Brazen Fury: Move D6\" as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                "This unit cannot Brazen Fury while Battle-shocked or within Engagement Range."
            )
            self._queue_reactive_move_confirmation(
                player=player,
                unit=target,
                kind="brazen_fury",
                movement_type="brazen_fury",
                source="Brazen Fury",
                message=msg,
                attacker_unit=attacker_unit,
            )

    def _on_shooting_targets_selected_frenzy(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        targets = list(self._frenzy_shooting_targets.get(attacking_unit, []) or [])
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            try:
                if not root.has_frenzy():
                    continue
            except Exception:
                continue
            if root not in targets:
                targets.append(root)
        if targets:
            self._frenzy_shooting_targets[attacking_unit] = targets

    def _on_unit_shooting_resolved_frenzy(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        targets = list(self._frenzy_shooting_targets.pop(attacker_unit, []) or [])
        if not targets:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        for target in targets:
            if target is None:
                continue
            try:
                if not target.has_frenzy():
                    continue
            except Exception:
                continue
            options = list(self._frenzy_available_actions(target, attacker_unit, phase_name=phase_name))
            if not options:
                continue
            player = None
            try:
                player = target.get_parent_army().player
            except Exception:
                player = None
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("frenzy_prompt"))
            if is_human and es is not None:
                es.publish(
                    "frenzy_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    options=list(options),
                    game=self,
                )
                if has_sub:
                    continue
            if "shoot" in options:
                self._execute_frenzy_shooting(target, attacker_unit)
            elif "fight" in options:
                self._execute_frenzy_fight(target, attacker_unit, phase_name=phase_name)

    def _on_fight_targets_selected_frenzy(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        targets = list(self._frenzy_fight_targets.get(attacking_unit, []) or [])
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            try:
                if not root.has_frenzy():
                    continue
            except Exception:
                continue
            if root not in targets:
                targets.append(root)
        if targets:
            self._frenzy_fight_targets[attacking_unit] = targets

    def _on_fight_attacks_resolved_frenzy(self, unit=None, target_unit=None, **_kwargs) -> None:
        attacker_unit = unit
        if attacker_unit is None:
            return
        targets = list(self._frenzy_fight_targets.pop(attacker_unit, []) or [])
        if not targets:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        for target in targets:
            if target is None:
                continue
            try:
                if not target.has_frenzy():
                    continue
            except Exception:
                continue
            options = list(self._frenzy_available_actions(target, attacker_unit, phase_name=phase_name))
            if not options:
                continue
            player = None
            try:
                player = target.get_parent_army().player
            except Exception:
                player = None
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("frenzy_prompt"))
            if is_human and es is not None:
                es.publish(
                    "frenzy_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    options=list(options),
                    game=self,
                )
                if has_sub:
                    continue
            if "shoot" in options:
                self._execute_frenzy_shooting(target, attacker_unit)
            elif "fight" in options:
                self._execute_frenzy_fight(target, attacker_unit, phase_name=phase_name)

    def _frenzy_has_eligible_shot(self, unit, target_unit) -> bool:
        if unit is None or target_unit is None:
            return False
        try:
            if hasattr(unit, "is_ranged_unit"):
                return bool(unit.is_ranged_unit)
        except Exception:
            pass
        for model in list(getattr(unit, "models", []) or []):
            if not getattr(model, "is_alive", True):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                try:
                    if wargear is not None and wargear.is_ranged():
                        return True
                except Exception:
                    continue
        return False

    def _frenzy_can_fight_target(self, unit, target_unit) -> bool:
        if unit is None or target_unit is None:
            return False
        if not getattr(unit, "is_alive", lambda: True)():
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        if getattr(unit, "is_embarked", False) or getattr(unit, "embarked_in", None) is not None:
            return False
        game_map = getattr(self, "map", None)
        if game_map is None:
            return False
        try:
            from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
            for m in list(getattr(unit, "models", []) or []):
                if not getattr(m, "is_alive", True):
                    continue
                for em in list(getattr(target_unit, "models", []) or []):
                    if not getattr(em, "is_alive", True):
                        continue
                    h = float(horizontal_distance_between_bases_2d(m.model_base, em.model_base))
                    v = float(vertical_distance_between_bases(m.model_base, em.model_base))
                    if v > ENGAGEMENT_RANGE_VERTICAL + 1e-6:
                        continue
                    if h <= float(ENGAGEMENT_RANGE_HORIZONTAL) + 3.0 + 1e-6:
                        return True
        except Exception:
            return False
        return False

    def _frenzy_available_actions(self, unit, attacker_unit, *, phase_name: str | None = None) -> list[str]:
        if unit is None or attacker_unit is None:
            return []
        try:
            if not unit.has_frenzy():
                return []
        except Exception:
            return []
        pname = str(phase_name or "").strip().upper()
        if pname and ("SHOOT" not in pname and "FIGHT" not in pname):
            return []
        options: list[str] = []
        if self._frenzy_has_eligible_shot(unit, attacker_unit):
            options.append("shoot")
        if self._frenzy_can_fight_target(unit, attacker_unit):
            options.append("fight")
        return options

    def _build_frenzy_shooting_declarations(self, unit, target_unit) -> list[dict]:
        declarations: list[dict] = []
        if unit is None or target_unit is None:
            return declarations
        for model in list(getattr(unit, "models", []) or []):
            if not getattr(model, "is_alive", True):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                try:
                    if not wargear.is_ranged():
                        continue
                except Exception:
                    continue
                profiles = getattr(wargear, "profiles", {}) or {}
                for profile in list(profiles.values()):
                    if profile is None:
                        continue
                    declarations.append(
                        {
                            "weapon_profile": profile,
                            "target_unit": target_unit,
                            "models": [model],
                        }
                    )
        return declarations

    def _execute_frenzy_shooting(self, unit, attacker_unit) -> bool:
        if unit is None or attacker_unit is None:
            return False
        declarations = self._build_frenzy_shooting_declarations(unit, attacker_unit)
        if not declarations:
            return False
        exec_fn = getattr(unit, "execute_shooting_declarations", None)
        if not callable(exec_fn):
            return False
        return bool(exec_fn(declarations, getattr(self, "map", None), out_of_phase=True))

    def resolve_frenzy_melee_attacks(self, unit, target_unit, weapon_declarations) -> None:
        if unit is None or target_unit is None:
            return
        try:
            from .fight_phase_manager import FightPhaseManager
            attack_summary = FightPhaseManager(self)._resolve_melee_attacks(unit, target_unit, weapon_declarations)
            self._maybe_trigger_daemonic_poisons(
                attacker_unit=unit,
                hits_by_target=attack_summary.get("hits_by_target"),
                hit_models_by_target=attack_summary.get("hit_models_by_target"),
                phase="fight",
            )
            if hasattr(self, "event_system"):
                self.event_system.publish(
                    "fight_attacks_resolved",
                    unit=unit,
                    target_unit=target_unit,
                )
        except Exception:
            return

    def _execute_frenzy_fight(self, unit, attacker_unit, *, phase_name: str | None = None) -> bool:
        if unit is None or attacker_unit is None:
            return False
        if not self._frenzy_can_fight_target(unit, attacker_unit):
            return False
        try:
            from .fight_phase_manager import FightPhaseManager
            declarations = FightPhaseManager(self)._auto_select_melee_weapons(unit)
        except Exception:
            declarations = []
        if not declarations:
            return False
        self.resolve_frenzy_melee_attacks(unit, attacker_unit, declarations)
        return True

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

    def add_player(self, player: Player) -> None:
        """Add a player to the game."""
        self.players.append(player)
        player.set_game(self)
        self.refresh_rule_subscribers()

    def add_objective(self, objective: Objective) -> None:
        """Add an objective to the game."""
        self.objectives.append(objective)

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
        if apply_result.ok:
            self.decision_queue.pop(result.decision_id)
            self.event_system.publish("decision_resolved", result=result, request=request, game=self)
            self._maybe_queue_reactive_move_followup(request, result)
            self._maybe_queue_setup_reactive_followup(request, result)
            self._maybe_queue_reverberating_summons_followup(request, result)
            self._maybe_apply_optional_ability_confirmation(request, result)
            self._maybe_queue_bodyguard_return_followup(request, result)
            self._maybe_apply_mortal_wounds_followup(request, result)
            self._maybe_apply_bodyguard_loss_followup(request, result)
            self._maybe_apply_daemonic_patrons_loss_followup(request, result)
            self._maybe_apply_cult_ambush_followup(request, result)
            self._maybe_queue_code_chivalric_followup(request, result)
        return apply_result

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
            army = self._get_player_army(p)
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
            if u.is_attached_leader:
                continue
            # Joined support artillery models deploy with their bodyguard
            if bool(getattr(u, "is_joined_support", False)):
                continue

            # Embarked units deploy with their transport
            if u.is_embarked or getattr(u, "embarked_in", None) is not None:
                continue

            # Units allocated to any reserves are not deployed now
            if u.reserve_status in ("reserves", "strategic_reserves"):
                continue

            deployable.append(u)

        return deployable
    
    def record_deployment_action(self, player: Player, unit: 'Unit', action: str, location: tuple = None) -> None:
        """Record a deployment action for display in the InfoPane."""
        if action == 'deployed' and location:
            # Accept both 2D (x,y) and 3D (x,y,z) tuples; ignore extra fields (e.g. facing)
            if not isinstance(location, (list, tuple)) or len(location) < 2:
                raise RuntimeError("Deployment location must provide at least x and y coordinates.")
            x = float(location[0])
            y = float(location[1])
            z = float(location[2]) if len(location) > 2 else 0.0

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
        
        self.deployment_actions[player.id] = action_text

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
            deploying_player = self.players[cur_idx]
            opponent_idx = (cur_idx + 1) % n
            opponent_player = self.players[opponent_idx]
            if self.get_deployable_units(opponent_player):
                self.deployment_notice = (
                    f"{deploying_player.name} deployed a TITANIC unit; they will skip their next deployment turn. "
                    f"{opponent_player.name} will deploy again."
                )
            else:
                self.deployment_notice = (
                    f"{deploying_player.name} deployed a TITANIC unit; they would skip their next deployment turn "
                    f"(no opponent units left to benefit)."
                )

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
                skipped_player = self.players[next_idx]
                other_player = self.players[(next_idx + 1) % n]
                self.deployment_notice = (
                    f"{skipped_player.name} skips this deployment turn (TITANIC rule). "
                    f"{other_player.name} deploys again."
                )
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
        """Auto-deployment disabled; units must be deployed via UI/controller."""
        print("WARN: Auto-deployment disabled; deploy units via UI/controller.")
        self.waiting_for_deployment_input = True
        return

    def auto_deploy_unit(self, unit: 'Unit') -> bool:
        """Auto-deployment disabled; units must be deployed via UI/controller."""
        name = getattr(unit, "name", "Unit")
        logger.warning("WARN: auto_deploy_unit called for %s; manual placement required.", name)
        return False


    def _is_position_too_crowded(self, x: float, y: float, unit: 'Unit', player_id: str) -> bool:
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

    def _get_infiltrate_search_zones(self, player_id: str, battlefield_width: float, battlefield_height: float) -> list:
        """Get valid search zones for infiltrate units (avoiding enemy deployment zones and 9\" buffer)."""
        # We intentionally do NOT derive "safe" search rectangles from deployment-zone bounding boxes.
        # Infiltrate legality is enforced by the validation logic itself (enemy zone + 9" buffer + enemy models).
        margin = 3.0
        return [(margin, battlefield_width - margin, margin, battlefield_height - margin)]

    def _deploy_unit_at_position(self, unit: 'Unit', x: float, y: float, z: float) -> bool:
        """Deploy a unit at the specified position using the same flow as manual deployment."""
        # Use the exact same approach as manual deployment in GameView.on_mouse_press
        # Calculate model positions (this also sets the positions internally)
        # CRITICAL: Use deployment-specific boundary repulsors to ensure models stay within deployment zones
        # This must match the repulsors used in is_valid_deployment_position for consistency
        deployment_repulsors = self.get_boundary_repulsors(unit, context='deployment')
        model_positions = unit.calculate_model_positions(
            x, y, self.map, avoid_friendly_units=False, boundary_repulsors=deployment_repulsors
        )

        if not model_positions:
            print(f"DEBUG: Infiltrate - no model positions found for {unit.name} at candidate ({x:.1f}, {y:.1f})")
            return False

        # CRITICAL: Validate that all models are actually within deployment zone after positioning
        # This is a final safety check to catch any edge cases where models extend outside zones
        # EXCEPTION: Skip this check for Infiltrate units as they can deploy outside deployment zones
        parent_army = unit.get_parent_army()
        player_id = parent_army.player.id if parent_army and parent_army.player else None
        if player_id and not unit.has_infiltrate():
            for model, position in zip(unit.models, model_positions):
                model_x, model_y = position[0], position[1]
                if not self.is_position_wholly_in_deployment_zone(model_x, model_y, model.model_base, player_id):
                    print(
                        "CRITICAL: Auto-deployment validation failed - "
                        f"{unit.name} {model.name} at ({model_x:.1f}, {model_y:.1f}) extends outside deployment zone"
                    )
                    return False

        # Unit position is now determined by model positions

        # Place unit on map (same as manual)
        if self.map and self.map.place_unit(unit):
            # Don't set unit.deployed here - let the calling function handle it
            return True
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

    def is_position_in_deployment_zone(self, x: float, y: float, player_id: str) -> bool:
        """Check if a position is within a player's deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False
        
        if player_id not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_id]
        
        # Only mission zones are supported
        if 'mission_zones' in zone and zone['mission_zones']:
            for mission_zone in zone['mission_zones']:
                if mission_zone.contains_point(x, y):
                    return True
        return False

    def is_model_wholly_in_deployment_zone(self, model: 'Model', player_id: str) -> bool:
        """Check if a model's entire base is wholly within a player's deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            raise RuntimeError("Deployment zones not configured (invalid configuration).")
        
        if player_id not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_id]
        
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

    def is_position_wholly_in_deployment_zone(self, x: float, y: float, model_base, player_id: str) -> bool:
        """Check if a model base at (x,y) is wholly within the player's deployment zone,
        using mission zones with cutout-aware Shapely checks when available."""
        # Require configured zones
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False

        # Player must have a zone
        if player_id not in self.deployment_zones:
            return False

        zone_info = self.deployment_zones[player_id]

        # Only support mission_zones from missions.py with cutouts
        if 'mission_zones' in zone_info and zone_info['mission_zones']:
            for mission_zone in zone_info['mission_zones']:
                if model_base.base_type.name == 'CIRCULAR':
                    # Coerce radius to scalar
                    radius_val = getattr(model_base, 'radius', None)
                    if radius_val is None:
                        radius_val = model_base.get_radius() if hasattr(model_base, 'get_radius') else 0.5
                    if isinstance(radius_val, (list, tuple)):
                        radius_val = float(max(radius_val)) if radius_val else 0.5
                    else:
                        radius_val = float(radius_val)
                    if mission_zone.contains_circular_base(x, y, radius_val):
                        return True
                else:
                    # Use provided Shapely geometry from the base itself.
                    if not hasattr(model_base, 'get_base_shape_at'):
                        return False
                    base_geom = model_base.get_base_shape_at(x, y, getattr(model_base, 'facing', 0.0))
                    if mission_zone.contains_base_geometry(base_geom):
                        return True
            return False
        return False

    def is_position_in_enemy_deployment_zone(self, x: float, y: float, player_id: str) -> bool:
        """Check if a position is within any enemy deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False
        
        for zone_player_id, zone in self.deployment_zones.items():
            if zone_player_id != player_id:
                # Deployment zones are polygons (mission_zones); rectangular zones are not supported.
                if 'mission_zones' not in zone or not zone['mission_zones']:
                    raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
                for mission_zone in zone['mission_zones']:
                    if mission_zone.contains_point(x, y):
                        return True
        return False

    def get_distance_to_enemy_deployment_zone(self, x: float, y: float, player_id: str) -> float:
        """Get the minimum distance from a position to any enemy deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return float('inf')
        
        min_distance = float('inf')
        
        for zone_player_id, zone in self.deployment_zones.items():
            if zone_player_id != player_id and 'mission_zones' in zone and zone['mission_zones']:
                from shapely.geometry import Point as _ShPoint
                from shapely.geometry import Polygon as _ShPoly
                pt = _ShPoint(x, y)
                for mission_zone in zone['mission_zones']:
                    poly = _ShPoly(mission_zone.vertices)
                    d = pt.distance(poly)
                    if d < min_distance:
                        min_distance = d
        
        return min_distance

    def get_distance_to_enemy_models(self, x: float, y: float, player_id: str) -> float:
        """Get the minimum distance from a position to any enemy model."""
        min_distance = float('inf')
        
        for player in self.players:
            if player.id != player_id and player.get_army():
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
        player_id = unit.get_parent_army().player.id if unit.get_parent_army() and unit.get_parent_army().player else None
        
        if context == 'deployment':
            # For deployment, add deployment zone boundaries (mission-aware) and cutouts as repulsors
            if hasattr(self, 'deployment_zones') and self.deployment_zones and player_id:
                if player_id in self.deployment_zones:
                    zone = self.deployment_zones[player_id]
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

    def is_valid_deployment_position(self, unit: 'Unit', x: float, y: float, player_id: str) -> bool:
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

            from ..battlefield.map import validate_ruins_placement
            for model, position in zip(unit.models, model_positions):
                model_x, model_y = position[0], position[1]

                # Check if any part of the model is in enemy deployment zone
                if self.is_position_in_enemy_deployment_zone(model_x, model_y, player_id):
                    model_name = getattr(model, 'name', 'model')
                    print(
                        f"DEBUG: Infiltrate - {unit.name} {model_name} at ({model_x:.1f}, {model_y:.1f}) "
                        "is inside enemy deployment zone"
                    )
                    return False

                # Check 9" distance to enemy deployment zone (from model edge)
                base_radius = model.model_base.get_radius()
                distance_to_enemy_zone = self.get_distance_to_enemy_deployment_zone(model_x, model_y, player_id)
                if distance_to_enemy_zone - base_radius < 9.0:
                    model_name = getattr(model, 'name', 'model')
                    print(
                        f"DEBUG: Infiltrate - {unit.name} {model_name} too close to enemy zone: "
                        f"edge_distance={distance_to_enemy_zone:.2f}\" base_radius={base_radius:.2f}\" < 9\""
                    )
                    return False

                # Check 9" distance to enemy models (from model edge)
                distance_to_enemy_models = self.get_distance_to_enemy_models(model_x, model_y, player_id)
                if distance_to_enemy_models - base_radius < 9.0:
                    model_name = getattr(model, 'name', 'model')
                    print(
                        f"DEBUG: Infiltrate - {unit.name} {model_name} too close to enemy models: "
                        f"edge_distance={distance_to_enemy_models:.2f}\" base_radius={base_radius:.2f}\" < 9\""
                    )
                    return False
                # RUINS validation: cannot start/end overlapping walls/floors
                model_z = position[2] if len(position) > 2 else 0.0
                ruins_validation = validate_ruins_placement(
                    unit, (model_x, model_y, model_z), self.map.terrain_features, moving_model=model
                )
                if not ruins_validation['valid']:
                    model_name = getattr(model, 'name', 'model')
                    reason = ruins_validation.get('reason', 'unknown')
                    floor_level = ruins_validation.get('floor_level', '?')
                    print(
                        f"DEBUG: Infiltrate - RUINS validation failed for {unit.name} {model_name}: "
                        f"{reason} (floor {floor_level})"
                    )
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

            from ..battlefield.map import validate_ruins_placement
            for model, position in zip(unit.models, model_positions):
                model_x, model_y, model_z = position[0], position[1], position[2]

                # Check if this model would be wholly within the deployment zone
                if not self.is_position_wholly_in_deployment_zone(model_x, model_y, model.model_base, player_id):
                    model_name = getattr(model, 'name', 'model')
                    print(
                        f"DEBUG: Zone check failed for {unit.name} {model_name} at "
                        f"({model_x:.1f}, {model_y:.1f}) in player '{player_id}' zone"
                    )
                    return False

                # Check RUINS terrain placement rules
                ruins_validation = validate_ruins_placement(
                    unit, (model_x, model_y, model_z), self.map.terrain_features, moving_model=model
                )
                if not ruins_validation['valid']:
                    model_name = getattr(model, 'name', 'model')
                    print(
                        f"DEBUG: RUINS validation failed for {unit.name} {model_name}: "
                        f"{ruins_validation['reason']}"
                    )
                    return False
            return True

    def is_valid_single_model_deployment(self, model: 'Model', x: float, y: float, z: float, player_id: str) -> dict:
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
            if self.is_position_in_enemy_deployment_zone(x, y, player_id):
                return {'valid': False, 'reason': 'Inside enemy deployment zone'}
            # 9" from enemy zone (from model edge)
            base_radius = model.model_base.get_radius()
            distance_to_enemy_zone = self.get_distance_to_enemy_deployment_zone(x, y, player_id)
            if distance_to_enemy_zone - base_radius < 9.0:
                return {'valid': False, 'reason': 'Too close to enemy deployment zone (<9\")'}
            # 9" from enemy models (from model edge)
            distance_to_enemy_models = self.get_distance_to_enemy_models(x, y, player_id)
            if distance_to_enemy_models - base_radius < 9.0:
                return {'valid': False, 'reason': 'Too close to enemy models (<9\")'}
        else:
            # Normal deployment: wholly within own zone
            if not self.is_position_wholly_in_deployment_zone(x, y, model.model_base, player_id):
                return {'valid': False, 'reason': 'Model base not wholly within deployment zone'}

        # RUINS placement validation for this single model
        from ..battlefield.map import validate_ruins_placement
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

    def start_command_phase(self) -> None:
        """Start the command phase: active player gains normal CP, then resolves any bonus CP sources."""
        # Battle-shock expires at the start of *your* next Command phase (even if the unit was later destroyed).
        # Clear it before doing anything else in the Command phase.
        self.battle_shock_step_active = False
        current_player = self.get_current_player()
        if current_player is None:
            return
        army = self._get_player_army(current_player)
        if army is None:
            return

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
            return max(0, int(requested_vp or 0))

        vp = int(requested_vp or 0)
        if vp <= 0:
            return 0

        # Per-turn cap (applies whenever the card scores this window).
        per_turn_cap = getattr(card, "score_cap_per_turn", None)
        if per_turn_cap is not None:
            vp = min(vp, int(per_turn_cap))

        # Total cap across the battle for this specific card instance.
        total_scored = int(getattr(card, "total_scored", 0) or 0)
        total_cap = getattr(card, "score_cap_total", None)
        effective_total_cap: int | None = None
        if total_cap is not None:
            effective_total_cap = int(total_cap)

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
        """Notify that VP were lost due to caps (event system only)."""
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
        if not hasattr(self, "event_system") or not hasattr(self.event_system, "publish"):
            raise RuntimeError("Event system missing for vp_capped notification.")
        self.event_system.publish("vp_capped", **payload)

    def _current_phase_label(self) -> str:
        if hasattr(self, "is_in_setup_phase") and self.is_in_setup_phase():
            setup_phase = self.get_current_setup_phase()
            return setup_phase.name.replace("_", " ").title() if setup_phase else "Setup"
        phase = getattr(self, "phase", None)
        if phase is None:
            return "Unknown Phase"
        if hasattr(phase, "name"):
            return str(phase.name).replace("_", " ").title()
        return str(phase)

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
        if not hasattr(player, "vp_history") or player.vp_history is None:
            player.vp_history = []
        card_name = getattr(card, "name", None) if card is not None else None
        card_scoring_text = None
        if card is not None:
            card_scoring_text = getattr(card, "scoring_text", None) or getattr(card, "summary", None)
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
        player.vp_history.append(entry)

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
        vp = int(requested_vp or 0)
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
            card.total_scored = int(getattr(card, "total_scored", 0) or 0) + int(to_add)

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

        self._record_vp_award(
            player=player,
            requested_vp=int(requested_vp or 0),
            awarded_vp=int(to_add),
            source=source_key,
            card=card,
            details=details,
            timing=timing,
        )

        details_payload = details
        if isinstance(details, list):
            details_payload = [str(d) for d in details]
        elif details is not None:
            details_payload = str(details)
        card_name = getattr(card, "name", None) if card is not None else None
        self.event_system.publish(
            "vp_awarded",
            player=player,
            source=str(source_key),
            requested_vp=int(requested_vp or 0),
            awarded_vp=int(to_add),
            total_vp=int(getattr(player, "score", 0) or 0),
            vp_primary=int(getattr(player, "vp_primary", 0) or 0),
            vp_secondary=int(getattr(player, "vp_secondary", 0) or 0),
            vp_battle_ready=int(getattr(player, "vp_battle_ready", 0) or 0),
            card_name=card_name,
            timing=str(timing) if timing is not None else None,
            phase=self._current_phase_label(),
            details=details_payload,
        )

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
                    print(
                        f"INFO: {turn_ending_player.name} scored {added} VP (end of turn) from Primary: "
                        f"{turn_ending_player.primary_mission.name}"
                    )

        # Primary: end-of-opponent's-turn scoring (only for primaries that explicitly do so, e.g. Burden of Trust).
        for p in list(getattr(self, "players", []) or []):
            if p is turn_ending_player:
                continue
            prim = getattr(p, "primary_mission", None)
            fn = getattr(prim, "score_at_end_of_opponents_turn", None)
            if callable(fn):
                vp = int(fn(self, p, turn_ending_player) or 0)
                if vp:
                    added = self.award_vp(
                        p,
                        vp,
                        source="primary",
                        card=prim,
                        timing="End of opponent turn",
                    )
                    if added:
                        print(
                            f"INFO: {p.name} scored {added} VP (opponent turn end) from Primary: "
                            f"{getattr(prim, 'name', 'Primary')}"
                        )

        # Secondary: evaluate active cards for BOTH players based on the card's scoring window.
        from .mission_cards import SecondaryScoringWindow

        def _should_score(card: SecondaryMissionCard, scoring_player: Player, ending_player: Player) -> bool:
            score_window_fn = getattr(card, "score_window", None)
            window = (
                score_window_fn()
                if callable(score_window_fn)
                else getattr(card, "scoring_window", SecondaryScoringWindow.END_OF_YOUR_TURN)
            )
            if scoring_player is ending_player:
                return window in (
                    SecondaryScoringWindow.END_OF_YOUR_TURN,
                    SecondaryScoringWindow.END_OF_EITHER_PLAYER_TURN,
                )
            return window in (SecondaryScoringWindow.END_OF_EITHER_PLAYER_TURN, SecondaryScoringWindow.END_OF_OPPONENT_TURN)

        # Tactical vs Fixed: in Fixed mode, scored cards are NOT discarded on scoring.
        is_fixed = self._is_fixed_secondaries()

        for scoring_player in list(self.players):
            achieved: list[SecondaryMissionCard] = []
            total_secondary_vp = 0
            for card in list(getattr(scoring_player, 'active_secondaries', [])):
                if not _should_score(card, scoring_player, turn_ending_player):
                    continue
                result = card.score_at_end_of_turn(self, scoring_player)
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
                        print(f"INFO: {scoring_player.name} scored {added} VP from Secondary: {card.name}")
                if getattr(result, 'achieved', False):
                    achieved.append(card)

            # a) Tactical: If you scored 1+ VP from a Secondary, discard that card (achieved).
            if (not is_fixed) and total_secondary_vp > 0:
                scoring_player.discard_achieved_secondaries(achieved)

        # End-of-turn cleanup for temporary stratagem effects.
        army = getattr(turn_ending_player, "army", None)
        if army is not None:
            for unit in list(getattr(army, "units", []) or []):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if sr.pop("apoplectic_frenzy_active", None) is not None:
                    sr.pop("apoplectic_frenzy_turn", None)
                    unit.special_rules = sr
                if sr.pop("red_wrath_mode", None) is not None:
                    sr.pop("red_wrath_turn_owner", None)
                    sr.pop("red_wrath_turn", None)
                    sr.pop("red_wrath_source", None)
                    unit.special_rules = sr
                if sr.get("selected_to_shoot_charge_reroll_target_ids"):
                    owner = str(sr.get("selected_to_shoot_charge_reroll_turn_owner", "") or "")
                    current_owner = ""
                    try:
                        current_owner = get_entity_id(turn_ending_player)
                    except Exception:
                        current_owner = str(getattr(turn_ending_player, "id", "") or "")
                    if (not owner) or (current_owner and owner == current_owner):
                        for key in (
                            "selected_to_shoot_charge_reroll_target_ids",
                            "selected_to_shoot_charge_reroll_turn_owner",
                            "selected_to_shoot_charge_reroll_turn",
                            "selected_to_shoot_charge_reroll_source",
                        ):
                            sr.pop(key, None)
                        unit.special_rules = sr
                if str(sr.get("post_shoot_ap_bonus_selected_scope", "") or "").strip().lower() == "turn":
                    owner = str(sr.get("post_shoot_ap_bonus_selected_owner", "") or "")
                    current_owner = ""
                    try:
                        current_owner = get_entity_id(turn_ending_player)
                    except Exception:
                        current_owner = str(getattr(turn_ending_player, "id", "") or "")
                    if (not owner) or (current_owner and owner == current_owner):
                        selected_turn = int(sr.get("post_shoot_ap_bonus_selected_turn", 0) or 0)
                        current_turn = int(getattr(self, "turn", 0) or 0)
                        if (not selected_turn) or (current_turn and selected_turn == current_turn):
                            for key in (
                                "post_shoot_ap_bonus_selected_owner",
                                "post_shoot_ap_bonus_selected_turn",
                                "post_shoot_ap_bonus_selected_scope",
                                "post_shoot_ap_bonus_selected_phase",
                            ):
                                sr.pop(key, None)
                            unit.special_rules = sr

        # Imperial Knights: Code Chivalric deed completion at end of turn.
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "get_army", lambda: None)()
            mgr = getattr(army, "code_chivalric", None) if army is not None else None
            if mgr is None:
                continue
            mgr.check_end_of_turn(game=self, turn_ending_player=turn_ending_player)

        # b) Allow voluntary discard for current player to gain 1CP (UI/controller should call explicitly). Here we do nothing automatically.

        # c) If deck runs out, player cannot generate additional secondaries (handled by deck empty check during draws)

        # End of opponent's turn: optional abilities to move units into Strategic Reserves.
        self._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player)

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
                vp = int(player.primary_mission.score_at_end_of_battle_round(self, player) or 0)
                if vp:
                    added = self.award_vp(
                        player,
                        vp,
                        source="primary",
                        card=player.primary_mission,
                        timing="End of battle round",
                    )
                    if added:
                        print(
                            f"INFO: {player.name} scored {added} VP (end of battle round) from Primary: "
                            f"{player.primary_mission.name}"
                        )

        # Imperial Knights: Code Chivalric deed completion at end of battle round.
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "get_army", lambda: None)()
            mgr = getattr(army, "code_chivalric", None) if army is not None else None
            if mgr is None:
                continue
            mgr.check_end_of_battle_round(game=self, battle_round=self.turn)

        # Emperor's Children: Pledges to the Dark Prince resolution (Coterie of the Conceited).
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

        # Chapter Approved: any units still in reserves at the end of battle round 3 are destroyed.
        # `self.turn` is the current battle round number when this hook is invoked.
        if int(getattr(self, "turn", 0) or 0) == 3:
            for p in list(getattr(self, "players", []) or []):
                army = getattr(p, "get_army", lambda: None)()
                if army is None:
                    continue
                to_remove = []
                for u in list(getattr(army, "units", []) or []):
                    if getattr(u, "is_in_reserves", lambda: False)() and bool(getattr(u, "_started_in_reserves", False)):
                        to_remove.append(u)
                for u in to_remove:
                    logger.warning(
                        "%s destroyed - still in reserves at end of battle round 3",
                        getattr(u, "name", "Unit"),
                    )
                    if u in army.units:
                        army.units.remove(u)

    def record_unit_destroyed(self, unit: 'Unit') -> None:
        """Record a unit destroyed event and incrementally score relevant secondaries."""
        if not hasattr(self, "destroyed_units_this_turn"):
            self.destroyed_units_this_turn = []
        self.destroyed_units_this_turn.append(unit)

        # Tally for Purge the Foe end-of-battle-round scoring
        if not hasattr(self, "destroyed_units_this_battle_round_by_player"):
            self.destroyed_units_this_battle_round_by_player = {}
        owner_player = unit.get_parent_army().player if unit.get_parent_army() else None
        if owner_player is not None:
            self.destroyed_units_this_battle_round_by_player[owner_player] = (
                self.destroyed_units_this_battle_round_by_player.get(owner_player, 0) + 1
            )

        # Incremental scoring for active secondaries that score on unit destruction
        for player in self.players:
            if player is owner_player:
                continue
            for card in getattr(player, 'active_secondaries', []) or []:
                fn = getattr(card, "on_unit_destroyed", None)
                if not callable(fn):
                    continue
                points = int(fn(self, player, unit) or 0)
                if points:
                    unit_name = getattr(unit, "name", "Unit")
                    if getattr(unit, "is_character", False):
                        detail = f"Destroyed Character unit: {unit_name}"
                    else:
                        detail = f"Destroyed unit: {unit_name}"
                    added = self.award_vp(
                        player,
                        points,
                        source="secondary",
                        card=card,
                        details=detail,
                        timing="Unit destroyed",
                    )
                    if added:
                        print(
                            f"INFO: {player.name} scored {added} VP from Secondary: "
                            f"{getattr(card, 'name', 'Unknown')} (unit destroyed)"
                        )

    def record_model_destroyed(self, model: 'Model') -> None:
        """Record a model destroyed event and incrementally score relevant secondaries that key off models."""
        if not hasattr(self, "models_destroyed_this_turn"):
            self.models_destroyed_this_turn = []
        self.models_destroyed_this_turn.append(model)

        # Incremental scoring for active secondaries that score on model destruction (e.g., Fixed Assassination).
        for player in self.players:
            for card in getattr(player, "active_secondaries", []) or []:
                fn = getattr(card, "on_model_destroyed", None)
                if not callable(fn):
                    continue
                points = int(fn(self, player, model) or 0)
                if points:
                    model_name = getattr(model, "name", "Model")
                    unit = getattr(model, "parent_unit", None)
                    if getattr(model, "is_character", False):
                        detail = f"Destroyed Character: {model_name}"
                    else:
                        detail = f"Destroyed model: {model_name}"
                    if unit is not None and getattr(unit, "name", None) and unit.name != model_name:
                        detail = f"{detail} (Unit: {unit.name})"
                    added = self.award_vp(
                        player,
                        points,
                        source="secondary",
                        card=card,
                        details=detail,
                        timing="Model destroyed",
                    )
                    if added:
                        print(
                            f"INFO: {player.name} scored {added} VP from Secondary: "
                            f"{getattr(card, 'name', 'Unknown')} (model destroyed)"
                        )

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
            army = unit.get_parent_army()
            mgr = getattr(army, "templar_vows", None) if army is not None else None
            if mgr is not None and mgr.allow_action_after_advance(unit, self):
                allow_advance_action = True
            if not allow_advance_action:
                return {"valid": False, "reason": "Units that Advanced cannot perform Actions"}
        # Not if not eligible to shoot this phase (includes units that have already been selected to shoot)
        if unit.round_state.shot_this_round:
            return {"valid": False, "reason": "Units already selected to shoot cannot start an Action this phase"}
        return {"valid": True, "reason": "Eligible"}

    def _unit_is_in_player_deployment(self, player: Player, unit: 'Unit') -> bool:
        zones = self.deployment_zones.get(player.id, {})
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

    def _objective_in_player_deployment(self, player: Player, objective_point) -> bool:
        zones = self.deployment_zones.get(player.id, {})
        zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
        if not zone:
            return False
        return hasattr(zone, 'contains_point') and zone.contains_point(objective_point.x, objective_point.y)

    def _unit_within_any_terrain_feature(self, unit: 'Unit') -> bool:
        for model in unit.models:
            if not model.is_alive:
                continue
            base_geom = model.model_base.get_base_shape()
            for t in self.map.terrain_features:
                if base_geom.intersects(t.footprint):
                    return True
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
                base = model.model_base
                if hasattr(base, 'get_base_shape') and hasattr(area, 'intersects'):
                    base_geom = base.get_base_shape()
                    if base_geom.intersects(area):
                        return obj
                    continue
                mpos = model.get_location()
                if mpos:
                    dx = mpos[0] - loc.x
                    dy = mpos[1] - loc.y
                    radius = getattr(base, 'get_radius', lambda: 1.0)()
                    if (dx * dx + dy * dy) ** 0.5 <= (loc.control_radius + radius):
                        return obj
        return None

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
        from .mission_cards import BurdenOfTrustPrimary
        if not isinstance(prim, BurdenOfTrustPrimary):
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
                if get_entity_id(u) in used_units:
                    continue
                if self._unit_within_range_of_objective(u) is obj:
                    chosen = u
                    break
            if chosen is None:
                continue
            chosen.guarding_objective = obj
            used_units.add(get_entity_id(chosen))

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
                zones = self.deployment_zones.get(p.id, {})
                zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
                if zone and hasattr(zone, "contains_point") and zone.contains_point(loc.x, loc.y):
                    return False
            return True

        # Unexploded Ordnance: NML objectives become Hazard objectives.
        from .mission_cards import UnexplodedOrdnancePrimary
        if isinstance(prim, UnexplodedOrdnancePrimary):
            for obj in getattr(self.map, "objectives", []) or []:
                loc = getattr(obj, "location", None)
                if not loc or getattr(loc, "removed", False):
                    continue
                if _is_nml(loc):
                    loc.is_hazard = True

        # Supply Drop: initialize Alpha/Omega selection if primary supports it.
        fn = getattr(prim, "initialize_alpha_omega", None)
        if callable(fn):
            fn(self)

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
        from .mission_cards import TheRitualPrimary
        if not isinstance(getattr(unit.get_parent_army().player, "primary_mission", None), TheRitualPrimary):
            return {"valid": False, "reason": "Primary mission is not The Ritual"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        x, y = float(new_objective_xy[0]), float(new_objective_xy[1])

        # Must be within No Man's Land (not in either deployment zone)
        for p in self.players:
            zones = self.deployment_zones.get(p.id, {})
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
                zones = self.deployment_zones.get(p.id, {})
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
        from .mission_cards import UnexplodedOrdnancePrimary
        if not isinstance(getattr(unit.get_parent_army().player, "primary_mission", None), UnexplodedOrdnancePrimary):
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
        nx, ny = float(new_xy[0]), float(new_xy[1])
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
        if not hasattr(self, "completed_actions_this_turn"):
            self.completed_actions_this_turn = []
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
                opponents = [p for p in self.players if p is not actor]
                opp = opponents[0] if opponents else None
                zones = self.deployment_zones.get(opp.id, {}) if opp is not None else {}
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
                from ..battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
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
                    opponent = next((p for p in self.players if p is not actor), None)
                    zones = self.deployment_zones.get(opponent.id, {}) if opponent is not None else {}
                    zone = zones.get('zone') or zones.get('Attacker Zone') or zones.get('Defender Zone')
                    in_opponent_dz = bool(zone and hasattr(zone, 'contains_point') and zone.contains_point(loc.x, loc.y))
                    vp = 10 if in_opponent_dz else 5
                    # Remove the objective
                    loc.removed = True
                    print(f"INFO: Scorched Earth burned objective at ({loc.x:.1f}, {loc.y:.1f})")
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
                        print(f"INFO: {actor.name} scored {added} VP for burning objective")
                unit.round_state.performing_action_name = None
                unit.round_state.action_locked_until_turn_end = False
            else:
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

    def roll_brazen_fury_distance(self, unit: 'Unit') -> int:
        """Roll Brazen Fury distance (D6)."""
        if unit is None:
            return 0
        from ..utility.dice import get_roll
        base_roll = int(get_roll("D6") or 0)
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(player, f"Brazen Fury roll: {int(base_roll or 0)}\" for {unit.name}")
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
    
    def _normalize_ability_text(self, text: str) -> str:
        raw = re.sub(r"<[^>]+>", " ", str(text or ""))
        raw = html.unescape(raw)
        raw = re.sub(r"\s+", " ", raw).strip().lower()
        return raw

    def _reserves_denial_ranges_for_unit(self, unit) -> list[dict]:
        ranges: list[dict] = []
        for ab in list(getattr(unit, "possible_abilities", []) or []):
            name = str(getattr(ab, "name", "") or "")
            desc = str(getattr(ab, "description", "") or "")
            text = self._normalize_ability_text(f"{name} {desc}")
            if not text:
                continue
            flat = re.sub(r"[^a-z0-9.]+", " ", text).strip()
            if "enemy" not in flat:
                continue
            if ("cannot be set up" not in flat) and ("cannot set up" not in flat):
                continue
            horizontal_only = ("horizontally" in flat) or ("horizontal" in flat)
            distances = []
            for match in re.finditer(r"within\s+(\d+(?:\.\d+)?)\b", flat):
                distances.append(float(match.group(1)))
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
        parent_army = unit.get_parent_army()
        player = parent_army.player if parent_army is not None else None
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
            if callable(getattr(enemy, "is_alive", None)):
                if not enemy.is_alive():
                    continue
            elif not getattr(enemy, "is_alive", True):
                continue
            if not bool(getattr(enemy, "deployed", False)):
                continue
            if str(getattr(enemy, "reserve_status", "deployed")) != "deployed":
                continue
            if getattr(enemy, "embarked_in", None) is not None:
                continue
            if bool(getattr(enemy, "is_embarked", False)):
                continue

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
                        if isinstance(rinfo, dict):
                            r = float(rinfo.get("range", 0) or 0)
                            horizontal_only = bool(rinfo.get("horizontal_only", False))
                        elif isinstance(rinfo, (list, tuple)) and rinfo:
                            r = float(rinfo[0])
                            if len(rinfo) > 1:
                                horizontal_only = bool(rinfo[1])
                        else:
                            r = float(rinfo)
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
        # Clear any prior pending edge-touch marker for this unit.
        if hasattr(unit, "_pending_reserves_edge_touch"):
            delattr(unit, "_pending_reserves_edge_touch")

        strategic_ok = True
        strategic_used_edge_touch = False
        if unit.is_in_strategic_reserves():
            strategic_ok = False
            # Determine which edge(s) to validate
            if battlefield_edge:
                candidate_edges = [battlefield_edge]
            else:
                candidate_edges = ["own", "left", "right", "enemy"]

            def _model_radius(m) -> float:
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
            boundary_repulsors = self.map.get_battlefield_edge_repulsors() if self.map else []
            prospective = unit.calculate_model_positions(
                position[0],
                position[1],
                self.map,
                boundary_repulsors=boundary_repulsors,
                avoid_friendly_units=True,
            )
            for m, loc in zip(unit.models, snapshot):
                if loc:
                    m.set_location(*loc)

            if not prospective:
                return False

            # Round 2 Strategic Reserves restriction: cannot be set up within the enemy deployment zone
            # (applies only when using Strategic Reserves edge placement, not Deep Strike alternative).
            parent_army = unit.get_parent_army()
            player_id = parent_army.player.id if parent_army and parent_army.player else None

            for edge in candidate_edges:
                if not self.is_valid_strategic_reserves_edge(edge):
                    continue

                # Turn-based enemy deployment zone restriction (turn 2 only)
                if self.turn == 2 and player_id:
                    any_in_enemy_dz = False
                    for (mx, my, _mz, _f) in prospective:
                        if self.is_position_in_enemy_deployment_zone(float(mx), float(my), player_id):
                            any_in_enemy_dz = True
                            break
                    if any_in_enemy_dz:
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
        boundary_repulsors = self.map.get_battlefield_edge_repulsors() if self.map else []
        prospective = unit.calculate_model_positions(
            position[0],
            position[1],
            self.map,
            boundary_repulsors=boundary_repulsors,
            avoid_friendly_units=True,
        )
        if not prospective:
            return False

        for m, loc in zip(unit.models, prospective):
            if loc:
                m.set_location(*loc)
        min_enemy_distance = float(self._warp_rifts_min_distance(unit) or 9.0)
        for m, loc in zip(unit.models, snapshot):
            if loc:
                m.set_location(*loc)

        if battlefield_edge is None:
            try:
                if hasattr(unit, "get_deep_strike_min_distance_override"):
                    override = unit.get_deep_strike_min_distance_override()
                else:
                    override = None
            except Exception:
                override = None
            if override:
                min_enemy_distance = min(float(min_enemy_distance), float(override))

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
                setattr(unit, "_pending_reserves_edge_touch", True)
            if ok:
                if battlefield_edge is None:
                    pending_deep_strike = bool(deep_strike_ok)
                else:
                    pending_deep_strike = bool(deep_strike_ok and not strategic_ok)
                setattr(unit, "_pending_reserves_deep_strike", pending_deep_strike)
            return ok

        setattr(unit, "_pending_reserves_deep_strike", True)
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
            Dict mapping player ids to lists of units that arrived from reserves
        """
        arrival_results = {}
        current_player = self.get_current_player()

        # Handle reserves arrivals for the current player
        units_arrived = self.process_player_reserves_arrivals(current_player)
        arrival_results[current_player.id] = units_arrived

        # Cult Ambush: opponent's reinforcements step (end of this player's Movement phase)
        self._handle_cult_ambush_reinforcements(current_player)

        # Chapter Approved "destroy after battle round 3" is enforced at end-of-battle-round.

        return arrival_results

    def _handle_cult_ambush_reinforcements(self, current_player) -> None:
        players = list(getattr(self, "players", []) or [])
        for p in players:
            if p is None or p is current_player:
                continue
            army = p.get_army()
            mgr = getattr(army, "cult_ambush", None) if army is not None else None
            if mgr is None:
                continue
            mgr.handle_reinforcements(game=self, player=p)

    def process_player_reserves_arrivals(self, player: Player) -> List['Unit']:
        """Process reserves arrivals for a specific player.

        This method requires explicit placement decisions from a controller.

        Args:
            player: The player whose reserves arrivals to process

        Returns:
            List of units that arrived from reserves
        """
        units_arrived: list['Unit'] = []
        units_that_can_arrive = self.get_units_that_can_arrive_from_reserves(player)
        units_that_must_arrive = self.get_units_that_must_arrive_from_reserves(player)

        player_name = getattr(player, "name", "Player")
        logger.info("INFO: %s has %d units that can arrive from reserves", player_name, len(units_that_can_arrive))
        if units_that_must_arrive:
            logger.warning(
                "WARN: %s has %d units that must arrive from reserves; no placement provider is configured.",
                player_name,
                len(units_that_must_arrive),
            )

        # Queue explicit placement decisions for each eligible unit.
        try:
            from ..utility.entity_ids import get_entity_id
        except Exception:
            get_entity_id = None
        pending = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    try:
                        if str(getattr(req, "decision_type", "")) != DECISION_MOVE_UNIT:
                            continue
                        ctx = dict(getattr(req, "context", {}) or {})
                        if str(ctx.get("placement_kind", "")) != "reserves_arrival":
                            continue
                        uid = str(ctx.get("unit_id", "") or "")
                        if uid:
                            pending.add(uid)
                    except Exception:
                        continue
        except Exception:
            pending = set()
        must_ids = set()
        for unit in list(units_that_must_arrive or []):
            try:
                must_ids.add(str(get_entity_id(unit)))
            except Exception:
                continue
        # Deterministic ordering by entity id
        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")
        for unit in sorted(list(units_that_can_arrive or []), key=_unit_sort_key):
            try:
                unit_id = str(get_entity_id(unit))
            except Exception:
                unit_id = ""
            if unit_id and unit_id in pending:
                continue
            allow_skip = True
            if unit_id and unit_id in must_ids:
                allow_skip = False
            try:
                if unit is not None and hasattr(unit, "get_cloudstrider_deep_strike_source"):
                    source = str(unit.get_cloudstrider_deep_strike_source() or "")
                else:
                    source = ""
            except Exception:
                source = ""
            try:
                can_deep_strike = bool(getattr(unit, "has_deep_strike", lambda: False)())
            except Exception:
                can_deep_strike = False
            if source and can_deep_strike:
                try:
                    sr = getattr(unit, "special_rules", None)
                    if not isinstance(sr, dict):
                        sr = {}
                    owner_id = str(getattr(player, "id", "") or "")
                    current_turn = int(getattr(self, "turn", 0) or 0)
                    active = (
                        str(sr.get("cloudstrider_choice_turn_owner", "") or "") == owner_id
                        and int(sr.get("cloudstrider_choice_turn", 0) or 0) == current_turn
                    )
                except Exception:
                    active = False
                if not active:
                    ctx = {
                        "unit_id": unit_id,
                        "ability_name": source or "Cloudstrider",
                        "phase": "Movement phase",
                    }
                    message = (
                        f"{source or 'Cloudstrider'}: use 6\" Deep Strike placement "
                        f"(no charge this turn)?"
                    )
                    self._queue_optional_ability_confirmation(
                        player=player,
                        ability_key="cloudstrider",
                        ability_name=source or "Cloudstrider",
                        message=message,
                        context=ctx,
                        payload={"unit_id": unit_id},
                        instance_key=f"{unit_id}:{getattr(self, 'turn', 0)}:cloudstrider",
                    )
            request = self._build_reserves_arrival_request(unit, allow_skip=allow_skip)
            if request is not None:
                try:
                    self.request_decision(request)
                except Exception:
                    pass

        return units_arrived

    def find_valid_reserves_position(self, unit: 'Unit') -> Optional[Tuple[float, float, float]]:
        """Return None unless a controller provides an explicit placement."""
        return None

    def _build_reserves_arrival_request(self, unit: 'Unit', *, allow_skip: bool) -> Optional["DecisionRequest"]:
        if unit is None:
            return None
        from .decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id
        unit_id = get_entity_id(unit)
        options = [
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit_id, "movement_type": "deploy", "action": "confirm"},
            )
        ]
        if allow_skip:
            options.append(
                DecisionOption.create(
                    "Skip",
                    payload={"unit_id": unit_id, "movement_type": "deploy", "action": "skip"},
                )
            )
        player_id = None
        try:
            army = unit.get_parent_army()
        except Exception:
            army = getattr(unit, "parent_army", None)
        if army is not None:
            player = getattr(army, "player", None)
            player_id = getattr(player, "id", None) if player is not None else None
        allowed_model_ids = [get_entity_id(m) for m in list(getattr(unit, "models", []) or []) if m is not None]
        context = {
            "unit_id": unit_id,
            "movement_type": "deploy",
            "placement_kind": "reserves_arrival",
            "allowed_model_ids": allowed_model_ids,
            "allow_skip": bool(allow_skip),
            "battle_round": int(getattr(self, "turn", 0) or 0),
            "reserve_status": str(getattr(unit, "reserve_status", "") or ""),
        }
        return DecisionRequest.create(
            DECISION_MOVE_UNIT,
            f"Arrive from Reserves: {getattr(unit, 'name', 'Unit')}",
            player_id=player_id,
            options=options,
            context=context,
        )

    def get_first_turn_player_index(self) -> int:
        """Get the index of player who goes first (will be set during DETERMINE_FIRST_TURN_ORDER)"""
        return self.first_turn_player_index
    
    def is_in_setup_phase(self) -> bool:
        """Check if we're still in the setup phase."""
        return not self.setup_complete
    
    def get_current_setup_phase(self) -> SetupPhase:
        """Get the current setup phase."""
        return self.setup_phase
    
    def _advance_setup_phase_impl(self) -> bool:
        """Advance to the next setup phase. Returns True if setup is complete."""
        if self.setup_complete:
            return True
        
        current_phase_value = self.setup_phase.value
        next_phase_value = current_phase_value + 1
        
        if next_phase_value >= len(SetupPhase):
            # Setup is complete, start battle rounds
            self.setup_complete = True
            # AIRCRAFT are treated as Strategic Reserves once the battle starts.
            for player in list(self.players or []):
                if player is None:
                    raise RuntimeError("Missing player when applying aircraft reserve updates.")
                army = player.get_army()
                if army is None:
                    raise RuntimeError(f"Missing army for {player.name} when applying aircraft reserve updates.")
                for unit in list(army.units):
                    if unit is None:
                        continue
                    if not bool(getattr(unit, "is_aircraft", False)):
                        continue
                    if bool(getattr(unit, "hover_mode", False)):
                        continue
                    if str(getattr(unit, "reserve_status", "deployed")) != "reserves":
                        continue
                    unit.set_reserve_status("strategic_reserves")
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
            for player in list(self.players or []):
                if player is None:
                    raise RuntimeError("Missing player when starting battle round.")
                army = player.get_army()
                if army is None:
                    raise RuntimeError(f"Missing army for {player.name} when starting battle round.")
                for unit in list(army.units):
                    unit.initialize_round()
                # Army-level battle round start hook (faction rules/buffs)
                army.on_battle_round_start(self.turn)
            self.event_system.publish("battle_round_started", game=self, battle_round=self.turn)

            # Start of Command phase for the first battle round.
            self.start_command_phase()

            # Show detailed first turn information
            first_turn_player = self.get_current_player()
            if self.first_turn_player_index == self.attacker_index:
                role = "Attacker"
            elif self.first_turn_player_index == self.defender_index:
                role = "Defender"
            else:
                role = "Player"

            print(f"Setup complete! {first_turn_player.name} ({role}) goes first")
            return True
        else:
            self.setup_phase = SetupPhase(next_phase_value)
            print(f"Advanced to setup phase: {self.setup_phase.name}")
            return False

    def advance_setup_phase(self) -> bool:
        """Advance to the next setup phase. Returns True if setup is complete."""
        if self.in_command_context():
            return self._advance_setup_phase_impl()
        player_id = None
        try:
            player_id = self.get_current_player().id
        except Exception:
            player_id = None
        cmd = GameCommand.create(CMD_ADVANCE_SETUP_PHASE, player_id=player_id)
        result = self.apply_command(cmd)
        if getattr(result, "ok", False):
            return bool(getattr(result, "value", False))
        return bool(self.setup_complete)

    def execute_muster_armies_phase(
        self,
        player1_army_file: str = None,
        player2_army_file: str = None,
        player1_muster: "ArmyMusterRequest" = None,
        player2_muster: "ArmyMusterRequest" = None,
    ) -> None:
        """Phase 1: Muster Armies - Load army lists for both players."""
        print("MUSTER ARMIES: Loading army lists...")
        
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
        from ..roster.army import parse_army_list
        from ..roster.army_muster import ArmyMusterer
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
            print(f"{self.players[0].name}: {player1_units} units loaded from {player1_army_file}")
            print(f"{self.players[1].name}: {player2_units} units loaded from {player2_army_file}")
            for player in list(self.players[:2]):
                if player is None:
                    raise RuntimeError("Missing player during mustering.")
                army = player.get_army()
                if army is None:
                    raise RuntimeError(f"Missing army for {player.name} during mustering.")
                pending = list(army.get_pending_daemonic_allegiance_units() or [])
                if not pending:
                    continue
                if not bool(getattr(self, "is_authoritative", True)):
                    continue
                army.resolve_daemonic_allegiances(player=player, game=self)
        else:
            print("Not enough players loaded")
    
    def execute_select_mission_objectives_phase(self) -> None:
        """Phase 2: Select Mission Objectives - Choose mission and objectives."""
        print("SELECT MISSION OBJECTIVES: Setting up mission...")
        
        # Set up available commands for high-level strategy
        self.commands = ["attack", "defend", "move"]
        print(f"Commands configured: {self.commands}")
        
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
            print(f"Using default mission: {self.selected_mission_info}")
        else:
            print(f"Mission selected: {self.selected_mission_info}")
        
        # Mission objectives will be placed during CREATE_BATTLEFIELD phase
        print("Mission framework configured")

        # Imperial Knights: Code Chivalric selection (end of Read Mission Objectives step).
        for player in list(self.players or []):
            if player is None:
                raise RuntimeError("Missing player during mission objective selection.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {player.name} during mission objective selection.")
            mgr = getattr(army, "code_chivalric", None)
            if mgr is None:
                continue
            if not mgr._army_has_code_chivalric():
                continue
            mgr.on_read_mission_objectives(game=self, player=player)
    
    def execute_create_battlefield_phase(self, mission_name: str = None) -> None:
        """Phase 3: Create Battlefield - Set up map, terrain, deployment zones, and objectives."""
        print("CREATE BATTLEFIELD: Setting up battlefield...")
        
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
        print(f"Map created: {battlefield_width}\" x {battlefield_height}\"")
        
        # 2. Terrain features based on selected terrain layout
        from ..battlefield.terrain_layouts import instantiate_layout
        terrain_features = instantiate_layout(terrain_layout)
        if terrain_features:
            self.map.add_terrain_features(terrain_features)
            print(f"Terrain layout {terrain_layout} placed: {len(terrain_features)} features")
            # Debug: print RUINS footprints for verification
            from ..battlefield.map import TerrainType
            from ..utility.constants import RUINS_FLOOR_HEIGHT
            for idx, tf in enumerate(terrain_features):
                if getattr(tf, 'terrain_type', None) == TerrainType.RUINS:
                    coords = list(tf.footprint.exterior.coords)[:-1]
                    pairs = [(round(float(x), 2), round(float(y), 2)) for (x, y) in coords]
                    print(f"   - RUINS #{idx+1} footprint: {pairs}")
                    # Floors detail (ground=0, first=1, second=2)
                    floors = getattr(tf, 'floors', []) or []
                    for fl in floors:
                        poly = fl.get('polygon')
                        elev = float(fl.get('elevation', 0.0))
                        level = int(round(elev / float(RUINS_FLOOR_HEIGHT)))
                        if hasattr(poly, 'exterior'):
                            fcoords = list(poly.exterior.coords)[:-1]
                            fpairs = [(round(float(x), 2), round(float(y), 2)) for (x, y) in fcoords]
                            print(f"      - Floor L{level} (elev {elev:.1f}\"): {fpairs}")
        else:
            print(f"Terrain layout {terrain_layout} has no registered features")
        
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
                self.deployment_zones[self.players[0].id] = zone
            elif zone['zone_type'] == 'attacker':
                # Assign to second player as attacker
                self.deployment_zones[self.players[1].id] = zone
        
        print(f"Mission deployment zones created: {deployment_mission}")
        
        # 4. Set up mission objectives
        deployment_manager.setup_mission_objectives()
        print(f"Mission objectives placed: {len(self.objectives)} objectives")
        print(f"Primary Mission: {primary_mission}")

        # Apply primary-mission setup rules that modify objective markers (Chapter Approved 2025/26).
        self._apply_primary_mission_setup_rules()
    
    def execute_determine_attacker_defender_phase(self) -> None:
        """Phase 4: Determine Attacker and Defender - Roll off to determine roles."""
        print("DETERMINE ATTACKER AND DEFENDER: Rolling off...")
        
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_dice
        
        player1_roll = get_roll("1D6")
        player2_roll = get_roll("1D6")
        append_dice(self.players[0], f"First turn roll: {player1_roll}")
        append_dice(self.players[1], f"First turn roll: {player2_roll}")
        
        print(f"{self.players[0].name} rolled: {player1_roll}")
        print(f"{self.players[1].name} rolled: {player2_roll}")
        
        if player1_roll > player2_roll:
            self.attacker_index = 0
            self.defender_index = 1
            print(f"{self.players[0].name} is the Attacker")
            print(f"{self.players[1].name} is the Defender")
        elif player2_roll > player1_roll:
            self.attacker_index = 1
            self.defender_index = 0
            print(f"{self.players[1].name} is the Attacker")
            print(f"{self.players[0].name} is the Defender")
        else:
            # Tie - re-roll
            print("Tie! Re-rolling...")
            return self.execute_determine_attacker_defender_phase()
        
        # Set deployment turn to defender (defender deploys first)
        self.deployment_turn_index = self.defender_index
        # Reset deployment special-rule trackers for a fresh setup sequence
        self.deployment_skip_turns = {}

    def _apply_hover_declarations(self) -> None:
        """Declare Hover mode choices before Battle Formations steps."""
        players = list(self.players or [])
        if not players:
            return
        pending_unit_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "hover_mode":
                    continue
                unit_id = str(ctx.get("unit_id", "") or "")
                if unit_id:
                    pending_unit_ids.add(unit_id)

        from .decision_requests import build_hover_mode_requests

        for player in players:
            if player is None:
                raise RuntimeError("Hover declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Hover declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            requests = build_hover_mode_requests(self, units, queue_requests=False)
            for req in list(requests or []):
                unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
                if unit_id and unit_id in pending_unit_ids:
                    continue
                self.request_decision(req)

    def execute_declare_battle_formations_phase(self) -> None:
        """Phase 5: Declare Battle Formations - Attach leaders, embark in transports, allocate reserves."""
        print("DECLARE BATTLE FORMATIONS: Validating formations...")

        # Hover mode declarations must happen before any other formation steps.
        self._apply_hover_declarations()

        # Validate leader attachment limits per army
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Missing player during Declare Battle Formations.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {p.name} during Declare Battle Formations.")
            army.validate_leaders()
            try:
                army.validate_support_artillery()
            except AttributeError:
                pass

        # Nurgle's Gift (Aura): select a Plague during Declare Battle Formations.
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Missing player during Declare Battle Formations.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {p.name} during Declare Battle Formations.")
            mgr = getattr(army, "nurgles_gift", None)
            if mgr is None:
                continue
            mgr.on_declare_battle_formations_start(game=self)

        print("INFO: Battle formations declared")
    
    def execute_deploy_armies_phase(self, manual_phases: bool = False, decision_makers: dict = None) -> None:
        """Phase 6: Deploy Armies - Execute the deployment phase."""
        print("DEPLOY ARMIES: Starting deployment sequence...")
        
        # Check if we have local players that need UI-based deployment
        has_local_players = any(getattr(player, "has_control", lambda: False)() for player in self.players)
        
        if has_local_players and manual_phases:
            # For local players in manual mode, set up deployment state but don't auto-deploy
            # The UI will handle the actual deployment decisions
            print("INFO: Local deployment mode - use UI to deploy units")
            
            # Set up deployment zones if not already done
            if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
                # Always use mission polygon deployment zones (rectangular zones are not supported).
                mission_name = (getattr(self, "selected_mission_info", None) or {}).get("deployment")
                if not mission_name:
                    raise RuntimeError("Missing deployment name in selected_mission_info.")

                from .deployment import DeploymentManager
                deployment_manager = DeploymentManager(self, mission_name=mission_name)
                zones = deployment_manager.create_deployment_zones()
                defender_zone = next(z for z in zones if z.get("zone_type") == "defender")
                attacker_zone = next(z for z in zones if z.get("zone_type") == "attacker")

                defender_idx = self.defender_index
                attacker_idx = self.attacker_index
                if defender_idx is None or attacker_idx is None:
                    raise RuntimeError("Attacker/defender indices not set before deployment.")

                self.deployment_zones = {
                    self.players[defender_idx].id: defender_zone,
                    self.players[attacker_idx].id: attacker_zone,
                }
            
            # Initialize deployment tracking
            if not hasattr(self, 'deployment_turn_index'):
                if self.defender_index is None:
                    raise RuntimeError("Defender index not set before deployment.")
                self.deployment_turn_index = self.defender_index
            # Reset / initialize TITANIC skip-turn tracker (safe for checkpoint-loaded games)
            self.deployment_skip_turns = {}
            
            # Mark that we're in deployment phase
            self.waiting_for_deployment_input = False
            print("INFO: Deployment phase initialized - deploy units through UI")
        
        elif decision_makers:
            # Use the proper deployment manager with decision makers for controller-driven
            from .deployment import DeploymentManager
            deployment_manager = DeploymentManager(self)
            deployment_results = deployment_manager.execute_deployment_sequence(decision_makers)
            
            # Store deployment results for reference
            self.deployment_results = deployment_results
            print("INFO: Army deployment complete")
        else:
            raise RuntimeError("Deployment requires manual UI or explicit decision_makers.")

    def execute_redeploy_units_phase(self) -> None:
        """Phase: Redeploy Units - Alternate resolving redeploy rules, Attacker first.

        Rules:
        - Some rules allow redeploying certain units after both armies are deployed.
        - Players alternate resolving such rules, starting with the Attacker.
        - Redeploy allows selecting a new valid deployment location for eligible units.
        """
        print("REDEPLOY UNITS: Resolving redeploy abilities...")
        if self.attacker_index is None or self.defender_index is None:
            print("WARN: Attacker/Defender not set; skipping Redeploy Units phase")
            return
        state = getattr(self, "_redeploy_state", None)
        if isinstance(state, dict) and state.get("active"):
            self._continue_redeploy_phase()
            return

        from ..utility.entity_ids import get_entity_id

        players_in_order = [self.players[self.attacker_index], self.players[self.defender_index]]
        redeploy_queues: dict[str, list[dict]] = {}

        for p in players_in_order:
            army = p.get_army()
            if not army:
                continue
            tokens: list[dict] = []
            for u in list(getattr(army, "units", []) or []):
                has_redeploy, count, can_place_in_reserves = u.has_redeploy()
                if not has_redeploy or int(count or 0) <= 0:
                    continue
                try:
                    cache = getattr(u, "_ability_cache", {}) or {}
                except Exception:
                    cache = {}
                filters = list(cache.get("redeploy_filters") or [])
                ability_name = str(cache.get("redeploy_ability_name") or "")
                if not ability_name:
                    ability_name = str(getattr(getattr(u, "enhancement", None), "name", "") or "Redeploy")
                tokens.append(
                    {
                        "source_unit_id": get_entity_id(u),
                        "remaining": int(count or 0),
                        "can_place_in_reserves": bool(can_place_in_reserves),
                        "filters": list(filters),
                        "used_unit_ids": [],
                        "ability_name": ability_name,
                    }
                )
            if tokens:
                tokens.sort(key=lambda t: str(t.get("source_unit_id", "")))
                redeploy_queues[str(getattr(p, "id", "") or "")] = tokens

        if not any(redeploy_queues.values()):
            print("INFO: No units with Redeploy; skipping")
            return

        self._redeploy_state = {
            "active": True,
            "turn_index": 0,
            "player_order": [str(getattr(p, "id", "") or "") for p in players_in_order],
            "queues": redeploy_queues,
            "pending_move": False,
            "pending_move_unit_id": "",
        }
        self._queue_redeploy_selection()

    def _continue_redeploy_phase(self) -> None:
        state = getattr(self, "_redeploy_state", None)
        if not isinstance(state, dict) or not state.get("active"):
            return
        if state.get("pending_move"):
            return
        self._queue_redeploy_selection()

    def _queue_redeploy_selection(self) -> None:
        state = getattr(self, "_redeploy_state", None)
        if not isinstance(state, dict) or not state.get("active"):
            return
        if state.get("pending_move"):
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        queue = getattr(self, "decision_queue", None)
        last_decision_id = str(state.get("last_decision_id", "") or "")
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) == "aeldari_guileful_strategist":
                    if last_decision_id and str(getattr(req, "decision_id", "") or "") == last_decision_id:
                        continue
                    return
        order = list(state.get("player_order") or [])
        if not order:
            state["active"] = False
            return
        turn_idx = int(state.get("turn_index", 0) or 0)

        player_id = ""
        player_obj = None
        for _ in range(len(order)):
            pid = str(order[turn_idx % len(order)] or "")
            tokens = list(state.get("queues", {}).get(pid, []) or [])
            if tokens:
                player_id = pid
                player_obj = self.entity_registry.get(pid, kind="player") if self.entity_registry else None
                break
            turn_idx += 1

        if not player_id or player_obj is None:
            state["active"] = False
            print("INFO: Redeploy phase complete")
            return

        state["turn_index"] = turn_idx
        tokens = list(state.get("queues", {}).get(player_id, []) or [])
        if not tokens:
            state["active"] = False
            print("INFO: Redeploy phase complete")
            return
        token = tokens[0]

        army = player_obj.get_army()
        if army is None:
            state["active"] = False
            print("INFO: Redeploy phase complete")
            return

        from ..utility.entity_ids import get_entity_id

        used = set(str(v) for v in list(token.get("used_unit_ids") or []) if v)
        filters = [str(f or "").strip().upper() for f in list(token.get("filters") or []) if str(f or "").strip()]

        candidates = []
        seen = set()
        for unit in list(getattr(army, "units", []) or []):
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            try:
                rid = str(get_entity_id(root))
            except Exception:
                continue
            if rid in seen:
                continue
            seen.add(rid)
            if rid in used:
                continue
            try:
                if not bool(getattr(root, "deployed", False)):
                    continue
                if str(getattr(root, "reserve_status", "deployed") or "deployed") != "deployed":
                    continue
            except Exception:
                continue
            try:
                if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
                    continue
            except Exception:
                continue
            if filters:
                try:
                    if not all(root.has_any_keyword(f) for f in filters):
                        continue
                except Exception:
                    continue
            candidates.append(root)

        if not candidates:
            tokens.pop(0)
            state.get("queues", {})[player_id] = tokens
            state["turn_index"] = turn_idx + 1
            self._queue_redeploy_selection()
            return

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        for cand in sorted(candidates, key=_cand_sort_key):
            cid = get_entity_id(cand)
            label = str(getattr(cand, "name", "Unit") or "Unit")
            if bool(token.get("can_place_in_reserves")):
                options.append(
                    DecisionOption.create(
                        f"{label} - Redeploy",
                        payload={"target_unit_id": cid, "redeploy_action": "battlefield"},
                    )
                )
                options.append(
                    DecisionOption.create(
                        f"{label} - Strategic Reserves",
                        payload={"target_unit_id": cid, "redeploy_action": "strategic_reserves"},
                    )
                )
            else:
                options.append(
                    DecisionOption.create(
                        f"{label} - Redeploy",
                        payload={"target_unit_id": cid, "redeploy_action": "battlefield"},
                    )
                )

        ability_name = str(token.get("ability_name") or "Redeploy").strip()
        remaining = int(token.get("remaining", 0) or 0)
        ctx = {
            "ability": "aeldari_guileful_strategist",
            "ability_name": ability_name,
            "phase": "Redeploy Units",
            "remaining": remaining,
            "redeploy_player_id": player_id,
            "source_unit_id": token.get("source_unit_id"),
            "can_place_in_reserves": bool(token.get("can_place_in_reserves")),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a unit to redeploy ({remaining} remaining).",
            player_id=player_id,
            options=options,
            context=ctx,
        )
        self.request_decision(request)

    def _apply_redeploy_choice(self, request, result, *, skipped: bool = False) -> None:
        state = getattr(self, "_redeploy_state", None)
        if not isinstance(state, dict) or not state.get("active"):
            return
        ctx = dict(getattr(request, "context", {}) or {})
        player_id = str(ctx.get("redeploy_player_id") or getattr(request, "player_id", "") or "")
        if not player_id:
            return
        queues = state.get("queues", {}) or {}
        tokens = list(queues.get(player_id, []) or [])
        if not tokens:
            return
        token = tokens[0]
        if skipped:
            state["last_decision_id"] = str(getattr(request, "decision_id", "") or "")
            tokens.pop(0)
            queues[player_id] = tokens
            state["turn_index"] = int(state.get("turn_index", 0) or 0) + 1
            self._queue_redeploy_selection()
            return

        from ..utility.entity_ids import get_entity_id
        payload = dict(getattr(result, "payload", {}) or {})
        if not payload:
            try:
                opt = next((o for o in list(getattr(request, "options", []) or []) if o.option_id == result.option_id), None)
                if opt is not None:
                    payload = dict(getattr(opt, "payload", {}) or {})
            except Exception:
                payload = {}
        target_id = str(payload.get("target_unit_id", "") or "")
        action = str(payload.get("redeploy_action", "battlefield") or "battlefield").strip().lower()
        if not target_id:
            tokens.pop(0)
            queues[player_id] = tokens
            state["turn_index"] = int(state.get("turn_index", 0) or 0) + 1
            self._queue_redeploy_selection()
            return
        target = self.entity_registry.get(target_id, kind="unit") if self.entity_registry else None
        if target is None:
            tokens.pop(0)
            queues[player_id] = tokens
            state["turn_index"] = int(state.get("turn_index", 0) or 0) + 1
            self._queue_redeploy_selection()
            return
        try:
            root = target.get_attached_unit_root()
        except Exception:
            root = target
        root_id = get_entity_id(root)
        used = token.get("used_unit_ids")
        if isinstance(used, set):
            used.add(root_id)
        elif isinstance(used, list):
            if root_id not in used:
                used.append(root_id)
        token["remaining"] = max(int(token.get("remaining", 0) or 0) - 1, 0)
        if token["remaining"] <= 0:
            tokens.pop(0)
        queues[player_id] = tokens
        state["turn_index"] = int(state.get("turn_index", 0) or 0) + 1
        state["last_decision_id"] = str(getattr(request, "decision_id", "") or "")

        if action == "strategic_reserves":
            self._redeploy_unit_to_strategic_reserves(root)
            self._queue_redeploy_selection()
            return

        player = self.entity_registry.get(player_id, kind="player") if self.entity_registry else None
        ability_name = str(token.get("ability_name") or ctx.get("ability_name") or "Redeploy").strip()
        self._queue_redeploy_placement(player, root, ability_name=ability_name)

    def _queue_redeploy_placement(self, player, unit, *, ability_name: str) -> None:
        if unit is None or not bool(getattr(self, "is_authoritative", True)):
            return
        from ..engine.decision_kinds import DECISION_MOVE_UNIT
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_MOVE_UNIT:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if bool(ctx.get("redeploy_followup")) and str(ctx.get("unit_id", "")) == str(get_entity_id(unit)):
                    return

        unit_id = get_entity_id(unit)
        options = [
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit_id, "movement_type": "deploy", "action": "confirm"},
            )
        ]
        player_id = getattr(player, "id", None) if player is not None else None
        allowed_ids = [get_entity_id(m) for m in list(getattr(unit, "models", []) or [])]
        ctx = {
            "unit_id": unit_id,
            "movement_type": "deploy",
            "placement_kind": "deployment",
            "allowed_model_ids": allowed_ids,
            "allow_skip": False,
            "redeploy_followup": True,
            "redeploy_unit_id": unit_id,
            "ability_name": str(ability_name or "Redeploy"),
        }
        request = DecisionRequest.create(
            DECISION_MOVE_UNIT,
            f"{ability_name}: redeploy {getattr(unit, 'name', 'Unit')}",
            player_id=player_id,
            options=options,
            context=ctx,
        )
        self._redeploy_state["pending_move"] = True
        self._redeploy_state["pending_move_unit_id"] = str(unit_id)
        self.request_decision(request)

    def _on_redeploy_placement_resolved(self, unit_id: str) -> None:
        state = getattr(self, "_redeploy_state", None)
        if not isinstance(state, dict) or not state.get("active"):
            return
        if str(state.get("pending_move_unit_id") or "") != str(unit_id or ""):
            return
        state["pending_move"] = False
        state["pending_move_unit_id"] = ""
        self._queue_redeploy_selection()

    def _redeploy_unit_to_strategic_reserves(self, unit) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        game_map = getattr(self, "map", None)

        for member in members:
            try:
                member.set_reserve_status("strategic_reserves")
            except Exception:
                try:
                    member.reserve_status = "strategic_reserves"
                except Exception:
                    pass
            try:
                member.deployed = True
                member.reserve_turn_deployed = None
                member.arrived_from_reserves_this_turn = False
            except Exception:
                pass
            try:
                if game_map is not None and hasattr(game_map, "units") and member in game_map.units:
                    game_map.units.remove(member)
            except Exception:
                pass

        # Keep embarked passengers embarked; ensure they follow the transport into reserves.
        try:
            passengers = list(getattr(root, "transport_passengers", []) or [])
        except Exception:
            passengers = []
        for passenger in passengers:
            try:
                passenger.set_reserve_status("strategic_reserves")
            except Exception:
                try:
                    passenger.reserve_status = "strategic_reserves"
                except Exception:
                    pass
            try:
                passenger.deployed = True
                passenger.reserve_turn_deployed = None
                passenger.arrived_from_reserves_this_turn = False
            except Exception:
                pass
            try:
                if game_map is not None and hasattr(game_map, "units") and passenger in game_map.units:
                    game_map.units.remove(passenger)
            except Exception:
                pass

    def _find_valid_redeploy_position(self, player: 'Player', unit: 'Unit') -> tuple | None:
        """Return None unless a controller provides a redeploy position."""
        return None


    def execute_determine_first_turn_order_phase(self) -> None:
        """Phase 7: Determine First Turn Order - Attacker rolls to see who goes first."""
        print("DETERMINE FIRST TURN ORDER: Rolling for first turn (roll-off)...")

        from ..utility.dice import get_roll
        from ..utility.event_bus import append_dice

        p1 = self.players[0]
        p2 = self.players[1]

        while True:
            roll1 = get_roll("1D6")
            roll2 = get_roll("1D6")
            append_dice(p1, f"First turn roll-off: {roll1}")
            append_dice(p2, f"First turn roll-off: {roll2}")
            print(f"INFO: {p1.name} rolled: {roll1}")
            print(f"INFO: {p2.name} rolled: {roll2}")
            if roll1 == roll2:
                print("INFO: Tie on roll-off - re-rolling...")
                continue
            if roll1 > roll2:
                self.first_turn_player_index = 0
                print(f"INFO: {p1.name} wins the roll-off and takes the first turn")
            else:
                self.first_turn_player_index = 1
                print(f"INFO: {p2.name} wins the roll-off and takes the first turn")
            break

        # Clear deployment actions since deployment phase is now complete
        self.clear_deployment_actions()
    
    def execute_resolve_prebattle_rules_phase(self) -> None:
        """Phase 8: Resolve Pre-battle Rules - Resolve any pre-battle rules, abilities, or stratagems."""
        print("RESOLVE PREBATTLE RULES: Resolving pre-battle rules...")
        
        # Handle Scout moves for all players
        self._handle_scout_moves()

        # TODO - other pre-battle rules (e.g., Detachment stuff like WE dice rolls, etc.)
        
        print("INFO: Pre-battle rules resolved")
    
    def _handle_scout_moves(self) -> None:
        """Handle scout moves for all players during pre-battle rules phase."""
        print("INFO: Processing Scout moves...")
        
        # Get all units with Scout ability from both players
        scout_units = []
        for player in self.players:
            if player.get_army():
                for unit in player.get_army().units:
                    has_scout, scout_distance = unit.has_scout()
                    if has_scout and unit.deployed and unit.reserve_status == 'deployed':
                        scout_units.append((player, unit, scout_distance))
        
        if not scout_units:
            print("INFO: No units with Scout ability found")
            return
        
        print(f"INFO: Found {len(scout_units)} units with Scout ability")
        
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
        
        # Check if we have local players that need UI-based scout moves
        has_local_players = any(getattr(player, "has_control", lambda: False)() for player in self.players)
        
        if has_local_players:
            # For local players, let the UI handle scout moves
            # The PreBattlePhaseHandler will manage the scout move sequence
            print("INFO: Local scout moves will be handled by UI")
            print("INFO: Scout phase initialized - use UI to make scout moves")
        else:
            # For games without local control, auto-skip scout moves for now
            # In the future, this could integrate with controller decision making
            for player in players_in_order:
                if player in scout_units_by_player:
                    print(f"INFO: {player.name}'s Scout moves:")
                    for unit, scout_distance in scout_units_by_player[player]:
                        print(f"  - {unit.name} (Scout {scout_distance}\")")
                        print(f"    Skipping scout move (auto-skip for remote-only)")
                        unit.scout_move_made = True  # Mark as skipped
            
            print("INFO: Scout moves processed (auto-skipped for remote-only)")
    
    def _execute_current_setup_phase_impl(self, **kwargs) -> None:
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

    def execute_current_setup_phase(self, **kwargs) -> None:
        """Execute the current setup phase via command dispatch."""
        if self.in_command_context():
            self._execute_current_setup_phase_impl(**kwargs)
            return
        if kwargs.get("decision_makers") is not None:
            raise ValueError("decision_makers cannot be serialized in command dispatch.")
        payload = {
            "player1_army_file": kwargs.get("player1_army_file"),
            "player2_army_file": kwargs.get("player2_army_file"),
            "manual_phases": bool(kwargs.get("manual_phases", False)),
        }
        player_id = None
        try:
            player_id = self.get_current_player().id
        except Exception:
            player_id = None
        cmd = GameCommand.create(CMD_EXECUTE_SETUP_PHASE, player_id=player_id, payload=payload)
        self.apply_command(cmd)

    def _apply_selected_mission(self, combination: dict, layout: object) -> None:
        self.selected_mission_info = {
            "combination_id": combination.get("id"),
            "primary": combination.get("primary"),
            "deployment": combination.get("deployment"),
            "layout": layout,
        }
        from .mission_cards import create_primary_mission_card

        for player in list(self.players or []):
            player.set_primary_mission(create_primary_mission_card(combination.get("primary")))

    def set_selected_mission(self, combination: dict, layout: object) -> None:
        if self.in_command_context():
            self._apply_selected_mission(combination, layout)
            return
        player_id = None
        try:
            player_id = self.get_current_player().id
        except Exception:
            player_id = None
        cmd = GameCommand.create(
            CMD_SELECT_MISSION,
            player_id=player_id,
            payload={"combination": dict(combination or {}), "layout": layout},
        )
        self.apply_command(cmd)

    def set_waiting_for_deployment_input(self, value: bool) -> None:
        if self.in_command_context():
            self.waiting_for_deployment_input = bool(value)
            return
        player_id = None
        try:
            player_id = self.get_current_player().id
        except Exception:
            player_id = None
        cmd = GameCommand.create(
            CMD_SET_DEPLOYMENT_WAITING,
            player_id=player_id,
            payload={"value": bool(value)},
        )
        self.apply_command(cmd)
