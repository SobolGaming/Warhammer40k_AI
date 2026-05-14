from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.ai_orchestration_context import attach_ai_orchestration_context
from warhammer40k_ai.engine.ai_policy_orchestrator import COMPONENT_DICE_POLICY, COMPONENT_MOVEMENT_RANKER
from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT, DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.engine.decisions import DecisionRequest


class _Serializable:
    def __init__(self, **payload) -> None:
        self._payload = dict(payload)

    def to_dict(self) -> dict:
        return dict(self._payload)


class _Plan:
    plan_id = "plan:p1:r1"
    battle_round = 1
    scoring_windows = [_Serializable(window_id="next_primary")]
    priority_opportunities = [_Serializable(opportunity_id="score_mid")]
    denial_opportunities = [_Serializable(opportunity_id="deny_mid")]

    def to_dict(self) -> dict:
        return {"plan_id": self.plan_id, "battle_round": self.battle_round}


class _Task:
    compute_tier = "P0"
    movement_intent = _Serializable(intent_id="move_to_mid")

    def to_dict(self) -> dict:
        return {"unit_id": "unit:1", "compute_tier": self.compute_tier}


class _Bundle:
    cp_reserve_policy = {"reserve_for_defense": 1}
    tasks_by_unit_id = {"unit:1": _Task()}


class _Game:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.map = SimpleNamespace(
            terrain_features=[
                SimpleNamespace(id="terrain:b"),
                SimpleNamespace(id="terrain:a"),
            ]
        )
        self.selected_mission_info = {"mission_id": "mission:test"}
        self.secondary_mission_mode = "tactical"

    def get_or_create_tier1_plan(self, player_id: str):
        self.calls.append(("tier1", str(player_id)))
        return _Plan()

    def get_or_create_tier2_task_bundle(self, player_id: str):
        self.calls.append(("tier2", str(player_id)))
        return _Bundle()


def test_orchestration_context_is_copy_out_and_attaches_matching_task_context() -> None:
    game = _Game()
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move",
        player_id="p1",
        context={"unit_id": "unit:1"},
    )
    original = {"unit_id": "unit:1", "compute_tier": "bad"}

    updated = attach_ai_orchestration_context(game, request, original, COMPONENT_MOVEMENT_RANKER)

    assert updated is not original
    assert "plan_id" not in original
    assert updated["plan_id"] == "plan:p1:r1"
    assert updated["tier2_task"]["unit_id"] == "unit:1"
    assert updated["movement_intent"] == {"intent_id": "move_to_mid"}
    assert updated["cp_reserve_policy"] == {"reserve_for_defense": 1}
    assert updated["terrain_state_summary"]["terrain_ids"] == ["terrain:a", "terrain:b"]
    assert updated["compute_tier"] == "P0"
    assert game.calls == [("tier1", "p1"), ("tier2", "p1")]


def test_orchestration_context_preserves_existing_valid_compute_tier_without_matching_task() -> None:
    game = _Game()
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move",
        player_id="p1",
        context={"unit_id": "unit:missing"},
    )

    updated = attach_ai_orchestration_context(
        game,
        request,
        {"unit_id": "unit:missing", "compute_tier": "P2"},
        COMPONENT_MOVEMENT_RANKER,
    )

    assert "tier2_task" not in updated
    assert updated["compute_tier"] == "P2"


def test_orchestration_context_excludes_dice_policy_and_normalizes_compute_tier() -> None:
    game = _Game()
    request = DecisionRequest.create(
        DECISION_REQUEST_DICE_ROLL,
        "Roll",
        player_id="p1",
        context={"compute_tier": "unknown"},
    )

    updated = attach_ai_orchestration_context(game, request, {"compute_tier": "unknown"}, COMPONENT_DICE_POLICY)

    assert "plan_id" not in updated
    assert "turn_plan" not in updated
    assert updated["compute_tier"] == "P1"
    assert game.calls == []
