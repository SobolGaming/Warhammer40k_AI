"""Deterministic offline roster search over validator-backed edit actions."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import random
from typing import Any, Protocol, runtime_checkable

from ..ml.interfaces import MatchupEvaluator
from ..ml.policy_bundle import JSONPolicyBundleLoader, ResolvedPolicyBundle
from ..ml.registry import ArtifactManifestStore
from ..waha_helper import WahaHelper
from .army import ArmyValidationError
from .army_build import ArmyBlueprint
from .build_capability import compile_build_capability_profile
from .event_policy import EventPolicyDescriptor
from .matchup_context import compile_matchup_context
from .roster_edit_actions import RosterEditAction, apply_roster_edit_action
from .roster_repair import BlueprintLegalityResult, validate_blueprint_runtime_legality
from .roster_search_report import (
    RosterSearchCandidateReport,
    RosterSearchIterationReport,
    RosterSearchReport,
)
from .tournament_field import TournamentFieldDistribution


@runtime_checkable
class RosterEvaluator(Protocol):
    def evaluate(self, blueprint: ArmyBlueprint) -> Mapping[str, Any]:
        """Return a JSON-safe mapping that includes score and utility decomposition."""


@runtime_checkable
class RosterActionProvider(Protocol):
    def actions_for_blueprint(self, blueprint: ArmyBlueprint) -> Sequence[RosterEditAction]:
        """Return deterministic edit actions for the supplied blueprint."""


@dataclass(frozen=True)
class RosterSearchConfig:
    strategy: str = "beam"
    max_iterations: int = 1
    beam_width: int = 3
    top_k: int = 5
    population_size: int = 4
    mutations_per_parent: int = 4
    random_seed: int | None = None

    def __post_init__(self) -> None:
        normalized = str(self.strategy or "beam").strip().lower()
        if normalized not in {"beam", "local", "evolutionary"}:
            raise ValueError("strategy must be one of: beam, local, evolutionary.")
        object.__setattr__(self, "strategy", normalized)
        object.__setattr__(self, "max_iterations", max(1, int(self.max_iterations or 1)))
        object.__setattr__(self, "beam_width", max(1, int(self.beam_width or 1)))
        object.__setattr__(self, "top_k", max(1, int(self.top_k or 1)))
        object.__setattr__(self, "population_size", max(1, int(self.population_size or 1)))
        object.__setattr__(self, "mutations_per_parent", max(1, int(self.mutations_per_parent or 1)))
        object.__setattr__(
            self,
            "random_seed",
            None if self.random_seed in (None, "") else int(self.random_seed),
        )


@dataclass(frozen=True)
class StaticRosterActionProvider:
    actions: tuple[RosterEditAction, ...]

    def __init__(self, actions: Sequence[RosterEditAction]) -> None:
        object.__setattr__(
            self,
            "actions",
            tuple(sorted(list(actions or []), key=lambda action: getattr(action, "action_id", ""))),
        )

    def actions_for_blueprint(self, blueprint: ArmyBlueprint) -> Sequence[RosterEditAction]:
        del blueprint
        return self.actions


@dataclass(frozen=True)
class HeuristicRosterEvaluator:
    waha_helper: WahaHelper
    policy_bundle_source: str | Mapping[str, Any]
    event_policy: EventPolicyDescriptor | Mapping[str, Any]
    field_distribution: TournamentFieldDistribution | Mapping[str, Any]
    models_root: str | None = None

    def __post_init__(self) -> None:
        event_policy = (
            self.event_policy
            if isinstance(self.event_policy, EventPolicyDescriptor)
            else EventPolicyDescriptor.from_dict(dict(self.event_policy))
        )
        field_distribution = (
            self.field_distribution
            if isinstance(self.field_distribution, TournamentFieldDistribution)
            else TournamentFieldDistribution.from_dict(dict(self.field_distribution))
        )
        manifest_store = None
        if self.models_root is not None:
            manifest_store = ArtifactManifestStore(self.models_root)
        bundle = JSONPolicyBundleLoader(manifest_store=manifest_store).load_bundle(self.policy_bundle_source)
        evaluator = _resolve_matchup_evaluator(bundle)
        if evaluator is None:
            raise ValueError("Resolved policy bundle does not provide a matchup evaluator.")
        object.__setattr__(self, "event_policy", event_policy)
        object.__setattr__(self, "field_distribution", field_distribution)
        object.__setattr__(self, "_policy_bundle", bundle)
        object.__setattr__(self, "_matchup_evaluator", evaluator)

    def evaluate(self, blueprint: ArmyBlueprint) -> Mapping[str, Any]:
        capability_profile = compile_build_capability_profile(
            blueprint,
            rules_bundle_id=self.field_distribution.rules_bundle_id,
            waha_helper=self.waha_helper,
        )
        matchup_context = compile_matchup_context(
            army_blueprint=blueprint,
            event_policy=self.event_policy,
            field_distribution=self.field_distribution,
        )
        payload = dict(
            self._matchup_evaluator.evaluate_matchup(
                {
                    "build_capability_profile": capability_profile.to_dict(),
                    "matchup_context": matchup_context.to_dict(),
                }
            )
            or {}
        )
        score = float(payload.get("utility", 0.0) or 0.0)
        utility = dict(payload.get("breakdown", {}) or {})
        utility.setdefault("utility", score)
        return {
            "score": score,
            "utility_decomposition": utility,
            "evaluation_summary": {
                "policy_bundle_id": self._policy_bundle.policy_bundle_id,
                "build_capability_profile_id": capability_profile.build_capability_profile_id,
                "matchup_context_id": matchup_context.matchup_context_id,
                "status": str(payload.get("status", "") or ""),
            },
        }


@dataclass
class _CandidateNode:
    blueprint: ArmyBlueprint
    score: float
    utility_decomposition: dict[str, Any]
    evaluation_summary: dict[str, Any]
    validation_summary: dict[str, Any]
    edit_trace: tuple[dict[str, Any], ...]

    @property
    def candidate_id(self) -> str:
        return self.blueprint.army_blueprint_hash


def _resolve_matchup_evaluator(bundle: ResolvedPolicyBundle) -> MatchupEvaluator | None:
    candidates: list[object] = []
    if "matchup_evaluator" in bundle.components:
        candidates.append(bundle.resolve_component("matchup_evaluator"))
    candidates.extend(bundle.resolve_fallbacks("matchup_evaluator"))
    for candidate in candidates:
        if isinstance(candidate, MatchupEvaluator):
            return candidate
    return None


def _resolve_action_provider(
    action_provider: RosterActionProvider | Sequence[RosterEditAction] | Callable[[ArmyBlueprint], Sequence[RosterEditAction]],
) -> RosterActionProvider:
    if isinstance(action_provider, Sequence):
        return StaticRosterActionProvider(action_provider)
    if isinstance(action_provider, RosterActionProvider):
        return action_provider
    if callable(action_provider):
        class _CallableProvider:
            def actions_for_blueprint(self, blueprint: ArmyBlueprint) -> Sequence[RosterEditAction]:
                return tuple(action_provider(blueprint) or ())

        return _CallableProvider()
    raise TypeError("action_provider must be a RosterActionProvider, callable, or sequence of actions.")


def _rank_nodes(nodes: Sequence[_CandidateNode]) -> list[_CandidateNode]:
    return sorted(
        list(nodes or []),
        key=lambda node: (
            -float(node.score),
            len(node.edit_trace),
            node.candidate_id,
        ),
    )


def _normalize_evaluation(payload: Mapping[str, Any]) -> tuple[float, dict[str, Any], dict[str, Any]]:
    score = float(payload.get("score", payload.get("utility", 0.0)) or 0.0)
    utility = dict(payload.get("utility_decomposition", payload.get("breakdown", {})) or {})
    utility.setdefault("score", score)
    evaluation_summary = {
        key: value
        for key, value in dict(payload or {}).items()
        if key not in {"score", "utility", "utility_decomposition", "breakdown"}
    }
    return score, utility, evaluation_summary


def _evaluate_legal_candidate(
    blueprint: ArmyBlueprint,
    *,
    evaluator: RosterEvaluator | Callable[[ArmyBlueprint], Mapping[str, Any]],
    legality_result: BlueprintLegalityResult,
    edit_trace: tuple[dict[str, Any], ...],
) -> _CandidateNode:
    payload = evaluator.evaluate(blueprint) if isinstance(evaluator, RosterEvaluator) else evaluator(blueprint)
    score, utility, evaluation_summary = _normalize_evaluation(dict(payload or {}))
    return _CandidateNode(
        blueprint=blueprint,
        score=score,
        utility_decomposition=utility,
        evaluation_summary=evaluation_summary,
        validation_summary={
            "repairs": list(legality_result.repairs),
            "runtime_summary": dict(legality_result.runtime_summary or {}),
        },
        edit_trace=edit_trace,
    )


def _next_frontier(
    *,
    strategy: str,
    candidates: Sequence[_CandidateNode],
    config: RosterSearchConfig,
    rng: random.Random,
) -> list[_CandidateNode]:
    ranked = _rank_nodes(candidates)
    if strategy == "local":
        return ranked[:1]
    if strategy == "beam":
        return ranked[: config.beam_width]
    if len(ranked) <= config.population_size:
        return ranked
    window_size = min(len(ranked), max(config.population_size * 2, config.population_size))
    window = ranked[:window_size]
    survivors = [window[0]]
    remaining = window[1:]
    sample_count = min(len(remaining), config.population_size - 1)
    if sample_count > 0:
        sampled = [remaining[index] for index in sorted(rng.sample(range(len(remaining)), sample_count))]
        survivors.extend(sampled)
    return _rank_nodes(survivors)


def _candidate_report(node: _CandidateNode) -> RosterSearchCandidateReport:
    return RosterSearchCandidateReport(
        candidate_id=node.candidate_id,
        army_blueprint=node.blueprint,
        score=node.score,
        utility_decomposition=node.utility_decomposition,
        edit_trace=node.edit_trace,
        evaluation_summary=node.evaluation_summary,
        validation_summary=node.validation_summary,
    )


def search_rosters(
    seed_blueprint: ArmyBlueprint | Mapping[str, Any],
    *,
    waha_helper: WahaHelper,
    evaluator: RosterEvaluator | Callable[[ArmyBlueprint], Mapping[str, Any]],
    action_provider: RosterActionProvider | Sequence[RosterEditAction] | Callable[[ArmyBlueprint], Sequence[RosterEditAction]],
    config: RosterSearchConfig | Mapping[str, Any] | None = None,
    event_policy: EventPolicyDescriptor | Mapping[str, Any] | None = None,
) -> RosterSearchReport:
    search_config = (
        config
        if isinstance(config, RosterSearchConfig)
        else RosterSearchConfig(**dict(config or {}))
    )
    seed = ArmyBlueprint.from_dict(seed_blueprint)
    resolved_action_provider = _resolve_action_provider(action_provider)
    rng = random.Random(search_config.random_seed)

    seed_legality = validate_blueprint_runtime_legality(
        seed,
        waha_helper=waha_helper,
        event_policy=event_policy,
    )
    if not seed_legality.is_valid:
        issues = "; ".join(issue.message for issue in seed_legality.issues)
        raise ArmyValidationError(f"Seed blueprint is not legal after repair: {issues}")

    seed_node = _evaluate_legal_candidate(
        seed_legality.repaired_blueprint,
        evaluator=evaluator,
        legality_result=seed_legality,
        edit_trace=(),
    )
    frontier: list[_CandidateNode] = [seed_node]
    best_nodes: dict[str, _CandidateNode] = {seed_node.candidate_id: seed_node}
    visited_hashes: set[str] = {seed_node.candidate_id}
    iteration_reports: list[RosterSearchIterationReport] = []
    generated_candidate_count = 1
    legal_candidate_count = 1
    rejected_candidate_count = 0

    for iteration_index in range(search_config.max_iterations):
        if search_config.strategy == "local":
            parents = frontier[:1]
        else:
            parents = list(frontier or [])
        candidate_nodes: list[_CandidateNode] = []
        iteration_generated = 0
        iteration_rejected = 0

        for parent in parents:
            actions = sorted(
                list(resolved_action_provider.actions_for_blueprint(parent.blueprint) or []),
                key=lambda action: getattr(action, "action_id", ""),
            )
            if search_config.strategy == "evolutionary" and actions:
                actions = list(actions)
                rng.shuffle(actions)
                actions = actions[: search_config.mutations_per_parent]

            for action in actions:
                iteration_generated += 1
                candidate_blueprint = apply_roster_edit_action(parent.blueprint, action)
                legality = validate_blueprint_runtime_legality(
                    candidate_blueprint,
                    waha_helper=waha_helper,
                    event_policy=event_policy,
                )
                candidate_hash = legality.repaired_blueprint.army_blueprint_hash
                if candidate_hash in visited_hashes:
                    continue
                visited_hashes.add(candidate_hash)
                if not legality.is_valid:
                    iteration_rejected += 1
                    continue
                edit_trace = tuple(list(parent.edit_trace) + [action.to_dict()])
                node = _evaluate_legal_candidate(
                    legality.repaired_blueprint,
                    evaluator=evaluator,
                    legality_result=legality,
                    edit_trace=edit_trace,
                )
                candidate_nodes.append(node)
                best_nodes[node.candidate_id] = node

        generated_candidate_count += iteration_generated
        rejected_candidate_count += iteration_rejected
        legal_candidate_count = len(best_nodes)
        if not candidate_nodes:
            iteration_reports.append(
                RosterSearchIterationReport(
                    iteration_index=iteration_index,
                    frontier_size=len(frontier),
                    candidate_count=0,
                    rejected_candidate_count=iteration_rejected,
                    best_candidate_id=frontier[0].candidate_id if frontier else seed_node.candidate_id,
                    best_score=frontier[0].score if frontier else seed_node.score,
                )
            )
            break

        frontier = _next_frontier(
            strategy=search_config.strategy,
            candidates=candidate_nodes,
            config=search_config,
            rng=rng,
        )
        best_frontier = _rank_nodes(frontier)[0] if frontier else _rank_nodes(candidate_nodes)[0]
        iteration_reports.append(
            RosterSearchIterationReport(
                iteration_index=iteration_index,
                frontier_size=len(frontier),
                candidate_count=len(candidate_nodes),
                rejected_candidate_count=iteration_rejected,
                best_candidate_id=best_frontier.candidate_id,
                best_score=best_frontier.score,
            )
        )

    top_candidates = tuple(
        _candidate_report(node)
        for node in _rank_nodes(best_nodes.values())[: search_config.top_k]
    )
    return RosterSearchReport(
        strategy=search_config.strategy,
        random_seed=search_config.random_seed,
        seed_blueprint=seed_legality.repaired_blueprint,
        top_candidates=top_candidates,
        iterations=tuple(iteration_reports),
        generated_candidate_count=generated_candidate_count,
        legal_candidate_count=legal_candidate_count,
        rejected_candidate_count=rejected_candidate_count,
        metadata={
            "validation_contract": {
                "runtime_army_validate": True,
                "warlord_validation": True,
                "enhancement_validation": True,
                "datasheet_limit_validation": True,
                "wargear_option_validation": True,
                "attachment_validation": True,
            }
        },
    )


__all__ = [
    "HeuristicRosterEvaluator",
    "RosterActionProvider",
    "RosterEvaluator",
    "RosterSearchConfig",
    "StaticRosterActionProvider",
    "search_rosters",
]
