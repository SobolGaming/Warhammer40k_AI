from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from . import decision_kinds as kinds
from .ai_component_rankers import (
    action_id_is_legal,
    action_order_with_preselected,
    first_legal_action_id,
    legal_candidates,
)
from .decisions import CandidateAction, DecisionRequest


COMPONENT_STRATEGIC_PLANNER = "strategic_planner"
COMPONENT_TACTICAL_ORCHESTRATOR = "tactical_orchestrator"
COMPONENT_DEPLOYMENT_RANKER = "deployment_ranker"
COMPONENT_MOVEMENT_RANKER = "movement_ranker"
COMPONENT_SHOOTING_RANKER = "shooting_ranker"
COMPONENT_CHARGE_RANKER = "charge_ranker"
COMPONENT_FIGHT_RANKER = "fight_ranker"
COMPONENT_TOOL_RANKER = "tool_ranker"
COMPONENT_REACTION_RANKER = "reaction_ranker"
COMPONENT_DICE_POLICY = "dice_policy"
COMPONENT_ALLOCATION_RANKER = "allocation_ranker"
COMPONENT_NO_AI = "n/a"

AI_POLICY_COMPONENTS: tuple[str, ...] = (
    COMPONENT_STRATEGIC_PLANNER,
    COMPONENT_TACTICAL_ORCHESTRATOR,
    COMPONENT_DEPLOYMENT_RANKER,
    COMPONENT_MOVEMENT_RANKER,
    COMPONENT_SHOOTING_RANKER,
    COMPONENT_CHARGE_RANKER,
    COMPONENT_FIGHT_RANKER,
    COMPONENT_TOOL_RANKER,
    COMPONENT_REACTION_RANKER,
    COMPONENT_DICE_POLICY,
    COMPONENT_ALLOCATION_RANKER,
)

_DEPLOYMENT_DECISIONS = {
    kinds.DECISION_CHOOSE_DEPLOYMENT_ZONE,
    kinds.DECISION_DECLARE_RESERVES,
    kinds.DECISION_SELECT_NEXT_DEPLOY_UNIT,
    kinds.DECISION_SCOUT_MOVE,
}

_TACTICAL_DECISIONS = {
    kinds.DECISION_ATTACH_LEADER,
    kinds.DECISION_ATTACH_SUPPORT_ARTILLERY,
    kinds.DECISION_ASSIGN_TRANSPORT,
    kinds.DECISION_SHADOW_ASSIGNMENT,
    kinds.DECISION_PICK_OBJECTIVE,
    kinds.DECISION_PICK_TERRAIN_FEATURE,
    kinds.DECISION_SELECT_REVERBERATING_SUMMONS_UNIT,
    kinds.DECISION_SELECT_VESSEL_OF_WRATH_MODELS,
    kinds.DECISION_SELECT_REALM_OF_CHAOS_UNITS,
    kinds.DECISION_CHOOSE_IMPOSSIBLE_ECLIPSE_ZONE,
    kinds.DECISION_CHOOSE_START_OF_BATTLE_KEYWORD,
    kinds.DECISION_CHOOSE_MURDEROUS_AGENDA,
    kinds.DECISION_CHOOSE_PATH_OF_WARRIOR,
    kinds.DECISION_CHOOSE_CRUEL_AMUSEMENT,
    kinds.DECISION_CHOOSE_MASTER_OF_MAGICKS,
    kinds.DECISION_CHOOSE_HARBINGER_OF_DEATH,
    kinds.DECISION_CHOOSE_DANCE_OF_DEATH,
    kinds.DECISION_CHOOSE_BLADEGUARD_STANCE,
    kinds.DECISION_CHOOSE_PLEDGE,
    kinds.DECISION_CHOOSE_QUARRY,
    kinds.DECISION_CHOOSE_HYSTERICAL_FRENZY_PSYKER,
    kinds.DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET,
    kinds.DECISION_ISSUE_ORDER,
    kinds.DECISION_CHOOSE_MALEFIC_SURGE_UNIT,
}

_MOVEMENT_DECISIONS = {
    kinds.DECISION_SELECT_MOVEMENT_ACTION,
    kinds.DECISION_SELECT_FLOOR,
    kinds.DECISION_RESOLVE_COHERENCY,
    kinds.DECISION_EMBARK,
    kinds.DECISION_DISEMBARK,
    kinds.DECISION_PICK_POINT,
    kinds.DECISION_CHOOSE_BATTLE_FOCUS_MANEUVER,
    kinds.DECISION_CHOOSE_MOVE_MODIFIER_IGNORES,
    kinds.DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES,
}

_SHOOTING_DECISIONS = {
    kinds.DECISION_SELECT_WEAPON,
    kinds.DECISION_DECLARE_SHOTS,
    kinds.DECISION_DECLARE_FIRING_DECK,
    kinds.DECISION_DEATHSTRIKE_ACTION,
    kinds.DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    kinds.DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET,
    kinds.DECISION_CHOOSE_POST_SHOOT_MORTAL_WOUNDS_TARGET,
    kinds.DECISION_CHOOSE_POST_SHOOT_WRACKED_AGONIES_TARGET,
    kinds.DECISION_CHOOSE_POST_SHOOT_AFLAME_TARGET,
    kinds.DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
    kinds.DECISION_CHOOSE_POST_SHOOT_LEADERSHIP_DEBUFF_TARGET,
    kinds.DECISION_CHOOSE_DAEMONIC_POISONS_TARGET,
}

_CHARGE_DECISIONS = {
    kinds.DECISION_DECLARE_CHARGE,
    kinds.DECISION_CHOOSE_CHARGE_MODIFIER_IGNORES,
}

_FIGHT_DECISIONS = {
    kinds.DECISION_SELECT_FIGHT_TARGETS,
    kinds.DECISION_DECLARE_MELEE_WEAPONS,
    kinds.DECISION_ALLOCATE_MELEE_TARGETS,
    kinds.DECISION_CHOOSE_FRENZY_TARGET,
    kinds.DECISION_USE_GILDED_CHAMPION,
    kinds.DECISION_CHOOSE_LIMB_FROM_LIMB,
    kinds.DECISION_CHOOSE_RED_WRATH,
    kinds.DECISION_CHOOSE_GIFT_OF_CHAOS_TARGET,
    kinds.DECISION_CHOOSE_POST_FIGHT_SUPPRESSION_TARGET,
    kinds.DECISION_SELECT_RISE_TO_CHALLENGE,
}

_TOOL_DECISIONS = {
    kinds.DECISION_SELECT_TOOL_ACTION,
    kinds.DECISION_SELECT_STRATAGEM_MODE,
    kinds.DECISION_CHOOSE_DARK_PACT,
    kinds.DECISION_CHOOSE_TECHNOSORCEROUS_AUGMENTATION,
    kinds.DECISION_CHOOSE_MOMENT_SHACKLE,
    kinds.DECISION_USE_LEADING_UNMODIFIED_SIX,
    kinds.DECISION_USE_MODEL_UNMODIFIED_SIX,
    kinds.DECISION_CHOOSE_HIT_MODIFIER_IGNORES,
    kinds.DECISION_CHOOSE_SKILL_MODIFIER_IGNORES,
}

_REACTION_DECISIONS = {
    kinds.DECISION_REACTIVE_MOVE,
    kinds.DECISION_SURGE_MOVE,
    kinds.DECISION_SELECT_HEROIC_INTERVENTION_MODE,
    kinds.DECISION_SELECT_REACTIVE_RESERVE_EXIT,
    kinds.DECISION_SELECT_OVERWATCH_SHOOTER,
    kinds.DECISION_SELECT_SETUP_REACTIVE_TARGET,
    kinds.DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
    kinds.DECISION_SELECT_UNLEASH_HELL_VEHICLE,
    kinds.DECISION_USE_CAREEN,
}

_DICE_DECISIONS = {
    kinds.DECISION_REQUEST_DICE_ROLL,
    kinds.DECISION_SELECT_DICE_REROLL,
    kinds.DECISION_REROLL_ROLL,
    kinds.DECISION_USE_MIRACLE_DIE,
}

_ALLOCATION_DECISIONS = {
    kinds.DECISION_ALLOCATE_TARGETS,
    kinds.DECISION_SPLIT_ATTACKS,
    kinds.DECISION_SELECT_TARGET_MODEL,
    kinds.DECISION_SELECT_PRECISION_TARGET,
    kinds.DECISION_ALLOCATE_DAMAGE,
    kinds.DECISION_SELECT_EXPLODING_HORRORS_TARGET,
    kinds.DECISION_SELECT_EXPLODING_HORRORS_MODELS,
}

_STRATEGIC_DECISIONS = {
    kinds.DECISION_CHOOSE_MISSION,
    kinds.DECISION_CHOOSE_BLESSINGS,
    kinds.DECISION_CHOOSE_BLOOD_TITHE,
    kinds.DECISION_CHOOSE_IDOL_OF_KHORNE,
    kinds.DECISION_CHOOSE_VESSEL_OF_WRATH_BLESSING,
    kinds.DECISION_CHOOSE_RITUALS,
    kinds.DECISION_CHOOSE_CHIVALRIC_OATH,
    kinds.DECISION_CHOOSE_DAEMONIC_ALLEGIANCE,
    kinds.DECISION_CHOOSE_DOCTRINA,
    kinds.DECISION_CHOOSE_COMBAT_DOCTRINE,
    kinds.DECISION_CHOOSE_MISSION_TACTIC,
    kinds.DECISION_CHOOSE_ANGELIC_LEGACY,
    kinds.DECISION_CHOOSE_GRAND_COVEN,
    kinds.DECISION_CHOOSE_COMBAT_DRUGS,
    kinds.DECISION_CHOOSE_HYPER_ADAPTATION,
    kinds.DECISION_CHOOSE_HARBINGER,
    kinds.DECISION_CHOOSE_MARTIAL_KATAH,
    kinds.DECISION_CHOOSE_ADAPTIVE_INSTINCTS,
    kinds.DECISION_CHOOSE_PLAGUE,
    kinds.DECISION_DISCARD_SECONDARY,
    kinds.DECISION_CHOOSE_SHADOW_FORM,
    kinds.DECISION_CHOOSE_VOW,
    kinds.DECISION_CHOOSE_WRATHFUL_PRESENCE,
    kinds.DECISION_CHOOSE_DAEMON_PRIMARCH_SLAANESH,
    kinds.DECISION_CHOOSE_WARMASTER_ABILITY,
    kinds.DECISION_CHOOSE_ASPECT,
    kinds.DECISION_CHOOSE_POWER_FROM_PAIN_OPTION,
    kinds.DECISION_CHOOSE_MALEFIC_SURGE_ABILITY,
}

_NO_AI_DECISIONS = {
    kinds.DECISION_CONFIRM_MODAL,
    kinds.DECISION_CHOOSE_PLAYER_COLOR,
    kinds.DECISION_CONFIRM_EXAMPLE,
}


@dataclass(frozen=True)
class AIOrchestrationResult:
    component_name: str
    action_id: str
    source: str


def _context(request_or_context: DecisionRequest | Mapping[str, Any] | None) -> dict[str, Any]:
    if isinstance(request_or_context, DecisionRequest):
        return dict(getattr(request_or_context, "context", {}) or {})
    return dict(request_or_context or {})


def _phase_key(context: Mapping[str, Any]) -> str:
    phase_values = [
        context.get("phase_step"),
        context.get("phase"),
        context.get("phase_name"),
        context.get("movement_type"),
        context.get("placement_kind"),
    ]
    return " ".join(str(value or "").upper() for value in phase_values)


def policy_component_for_decision(decision_type: str, context: Mapping[str, Any] | None = None) -> str:
    dtype = str(decision_type or "").strip()
    ctx = dict(context or {})
    phase_key = _phase_key(ctx)
    if dtype in _NO_AI_DECISIONS:
        return COMPONENT_NO_AI
    if dtype == kinds.DECISION_MOVE_UNIT:
        placement_kind = str(ctx.get("placement_kind", "") or "").strip().lower()
        if placement_kind == "deployment":
            return COMPONENT_DEPLOYMENT_RANKER
        if placement_kind == "reserves_arrival":
            return COMPONENT_MOVEMENT_RANKER
        if "CHARGE" in phase_key:
            return COMPONENT_CHARGE_RANKER
        if "FIGHT" in phase_key or "PILE" in phase_key or "CONSOLIDATE" in phase_key:
            return COMPONENT_FIGHT_RANKER
        return COMPONENT_MOVEMENT_RANKER
    if dtype == kinds.DECISION_SELECT_UNIT:
        if "FIGHT" in phase_key:
            return COMPONENT_FIGHT_RANKER
        return COMPONENT_TACTICAL_ORCHESTRATOR
    if dtype == kinds.DECISION_CONFIRM_YES_NO:
        ability = str(ctx.get("ability", ctx.get("ability_name", "")) or "").strip().lower()
        if "overwatch" in ability or "react" in ability or "opponent" in phase_key:
            return COMPONENT_REACTION_RANKER
        if bool(ctx.get("optional", False)):
            return COMPONENT_TOOL_RANKER
        return COMPONENT_TOOL_RANKER
    if dtype in _DEPLOYMENT_DECISIONS:
        return COMPONENT_DEPLOYMENT_RANKER
    if dtype in _TACTICAL_DECISIONS:
        return COMPONENT_TACTICAL_ORCHESTRATOR
    if dtype in _MOVEMENT_DECISIONS:
        return COMPONENT_MOVEMENT_RANKER
    if dtype in _SHOOTING_DECISIONS:
        return COMPONENT_SHOOTING_RANKER
    if dtype in _CHARGE_DECISIONS:
        return COMPONENT_CHARGE_RANKER
    if dtype in _FIGHT_DECISIONS:
        return COMPONENT_FIGHT_RANKER
    if dtype in _TOOL_DECISIONS:
        return COMPONENT_TOOL_RANKER
    if dtype in _REACTION_DECISIONS:
        return COMPONENT_REACTION_RANKER
    if dtype in _DICE_DECISIONS:
        return COMPONENT_DICE_POLICY
    if dtype in _ALLOCATION_DECISIONS:
        return COMPONENT_ALLOCATION_RANKER
    if dtype in _STRATEGIC_DECISIONS:
        return COMPONENT_STRATEGIC_PLANNER
    return COMPONENT_TACTICAL_ORCHESTRATOR


def policy_component_for_request(request: DecisionRequest) -> str:
    return policy_component_for_decision(
        str(getattr(request, "decision_type", "") or ""),
        _context(request),
    )


def all_known_decision_types() -> tuple[str, ...]:
    values = {
        str(value)
        for name, value in vars(kinds).items()
        if name.startswith("DECISION_") and isinstance(value, str)
    }
    return tuple(sorted(values))


def unmapped_decision_types() -> tuple[str, ...]:
    return tuple(
        value
        for value in all_known_decision_types()
        if policy_component_for_decision(value) not in (*AI_POLICY_COMPONENTS, COMPONENT_NO_AI)
    )


class AIPolicyOrchestrator:
    """Orchestrate authoritative decision requests across policy components."""

    def __init__(
        self,
        *,
        components: Mapping[str, object] | None = None,
        fallbacks: Mapping[str, Iterable[object]] | None = None,
    ) -> None:
        self._components = {
            str(name): implementation
            for name, implementation in sorted(dict(components or {}).items())
            if str(name) in AI_POLICY_COMPONENTS
        }
        self._fallbacks = {
            str(name): tuple(entries)
            for name, entries in sorted(dict(fallbacks or {}).items())
            if str(name) in AI_POLICY_COMPONENTS
        }

    @classmethod
    def from_policy_bundle(cls, bundle: object) -> "AIPolicyOrchestrator":
        components: dict[str, object] = {}
        for name, resolved in sorted(dict(getattr(bundle, "components", {}) or {}).items()):
            if str(name) not in AI_POLICY_COMPONENTS:
                continue
            components[str(name)] = getattr(resolved, "implementation", resolved)

        fallbacks: dict[str, tuple[object, ...]] = {}
        for name, entries in sorted(dict(getattr(bundle, "fallbacks", {}) or {}).items()):
            if str(name) not in AI_POLICY_COMPONENTS:
                continue
            fallbacks[str(name)] = tuple(getattr(entry, "implementation", entry) for entry in list(entries or []))
        return cls(components=components, fallbacks=fallbacks)

    def route(self, request: DecisionRequest) -> str:
        return policy_component_for_request(request)

    def choose_action(self, request: DecisionRequest) -> AIOrchestrationResult:
        component_name = self.route(request)
        if component_name == COMPONENT_NO_AI:
            return AIOrchestrationResult(component_name=component_name, action_id="", source="no_ai")
        for source, ranker in self._component_chain(component_name):
            choose = getattr(ranker, "choose_action_id", None)
            if not callable(choose):
                continue
            action_id = str(choose(request) or "")
            if action_id_is_legal(request, action_id):
                return AIOrchestrationResult(component_name=component_name, action_id=action_id, source=source)

        fallback = first_legal_action_id(
            request,
            prefer_decline=self._prefer_decline_fallback(component_name, request),
        )
        return AIOrchestrationResult(component_name=component_name, action_id=fallback, source="first_legal")

    def rank_legal_candidates(
        self,
        request: DecisionRequest,
        *,
        fallback_order: Iterable[CandidateAction] | None = None,
    ) -> list[CandidateAction]:
        route = self.choose_action(request)
        if route.action_id:
            return action_order_with_preselected(
                request,
                selected_action_id=route.action_id,
                fallback_order=fallback_order,
            )
        fallback = list(fallback_order or legal_candidates(request))
        return fallback

    def component_implementations(self) -> dict[str, object]:
        return dict(self._components)

    def collect_component_traces(self) -> list[dict[str, Any]]:
        traces: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        implementations: list[object] = list(self._components.values())
        for fallback_entries in self._fallbacks.values():
            implementations.extend(list(fallback_entries or ()))
        for implementation in implementations:
            identity = id(implementation)
            if identity in seen_ids:
                continue
            seen_ids.add(identity)
            get_traces = getattr(implementation, "traces", None)
            if not callable(get_traces):
                continue
            for trace in list(get_traces() or []):
                to_dict = getattr(trace, "to_dict", None)
                if callable(to_dict):
                    traces.append(dict(to_dict()))
                elif isinstance(trace, dict):
                    traces.append(dict(trace))
        return traces

    def _component_chain(self, component_name: str) -> tuple[tuple[str, object], ...]:
        chain: list[tuple[str, object]] = []
        primary = self._components.get(component_name)
        if primary is not None:
            chain.append((component_name, primary))
        for index, fallback in enumerate(self._fallbacks.get(component_name, ())):
            chain.append((f"{component_name}.fallback[{index}]", fallback))
        return tuple(chain)

    @staticmethod
    def _prefer_decline_fallback(component_name: str, request: DecisionRequest) -> bool:
        if component_name == COMPONENT_REACTION_RANKER:
            return True
        ctx = dict(getattr(request, "context", {}) or {})
        return bool(ctx.get("optional", False) or ctx.get("allow_skip", False))
