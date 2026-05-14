from __future__ import annotations

import json
from pathlib import Path

from warhammer40k_ai.engine import decision_kinds as kinds
from warhammer40k_ai.engine.ai_controller_router import (
    AI_POLICY_COMPONENTS,
    COMPONENT_CHARGE_RANKER,
    COMPONENT_DEPLOYMENT_RANKER,
    COMPONENT_FIGHT_RANKER,
    COMPONENT_MOVEMENT_RANKER,
    COMPONENT_NO_AI,
    COMPONENT_REACTION_RANKER,
    COMPONENT_SHOOTING_RANKER,
    COMPONENT_TACTICAL_ORCHESTRATOR,
    COMPONENT_TOOL_RANKER,
    AIControllerRouter,
    decision_component_for,
    unmapped_decision_types,
)
from warhammer40k_ai.engine.ai_domain_agents import default_ai_domain_rankers
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.ml import ArtifactManifestStore, JSONPolicyBundleLoader


def _request(
    decision_type: str,
    *,
    context: dict | None = None,
    candidates: list[CandidateAction] | None = None,
    mask: list[bool] | None = None,
) -> DecisionRequest:
    options = [
        DecisionOption.create("A", payload={"action_id": "a", "action": "confirm"}),
        DecisionOption.create("B", payload={"action_id": "b", "action": "confirm"}),
        DecisionOption.create("C", payload={"action_id": "c", "action": "skip"}),
    ]
    if candidates is None:
        candidates = [
            CandidateAction("a", params={"action": "confirm"}, metadata={}),
            CandidateAction("b", params={"action": "confirm"}, metadata={}),
            CandidateAction("c", params={"action": "skip"}, metadata={"candidate_kind": "noop"}),
        ]
    return DecisionRequest.create(
        decision_type,
        "test request",
        player_id="p1",
        options=options,
        candidates=candidates,
        mask=mask or [True] * len(candidates),
        context=context or {},
    )


def _decision_kind_values() -> set[str]:
    return {
        str(value)
        for name, value in vars(kinds).items()
        if name.startswith("DECISION_") and isinstance(value, str)
    }


def test_router_maps_every_decision_kind_to_a_component_or_no_ai() -> None:
    assert unmapped_decision_types() == ()
    allowed = set(AI_POLICY_COMPONENTS) | {COMPONENT_NO_AI}
    for decision_type in sorted(_decision_kind_values()):
        assert decision_component_for(decision_type) in allowed


def test_router_uses_context_for_shared_decision_surfaces() -> None:
    assert (
        decision_component_for(kinds.DECISION_MOVE_UNIT, {"placement_kind": "deployment"})
        == COMPONENT_DEPLOYMENT_RANKER
    )
    assert decision_component_for(kinds.DECISION_MOVE_UNIT, {"phase_step": "CHARGE_MOVE"}) == COMPONENT_CHARGE_RANKER
    assert decision_component_for(kinds.DECISION_MOVE_UNIT, {"phase_step": "FIGHT_FIRST"}) == COMPONENT_FIGHT_RANKER
    assert decision_component_for(kinds.DECISION_MOVE_UNIT, {"movement_type": "normal"}) == COMPONENT_MOVEMENT_RANKER
    assert decision_component_for(kinds.DECISION_SELECT_UNIT, {"phase_step": "FIGHT_FIRST"}) == COMPONENT_FIGHT_RANKER
    assert decision_component_for(kinds.DECISION_SELECT_UNIT, {"phase_step": "MOVE_UNITS"}) == COMPONENT_TACTICAL_ORCHESTRATOR
    assert (
        decision_component_for(kinds.DECISION_CONFIRM_YES_NO, {"ability": "fire_overwatch_reaction"})
        == COMPONENT_REACTION_RANKER
    )
    assert decision_component_for(kinds.DECISION_CONFIRM_YES_NO, {"optional": True}) == COMPONENT_TOOL_RANKER
    assert decision_component_for(kinds.DECISION_DECLARE_SHOTS) == COMPONENT_SHOOTING_RANKER


def test_domain_ranker_ignores_masked_candidates_and_ties_by_action_id() -> None:
    ranker = default_ai_domain_rankers()[COMPONENT_SHOOTING_RANKER]
    request = _request(
        kinds.DECISION_DECLARE_SHOTS,
        candidates=[
            CandidateAction("a", params={}, metadata={"projected_trade_ev": 100.0}),
            CandidateAction("b", params={}, metadata={"projected_trade_ev": 4.0}),
            CandidateAction("c", params={}, metadata={"projected_trade_ev": 4.0}),
        ],
        mask=[False, True, True],
    )

    assert ranker.choose_action_id(request) == "b"


class _StaticRanker:
    def __init__(self, action_id: str) -> None:
        self._action_id = action_id

    def choose_action_id(self, request: DecisionRequest) -> str:
        del request
        return self._action_id


def test_router_uses_fallback_component_when_primary_returns_illegal_action() -> None:
    request = _request(kinds.DECISION_DECLARE_SHOTS, mask=[False, True, True])
    router = AIControllerRouter(
        components={COMPONENT_SHOOTING_RANKER: _StaticRanker("a")},
        fallbacks={COMPONENT_SHOOTING_RANKER: [_StaticRanker("b")]},
    )

    route = router.choose_action(request)

    assert route.component_name == COMPONENT_SHOOTING_RANKER
    assert route.action_id == "b"
    assert route.source == f"{COMPONENT_SHOOTING_RANKER}.fallback[0]"


def test_router_first_legal_reaction_fallback_prefers_decline() -> None:
    request = _request(kinds.DECISION_SELECT_OVERWATCH_SHOOTER)
    router = AIControllerRouter()

    route = router.choose_action(request)

    assert route.component_name == COMPONENT_REACTION_RANKER
    assert route.action_id == "c"
    assert route.source == "first_legal"


def test_router_preserves_movement_path_witness_candidate_metadata() -> None:
    request = _request(
        kinds.DECISION_MOVE_UNIT,
        candidates=[
            CandidateAction("a", params={}, metadata={"projected_score_delta_next_window": 0.0}),
            CandidateAction(
                "b",
                params={},
                metadata={
                    "projected_score_delta_next_window": 2.0,
                    "path_witness_ref": "pathwitness://unit/u1/move/b",
                },
            ),
        ],
        mask=[True, True],
        context={"movement_type": "normal"},
    )
    router = AIControllerRouter(components={COMPONENT_MOVEMENT_RANKER: default_ai_domain_rankers()[COMPONENT_MOVEMENT_RANKER]})

    ranked = router.rank_legal_candidates(request)

    assert ranked[0].action_id == "b"
    assert ranked[0].metadata["path_witness_ref"] == "pathwitness://unit/u1/move/b"


def test_policy_bundle_resolves_policy_orchestration_component_names(tmp_path: Path) -> None:
    bundle_id = "policy_bundle:policy_orchestration_heuristic_v1"
    manifest_store = ArtifactManifestStore(tmp_path / "models")
    bundle_path = manifest_store.bundle_manifest_path(bundle_id)
    payload = {
        "policy_bundle_schema_id": "policy_bundle_schema:v1",
        "policy_bundle_id": bundle_id,
        "controller_type": "headless_self_play",
        "rules_bundle_scope": {"match_mode": "exact", "ids": ["rules_bundle:preview_11e_q2"]},
        "descriptor_bundle_scope": {"match_mode": "exact", "ids": ["descriptor_bundle:preview_11e_q2"]},
        "event_policy_scope": {"match_mode": "exact", "ids": ["event_policy:gt_fixed_roster_v1"]},
        "components": {
            component: {
                "resolver_kind": "heuristic",
                "resolver_ref": f"heuristic:{component}:v1",
            }
            for component in AI_POLICY_COMPONENTS
        },
        "fallbacks": {
            COMPONENT_MOVEMENT_RANKER: [f"heuristic:{COMPONENT_TACTICAL_ORCHESTRATOR}:v1"],
        },
        "required_feature_schema_ids": ["feature_schema:roster_matchup_v1"],
        "required_capability_schema_ids": ["capability_schema:build_capability_v1"],
        "created_from_commit": "0123456789abcdef0123456789abcdef01234567",
    }
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    bundle = JSONPolicyBundleLoader(manifest_store=manifest_store).load_bundle(bundle_id)
    router = AIControllerRouter.from_policy_bundle(bundle)
    request = _request(
        kinds.DECISION_DECLARE_CHARGE,
        candidates=[
            CandidateAction("a", params={}, metadata={"projected_trade_ev": 1.0}),
            CandidateAction("b", params={}, metadata={"projected_trade_ev": 3.0}),
        ],
        mask=[True, True],
    )

    assert hasattr(bundle.resolve_component(COMPONENT_CHARGE_RANKER), "choose_action_id")
    assert router.choose_action(request).action_id == "b"
