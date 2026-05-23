from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
import html
import re
import logging
import copy
import math
import sys

from ..event.system import EventSystem
from ..event_log import DeterministicEventLog
from ...battlefield.map import Map, Objective
from ..mission_cards import PrimaryMissionCard, SecondaryMissionCard
from ...roster.player import Player
from ...units.unit import Unit
from ...units.model import Model
from ..phase import SetupPhase, BattleRoundPhases
from ..battlefield import Battlefield, BattlefieldSize
from ..turn_manager import next_phase as _next_phase
from ..commands import GameCommand
from ..command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_NEXT_PHASE,
    CMD_SELECT_MISSION,
    CMD_SET_DEPLOYMENT_WAITING,
)
from ..decisions import CandidateAction, DecisionOption, DecisionQueue, DecisionRequest, DecisionResult
from ..decision_kinds import (
    DECISION_CHOOSE_MISSION,
    DECISION_CHOOSE_PLEDGE,
    DECISION_CONFIRM_YES_NO,
    DECISION_DISEMBARK,
    DECISION_DECLARE_MELEE_WEAPONS,
    DECISION_DECLARE_SHOTS,
    DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
    DECISION_CHOOSE_QUARRY,
    DECISION_CHOOSE_CHIVALRIC_OATH,
    DECISION_CHOOSE_START_OF_BATTLE_KEYWORD,
    DECISION_DISCARD_SECONDARY,
    DECISION_MOVE_UNIT,
    DECISION_REACTIVE_MOVE,
    DECISION_ALLOCATE_DAMAGE,
    DECISION_SELECT_SETUP_REACTIVE_TARGET,
    DECISION_SELECT_TARGET_MODEL,
    DECISION_SELECT_OVERWATCH_SHOOTER,
    DECISION_SELECT_REACTIVE_RESERVE_EXIT,
    DECISION_SELECT_REVERBERATING_SUMMONS_UNIT,
    DECISION_SURGE_MOVE,
)
from ..random_source import RandomSource
from ..decision_controller import DecisionController, DecisionControllerHub
from ..decision_record import DecisionRecordStore
from ..decision_port import get_decision_provider
from ..ruleset import RulesetBundle
from ..tier1_plan import Tier1Plan, build_heuristic_tier1_plan
from ..tier2_orchestrator import Tier2TaskBundle, build_tier2_task_bundle
from ..time_manager import TimeManager
from ..movement_intent import MovementIntent
from ..movement_solver import generate_move_unit_candidates
from ..path_witness import PathWitnessStore
from ..dice_rolls import DiceRollManager
from ..attack_resolution import AttackResolutionManager
from ..ref_codec import encode_refs
from ...rules.lifecycle import AbilityLifecycle
from ...rules.registry import RuleRegistry
from ...rules.providers.default_rules import build_default_rule_providers
from ...rules.emperors_children import (
    INTERNAL_RIVALRIES_NAME,
    PLEDGES_TO_THE_DARK_PRINCE_NAME,
)
from ...utility.calcs import get_dist, clear_enemy_model_cache
from ...utility.charge_roll import ChargeRollResult, ChargeRollSpec
from ...utility.dice import DiceCollection, get_roll as _dice_get_roll
from ...utility.constants import TOTAL_ROUNDS, ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
from ...utility.entity_ids import get_entity_id, maybe_entity_id
from ...utility.entity_registry import EntityRegistry, rebuild_registry_from_game
from ...utility.game_context import game_context

logger = logging.getLogger(__name__)


def get_roll(spec, *args, **kwargs):
    """
    Resolve dice rolls through ``warhammer40k_ai.engine.game.get_roll`` when available.

    This preserves existing test hooks that monkeypatch the game module function.
    """
    game_mod = sys.modules.get("warhammer40k_ai.engine.game")
    if game_mod is not None:
        roll_fn = getattr(game_mod, "get_roll", None)
        if callable(roll_fn):
            return roll_fn(spec, *args, **kwargs)
    return _dice_get_roll(spec, *args, **kwargs)

if TYPE_CHECKING:
    from ...roster.army_muster import ArmyMusterRequest
