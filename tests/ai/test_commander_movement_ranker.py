from __future__ import annotations

from warhammer40k_ai.engine.ai_component_rankers import default_ai_component_rankers, legal_candidates
from warhammer40k_ai.engine.ai_policy_orchestrator import COMPONENT_MOVEMENT_RANKER
from warhammer40k_ai.engine.candidate_semantics import ensure_candidate_semantic_metadata
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_MOVEMENT_ACTION
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest


def _movement_ranker():
    return default_ai_component_rankers()[COMPONENT_MOVEMENT_RANKER]


def _movement_request(
    *,
    context: dict,
    candidates: list[CandidateAction],
) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_SELECT_MOVEMENT_ACTION,
        "Choose movement action",
        player_id="p1",
        options=[
            DecisionOption.create("Move", payload={"action_type": "move"}),
            DecisionOption.create("Advance", payload={"action_type": "advance"}),
            DecisionOption.create("Stationary", payload={"action_type": "stationary"}),
        ],
        candidates=candidates,
        mask=[True] * len(candidates),
        context={
            "phase_name": "MOVEMENT_PHASE",
            "phase_step": "MOVE_UNITS",
            **dict(context or {}),
        },
    )


def _candidate(action_id: str, *, action_type: str, metadata: dict | None = None) -> CandidateAction:
    return CandidateAction(
        action_id=action_id,
        params={"action_type": action_type},
        metadata=dict(metadata or {}),
    )


def _normalize(request: DecisionRequest) -> DecisionRequest:
    ensure_candidate_semantic_metadata(request, rules_bundle_id="rules_bundle:test")
    return request


def test_shooting_first_unit_penalizes_advance_when_it_loses_shooting_eligibility() -> None:
    request = _normalize(
        _movement_request(
            context={
                "unit_battle_task": {
                    "role": "shooting_first",
                    "forbidden_movement_actions": ["advance"],
                },
                "commander_movement_task": {
                    "desired_action": "normal_move",
                    "avoid_becoming_shooting_ineligible": True,
                },
                "commander_fire_assignment": {"primary_target_unit_id": "target:tank"},
            },
            candidates=[
                _candidate("advance", action_type="advance"),
                _candidate("move", action_type="move"),
            ],
        )
    )

    by_id = {candidate.action_id: dict(candidate.metadata or {}) for candidate in request.candidates}

    assert _movement_ranker().choose_action_id(request) == "move"
    assert by_id["advance"]["commander_action_violation"] == 1.0
    assert (
        by_id["advance"]["commander_task_alignment"]
        < by_id["move"]["commander_task_alignment"]
    )
    assert len(legal_candidates(request)) == 2


def test_melee_first_unit_rewards_advance_when_shooting_ineligibility_is_intentional() -> None:
    request = _normalize(
        _movement_request(
            context={
                "unit_battle_task": {"role": "melee_first"},
                "commander_movement_task": {
                    "desired_action": "advance",
                    "intentionally_accept_shooting_ineligible": True,
                    "charge_staging_target_unit_id": "target:charge",
                },
                "commander_charge_assignment": {
                    "primary_target_unit_id": "target:charge",
                    "desired_charge_probability": 0.65,
                },
            },
            candidates=[
                _candidate(
                    "advance",
                    action_type="advance",
                    metadata={"charge_staging_target_unit_ids": ["target:charge"]},
                ),
                _candidate("move", action_type="move"),
            ],
        )
    )

    by_id = {candidate.action_id: dict(candidate.metadata or {}) for candidate in request.candidates}

    assert _movement_ranker().choose_action_id(request) == "advance"
    assert by_id["advance"]["commander_intentional_shooting_ineligible"] == 1.0
    assert by_id["advance"]["commander_charge_lane_score"] == 1.0
    assert (
        by_id["advance"]["commander_task_alignment"]
        > by_id["move"]["commander_task_alignment"]
    )


def test_required_los_target_adds_positive_commander_alignment() -> None:
    request = _normalize(
        _movement_request(
            context={
                "commander_movement_task": {
                    "desired_action": "normal_move",
                    "required_los_to_unit_ids": ["target:visible"],
                },
                "commander_fire_assignment": {
                    "primary_target_unit_id": "target:visible",
                    "expected_damage_by_target": {"target:visible": 4.0},
                },
            },
            candidates=[
                _candidate("no_los", action_type="move", metadata={"visible_target_unit_ids": []}),
                _candidate(
                    "has_los",
                    action_type="move",
                    metadata={"visible_target_unit_ids": ["target:visible"]},
                ),
            ],
        )
    )

    by_id = {candidate.action_id: dict(candidate.metadata or {}) for candidate in request.candidates}

    assert _movement_ranker().choose_action_id(request) == "has_los"
    assert by_id["has_los"]["commander_required_los_satisfied"] == 1.0
    assert by_id["has_los"]["commander_task_alignment"] > by_id["no_los"]["commander_task_alignment"]


def test_generic_half_range_band_adds_positive_commander_alignment() -> None:
    request = _normalize(
        _movement_request(
            context={
                "commander_movement_task": {
                    "desired_action": "normal_move",
                    "desired_range_bands": [
                        {
                            "target_unit_id": "target:melta",
                            "minimum_inches": 0.0,
                            "maximum_inches": 6.0,
                            "trigger_kind": "generic_half_range",
                        }
                    ],
                },
                "commander_fire_assignment": {"primary_target_unit_id": "target:melta"},
            },
            candidates=[
                _candidate(
                    "outside_band",
                    action_type="move",
                    metadata={"range_to_unit_inches_by_id": {"target:melta": 9.0}},
                ),
                _candidate(
                    "inside_band",
                    action_type="move",
                    metadata={"range_to_unit_inches_by_id": {"target:melta": 5.5}},
                ),
            ],
        )
    )

    by_id = {candidate.action_id: dict(candidate.metadata or {}) for candidate in request.candidates}

    assert _movement_ranker().choose_action_id(request) == "inside_band"
    assert by_id["inside_band"]["commander_desired_range_band_satisfied"] == 1.0
    assert (
        by_id["inside_band"]["commander_task_alignment"]
        > by_id["outside_band"]["commander_task_alignment"]
    )


def test_forbidden_movement_action_receives_negative_score_without_masking() -> None:
    request = _normalize(
        _movement_request(
            context={
                "unit_battle_task": {"forbidden_movement_actions": ["advance"]},
                "commander_movement_task": {"desired_action": "advance"},
            },
            candidates=[
                _candidate("advance", action_type="advance"),
                _candidate("move", action_type="move"),
            ],
        )
    )

    by_id = {candidate.action_id: dict(candidate.metadata or {}) for candidate in request.candidates}

    assert _movement_ranker().choose_action_id(request) == "move"
    assert by_id["advance"]["commander_action_violation"] == 1.0
    assert [candidate.action_id for candidate in legal_candidates(request)] == ["advance", "move"]


def test_dirty_movement_commander_scope_reduces_alignment() -> None:
    base_context = {
        "commander_movement_task": {
            "desired_action": "normal_move",
            "required_los_to_unit_ids": ["target:visible"],
        },
        "commander_fire_assignment": {"primary_target_unit_id": "target:visible"},
    }
    clean = _normalize(
        _movement_request(
            context={**base_context, "commander_replan_scope": "none"},
            candidates=[
                _candidate(
                    "has_los",
                    action_type="move",
                    metadata={"visible_target_unit_ids": ["target:visible"]},
                ),
            ],
        )
    )
    dirty = _normalize(
        _movement_request(
            context={
                **base_context,
                "commander_replan_scope": "movement_only",
                "commander_dirty_flags": {"movement_plan_dirty": True},
            },
            candidates=[
                _candidate(
                    "has_los",
                    action_type="move",
                    metadata={"visible_target_unit_ids": ["target:visible"]},
                ),
            ],
        )
    )

    clean_alignment = float(clean.candidates[0].metadata["commander_task_alignment"])
    dirty_alignment = float(dirty.candidates[0].metadata["commander_task_alignment"])

    assert dirty.candidates[0].metadata["commander_plan_stale_penalty"] == 1.0
    assert dirty_alignment < clean_alignment


def test_unsatisfied_commander_intent_still_falls_back_to_local_movement_score() -> None:
    request = _normalize(
        _movement_request(
            context={
                "commander_movement_task": {
                    "desired_action": "normal_move",
                    "required_los_to_unit_ids": ["target:missing"],
                },
            },
            candidates=[
                _candidate(
                    "low_local",
                    action_type="move",
                    metadata={"projected_score_delta_next_window": 0.1},
                ),
                _candidate(
                    "high_local",
                    action_type="move",
                    metadata={"projected_score_delta_next_window": 2.0},
                ),
            ],
        )
    )

    by_id = {candidate.action_id: dict(candidate.metadata or {}) for candidate in request.candidates}

    assert _movement_ranker().choose_action_id(request) == "high_local"
    assert by_id["low_local"]["commander_task_alignment"] == by_id["high_local"]["commander_task_alignment"]
